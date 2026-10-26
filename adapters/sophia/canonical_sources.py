"""DIO-owned, digest-bound diagnostic service loading; no sibling source fallback."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ORGAN_ROOT = ROOT / "cross_folder_variants/Integritas-Mechanicus/A_CODE"
SERVICES = ORGAN_ROOT / "arda_os/backend/services"
SOURCE_PINS = {'response_evidence': 'ed986339db9db4b8d64d29fb835d4c6a6c27ed62fe0e7a5da673c651bd87cf31', 'sophia_custody': '69723ce23ea5424ef8c5ef8af1d7017dd3c1989485006151679aafdd74704c7a', 'mandos_sophia_adapter': '45246d9f1c921c3ab738b4156744536c60b59de45586b17a01ca1357a9dab20e', 'mandos_protocol_judge': '9e0d96220f91f0be713fb33a157143794ee02ed92d55ca9352cc3b3ba649776c'}


def load_service(name: str):
    if name not in SOURCE_PINS:
        raise ValueError("REFUSE: unknown_canonical_service")
    path = SERVICES / (name + ".py")
    if not path.is_file():
        raise FileNotFoundError("REFUSE: canonical_source_missing:" + name)
    resolved = path.resolve()
    if resolved != path or not resolved.is_relative_to(ROOT):
        raise ValueError("REFUSE: canonical_source_escape:" + name)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_PINS[name]:
        raise ValueError("REFUSE: source_digest_mismatch:" + name)
    module_name = "_dio_canonical_" + name + "_" + digest[:12]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("REFUSE: canonical_source_unloadable:" + name)
    module = importlib.util.module_from_spec(spec)
    # Execute exactly the bytes checked above, without a second path read or stale pyc.
    sys.modules[module_name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module
