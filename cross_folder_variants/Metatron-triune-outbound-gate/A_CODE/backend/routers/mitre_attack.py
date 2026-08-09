import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.mitre_catalog import load_mitre_catalog_totals

from .dependencies import get_current_user
try:
    from sigma_engine import sigma_engine
except Exception:
    from backend.sigma_engine import sigma_engine

router = APIRouter(prefix="/mitre", tags=["MITRE ATT&CK"])
MITRE_COVERAGE_CACHE_TTL_SECONDS = max(
    30,
    int(os.environ.get("MITRE_COVERAGE_CACHE_TTL_SECONDS", "900") or 900),
)

TACTICS = [
    {"id": "TA0043", "name": "Reconnaissance"},
    {"id": "TA0042", "name": "Resource Development"},
    {"id": "TA0001", "name": "Initial Access"},
    {"id": "TA0002", "name": "Execution"},
    {"id": "TA0003", "name": "Persistence"},
    {"id": "TA0004", "name": "Privilege Escalation"},
    {"id": "TA0005", "name": "Defense Evasion"},
    {"id": "TA0006", "name": "Credential Access"},
    {"id": "TA0007", "name": "Discovery"},
    {"id": "TA0008", "name": "Lateral Movement"},
    {"id": "TA0009", "name": "Collection"},
    {"id": "TA0011", "name": "Command and Control"},
    {"id": "TA0010", "name": "Exfiltration"},
    {"id": "TA0040", "name": "Impact"},
]

_coverage_cache: Dict[str, Any] = {}
_coverage_cache_ts: float = 0.0
_tactic_mapping_cache: Dict[str, Any] = {}
_tactic_mapping_cache_ts: float = 0.0
TACTIC_PHASE_TO_ID = {
    "reconnaissance": "TA0043",
    "resource-development": "TA0042",
    "initial-access": "TA0001",
    "execution": "TA0002",
    "persistence": "TA0003",
    "privilege-escalation": "TA0004",
    "defense-evasion": "TA0005",
    "credential-access": "TA0006",
    "discovery": "TA0007",
    "lateral-movement": "TA0008",
    "collection": "TA0009",
    "command-and-control": "TA0011",
    "exfiltration": "TA0010",
    "impact": "TA0040",
}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _score_int_to_level(score: int) -> str:
    if score >= 5:
        return "S5"
    if score >= 4:
        return "S4"
    if score >= 3:
        return "S3"
    if score >= 2:
        return "S2"
    if score >= 1:
        return "S1"
    return "S0"


def _load_tvr_index() -> Dict[str, Any]:
    """Load the canonical TVR index from evidence_bundle.

    technique_index.json is the authoritative key set (691 techniques).
    coverage_summary.json provides updated tier/score data for techniques
    already in the index and takes priority on a per-technique basis.
    """
    import json
    from pathlib import Path

    evidence_root = Path(os.environ.get("EVIDENCE_BUNDLE_ROOT", "/var/lib/seraph-ai/evidence-bundle"))

    # Step 1: load technique_index.json as the authoritative key set
    merged: Dict[str, Any] = {}
    idx_path = evidence_root / "technique_index.json"
    if idx_path.exists():
        try:
            raw = json.loads(idx_path.read_text(encoding="utf-8"))
            techs = raw.get("techniques") or {}
            if isinstance(techs, dict):
                merged.update(techs)
        except Exception:
            pass

    # Step 2: override with coverage_summary.json data, but ONLY for techniques
    # already in the index — never add new techniques from coverage_summary
    cs_path = evidence_root / "coverage_summary.json"
    if cs_path.exists():
        try:
            raw = json.loads(cs_path.read_text(encoding="utf-8"))
            tech_list = raw.get("techniques") or []
            if isinstance(tech_list, list):
                for entry in tech_list:
                    tid = entry.get("technique_id")
                    if tid and tid in merged:
                        merged[tid] = entry
        except Exception:
            pass

    return merged


def _load_soar_overlay() -> Dict[str, Dict[str, int]]:
    """Load lightweight SOAR linkage counts for MITRE techniques.

    We intentionally do not depend on sigma_engine rows being exhaustive.
    Instead, we derive per-technique counts from:
    - Archived SOAR executions JSON (materialized evidence snapshot)
    - SOAR playbook definitions (mitre_techniques mapping)
    """
    import json
    from pathlib import Path

    overlay: Dict[str, Dict[str, int]] = {}

    # 1) Playbook mapping (technique -> playbook_count)
    try:
        try:
            from soar_engine import soar_engine
        except Exception:
            from backend.soar_engine import soar_engine  # type: ignore

        playbooks = soar_engine.get_playbooks()
        if isinstance(playbooks, list):
            for pb in playbooks:
                if not isinstance(pb, dict):
                    continue
                for raw in pb.get("mitre_techniques") or []:
                    tid = str(raw or "").strip().upper()
                    if not tid:
                        continue
                    overlay.setdefault(tid, {"playbook_count": 0, "execution_count": 0})
                    overlay[tid]["playbook_count"] += 1
    except Exception:
        pass

    # 2) Archived execution evidence (technique -> execution_count)
    try:
        archive_path = Path(
            os.environ.get(
                "SIGMA_SOAR_EXECUTION_ARCHIVE_PATH",
                str(Path(__file__).resolve().parent.parent / "data" / "soar_executions_archive.json"),
            )
        )
        if archive_path.exists():
            payload = json.loads(archive_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                for row in payload:
                    if not isinstance(row, dict):
                        continue
                    status = str(row.get("status") or "").lower()
                    if status not in {"completed", "commands_queued", "success", "executed", "partial"}:
                        continue
                    trigger_event = row.get("trigger_event") if isinstance(row.get("trigger_event"), dict) else {}
                    for key in ("validated_techniques", "techniques", "mitre_techniques", "attack_techniques"):
                        value = trigger_event.get(key)
                        if not isinstance(value, list):
                            continue
                        for raw in value:
                            tid = str(raw or "").strip().upper()
                            if not tid:
                                continue
                            overlay.setdefault(tid, {"playbook_count": 0, "execution_count": 0})
                            overlay[tid]["execution_count"] += 1
    except Exception:
        pass

    return overlay


def _load_arda_prevention_overlay() -> Dict[str, Dict[str, int]]:
    """Load per-technique ARDA exec-prevention evidence counts.

    Evidence records are written by scripts/run_arda_prevention_evidence.py.
    """
    import json
    from pathlib import Path

    overlay: Dict[str, Dict[str, int]] = {}
    evidence_dir = _arda_prevention_dir()
    if not evidence_dir.exists():
        return overlay

    for path in sorted(evidence_dir.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        tid = str(row.get("technique_id") or "").strip().upper()
        if not tid:
            continue
        exec_attempt = row.get("exec_attempt") if isinstance(row.get("exec_attempt"), dict) else {}
        enforcement = row.get("enforcement") if isinstance(row.get("enforcement"), dict) else {}
        denied = bool(exec_attempt.get("denied"))
        delta = _as_int(enforcement.get("deny_count_delta", 0), 0)
        pulse_total = _as_int(enforcement.get("pulse_total_denials", 0), 0)
        overlay.setdefault(
            tid,
            {
                "prevention_events": 0,
                "exec_denied_events": 0,
                "deny_count_total": 0,
                "max_pulse_total_denials": 0,
            },
        )
        overlay[tid]["prevention_events"] += 1
        if denied:
            overlay[tid]["exec_denied_events"] += 1
        overlay[tid]["deny_count_total"] += delta
        if pulse_total > overlay[tid]["max_pulse_total_denials"]:
            overlay[tid]["max_pulse_total_denials"] = pulse_total

    return overlay


def _evidence_root() -> Path:
    return Path(os.environ.get("EVIDENCE_BUNDLE_ROOT", "/var/lib/seraph-ai/evidence-bundle"))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _artifacts_root() -> Path:
    """Where artifacts/evidence/* lives. In container this is mounted at
    /var/lib/seraph-ai/artifacts (via SERAPH_DATA_DIR); on host it's the project's
    artifacts/ directory."""
    candidates = [
        os.environ.get("SERAPH_DATA_DIR"),
        os.environ.get("SERAPH_ARTIFACTS_ROOT"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return _project_root() / "artifacts"


def _atomic_red_team_root() -> Path:
    """Where the MITRE STIX bundle lives. Container mount: /opt/atomic-red-team.
    Host: project's atomic-red-team/."""
    for cand in [
        os.environ.get("ATOMIC_RED_TEAM_PATH"),
        "/opt/atomic-red-team",
        str(_project_root() / "atomic-red-team"),
    ]:
        if not cand:
            continue
        # ATOMIC_RED_TEAM_PATH may point at .../atomics — climb to its parent dir
        # so we can find atomic_red_team/enterprise-attack.json next to it.
        p = Path(cand)
        if p.name == "atomics" and p.parent.exists():
            p = p.parent
        if p.exists():
            return p
    return _project_root() / "atomic-red-team"


def _load_tactic_mapping(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Build technique_id -> {name, tactic_ids[], tactic_names[]} from the STIX
    enterprise-attack bundle. Cached."""
    global _tactic_mapping_cache, _tactic_mapping_cache_ts
    now = time.monotonic()
    if not force_refresh and _tactic_mapping_cache and (now - _tactic_mapping_cache_ts) < 3600:
        return _tactic_mapping_cache

    import json
    art = _atomic_red_team_root()
    candidates = [
        Path(os.environ.get("MITRE_STIX_BUNDLE_PATH", "")),
        art / "atomic_red_team" / "enterprise-attack.json",
        _project_root() / "atomic-red-team" / "atomic_red_team" / "enterprise-attack.json",
    ]
    bundle = None
    for path in candidates:
        if path and path.exists():
            try:
                bundle = json.loads(path.read_text(encoding="utf-8"))
                break
            except Exception:
                continue
    mapping: Dict[str, Dict[str, Any]] = {}
    if not bundle:
        _tactic_mapping_cache = mapping
        _tactic_mapping_cache_ts = now
        return mapping

    for obj in bundle.get("objects", []) or []:
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        ext = next(
            (ref for ref in obj.get("external_references") or [] if ref.get("source_name") == "mitre-attack"),
            None,
        )
        if not ext or not ext.get("external_id"):
            continue
        tid = ext["external_id"]
        tactic_ids: List[str] = []
        tactic_names: List[str] = []
        for phase in obj.get("kill_chain_phases") or []:
            if phase.get("kill_chain_name") != "mitre-attack":
                continue
            phase_name = phase.get("phase_name") or ""
            tid_ta = TACTIC_PHASE_TO_ID.get(phase_name)
            if tid_ta and tid_ta not in tactic_ids:
                tactic_ids.append(tid_ta)
                tactic_names.append(phase_name.replace("-", " ").title())
        mapping[tid] = {
            "name": obj.get("name") or tid,
            "tactic_ids": tactic_ids,
            "tactic_names": tactic_names,
        }

    _tactic_mapping_cache = mapping
    _tactic_mapping_cache_ts = now
    return mapping


def _load_honest_classification() -> Dict[str, Dict[str, Any]]:
    """Load the most recent honest TVR classification override.

    The honest classification (built from observed K0 kernel denials + deductive
    K1/K2/L1/A2 modes) is the freshest scoring source and overrides the
    snapshot-baked technique_index when present."""
    import json
    import glob

    project = _project_root()
    artifacts = _artifacts_root()
    candidates: List[str] = []
    custom = os.environ.get("HONEST_TVR_CLASSIFICATION_PATH")
    if custom:
        candidates.append(custom)
    candidates.extend(
        sorted(glob.glob(str(project / "metatron_honest_tvr_classification_*.json")), reverse=True)
    )
    # Container/cloud layout — undeniable_pipeline runs drop a tagged copy of
    # the classification under artifacts/. Pick the most recent one.
    candidates.extend(
        sorted(
            glob.glob(str(artifacts / "undeniable_pipeline" / "*" / "metatron_honest_tvr_classification*.json")),
            reverse=True,
        )
    )
    candidates.extend(
        sorted(glob.glob(str(artifacts / "metatron_honest_tvr_classification_*.json")), reverse=True)
    )
    for path in candidates:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            techs = data.get("techniques") or {}
            if isinstance(techs, dict) and techs:
                return techs
        except Exception:
            continue
    return {}


def _honest_score(tier: str, evidence_modes: List[Dict[str, Any]]) -> int:
    """Map honest classification tier + evidence modes to integer score 0-5."""
    if tier == "platinum":
        return 5
    has_hard = any(em.get("strength") == "HARD_POSITIVE" for em in evidence_modes or [])
    if has_hard:
        return 5
    has_strong = any(
        (em.get("strength") in ("STRONG_SUPPORT", "STRONG"))
        or em.get("mode") in ("K1", "K2", "L1", "A2", "L0", "H1")
        for em in evidence_modes or []
    )
    if tier == "support_only" and has_strong:
        return 3
    if tier == "support_only":
        return 2
    return 0


def _load_multi_source_detection() -> Dict[str, Dict[str, Any]]:
    """Load per-technique live multi-source detection report (Falco/Suricata/
    Zeek/Osquery/Deception/etc.)."""
    import json
    path = _evidence_root() / "multi_source_detection_report.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("detections_by_technique") or {}
    except Exception:
        return {}


_telemetry_overlay_cache: Dict[str, Any] = {}
_telemetry_overlay_ts: float = 0.0


def _read_json(path: Path) -> Any:
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_glob(pattern_dir: Path, pattern: str) -> Path:
    """Return the most recently modified file matching pattern, or None."""
    if not pattern_dir.exists():
        return None
    matches = sorted(pattern_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _load_telemetry_overlay(force: bool = False) -> Dict[str, Dict[str, Any]]:
    """Aggregate per-technique counts across every telemetry integration.

    Returns: tid -> {falco_event_count, falco_rule_count, suricata_event_count,
    arkime_packet_count, arkime_pcap_files, yara_match_count, clamav_scan_count,
    deception_trigger_count, unified_agent_runs, sources: set}
    Cached for 15 min to avoid re-reading the falco dedup (~62MB)."""
    global _telemetry_overlay_cache, _telemetry_overlay_ts
    now = time.monotonic()
    if not force and _telemetry_overlay_cache and (now - _telemetry_overlay_ts) < MITRE_COVERAGE_CACHE_TTL_SECONDS:
        return _telemetry_overlay_cache

    overlay: Dict[str, Dict[str, Any]] = {}
    artifacts = _artifacts_root() / "evidence"

    def slot(tid: str) -> Dict[str, Any]:
        return overlay.setdefault(
            tid,
            {
                "falco_event_count": 0,
                "falco_rule_count": 0,
                "falco_rules": [],
                "suricata_event_count": 0,
                "arkime_packet_count": 0,
                "arkime_pcap_files": 0,
                "yara_match_count": 0,
                "clamav_scan_count": 0,
                "deception_trigger_count": 0,
                "unified_agent_runs": 0,
                "zeek_event_count": 0,
                "sources": [],
            },
        )

    # Telemetry harvest summary (yara / clamav / suricata / arkime per-tid totals)
    harvest = _read_json(artifacts / "telemetry_harvest_summary.json") or {}
    for source_name in ("yara", "clamav", "suricata", "arkime"):
        techs = ((harvest.get("results") or {}).get(source_name) or {}).get("techniques") or {}
        for tid, count in techs.items():
            s = slot(tid)
            if source_name == "yara":
                s["yara_match_count"] += int(count or 0)
            elif source_name == "clamav":
                s["clamav_scan_count"] += int(count or 0)
            elif source_name == "suricata":
                s["suricata_event_count"] += int(count or 0)
            elif source_name == "arkime":
                s["arkime_packet_count"] += int(count or 0)
            if source_name not in s["sources"]:
                s["sources"].append(source_name)

    # Falco dedup summary — authoritative deduplicated rule firings per technique
    falco_summary = _latest_glob(artifacts / "falco", "falco_dedup_summary_*.json")
    if falco_summary:
        falco_data = _read_json(falco_summary) or {}
        for group in falco_data.get("groups") or []:
            count = int(group.get("count") or 0)
            rule = group.get("rule") or ""
            for tid in group.get("techniques") or []:
                if not tid:
                    continue
                s = slot(tid)
                s["falco_event_count"] += count
                s["falco_rule_count"] += 1
                if rule and rule not in s["falco_rules"]:
                    s["falco_rules"].append(rule)
                if "falco" not in s["sources"]:
                    s["sources"].append("falco")

    # Unified agent harvest summary — composite monitor coverage list
    ua_summary = _latest_glob(artifacts / "unified_agent", "harvest_summary_*.json")
    if ua_summary:
        ua_data = _read_json(ua_summary) or {}
        runs = int(ua_data.get("run_records_written") or 0)
        for tid in ua_data.get("techniques_covered") or []:
            s = slot(tid)
            s["unified_agent_runs"] += runs
            if "unified_agent" not in s["sources"]:
                s["sources"].append("unified_agent")

    # Deception harvest summaries — count canary triggers per technique
    deception_dir = artifacts / "deception"
    if deception_dir.exists():
        for path in deception_dir.glob("run_*.json"):
            data = _read_json(path) or {}
            tids = []
            evid = data.get("deception_evidence") or {}
            tids.extend(data.get("techniques") or [])
            tids.extend(evid.get("techniques") or [])
            triggers = sum(1 for r in (evid.get("probe_results") or []) if r.get("triggered"))
            triggers = max(triggers, int(evid.get("trigger_count") or 0), 1 if tids else 0)
            for tid in tids:
                s = slot(tid)
                s["deception_trigger_count"] += triggers
                if "deception" not in s["sources"]:
                    s["sources"].append("deception")

    _telemetry_overlay_cache = overlay
    _telemetry_overlay_ts = now
    return overlay


def _load_telemetry_harvest() -> Dict[str, Any]:
    """Load yara/clamav/suricata/arkime per-technique harvest counts."""
    import json
    candidates = [
        Path(os.environ.get("TELEMETRY_HARVEST_SUMMARY_PATH", "")),
        _artifacts_root() / "evidence" / "telemetry_harvest_summary.json",
        _project_root() / "artifacts" / "evidence" / "telemetry_harvest_summary.json",
    ]
    for path in candidates:
        if path and path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


def _arda_prevention_dir() -> Path:
    custom = os.environ.get("ARDA_PREVENTION_EVIDENCE_DIR")
    if custom:
        return Path(custom)
    for cand in (
        _artifacts_root() / "evidence" / "arda_prevention",
        _project_root() / "artifacts" / "evidence" / "arda_prevention",
    ):
        if cand.exists():
            return cand
    return _artifacts_root() / "evidence" / "arda_prevention"


def _load_per_technique_evidence(tid: str) -> Dict[str, Any]:
    """Aggregate every piece of telemetry/evidence we have for one technique.

    Returns a structured payload the UI can render as expandable rows of
    arda_kernel_denial events, falco kernel firings, deception lure hits,
    osquery rows, sigma matches, and integration summaries."""
    import json

    tid = (tid or "").strip().upper()
    if not tid:
        return {"technique": "", "evidence": {}}
    short = tid.replace(".", "")
    bundle: Dict[str, Any] = {
        "technique_id": tid,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "arda_prevention": {"events": [], "denied_count": 0, "total_count": 0},
        "multi_source_detection": {},
        "integration": {},
        "sigma_matches": {"rules": [], "match_semantics": ""},
        "harvest_telemetry": {},
        "honest_classification": None,
    }

    # 1) ARDA per-technique prevention records (newest first so the drawer
    # surfaces the freshest K0 evidence at the top of the list).
    arda_dir = _arda_prevention_dir()
    if arda_dir.exists():
        glob_patterns = [f"arda_prevention_{tid}_*.json", f"arda_prevention_{short}_*.json"]
        seen_paths = set()
        for pattern in glob_patterns:
            for fp in sorted(arda_dir.glob(pattern), reverse=True):
                if fp in seen_paths:
                    continue
                seen_paths.add(fp)
                try:
                    row = json.loads(fp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                bundle["arda_prevention"]["total_count"] += 1
                exec_attempt = row.get("exec_attempt") or {}
                if exec_attempt.get("denied"):
                    bundle["arda_prevention"]["denied_count"] += 1
                # Try to express source_file as a relative path under whichever
                # mount actually contains it (project root on host, artifacts
                # root in container). Fall back to the basename if neither works.
                rel_source = fp.name
                for base in (_project_root(), _artifacts_root()):
                    try:
                        rel_source = str(fp.relative_to(base))
                        break
                    except ValueError:
                        continue
                enforcement = row.get("enforcement") or {}
                bundle["arda_prevention"]["events"].append(
                    {
                        "captured_at": row.get("captured_at"),
                        "denied": bool(exec_attempt.get("denied")),
                        "rc": exec_attempt.get("rc"),
                        "deny_count_delta": enforcement.get("deny_count_delta", row.get("deny_count_delta")),
                        "pulse_total_denials": enforcement.get("pulse_total_denials", row.get("pulse_total_denials")),
                        "payload_sha256": (exec_attempt.get("payload_sha256") or row.get("payload_sha256")),
                        "bpf_sha256": ((row.get("substrate_proof") or {}).get("bpf_program") or {}).get("sha256") or row.get("bpf_sha256"),
                        "source_file": rel_source,
                    }
                )

    # 2) Multi-source detection (live falco/zeek/suricata/deception/osquery)
    ms = _load_multi_source_detection()
    if tid in ms:
        bundle["multi_source_detection"] = ms[tid]

    # 3) Integration evidence directory (per-technique)
    integ_dir = _evidence_root() / "integration_evidence" / tid
    if integ_dir.exists() and integ_dir.is_dir():
        files = {}
        for fp in integ_dir.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    files[fp.stem] = {
                        "source": data.get("source"),
                        "collected_at": data.get("collected_at") or data.get("generated_at"),
                        "row_count": len(data.get("data") or []) if isinstance(data.get("data"), list) else None,
                        "sample": (data.get("data") or [None])[:2] if isinstance(data.get("data"), list) else None,
                        "summary": {k: v for k, v in data.items() if k not in {"data", "raw_events", "events"}},
                    }
            except Exception:
                continue
        bundle["integration"] = files

    # 4) Sigma matches (per technique)
    sigma_dir = _project_root() / "sigma_matches"
    for stem in (tid, short, tid.replace(".", "_")):
        sigma_path = sigma_dir / f"{stem}.json"
        if sigma_path.exists():
            try:
                bundle["sigma_matches"] = json.loads(sigma_path.read_text(encoding="utf-8"))
            except Exception:
                pass
            break

    # 5) Telemetry harvest counts
    harvest = _load_telemetry_harvest()
    h_results = harvest.get("results") or {}
    for source_name in ("yara", "clamav", "suricata", "arkime"):
        techs = (h_results.get(source_name) or {}).get("techniques") or {}
        if tid in techs:
            bundle["harvest_telemetry"][source_name] = {"event_count": techs[tid]}

    # 6) Honest classification (if applicable)
    honest = _load_honest_classification()
    if tid in honest:
        bundle["honest_classification"] = honest[tid]

    # 7) Multi-integration telemetry overlay (cached)
    telem = _load_telemetry_overlay().get(tid)
    if telem:
        bundle["telemetry_overlay"] = telem

    return bundle


def _build_coverage_response(force_refresh: bool = False) -> Dict[str, Any]:
    global _coverage_cache, _coverage_cache_ts

    now = time.monotonic()
    if not force_refresh and _coverage_cache and (now - _coverage_cache_ts) < MITRE_COVERAGE_CACHE_TTL_SECONDS:
        return _coverage_cache

    # --- Canonical TVR source (evidence_bundle) ---
    tvr_index = _load_tvr_index()
    catalog_totals = load_mitre_catalog_totals()
    enterprise_total = int(catalog_totals.get("enterprise_technique_total") or 0)
    enterprise_parent_total = int(catalog_totals.get("enterprise_parent_total") or 0)
    roadmap_total = int(catalog_totals.get("roadmap_target_total") or enterprise_total or 0)

    # --- Sigma engine for SOAR / telemetry overlays and (optional) fallback scoring ---
    summary = sigma_engine.coverage_summary()
    unified = summary.get("unified_coverage") or {}
    sigma_rows = {row.get("technique"): row for row in (unified.get("techniques") or []) if row.get("technique")}
    soar_overlay = _load_soar_overlay()
    arda_prevention_overlay = _load_arda_prevention_overlay()
    tactic_mapping = _load_tactic_mapping()
    honest_classification = _load_honest_classification()
    multi_source_detection = _load_multi_source_detection()
    telemetry_overlay = _load_telemetry_overlay()

    # When TVR index is populated, it is the authoritative key set. Sigma augments
    # evidence (SOAR/osquery/atomic) but must not add new technique IDs.
    # Honest classification may include K0-observed techniques the legacy index
    # missed (e.g. T1547.011, T1574.002) — fold those in so the UI shows them.
    if tvr_index:
        all_technique_ids = set(tvr_index.keys()) | set(honest_classification.keys())
    else:
        all_technique_ids = set(tvr_index.keys()) | set(sigma_rows.keys()) | set(honest_classification.keys())

    techniques: List[Dict[str, Any]] = []
    for tid in sorted(all_technique_ids):
        tvr = tvr_index.get(tid) or {}
        sigma_row = sigma_rows.get(tid) or {}
        evidence = sigma_row.get("evidence") or {}
        overlay = soar_overlay.get(tid) or {}
        prevention = arda_prevention_overlay.get(tid) or {}
        if "soar_playbook_count" not in evidence and overlay:
            evidence = dict(evidence)
            evidence["soar_playbook_count"] = _as_int(overlay.get("playbook_count", 0), 0)
            evidence["soar_execution_count"] = _as_int(overlay.get("execution_count", 0), 0)
        if "soar_playbook_count" not in evidence:
            evidence = dict(evidence)
            evidence["soar_playbook_count"] = 0
            evidence["soar_execution_count"] = 0

        if prevention:
            evidence = dict(evidence)
            evidence["arda_prevention_events"] = _as_int(prevention.get("prevention_events", 0), 0)
            evidence["arda_exec_denied_events"] = _as_int(prevention.get("exec_denied_events", 0), 0)
            evidence["arda_deny_count_total"] = _as_int(prevention.get("deny_count_total", 0), 0)
            evidence["arda_max_pulse_total_denials"] = _as_int(
                prevention.get("max_pulse_total_denials", 0), 0
            )

        # Multi-integration telemetry overlay (Falco/Suricata/Zeek/Arkime/Yara/
        # ClamAV/Deception/Unified-Agent)
        telem = telemetry_overlay.get(tid) or {}
        if telem:
            evidence = dict(evidence)
            for k in (
                "falco_event_count",
                "falco_rule_count",
                "suricata_event_count",
                "arkime_packet_count",
                "yara_match_count",
                "clamav_scan_count",
                "deception_trigger_count",
                "unified_agent_runs",
            ):
                evidence[k] = _as_int(telem.get(k, 0), 0)
            evidence["telemetry_sources"] = list(telem.get("sources") or [])

        # Base score from TVR validation (0-5, integer). Sigma augments with SOAR
        # evidence; when SOAR response evidence is present we treat S5 as "validated
        # + automated response linked". This aligns the UI's S5 definition with
        # the evidence overlays the system can actually observe.
        tvr_score = _as_int(tvr.get("score", 0), 0) if tvr else _as_int(sigma_row.get("score", 0), 0)
        tvr_tier = str(tvr.get("tier", "none") or "none") if tvr else str(sigma_row.get("promotion_tier", "none") or "none")
        runs = _as_int(tvr.get("repeated_runs", 0), 0) if tvr else _as_int(evidence.get("atomic_validated_runs", 0), 0)
        reason = str(tvr.get("reason", "") or "") if tvr else ""

        soar_playbook_count = _as_int(evidence.get("soar_playbook_count", 0), 0)
        soar_execution_count = _as_int(evidence.get("soar_execution_count", 0), 0)
        soar_linked = (soar_playbook_count > 0) or (soar_execution_count > 0)

        # Honest TVR classification overlay — when the latest run produced a
        # K0/K1/K2/L1/A2 evidence record for this technique, override the snapshot
        # score so the UI reflects the freshest live posture.
        honest_row = honest_classification.get(tid) or {}
        honest_tier = str(honest_row.get("tier") or "")
        honest_modes = (honest_row.get("evidence") or {}).get("evidence_modes") or []
        if honest_row:
            honest_score_val = _honest_score(honest_tier, honest_modes)
            tvr_score = max(tvr_score, honest_score_val)
            if honest_tier and (honest_score_val >= 5 or not tvr_tier or tvr_tier == "none"):
                tvr_tier = honest_tier
            evidence = dict(evidence)
            evidence["honest_modes"] = [em.get("mode") for em in honest_modes if em.get("mode")]
            evidence["honest_tier"] = honest_tier
            evidence["honest_hard_positive"] = bool(
                (honest_row.get("evidence") or {}).get("hard_positives_present")
            )

        # Multi-source live-detection overlay (Falco/Suricata/Zeek/Deception/Osquery)
        ms_row = multi_source_detection.get(tid) or {}
        if ms_row:
            evidence = dict(evidence)
            evidence["live_detection_count"] = _as_int(ms_row.get("detection_count", 0), 0)
            evidence["live_source_count"] = _as_int(ms_row.get("source_count", 0), 0)
            evidence["live_sources"] = list(ms_row.get("sources") or [])

        score = int(max(0, min(5, tvr_score)))
        if score >= 4 and soar_linked:
            score = 5
        # Note: honest K0-observed (kernel denial) is itself a hard positive; we no
        # longer downshift platinum just because a SOAR playbook isn't wired up.
        # If the legacy snapshot said S5 but there's no honest/SOAR evidence, fall
        # back to S4 so we don't over-claim.
        elif score >= 5 and not soar_linked and not honest_row:
            score = 4

        tier = "platinum" if score >= 5 else (honest_tier or tvr_tier)
        sources = (["tvr_validated"] if tvr else []) + (sigma_row.get("sources") or [])
        if honest_row:
            sources.append("honest_tvr")
            for em in honest_modes:
                mode = em.get("mode")
                if mode and mode not in sources:
                    sources.append(f"honest_{mode}")
        for ls in (evidence.get("live_sources") or []):
            if ls not in sources:
                sources.append(ls)
        for ls in (evidence.get("telemetry_sources") or []):
            if ls not in sources:
                sources.append(ls)

        operational = (
            runs > 0
            or _as_int(evidence.get("osquery_telemetry_hits", 0), 0) > 0
            or _as_int(evidence.get("ebpf_event_count", 0), 0) > 0
            or soar_execution_count > 0
        )

        # Resolve tactic membership from the canonical STIX bundle, falling back
        # to whatever sigma_row provided.
        tmap = tactic_mapping.get(tid) or {}
        tactic_ids = tmap.get("tactic_ids") or sigma_row.get("tactics") or []
        primary_tactic = (
            sigma_row.get("tactic")
            or (tactic_ids[0] if tactic_ids else "")
            or ""
        )

        techniques.append({
            "technique": tid,
            "id": tid,
            "name": tmap.get("name") or sigma_row.get("name") or tid,
            "score": int(score),
            "score_level": _score_int_to_level(int(score)),
            "tactic": primary_tactic,
            "tactic_ids": list(tactic_ids),
            "tactics": list(tactic_ids),
            "implemented": int(score) >= 1,
            "operational_evidence": operational,
            "implemented_evidence_count": runs,
            "sources": sources,
            "tvr_validated": bool(tvr),
            "tvr_runs": runs,
            "tvr_reason": reason,
            "tvr_score": tvr_score,
            "tvr_tier": tvr_tier,
            "soar_linked": soar_linked,
            "evidence": evidence,
            "promotion_tier": tier,
        })

    covered_gte2 = sum(1 for t in techniques if int(t["score"]) >= 2)
    covered_gte3 = sum(1 for t in techniques if int(t["score"]) >= 3)
    covered_gte4 = sum(1 for t in techniques if int(t["score"]) >= 4)
    covered_gte5 = sum(1 for t in techniques if int(t["score"]) >= 5)
    covered_parent_gte3 = len({str(t["technique"]).split(".")[0] for t in techniques if int(t["score"]) >= 3})
    covered_parent_gte4 = len({str(t["technique"]).split(".")[0] for t in techniques if int(t["score"]) >= 4})
    covered_parent_gte5 = len({str(t["technique"]).split(".")[0] for t in techniques if int(t["score"]) >= 5})
    operational_observed = sum(1 for t in techniques if t["operational_evidence"])

    total = len(techniques)

    # Tactic summary and priority gaps are UI-only helpers. The heat grid shows
    # a per-tactic coverage roll-up; we compute it here from the merged technique
    # set so the percentages always match what the dropdown would filter to.
    # Build full canonical tactic membership from the STIX mapping so totals
    # reflect every technique that belongs to that tactic — even ones outside
    # our snapshot universe — which is what the user expects.
    tactic_universe: Dict[str, set] = {tactic["id"]: set() for tactic in TACTICS}
    for tid, tmap in tactic_mapping.items():
        for ta_id in tmap.get("tactic_ids") or []:
            if ta_id in tactic_universe:
                tactic_universe[ta_id].add(tid)

    techniques_by_id = {t["technique"]: t for t in techniques}

    tactic_rows: List[Dict[str, Any]] = []
    for tactic in TACTICS:
        tactic_id = tactic["id"]
        members = tactic_universe.get(tactic_id, set())
        observed_members = [techniques_by_id[m] for m in members if m in techniques_by_id]
        member_techniques = sorted(members)
        gte3 = sum(1 for t in observed_members if int(t["score"]) >= 3)
        gte4 = sum(1 for t in observed_members if int(t["score"]) >= 4)
        gte5 = sum(1 for t in observed_members if int(t["score"]) >= 5)
        tactic_rows.append(
            {
                "tactic_id": tactic_id,
                "tactic_name": tactic["name"],
                "technique_count": len(member_techniques),
                "observed_count": len(observed_members),
                "score_gte3_count": gte3,
                "score_gte4_count": gte4,
                "score_s5_count": gte5,
                "techniques": member_techniques,
            }
        )

    priority_gaps = [
        {
            "technique": row["technique"],
            "name": row["technique"],
            "score": int(row["score"]),
            "status": "partial" if int(row["score"]) >= 3 else "missing",
        }
        for row in techniques
        if int(row["score"]) >= 3 and int(row["score"]) < 5
    ]
    priority_gaps.sort(key=lambda g: (g["score"], g["technique"]), reverse=True)
    priority_gaps = priority_gaps[:50]

    result = {
        "techniques": techniques,
        "tactics": tactic_rows,
        "priority_gaps": priority_gaps,
        "implemented_techniques": sum(1 for t in techniques if t["implemented"]),
        "operational_observed_techniques": operational_observed,
        "covered_score_gte2": covered_gte2,
        "covered_score_gte3": covered_gte3,
        "covered_score_gte4": covered_gte4,
        "covered_score_gte5": covered_gte5,
        "coverage_percent_gte2": round(covered_gte2 / enterprise_total * 100, 2) if enterprise_total else 0.0,
        "coverage_percent_gte3": round(covered_gte3 / enterprise_total * 100, 2) if enterprise_total else 0.0,
        "coverage_percent_gte4": round(covered_gte4 / enterprise_total * 100, 2) if enterprise_total else 0.0,
        "coverage_percent_gte5": round(covered_gte5 / enterprise_total * 100, 2) if enterprise_total else 0.0,
        "operational_coverage_percent": round(operational_observed / enterprise_total * 100, 2) if enterprise_total else 0.0,
        "enterprise_technique_total": enterprise_total,
        "enterprise_parent_total": enterprise_parent_total,
        "roadmap_target_techniques": roadmap_total,
        "roadmap_coverage_percent_gte3": round(covered_gte3 / roadmap_total * 100, 2) if roadmap_total else 0.0,
        "roadmap_coverage_percent_gte2": round(covered_gte2 / roadmap_total * 100, 2) if roadmap_total else 0.0,
        "roadmap_referenced_percent": round(total / roadmap_total * 100, 2) if roadmap_total else 0.0,
        "enterprise_covered_parent_techniques_gte3": covered_parent_gte3,
        "enterprise_covered_parent_techniques_gte4": covered_parent_gte4,
        "enterprise_covered_parent_techniques_gte5": covered_parent_gte5,
        "enterprise_parent_coverage_percent_gte3": round(covered_parent_gte3 / enterprise_parent_total * 100, 2) if enterprise_parent_total else 0.0,
        "enterprise_parent_coverage_percent_gte4": round(covered_parent_gte4 / enterprise_parent_total * 100, 2) if enterprise_parent_total else 0.0,
        "enterprise_parent_coverage_percent_gte5": round(covered_parent_gte5 / enterprise_parent_total * 100, 2) if enterprise_parent_total else 0.0,
        "gap_to_full_catalog_gte3": max(0, enterprise_total - covered_gte3),
        "gap_to_full_catalog_gte4": max(0, enterprise_total - covered_gte4),
        "gap_to_full_catalog_gte5": max(0, enterprise_total - covered_gte5),
        "gap_to_full_parent_gte3": max(0, enterprise_parent_total - covered_parent_gte3),
        "gap_to_full_parent_gte4": max(0, enterprise_parent_total - covered_parent_gte4),
        "gap_to_full_parent_gte5": max(0, enterprise_parent_total - covered_parent_gte5),
        "tvr_validated_count": len(tvr_index),
        "tvr_s5_count": covered_gte5,
        "tier_breakdown": {"platinum": covered_gte5, "gold": covered_gte4 - covered_gte5, "silver": covered_gte3 - covered_gte4, "bronze": covered_gte2 - covered_gte3, "none": total - covered_gte2},
        "telemetry_summary": unified.get("telemetry_summary") or {},
        "scoring_pass_trace": unified.get("scoring_pass_trace") or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "evidence_bundle_tvr+sigma_engine",
        "catalog_source": catalog_totals.get("catalog_path"),
    }

    _coverage_cache = result
    _coverage_cache_ts = now
    return result


@router.get("/coverage")
async def mitre_coverage(
    refresh: bool = Query(False),
    profile: str = Query("default"),
    current_user: dict = Depends(get_current_user),
):
    return _build_coverage_response(force_refresh=refresh)


@router.get("/tactics")
async def mitre_tactics(current_user: dict = Depends(get_current_user)):
    return {"tactics": TACTICS, "count": len(TACTICS)}


@router.get("/techniques")
async def mitre_techniques(
    tactic: str = Query("", max_length=10),
    current_user: dict = Depends(get_current_user),
):
    coverage = _build_coverage_response()
    techniques = coverage.get("techniques") or []
    if tactic:
        target = tactic.upper()
        techniques = [
            t for t in techniques
            if target in (t.get("tactic_ids") or t.get("tactics") or [])
            or target == str(t.get("tactic") or "").upper()
        ]
    return {"count": len(techniques), "techniques": techniques}


@router.get("/techniques/{technique_id}/evidence")
async def mitre_technique_evidence(
    technique_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return the full multi-source telemetry trail collected for one technique.

    Reads ARDA kernel-prevention records, Falco/Suricata/Zeek/Deception/Osquery
    detections, sigma matches, integration evidence, telemetry harvests, and the
    honest TVR classification override."""
    detail = _load_per_technique_evidence(technique_id)
    if not detail.get("technique_id"):
        raise HTTPException(status_code=400, detail="invalid technique id")

    coverage = _build_coverage_response()
    summary = next(
        (t for t in coverage.get("techniques") or [] if t.get("technique") == detail["technique_id"]),
        None,
    )
    detail["summary"] = summary or {}
    return detail
