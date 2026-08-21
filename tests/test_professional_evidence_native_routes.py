from __future__ import annotations

from pathlib import Path

import pytest

from products import professional_evidence_native_routes as native


def _packet(tmp_path: Path) -> dict:
    packet_dir = tmp_path / "CUSTOMER_PACKET"
    sources = packet_dir / "SOURCES"
    sources.mkdir(parents=True)
    (sources / "source_pack.md").write_text(
        "# Source 1\nNationalism in South Africa.\n\n"
        "# Source 2\nApartheid and resistance in the 1940s-1960s.\n\n"
        "Publication date for Source 2: not supplied.\n",
        encoding="utf-8",
    )
    return {
        "packet_dir": packet_dir,
        "packet_fingerprint": "sha256:test-packet",
        "intake": {
            "request": "Build a Grade 11 History mid-year examination and memorandum from this scope, weighting and source pack. Keep it at 150 marks and two hours.",
            "context": "The paper covers nationalism in South Africa and apartheid in the 1940s-1960s.",
            "exception": "One supplied source has no publication date. Do not invent one.",
        },
        "evidence_register": [
            {"record_id": "R01", "customer_supplied_record": "Total marks: 150."},
            {"record_id": "R02", "customer_supplied_record": "Duration: 2 hours."},
            {"record_id": "R03", "customer_supplied_record": "Source-based section must contribute 90 marks."},
        ],
    }


def test_homs_native_request_preserves_customer_scope_and_source_hash(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(tmp_path)
    monkeypatch.setattr(native, "evidence_rows", lambda packet: packet["evidence_register"])
    source = Path(packet["packet_dir"]) / "SOURCES" / "source_pack.md"

    request = native._homs_exam_request(packet, source)

    assert request["module_name"] == "Grade 11 History"
    assert request["total_marks"] == 150
    assert request["duration_hours"] == 2
    assert request["dio_customer_source_booklet_sha256"] == native.sha256(source)
    assert request["dio_surrogate_fallback_allowed"] is False
    assert "Publication date for Source 2: not supplied" in request["additional_instructions"]
    assert "do not invent dates" in request["additional_instructions"].lower()


def test_vamp_performance_requires_real_vamp_engine(tmp_path: Path) -> None:
    route = {"route": "vamp_raw_performance"}

    def good(*args, **kwargs):
        return {
            "executor": "adapters.vamp.snapshot_pipeline.build_snapshot",
            "receipt": {"authority_created": False, "external_effects": False},
        }

    result = native.execute_native_route(
        {},
        tmp_path,
        incarnation="VAMP Performance",
        route=route,
        operator_id="test",
        now="2026-08-21T00:00:00+00:00",
        online=False,
        generic_executor=good,
    )
    assert result["native_capability_preserved"] is True
    assert result["surrogate_fallback_used"] is False

    def bad(*args, **kwargs):
        return {"executor": "products.synthetic_vamp_review", "receipt": {}}

    with pytest.raises(RuntimeError, match="Surrogate fallback is forbidden"):
        native.execute_native_route(
            {},
            tmp_path,
            incarnation="VAMP Performance",
            route=route,
            operator_id="test",
            now="2026-08-21T00:00:00+00:00",
            online=False,
            generic_executor=bad,
        )


def test_evidex_requires_real_evidex_engine(tmp_path: Path) -> None:
    route = {"route": "evidex_raw"}

    def good(*args, **kwargs):
        return {
            "executor": "scripts.run_evidex_jobs.run_evidex + customer-context projection",
            "receipt": {"authority_created": False, "external_effects": False},
        }

    result = native.execute_native_route(
        {},
        tmp_path,
        incarnation="Evidex EvidenceOps",
        route=route,
        operator_id="test",
        now="2026-08-21T00:00:00+00:00",
        online=False,
        generic_executor=good,
    )
    assert result["native_engine_identity"] == "scripts.run_evidex_jobs.run_evidex"
    assert result["surrogate_fallback_used"] is False


def test_non_native_route_falls_through() -> None:
    result = native.execute_native_route(
        {},
        Path("/tmp/unused"),
        incarnation="Document Studio Edit",
        route={"route": "document_studio_raw"},
        operator_id="test",
        now="2026-08-21T00:00:00+00:00",
        online=False,
        generic_executor=lambda *args, **kwargs: {},
    )
    assert result is native.NATIVE_ROUTE_NOT_HANDLED
