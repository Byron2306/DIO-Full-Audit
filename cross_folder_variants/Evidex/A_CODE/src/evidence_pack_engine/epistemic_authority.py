from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_spine() -> ModuleType:
    configured_root = (
        os.environ.get("DIO_ROOT")
        or os.environ.get("DIO_REPO_ROOT")
        or os.environ.get("DIO_FULL_AUDIT_ROOT")
    )
    if not configured_root:
        raise RuntimeError("DIO repository root is required for the epistemic spine")

    root = Path(configured_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"DIO repository root does not exist: {root}")
    expected_root = Path(__file__).resolve().parents[5]
    if root != expected_root:
        raise RuntimeError("DIO spine root does not match the canonical engine owner")
    spine_path = root / "scripts" / "dio_epistemic_spine.py"
    if (root / "scripts").is_symlink() or spine_path.is_symlink():
        raise RuntimeError("DIO spine source symlink refused")
    if not spine_path.is_file():
        raise FileNotFoundError("Canonical DIO epistemic spine source is missing")
    # Resolve the exact owned file, never an ambient/cached same-name package.
    spec = importlib.util.spec_from_file_location("_dio_owned_epistemic_spine", spine_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load canonical DIO epistemic spine")
    spine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(spine)
    if not callable(getattr(spine, "claim_epistemic_state", None)):
        raise RuntimeError("DIO epistemic spine lacks claim_epistemic_state")
    if not callable(getattr(spine, "epistemic_tokens", None)):
        raise RuntimeError("DIO epistemic spine lacks epistemic_tokens")
    return spine


def __getattr__(name: str) -> Any:
    return getattr(_load_spine(), name)
