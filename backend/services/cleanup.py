"""Automatic cleanup of old output files."""
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 3600  # verifica a cada 1 hora


def _delete_old_files(outputs_dir: Path, max_age_days: int):
    if not outputs_dir.exists():
        return
    cutoff = time.time() - max_age_days * 86400
    deleted = 0
    for f in outputs_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"Cleanup: não foi possível deletar {f.name}: {e}")
    if deleted:
        logger.info(f"Cleanup: {deleted} arquivo(s) removido(s) de '{outputs_dir}' (>{max_age_days} dias)")


def start_cleanup_scheduler(outputs_dir: Path, max_age_days: int = 7):
    """Start a background thread that periodically deletes old output files."""

    def _loop():
        while True:
            try:
                _delete_old_files(outputs_dir, max_age_days)
            except Exception as e:
                logger.error(f"Cleanup scheduler error: {e}", exc_info=True)
            time.sleep(_CHECK_INTERVAL_SECONDS)

    _delete_old_files(outputs_dir, max_age_days)  # roda imediatamente ao iniciar

    t = threading.Thread(target=_loop, daemon=True, name="cleanup-scheduler")
    t.start()
    logger.info(f"Cleanup scheduler iniciado: outputs com mais de {max_age_days} dia(s) serão deletados.")
