import re
from typing import Any, Dict, Iterable, List, Set


ATTACK_TECHNIQUE_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)

# Keep this map intentionally focused to techniques we emit from Celery envelope
# and techniques frequently found in operational payloads.
TECHNIQUE_TO_TACTIC: Dict[str, str] = {
    "T1016": "TA0007",
    "T1049": "TA0007",
    "T1057": "TA0007",
    "T1082": "TA0007",
    "T1195": "TA0001",
    "T1195.002": "TA0001",
    "T1553.006": "TA0005",
}

TASK_BASELINE_TECHNIQUES: Dict[str, List[str]] = {
    # Velociraptor endpoint collection aligns with common discovery telemetry
    # used to detect and investigate discovery techniques.
    "backend.tasks.integrations_tasks.run_velociraptor_task": [
        "T1057",
        "T1082",
        "T1016",
        "T1049",
    ],
}


def _normalize_technique(value: str) -> str:
    return (value or "").strip().upper()


def _extract_techniques(value: Any, out: Set[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        for match in ATTACK_TECHNIQUE_RE.finditer(value):
            normalized = _normalize_technique(match.group(0))
            if normalized:
                out.add(normalized)
        return
    if isinstance(value, dict):
        for inner in value.values():
            _extract_techniques(inner, out)
        return
    if isinstance(value, list):
        for inner in value:
            _extract_techniques(inner, out)
        return


def extract_attack_techniques(value: Any) -> List[str]:
    found: Set[str] = set()
    _extract_techniques(value, found)
    return sorted(found)


def _baseline_techniques(task_name: str) -> List[str]:
    if not task_name:
        return []
    direct = TASK_BASELINE_TECHNIQUES.get(task_name)
    if direct:
        return direct
    for known_name, techniques in TASK_BASELINE_TECHNIQUES.items():
        if task_name.endswith(known_name) or known_name.endswith(task_name):
            return techniques
    return []


def _techniques_to_tactics(techniques: Iterable[str]) -> List[str]:
    tactics: Set[str] = set()
    for technique in techniques:
        norm = _normalize_technique(technique)
        if not norm:
            continue
        mapped = TECHNIQUE_TO_TACTIC.get(norm) or TECHNIQUE_TO_TACTIC.get(norm.split(".")[0])
        if mapped:
            tactics.add(mapped)
    return sorted(tactics)


def build_celery_attack_metadata(
    *,
    task_name: str,
    event_type: str,
    payload: Dict[str, Any] = None,
    explicit_techniques: Iterable[str] = None,
) -> Dict[str, Any]:
    payload = payload or {}
    observed = set(extract_attack_techniques(payload))
    baseline = {_normalize_technique(x) for x in _baseline_techniques(task_name)}
    explicit = {
        _normalize_technique(x)
        for x in (explicit_techniques or [])
        if _normalize_technique(x)
    }
    techniques = sorted(t for t in (observed | baseline | explicit) if t)
    tactics = _techniques_to_tactics(techniques)

    if explicit:
        evidence_kind = "explicit"
    elif observed:
        evidence_kind = "observed"
    elif baseline:
        evidence_kind = "baseline"
    else:
        evidence_kind = "none"

    return {
        "schema": "attack_metadata.v1",
        "task_name": task_name or "unknown",
        "event_type": event_type or "unknown",
        "techniques": techniques,
        "tactics": tactics,
        "evidence_kind": evidence_kind,
        "operational_evidence": bool(techniques),
    }
