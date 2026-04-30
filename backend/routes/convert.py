"""Image → PDF converter (standalone utility)."""
import io
import zipfile
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _to_rgb(file_bytes: bytes, filename: str) -> "Image.Image":
    from PIL import Image
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        return bg
    return img.convert("RGB")


@router.post("/convert/images-to-pdf")
async def images_to_pdf(
    files: list[UploadFile] = File(...),
    combined: bool = Form(True),
):
    if not files:
        raise HTTPException(status_code=400, detail="Envie ao menos uma imagem.")

    images: list[tuple[str, bytes]] = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato não suportado: {f.filename}. Use PNG, JPG, WEBP, BMP ou TIFF.",
            )
        images.append((Path(f.filename).stem, await f.read()))

    if not images:
        raise HTTPException(status_code=400, detail="Nenhuma imagem válida encontrada.")

    try:
        if combined:
            return _respond_combined(images)
        else:
            return _respond_zip(images)
    except Exception as e:
        logger.error(f"Conversão falhou: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro na conversão: {e}")


def _respond_combined(images: list[tuple[str, bytes]]) -> StreamingResponse:
    pages = [_to_rgb(data, name) for name, data in images]
    buf = io.BytesIO()
    pages[0].save(
        buf, format="PDF", resolution=300,
        save_all=True, append_images=pages[1:],
    )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="imagens_combinadas.pdf"'},
    )


def _respond_zip(images: list[tuple[str, bytes]]) -> StreamingResponse:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        seen: dict[str, int] = {}
        for name, data in images:
            page = _to_rgb(data, name)
            pdf_buf = io.BytesIO()
            page.save(pdf_buf, format="PDF", resolution=300)

            seen[name] = seen.get(name, 0) + 1
            count = seen[name]
            fname = f"{name}.pdf" if count == 1 else f"{name} ({count}).pdf"
            zf.writestr(fname, pdf_buf.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="pdfs_individuais.zip"'},
    )
