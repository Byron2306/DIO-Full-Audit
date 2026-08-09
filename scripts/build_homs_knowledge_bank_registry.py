#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deliverables" / "homs_knowledge_bank"

PATHS = {
    "caps_manifest": ROOT / "corpora" / "caps" / "caps_corpus_manifest.json",
    "caps_matrix": ROOT / "deliverables" / "caps_matrix_analysis" / "caps_matrix_analysis.json",
    "caps_ontology": ROOT / "deliverables" / "caps_assessment_ontology" / "caps_assessment_ontology.json",
    "caps_design": ROOT / "deliverables" / "caps_assessment_design" / "caps_assessment_design.json",
    "exam_source_matrix_tight8_2025": ROOT / "deliverables" / "exam_source_matrix_tight8_2025" / "exam_source_matrix.json",
    "curated_source_bank": ROOT / "deliverables" / "homs_core_source_bank_curated" / "HOMS_CORE_SOURCE_BANK_CURATED.json",
    "fet_paper_audit": ROOT / "deliverables" / "homs_fet_paper_audit" / "HOMS_FET_PAPER_AUDIT.json",
    "subject_profile_dir": ROOT / "config" / "homs_subject_profiles",
    "grade_ladder": ROOT / "config" / "homs_grade_ladder.json",
    "provider_secrets": Path("/home/byron/EdgeK-BEAST/.beast/provider_secrets.env"),
    "sophia_academic_retrieval": Path("/home/byron/Integritas-Mechanicus/arda_os/backend/services/academic_retrieval.py"),
    "sophia_pedagogy": Path("/home/byron/Integritas-Mechanicus/arda_os/backend/services/sophia_pedagogy_orchestrator.py"),
    "sophia_curriculum_gate": Path("/home/byron/Integritas-Mechanicus/arda_os/backend/services/sophia_curriculum_gate.py"),
    "sophia_project_store": Path("/home/byron/Integritas-Mechanicus/evidence/sophia_project_store"),
    "mandos_relational_memory": Path("/home/byron/Integritas-Mechanicus/evidence/mandos/resonant/relational_memory.json"),
    "mandos_covenant_db": Path("/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/mandos/covenant_chain.db"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def redact_env_keys(path: Path) -> list[str]:
    if not path.exists():
        return []
    keys: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].replace("export ", "").strip()
        if re.search(r"(KEY|TOKEN|SECRET|PASSWORD)", key):
            keys.append(key)
    return sorted(set(keys))


def count_subject_profiles(path: Path) -> dict[str, Any]:
    rows = []
    if path.exists():
        for profile_path in sorted(path.glob("*.json")):
            data = load_json(profile_path, {})
            rows.append(
                {
                    "subject_id": data.get("subject_id") or profile_path.stem,
                    "display_name": data.get("display_name") or profile_path.stem.replace("_", " ").title(),
                    "path": str(profile_path),
                    "retrieval_queries": len(data.get("retrieval_queries") or []),
                    "source_types": data.get("source_types") or [],
                    "question_families": data.get("question_families") or [],
                    "blocked_claims_or_modes": data.get("blocked_claims_or_modes") or [],
                }
            )
    return {"count": len(rows), "profiles": rows}


def summarize_caps_manifest(data: dict[str, Any]) -> dict[str, Any]:
    docs = data.get("documents") or []
    phases = Counter(row.get("phase") or "unknown" for row in docs)
    statuses = Counter(row.get("status") or "unknown" for row in docs)
    return {
        "document_count": len(docs),
        "phase_counts": dict(sorted(phases.items())),
        "status_counts": dict(sorted(statuses.items())),
    }


def summarize_caps_matrix(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get("rows") or []
    blueprint_counts = Counter(row.get("recommended_blueprint") or "unknown" for row in rows)
    return {
        "document_count": data.get("document_count") or len(rows),
        "failure_count": data.get("failure_count", 0),
        "blueprint_counts": dict(sorted(blueprint_counts.items())),
        "known_noise": [
            "Document-level keyword extraction can over-trigger broad signals.",
            "Generic policy/support documents are evidence only, not generation blueprints.",
            "Language variants must collapse into canonical subject+phase profiles before generation.",
        ],
    }


def summarize_assessment_profiles(data: dict[str, Any]) -> dict[str, Any]:
    profiles = data.get("profiles") or []
    by_id = {}
    for row in profiles:
        profile_id = row.get("profile_id") or row.get("id")
        if not profile_id:
            continue
        by_id[profile_id] = {
            "subject": row.get("subject"),
            "phase": row.get("phase"),
            "assessment_family": row.get("assessment_family"),
            "render_shell": row.get("render_shell"),
            "confidence": row.get("confidence"),
            "allowed": row.get("allowed"),
            "required_distribution": row.get("required_distribution"),
        }
    return {"profile_count": len(profiles), "profiles_by_id": by_id}


def summarize_exam_sources(data: dict[str, Any]) -> dict[str, Any]:
    subject_counts: dict[str, Counter[str]] = defaultdict(Counter)
    paper_shapes = []
    for paper in data.get("papers") or []:
        subject = str(paper.get("subject") or "unknown")
        counts = paper.get("source_type_counts") or {}
        subject_counts[subject].update({str(k): int(v) for k, v in counts.items()})
        paper_shapes.append(
            {
                "subject": subject,
                "title": paper.get("title"),
                "unique_source_object_count": paper.get("unique_source_object_count"),
                "source_type_counts": counts,
                "quality_counts": paper.get("quality_counts") or {},
                "question_titles_seen": paper.get("question_titles_seen") or [],
            }
        )
    return {
        "paper_count": data.get("paper_count") or len(paper_shapes),
        "source_type_counts": data.get("aggregate", {}).get("source_type_counts") or {},
        "subjects": {subject: dict(counter) for subject, counter in sorted(subject_counts.items())},
        "paper_shapes": paper_shapes,
    }


def summarize_curated_sources(data: dict[str, Any]) -> dict[str, Any]:
    assets = data.get("assets") or []
    by_subject: dict[str, Counter[str]] = defaultdict(Counter)
    flags: dict[str, Counter[str]] = defaultdict(Counter)
    for asset in assets:
        subject = str(asset.get("subject_id") or asset.get("subject") or "unknown")
        source_type = str(asset.get("source_type") or "unknown")
        by_subject[subject][source_type] += 1
        for flag in asset.get("flags") or []:
            flags[subject][str(flag)] += 1
    return {
        "asset_count": data.get("asset_count") or len(assets),
        "subjects": {subject: dict(counter) for subject, counter in sorted(by_subject.items())},
        "flags_by_subject": {subject: dict(counter) for subject, counter in sorted(flags.items())},
        "embedding_policy": "Official-paper exemplars may support shape/source-type learning; review copyright/licensing before client delivery.",
    }


def summarize_audit(data: dict[str, Any]) -> dict[str, Any]:
    papers = data.get("papers") or data.get("paper_audits") or []
    status_counts = Counter(row.get("status") or row.get("verdict") or "unknown" for row in papers)
    common_failures: Counter[str] = Counter()
    for row in papers:
        for issue in row.get("issues") or row.get("failures") or []:
            if isinstance(issue, dict):
                common_failures[issue.get("id") or issue.get("code") or issue.get("severity") or "issue"] += 1
            else:
                common_failures[str(issue)] += 1
    return {
        "overall_status": data.get("overall_status"),
        "paper_count": data.get("paper_count") or len(papers),
        "status_counts": dict(status_counts),
        "top_failures": dict(common_failures.most_common(12)),
        "hard_bans_for_learner_papers": [
            "smoke test",
            "source exemplar",
            "review pipeline",
            "quality gate",
            "method and review",
            "educator approval required before classroom use",
        ],
    }


def summarize_sophia_and_mandos() -> dict[str, Any]:
    project_store = PATHS["sophia_project_store"]
    project_count = 0
    event_count = 0
    if project_store.exists():
        project_count = len(list((project_store / "projects").glob("*/project.json"))) if (project_store / "projects").exists() else 0
        events = project_store / "events.jsonl"
        if events.exists():
            event_count = sum(1 for _ in events.open("r", encoding="utf-8", errors="ignore"))

    mandos = PATHS["mandos_relational_memory"]
    mandos_shape: dict[str, Any] = {"exists": mandos.exists(), "encrypted_or_wrapped": False}
    if mandos.exists():
        data = load_json(mandos, {})
        mandos_shape.update(
            {
                "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else [],
                "encrypted_or_wrapped": bool(isinstance(data, dict) and data.get("encryption")),
            }
        )

    return {
        "sophia_services": {
            "academic_retrieval": str(PATHS["sophia_academic_retrieval"]),
            "pedagogy_orchestrator": str(PATHS["sophia_pedagogy"]),
            "curriculum_gate": str(PATHS["sophia_curriculum_gate"]),
            "all_present": all(PATHS[key].exists() for key in ["sophia_academic_retrieval", "sophia_pedagogy", "sophia_curriculum_gate"]),
        },
        "sophia_project_store": {
            "path": str(project_store),
            "exists": project_store.exists(),
            "project_count": project_count,
            "event_count": event_count,
        },
        "mandos_memory": {
            "relational_memory": mandos_shape,
            "covenant_db": {
                "path": str(PATHS["mandos_covenant_db"]),
                "exists": PATHS["mandos_covenant_db"].exists(),
                "bytes": PATHS["mandos_covenant_db"].stat().st_size if PATHS["mandos_covenant_db"].exists() else 0,
            },
            "homs_recommendation": "Use a new HOMS correction ledger first; import old Mandos only as design pattern, not raw memory.",
        },
    }


def build_registry() -> dict[str, Any]:
    provider_keys = redact_env_keys(PATHS["provider_secrets"])
    registry = {
        "schema": "knowedge.homs_knowledge_bank_registry.v1",
        "created_at": utc_now(),
        "root": str(ROOT),
        "knowledge_layers": {
            "curriculum_authority": summarize_caps_manifest(load_json(PATHS["caps_manifest"], {})),
            "caps_document_evidence": summarize_caps_matrix(load_json(PATHS["caps_matrix"], {})),
            "canonical_caps_ontology": summarize_assessment_profiles(load_json(PATHS["caps_ontology"], {})),
            "render_and_assessment_design": summarize_assessment_profiles(load_json(PATHS["caps_design"], {})),
            "official_paper_source_catalogue": summarize_exam_sources(load_json(PATHS["exam_source_matrix_tight8_2025"], {})),
            "curated_source_asset_bank": summarize_curated_sources(load_json(PATHS["curated_source_bank"], {})),
            "subject_profiles": count_subject_profiles(PATHS["subject_profile_dir"]),
            "grade_ladder": load_json(PATHS["grade_ladder"], {}),
            "paper_quality_memory": summarize_audit(load_json(PATHS["fet_paper_audit"], {})),
            "sophia_mandos_bridge": summarize_sophia_and_mandos(),
        },
        "provider_support": {
            "secret_file": str(PATHS["provider_secrets"]),
            "values_redacted": True,
            "available_secret_names": provider_keys,
            "gemini_ready": "GEMINI_API_KEY" in provider_keys,
            "gemini_default_model_hint": "gemini-3.5-flash",
            "nvidia_nim_ready": "NVIDIA_API_KEY" in provider_keys,
            "nvidia_default_base_url": "https://integrate.api.nvidia.com/v1",
            "nvidia_default_model_hint": "nvidia/nemotron-3-super-120b-a12b",
        },
        "required_runtime_order": [
            "resolve subject + grade + term",
            "retrieve CAPS excerpts and canonical assessment profile",
            "retrieve official-paper source/object patterns for that subject",
            "retrieve HOMS correction memory and hard bans",
            "construct subject knowledge packet",
            "provider draft generation as JSON only",
            "provider critic pass against CAPS/profile/source/format constraints",
            "render only if validation passes",
            "educator approval before classroom use",
        ],
    }
    return registry


def write_outputs(registry: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "HOMS_KNOWLEDGE_BANK_REGISTRY.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    layers = registry["knowledge_layers"]
    provider = registry["provider_support"]
    lines = [
        "# HOMS Knowledge Bank Registry",
        "",
        f"Created: {registry['created_at']}",
        f"Root: `{registry['root']}`",
        "",
        "## Verdict",
        "",
        "The knowledge bank exists, but it was fragmented. This registry makes the usable layers explicit before provider-backed generation.",
        "",
        "## Core Stores",
        "",
        f"- CAPS authority: {layers['curriculum_authority']['document_count']} documents.",
        f"- CAPS matrix evidence: {layers['caps_document_evidence']['document_count']} documents; failures {layers['caps_document_evidence']['failure_count']}.",
        f"- CAPS ontology profiles: {layers['canonical_caps_ontology']['profile_count']}.",
        f"- Assessment design profiles: {layers['render_and_assessment_design']['profile_count']}.",
        f"- Official-paper source catalogue: {layers['official_paper_source_catalogue']['paper_count']} papers.",
        f"- Curated source assets: {layers['curated_source_asset_bank']['asset_count']} assets.",
        f"- Subject profiles: {layers['subject_profiles']['count']}.",
        "",
        "## Sophia / Mandos",
        "",
        f"- Sophia service modules present: {layers['sophia_mandos_bridge']['sophia_services']['all_present']}.",
        f"- Sophia project store events: {layers['sophia_mandos_bridge']['sophia_project_store']['event_count']}.",
        f"- Sophia project records: {layers['sophia_mandos_bridge']['sophia_project_store']['project_count']}.",
        f"- Mandos relational memory wrapped/encrypted: {layers['sophia_mandos_bridge']['mandos_memory']['relational_memory']['encrypted_or_wrapped']}.",
        "",
        "## Provider Support",
        "",
        f"- Gemini key present: {provider['gemini_ready']}.",
        f"- Gemini default model hint: `{provider['gemini_default_model_hint']}`.",
        f"- NVIDIA NIM key present: {provider['nvidia_nim_ready']}.",
        f"- Secret values redacted: {provider['values_redacted']}.",
        f"- NVIDIA default base URL: `{provider['nvidia_default_base_url']}`.",
        "",
        "## Runtime Order",
        "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(registry["required_runtime_order"], start=1))
    lines.append("")
    (out_dir / "HOMS_KNOWLEDGE_BANK_REGISTRY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    registry = build_registry()
    write_outputs(registry, DEFAULT_OUT)
    print(json.dumps({"ok": True, "out": str(DEFAULT_OUT), "nvidia_nim_ready": registry["provider_support"]["nvidia_nim_ready"]}, indent=2))


if __name__ == "__main__":
    main()
