from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_business_uses_controlled_intake_wrapper_for_homs_and_evidex():
    server = (ROOT / "scripts" / "serve_business_workbench.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "operator_evidence_intake.py").read_text(encoding="utf-8")
    assert "from operator_evidence_intake import stage_controlled_evidence_run" in server
    assert 'run_id = "demo-controlled-"' in wrapper
    assert 'job["controlled"] = True' in wrapper
    assert 'workflow.get("mode") != "controlled"' in wrapper
    assert '"payment_required": False' in wrapper
    assert '"external_release_authorized": False' in wrapper


def test_homs_controlled_intake_requires_real_hymark_batch_shape():
    wrapper = (ROOT / "operator_evidence_intake.py").read_text(encoding="utf-8")
    assert '(hymark_dir / "uploads").is_dir()' in wrapper
    assert '(hymark_dir / "rubric.json").is_file()' in wrapper


def test_evidex_controlled_intake_requires_actual_source_summary():
    wrapper = (ROOT / "operator_evidence_intake.py").read_text(encoding="utf-8")
    assert "Evidex controlled intake requires an evidence/source summary" in wrapper
