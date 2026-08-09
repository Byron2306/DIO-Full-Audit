import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    probe_file = path / f".seraph-write-probe-{os.getpid()}"
    try:
        with open(probe_file, "w", encoding="utf-8") as probe:
            probe.write("ok")
    except OSError:
        return False
    finally:
        try:
            probe_file.unlink()
        except OSError:
            pass

    return True


def ensure_data_dir(*parts: str) -> Path:
    primary_root = Path(os.environ.get("SERAPH_DATA_DIR", "/var/lib/anti-ai-defense"))
    fallback_root = Path(os.environ.get("SERAPH_DATA_FALLBACK", "/tmp/anti-ai-defense"))

    primary_path = primary_root.joinpath(*parts) if parts else primary_root
    if _is_writable_directory(primary_path):
        return primary_path

    fallback_path = fallback_root.joinpath(*parts) if parts else fallback_root
    if _is_writable_directory(fallback_path):
        logger.warning(
            "Using fallback data path %s because primary path is not writable: %s",
            fallback_path,
            primary_path,
        )
        return fallback_path

    message = (
        f"No writable data directory available. Tried primary '{primary_path}' "
        f"and fallback '{fallback_path}'."
    )
    logger.error(message)
    raise PermissionError(message)