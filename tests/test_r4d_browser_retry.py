import json
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("mode", ["text", "attachments", "validation"])
def test_browser_reload_reuses_pending_identity_and_holds_changed_content(mode):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the browser retry harness")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, str(root / "tests/r4d_browser_retry_harness.cjs"),
                             str(root / "dashboard/vesper-intake.js"), mode],
                            capture_output=True, text=True, check=True, timeout=15)
    observed = json.loads(result.stdout)
    assert (observed["retry"] == observed["initial"]) is (mode != "validation")
    assert observed["totalPosts"] == 2
    assert observed["afterMissingFiles"] == (1 if mode == "attachments" else 2)
