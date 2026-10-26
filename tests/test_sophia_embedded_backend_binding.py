from pathlib import Path

import pytest

from adapters.sophia.review_pipeline import bind_sophia_backend


ROOT = Path(__file__).resolve().parents[1]

SOPHIA_ROOT = (
    ROOT / "cross_folder_variants/Integritas-Mechanicus/A_CODE"
)


def test_embedded_sophia_backend_binding():
    import importlib

    bind_sophia_backend(SOPHIA_ROOT)

    modules = (
        "academic_retrieval",
        "sophia_academic_claim_tools",
        "sophia_source_support",
    )

    for name in modules:
        module = importlib.import_module(f"backend.services.{name}")
        assert Path(module.__file__).resolve().is_relative_to(
            SOPHIA_ROOT.resolve()
        )


def test_missing_sophia_runtime_refused(tmp_path):
    with pytest.raises(FileNotFoundError, match="REFUSE"):
        bind_sophia_backend(tmp_path)
