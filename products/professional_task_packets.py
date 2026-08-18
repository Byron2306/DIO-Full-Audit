from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "config" / "professional_task_gauntlet" / "v1"
CASE_DIR = CASE_ROOT / "cases"

BASE_MANIFESTS = {
    "site_studio": "site_studio.json",
    "professional_correspondence_studio": "professional_correspondence_studio.json",
    "finance_readiness_studio": "finance_readiness_studio.json",
    "article_publication_studio": "article_publication_studio.json",
}
TIERS = ("normal", "messy", "adversarial")


class ProfessionalTaskGauntletError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ProfessionalTaskGauntletError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ProfessionalTaskGauntletError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case_definition(case: dict[str, Any]) -> None:
    required = {
        "case_id", "studio_id", "tier", "title", "job", "case_context",
        "deliverable", "source_documents", "constraints", "expected_facts",
        "prohibited_inventions", "authority_boundary", "acceptance_rubric",
    }
    missing = sorted(required - set(case))
    if missing:
        raise ProfessionalTaskGauntletError(f"{case.get('case_id', '<unknown>')} missing fields: {missing}")
    if case["studio_id"] not in BASE_MANIFESTS:
        raise ProfessionalTaskGauntletError(f"unsupported Studio: {case['studio_id']}")
    if case["tier"] not in TIERS:
        raise ProfessionalTaskGauntletError(f"unsupported tier: {case['tier']}")
    if not case["source_documents"]:
        raise ProfessionalTaskGauntletError(f"{case['case_id']} has no source documents")
    if any("final_copy" in key.casefold() or "golden_output" in key.casefold() for key in case):
        raise ProfessionalTaskGauntletError("professional task cases may not contain desired final copy")


def load_case(case_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    path = Path(root).resolve() / "config" / "professional_task_gauntlet" / "v1" / "cases" / f"{case_id}.json"
    case = load_json(path)
    validate_case_definition(case)
    return case


def load_portfolio(*, root: Path = ROOT) -> dict[str, Any]:
    return load_json(Path(root).resolve() / "config" / "professional_task_gauntlet" / "v1" / "portfolio.json")


def studio_input(case: dict[str, Any]) -> dict[str, Any]:
    """Return only material the Studio may see; examiner truth remains hidden."""
    visible_keys = (
        "case_id", "tier", "title", "job", "case_context", "deliverable",
        "source_documents", "constraints", "authority_boundary", "poisoned_instruction",
    )
    return {key: copy.deepcopy(case.get(key)) for key in visible_keys if key in case}


def materialize_case_packet(case: dict[str, Any], *, output_dir: Path) -> Path:
    validate_case_definition(case)
    output_dir = Path(output_dir).resolve()
    packet = output_dir / "packet"
    sources_dir = packet / "SOURCES"
    sources_dir.mkdir(parents=True, exist_ok=True)

    job = case["job"]
    job_md = "\n".join(
        [
            f"# {case['title']}", "",
            f"**Case:** `{case['case_id']}`",
            f"**Studio:** `{case['studio_id']}`",
            f"**Tier:** `{case['tier']}`",
            f"**Buyer:** {job['buyer']}", "",
            "## Professional task", "",
            str(job["request"]), "",
            "## Delivery boundary", "",
            "Produce the best permissible professional artifact from the supplied material. "
            "Do not invent evidence or create external authority.", "",
        ]
    )
    (packet / "JOB.md").write_text(job_md, encoding="utf-8")
    for row in case.get("source_documents") or []:
        filename = Path(str(row["filename"])).name
        (sources_dir / filename).write_text(str(row.get("text") or "").rstrip() + "\n", encoding="utf-8")

    write_json(packet / "CONSTRAINTS.json", {"constraints": case.get("constraints") or []})
    write_json(packet / "EXPECTED_FACTS.json", {"expected_facts": case.get("expected_facts") or []})
    write_json(packet / "PROHIBITED_INVENTIONS.json", {"prohibited_inventions": case.get("prohibited_inventions") or []})
    write_json(packet / "AUTHORITY_BOUNDARY.json", case.get("authority_boundary") or {})
    write_json(packet / "ACCEPTANCE_RUBRIC.json", case.get("acceptance_rubric") or {})
    write_json(
        packet / "CASE.json",
        {
            "schema": case["schema"],
            "case_id": case["case_id"],
            "studio_id": case["studio_id"],
            "tier": case["tier"],
            "title": case["title"],
            "case_context": case["case_context"],
            "deliverable": case["deliverable"],
            "poisoned_instruction": case.get("poisoned_instruction"),
        },
    )
    return packet
