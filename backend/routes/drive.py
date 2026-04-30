"""Google Drive integration endpoints (OAuth2)."""
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from backend.services import gdrive
from backend.routes.generate import _jobs, _jobs_lock

logger = logging.getLogger(__name__)
router = APIRouter()

_drive_jobs: dict[str, dict[str, Any]] = {}
_drive_lock = threading.Lock()


def _new_drive_job() -> str:
    jid = uuid.uuid4().hex
    with _drive_lock:
        _drive_jobs[jid] = {"status": "running", "progress": 0, "total": 0,
                             "uploaded": 0, "errors": [], "folder_link": ""}
    return jid

def _update_drive_job(jid: str, **kw):
    with _drive_lock:
        _drive_jobs[jid].update(kw)


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/drive/status")
def drive_status():
    return JSONResponse({
        "available":       gdrive.AVAILABLE,
        "has_credentials": gdrive.CREDS_PATH.exists(),
        "authorized":      gdrive.is_authorized(),
        "root_folder_id":  gdrive.get_root_folder_id(),
        "year":            gdrive.get_year(),
        "configured":      gdrive.is_configured(),
    })


# ── Credentials (OAuth2 client JSON) ─────────────────────────────────────────

@router.post("/drive/credentials")
async def save_credentials(file: UploadFile = File(...)):
    content = await file.read()
    try:
        import json
        data = json.loads(content)
        client_type = None
        if "web" in data:
            client_type = "web"
        elif "installed" in data:
            client_type = "installed"
        if not client_type:
            raise ValueError(
                "JSON inválido: precisa ser um OAuth2 Client ID (tipo 'Aplicativo da Web' ou 'App para computador'). "
                "Não use chaves de API nem credenciais de conta de serviço."
            )
        inner = data[client_type]
        if not inner.get("client_id") or not inner.get("client_secret"):
            raise ValueError("JSON OAuth2 incompleto: faltam client_id ou client_secret.")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Arquivo não é um JSON válido: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    gdrive.CREDS_PATH.write_bytes(content)
    return JSONResponse({"ok": True})


# ── OAuth2 flow ───────────────────────────────────────────────────────────────

@router.get("/drive/oauth/start")
def oauth_start():
    if not gdrive.CREDS_PATH.exists():
        raise HTTPException(400, "Faça upload das credenciais OAuth2 primeiro.")
    try:
        url = gdrive.get_auth_url()
    except Exception as e:
        logger.error(f"OAuth start error: {e}", exc_info=True)
        raise HTTPException(400, f"Erro ao gerar URL de autorização: {e}. Verifique se o JSON é do tipo 'Aplicativo da Web'.")
    return RedirectResponse(url)

@router.get("/drive/oauth-callback")
def oauth_callback(code: str):
    try:
        gdrive.handle_oauth_callback(code)
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        raise HTTPException(500, f"Erro na autorização: {e}")
    return RedirectResponse("http://localhost:8001/?drive=ok")

@router.post("/drive/revoke")
def revoke_oauth():
    gdrive.revoke()
    return JSONResponse({"ok": True})


# ── Config ────────────────────────────────────────────────────────────────────

class FolderConfig(BaseModel):
    root_folder_id: str
    year: str = ""

@router.post("/drive/config")
def save_config(body: FolderConfig):
    fid = body.root_folder_id.strip()
    if not fid:
        raise HTTPException(status_code=400, detail="ID da pasta não pode ser vazio.")
    import datetime
    year = body.year.strip() or str(datetime.datetime.now().year)
    gdrive.set_config(fid, year)
    return JSONResponse({"ok": True})


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadRequest(BaseModel):
    job_id:   str
    category: str
    variant:  str

@router.post("/drive/upload")
def upload_to_drive(req: UploadRequest):
    if not gdrive.is_configured():
        raise HTTPException(status_code=400, detail="Drive não configurado ou não autorizado.")

    with _jobs_lock:
        gen_job = _jobs.get(req.job_id)
    if not gen_job or gen_job["status"] != "done":
        raise HTTPException(status_code=404, detail="Job de geração não encontrado.")

    file_path = Path(gen_job["output_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo de saída não encontrado.")

    drive_jid = _new_drive_job()

    def _run():
        try:
            def on_progress(done, total):
                _update_drive_job(drive_jid, progress=done, total=total)
            result = gdrive.upload_certificates(file_path, req.category, req.variant, on_progress)
            _update_drive_job(drive_jid, status="done", **result)
        except Exception as e:
            logger.error(f"Drive job {drive_jid} failed: {e}", exc_info=True)
            _update_drive_job(drive_jid, status="error",
                              errors=[{"name": "—", "reason": str(e)}])

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"drive_job_id": drive_jid})

@router.get("/drive/jobs/{drive_job_id}")
def poll_drive_job(drive_job_id: str):
    with _drive_lock:
        job = _drive_jobs.get(drive_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Drive job não encontrado.")
    return JSONResponse(job)
