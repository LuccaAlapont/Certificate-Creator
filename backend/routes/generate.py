"""Batch certificate generation with background thread + progress polling."""
import io
import re
import uuid
import zipfile
import logging
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.database import get_template, get_verso_for
from backend.services.name_parser import parse_names_from_text, parse_names_from_file
from backend.services.image_gen import render_certificate, render_certificate_pil

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR      = Path(__file__).parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR   = BASE_DIR / "outputs"

VALID_FORMATS = {"png", "jpeg_cmyk", "pdf", "pdf_combined"}

_EXT = {"png": ".png", "jpeg_cmyk": ".jpg", "pdf": ".pdf", "pdf_combined": ".pdf"}
_MIME = {
    "png":          "application/zip",
    "jpeg_cmyk":    "application/zip",
    "pdf":          "application/zip",
    "pdf_combined": "application/pdf",
}

# In-memory job store  {job_id: {...}}
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _new_job() -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending", "progress": 0, "total": 0,
            "alerts": [], "output_path": None, "output_format": "png",
            "category": "", "variant": "",
        }
    return job_id


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        _jobs[job_id].update(kwargs)


# ── Preview ───────────────────────────────────────────────────────────────────

class PreviewRequest(BaseModel):
    template_id: int
    name: str


@router.post("/preview")
def preview_certificate(req: PreviewRequest):
    t = get_template(req.template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")

    img_path = TEMPLATES_DIR / t["filename"]
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo do modelo não encontrado.")

    try:
        img_bytes, _ = render_certificate(img_path, req.name, t["config"], output_format="png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(io.BytesIO(img_bytes), media_type="image/png")


# ── Generate via text ─────────────────────────────────────────────────────────

class GenerateTextRequest(BaseModel):
    template_id:   int
    names_text:    str
    output_format: str = "png"


@router.post("/generate/text")
def generate_from_text(req: GenerateTextRequest):
    t = get_template(req.template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")

    fmt = req.output_format if req.output_format in VALID_FORMATS else "png"
    names = parse_names_from_text(req.names_text)
    if not names:
        raise HTTPException(status_code=400, detail="Nenhum nome encontrado na lista.")

    job_id = _new_job()
    threading.Thread(target=_run_batch, args=(job_id, t, names, fmt), daemon=True).start()
    return JSONResponse({"job_id": job_id, "total": len(names), "output_format": fmt})


# ── Generate via spreadsheet ──────────────────────────────────────────────────

@router.post("/generate/spreadsheet")
async def generate_from_spreadsheet(
    template_id:   int = Form(...),
    column_index:  int = Form(0),
    has_header:    bool = Form(True),
    output_format: str = Form("png"),
    file: UploadFile = File(...),
):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")

    fmt = output_format if output_format in VALID_FORMATS else "png"
    ext = Path(file.filename).suffix.lower()
    if ext not in {".xlsx", ".csv"}:
        raise HTTPException(status_code=400, detail="Use arquivo .xlsx ou .csv.")

    file_bytes = await file.read()
    try:
        names = parse_names_from_file(file_bytes, ext, column_index, has_header)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler planilha: {e}")

    if not names:
        raise HTTPException(status_code=400, detail="Nenhum nome encontrado na planilha.")

    job_id = _new_job()
    threading.Thread(target=_run_batch, args=(job_id, t, names, fmt), daemon=True).start()
    return JSONResponse({"job_id": job_id, "total": len(names), "output_format": fmt})


# ── Spreadsheet preview (first 10 rows) ──────────────────────────────────────

@router.post("/spreadsheet/peek")
async def peek_spreadsheet(
    column_index: int = Form(0),
    has_header: bool = Form(True),
    file: UploadFile = File(...),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in {".xlsx", ".csv"}:
        raise HTTPException(status_code=400, detail="Use arquivo .xlsx ou .csv.")
    file_bytes = await file.read()
    try:
        names = parse_names_from_file(file_bytes, ext, column_index, has_header)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler planilha: {e}")
    return JSONResponse({"preview": names[:10], "total": len(names)})


# ── Job polling ───────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
def poll_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return JSONResponse(job)


# ── Download ──────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}/download")
def download_output(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=404, detail="Arquivo ainda não disponível.")

    out_path = Path(job["output_path"])
    if not out_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    fmt  = job.get("output_format", "png")
    mime = _MIME.get(fmt, "application/octet-stream")

    variant_label = "Profissionais" if job.get("variant") == "verde" else "Médicos"
    category      = re.sub(r'[\\/:*?"<>|]', "", job.get("category", "") or "Certificados").strip() or "Certificados"
    ext           = ".pdf" if fmt == "pdf_combined" else ".zip"
    filename      = f"{variant_label} - {category}{ext}"

    def iterfile():
        with open(out_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    ascii_name = filename.encode("ascii", errors="replace").decode("ascii")
    utf8_name  = quote(filename, safe=" -.()")
    return StreamingResponse(
        iterfile(),
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"},
    )


# ── Batch worker ──────────────────────────────────────────────────────────────

def _run_batch(job_id: str, template: dict, names: list[str], output_format: str):
    _update_job(job_id, status="running", total=len(names), output_format=output_format,
                category=template.get("category", ""), variant=template.get("variant", ""))
    img_path = TEMPLATES_DIR / template["filename"]
    config   = template["config"]
    alerts   = []
    seen: dict[str, int] = {}
    ext = _EXT.get(output_format, ".png")

    # Fetch the matching verso (same category + variant) for PDF formats
    verso_path: Path | None = None
    if output_format in {"pdf", "pdf_combined"}:
        verso = get_verso_for(template.get("category", ""), template.get("variant", ""))
        if verso:
            verso_path = TEMPLATES_DIR / verso["filename"]
            if not verso_path.exists():
                verso_path = None

    try:
        if output_format == "pdf_combined":
            _run_batch_pdf_combined(job_id, img_path, config, names, alerts, seen, verso_path)
        else:
            _run_batch_zip(job_id, img_path, config, names, alerts, seen, output_format, ext, verso_path)

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}", exc_info=True)
        _update_job(job_id, status="error", alerts=[{"name": "—", "reason": str(e)}])


def _load_verso_pil(verso_path: "Path | None") -> "PILImage.Image | None":
    if not verso_path:
        return None
    from PIL import Image as PILImage
    img = PILImage.open(str(verso_path))
    if img.mode in ("RGBA", "LA", "P"):
        bg = PILImage.new("RGB", img.size, (255, 255, 255))
        alpha = img.convert("RGBA").split()[3]
        bg.paste(img.convert("RGB"), mask=alpha)
        return bg
    return img.convert("RGB")


def _run_batch_zip(job_id, img_path, config, names, alerts, seen, output_format, ext, verso_path):
    from PIL import Image as PILImage

    verso_pil = _load_verso_pil(verso_path) if output_format == "pdf" else None
    zip_path  = OUTPUTS_DIR / f"{job_id}.zip"

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for i, name in enumerate(names):
            try:
                seen[name] = seen.get(name, 0) + 1
                count = seen[name]
                fname = f"{name}{ext}" if count == 1 else f"{name} ({count}){ext}"

                if output_format == "pdf" and verso_pil:
                    # Build 2-page PDF: front + verso
                    front_pil, font_reduced = render_certificate_pil(img_path, name, config)
                    buf = io.BytesIO()
                    front_pil.save(buf, format="PDF", resolution=300,
                                   save_all=True, append_images=[verso_pil])
                    img_bytes = buf.getvalue()
                else:
                    img_bytes, font_reduced = render_certificate(img_path, name, config, output_format)

                zf.writestr(fname, img_bytes)
                if font_reduced:
                    alerts.append({"name": name, "reason": "fonte reduzida para caber"})
            except Exception as e:
                logger.error(f"Erro '{name}': {e}")
                alerts.append({"name": name, "reason": str(e)})
            _update_job(job_id, progress=i + 1)

    _update_job(job_id, status="done", output_path=str(zip_path), alerts=alerts)


def _run_batch_pdf_combined(job_id, img_path, config, names, alerts, seen, verso_path):
    from PIL import Image as PILImage

    verso_pil = _load_verso_pil(verso_path)
    pdf_path  = OUTPUTS_DIR / f"{job_id}.pdf"
    pages: list[PILImage.Image] = []

    for i, name in enumerate(names):
        try:
            pil_img, font_reduced = render_certificate_pil(img_path, name, config)
            pages.append(pil_img)
            if verso_pil:
                pages.append(verso_pil.copy())
            if font_reduced:
                alerts.append({"name": name, "reason": "fonte reduzida para caber"})
        except Exception as e:
            logger.error(f"Erro '{name}': {e}")
            alerts.append({"name": name, "reason": str(e)})
        _update_job(job_id, progress=i + 1)

    if not pages:
        raise RuntimeError("Nenhuma página gerada.")

    pages[0].save(
        str(pdf_path), format="PDF", resolution=300,
        save_all=True, append_images=pages[1:],
    )
    _update_job(job_id, status="done", output_path=str(pdf_path), alerts=alerts)


