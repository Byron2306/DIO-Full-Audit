"""Durable project store for Sophia Writing Desk evidence ledgers.

The store is intentionally stdlib-only because the Presence server often runs
as a lightweight local bridge. Records are separated by project identity so an
uploaded Fides paper cannot silently inherit Gospel/BEAST ledger state.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from backend.services.sophia_academic_claim_tools import classify_claim_type, source_quality_rubric, verify_table_claim
except Exception:  # pragma: no cover - lightweight server fallback
    classify_claim_type = None  # type: ignore[assignment]
    source_quality_rubric = None  # type: ignore[assignment]
    verify_table_claim = None  # type: ignore[assignment]


SCHEMA_VERSION = "sophia.project_store.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_slug(value: str, fallback: str = "project") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-._").lower()
    return slug[:80] or fallback


def _sha256_text(value: str, length: int = 16) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()[:length]


def _sha256_json(value: Any, length: int = 64) -> str:
    material = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8", errors="ignore")).hexdigest()[:length]


def _issue_label(value: Any) -> str:
    return str(value or "").split(":", 1)[0].strip().lower()


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True, default=str)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


class SophiaProjectStore:
    """Small file-backed project/version/ledger store."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.projects_dir = self.root / "projects"
        self.events_path = self.root / "events.jsonl"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def derive_project_identity(
        self,
        *,
        session_token: str = "",
        document_name: str = "",
        document_hash: str = "",
        draft_text: str = "",
        explicit_project_id: str = "",
    ) -> Dict[str, Any]:
        """Derive a stable project identity from explicit ID or active document."""
        if explicit_project_id:
            project_id = _clean_slug(explicit_project_id)
            basis = "explicit_project_id"
        else:
            draft_hash = _sha256_text(draft_text[:12000], 16) if draft_text else ""
            identity_material = "|".join(
                part for part in (session_token[:24], document_name, document_hash, draft_hash) if part
            )
            if not identity_material:
                identity_material = f"sessionless-{_now()}"
            project_id = f"{_clean_slug(document_name or 'writing-desk')}-{_sha256_text(identity_material, 12)}"
            basis = "active_document_or_draft_hash"
        return {
            "project_id": project_id,
            "identity_basis": basis,
            "document_name": document_name,
            "document_hash": document_hash,
        }

    def _project_path(self, project_id: str) -> Path:
        return self.projects_dir / _clean_slug(project_id) / "project.json"

    def _load_project(self, project_id: str) -> Dict[str, Any]:
        path = self._project_path(project_id)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": project_id,
            "created_at": _now(),
            "updated_at": _now(),
            "draft_versions": [],
            "uploaded_documents": [],
            "retrieved_sources": [],
            "claim_ledger": [],
            "intervention_ledger": [],
            "source_pool": [],
            "mandos_category": "writing_desk",
        }

    def _save_project(self, project: Dict[str, Any]) -> None:
        project["updated_at"] = _now()
        _atomic_write_json(self._project_path(str(project["project_id"])), project)

    def _append_event(self, event: Dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, default=str) + "\n")

    def upsert_project(
        self,
        *,
        project_id: str,
        session_token: str = "",
        document_name: str = "",
        document_hash: str = "",
        mandos_category: str = "writing_desk",
    ) -> Dict[str, Any]:
        project = self._load_project(project_id)
        project["session_token_hash"] = _sha256_text(session_token, 16) if session_token else project.get("session_token_hash", "")
        project["mandos_category"] = mandos_category or project.get("mandos_category") or "writing_desk"
        if document_name or document_hash:
            doc_record = {
                "document_name": document_name,
                "document_hash": document_hash,
                "seen_at": _now(),
            }
            existing = {
                (doc.get("document_name"), doc.get("document_hash"))
                for doc in project.get("uploaded_documents", [])
                if isinstance(doc, dict)
            }
            if (document_name, document_hash) not in existing:
                project.setdefault("uploaded_documents", []).append(doc_record)
        self._save_project(project)
        return project

    def add_draft_version(
        self,
        *,
        project_id: str,
        draft_text: str,
        source: str = "writing_desk",
        line_start: int = 1,
        line_end: int = 1,
    ) -> Dict[str, Any]:
        project = self._load_project(project_id)
        draft_hash = _sha256_text(draft_text, 24)
        version_id = f"draft-{draft_hash}"
        version = {
            "version_id": version_id,
            "draft_hash": draft_hash,
            "source": source,
            "line_start": line_start,
            "line_end": line_end,
            "word_count": len(re.findall(r"\S+", draft_text or "")),
            "created_at": _now(),
        }
        if not any(v.get("version_id") == version_id for v in project.get("draft_versions", [])):
            project.setdefault("draft_versions", []).append(version)
            self._save_project(project)
            self._append_event({"event": "draft_version_added", "project_id": project_id, **version})
        return version

    def append_claim_records(
        self,
        *,
        project_id: str,
        draft_version_id: str,
        records: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        project = self._load_project(project_id)
        existing = {str(item.get("record_id") or ""): item for item in project.get("claim_ledger", [])}
        appended = 0
        updated = 0
        for raw in records:
            record = dict(raw or {})
            if classify_claim_type and str(record.get("claim") or "").strip():
                classification = classify_claim_type(str(record.get("claim") or ""))
                record.setdefault("claim_type", classification.get("claim_type"))
                record.setdefault("claim_type_analysis", classification)
                record.setdefault("evidence_standard", classification.get("evidence_standard"))
            if source_quality_rubric:
                rubric = source_quality_rubric(record)
                record.setdefault("source_quality_rubric", rubric)
                record.setdefault("quality_score", rubric.get("score"))
                record.setdefault("quality", rubric.get("score"))
            record_id = str(record.get("record_id") or "")
            if not record_id:
                material = "|".join(
                    str(record.get(key) or "")[:500]
                    for key in ("claim", "source_name", "exact_span", "status")
                )
                record_id = f"claim-{_sha256_text(material, 18)}"
            record.update({
                "record_id": record_id,
                "project_id": project_id,
                "draft_version_id": draft_version_id,
                "schema_version": SCHEMA_VERSION,
                "updated_at": _now(),
            })
            if record_id in existing:
                prior = existing[record_id]
                prior.update(record)
                prior.setdefault("created_at", record.get("created_at") or _now())
                updated += 1
            else:
                record.setdefault("created_at", _now())
                project.setdefault("claim_ledger", []).append(record)
                existing[record_id] = record
                appended += 1
        self._save_project(project)
        self._append_event({
            "event": "claim_records_appended",
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "appended": appended,
            "updated": updated,
            "at": _now(),
        })
        return {
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "appended": appended,
            "updated": updated,
            "total_claim_records": len(project.get("claim_ledger", [])),
        }

    def append_intervention_record(
        self,
        *,
        project_id: str,
        draft_version_id: str,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persist a pedagogical intervention for ipsative review."""
        project = self._load_project(project_id)
        payload = dict(record or {})
        material = "|".join(
            str(payload.get(key) or "")[:500]
            for key in ("task", "selected_excerpt", "pedagogical_move", "next_revision_move")
        )
        created_at = str(payload.get("created_at") or _now())
        intervention_id = str(payload.get("intervention_id") or f"intervention-{_sha256_text(material + '|' + created_at, 18)}")
        payload.update({
            "intervention_id": intervention_id,
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "updated_at": _now(),
        })
        existing = {
            str(item.get("intervention_id") or ""): item
            for item in project.get("intervention_ledger", [])
            if isinstance(item, dict)
        }
        if intervention_id in existing:
            existing[intervention_id].update(payload)
            action = "updated"
        else:
            project.setdefault("intervention_ledger", []).append(payload)
            action = "appended"
        self._save_project(project)
        self._append_event({
            "event": "intervention_record_appended",
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "intervention_id": intervention_id,
            "action": action,
            "at": _now(),
        })
        return {
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "intervention_id": intervention_id,
            "action": action,
            "total_interventions": len(project.get("intervention_ledger", [])),
        }

    def append_final_decision(
        self,
        *,
        project_id: str,
        draft_version_id: str = "",
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Record the learner's final decision after Sophia's scaffolding."""
        project = self._load_project(project_id)
        payload = dict(decision or {})
        created_at = str(payload.get("created_at") or _now())
        material = "|".join(
            str(payload.get(key) or "")[:500]
            for key in ("claim_record_id", "decision", "rationale", "final_text_hash")
        )
        decision_id = str(payload.get("decision_id") or f"decision-{_sha256_text(material + '|' + created_at, 18)}")
        payload.update({
            "decision_id": decision_id,
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "updated_at": _now(),
            "authorship_assertion": payload.get("authorship_assertion") or "human_final_decision",
        })
        project.setdefault("final_decision_ledger", []).append(payload)
        self._save_project(project)
        self._append_event({
            "event": "final_decision_appended",
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "decision_id": decision_id,
            "at": _now(),
        })
        return {
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "decision_id": decision_id,
            "total_final_decisions": len(project.get("final_decision_ledger", [])),
        }

    def append_retrieved_sources(
        self,
        *,
        project_id: str,
        sources: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Attach retrieved source leads to a project without claiming support."""
        project = self._load_project(project_id)
        existing = {
            str(item.get("source_id") or item.get("title") or item.get("url") or "")
            for item in project.get("retrieved_sources", [])
            if isinstance(item, dict)
        }
        appended = 0
        for index, raw in enumerate(sources):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or raw.get("source") or raw.get("name") or f"Retrieved Source {index + 1}").strip()
            url = str(raw.get("url") or raw.get("doi") or "").strip()
            material = "|".join(part for part in (title, url, str(raw.get("year") or "")) if part)
            source_id = str(raw.get("source_id") or f"source-{_sha256_text(material, 18)}")
            if source_id in existing:
                continue
            record = {
                "source_id": source_id,
                "title": title,
                "url": raw.get("url") or "",
                "doi": raw.get("doi") or "",
                "year": raw.get("year") or "",
                "authors": raw.get("authors") or [],
                "summary": raw.get("summary") or raw.get("abstract") or "",
                "source": raw.get("source") or raw.get("provider") or "academic_retrieval",
                "quality": raw.get("quality") or raw.get("quality_score"),
                "relevance": raw.get("relevance") or raw.get("relevance_score"),
                "captured_at": _now(),
                "support_status": "lead_only_unmapped",
            }
            project.setdefault("retrieved_sources", []).append(record)
            existing.add(source_id)
            appended += 1
        self._save_project(project)
        self._append_event({
            "event": "retrieved_sources_appended",
            "project_id": project_id,
            "appended": appended,
            "at": _now(),
        })
        return {
            "project_id": project_id,
            "appended": appended,
            "total_retrieved_sources": len(project.get("retrieved_sources", [])),
        }

    def append_source_records(
        self,
        *,
        project_id: str,
        sources: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        project = self._load_project(project_id)
        existing = {
            (str(item.get("name") or ""), str(item.get("text_hash") or ""))
            for item in project.get("source_pool", [])
            if isinstance(item, dict)
        }
        appended = 0
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or "")
            record = {
                "name": str(raw.get("name") or raw.get("source_name") or raw.get("title") or "Unnamed source"),
                "category": str(raw.get("category") or raw.get("source_type") or "session_source"),
                "text_hash": _sha256_text(text, 24) if text else "",
                "text": text[:20000],
                "char_count": len(text),
                "recorded_at": _now(),
            }
            key = (record["name"], record["text_hash"])
            if key in existing:
                continue
            project.setdefault("source_pool", []).append(record)
            existing.add(key)
            appended += 1
        self._save_project(project)
        if appended:
            self._append_event({
                "event": "source_records_appended",
                "project_id": project_id,
                "appended": appended,
                "at": _now(),
            })
        return {
            "project_id": project_id,
            "appended": appended,
            "total_source_records": len(project.get("source_pool", [])),
        }

    def summarize_project(self, project_id: str) -> Dict[str, Any]:
        project = self._load_project(project_id)
        records = [r for r in project.get("claim_ledger", []) if isinstance(r, dict)]
        interventions = [r for r in project.get("intervention_ledger", []) if isinstance(r, dict)]
        status_counts: Dict[str, int] = {}
        for record in records:
            status = str(record.get("status") or "open")
            status_counts[status] = status_counts.get(status, 0) + 1
        issue_counts: Dict[str, int] = {}
        office_counts: Dict[str, int] = {}
        for item in interventions:
            office = str(((item.get("pedagogical_plan") or {}).get("selected_office")) or item.get("office") or "unknown")
            office_counts[office] = office_counts.get(office, 0) + 1
            for finding in item.get("findings") or []:
                label = str(finding).split(":", 1)[0].strip().lower() or "unknown"
                issue_counts[label] = issue_counts.get(label, 0) + 1
        repeated_weakness_types = [
            {"issue": key, "count": value}
            for key, value in sorted(issue_counts.items(), key=lambda pair: (-pair[1], pair[0]))
            if value >= 2
        ][:8]
        improvement = self._latest_intervention_improvement(interventions)
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": project_id,
            "draft_versions": len(project.get("draft_versions", [])),
            "uploaded_documents": len(project.get("uploaded_documents", [])),
            "retrieved_sources": len(project.get("retrieved_sources", [])),
            "source_pool": len(project.get("source_pool", [])),
            "source_pool_records": len(project.get("source_pool", [])),
            "claim_records": len(records),
            "intervention_records": len(interventions),
            "status_counts": status_counts,
            "pedagogy_office_counts": office_counts,
            "repeated_weakness_types": repeated_weakness_types,
            "latest_intervention_improvement": improvement,
            "weak_warrants": sum(1 for r in records if str(r.get("status") or "") in {"warrant-needed", "partial"}),
            "missing_limitations": sum(1 for r in records if not str(r.get("limitation") or "").strip()),
            "unsupported_claims": sum(1 for r in records if str(r.get("status") or "") in {"needs-source", "unsupported", "contradicted"}),
            "updated_at": project.get("updated_at"),
        }

    @staticmethod
    def _latest_intervention_improvement(interventions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(interventions) < 2:
            return {
                "status": "insufficient_history",
                "prior_issue_count": None,
                "latest_issue_count": None,
                "resolved_issue_labels": [],
                "new_issue_labels": [],
                "persistent_issue_labels": [],
                "interpretation": "Need at least two Writing Desk interventions on this project to estimate revision movement.",
            }
        ordered = sorted(interventions, key=lambda item: str(item.get("created_at") or ""))
        prior = ordered[-2]
        latest = ordered[-1]
        prior_labels = {
            _issue_label(item)
            for item in prior.get("findings") or []
            if _issue_label(item)
        }
        latest_labels = {
            _issue_label(item)
            for item in latest.get("findings") or []
            if _issue_label(item)
        }
        resolved = sorted(prior_labels - latest_labels)
        new = sorted(latest_labels - prior_labels)
        persistent = sorted(prior_labels & latest_labels)
        prior_count = len(prior_labels)
        latest_count = len(latest_labels)
        if latest_count < prior_count and len(new) <= len(resolved):
            status = "improved"
        elif latest_count > prior_count or new:
            status = "regressed_or_new_risk"
        elif persistent:
            status = "stable_unresolved"
        else:
            status = "stable_clear"
        return {
            "status": status,
            "prior_intervention_id": prior.get("intervention_id"),
            "latest_intervention_id": latest.get("intervention_id"),
            "prior_issue_count": prior_count,
            "latest_issue_count": latest_count,
            "resolved_issue_labels": resolved,
            "new_issue_labels": new,
            "persistent_issue_labels": persistent,
            "interpretation": {
                "improved": "Latest feedback shows fewer or weaker issue labels than the prior intervention.",
                "regressed_or_new_risk": "Latest feedback introduced new issue labels or increased the issue count.",
                "stable_unresolved": "The same issue labels remain visible; Sophia should scaffold the repeated pattern.",
                "stable_clear": "Neither the prior nor latest intervention shows issue labels.",
            }.get(status, "Compare the two interventions before making a learning claim."),
        }

    @staticmethod
    def _support_confidence(claim: Dict[str, Any]) -> float:
        """Small transparent confidence score for the mirror ledger."""
        score = 0.0
        support = str(claim.get("support_label") or "").lower()
        status = str(claim.get("status") or "").lower()
        entailment_status = str(claim.get("entailment_status") or "").lower()
        entailment_score = claim.get("entailment_score")
        if support in {"supports", "directly supports", "partial support"}:
            score += 0.25
        if status in {"supported", "partial"}:
            score += 0.2
        if entailment_status in {"entails", "supported", "directly_supports", "directly supports"}:
            score += 0.12
        elif entailment_status in {"partial_support", "partial support", "partially_supports", "partially supports"}:
            score += 0.06
        if str(claim.get("exact_span") or "").strip():
            score += 0.2
        if str(claim.get("warrant") or "").strip():
            score += 0.15
        if str(claim.get("limitation") or "").strip():
            score += 0.1
        if str(claim.get("page_locator") or "").strip() or str(claim.get("page_status") or "").strip():
            score += 0.1
        if entailment_score is not None:
            try:
                score += max(0.0, min(1.0, float(entailment_score))) * 0.08
            except (TypeError, ValueError):
                pass
        if entailment_status in {"contradiction", "contradicts", "does_not_support", "does not support", "not_supported"}:
            score = min(score, 0.35)
        return round(min(1.0, score), 3)

    @staticmethod
    def _risk_flags_for_claim(claim: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        status = str(claim.get("status") or "").lower()
        support = str(claim.get("support_label") or "").lower()
        if status in {"needs-source", "unsupported", "contradicted"} or support in {"does not support", "unsupported"}:
            flags.append("unsupported_or_missing_source")
        entailment_status = str(claim.get("entailment_status") or "").lower()
        if entailment_status in {"contradiction", "contradicts"}:
            flags.append("nli_contradiction")
        if entailment_status in {"does_not_support", "does not support", "not_supported"}:
            flags.append("nli_does_not_support")
        if entailment_status in {"unknown", "not_tested", "insufficient_text"}:
            flags.append("nli_unverified")
        if status in {"warrant-needed", "partial"} or not str(claim.get("warrant") or "").strip():
            flags.append("warrant_gap")
        if not str(claim.get("limitation") or "").strip():
            flags.append("limitation_gap")
        if not str(claim.get("exact_span") or "").strip():
            flags.append("missing_exact_span")
        page_status = str(claim.get("page_status") or "").lower()
        if "do not invent" in page_status or "no page" in page_status:
            flags.append("page_locator_not_visible")
        return flags

    @staticmethod
    def _source_quality_snapshot(claim: Dict[str, Any]) -> Dict[str, Any]:
        """Capture source-quality signals without turning leads into proof."""
        return {
            "citation": claim.get("citation") or "",
            "doi": claim.get("doi") or "",
            "url": claim.get("url") or "",
            "quality_score": claim.get("quality_score") or claim.get("quality") or None,
            "relevance_score": claim.get("relevance") or claim.get("relevance_score") or None,
            "rubric": claim.get("source_quality_rubric") or {},
            "source_status": (
                "span_mapped"
                if str(claim.get("exact_span") or "").strip()
                else "lead_or_unmapped"
            ),
        }

    @staticmethod
    def _speculum_unknowns(claim: Dict[str, Any], intervention: Dict[str, Any]) -> List[str]:
        unknowns: List[str] = []
        if not str(claim.get("exact_span") or "").strip():
            unknowns.append("No exact source span is visible for this claim.")
        if not str(claim.get("warrant") or "").strip():
            unknowns.append("The warrant connecting claim to evidence is not yet explicit.")
        if not str(claim.get("limitation") or "").strip():
            unknowns.append("The limitation/scope boundary is not yet explicit.")
        if not str(claim.get("page_locator") or "").strip():
            unknowns.append("No page locator is visible; Sophia must not invent one.")
        if not intervention:
            unknowns.append("No pedagogical intervention is linked strongly enough to this claim yet.")
        if not unknowns:
            unknowns.append("No major unknowns recorded by the current mirror fields.")
        return unknowns

    @staticmethod
    def _revision_movement_for_claim(
        claim: Dict[str, Any],
        interventions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Summarize before/after movement visible in intervention history."""
        if len(interventions) < 2:
            return {
                "status": "insufficient_history",
                "prior_intervention_id": "",
                "latest_intervention_id": str(interventions[-1].get("intervention_id") or "") if interventions else "",
                "resolved_issue_labels": [],
                "new_issue_labels": [],
                "persistent_issue_labels": [],
                "interpretation": "Need at least two interventions to judge revision movement for this claim.",
            }
        ordered = sorted(interventions, key=lambda item: str(item.get("created_at") or ""))
        prior = ordered[-2]
        latest = ordered[-1]
        prior_labels = {_issue_label(item) for item in prior.get("findings") or [] if _issue_label(item)}
        latest_labels = {_issue_label(item) for item in latest.get("findings") or [] if _issue_label(item)}
        resolved = sorted(prior_labels - latest_labels)
        new = sorted(latest_labels - prior_labels)
        persistent = sorted(prior_labels & latest_labels)
        if resolved and not new:
            status = "improved"
        elif new:
            status = "new_or_shifted_risk"
        elif persistent:
            status = "stable_unresolved"
        else:
            status = "stable_clear"
        return {
            "status": status,
            "prior_intervention_id": prior.get("intervention_id") or "",
            "latest_intervention_id": latest.get("intervention_id") or "",
            "resolved_issue_labels": resolved,
            "new_issue_labels": new,
            "persistent_issue_labels": persistent,
            "interpretation": {
                "improved": "The latest intervention shows previously flagged issues resolved without adding new visible risks.",
                "new_or_shifted_risk": "The latest intervention introduced new issue labels or shifted the risk profile.",
                "stable_unresolved": "The same issue labels remain visible and should be scaffolded again.",
                "stable_clear": "No issue labels are visible in the compared interventions.",
            }.get(status, "Compare interventions before making a learning claim."),
        }

    @staticmethod
    def _evidence_state_transition(claim: Dict[str, Any]) -> Dict[str, Any]:
        has_source = bool(str(claim.get("source_name") or "").strip()) and str(claim.get("source_name") or "").lower() != "unassigned"
        has_span = bool(str(claim.get("exact_span") or "").strip())
        has_warrant = bool(str(claim.get("warrant") or "").strip())
        has_limitation = bool(str(claim.get("limitation") or "").strip())
        supported = str(claim.get("status") or "").lower() in {"supported", "partial"} or str(claim.get("support_label") or "").lower() in {"supports", "directly supports", "partial support"}
        if not has_source:
            state = "unmapped"
        elif not has_span:
            state = "lead_found"
        elif not has_warrant:
            state = "span_mapped_needs_warrant"
        elif not has_limitation:
            state = "warrant_added_needs_limitation"
        elif supported:
            state = "support_ready_with_limitation"
        else:
            state = "mapped_but_not_supporting"
        completed = [
            label for label, done in (
                ("source_named", has_source),
                ("span_mapped", has_span),
                ("warrant_added", has_warrant),
                ("limitation_added", has_limitation),
                ("support_status_recorded", bool(claim.get("status") or claim.get("support_label"))),
            )
            if done
        ]
        remaining = [
            label for label, done in (
                ("source_named", has_source),
                ("span_mapped", has_span),
                ("warrant_added", has_warrant),
                ("limitation_added", has_limitation),
            )
            if not done
        ]
        return {
            "state": state,
            "completed_steps": completed,
            "remaining_steps": remaining,
            "progress_ratio": round(len(completed) / 5.0, 3),
        }

    @staticmethod
    def _claim_lineage_for_claim(
        claim: Dict[str, Any],
        decisions: List[Dict[str, Any]],
        movement: Dict[str, Any],
    ) -> Dict[str, Any]:
        if decisions:
            latest_decision = str(decisions[-1].get("decision") or "")
            if "abandon" in latest_decision or "remove" in latest_decision:
                state = "abandoned_by_author"
            elif "limitation" in latest_decision:
                state = "retained_with_limitation"
            elif "revise" in latest_decision:
                state = "revised_by_author"
            else:
                state = "author_decision_recorded"
        elif movement.get("status") == "improved":
            state = "revision_improved_after_scaffold"
        elif str(claim.get("status") or "").lower() in {"unsupported", "needs-source", "contradicted"}:
            state = "claim_at_risk"
        else:
            state = "open_claim"
        return {
            "state": state,
            "draft_version_id": claim.get("draft_version_id") or "",
            "latest_decision": decisions[-1].get("decision") if decisions else "",
            "decision_count": len(decisions),
            "movement_status": movement.get("status") or "unknown",
            "interpretation": {
                "abandoned_by_author": "The human author chose not to retain the claim.",
                "retained_with_limitation": "The human author retained the claim while preserving a scope limit.",
                "revised_by_author": "The human author recorded revision after Sophia's scaffolding.",
                "author_decision_recorded": "A human decision is present, but its revision meaning should be inspected.",
                "revision_improved_after_scaffold": "Intervention history suggests improvement, but no final user decision is recorded yet.",
                "claim_at_risk": "The claim remains risky until the author maps evidence, warrant, and limitation.",
                "open_claim": "The claim is open and awaits author decision.",
            }.get(state, "Inspect the claim history before making a learning claim."),
        }

    def _build_speculum_ledger(
        self,
        *,
        claims: List[Dict[str, Any]],
        interventions: List[Dict[str, Any]],
        source_pool: Optional[List[Dict[str, Any]]] = None,
        final_decisions: List[Dict[str, Any]],
        include_excerpts: bool,
    ) -> List[Dict[str, Any]]:
        """Derive the Speculum mirror ledger from existing auditable ledgers."""
        latest_intervention = sorted(
            interventions,
            key=lambda item: str(item.get("created_at") or ""),
        )[-1] if interventions else {}
        decisions_by_claim: Dict[str, List[Dict[str, Any]]] = {}
        for decision in final_decisions:
            decisions_by_claim.setdefault(str(decision.get("claim_record_id") or ""), []).append(decision)
        table_report: Dict[str, Any] = {}
        if verify_table_claim and source_pool:
            try:
                from backend.services.advanced_evidence_engine import extract_structured_tables
                table_report = extract_structured_tables(source_pool)
            except Exception:
                table_report = {}

        entries: List[Dict[str, Any]] = []
        for index, claim in enumerate(claims[:200], start=1):
            record_id = str(claim.get("record_id") or f"claim-{index:03d}")
            flags = self._risk_flags_for_claim(claim)
            confidence = self._support_confidence(claim)
            learner_next_action = (
                str(latest_intervention.get("next_revision_move") or "").strip()
                or (
                    "Add a visible source span, warrant, and limitation before relying on this claim."
                    if flags and not latest_intervention
                    else "Decide whether to keep, revise, or cite this claim in your own final wording."
                    if not latest_intervention
                    else ""
                )
            )
            authorship_boundary = (
                str(latest_intervention.get("authorship_boundary") or "").strip()
                or (
                    "Sophia mirrors evidence and risk; the human author decides wording, citations, and submission."
                    if not latest_intervention
                    else ""
                )
            )
            table_verification = claim.get("table_claim_verification") or {}
            if verify_table_claim and not table_verification:
                try:
                    table_verification = verify_table_claim(str(claim.get("claim") or ""), table_report)
                except Exception:
                    table_verification = {}
            entry = {
                "speculum_id": f"speculum-{_sha256_text(record_id + '|' + str(claim.get('claim') or ''), 18)}",
                "schema_version": "sophia.speculum_entry.v2",
                "mirror_basis": [
                    "claim_ledger",
                    "intervention_ledger" if latest_intervention else "no_intervention_linked",
                    "final_decision_ledger" if decisions_by_claim.get(record_id) else "no_final_decision_linked",
                ],
                "claim_record_id": record_id,
                "line_start": claim.get("line_start"),
                "line_end": claim.get("line_end"),
                "claim_hash": _sha256_text(str(claim.get("claim") or ""), 24),
                "claim": str(claim.get("claim") or "")[:700] if include_excerpts else "",
                "claim_type_analysis": claim.get("claim_type_analysis") or {
                    "claim_type": claim.get("claim_type") or "unknown",
                    "evidence_standard": claim.get("evidence_standard") or "",
                },
                "evidence_source": claim.get("source_name") or "",
                "source_quality": self._source_quality_snapshot(claim),
                "evidence_span_hash": _sha256_text(str(claim.get("exact_span") or ""), 24),
                "evidence_span": str(claim.get("exact_span") or "")[:700] if include_excerpts else "",
                "page_locator": claim.get("page_locator") or "",
                "support_label": claim.get("support_label") or "unknown",
                "status": claim.get("status") or "open",
                "nli_support": {
                    "entailment_status": claim.get("entailment_status") or "",
                    "entailment_score": claim.get("entailment_score"),
                    "semantic_similarity": claim.get("semantic_similarity"),
                    "support_model": claim.get("support_model") or claim.get("entailment_model") or "",
                    "similarity_model": claim.get("similarity_model") or "",
                    "support_source": claim.get("support_source") or "not_recorded",
                },
                "table_claim_verification": table_verification,
                "warrant": claim.get("warrant") or "",
                "limitation": claim.get("limitation") or "",
                "authorship_boundary": authorship_boundary,
                "learner_next_action": learner_next_action,
                "pedagogical_move": latest_intervention.get("pedagogical_move") or "",
                "response_provenance": {
                    "response_source": (
                        latest_intervention.get("response_source")
                        or latest_intervention.get("source")
                        or "not_recorded"
                    ),
                    "response_source_detail": latest_intervention.get("response_source_detail") or "",
                    "repair_steps": list(latest_intervention.get("repair_steps") or [])[:20],
                    "release_ledger_hash": _sha256_json(latest_intervention.get("response_release_ledger") or {}, 24)
                    if latest_intervention.get("response_release_ledger") else "",
                },
                "evidence_transition": self._evidence_state_transition(claim),
                "revision_movement": self._revision_movement_for_claim(claim, interventions),
                "unresolved_risks": flags,
                "unknowns": self._speculum_unknowns(claim, latest_intervention),
                "support_confidence": confidence,
                "final_user_decisions": [
                    {
                        "decision": item.get("decision") or "",
                        "rationale": item.get("rationale") or "",
                        "authorship_assertion": item.get("authorship_assertion") or "human_final_decision",
                    }
                    for item in decisions_by_claim.get(record_id, [])[-5:]
                ],
            }
            entry["claim_lineage"] = self._claim_lineage_for_claim(
                claim,
                decisions_by_claim.get(record_id, []),
                entry["revision_movement"],
            )
            entries.append(entry)
        return entries

    @staticmethod
    def _provider_contribution_class(entry_scores: List[Dict[str, Any]], speculum_ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
        classes: Dict[str, int] = {}
        for entry in speculum_ledger:
            provenance = entry.get("response_provenance") or {}
            source = str(provenance.get("response_source") or "not_recorded")
            repair_steps = list(provenance.get("repair_steps") or [])
            if source == "model":
                label = "model_led"
            elif source == "hybrid_model_with_constitutional_judgment":
                label = "hybrid_model_with_governance"
            elif source == "runtime_synthesis" and repair_steps:
                label = "runtime_synthesized_with_repair"
            elif source == "runtime_repair" or repair_steps:
                label = "runtime_repaired"
            elif source == "runtime_synthesis":
                label = "runtime_synthesized"
            elif source == "not_recorded":
                label = "not_recorded"
            else:
                label = source
            classes[label] = classes.get(label, 0) + 1
        dominant = sorted(classes.items(), key=lambda pair: (-pair[1], pair[0]))[0][0] if classes else "not_recorded"
        return {
            "dominant_class": dominant,
            "counts": classes,
            "interpretation": (
                "Provider contribution describes whether the visible help was model-led, runtime-repaired, "
                "runtime-synthesized, or not recorded. It is descriptive, not a quality penalty by itself."
            ),
        }

    @staticmethod
    def _category_subscores(dimension_means: Dict[str, float]) -> Dict[str, Any]:
        groups = {
            "authorship_safety": ["no_substitution", "learner_agency"],
            "evidence_integrity": ["source_grounding", "semantic_entailment", "provenance_visibility", "source_quality_signal"],
            "reasoning_quality": ["warrant_quality", "limitation_quality"],
            "pedagogical_usefulness": ["revision_usefulness", "revision_movement"],
            "audit_maturity": ["response_provenance", "unknown_transparency"],
        }
        scores: Dict[str, float] = {}
        for name, dims in groups.items():
            values = [float(dimension_means.get(dim, 0.0)) for dim in dims]
            scores[name] = round(sum(values) / len(values), 3) if values else 0.0
        weakest = sorted(scores.items(), key=lambda pair: pair[1])[:2]
        return {
            "scores": scores,
            "weakest_categories": [{"category": key, "score": value} for key, value in weakest],
        }

    @staticmethod
    def _score_authorship_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Transparent authorship-preservation scoring for one mirror entry."""
        risks = set(str(item) for item in (entry.get("unresolved_risks") or []))
        support = str(entry.get("support_label") or "").lower()
        status = str(entry.get("status") or "").lower()
        has_evidence = bool(str(entry.get("evidence_span") or entry.get("evidence_span_hash") or "").strip())
        has_warrant = bool(str(entry.get("warrant") or "").strip())
        has_limitation = bool(str(entry.get("limitation") or "").strip())
        has_next_action = bool(str(entry.get("learner_next_action") or "").strip())
        has_boundary = bool(str(entry.get("authorship_boundary") or "").strip())
        provenance = entry.get("response_provenance") or {}
        source_quality = entry.get("source_quality") or {}
        movement = entry.get("revision_movement") or {}
        nli_support = entry.get("nli_support") or {}
        pedagogical_move = str(entry.get("pedagogical_move") or "").lower()
        unknowns = [
            str(item)
            for item in (entry.get("unknowns") or [])
            if "No major unknowns" not in str(item)
        ]
        response_source = str(provenance.get("response_source") or "not_recorded")
        has_release_trace = bool(provenance.get("release_ledger_hash"))
        source_quality_value = source_quality.get("quality_score")
        source_relevance_value = source_quality.get("relevance_score")
        source_has_identifier = bool(source_quality.get("doi") or source_quality.get("url") or source_quality.get("citation"))
        supported = support in {"supports", "directly supports", "partial support"} or status in {"supported", "partial"}
        entailment_status = str(nli_support.get("entailment_status") or "").lower()
        entailment_score = nli_support.get("entailment_score")
        semantic_similarity = nli_support.get("semantic_similarity")
        nli_positive = entailment_status in {"entails", "supported", "directly_supports", "directly supports"}
        nli_partial = entailment_status in {"partial_support", "partial support", "partially_supports", "partially supports"}
        nli_negative = entailment_status in {"contradiction", "contradicts", "does_not_support", "does not support", "not_supported"}
        nli_recorded = bool(entailment_status)
        try:
            entailment_value = max(0.0, min(1.0, float(entailment_score))) if entailment_score is not None else None
        except (TypeError, ValueError):
            entailment_value = None
        try:
            similarity_value = max(0.0, min(1.0, float(semantic_similarity))) if semantic_similarity is not None else None
        except (TypeError, ValueError):
            similarity_value = None
        substitution_surface = bool(
            re.search(
                r"\b(polished answer|polished sentence|submission-ready|provides? .*answer|instead of preserving authorship|write(?:s)? .*for (?:the )?(?:user|learner))\b",
                pedagogical_move,
                re.IGNORECASE,
            )
        )

        dimensions = {
            "no_substitution": 1.0 if has_boundary else 0.65,
            "source_grounding": 1.0 if has_evidence and supported else 0.55 if has_evidence else 0.2,
            "semantic_entailment": (
                max(0.72, entailment_value or 0.72)
                if nli_positive
                else max(0.58, min(0.82, entailment_value or 0.62))
                if nli_partial
                else min(0.28, 1.0 - (entailment_value or 0.72))
                if nli_negative
                else 0.55
            ),
            "provenance_visibility": 1.0 if entry.get("evidence_source") and has_evidence else 0.6 if entry.get("evidence_source") else 0.25,
            "warrant_quality": 1.0 if has_warrant else 0.35,
            "limitation_quality": 1.0 if has_limitation else 0.35,
            "learner_agency": 1.0 if has_next_action and has_boundary else 0.55 if has_next_action else 0.25,
            "revision_usefulness": 1.0 if has_next_action and not {"warrant_gap", "limitation_gap"} <= risks else 0.7 if has_next_action else 0.25,
            "response_provenance": 1.0 if response_source != "not_recorded" and has_release_trace else 0.75 if response_source != "not_recorded" else 0.35,
            "revision_movement": {
                "improved": 1.0,
                "stable_clear": 0.9,
                "stable_unresolved": 0.65,
                "new_or_shifted_risk": 0.45,
                "insufficient_history": 0.55,
            }.get(str(movement.get("status") or "insufficient_history"), 0.55),
            "source_quality_signal": (
                max(0.0, min(1.0, (
                    (float(source_quality_value) if source_quality_value is not None else 0.5) * 0.55
                    + (float(source_relevance_value) if source_relevance_value is not None else 0.5) * 0.35
                    + (1.0 if source_has_identifier else 0.4) * 0.10
                )))
            ),
            "unknown_transparency": max(0.2, 1.0 - min(0.8, len(unknowns) * 0.18)),
        }
        if "unsupported_or_missing_source" in risks:
            dimensions["source_grounding"] = min(dimensions["source_grounding"], 0.35)
        if "nli_contradiction" in risks or "nli_does_not_support" in risks:
            dimensions["source_grounding"] = min(dimensions["source_grounding"], 0.25)
            dimensions["warrant_quality"] = min(dimensions["warrant_quality"], 0.3)
            dimensions["semantic_entailment"] = min(dimensions["semantic_entailment"], 0.2)
        if "missing_exact_span" in risks:
            dimensions["provenance_visibility"] = min(dimensions["provenance_visibility"], 0.45)
        if "warrant_gap" in risks:
            dimensions["warrant_quality"] = min(dimensions["warrant_quality"], 0.35)
        if "limitation_gap" in risks:
            dimensions["limitation_quality"] = min(dimensions["limitation_quality"], 0.35)
        if substitution_surface:
            dimensions["no_substitution"] = min(dimensions["no_substitution"], 0.15)
            dimensions["learner_agency"] = min(dimensions["learner_agency"], 0.2)
            dimensions["revision_usefulness"] = min(dimensions["revision_usefulness"], 0.25)

        weights = {
            "no_substitution": 0.15,
            "source_grounding": 0.12,
            "semantic_entailment": 0.1,
            "provenance_visibility": 0.1,
            "warrant_quality": 0.09,
            "limitation_quality": 0.09,
            "learner_agency": 0.13,
            "revision_usefulness": 0.09,
            "response_provenance": 0.05,
            "revision_movement": 0.035,
            "source_quality_signal": 0.025,
            "unknown_transparency": 0.02,
        }
        score = round(sum(dimensions[key] * weights[key] for key in weights), 3)
        uncertainty_penalty = 0.0
        if response_source == "not_recorded":
            uncertainty_penalty += 0.03
        if movement.get("status") == "insufficient_history":
            uncertainty_penalty += 0.03
        if unknowns:
            uncertainty_penalty += min(0.08, len(unknowns) * 0.015)
        if not nli_recorded:
            uncertainty_penalty += 0.025
        elif entailment_status in {"unknown", "not_tested", "insufficient_text"}:
            uncertainty_penalty += 0.02
        if similarity_value is not None and has_evidence and similarity_value < 0.35:
            uncertainty_penalty += 0.025
        if substitution_surface:
            uncertainty_penalty += 0.08
        adjusted_score = round(max(0.0, score - uncertainty_penalty), 3)
        if adjusted_score >= 0.85:
            band = "strong"
        elif adjusted_score >= 0.7:
            band = "adequate"
        elif adjusted_score >= 0.5:
            band = "fragile"
        else:
            band = "weak"
        return {
            "speculum_id": entry.get("speculum_id") or "",
            "claim_record_id": entry.get("claim_record_id") or "",
            "score": adjusted_score,
            "raw_weighted_score": score,
            "band": band,
            "dimensions": {key: round(value, 3) for key, value in dimensions.items()},
            "dimension_weights": weights,
            "risk_penalties": sorted(risks),
            "substitution_surface_detected": substitution_surface,
            "uncertainty_penalty": round(uncertainty_penalty, 3),
            "uncertainty_reasons": [
                reason for reason, active in (
                    ("response_source_not_recorded", response_source == "not_recorded"),
                    ("insufficient_revision_history", movement.get("status") == "insufficient_history"),
                    ("visible_unknowns_present", bool(unknowns)),
                    ("semantic_entailment_not_recorded", not nli_recorded),
                    ("low_semantic_similarity", similarity_value is not None and has_evidence and similarity_value < 0.35),
                    ("substitution_surface_detected", substitution_surface),
                )
                if active
            ],
        }

    def _build_authorship_preservation_index(self, speculum_ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate Speculum entries into an auditable authorship index."""
        entry_scores = [self._score_authorship_entry(entry) for entry in speculum_ledger]
        if not entry_scores:
            return {
                "schema_version": "sophia.authorship_preservation_index.v2",
                "score": None,
                "lower_bound_score": None,
                "band": "not_computable",
                "maturity": "no_data",
                "entry_scores": [],
                "dimension_means": {},
                "interpretation": "No Speculum entries were available to score.",
                "validation_status": "engineering_metric_unvalidated",
            }
        dimension_totals: Dict[str, float] = {}
        uncertainty_total = 0.0
        for scored in entry_scores:
            uncertainty_total += float(scored.get("uncertainty_penalty") or 0.0)
            for key, value in (scored.get("dimensions") or {}).items():
                dimension_totals[key] = dimension_totals.get(key, 0.0) + float(value)
        dimension_means = {
            key: round(value / len(entry_scores), 3)
            for key, value in sorted(dimension_totals.items())
        }
        category_subscores = self._category_subscores(dimension_means)
        provider_contribution = self._provider_contribution_class(entry_scores, speculum_ledger)
        score = round(sum(item["score"] for item in entry_scores) / len(entry_scores), 3)
        raw_score = round(sum(item.get("raw_weighted_score", item["score"]) for item in entry_scores) / len(entry_scores), 3)
        mean_uncertainty = round(uncertainty_total / len(entry_scores), 3)
        lower_bound_score = round(max(0.0, score - mean_uncertainty), 3)
        score_values = [float(item["score"]) for item in entry_scores]
        score_min = round(min(score_values), 3)
        score_max = round(max(score_values), 3)
        weak_or_fragile = sum(1 for item in entry_scores if item.get("band") in {"weak", "fragile"})
        provenance_recorded = sum(
            1
            for item in entry_scores
            if "response_source_not_recorded" not in set(item.get("uncertainty_reasons") or [])
        )
        if len(entry_scores) >= 10 and mean_uncertainty <= 0.04 and weak_or_fragile == 0:
            maturity = "stable_engineering_signal"
        elif mean_uncertainty <= 0.06 and weak_or_fragile <= max(1, len(entry_scores) // 4):
            maturity = "usable_engineering_signal"
        else:
            maturity = "fragile_engineering_signal"
        if score >= 0.85:
            band = "strong"
        elif score >= 0.7:
            band = "adequate"
        elif score >= 0.5:
            band = "fragile"
        else:
            band = "weak"
        weakest = sorted(dimension_means.items(), key=lambda pair: pair[1])[:3]
        return {
            "schema_version": "sophia.authorship_preservation_index.v2",
            "score": score,
            "raw_weighted_score": raw_score,
            "lower_bound_score": lower_bound_score,
            "band": band,
            "maturity": maturity,
            "entry_scores": entry_scores,
            "dimension_means": dimension_means,
            "category_subscores": category_subscores,
            "provider_contribution": provider_contribution,
            "weakest_dimensions": [{"dimension": key, "score": value} for key, value in weakest],
            "distribution": {
                "entries": len(entry_scores),
                "min": score_min,
                "max": score_max,
                "weak_or_fragile_entries": weak_or_fragile,
                "provenance_recorded_entries": provenance_recorded,
                "mean_uncertainty_penalty": mean_uncertainty,
            },
            "construct_dimensions": [
                "no_substitution",
                "source_grounding",
                "semantic_entailment",
                "provenance_visibility",
                "warrant_quality",
                "limitation_quality",
                "learner_agency",
                "revision_usefulness",
                "response_provenance",
                "revision_movement",
                "source_quality_signal",
                "unknown_transparency",
            ],
            "validation_status": "engineering_metric_unvalidated",
            "calibration_needed": [
                "human rater calibration",
                "LLM judge calibration",
                "inter-rater reliability",
                "construct validity against real academic writing outcomes",
            ],
            "interpretation": (
                "Higher scores mean Sophia preserved human authorship while making evidence, warrant, limitation, "
                "learner-owned next action, provenance, and uncertainty visible. This is an audit signal, "
                "not a certificate of originality or a validated educational measurement instrument."
            ),
        }

    @staticmethod
    def _pedagogical_event_from_intervention(intervention: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an intervention into auditable pedagogy telemetry."""
        plan = intervention.get("pedagogical_plan") or {}
        findings = [str(item) for item in (intervention.get("findings") or [])]
        learner_need = (
            plan.get("pedagogical_need_state")
            or plan.get("need_state")
            or ("source_support_gap" if any("SOURCE" in item.upper() for item in findings) else "")
            or ("limitation_gap" if any("LIMIT" in item.upper() for item in findings) else "")
            or ("revision_scaffold" if intervention.get("next_revision_move") else "not_recorded")
        )
        selected_office = (
            plan.get("selected_office")
            or intervention.get("office")
            or "not_recorded"
        )
        assessment_layer = (
            plan.get("assessment_layer")
            or ((plan.get("assessment_cycle") or {}).get("active_layer") if isinstance(plan.get("assessment_cycle"), dict) else "")
            or "not_recorded"
        )
        scaffold_type = (
            plan.get("scaffold_type")
            or plan.get("feedback_style")
            or plan.get("response_contract")
            or ("revision_move" if intervention.get("next_revision_move") else "not_recorded")
        )
        complexity_level = (
            plan.get("zpd_level")
            or plan.get("desired_depth")
            or plan.get("bloom_target")
            or "not_recorded"
        )
        next_action = (
            intervention.get("next_revision_move")
            or plan.get("next_best_learning_move")
            or "not_recorded"
        )
        similarity_summary = (
            (intervention.get("similarity_report") or {}).get("summary")
            if isinstance(intervention.get("similarity_report"), dict)
            else {}
        ) or {}
        outcome_signals = {
            "finding_count": len(findings),
            "has_next_action": next_action != "not_recorded",
            "has_authorship_boundary": bool(intervention.get("authorship_boundary") or plan.get("authorship_boundary")),
            "similarity_risk_level": similarity_summary.get("risk_level") or "",
            "repair_options": list(intervention.get("repair_without_rewriting") or [])[:8],
        }
        if outcome_signals["finding_count"] == 0 and outcome_signals["has_next_action"]:
            outcome_state = "scaffold_without_issue_labels"
        elif outcome_signals["finding_count"] > 0 and outcome_signals["has_next_action"]:
            outcome_state = "diagnosis_with_scaffold"
        elif outcome_signals["finding_count"] > 0:
            outcome_state = "diagnosis_without_next_action"
        else:
            outcome_state = "thin_or_unclassified"
        material = "|".join(
            str(value or "")[:400]
            for value in (
                intervention.get("intervention_id"),
                learner_need,
                selected_office,
                assessment_layer,
                next_action,
            )
        )
        return {
            "event_id": f"pedagogy-{_sha256_text(material, 18)}",
            "schema_version": "sophia.pedagogical_event.v1",
            "intervention_id": intervention.get("intervention_id") or "",
            "created_at": intervention.get("created_at") or "",
            "task": intervention.get("task") or "",
            "task_label": intervention.get("task_label") or "",
            "learner_need": learner_need,
            "selected_office": selected_office,
            "assessment_layer": assessment_layer,
            "scaffold_type": scaffold_type,
            "complexity_level": complexity_level,
            "bloom_target": plan.get("bloom_target") or "",
            "zpd_level": plan.get("zpd_level") or "",
            "scaffold_intensity": plan.get("scaffold_intensity") or "",
            "next_action": next_action,
            "outcome_state": outcome_state,
            "outcome_signals": outcome_signals,
            "authorship_boundary": intervention.get("authorship_boundary") or plan.get("authorship_boundary") or "",
            "telemetry_basis": ["intervention_ledger", "pedagogical_plan" if plan else "intervention_fields"],
        }

    def _build_pedagogical_event_ledger(self, interventions: List[Dict[str, Any]]) -> Dict[str, Any]:
        events = [self._pedagogical_event_from_intervention(item) for item in interventions[-200:]]
        office_counts: Dict[str, int] = {}
        layer_counts: Dict[str, int] = {}
        need_counts: Dict[str, int] = {}
        outcome_counts: Dict[str, int] = {}
        scaffold_counts: Dict[str, int] = {}
        for event in events:
            office_counts[event["selected_office"]] = office_counts.get(event["selected_office"], 0) + 1
            layer_counts[event["assessment_layer"]] = layer_counts.get(event["assessment_layer"], 0) + 1
            need_counts[event["learner_need"]] = need_counts.get(event["learner_need"], 0) + 1
            outcome_counts[event["outcome_state"]] = outcome_counts.get(event["outcome_state"], 0) + 1
            scaffold_counts[event["scaffold_type"]] = scaffold_counts.get(event["scaffold_type"], 0) + 1
        handback_rate = (
            round(sum(1 for event in events if event["outcome_signals"].get("has_next_action")) / len(events), 3)
            if events else None
        )
        authorship_boundary_rate = (
            round(sum(1 for event in events if event["outcome_signals"].get("has_authorship_boundary")) / len(events), 3)
            if events else None
        )
        return {
            "schema_version": "sophia.pedagogical_event_ledger.v1",
            "event_count": len(events),
            "events": events,
            "summary": {
                "office_counts": office_counts,
                "assessment_layer_counts": layer_counts,
                "learner_need_counts": need_counts,
                "scaffold_type_counts": scaffold_counts,
                "outcome_counts": outcome_counts,
                "handback_rate": handback_rate,
                "authorship_boundary_rate": authorship_boundary_rate,
            },
            "interpretation": (
                "This ledger shows how Sophia translated a writing/integrity intervention into pedagogical action. "
                "It is runtime telemetry, not evidence of learning gain until paired with human/longitudinal validation."
            ),
        }

    def load_project(self, project_id: str) -> Dict[str, Any]:
        return self._load_project(project_id)

    def export_integrity_record(
        self,
        *,
        project_id: str,
        include_excerpts: bool = True,
        reviewer_mode: str = "integrity_auditor",
    ) -> Dict[str, Any]:
        """Build a read-only academic integrity record for review/audit."""
        project = self._load_project(project_id)
        dashboard = self.summarize_project(project_id)
        draft_versions = list(project.get("draft_versions") or [])
        claims = [record for record in project.get("claim_ledger", []) if isinstance(record, dict)]
        interventions = [record for record in project.get("intervention_ledger", []) if isinstance(record, dict)]
        source_pool = [record for record in project.get("source_pool", []) if isinstance(record, dict)]
        retrieved_sources = [record for record in project.get("retrieved_sources", []) if isinstance(record, dict)]
        final_decisions = [record for record in project.get("final_decision_ledger", []) if isinstance(record, dict)]
        speculum_ledger = self._build_speculum_ledger(
            claims=claims,
            interventions=interventions,
            source_pool=source_pool + retrieved_sources,
            final_decisions=final_decisions,
            include_excerpts=include_excerpts,
        )
        authorship_index = self._build_authorship_preservation_index(speculum_ledger)
        pedagogical_event_ledger = self._build_pedagogical_event_ledger(interventions)

        status_counts: Dict[str, int] = {}
        support_counts: Dict[str, int] = {}
        page_status_counts: Dict[str, int] = {}
        for claim in claims:
            status = str(claim.get("status") or "open")
            support = str(claim.get("support_label") or "unknown")
            page_status = str(claim.get("page_status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            support_counts[support] = support_counts.get(support, 0) + 1
            page_status_counts[page_status] = page_status_counts.get(page_status, 0) + 1

        unresolved = [
            {
                "record_id": claim.get("record_id") or "",
                "status": claim.get("status") or "open",
                "support_label": claim.get("support_label") or "unknown",
                "line_start": claim.get("line_start"),
                "line_end": claim.get("line_end"),
                "claim_hash": _sha256_text(str(claim.get("claim") or ""), 24),
                "claim_excerpt": str(claim.get("claim") or "")[:500] if include_excerpts else "",
                "source_name": claim.get("source_name") or "",
                "page_locator": claim.get("page_locator") or "",
                "limitation": claim.get("limitation") or "",
            }
            for claim in claims
            if str(claim.get("status") or "") in {"needs-source", "unsupported", "contradicted", "warrant-needed", "partial", "limitation-needed", "open"}
        ][:80]

        claim_exports = []
        for claim in claims[:200]:
            claim_exports.append({
                "record_id": claim.get("record_id") or "",
                "line_start": claim.get("line_start"),
                "line_end": claim.get("line_end"),
                "claim_hash": _sha256_text(str(claim.get("claim") or ""), 24),
                "claim_excerpt": str(claim.get("claim") or "")[:700] if include_excerpts else "",
                "source_name": claim.get("source_name") or "",
                "support_label": claim.get("support_label") or "",
                "status": claim.get("status") or "",
                "page_status": claim.get("page_status") or "",
                "page_locator": claim.get("page_locator") or "",
                "doi": claim.get("doi") or "",
                "url": claim.get("url") or "",
                "exact_span_hash": _sha256_text(str(claim.get("exact_span") or ""), 24),
                "exact_span_excerpt": str(claim.get("exact_span") or "")[:700] if include_excerpts else "",
                "warrant": claim.get("warrant") or "",
                "limitation": claim.get("limitation") or "",
                "entailment_status": claim.get("entailment_status") or "",
                "entailment_score": claim.get("entailment_score"),
            })

        intervention_exports = []
        for intervention in interventions[-80:]:
            similarity = intervention.get("similarity_report") or {}
            similarity_summary = similarity.get("summary") if isinstance(similarity, dict) else {}
            intervention_exports.append({
                "intervention_id": intervention.get("intervention_id") or "",
                "created_at": intervention.get("created_at") or "",
                "task": intervention.get("task") or "",
                "task_label": intervention.get("task_label") or "",
                "line_start": intervention.get("line_start"),
                "line_end": intervention.get("line_end"),
                "selected_excerpt_hash": _sha256_text(str(intervention.get("selected_excerpt") or ""), 24),
                "selected_excerpt": str(intervention.get("selected_excerpt") or "")[:700] if include_excerpts else "",
                "pedagogical_move": intervention.get("pedagogical_move") or "",
                "next_revision_move": intervention.get("next_revision_move") or "",
                "authorship_boundary": intervention.get("authorship_boundary") or "",
                "findings": list(intervention.get("findings") or [])[:12],
                "pedagogical_plan": intervention.get("pedagogical_plan") or {},
                "similarity_report_hash": _sha256_json(similarity, 24) if similarity else "",
                "similarity_summary": similarity_summary or {},
                "repair_without_rewriting": intervention.get("repair_without_rewriting") or [],
            })

        final_decision_exports = []
        for decision in final_decisions[-120:]:
            final_decision_exports.append({
                "decision_id": decision.get("decision_id") or "",
                "created_at": decision.get("created_at") or "",
                "claim_record_id": decision.get("claim_record_id") or "",
                "decision": decision.get("decision") or "",
                "rationale": decision.get("rationale") or "",
                "final_text_hash": decision.get("final_text_hash") or "",
                "authorship_assertion": decision.get("authorship_assertion") or "human_final_decision",
            })

        record = {
            "schema_version": "sophia.integrity_record.v1",
            "generated_at": _now(),
            "project_id": project_id,
            "reviewer_mode": reviewer_mode,
            "include_excerpts": include_excerpts,
            "dashboard": dashboard,
            "integrity_contract": {
                "authorship_boundary": "Sophia provides diagnosis, scaffolding, source mapping, and audit records; the human author decides final wording, claims, citations, and submission.",
                "provenance_boundary": "No source is treated as proof unless a visible span and support label are recorded.",
                "page_boundary": "Page numbers and locators are reported only when visible in source metadata or extracted spans.",
                "review_boundary": "This record supports audit and supervision; it does not certify truth, originality, or institutional compliance by itself.",
            },
            "hashes": {
                "project_hash": _sha256_json(project),
                "draft_versions_hash": _sha256_json(draft_versions),
                "claim_ledger_hash": _sha256_json(claims),
                "intervention_ledger_hash": _sha256_json(interventions),
                "source_pool_hash": _sha256_json(source_pool),
                "retrieved_sources_hash": _sha256_json(retrieved_sources),
                "final_decision_ledger_hash": _sha256_json(final_decisions),
                "speculum_ledger_hash": _sha256_json(speculum_ledger),
                "authorship_preservation_index_hash": _sha256_json(authorship_index),
                "pedagogical_event_ledger_hash": _sha256_json(pedagogical_event_ledger),
            },
            "counts": {
                "draft_versions": len(draft_versions),
                "uploaded_documents": len(project.get("uploaded_documents") or []),
                "source_pool_records": len(source_pool),
                "retrieved_sources": len(retrieved_sources),
                "claim_records": len(claims),
                "intervention_records": len(interventions),
                "final_decisions": len(final_decisions),
                "speculum_entries": len(speculum_ledger),
                "authorship_index_entries": len(authorship_index.get("entry_scores") or []),
                "pedagogical_events": pedagogical_event_ledger.get("event_count") or 0,
            },
            "status_counts": status_counts,
            "support_counts": support_counts,
            "page_status_counts": page_status_counts,
            "unresolved_issues": unresolved,
            "speculum_ledger": speculum_ledger,
            "authorship_preservation_index": authorship_index,
            "pedagogical_event_ledger": pedagogical_event_ledger,
            "claim_records": claim_exports,
            "interventions": intervention_exports,
            "final_decisions": final_decision_exports,
            "source_pool_manifest": source_pool[:200],
            "retrieved_source_manifest": retrieved_sources[:200],
        }
        record["integrity_record_hash"] = _sha256_json(record)
        record["markdown"] = self._render_integrity_record_markdown(record)
        return record

    def export_blinded_evaluator_packet(
        self,
        *,
        project_id: str,
        packet_id: str = "",
        include_answer_key: bool = True,
    ) -> Dict[str, Any]:
        """Create a blinded review packet from the integrity record."""
        integrity = self.export_integrity_record(
            project_id=project_id,
            include_excerpts=True,
            reviewer_mode="blinded_evaluator",
        )
        packet_id = packet_id or f"blind-{_sha256_text(project_id + '|' + integrity.get('integrity_record_hash', ''), 16)}"
        items = []
        answer_key = []
        for index, claim in enumerate(integrity.get("claim_records") or [], start=1):
            item_id = f"{packet_id}-item-{index:03d}"
            items.append({
                "item_id": item_id,
                "claim_excerpt": claim.get("claim_excerpt") or "",
                "source_span_excerpt": claim.get("exact_span_excerpt") or "",
                "page_locator": claim.get("page_locator") or "",
                "rating_dimensions": [
                    "source_support",
                    "authorship_preservation",
                    "warrant_quality",
                    "limitation_quality",
                    "risk_of_substitution",
                ],
                "rating_scale": "1=poor/unsafe, 2=weak, 3=adequate, 4=strong, 5=excellent",
                "blinding_note": "Project identity, author identity, and Sophia's internal labels are withheld from evaluator item text.",
            })
            answer_key.append({
                "item_id": item_id,
                "record_id": claim.get("record_id") or "",
                "support_label": claim.get("support_label") or "",
                "status": claim.get("status") or "",
                "claim_hash": claim.get("claim_hash") or "",
                "exact_span_hash": claim.get("exact_span_hash") or "",
            })
        packet = {
            "schema_version": "sophia.blinded_evaluator_packet.v1",
            "packet_id": packet_id,
            "generated_at": _now(),
            "integrity_record_hash": integrity.get("integrity_record_hash") or "",
            "instructions": [
                "Rate only the visible claim and source-span evidence.",
                "Do not infer missing citations, page numbers, or author intent.",
                "Mark not enough information when the visible evidence does not support a rating.",
                "Use the same scale for every item so inter-rater reliability can be computed.",
            ],
            "rater_form_columns": [
                "item_id",
                "source_support_1_5",
                "authorship_preservation_1_5",
                "warrant_quality_1_5",
                "limitation_quality_1_5",
                "risk_of_substitution_1_5",
                "notes",
            ],
            "items": items,
            "answer_key": answer_key if include_answer_key else [],
        }
        packet["packet_hash"] = _sha256_json(packet)
        return packet

    def export_anonymized_research_dataset(self, *, project_id: str) -> Dict[str, Any]:
        """Export research-safe aggregate data without learner/source excerpts."""
        integrity = self.export_integrity_record(project_id=project_id, include_excerpts=False, reviewer_mode="research_export")
        packet = self.export_blinded_evaluator_packet(project_id=project_id, include_answer_key=False)
        rows = []
        for claim in integrity.get("claim_records") or []:
            rows.append({
                "project_hash": _sha256_text(project_id, 24),
                "record_id_hash": _sha256_text(str(claim.get("record_id") or ""), 24),
                "line_start": claim.get("line_start"),
                "line_end": claim.get("line_end"),
                "support_label": claim.get("support_label") or "",
                "status": claim.get("status") or "",
                "page_status": claim.get("page_status") or "",
                "entailment_status": claim.get("entailment_status") or "",
                "entailment_score": claim.get("entailment_score"),
                "has_doi": bool(claim.get("doi")),
                "has_url": bool(claim.get("url")),
                "has_page_locator": bool(claim.get("page_locator")),
                "has_exact_span": bool(claim.get("exact_span_hash")),
                "claim_hash": claim.get("claim_hash") or "",
                "exact_span_hash": claim.get("exact_span_hash") or "",
            })
        dataset = {
            "schema_version": "sophia.anonymized_research_export.v1",
            "generated_at": _now(),
            "project_hash": _sha256_text(project_id, 24),
            "integrity_record_hash": integrity.get("integrity_record_hash") or "",
            "packet_hash": packet.get("packet_hash") or "",
            "counts": integrity.get("counts") or {},
            "status_counts": integrity.get("status_counts") or {},
            "support_counts": integrity.get("support_counts") or {},
            "page_status_counts": integrity.get("page_status_counts") or {},
            "rater_form_columns": packet.get("rater_form_columns") or [],
            "rows": rows,
            "privacy_contract": [
                "No claim/source excerpts are included.",
                "Project and record identifiers are hashed.",
                "The dataset supports aggregate evaluation, not learner identification.",
            ],
        }
        dataset["dataset_hash"] = _sha256_json(dataset)
        return dataset

    def export_reviewer_dashboard(
        self,
        *,
        project_id: str,
        include_answer_key: bool = False,
    ) -> Dict[str, Any]:
        """Export a self-contained read-only reviewer dashboard."""
        integrity = self.export_integrity_record(project_id=project_id, include_excerpts=True, reviewer_mode="reviewer_dashboard")
        packet = self.export_blinded_evaluator_packet(project_id=project_id, include_answer_key=include_answer_key)
        research = self.export_anonymized_research_dataset(project_id=project_id)
        html_doc = self._render_reviewer_dashboard_html(integrity=integrity, packet=packet, research=research)
        dashboard = {
            "schema_version": "sophia.reviewer_dashboard.v1",
            "generated_at": _now(),
            "project_id": project_id,
            "integrity_record_hash": integrity.get("integrity_record_hash") or "",
            "packet_hash": packet.get("packet_hash") or "",
            "research_dataset_hash": research.get("dataset_hash") or "",
            "html": html_doc,
            "integrity_record": integrity,
            "evaluator_packet": packet,
            "anonymized_research_export": research,
        }
        dashboard["dashboard_hash"] = _sha256_json({
            "schema_version": dashboard["schema_version"],
            "generated_at": dashboard["generated_at"],
            "project_id": project_id,
            "integrity_record_hash": dashboard["integrity_record_hash"],
            "packet_hash": dashboard["packet_hash"],
            "research_dataset_hash": dashboard["research_dataset_hash"],
            "html_hash": _sha256_text(html_doc, 64),
        })
        return dashboard

    @staticmethod
    def _render_reviewer_dashboard_html(*, integrity: Dict[str, Any], packet: Dict[str, Any], research: Dict[str, Any]) -> str:
        counts = integrity.get("counts") or {}
        unresolved = integrity.get("unresolved_issues") or []
        claims = integrity.get("claim_records") or []
        interventions = integrity.get("interventions") or []

        def esc(value: Any) -> str:
            return html.escape(str(value or ""), quote=True)

        def metric(label: str, value: Any) -> str:
            return f"<div class='metric'><span>{esc(label)}</span><strong>{esc(value)}</strong></div>"

        claim_rows = "\n".join(
            "<tr>"
            f"<td>{esc(row.get('status'))}</td>"
            f"<td>{esc(row.get('support_label'))}</td>"
            f"<td>{esc(row.get('page_locator') or row.get('page_status'))}</td>"
            f"<td>{esc(row.get('claim_excerpt'))}</td>"
            f"<td>{esc(row.get('exact_span_excerpt'))}</td>"
            "</tr>"
            for row in claims[:80]
        )
        unresolved_items = "\n".join(
            f"<li><strong>{esc(item.get('status'))}</strong>: {esc(item.get('claim_excerpt'))}</li>"
            for item in unresolved[:40]
        ) or "<li>No unresolved issues recorded.</li>"
        intervention_items = "\n".join(
            f"<li><strong>{esc(item.get('task_label') or item.get('task'))}</strong>: {esc(item.get('pedagogical_move'))}<br><small>{esc(item.get('next_revision_move'))}</small></li>"
            for item in interventions[-20:]
        ) or "<li>No interventions recorded.</li>"
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sophia Reviewer Dashboard</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; margin: 0; background: #f6f1e8; color: #201a14; }}
    header {{ padding: 32px; background: #18241f; color: #f8f2e8; }}
    main {{ padding: 28px; max-width: 1180px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }}
    .metric, section {{ background: #fffaf0; border: 1px solid #dacdb8; border-radius: 16px; padding: 16px; box-shadow: 0 8px 24px rgba(37, 28, 18, .08); }}
    .metric span {{ display: block; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #75634f; }}
    .metric strong {{ font-size: 28px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e4d8c8; padding: 10px; vertical-align: top; text-align: left; }}
    th {{ background: #efe3d0; }}
    code {{ background: #efe3d0; padding: 2px 5px; border-radius: 5px; }}
  </style>
</head>
<body>
  <header>
    <h1>Sophia Reviewer Dashboard</h1>
    <p>Read-only academic integrity review package. Hash: <code>{esc(integrity.get('integrity_record_hash'))}</code></p>
  </header>
  <main>
    <div class="grid">
      {metric('Claims', counts.get('claim_records', 0))}
      {metric('Interventions', counts.get('intervention_records', 0))}
      {metric('Sources', counts.get('source_pool_records', 0))}
      {metric('Final Decisions', counts.get('final_decisions', 0))}
      {metric('Evaluator Items', len(packet.get('items') or []))}
      {metric('Research Rows', len(research.get('rows') or []))}
    </div>
    <section>
      <h2>Integrity Contract</h2>
      <ul>{''.join(f'<li>{esc(k)}: {esc(v)}</li>' for k, v in (integrity.get('integrity_contract') or {{}}).items())}</ul>
    </section>
    <section>
      <h2>Unresolved Issues</h2>
      <ul>{unresolved_items}</ul>
    </section>
    <section>
      <h2>Recent Interventions</h2>
      <ul>{intervention_items}</ul>
    </section>
    <section>
      <h2>Claim Evidence Table</h2>
      <table>
        <thead><tr><th>Status</th><th>Support</th><th>Page</th><th>Claim</th><th>Visible Source Span</th></tr></thead>
        <tbody>{claim_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Hashes</h2>
      <p>Packet hash: <code>{esc(packet.get('packet_hash'))}</code></p>
      <p>Research dataset hash: <code>{esc(research.get('dataset_hash'))}</code></p>
    </section>
  </main>
</body>
</html>"""

    @staticmethod
    def _render_integrity_record_markdown(record: Dict[str, Any]) -> str:
        lines = [
            "# Sophia Integrity Record",
            "",
            f"Generated: {record.get('generated_at')}",
            f"Project ID: `{record.get('project_id')}`",
            f"Integrity record hash: `{record.get('integrity_record_hash')}`",
            f"Reviewer mode: `{record.get('reviewer_mode')}`",
            "",
            "## Integrity Contract",
            "",
        ]
        for key, value in (record.get("integrity_contract") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Counts", ""])
        for key, value in (record.get("counts") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Status Counts", ""])
        for key, value in sorted((record.get("status_counts") or {}).items()):
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Support Counts", ""])
        for key, value in sorted((record.get("support_counts") or {}).items()):
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Hash Chain", ""])
        for key, value in (record.get("hashes") or {}).items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Final User Decisions", ""])
        decisions = record.get("final_decisions") or []
        if not decisions:
            lines.append("No final user decisions have been recorded yet.")
        for item in decisions:
            lines.append(f"- `{item.get('decision_id')}`: {item.get('decision')} | rationale: {item.get('rationale')}")
        index = record.get("authorship_preservation_index") or {}
        lines.extend(["", "## Authorship Preservation Index", ""])
        lines.append(f"- Score: {index.get('score')}")
        lines.append(f"- Raw weighted score: {index.get('raw_weighted_score')}")
        lines.append(f"- Lower-bound score: {index.get('lower_bound_score')}")
        lines.append(f"- Band: {index.get('band')}")
        lines.append(f"- Maturity: {index.get('maturity')}")
        lines.append(f"- Validation status: {index.get('validation_status')}")
        if index.get("interpretation"):
            lines.append(f"- Interpretation: {index.get('interpretation')}")
        if index.get("distribution"):
            lines.append(f"- Distribution: {index.get('distribution')}")
        if index.get("category_subscores"):
            lines.append(f"- Category subscores: {index.get('category_subscores')}")
        if index.get("provider_contribution"):
            lines.append(f"- Provider contribution: {index.get('provider_contribution')}")
        if index.get("calibration_needed"):
            lines.append("- Calibration needed:")
            for item in index.get("calibration_needed") or []:
                lines.append(f"  - {item}")
        if index.get("dimension_means"):
            lines.append("- Dimension means:")
            for key, value in (index.get("dimension_means") or {}).items():
                lines.append(f"  - {key}: {value}")
        if index.get("weakest_dimensions"):
            lines.append("- Weakest dimensions:")
            for item in index.get("weakest_dimensions") or []:
                lines.append(f"  - {item.get('dimension')}: {item.get('score')}")
        if index.get("entry_scores"):
            lines.append("- Entry scores:")
            for item in (index.get("entry_scores") or [])[:40]:
                lines.append(
                    f"  - `{item.get('claim_record_id')}`: {item.get('score')} ({item.get('band')})"
                )
        pedagogy = record.get("pedagogical_event_ledger") or {}
        lines.extend(["", "## Pedagogical Event Telemetry", ""])
        lines.append(f"- Schema: {pedagogy.get('schema_version')}")
        lines.append(f"- Event count: {pedagogy.get('event_count')}")
        if pedagogy.get("interpretation"):
            lines.append(f"- Interpretation: {pedagogy.get('interpretation')}")
        if pedagogy.get("summary"):
            lines.append(f"- Summary: {pedagogy.get('summary')}")
        for event in (pedagogy.get("events") or [])[:40]:
            lines.append(f"### {event.get('event_id') or event.get('intervention_id') or 'pedagogy-event'}")
            lines.append(f"- Intervention: `{event.get('intervention_id')}`")
            lines.append(f"- Learner need: {event.get('learner_need')}")
            lines.append(f"- Selected office: {event.get('selected_office')}")
            lines.append(f"- Assessment layer: {event.get('assessment_layer')}")
            lines.append(f"- Scaffold type: {event.get('scaffold_type')}")
            lines.append(f"- Complexity level: {event.get('complexity_level')}")
            lines.append(f"- Outcome state: {event.get('outcome_state')}")
            lines.append(f"- Next action: {event.get('next_action')}")
            lines.append(f"- Outcome signals: {event.get('outcome_signals')}")
            lines.append("")
        lines.extend(["", "## Speculum Ledger", ""])
        speculum = record.get("speculum_ledger") or []
        if not speculum:
            lines.append("No Speculum mirror entries were available.")
        for item in speculum[:80]:
            lines.append(f"### {item.get('speculum_id') or item.get('claim_record_id') or 'speculum-entry'}")
            lines.append(f"- Claim record: `{item.get('claim_record_id')}`")
            lines.append(f"- Mirror basis: {', '.join(str(x) for x in item.get('mirror_basis') or [])}")
            lines.append(f"- Lines: {item.get('line_start')}-{item.get('line_end')}")
            claim_type = item.get("claim_type_analysis") or {}
            if claim_type:
                lines.append(f"- Claim type/evidence standard: {claim_type}")
            lines.append(f"- Support/status: {item.get('support_label')} / {item.get('status')}")
            lines.append(f"- Support confidence: {item.get('support_confidence')}")
            source_quality = item.get("source_quality") or {}
            if source_quality:
                lines.append(f"- Source quality snapshot: {source_quality}")
            nli_support = item.get("nli_support") or {}
            if nli_support:
                lines.append(f"- NLI/semantic support: {nli_support}")
            if item.get("table_claim_verification"):
                lines.append(f"- Table claim verification: {item.get('table_claim_verification')}")
            if item.get("evidence_transition"):
                lines.append(f"- Evidence transition: {item.get('evidence_transition')}")
            if item.get("claim_lineage"):
                lines.append(f"- Claim lineage: {item.get('claim_lineage')}")
            if item.get("claim"):
                lines.append(f"- Claim: {item.get('claim')}")
            if item.get("evidence_source"):
                lines.append(f"- Evidence source: {item.get('evidence_source')}")
            if item.get("evidence_span"):
                lines.append(f"- Evidence span: {item.get('evidence_span')}")
            if item.get("warrant"):
                lines.append(f"- Warrant: {item.get('warrant')}")
            if item.get("limitation"):
                lines.append(f"- Limitation: {item.get('limitation')}")
            if item.get("unresolved_risks"):
                lines.append(f"- Unresolved risks: {', '.join(str(x) for x in item.get('unresolved_risks') or [])}")
            if item.get("unknowns"):
                lines.append(f"- Unknowns: {'; '.join(str(x) for x in item.get('unknowns') or [])}")
            provenance = item.get("response_provenance") or {}
            if provenance:
                lines.append(f"- Response provenance: {provenance}")
            movement = item.get("revision_movement") or {}
            if movement:
                lines.append(f"- Revision movement: {movement.get('status')} | {movement.get('interpretation')}")
            lines.append(f"- Authorship boundary: {item.get('authorship_boundary')}")
            lines.append(f"- Learner next action: {item.get('learner_next_action')}")
            if item.get("final_user_decisions"):
                lines.append(f"- Final user decisions: {item.get('final_user_decisions')}")
            lines.append("")
        lines.extend(["", "## Unresolved Issues", ""])
        unresolved = record.get("unresolved_issues") or []
        if not unresolved:
            lines.append("No unresolved claim-ledger issues were recorded.")
        for item in unresolved:
            lines.append(f"### {item.get('record_id') or 'unresolved'}")
            lines.append(f"- Status: {item.get('status')}")
            lines.append(f"- Support label: {item.get('support_label')}")
            lines.append(f"- Lines: {item.get('line_start')}-{item.get('line_end')}")
            lines.append(f"- Claim hash: `{item.get('claim_hash')}`")
            if item.get("claim_excerpt"):
                lines.append(f"- Claim excerpt: {item.get('claim_excerpt')}")
            if item.get("source_name"):
                lines.append(f"- Source: {item.get('source_name')}")
            if item.get("page_locator"):
                lines.append(f"- Page locator: {item.get('page_locator')}")
            if item.get("limitation"):
                lines.append(f"- Limitation: {item.get('limitation')}")
            lines.append("")
        lines.extend(["## Recent Interventions", ""])
        interventions = record.get("interventions") or []
        if not interventions:
            lines.append("No intervention records were available.")
        for item in interventions[-20:]:
            lines.append(f"### {item.get('task_label') or item.get('task') or 'Writing Desk intervention'}")
            lines.append(f"- Created: {item.get('created_at')}")
            lines.append(f"- Intervention ID: `{item.get('intervention_id')}`")
            lines.append(f"- Lines: {item.get('line_start')}-{item.get('line_end')}")
            lines.append(f"- Pedagogical move: {item.get('pedagogical_move')}")
            lines.append(f"- Next revision move: {item.get('next_revision_move')}")
            if item.get("similarity_summary"):
                lines.append(f"- Similarity summary: {item.get('similarity_summary')}")
            if item.get("repair_without_rewriting"):
                lines.append(f"- Repair options: {', '.join(str(x) for x in item.get('repair_without_rewriting') or [])}")
            if item.get("authorship_boundary"):
                lines.append(f"- Authorship boundary: {item.get('authorship_boundary')}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def contamination_report(self, project_ids: Iterable[str]) -> Dict[str, Any]:
        ids = [str(project_id) for project_id in project_ids if str(project_id or "").strip()]
        projects = [self._load_project(project_id) for project_id in ids]
        document_sets = []
        source_sets = []
        claim_sets = []
        for project in projects:
            document_sets.append({
                str(doc.get("document_hash") or "")
                for doc in project.get("uploaded_documents", [])
                if isinstance(doc, dict) and str(doc.get("document_hash") or "")
            })
            source_sets.append({
                (str(src.get("name") or ""), str(src.get("text_hash") or ""))
                for src in project.get("source_pool", [])
                if isinstance(src, dict)
            })
            claim_sets.append({
                str(record.get("record_id") or "")
                for record in project.get("claim_ledger", [])
                if isinstance(record, dict) and str(record.get("record_id") or "")
            })

        pairwise = []
        contamination_signals = 0
        for i, left_id in enumerate(ids):
            for j, right_id in enumerate(ids):
                if j <= i:
                    continue
                shared_documents = sorted(document_sets[i] & document_sets[j])
                shared_sources = sorted(f"{name}|{text_hash}" for name, text_hash in (source_sets[i] & source_sets[j]))
                shared_claim_records = sorted(claim_sets[i] & claim_sets[j])
                if shared_documents or shared_claim_records:
                    contamination_signals += 1
                pairwise.append({
                    "left_project_id": left_id,
                    "right_project_id": right_id,
                    "shared_document_hashes": shared_documents,
                    "shared_source_records": shared_sources,
                    "shared_claim_record_ids": shared_claim_records,
                })
        return {
            "schema_version": SCHEMA_VERSION,
            "project_count": len(ids),
            "pair_count": len(pairwise),
            "contamination_signals": contamination_signals,
            "pairwise": pairwise,
            "passed": contamination_signals == 0,
        }


_STORE: Optional[SophiaProjectStore] = None


def get_sophia_project_store(evidence_dir: Path) -> SophiaProjectStore:
    global _STORE
    root = Path(evidence_dir) / "sophia_project_store"
    if _STORE is None or _STORE.root != root:
        _STORE = SophiaProjectStore(root)
    return _STORE
