from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (
    ROOT
    / "cross_folder_variants"
    / "Evidex"
    / "A_CODE"
    / "src"
    / "evidence_pack_engine"
    / "epistemic_authority.py"
)


def test_evidex_bridge_loads_shared_dio_epistemic_spine(monkeypatch) -> None:
    monkeypatch.setenv("DIO_ROOT", str(ROOT))
    module_name = "evidence_pack_engine.epistemic_authority"
    spec = importlib.util.spec_from_file_location(module_name, BRIDGE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    spine = module._load_spine()

    assert spine.__name__ == "scripts.dio_epistemic_spine"
    assert spine.claim_epistemic_state(support_count=1) == "SUPPORTED"
