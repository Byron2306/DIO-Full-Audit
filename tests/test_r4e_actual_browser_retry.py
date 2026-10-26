import json
from pathlib import Path
import shutil
import subprocess
import os

import pytest


@pytest.mark.parametrize('mode', ['accepted', 'not_accepted', 'voice_accepted', 'voice_not_accepted'])
def test_actual_site_reload_recovers_or_retries_the_original_request(mode):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the actual website browser harness')
    root = Path(__file__).resolve().parents[1]
    script = Path(os.getenv('DIO_R4E_SITE_SCRIPT', str(root.parent / 'actual-site-recovery/vesper-intake.js')))
    result = subprocess.run([node, str(root / 'tests/r4e_actual_website_retry_harness.cjs'), str(script), mode],
                            check=True, capture_output=True, text=True, timeout=15)
    assert json.loads(result.stdout)['created'] == 1
