"""Template library: upload, list, configure, delete."""
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import (
    POS_GRADUACOES, VARIANTS,
    add_template, list_templates, get_template,
    update_config, delete_template,
)

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR      = Path(__file__).parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "uploads"
ALLOWED_EXTS  = {".png", ".jpg", ".jpeg"}

# All 4 slot keys per group
SLOT_KEYS = [
    ("azul",  False),
    ("verde", False),
    ("azul",  True),
    ("verde", True),
]


class TemplateConfig(BaseModel):
    center_x:  float = 0.5
    center_y:  float = 0.5
    max_width: float = 0.7
    font_size: int   = 200
    font_name: str   = ""
    color:     str   = "#ffffff"
    alignment: str   = "center"


@router.get("/templates/meta")
def get_meta():
    return JSONResponse({"pos_graduacoes": POS_GRADUACOES, "variants": VARIANTS})


@router.post("/templates/upload")
async def upload_template(
    file:     UploadFile = File(...),
    category: str  = Form(""),
    variant:  str  = Form(""),
    is_verso: bool = Form(False),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use PNG ou JPG.")

    filename = f"{uuid.uuid4().hex}{ext}"
    (TEMPLATES_DIR / filename).write_bytes(await file.read())

    record = add_template(filename, file.filename, category, variant, is_verso)
    logger.info(f"Upload: {filename} cat={category!r} var={variant!r} verso={is_verso}")
    return JSONResponse({"template": record})


@router.get("/templates")
def list_all_templates():
    templates = list_templates()

    grouped = []
    for pos in POS_GRADUACOES:
        slots: dict[str, dict | None] = {}
        for t in templates:
            if t["category"] != pos:
                continue
            key = f"{t['variant']}_verso" if t["is_verso"] else t["variant"]
            slots[key] = t
        # Ensure all 4 keys exist
        for variant, is_verso in SLOT_KEYS:
            key = f"{variant}_verso" if is_verso else variant
            slots.setdefault(key, None)
        grouped.append({"category": pos, "slots": slots})

    return JSONResponse({"templates": templates, "grouped": grouped})


@router.get("/templates/{template_id}")
def get_one_template(template_id: int):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    return JSONResponse({"template": t})


@router.put("/templates/{template_id}/config")
def save_config(template_id: int, cfg: TemplateConfig):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    updated = update_config(template_id, cfg.model_dump())
    return JSONResponse({"template": updated})


@router.delete("/templates/{template_id}")
def remove_template(template_id: int):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    (TEMPLATES_DIR / t["filename"]).unlink(missing_ok=True)
    delete_template(template_id)
    return JSONResponse({"ok": True})
