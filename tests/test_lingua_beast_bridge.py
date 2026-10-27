import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_beast_bridge_uses_configured_runtime_root(tmp_path):
    configured_root = tmp_path / "beast"
    env = dict(os.environ, DIO_BEAST_ROOT=str(configured_root))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts.lingua_beast_bridge import BEAST_ROOT; print(BEAST_ROOT)",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == str(configured_root.resolve())


def test_beast_bridge_uses_bundled_runtime_when_deployed_root_is_absent(monkeypatch):
    import scripts.lingua_beast_bridge as bridge

    monkeypatch.delenv("DIO_BEAST_ROOT", raising=False)
    monkeypatch.setattr(bridge, "ROOT", ROOT)
    monkeypatch.setattr(bridge.Path, "is_dir", lambda path: False if str(path) == "/home/byron/EdgeK-BEAST" else Path.is_dir(path))
    assert bridge.resolve_beast_root() == (ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE").resolve()
