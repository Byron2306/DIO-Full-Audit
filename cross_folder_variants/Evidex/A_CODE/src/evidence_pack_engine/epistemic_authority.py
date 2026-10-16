from __future__ import annotations

import importlib
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
    root_string = str(root)
    if root_string not in sys.path:
        sys.path.insert(0, root_string)

    spine = importlib.import_module("scripts.dio_epistemic_spine")
    if not callable(getattr(spine, "claim_epistemic_state", None)):
        raise RuntimeError("DIO epistemic spine lacks claim_epistemic_state")
    if not callable(getattr(spine, "epistemic_tokens", None)):
        raise RuntimeError("DIO epistemic spine lacks epistemic_tokens")
    return spine


def __getattr__(name: str) -> Any:
    return getattr(_load_spine(), name)
