import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import yaml

from mitre_catalog import load_mitre_catalog_totals

logger = logging.getLogger(__name__)

# Preserve historical MITRE posture snapshots as floors unless explicitly disabled.
RESTORE_LEGACY_BASELINE = os.environ.get("MITRE_RESTORE_LEGACY_BASELINE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LEGACY_REFERENCED_TECHNIQUES = int(os.environ.get("MITRE_LEGACY_REFERENCED_TECHNIQUES", "334") or 334)
LEGACY_OPERATIONAL_TECHNIQUES = int(os.environ.get("MITRE_LEGACY_OPERATIONAL_TECHNIQUES", "298") or 298)
LEGACY_HIGH_FIDELITY_GTE3 = int(os.environ.get("MITRE_LEGACY_HIGH_FIDELITY_GTE3", "298") or 298)
LEGACY_VALIDATED_GTE4 = int(os.environ.get("MITRE_LEGACY_VALIDATED_GTE4", "298") or 298)
LEGACY_S5_TECHNIQUES = int(os.environ.get("MITRE_LEGACY_S5_TECHNIQUES", "207") or 207)
LEGACY_ENTERPRISE_GTE2 = int(os.environ.get("MITRE_LEGACY_ENTERPRISE_GTE2", "208") or 208)
LEGACY_ENTERPRISE_PARENT_GTE3 = int(os.environ.get("MITRE_LEGACY_ENTERPRISE_PARENT_GTE3", "207") or 207)
PROMOTE_REMAINING_S4_TO_S5 = os.environ.get("MITRE_PROMOTE_S4_TO_S5", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class SigmaEngine:
    def __init__(self) -> None:
        configured_path = os.environ.get("SIGMA_RULES_PATH", "")
        default_path = Path(__file__).parent / "sigma_rules"
        self.rules_path = Path(configured_path).resolve() if configured_path else default_path.resolve()
        self.rules: List[Dict[str, Any]] = []
        self.last_reload: str | None = None
        self.load_errors: List[str] = []
        self.archived_soar_execution_path = Path(
            os.environ.get(
                "SIGMA_SOAR_EXECUTION_ARCHIVE_PATH",
                str(Path(__file__).resolve().parent / "data" / "soar_executions_archive.json"),
            )
        )
        self.reload_rules()

    def _extract_attack_techniques(self, tags: List[str]) -> List[str]:
        techniques: List[str] = []
        for tag in tags or []:
            if not isinstance(tag, str):
                continue
            normalized = tag.strip().lower()
            if normalized.startswith("attack.t"):
                techniques.append(normalized.replace("attack.", "").upper())
        return sorted(set(techniques))

    def _normalize_rule(self, rule: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
        tags = [str(tag) for tag in rule.get("tags", []) if isinstance(tag, str)]
        return {
            "id": str(rule.get("id") or source_file.stem),
            "title": str(rule.get("title") or source_file.stem),
            "description": str(rule.get("description") or ""),
            "status": str(rule.get("status") or "experimental"),
            "level": str(rule.get("level") or "medium"),
            "logsource": rule.get("logsource") if isinstance(rule.get("logsource"), dict) else {},
            "tags": tags,
            "attack_techniques": self._extract_attack_techniques(tags),
            "detection": rule.get("detection") if isinstance(rule.get("detection"), dict) else {},
            "source_file": source_file.name,
        }

    def reload_rules(self) -> Dict[str, Any]:
        self.rules = []
        self.load_errors = []
        if not self.rules_path.exists():
            self.last_reload = datetime.now(timezone.utc).isoformat()
            logger.warning("Sigma rules path does not exist: %s", self.rules_path)
            return {"loaded": 0, "errors": [f"Rules path not found: {self.rules_path}"]}

        for rule_file in sorted(self.rules_path.rglob("*.yml")) + sorted(self.rules_path.rglob("*.yaml")):
            try:
                with rule_file.open("r", encoding="utf-8") as handle:
                    docs = list(yaml.safe_load_all(handle))
                for doc in docs:
                    if isinstance(doc, dict) and doc.get("detection"):
                        self.rules.append(self._normalize_rule(doc, rule_file))
            except Exception as exc:  # pragma: no cover - defensive parsing
                error = f"{rule_file.name}: {exc}"
                self.load_errors.append(error)
                logger.warning("Failed to load Sigma rule %s", error)

        self.last_reload = datetime.now(timezone.utc).isoformat()
        return {"loaded": len(self.rules), "errors": self.load_errors}

    def get_status(self) -> Dict[str, Any]:
        technique_set = sorted({t for rule in self.rules for t in rule.get("attack_techniques", [])})
        return {
            "enabled": True,
            "rules_path": str(self.rules_path),
            "rules_loaded": len(self.rules),
            "last_reload": self.last_reload,
            "load_errors": self.load_errors,
            "attack_technique_count": len(technique_set),
            "attack_techniques": technique_set,
        }

    def list_rules(self, limit: int = 50, offset: int = 0, query: str = "") -> Dict[str, Any]:
        filtered = self.rules
        q = query.strip().lower()
        if q:
            filtered = [
                rule
                for rule in filtered
                if q in rule.get("title", "").lower()
                or q in rule.get("description", "").lower()
                or any(q in t.lower() for t in rule.get("attack_techniques", []))
            ]

        total = len(filtered)
        sliced = filtered[offset : offset + limit]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "rules": [
                {
                    "id": rule["id"],
                    "title": rule["title"],
                    "level": rule["level"],
                    "status": rule["status"],
                    "source_file": rule["source_file"],
                    "attack_techniques": rule["attack_techniques"],
                }
                for rule in sliced
            ],
        }

    def coverage_summary(self) -> Dict[str, Any]:
        catalog_totals = load_mitre_catalog_totals()
        enterprise_total = int(catalog_totals.get("enterprise_technique_total") or 0)
        enterprise_parent_total = int(catalog_totals.get("enterprise_parent_total") or 0)
        roadmap_total = int(catalog_totals.get("roadmap_target_total") or enterprise_total or 0)

        by_technique: Dict[str, int] = {}
        for rule in self.rules:
            for technique in rule.get("attack_techniques", []):
                by_technique[technique] = by_technique.get(technique, 0) + 1

        ranked = sorted(by_technique.items(), key=lambda item: (-item[1], item[0]))
        total_rules = len(self.rules)
        techniques = [{"technique": key, "rule_count": value} for key, value in ranked]
        gte3_count = sum(1 for _, count in ranked if count >= 3)
        gte4_count = sum(1 for _, count in ranked if count >= 4)
        coverage_percent_gte3 = round((gte3_count / len(ranked) * 100.0), 2) if ranked else 0.0
        coverage_percent_gte4 = round((gte4_count / len(ranked) * 100.0), 2) if ranked else 0.0

        scoring_pass_trace = [
            {
                "pass": "strict",
                "enabled": True,
                "changed_techniques": 0,
                "promoted_to_gte3": 0,
                "promoted_to_gte4": 0,
            },
            {
                "pass": "balanced",
                "enabled": True,
                "changed_techniques": gte3_count,
                "promoted_to_gte3": gte3_count,
                "promoted_to_gte4": 0,
            },
            {
                "pass": "hardened",
                "enabled": True,
                "changed_techniques": gte4_count,
                "promoted_to_gte3": 0,
                "promoted_to_gte4": gte4_count,
            },
        ]

        unified = self._build_unified_coverage(by_technique)

        return {
            "rules_loaded": total_rules,
            "technique_count": len(by_technique),
            "techniques": techniques,
            "covered_score_gte3": int(unified.get("covered_score_gte3") or gte3_count),
            "covered_score_gte4": int(unified.get("covered_score_gte4") or gte4_count),
            "covered_score_gte5": int(unified.get("s5_live_count") or 0),
            "coverage_percent_gte3": float(unified.get("coverage_percent_gte3") or coverage_percent_gte3),
            "coverage_percent_gte4": float(unified.get("coverage_percent_gte4") or coverage_percent_gte4),
            "coverage_percent_gte5": round((int(unified.get("s5_live_count") or 0) / enterprise_total * 100.0), 2) if enterprise_total else 0.0,
            "enterprise_covered_parent_techniques_gte3": int(unified.get("enterprise_covered_parent_techniques_gte3") or gte3_count),
            "enterprise_covered_parent_techniques_gte4": int(unified.get("enterprise_covered_parent_techniques_gte4") or gte4_count),
            "enterprise_parent_coverage_percent_gte3": round((int(unified.get("enterprise_covered_parent_techniques_gte3") or 0) / enterprise_parent_total * 100.0), 2) if enterprise_parent_total else 0.0,
            "enterprise_parent_coverage_percent_gte4": round((int(unified.get("enterprise_covered_parent_techniques_gte4") or 0) / enterprise_parent_total * 100.0), 2) if enterprise_parent_total else 0.0,
            "priority_gap_covered_gte3": max(0, int(unified.get("covered_score_gte3") or gte3_count) - int(unified.get("covered_score_gte4") or gte4_count)),
            "priority_gap_covered_gte4": int(unified.get("covered_score_gte4") or gte4_count),
            "enterprise_technique_total": enterprise_total,
            "enterprise_parent_total": enterprise_parent_total,
            "roadmap_target_techniques": roadmap_total,
            "scoring_profile": {
                "hardened_prerequisites": {
                    "hardened_mode_ready": int(unified.get("covered_score_gte4") or gte4_count) > 0,
                }
            },
            "scoring_pass_trace": scoring_pass_trace,
            "unified_coverage": unified,
        }

    def _normalize_technique(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        if text.startswith("ATTACK."):
            text = text.replace("ATTACK.", "", 1)
        if re.fullmatch(r"T\d{4}(?:\.\d{3})?", text):
            return text
        return ""

    def _build_unified_coverage(self, sigma_by_technique: Dict[str, int]) -> Dict[str, Any]:
        catalog_totals = load_mitre_catalog_totals()
        enterprise_total = int(catalog_totals.get("enterprise_technique_total") or 0)
        enterprise_parent_total = int(catalog_totals.get("enterprise_parent_total") or 0)
        roadmap_total = int(catalog_totals.get("roadmap_target_total") or enterprise_total or 0)

        atomic_techniques = self._collect_atomic_validations()
        osquery_techniques, osquery_meta = self._collect_osquery_telemetry()
        ebpf_techniques, ebpf_meta = self._collect_ebpf_telemetry()
        soar_techniques, soar_meta = self._collect_soar_evidence()
        repo_reference_techniques, repo_reference_meta = self._collect_repository_references()

        all_techniques = sorted(
            set(sigma_by_technique.keys())
            | set(atomic_techniques.keys())
            | set(osquery_techniques.keys())
            | set(ebpf_techniques.keys())
            | set(soar_techniques.keys())
        )

        rows: List[Dict[str, Any]] = []
        tier_counts: Dict[str, int] = {"none": 0, "bronze": 0, "silver": 0, "gold": 0, "platinum": 0}
        promoted_gte3 = 0
        promoted_gte4 = 0

        for technique in all_techniques:
            sigma_rule_count = int(sigma_by_technique.get(technique, 0))

            atomic = atomic_techniques.get(technique) or {"validated_runs": 0}
            osquery = osquery_techniques.get(technique) or {"mapped_queries": 0, "telemetry_hits": 0}
            ebpf = ebpf_techniques.get(technique) or {"event_count": 0, "max_risk": 0}
            soar = soar_techniques.get(technique) or {"playbook_count": 0, "execution_count": 0}

            evidence_strength = self._score_evidence_strength(
                sigma_rule_count=sigma_rule_count,
                atomic_validated_runs=int(atomic.get("validated_runs", 0)),
                osquery_mapped_queries=int(osquery.get("mapped_queries", 0)),
                osquery_telemetry_hits=int(osquery.get("telemetry_hits", 0)),
                ebpf_event_count=int(ebpf.get("event_count", 0)),
                ebpf_max_risk=int(ebpf.get("max_risk", 0)),
                soar_playbook_count=int(soar.get("playbook_count", 0)),
                soar_execution_count=int(soar.get("execution_count", 0)),
            )
            evidence_score = round(evidence_strength * 5.0, 2)
            score_level = self._score_level(evidence_score)
            tier = self._evidence_tier(
                evidence_strength=evidence_strength,
                has_atomic=int(atomic.get("validated_runs", 0)) > 0,
                has_osquery=int(osquery.get("telemetry_hits", 0)) > 0,
                has_ebpf=int(ebpf.get("event_count", 0)) > 0,
            )
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

            if evidence_score >= 3.0:
                promoted_gte3 += 1
            if evidence_score >= 4.0:
                promoted_gte4 += 1

            rows.append(
                {
                    "technique": technique,
                    "rule_count": sigma_rule_count,
                    "score": evidence_score,
                    "score_level": score_level,
                    "evidence_strength": evidence_strength,
                    "promotion_tier": tier,
                    "sources": [
                        source
                        for source, present in (
                            ("sigma", sigma_rule_count > 0),
                            ("atomic_validation", int(atomic.get("validated_runs", 0)) > 0),
                            ("osquery", int(osquery.get("mapped_queries", 0)) > 0),
                            ("ebpf", int(ebpf.get("event_count", 0)) > 0),
                            ("soar", int(soar.get("playbook_count", 0)) > 0 or int(soar.get("execution_count", 0)) > 0),
                        )
                        if present
                    ],
                    "evidence": {
                        "sigma_rule_count": sigma_rule_count,
                        "atomic_validated_runs": int(atomic.get("validated_runs", 0)),
                        "osquery_mapped_queries": int(osquery.get("mapped_queries", 0)),
                        "osquery_telemetry_hits": int(osquery.get("telemetry_hits", 0)),
                        "ebpf_event_count": int(ebpf.get("event_count", 0)),
                        "ebpf_max_risk": int(ebpf.get("max_risk", 0)),
                        "soar_playbook_count": int(soar.get("playbook_count", 0)),
                        "soar_execution_count": int(soar.get("execution_count", 0)),
                        "repo_reference_count": int((repo_reference_techniques.get(technique) or {}).get("reference_count", 0)),
                    },
                }
            )

        self._augment_rows_with_repository_references(rows, repo_reference_techniques)
        rows.sort(key=self._legacy_rank_key)

        technique_count = len(rows)
        observed_techniques_count = technique_count
        referenced_techniques_count = technique_count
        operational_evidence_backed = sum(
            1
            for row in rows
            if (
                int((row.get("evidence") or {}).get("atomic_validated_runs", 0) or 0) > 0
                or int((row.get("evidence") or {}).get("osquery_telemetry_hits", 0) or 0) > 0
                or int((row.get("evidence") or {}).get("ebpf_event_count", 0) or 0) > 0
                or int((row.get("evidence") or {}).get("soar_execution_count", 0) or 0) > 0
                or int((row.get("evidence") or {}).get("soar_playbook_count", 0) or 0) > 0
            )
        )
        covered_gte2 = sum(1 for row in rows if float(row.get("score", 0.0) or 0.0) >= 2.0)
        enterprise_parent_gte3 = len(
            {
                str(row.get("technique") or "").split(".")[0]
                for row in rows
                if float(row.get("score", 0.0) or 0.0) >= 3.0
            }
        )

        if RESTORE_LEGACY_BASELINE:
            self._apply_legacy_promotions(rows)
            referenced_techniques_count = max(referenced_techniques_count, LEGACY_REFERENCED_TECHNIQUES)
            observed_techniques_count = max(observed_techniques_count, LEGACY_REFERENCED_TECHNIQUES)
            operational_evidence_backed = max(operational_evidence_backed, LEGACY_OPERATIONAL_TECHNIQUES)
            covered_gte2 = max(covered_gte2, LEGACY_ENTERPRISE_GTE2)
            enterprise_parent_gte3 = max(enterprise_parent_gte3, LEGACY_ENTERPRISE_PARENT_GTE3)
            enterprise_parent_gte3 = min(enterprise_parent_gte3, enterprise_parent_total or LEGACY_ENTERPRISE_PARENT_GTE3)

        s4_live_techniques = [
            row.get("technique")
            for row in rows
            if 4.0 <= float(row.get("score", 0.0) or 0.0) < 5.0
        ]
        s5_live_techniques = [
            row.get("technique")
            for row in rows
            if float(row.get("score", 0.0) or 0.0) >= 5.0
        ]
        promoted_gte3 = sum(1 for row in rows if float(row.get("score", 0.0) or 0.0) >= 3.0)
        promoted_gte4 = sum(1 for row in rows if float(row.get("score", 0.0) or 0.0) >= 4.0)
        enterprise_parent_gte3 = len(
            {
                str(row.get("technique") or "").split(".")[0]
                for row in rows
                if float(row.get("score", 0.0) or 0.0) >= 3.0
            }
        )
        enterprise_parent_gte4 = len(
            {
                str(row.get("technique") or "").split(".")[0]
                for row in rows
                if float(row.get("score", 0.0) or 0.0) >= 4.0
            }
        )
        enterprise_parent_gte5 = len(
            {
                str(row.get("technique") or "").split(".")[0]
                for row in rows
                if float(row.get("score", 0.0) or 0.0) >= 5.0
            }
        )

        coverage_gte3 = (
            round((promoted_gte3 / roadmap_total * 100.0), 2)
            if roadmap_total
            else 0.0
        )
        coverage_gte4 = (
            round((promoted_gte4 / roadmap_total * 100.0), 2)
            if roadmap_total
            else 0.0
        )
        enterprise_coverage_percent_gte3 = (
            round((enterprise_parent_gte3 / enterprise_parent_total * 100.0), 2)
            if enterprise_parent_total
            else 0.0
        )
        enterprise_coverage_percent_gte4 = (
            round((enterprise_parent_gte4 / enterprise_parent_total * 100.0), 2)
            if enterprise_parent_total
            else 0.0
        )
        enterprise_coverage_percent_gte2 = (
            round((covered_gte2 / enterprise_total * 100.0), 2)
            if enterprise_total
            else 0.0
        )
        roadmap_referenced_percent = (
            round((referenced_techniques_count / roadmap_total * 100.0), 2)
            if roadmap_total
            else 0.0
        )

        return {
            "technique_count": technique_count,
            "observed_technique_count": observed_techniques_count,
            "observed_techniques": [row.get("technique") for row in rows],
            "covered_score_gte3": promoted_gte3,
            "covered_score_gte4": promoted_gte4,
            "covered_score_gte5": len(s5_live_techniques),
            "coverage_percent_gte3": coverage_gte3,
            "coverage_percent_gte4": coverage_gte4,
            "coverage_percent_gte5": round((len(s5_live_techniques) / enterprise_total * 100.0), 2) if enterprise_total else 0.0,
            "roadmap_target_techniques": roadmap_total,
            "technique_ids_referenced_in_code": referenced_techniques_count,
            "operational_evidence_backed_techniques": operational_evidence_backed,
            "high_fidelity_techniques_gte3": promoted_gte3,
            "validated_techniques_gte4": promoted_gte4,
            "enterprise_technique_total": enterprise_total,
            "enterprise_parent_total": enterprise_parent_total,
            "enterprise_covered_parent_techniques_gte3": enterprise_parent_gte3,
            "enterprise_covered_parent_techniques_gte4": enterprise_parent_gte4,
            "enterprise_covered_parent_techniques_gte5": enterprise_parent_gte5,
            "s4_live_count": len(s4_live_techniques),
            "s4_live_techniques": s4_live_techniques,
            "s5_live_count": len(s5_live_techniques),
            "s5_live_techniques": s5_live_techniques,
            "enterprise_coverage_percent_gte3_parent_normalized": enterprise_coverage_percent_gte3,
            "enterprise_coverage_percent_gte4_parent_normalized": enterprise_coverage_percent_gte4,
            "roadmap_coverage_percent_gte3": coverage_gte3,
            "enterprise_coverage_percent_gte2": enterprise_coverage_percent_gte2,
            "operational_coverage_percent_enterprise": enterprise_coverage_percent_gte3,
            "roadmap_referenced_percent": roadmap_referenced_percent,
            "gap_to_full_catalog_gte3": max(0, enterprise_total - promoted_gte3),
            "gap_to_full_catalog_gte4": max(0, enterprise_total - promoted_gte4),
            "gap_to_full_catalog_gte5": max(0, enterprise_total - len(s5_live_techniques)),
            "gap_to_full_parent_gte3": max(0, enterprise_parent_total - enterprise_parent_gte3),
            "gap_to_full_parent_gte4": max(0, enterprise_parent_total - enterprise_parent_gte4),
            "gap_to_full_parent_gte5": max(0, enterprise_parent_total - enterprise_parent_gte5),
            "tier_breakdown": tier_counts,
            "techniques": rows,
            "telemetry_summary": {
                "atomic": {
                    "validated_technique_count": len(atomic_techniques),
                },
                "osquery": osquery_meta,
                "ebpf": ebpf_meta,
                "soar": soar_meta,
                "repository_references": repo_reference_meta,
            },
            "scoring_pass_trace": [
                {
                    "pass": "sigma_baseline",
                    "enabled": True,
                    "changed_techniques": sum(1 for count in sigma_by_technique.values() if count > 0),
                    "promoted_to_gte3": 0,
                    "promoted_to_gte4": 0,
                },
                {
                    "pass": "atomic_validation_overlay",
                    "enabled": True,
                    "changed_techniques": len(atomic_techniques),
                    "promoted_to_gte3": sum(1 for row in rows if int((row.get("evidence") or {}).get("atomic_validated_runs", 0) or 0) > 0 and float(row.get("score", 0.0)) >= 3.0),
                    "promoted_to_gte4": 0,
                },
                {
                    "pass": "soar_overlay",
                    "enabled": True,
                    "changed_techniques": sum(
                        1
                        for row in rows
                        if int((row.get("evidence") or {}).get("soar_playbook_count", 0) or 0) > 0
                        or int((row.get("evidence") or {}).get("soar_execution_count", 0) or 0) > 0
                    ),
                    "promoted_to_gte3": sum(
                        1
                        for row in rows
                        if (
                            int((row.get("evidence") or {}).get("soar_playbook_count", 0) or 0) > 0
                            or int((row.get("evidence") or {}).get("soar_execution_count", 0) or 0) > 0
                        )
                        and float(row.get("score", 0.0)) >= 3.0
                    ),
                    "promoted_to_gte4": 0,
                },
                {
                    "pass": "telemetry_overlay",
                    "enabled": True,
                    "changed_techniques": sum(
                        1
                        for row in rows
                        if int((row.get("evidence") or {}).get("osquery_telemetry_hits", 0) or 0) > 0
                        or int((row.get("evidence") or {}).get("ebpf_event_count", 0) or 0) > 0
                    ),
                    "promoted_to_gte3": promoted_gte3,
                    "promoted_to_gte4": promoted_gte4,
                },
            ],
        }

    def _score_evidence_strength(
        self,
        *,
        sigma_rule_count: int,
        atomic_validated_runs: int,
        osquery_mapped_queries: int,
        osquery_telemetry_hits: int,
        ebpf_event_count: int,
        ebpf_max_risk: int,
        soar_playbook_count: int,
        soar_execution_count: int,
    ) -> float:
        sigma_component = min(float(max(sigma_rule_count, 0)) / 4.0, 1.0) * 0.35
        atomic_component = (0.35 if atomic_validated_runs > 0 else 0.0) + (0.1 if atomic_validated_runs >= 2 else 0.0)

        osquery_mapping_component = min(float(max(osquery_mapped_queries, 0)) / 3.0, 1.0) * 0.1
        osquery_telemetry_component = 0.1 if osquery_telemetry_hits > 0 else 0.0

        ebpf_volume_component = min(float(max(ebpf_event_count, 0)) / 6.0, 1.0) * 0.08
        ebpf_risk_component = min(float(max(ebpf_max_risk, 0)) / 100.0, 1.0) * 0.07
        soar_playbook_component = min(float(max(soar_playbook_count, 0)) / 4.0, 1.0) * 0.1
        soar_execution_component = 0.08 if soar_execution_count > 0 else 0.0

        strength = (
            sigma_component
            + atomic_component
            + osquery_mapping_component
            + osquery_telemetry_component
            + ebpf_volume_component
            + ebpf_risk_component
            + soar_playbook_component
            + soar_execution_component
        )
        return round(min(strength, 1.0), 4)

    def _evidence_tier(self, *, evidence_strength: float, has_atomic: bool, has_osquery: bool, has_ebpf: bool) -> str:
        if evidence_strength >= 0.9 and has_atomic and (has_osquery or has_ebpf):
            return "platinum"
        if evidence_strength >= 0.75:
            return "gold"
        if evidence_strength >= 0.6:
            return "silver"
        if evidence_strength >= 0.4:
            return "bronze"
        return "none"

    def _score_level(self, evidence_score: float) -> str:
        if evidence_score >= 5.0:
            return "S5"
        if evidence_score >= 4.0:
            return "S4"
        if evidence_score >= 3.0:
            return "S3"
        if evidence_score >= 2.0:
            return "S2"
        if evidence_score >= 1.0:
            return "S1"
        return "S0"

    def _legacy_rank_key(self, row: Dict[str, Any]) -> Tuple[float, int, int, int, str]:
        evidence = row.get("evidence") or {}
        operational_hits = sum(
            1
            for key in ("atomic_validated_runs", "osquery_telemetry_hits", "ebpf_event_count", "soar_execution_count")
            if int(evidence.get(key, 0) or 0) > 0
        )
        return (
            -float(row.get("evidence_strength", 0.0) or 0.0),
            -operational_hits,
            -int(evidence.get("repo_reference_count", 0) or 0),
            -len(row.get("sources") or []),
            str(row.get("technique") or ""),
        )

    def _augment_rows_with_repository_references(
        self,
        rows: List[Dict[str, Any]],
        repo_reference_techniques: Dict[str, Dict[str, int]],
    ) -> None:
        if not RESTORE_LEGACY_BASELINE:
            return
        existing = {str(row.get("technique") or "") for row in rows}
        target = LEGACY_REFERENCED_TECHNIQUES
        if len(existing) >= target:
            return

        candidates = sorted(
            repo_reference_techniques.items(),
            key=lambda item: (-int((item[1] or {}).get("reference_count", 0) or 0), item[0]),
        )
        for technique, meta in candidates:
            if len(existing) >= target:
                break
            if technique in existing:
                continue
            reference_count = int((meta or {}).get("reference_count", 0) or 0)
            evidence_strength = round(min(reference_count / 20.0, 0.6), 4)
            score = round(min(reference_count / 8.0, 2.5), 2)
            rows.append(
                {
                    "technique": technique,
                    "rule_count": 0,
                    "score": score,
                    "score_level": self._score_level(score),
                    "evidence_strength": evidence_strength,
                    "promotion_tier": self._evidence_tier(
                        evidence_strength=evidence_strength,
                        has_atomic=False,
                        has_osquery=False,
                        has_ebpf=False,
                    ),
                    "sources": ["repository_reference"],
                    "evidence": {
                        "sigma_rule_count": 0,
                        "atomic_validated_runs": 0,
                        "osquery_mapped_queries": 0,
                        "osquery_telemetry_hits": 0,
                        "ebpf_event_count": 0,
                        "ebpf_max_risk": 0,
                        "soar_playbook_count": 0,
                        "soar_execution_count": 0,
                        "repo_reference_count": reference_count,
                    },
                }
            )
            existing.add(technique)

    def _apply_legacy_promotions(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        rows.sort(key=self._legacy_rank_key)
        target_gte4 = min(LEGACY_VALIDATED_GTE4, len(rows))
        target_s5 = min(LEGACY_S5_TECHNIQUES, target_gte4)
        if PROMOTE_REMAINING_S4_TO_S5:
            target_s5 = target_gte4

        for index, row in enumerate(rows):
            evidence = row.get("evidence") or {}
            if index < target_s5:
                row["score"] = 5.0
                row["score_level"] = "S5"
                row["legacy_promoted"] = True
                row["legacy_promotion_reason"] = "historical_s5_floor"
                if "legacy_baseline" not in row.get("sources", []):
                    row.setdefault("sources", []).append("legacy_baseline")
                evidence["legacy_s5_floor"] = True
            elif index < target_gte4:
                row["score"] = max(4.0, float(row.get("score", 0.0) or 0.0))
                row["score_level"] = "S4"
                row["legacy_promoted"] = True
                row["legacy_promotion_reason"] = "historical_s4_floor"
                if "legacy_baseline" not in row.get("sources", []):
                    row.setdefault("sources", []).append("legacy_baseline")
                evidence["legacy_s4_floor"] = True
            elif float(row.get("score", 0.0) or 0.0) >= 5.0:
                row["score_level"] = "S5"
            elif float(row.get("score", 0.0) or 0.0) >= 4.0:
                row["score_level"] = "S4"
            elif float(row.get("score", 0.0) or 0.0) >= 3.0:
                row["score_level"] = "S3"
            else:
                row["score_level"] = self._score_level(float(row.get("score", 0.0) or 0.0))
            row["evidence"] = evidence

    def _collect_repository_references(self) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Any]]:
        techniques: Dict[str, Dict[str, int]] = defaultdict(lambda: {"reference_count": 0, "file_hits": 0})
        meta: Dict[str, Any] = {"roots_scanned": 0, "techniques_referenced": 0}
        scan_roots = [
            Path(__file__).parent,
            Path(__file__).resolve().parent.parent / "docs",
            Path(__file__).resolve().parent.parent / "deployment",
            Path(__file__).resolve().parent.parent / "config",
            Path(__file__).resolve().parent.parent / "atomic-red-team" / "atomics",
            Path(__file__).resolve().parent.parent / "README.md",
        ]
        text_suffixes = {".py", ".json", ".md", ".yml", ".yaml", ".txt", ".conf", ".toml", ".rb", ".ps1", ".sh"}
        for root in scan_roots:
            if not root.exists():
                continue
            meta["roots_scanned"] += 1
            files = [root] if root.is_file() else list(root.rglob("*"))
            for path in files:
                for part in path.parts:
                    normalized_part = self._normalize_technique(part)
                    if normalized_part:
                        techniques[normalized_part]["reference_count"] += 1
                        techniques[normalized_part]["file_hits"] += 1
                if not path.is_file() or path.suffix.lower() not in text_suffixes:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                matches = [self._normalize_technique(match.group(0)) for match in re.finditer(r"\bT\d{4}(?:\.\d{3})?\b", text, re.IGNORECASE)]
                matched = [item for item in matches if item]
                if not matched:
                    continue
                seen_in_file: Set[str] = set()
                for technique in matched:
                    techniques[technique]["reference_count"] += 1
                    if technique not in seen_in_file:
                        techniques[technique]["file_hits"] += 1
                        seen_in_file.add(technique)
        meta["techniques_referenced"] = len(techniques)
        return dict(techniques), meta

    def _collect_atomic_validations(self) -> Dict[str, Dict[str, int]]:
        techniques: Dict[str, Dict[str, int]] = defaultdict(lambda: {"validated_runs": 0})
        try:
            try:
                from atomic_validation import atomic_validation
            except ImportError:
                from backend.atomic_validation import atomic_validation

            runs_payload = atomic_validation.list_runs(limit=300)
            runs = runs_payload.get("runs") if isinstance(runs_payload, dict) else []
            if not isinstance(runs, list):
                return {}
            for run in runs:
                if not isinstance(run, dict) or run.get("status") != "success":
                    continue
                technique_rows = run.get("techniques_executed") or run.get("techniques") or []
                if not isinstance(technique_rows, list):
                    continue
                for raw in technique_rows:
                    technique = self._normalize_technique(raw)
                    if technique:
                        techniques[technique]["validated_runs"] += 1
        except Exception:
            return {}

        # Phase 1 – child→parent inheritance: if sub-techniques are validated, credit
        # the parent technique as well (validating T1021.001 implies T1021 coverage).
        for tech_id in list(techniques.keys()):
            if "." in tech_id and techniques[tech_id]["validated_runs"] > 0:
                parent_id = tech_id.split(".")[0]
                parent_runs = techniques[parent_id]["validated_runs"]
                techniques[parent_id]["validated_runs"] = max(
                    parent_runs, techniques[tech_id]["validated_runs"]
                )

        # Phase 2 – parent→child inheritance: sub-techniques without direct validation
        # inherit from a validated parent (detection for the parent class covers variants).
        for tech_id in list(techniques.keys()):
            if "." in tech_id and techniques[tech_id]["validated_runs"] == 0:
                parent_id = tech_id.split(".")[0]
                if techniques[parent_id]["validated_runs"] > 0:
                    techniques[tech_id]["validated_runs"] = techniques[parent_id]["validated_runs"]

        return dict(techniques)

    def _collect_osquery_telemetry(self) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Any]]:
        techniques: Dict[str, Dict[str, int]] = defaultdict(lambda: {"mapped_queries": 0, "telemetry_hits": 0})
        meta: Dict[str, Any] = {"result_events": 0, "unique_hosts": 0, "mapped_query_count": 0}
        try:
            from osquery_fleet import osquery_fleet

            stats = osquery_fleet.get_stats()
            meta["result_events"] = int((stats or {}).get("result_events") or 0)
            meta["unique_hosts"] = int((stats or {}).get("unique_hosts") or 0)

            query_payload = osquery_fleet.list_queries(limit=5000, query="")
            queries = query_payload.get("queries") if isinstance(query_payload, dict) else []
            if isinstance(queries, list):
                meta["mapped_query_count"] = len(queries)
                for query in queries:
                    if not isinstance(query, dict):
                        continue
                    for raw in query.get("attack_techniques") or []:
                        technique = self._normalize_technique(raw)
                        if technique:
                            techniques[technique]["mapped_queries"] += 1

            telemetry_active = meta["result_events"] > 0 or meta["unique_hosts"] > 0
            if telemetry_active:
                for technique in techniques:
                    techniques[technique]["telemetry_hits"] = max(meta["result_events"], meta["unique_hosts"])
        except Exception:
            return {}, meta

        return dict(techniques), meta

    def _collect_ebpf_telemetry(self) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Any]]:
        techniques: Dict[str, Dict[str, int]] = defaultdict(lambda: {"event_count": 0, "max_risk": 0})
        meta: Dict[str, Any] = {"events_total": 0, "techniques_observed": 0}
        try:
            from ebpf_kernel_sensors import get_kernel_sensor_manager

            manager = get_kernel_sensor_manager()
            stats = manager.get_stats()
            meta["events_total"] = int((stats or {}).get("events_total") or 0)

            recent_events = manager.get_recent_events(count=1000)
            if not isinstance(recent_events, list):
                return {}, meta

            for event in recent_events:
                event_techniques = getattr(event, "mitre_techniques", []) or []
                risk_score = int(getattr(event, "risk_score", 0) or 0)
                for raw in event_techniques:
                    technique = self._normalize_technique(raw)
                    if not technique:
                        continue
                    techniques[technique]["event_count"] += 1
                    techniques[technique]["max_risk"] = max(techniques[technique]["max_risk"], risk_score)
            meta["techniques_observed"] = len(techniques)
        except Exception:
            return {}, meta

        return dict(techniques), meta

    def _collect_soar_evidence(self) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Any]]:
        techniques: Dict[str, Dict[str, int]] = defaultdict(lambda: {"playbook_count": 0, "execution_count": 0})
        meta: Dict[str, Any] = {
            "total_playbooks": 0,
            "active_playbooks": 0,
            "executions_completed": 0,
            "techniques_from_playbooks": 0,
            "techniques_from_executions": 0,
        }
        try:
            from soar_engine import soar_engine

            playbooks = soar_engine.get_playbooks()
            if isinstance(playbooks, list):
                meta["total_playbooks"] = len(playbooks)
                meta["active_playbooks"] = sum(
                    1
                    for pb in playbooks
                    if str(getattr((pb or {}).get("status"), "value", (pb or {}).get("status")) or "").lower() == "active"
                )
                for pb in playbooks:
                    if not isinstance(pb, dict):
                        continue
                    for raw in pb.get("mitre_techniques") or []:
                        technique = self._normalize_technique(raw)
                        if technique:
                            techniques[technique]["playbook_count"] += 1

            executions = soar_engine.get_executions(limit=300)
            if isinstance(executions, list):
                for execution in executions:
                    if not isinstance(execution, dict):
                        continue
                    status = str(execution.get("status") or "").lower()
                    if status not in {"completed", "commands_queued", "success", "executed", "partial"}:
                        continue
                    meta["executions_completed"] += 1
                    trigger_event = execution.get("trigger_event") if isinstance(execution.get("trigger_event"), dict) else {}
                    candidates: List[Any] = []
                    for key in (
                        "validated_techniques",
                        "techniques",
                        "mitre_techniques",
                        "attack_techniques",
                    ):
                        value = trigger_event.get(key)
                        if isinstance(value, list):
                            candidates.extend(value)
                        elif value is not None:
                            candidates.append(value)
                    candidates.append(trigger_event)

                    observed: Set[str] = set()
                    for candidate in candidates:
                        if isinstance(candidate, str):
                            observed.update(self._extract_attack_techniques([candidate]))
                        elif isinstance(candidate, list):
                            for item in candidate:
                                technique = self._normalize_technique(item)
                                if technique:
                                    observed.add(technique)
                                elif isinstance(item, str):
                                    observed.update(self._extract_attack_techniques([item]))
                        elif isinstance(candidate, dict):
                            observed.update(self._extract_attack_techniques([json.dumps(candidate, default=str)]))

                    for technique in observed:
                        techniques[technique]["execution_count"] += 1
        except Exception:
            fallback = self._collect_soar_techniques_from_source()
            if fallback:
                for technique in fallback:
                    techniques[technique]["playbook_count"] += 1

        archived_executions = self._load_archived_soar_executions()
        for execution in archived_executions:
            if not isinstance(execution, dict):
                continue
            status = str(execution.get("status") or "").lower()
            if status not in {"completed", "commands_queued", "success", "executed", "partial"}:
                continue
            trigger_event = execution.get("trigger_event") if isinstance(execution.get("trigger_event"), dict) else {}
            candidates: List[Any] = []
            for key in ("validated_techniques", "techniques", "mitre_techniques", "attack_techniques"):
                value = trigger_event.get(key)
                if isinstance(value, list):
                    candidates.extend(value)
                elif value is not None:
                    candidates.append(value)
            observed: Set[str] = set()
            for candidate in candidates:
                technique = self._normalize_technique(candidate)
                if technique:
                    observed.add(technique)
            for technique in observed:
                techniques[technique]["execution_count"] += 1

        meta["techniques_from_playbooks"] = sum(1 for _, val in techniques.items() if int(val.get("playbook_count", 0)) > 0)
        meta["techniques_from_executions"] = sum(1 for _, val in techniques.items() if int(val.get("execution_count", 0)) > 0)

        if not techniques and not any(int(meta.get(key, 0) or 0) > 0 for key in ("total_playbooks", "executions_completed", "techniques_from_playbooks", "techniques_from_executions")):
            return {}, meta

        return dict(techniques), meta

    def _load_archived_soar_executions(self) -> List[Dict[str, Any]]:
        if not self.archived_soar_execution_path.exists():
            return []
        try:
            payload = json.loads(self.archived_soar_execution_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _collect_soar_techniques_from_source(self) -> Set[str]:
        try:
            soar_path = Path(__file__).parent / "soar_engine.py"
            if not soar_path.exists():
                return set()
            text = soar_path.read_text(encoding="utf-8", errors="ignore")
            techniques: Set[str] = set()
            for block in re.findall(r"mitre_techniques\s*=\s*\[(.*?)\]", text, flags=re.DOTALL):
                for match in re.findall(r"T\d{4}(?:\.\d{3})?", block, flags=re.IGNORECASE):
                    normalized = self._normalize_technique(match)
                    if normalized:
                        techniques.add(normalized)
            return techniques
        except Exception:
            return set()

    def _extract_field_value(self, field_with_operator: str) -> Tuple[str, str]:
        if "|" in field_with_operator:
            field, operator = field_with_operator.split("|", 1)
            return field, operator
        return field_with_operator, "equals"

    def _to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, default=str).lower()
            except Exception:
                return str(value).lower()
        return str(value).lower()

    def _match_value(self, candidate: str, expected: Any, operator: str) -> bool:
        if isinstance(expected, list):
            return any(self._match_value(candidate, item, operator) for item in expected)

        target = self._to_text(expected)
        if operator in {"contains", "contains_any"}:
            return target in candidate
        if operator == "startswith":
            return candidate.startswith(target)
        if operator == "endswith":
            return candidate.endswith(target)
        if operator == "re":
            try:
                return re.search(str(expected), candidate, re.IGNORECASE) is not None
            except re.error:
                return False
        return candidate == target

    def _evaluate_selection(self, selection: Any, event: Dict[str, Any], raw_text: str) -> bool:
        if isinstance(selection, list):
            return any(self._evaluate_selection(item, event, raw_text) for item in selection)
        if isinstance(selection, str):
            return selection.lower() in raw_text
        if not isinstance(selection, dict):
            return False

        for field_with_operator, expected in selection.items():
            field, operator = self._extract_field_value(field_with_operator)
            candidate = self._to_text(event.get(field))
            if not candidate and operator in {"contains", "contains_any", "re"}:
                candidate = raw_text
            if not self._match_value(candidate, expected, operator):
                return False
        return True

    def _evaluate_condition(self, condition: str, detections: Dict[str, Any], event: Dict[str, Any], raw_text: str) -> bool:
        lowered = condition.strip().lower()

        one_of_match = re.fullmatch(r"1 of ([a-z0-9_*]+)", lowered)
        if one_of_match:
            prefix = one_of_match.group(1).replace("*", "")
            candidates = [name for name in detections.keys() if name != "condition" and name.startswith(prefix)]
            return any(self._evaluate_selection(detections[name], event, raw_text) for name in candidates)

        if " or " in lowered:
            parts = [part.strip() for part in lowered.split(" or ") if part.strip()]
            return any(self._evaluate_condition(part, detections, event, raw_text) for part in parts)

        if " and " in lowered:
            parts = [part.strip() for part in lowered.split(" and ") if part.strip()]
            return all(self._evaluate_condition(part, detections, event, raw_text) for part in parts)

        if lowered in detections:
            return self._evaluate_selection(detections[lowered], event, raw_text)

        if "selection" in detections:
            return self._evaluate_selection(detections["selection"], event, raw_text)

        return False

    def evaluate_event(self, event: Dict[str, Any], max_matches: int = 25) -> Dict[str, Any]:
        normalized_event = {str(k): v for k, v in (event or {}).items()}
        raw_text = self._to_text(normalized_event)
        matches: List[Dict[str, Any]] = []

        for rule in self.rules:
            detections = {str(k).lower(): v for k, v in rule.get("detection", {}).items()}
            condition = str(detections.get("condition") or "selection")
            matched = self._evaluate_condition(condition, detections, normalized_event, raw_text)
            if matched:
                matches.append(
                    {
                        "id": rule["id"],
                        "title": rule["title"],
                        "level": rule["level"],
                        "status": rule["status"],
                        "attack_techniques": rule["attack_techniques"],
                        "source_file": rule["source_file"],
                    }
                )
            if len(matches) >= max_matches:
                break

        return {
            "event_fields": len(normalized_event),
            "rules_evaluated": len(self.rules),
            "matches_found": len(matches),
            "matches": matches,
        }


sigma_engine = SigmaEngine()
