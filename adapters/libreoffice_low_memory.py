from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


class LibreOfficeConversionError(RuntimeError):
    pass


def _binary() -> str:
    explicit = str(os.environ.get("DIO_LIBREOFFICE_BIN") or "").strip()
    for candidate in (explicit, shutil.which("libreoffice"), "/usr/bin/libreoffice", shutil.which("soffice"), "/usr/bin/soffice"):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise LibreOfficeConversionError("LibreOffice executable is unavailable")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("SAL_USE_VCLPLUGIN", "svp")
    env.setdefault("MALLOC_ARENA_MAX", "2")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    return env


def convert_many_to_pdf(
    paths: Iterable[Path],
    out_dir: Path,
    *,
    profile_prefix: str = "dio-lo-profile-",
    timeout: int = 180,
) -> list[Path]:
    """Convert office documents to PDF one process at a time.

    Each source receives a fresh LibreOffice user profile so one large conversion
    cannot retain state or heap across the rest of a customer pack. This is
    intentionally sequential: bounded memory is more important than throughput
    on the local DIO production runtime.
    """
    sources = [Path(path).resolve() for path in paths]
    if not sources:
        return []
    for source in sources:
        if not source.is_file():
            raise LibreOfficeConversionError(f"source document is missing: {source}")

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    binary = _binary()
    produced: list[Path] = []

    for source in sources:
        with tempfile.TemporaryDirectory(prefix=profile_prefix) as profile:
            command = [
                binary,
                "--headless",
                "--nologo",
                "--nodefault",
                "--nolockcheck",
                "--norestore",
                "--nofirststartwizard",
                f"-env:UserInstallation={Path(profile).resolve().as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(source),
            ]
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
                env=_env(),
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "LibreOffice returned no diagnostics").strip()
                raise LibreOfficeConversionError(
                    f"LibreOffice PDF conversion failed for {source.name}: {detail[-1200:]}"
                )

        target = out_dir / f"{source.stem}.pdf"
        if not target.is_file() or target.stat().st_size < 200:
            raise LibreOfficeConversionError(
                f"LibreOffice reported success without a substantial PDF for {source.name}"
            )
        produced.append(target)

    return produced


__all__ = ["LibreOfficeConversionError", "convert_many_to_pdf"]
