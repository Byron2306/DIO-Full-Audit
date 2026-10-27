"""Guard the release branch's actual critical CI dispatch contracts."""
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'


def workflow(name: str) -> dict:
    return yaml.load((WORKFLOWS / name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)


@pytest.mark.parametrize(('filename', 'changed_path'), [
    ('dio-canon-extension-productgrade.yml', 'products/canon_extension_materializer.py'),
    ('dio-obligation-family-phase6.yml', 'products/obligationfamily/runner.py'),
    ('dio-customer-journey-phase4.yml', 'presence_core/fulfilment_contract.py'),
])
def test_proven_critical_lanes_run_on_integrated_source_changes(filename: str, changed_path: str):
    from fnmatch import fnmatchcase

    events = workflow(filename)['on']
    push = events['push']
    assert any(fnmatchcase('integrated/production-handoff-20261027', pattern)
               for pattern in push['branches'])
    assert any(fnmatchcase(changed_path, pattern) for pattern in push['paths'])
    assert 'pull_request' in events
    assert 'workflow_dispatch' in events


def test_phase5_test_failures_cannot_be_hidden_by_log_capture():
    job = workflow('dio-customer-journey-phase5.yml')['jobs']['phase5']
    steps = job['steps']
    test_step = next(step for step in steps if step.get('name') == 'Verify Phase 4 and Phase 5 journey contracts')
    assert '| tee' in test_step['run']
    assert 'set -o pipefail' in test_step['run']
    install = next(step['run'] for step in steps if step.get('name') == 'Install test dependencies')
    for dependency in ('fastapi', 'uvicorn', 'httpx'):
        assert dependency in install.split()
    assert int(job['timeout-minutes']) <= 15


def test_phase4_ci_installs_the_actual_document_renderer_dependencies():
    job = workflow('dio-customer-journey-phase4.yml')['jobs']['universal-fulfilment']
    install = next(step['run'] for step in job['steps'] if step.get('name') == 'Install test dependencies')
    # The exercised fulfilment path imports Format Core's DOCX, PPTX and image
    # renderers, even when the test's source document is only a held review.
    for dependency in ('python-docx', 'python-pptx', 'pillow'):
        assert dependency in install.split()
