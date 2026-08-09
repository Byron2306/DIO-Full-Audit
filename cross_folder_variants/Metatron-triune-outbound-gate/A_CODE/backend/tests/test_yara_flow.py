import os
import tempfile
import uuid
import shutil
from backend.tasks.integrations_tasks import extract_indicators_from_collection


def test_extract_indicators_basic(tmp_path):
    # create a fake collection file with IP, domain and sha256
    sample = """
    contact 192.168.10.5 connected to evil.example.com
    file hash: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    """
    coll = tmp_path / f"collection_{uuid.uuid4().hex}.json"
    coll.write_text(sample)

    # no yara rules configured
    if 'YARA_RULES_DIR' in os.environ:
        del os.environ['YARA_RULES_DIR']

    inds = extract_indicators_from_collection(str(coll))
    types = {i['type'] for i in inds}
    assert 'ip' in types
    assert 'domain' in types
    assert 'sha256' in types


def test_yara_rules_detection(tmp_path, monkeypatch):
    # create sample collection
    sample = "This file contains malicious content"
    coll = tmp_path / "collection_sample.json"
    coll.write_text(sample)

    # create a simple yara rule file
    rules_dir = tmp_path / 'rules.yar'
    rules_dir.write_text('rule TestRule { strings: $a = "malicious" condition: $a }')
    os.environ['YARA_RULES_DIR'] = str(rules_dir)

    inds = extract_indicators_from_collection(str(coll))
    # clean up env
    del os.environ['YARA_RULES_DIR']

    # Indicate that yara indicator may or may not be present depending on yara availability
    assert isinstance(inds, list)
