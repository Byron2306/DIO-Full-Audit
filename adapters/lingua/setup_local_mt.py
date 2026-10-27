"""Download the pinned public MT model; never accepts customer source text."""

from __future__ import annotations
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from adapters.lingua.local_mt import (
    DEFAULT_MODEL_ROOT,
    MODEL_ID,
    MODEL_REVISION,
    verify_model,
)

FILES = (
    "README.md",
    "config.json",
    "generation_config.json",
    "pytorch_model.bin",
    "source.spm",
    "target.spm",
    "tokenizer_config.json",
    "vocab.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    args = parser.parse_args()
    destination = args.model_root.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        "repository": MODEL_ID,
        "revision": MODEL_REVISION,
        "license": "Apache-2.0",
        "files": {},
    }
    for filename in FILES:
        path = destination / filename
        temporary = destination / (filename + ".download")
        if not path.is_file():
            urllib.request.urlretrieve(
                f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{filename}",
                temporary,
            )
            temporary.replace(path)
        manifest["files"][filename] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    (destination / "DIO_MODEL_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    verify_model(destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
