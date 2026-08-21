from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable

from products.professional_evidence_projection import evidence_rows, exception_text, sha256, write_json


SCHEMA = "dio.professional_evidence.native_route_binding.v1"
NATIVE_ROUTE_NOT_HANDLED = object()

# These routes already have mature product engines. The portfolio adapter may
# project Vesper-custodied input into their native contract, but may never
# substitute a weaker implementation and inherit the mature product identity.
NATIVE_ENGINE_ROUTES = {
    "homs_raw_exam": "scripts.run_hymark_exam_builder.run_builder",
    "vamp_raw_performance": "adapters.vamp.snapshot_pipeline.build_snapshot",
    "evidex_raw": "scripts.run_evidex_jobs.run_evidex",
}


def _request_document_text(packet: dict[str, Any]) -> str:
    path = Path(str(packet.get("request_path") or "")) if packet.get("request_path") else Path(packet["packet_dir"]) / "CUSTOMER_REQUEST.md"
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _packet_text(packet: dict[str, Any]) -> str:
    intake = dict(packet.get("intake") or {})
    rows = evidence_rows(packet)
    return "\n".join(
        [
            str(intake.get("request") or ""),
            _request_document_text(packet),
            *[str(row.get("customer_supplied_record") or "") for row in rows],
            exception_text(packet),
        ]
    )


def _first_int(pattern: str, text: str, default: int) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else default


def _history_topics(text: str) -> list[str]:
    lower = text.casefold()
    topics: list[str] = []
    known = (
        ("nationalism", "Nationalism in South Africa"),
        ("apartheid", "Apartheid in South Africa, 1940s-1960s"),
    )
    for needle, label in known:
        if needle in lower and label not in topics:
            topics.append(label)
    return topics[:2] or ["Customer-supplied History source scope"]


def _homs_exam_request(packet: dict[str, Any], source_booklet: Path) -> dict[str, Any]:
    intake = dict(packet.get("intake") or {})
    text = _packet_text(packet)
    grade = _first_int(r"\bgrade\s+(\d{1,2})\b", text, 11)
    total_marks = _first_int(r"\btotal\s+marks\s*[:=-]?\s*(\d{2,3})\b", text, 150)
    duration_hours = _first_int(r"\b(\d+)\s*hours?\b", text, 2)
    source_text = source_booklet.read_text(encoding="utf-8", errors="replace")
    source_excerpt = source_text[:16000]
    customer_request = str(intake.get("request") or "").strip()
    exception = exception_text(packet)
    return {
        "module_code": "DIO-HIST11",
        "module_name": f"Grade {grade} History",
        "topics": _history_topics(text),
        "methodology_topic": "Source-based historical interpretation and evaluation",
        "essay_topic": "Extended historical argument within the customer-supplied scope",
        "total_marks": total_marks,
        "duration_hours": duration_hours,
        "additional_instructions": (
            "This request entered through DIO Vesper custody and MUST be treated as a real customer exam-build job. "
            "Use the customer source booklet below as source evidence where applicable. Preserve any missing provenance as missing; "
            "do not invent dates, authors, publication titles, or source authority. Build complete learner-facing source material, "
            "complete questions, and specific memorandum answers. Produce both opportunities.\n\n"
            f"CUSTOMER REQUEST:\n{customer_request}\n\n"
            f"CUSTOMER EXCEPTION / AUTHORITY BOUNDARY:\n{exception}\n\n"
            f"CUSTOMER SOURCE BOOKLET SHA256: {sha256(source_booklet)}\n\n"
            f"CUSTOMER SOURCE BOOKLET:\n{source_excerpt}"
        ),
        "dio_customer_packet_fingerprint": packet.get("packet_fingerprint"),
        "dio_customer_source_booklet": str(source_booklet.resolve()),
        "dio_customer_source_booklet_sha256": sha256(source_booklet),
        "dio_surrogate_fallback_allowed": False,
    }


def _require_native_outputs(receipt: dict[str, Any]) -> dict[str, Path]:
    if receipt.get("schema") != "knowedge.hymark_exam_builder_receipt.v1":
        raise RuntimeError("HOMS Exam native route returned the wrong receipt schema")
    if receipt.get("status") != "completed":
        raise RuntimeError(f"HOMS Exam native HyMark route did not complete: {receipt.get('status')}")
    outputs = dict(receipt.get("outputs") or {})
    required = {
        "first_exam": Path(str(outputs.get("first_exam") or "")),
        "first_memo": Path(str(outputs.get("first_memo") or "")),
        "second_exam": Path(str(outputs.get("second_exam") or "")),
        "second_memo": Path(str(outputs.get("second_memo") or "")),
        "review_zip": Path(str(outputs.get("review_zip") or "")),
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise RuntimeError("HOMS Exam native HyMark route missed required outputs: " + ", ".join(missing))
    for name in ("first_exam", "first_memo", "second_exam", "second_memo"):
        if required[name].stat().st_size < 1000:
            raise RuntimeError(f"HOMS Exam native output is implausibly small: {name}")
    if sha256(required["first_exam"]) == sha256(required["second_exam"]):
        raise RuntimeError("HOMS Exam native route produced identical first and second opportunity papers")
    if sha256(required["first_memo"]) == sha256(required["second_memo"]):
        raise RuntimeError("HOMS Exam native route produced identical first and second opportunity memoranda")
    return required


def _run_hymark_exam(packet: dict[str, Any], execution_dir: Path, *, now: str) -> dict[str, Any]:
    from scripts import run_hymark_exam_builder as hymark

    source_booklet = Path(packet["packet_dir"]) / "SOURCES" / "source_pack.md"
    if not source_booklet.is_file():
        raise RuntimeError("HOMS Exam native route requires the Vesper-custodied customer source booklet")

    projection_dir = execution_dir.parent / "PROJECTION"
    request_path = projection_dir / "HYMARK_NATIVE_EXAM_REQUEST.json"
    request = _homs_exam_request(packet, source_booklet)
    write_json(request_path, request)

    provider = os.environ.get("HOMS_PROVIDER", "nim")
    model = os.environ.get("HOMS_MODEL", "")
    secret_file = Path(os.environ.get("HOMS_SECRET_FILE") or hymark.DEFAULT_SECRET_FILE).expanduser().resolve()
    backend = Path(os.environ.get("HOMS_HYMARK_BACKEND") or hymark.DEFAULT_HYMARK_BACKEND).expanduser().resolve()
    if not backend.is_file():
        raise FileNotFoundError(f"HOMS native HyMark backend missing: {backend}")

    native_root = execution_dir / "hymark_native"
    receipt = hymark.run_builder(
        request_path,
        native_root,
        secret_file,
        backend,
        provider,
        model,
        "history",
        None,
        int(request["module_name"].split()[1]),
        hymark.DEFAULT_GRADE_LADDER,
        hymark.DEFAULT_CAPS_MANIFEST,
        hymark.DEFAULT_CAPS_MATRIX,
        hymark.DEFAULT_CAPS_ONTOLOGY,
        hymark.DEFAULT_CAPS_ASSESSMENT_DESIGN,
        hymark.DEFAULT_DESIGN_LAW,
        "English",
        3500,
        False,
        "auto",
        None,
        "both",
        None,
        None,
    )
    outputs = _require_native_outputs(receipt)
    job_dir = Path(str((receipt.get("outputs") or {}).get("job_dir") or ""))
    if not job_dir.is_dir():
        raise RuntimeError("HOMS Exam native route did not persist its job directory")
    shutil.copy2(source_booklet, job_dir / "CUSTOMER_SOURCE_BOOKLET.md")

    binding = {
        "schema": SCHEMA,
        "incarnation": "HOMS Exam",
        "route": "homs_raw_exam",
        "native_engine": NATIVE_ENGINE_ROUTES["homs_raw_exam"],
        "native_receipt_schema": receipt.get("schema"),
        "native_job_id": receipt.get("job_id"),
        "native_generation_backend": ((receipt.get("assessor") or {}).get("generation_backend")),
        "native_output_hashes": {name: sha256(path) for name, path in outputs.items()},
        "customer_packet_fingerprint": packet.get("packet_fingerprint"),
        "customer_source_booklet_sha256": sha256(source_booklet),
        "native_capability_preserved": True,
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    write_json(execution_dir / "HOMS_NATIVE_ROUTE_BINDING.json", binding)
    return {
        "executor": NATIVE_ENGINE_ROUTES["homs_raw_exam"],
        "native_engine_identity": NATIVE_ENGINE_ROUTES["homs_raw_exam"],
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_id": "homs_exam",
        "terminal_artifact_kind": "native_hymark_exam_and_memoranda_pack",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": binding,
        "native_result": receipt,
    }


def _assert_native_identity(result: dict[str, Any], expected: str, incarnation: str) -> dict[str, Any]:
    executor = str(result.get("executor") or "")
    if expected not in executor:
        raise RuntimeError(
            f"{incarnation} canonical route resolved to non-native executor {executor!r}; expected {expected}. "
            "Surrogate fallback is forbidden."
        )
    receipt = dict(result.get("receipt") or {})
    receipt["native_engine_identity"] = expected
    receipt["native_capability_preserved"] = True
    receipt["surrogate_fallback_allowed"] = False
    receipt["surrogate_fallback_used"] = False
    result = dict(result)
    result["receipt"] = receipt
    result["native_engine_identity"] = expected
    result["native_capability_preserved"] = True
    result["surrogate_fallback_used"] = False
    return result


def execute_native_route(
    packet: dict[str, Any],
    execution_dir: Path,
    *,
    incarnation: str,
    route: dict[str, Any],
    operator_id: str,
    now: str,
    online: bool,
    generic_executor: Callable[..., dict[str, Any]],
) -> dict[str, Any] | object:
    route_name = str(route.get("route") or "")
    if route_name == "homs_raw_exam":
        return _run_hymark_exam(packet, execution_dir, now=now)

    if route_name == "vamp_raw_performance":
        result = generic_executor(
            packet,
            execution_dir,
            incarnation=incarnation,
            route=route,
            operator_id=operator_id,
            now=now,
            online=online,
        )
        return _assert_native_identity(result, NATIVE_ENGINE_ROUTES[route_name], incarnation)

    if route_name == "evidex_raw":
        result = generic_executor(
            packet,
            execution_dir,
            incarnation=incarnation,
            route=route,
            operator_id=operator_id,
            now=now,
            online=online,
        )
        return _assert_native_identity(result, NATIVE_ENGINE_ROUTES[route_name], incarnation)

    return NATIVE_ROUTE_NOT_HANDLED


__all__ = [
    "NATIVE_ENGINE_ROUTES",
    "NATIVE_ROUTE_NOT_HANDLED",
    "SCHEMA",
    "_homs_exam_request",
    "execute_native_route",
]
