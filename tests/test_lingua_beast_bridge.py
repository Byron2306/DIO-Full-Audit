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
