#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path


DEFAULT_FOUNDRY = Path("/home/byron/Downloads/NicheFoundry_Phase11")
VOICE_NAME = "en_US-lessac-high"
VOICE_RELATIVE_DIR = Path("assets/piper") / VOICE_NAME
VOICE_FILE = f"{VOICE_NAME}.onnx"
CONFIG_FILE = f"{VOICE_NAME}.onnx.json"
VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "en/en_US/lessac/high/en_US-lessac-high.onnx?download=true"
)
VOICE_SHA256 = "4cabf7c3a638017137f34a1516522032d4fe3f38228a843cc9b764ddcbcd9e09"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install(foundry_root: Path, *, force: bool = False) -> Path:
    target_dir = foundry_root.expanduser().resolve() / VOICE_RELATIVE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / VOICE_FILE
    config = target_dir / CONFIG_FILE

    if not config.is_file():
        raise RuntimeError(
            f"Piper config is missing: {config}. The installer will not invent or replace voice metadata."
        )

    if target.is_file() and not force:
        digest = sha256_file(target)
        if digest == VOICE_SHA256:
            print(f"PASS: Piper voice already installed and checksum verified: {target}")
            return target
        raise RuntimeError(
            f"Existing Piper model has unexpected SHA-256: {digest}. Re-run with --force only if you intend to replace it."
        )

    with tempfile.NamedTemporaryFile(
        prefix=f".{VOICE_FILE}.", suffix=".download", dir=target_dir, delete=False
    ) as handle:
        temporary = Path(handle.name)

    try:
        request = urllib.request.Request(
            VOICE_URL,
            headers={"User-Agent": "DIO-NicheFoundry-Piper-Installer/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                output.flush()
            os.fsync(output.fileno())

        digest = sha256_file(temporary)
        if digest != VOICE_SHA256:
            raise RuntimeError(
                "Downloaded Piper model failed SHA-256 verification: "
                f"expected {VOICE_SHA256}, got {digest}"
            )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()

    print(f"PASS: installed {VOICE_NAME}")
    print(f"MODEL: {target}")
    print(f"SHA256: {VOICE_SHA256}")
    print(f"CONFIG: {config}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the configured Piper Lessac high voice into the original NicheFoundry tree."
    )
    parser.add_argument("--nichefoundry-root", type=Path, default=DEFAULT_FOUNDRY)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    install(args.nichefoundry_root, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
