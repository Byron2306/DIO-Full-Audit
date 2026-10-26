from __future__ import annotations

import os
from pathlib import Path

from scripts.install_edge_tts_provider_adapter import install_adapter, probe_adapter


def test_provider_adapter_removes_python_no_user_site_only_for_edge_child(tmp_path: Path) -> None:
    real = tmp_path / "real-edge-tts"
    real.write_text(
        "#!/bin/sh\n"
        "if [ \"${PYTHONNOUSERSITE+x}\" = x ]; then echo inherited; exit 9; fi\n"
        "echo edge-tts-test 1.0\n",
        encoding="utf-8",
    )
    real.chmod(0o755)
    foundry = tmp_path / "NicheFoundry"
    foundry.mkdir()

    adapter = install_adapter(foundry, real)
    assert adapter == (foundry / ".venv-voicebox" / "bin" / "edge-tts").resolve()
    assert os.access(adapter, os.X_OK)

    probe = probe_adapter(adapter)
    assert probe["python_no_user_site_was_set_for_probe"] is True
    assert probe["passed"] is True
    assert probe["returncode"] == 0
    assert "edge-tts-test 1.0" in str(probe["output"])


def test_adapter_delegates_arguments_unchanged(tmp_path: Path) -> None:
    real = tmp_path / "real-edge-tts"
    real.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    real.chmod(0o755)
    foundry = tmp_path / "NicheFoundry"
    foundry.mkdir()
    adapter = install_adapter(foundry, real)

    body = adapter.read_text(encoding="utf-8")
    assert "unset PYTHONNOUSERSITE" in body
    assert '"$@"' in body
    assert str(real.resolve()) in body
