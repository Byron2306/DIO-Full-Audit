from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _held_pack(tmp_path: Path) -> tuple[Path, dict]:
    pack = tmp_path / "SYNTHETIC_EVIDEX_PACK"
    pack.mkdir(parents=True)
    (pack / "SOURCE_REVIEW.json").write_text(
        json.dumps(
            {
                "schema": "dio.evidex.source_review.v1",
                "release_authorized": False,
                "human_review_required": True,
                "claims": [
                    {
                        "kpi_name": "Participants trained",
                        "declared_target": 20,
                        "declared_actual": 12,
                        "epistemic_state": "UNVERIFIED",
                        "source_bindings": [
                            {
                                "source_ref": "03_SOURCES/register.txt",
                                "source_name": "register.txt",
                                "sha256": "a" * 64,
                                "excerpt": "Participants trained: 12; independent verification absent.",
                                "excerpt_kind": "parser_text_excerpt_not_entailment",
                            }
                        ],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    intake = {
        "client": {"organization": "SYNTHETIC FIXTURE"},
        "pack": {
            "project_name": "Quality Rendering Check",
            "purpose": "Internal evidence review",
            "reporting_period": {"start": "2026-01-01", "end": "2026-08-31"},
        },
    }
    return pack, intake


def test_finish_preserves_human_gate_and_unverified_claims(tmp_path: Path) -> None:
    from products.evidex_studio_finish import finish_evidex_pack

    pack, intake = _held_pack(tmp_path)
    receipt = finish_evidex_pack(pack_dir=pack, intake=intake, source_root=ROOT)

    finish_dir = pack / "05_STUDIO_FINISH"
    stored = json.loads((finish_dir / "EVIDEX_STUDIO_FINISH_RECEIPT.json").read_text(encoding="utf-8"))
    html_output = next(row for row in stored["format_core"]["outputs"] if row["channel"] == "html")
    rendered = (finish_dir / html_output["path"]).read_text(encoding="utf-8")

    assert receipt == stored
    assert stored["schema"] == "dio.evidex_studio_finish.v1"
    assert stored["review_boundary"] == {
        "human_review_required": True,
        "release_authorized": False,
    }
    assert stored["format_core"]["qa_passed"] is True
    assert stored["format_core"]["release_mode"] is False
    assert stored["production_studio"]["customer_artifact_separated_from_proof"] is True
    assert stored["nichefoundry"] == {
        "state": "AVAILABLE_ON_APPROVED_BRAND_REQUEST",
        "executed": False,
    }
    assert stored["external_delivery"] == "REFUSE"
    assert stored["publication"] == "REFUSE"
    assert stored["spend"] == "REFUSE"
    assert stored["authority_created"] is False
    assert "UNVERIFIED" in rendered
    assert "HUMAN REVIEW REQUIRED" in rendered
    assert "KPI Participants trained" in rendered
    assert "Declared target: 20" in rendered
    assert "Declared actual: 12" in rendered
    assert "Claim text missing" not in rendered
    receipt_output = next(row for row in stored["format_core"]["outputs"] if row["channel"] == "receipt")
    assert receipt_output["path"] == "FORMAT_CORE/FORMAT_CORE_RECEIPT.json"
    assert len(receipt_output["sha256"]) == 64


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"release_authorized": True, "human_review_required": False, "claims": []},
        {"release_authorized": False, "human_review_required": True, "claims": "invalid"},
        {"release_authorized": False, "human_review_required": True, "claims": [{}]},
    ],
)
def test_finish_refuses_missing_or_malformed_source_review(tmp_path: Path, payload: object | None) -> None:
    from products.evidex_studio_finish import EvidexStudioFinishError, finish_evidex_pack

    pack, intake = _held_pack(tmp_path)
    review = pack / "SOURCE_REVIEW.json"
    if payload is None:
        review.unlink()
    else:
        review.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidexStudioFinishError):
        finish_evidex_pack(pack_dir=pack, intake=intake, source_root=ROOT)

    assert not (pack / "05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json").exists()


def _initial_archive(pack: Path) -> Path:
    archive = pack.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(pack.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(pack).as_posix())
    return archive


def _job() -> dict:
    return {
        "job_id": "SYNTHETIC-STUDIO-FINISH",
        "created_at": "2026-10-27T00:00:00+00:00",
        "route": {"product": "evidex", "reason": "test", "confidence": 1},
        "inputs": [{"sender": "Test User <test@example.invalid>", "subject": "Evidence review"}],
        "evidence": [{"text_extract": "Synthetic evidence only."}],
    }


def test_archive_finish_reseals_relative_regular_files_once(tmp_path: Path) -> None:
    from products.evidex_studio_finish import finish_evidex_archive

    pack, intake = _held_pack(tmp_path)
    archive = _initial_archive(pack)

    result = finish_evidex_archive(archive_path=archive, intake=intake, source_root=ROOT)

    assert result["status"] == "finished_review_candidate"
    assert result["archive_sha256"]
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
    receipt_name = "05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json"
    assert names.count(receipt_name) == 1
    assert all(not Path(name).is_absolute() for name in names)
    assert all(".." not in Path(name).parts for name in names)


def test_archive_finish_rejects_symlink_without_replacing_archive(tmp_path: Path) -> None:
    from products.evidex_studio_finish import EvidexStudioFinishError, finish_evidex_archive

    pack, intake = _held_pack(tmp_path)
    archive = _initial_archive(pack)
    original = archive.read_bytes()
    (pack / "unsafe-link").symlink_to(tmp_path / "outside")

    with pytest.raises(EvidexStudioFinishError, match="symlink"):
        finish_evidex_archive(archive_path=archive, intake=intake, source_root=ROOT)

    assert archive.read_bytes() == original


def test_real_engine_schema_reaches_finished_customer_review(tmp_path: Path) -> None:
    from products.evidex_studio_finish import finish_evidex_archive

    engine = ROOT / "cross_folder_variants/Evidex/A_CODE"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "register.txt").write_text(
        "Participants trained: 12; independent verification absent.", encoding="utf-8"
    )
    intake = {
        "client": {"organization": "SYNTHETIC FIXTURE"},
        "pack": {
            "purpose": "Internal evidence review",
            "project_name": "Engine Schema Integration",
            "reporting_period": {"start": "2026-01-01", "end": "2026-08-31"},
        },
        "kpis": [
            {
                "name": "Participants trained",
                "target": 20,
                "actual": 12,
                "measurement": "Attendance register",
            }
        ],
    }
    intake_path = tmp_path / "intake.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith(("OPENAI_", "OLLAMA_", "LLM_"))}
    env.update(
        PYTHONPATH=os.pathsep.join([str(engine / "src"), str(ROOT)]),
        DIO_ROOT=str(ROOT),
        LLM_DISABLED="1",
        SUMMARY_USE_LLM="0",
        NARRATIVE_USE_LLM="0",
    )
    generated = subprocess.run(
        [
            sys.executable,
            "-m",
            "evidence_pack_engine.cli",
            "generate",
            "--intake",
            str(intake_path),
            "--uploads",
            str(uploads),
            "--out",
            str(tmp_path / "output"),
        ],
        cwd=engine,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert generated.returncode == 0, generated.stderr
    lines = generated.stdout.strip().splitlines()
    pack_dir = Path(next(line.removeprefix("EVIDEX_PACK_ROOT=") for line in lines if line.startswith("EVIDEX_PACK_ROOT=")))
    archive = Path(lines[-1])

    receipt = finish_evidex_archive(archive_path=archive, intake=intake, source_root=ROOT, pack_dir=pack_dir)

    html_row = next(row for row in receipt["format_core"]["outputs"] if row["channel"] == "html")
    rendered = (pack_dir / "05_STUDIO_FINISH" / html_row["path"]).read_text(encoding="utf-8")
    assert "KPI Participants trained" in rendered
    assert "Declared target: 20" in rendered
    assert "Declared actual: 12" in rendered
    assert "UNVERIFIED" in rendered


def test_runner_records_successful_studio_finish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_evidex_jobs as runner

    out_root = tmp_path / "deliverables"
    output = out_root / "evidex/SYNTHETIC-STUDIO-FINISH/evidex_engine/output"
    pack, _intake = _held_pack(output)
    archive = _initial_archive(pack)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=str(archive) + "\n", stderr=""),
    )

    receipt = runner.run_evidex(_job(), out_root)

    assert receipt["returncode"] == 0
    assert receipt["engine_returncode"] == 0
    assert receipt["studio_finish"]["status"] == "finished_review_candidate"
    stored = json.loads(
        (out_root / "evidex/SYNTHETIC-STUDIO-FINISH/EVIDEX_RUN_RECEIPT.json").read_text(encoding="utf-8")
    )
    assert stored["studio_finish"]["archive_sha256"] == receipt["studio_finish"]["archive_sha256"]


def test_runner_fails_when_studio_finish_fails_without_removing_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.run_evidex_jobs as runner

    out_root = tmp_path / "deliverables"
    output = out_root / "evidex/SYNTHETIC-STUDIO-FINISH/evidex_engine/output"
    pack = output / "BROKEN_PACK"
    pack.mkdir(parents=True)
    archive = _initial_archive(pack)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=str(archive) + "\n", stderr=""),
    )

    receipt = runner.run_evidex(_job(), out_root)

    assert receipt["engine_returncode"] == 0
    assert receipt["returncode"] == 1
    assert receipt["studio_finish"]["status"] == "failed"
    assert "source review" in receipt["studio_finish"]["error"]
    assert pack.is_dir()
    assert archive.is_file()
