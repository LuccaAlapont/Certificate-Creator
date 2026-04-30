"""Google Drive upload via OAuth2 (user's own account — no quota issues)."""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).parent.parent.parent
CREDS_PATH  = BASE_DIR / "gdrive-credentials.json"   # OAuth2 client JSON
TOKEN_PATH  = BASE_DIR / "gdrive-token.json"          # saved access/refresh tokens
CONFIG_PATH = BASE_DIR / "gdrive-config.json"

SCOPES       = ["https://www.googleapis.com/auth/drive"]
REDIRECT_URI = "http://localhost:8001/api/drive/oauth-callback"

def _client_type() -> str:
    """Return 'web' or 'installed' based on uploaded credentials file."""
    if not CREDS_PATH.exists():
        return "web"
    try:
        data = json.loads(CREDS_PATH.read_text(encoding="utf-8"))
        return "web" if "web" in data else "installed"
    except Exception:
        return "web"

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Pacotes Google não instalados. Drive desabilitado.")

_pending_flow: Optional[object] = None


# ── Config ────────────────────────────────────────────────────────────────────

def _read_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}

def _write_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

def get_root_folder_id() -> Optional[str]:
    return _read_config().get("root_folder_id") or None

def get_year() -> str:
    import datetime
    return _read_config().get("year") or str(datetime.datetime.now().year)

def set_config(folder_id: str, year: str):
    cfg = _read_config()
    cfg["root_folder_id"] = folder_id.strip()
    cfg["year"] = year.strip()
    _write_config(cfg)


# ── OAuth2 ────────────────────────────────────────────────────────────────────

def _get_credentials() -> Optional["Credentials"]:
    if not TOKEN_PATH.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        return creds if (creds and creds.valid) else None
    except Exception as e:
        logger.warning(f"Erro ao carregar credenciais OAuth2: {e}")
        return None

def is_authorized() -> bool:
    return AVAILABLE and bool(_get_credentials())

def is_configured() -> bool:
    return is_authorized() and bool(get_root_folder_id())

def _make_flow() -> "Flow":
    redirect = REDIRECT_URI
    return Flow.from_client_secrets_file(
        str(CREDS_PATH), scopes=SCOPES, redirect_uri=redirect,
    )

def get_auth_url() -> str:
    global _pending_flow
    _pending_flow = _make_flow()
    url, _ = _pending_flow.authorization_url(prompt="consent", access_type="offline")
    return url

def handle_oauth_callback(code: str):
    global _pending_flow
    if _pending_flow is None:
        _pending_flow = _make_flow()
    _pending_flow.fetch_token(code=code)
    TOKEN_PATH.write_text(_pending_flow.credentials.to_json(), encoding="utf-8")
    _pending_flow = None

def revoke():
    TOKEN_PATH.unlink(missing_ok=True)


# ── Drive helpers ─────────────────────────────────────────────────────────────

def _service():
    creds = _get_credentials()
    if not creds:
        raise RuntimeError("Não autorizado. Faça login com o Google primeiro.")
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _find_or_create_folder(svc, name: str, parent_id: str) -> str:
    safe = name.replace("'", "\\'")
    q = (f"name='{safe}' and mimeType='application/vnd.google-apps.folder' "
         f"and '{parent_id}' in parents and trashed=false")
    res = svc.files().list(q=q, fields="files(id)", pageSize=1,
                           supportsAllDrives=True,
                           includeItemsFromAllDrives=True).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    return svc.files().create(body=meta, fields="id", supportsAllDrives=True).execute()["id"]


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_certificates(output_path: Path, category: str, variant: str, progress_cb=None) -> dict:
    """Extract ZIP (or single PDF) and upload each file to Drive under the user's account."""
    if not AVAILABLE:
        raise RuntimeError("Pacotes Google não instalados.")
    if not is_configured():
        raise RuntimeError("Drive não configurado ou não autorizado.")

    import zipfile, mimetypes, io
    from googleapiclient.http import MediaIoBaseUpload

    svc       = _service()
    root_id   = get_root_folder_id()
    var_label = "PROFISSIONAIS DE SAÚDE" if variant == "verde" else "MÉDICOS"

    year_id = _find_or_create_folder(svc, get_year(), root_id)
    cat_id  = _find_or_create_folder(svc, (category or "Sem Categoria").upper(), year_id)
    var_id  = _find_or_create_folder(svc, var_label, cat_id)
    folder_link = f"https://drive.google.com/drive/folders/{var_id}"

    errors = []
    uploaded = 0

    if zipfile.is_zipfile(str(output_path)):
        with zipfile.ZipFile(str(output_path)) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            total = len(names)
            for i, name in enumerate(names):
                try:
                    data  = zf.read(name)
                    mime  = mimetypes.guess_type(name)[0] or "application/octet-stream"
                    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime)
                    svc.files().create(
                        body={"name": name, "parents": [var_id]},
                        media_body=media, fields="id",
                        supportsAllDrives=True,
                    ).execute()
                    uploaded += 1
                except Exception as e:
                    logger.error(f"Drive: erro ao enviar '{name}': {e}")
                    errors.append({"name": name, "reason": str(e)})
                if progress_cb:
                    progress_cb(i + 1, total)
    else:
        total = 1
        try:
            media = MediaFileUpload(str(output_path), mimetype="application/pdf", resumable=True)
            svc.files().create(
                body={"name": output_path.name, "parents": [var_id]},
                media_body=media, fields="id",
                supportsAllDrives=True,
            ).execute()
            uploaded = 1
        except Exception as e:
            errors.append({"name": output_path.name, "reason": str(e)})
        if progress_cb:
            progress_cb(1, 1)

    logger.info(f"Drive: {uploaded}/{total} enviados → {folder_link}")
    return {"uploaded": uploaded, "total": total, "errors": errors, "folder_link": folder_link}
