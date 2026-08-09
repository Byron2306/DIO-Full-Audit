from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORLD_MANIFOLD_PATH = ROOT / "backend" / "services" / "world_manifold.py"


def test_world_manifold_uses_direct_backend_imports_for_canonical_dependencies():
    content = WORLD_MANIFOLD_PATH.read_text()

    assert "from backend.schemas.phase2_models import WorldManifoldSnapshot" in content
    assert "from backend.services.world_model import WorldModelService" in content
    assert "except Exception:\n    from backend.schemas.phase2_models" not in content


def test_world_manifold_declares_canonical_backend_authority():
    content = WORLD_MANIFOLD_PATH.read_text()

    assert "The canonical backend world-state/manifold authority path." in content
