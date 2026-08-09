from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

try:
    from backend.arda.ainur.verdicts import ChoirVerdict
    from backend.arda.ainur.dissonance import ResonanceMapper
except Exception:
    from backend.services.ainur.verdicts import ChoirVerdict  # type: ignore
    from backend.services.ainur.dissonance import ResonanceMapper  # type: ignore

@dataclass
class ProjectionSubject:
    subject_id: str
    node_id: str
    parent_id: Optional[str] = None
    pid: Optional[int] = None


def get_projection_valinor_runtime():
    try:
        from backend.valinor.runtime_hooks import get_valinor_runtime
    except Exception:
        from backend.services.runtime_hooks import get_valinor_runtime  # type: ignore
    return get_valinor_runtime()


def get_projection_arda_fabric():
    from backend.services.arda_fabric import get_arda_fabric
    return get_arda_fabric()


def get_projection_earendil_flow():
    from backend.services.earendil_flow import get_earendil_flow
    return get_earendil_flow()


def _resolve_projection_subject(payload: Any) -> Tuple[str, str]:
    subject_id = getattr(payload, "subject_id", None) or getattr(payload, "entity_id", None)
    node_id = getattr(payload, "node_id", None) or subject_id
    subject_id = subject_id or node_id or "local-substrate"
    node_id = node_id or subject_id
    return str(subject_id), str(node_id)


def _extract_identity_anchors_from_verdict(verdict: ChoirVerdict) -> Tuple[Optional[str], Optional[str]]:
    workload_hash = None
    executable_path = None
    for ainur_verdict in verdict.ainur:
        for ev in ainur_verdict.evidence or []:
            try:
                payload = getattr(ev, "evidence", None) or {}
                if isinstance(payload, dict):
                    if not workload_hash and payload.get("workload_hash"):
                        workload_hash = payload.get("workload_hash")
                    if not executable_path and payload.get("executable_path"):
                        executable_path = payload.get("executable_path")
            except Exception:
                continue

        if workload_hash and executable_path:
            break
    return workload_hash, executable_path


def _extract_identity_anchors_from_advisory(advisory: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    command = advisory.get("command")
    target_domain = advisory.get("harmonic_observation", {}).get("event", {}).get("target_domain")
    executable_path = command if isinstance(command, str) and command.startswith("/") else None
    if executable_path is None and isinstance(target_domain, str) and target_domain.startswith("/"):
        executable_path = target_domain
    workload_hash = None
    provenance = advisory.get("provenance_attestation") or {}
    payload = provenance.get("payload") if isinstance(provenance, dict) else None
    if isinstance(payload, dict):
        workload_hash = payload.get("artifact_digest")
    return workload_hash, executable_path


async def _apply_projection(
    *,
    subject_id: str,
    node_id: str,
    state: str,
    reason: str,
    workload_hash: Optional[str],
    executable_path: Optional[str],
    epoch: Optional[str],
    event_type: str,
) -> Any:
    subject_amplitude = ResonanceMapper.from_choir_state(subject_id, state, reason=reason)

    valinor = get_projection_valinor_runtime()
    valinor.bridge.update_state(subject_id, subject_amplitude)

    node_amplitude = subject_amplitude
    if node_id != subject_id:
        node_amplitude = ResonanceMapper.from_choir_state(node_id, state, reason=reason)
        valinor.bridge.update_state(node_id, node_amplitude)

    fabric = get_projection_arda_fabric()
    fabric.ensure_subject(node_id, workload_hash=workload_hash, executable_path=executable_path)
    fabric.update_resonance_amplitude(node_id, node_amplitude)

    flow = get_projection_earendil_flow()
    await flow.shine_light(subject_id, subject_amplitude, source_reason=reason)
    if node_id != subject_id:
        await flow.shine_light(node_id, node_amplitude, source_reason=f"{reason} (Node Scope)")

    if hasattr(valinor, "taniquetil") and hasattr(valinor.taniquetil, "mandos") and valinor.taniquetil.mandos:
        valinor.taniquetil.mandos.record_event(
            entity_id=subject_id,
            event_type=event_type,
            state=subject_amplitude.constitutional_state,
            reason=reason,
            epoch=epoch,
        )

    return subject_amplitude

def canonical_runtime_state(verdict: ChoirVerdict) -> str:
    """Translates choir verdict labels into canonical runtime dissonance states."""
    if verdict.heralding_allowed or verdict.overall_state == "heralded":
        return "harmonic"
    if verdict.overall_state == "withheld":
        return "muted"
    if verdict.overall_state in {"vetoed", "fallen", "false", "dark", "voided"}:
        return "fallen"
    if verdict.overall_state in {"strained", "dimmed", "troubled"}:
        return "strained"
    if verdict.overall_state in {"fractured", "stalled", "dissonant"}:
        return "dissonant"
    return "strained"


def canonical_runtime_state_from_advisory(advisory: Dict[str, Any]) -> str:
    state = str(advisory.get("canonical_runtime_state") or "").strip().lower()
    if state in {"harmonic", "muted", "fallen", "strained", "dissonant"}:
        return state
    action = str(advisory.get("action") or "").strip().upper()
    recommendation = str(advisory.get("overall_recommendation") or "").strip().upper()
    lane = str(advisory.get("lane") or "").strip()
    if action == "DISSONANCE_VETO":
        return "fallen"
    if recommendation == "HARMONIC" and lane == "Shire":
        return "harmonic"
    if recommendation == "HARMONIC":
        return "strained"
    return "muted"

async def project_choir_truth(verdict: ChoirVerdict):
    """
    Every choir sweep must end in this canonical projection step.
    Bridges Choir truth to Valinor LightBridge, Arda Fabric, and Eärendil Flow.
    """
    subject_id, node_id = _resolve_projection_subject(verdict)
    state = canonical_runtime_state(verdict)
    reason = verdict.reasons[0] if verdict.reasons else "Choir projection"
    workload_hash, executable_path = _extract_identity_anchors_from_verdict(verdict)
    return await _apply_projection(
        subject_id=subject_id,
        node_id=node_id,
        state=state,
        reason=reason,
        workload_hash=workload_hash,
        executable_path=executable_path,
        epoch=getattr(verdict, "epoch", None),
        event_type="choir_projection",
    )


async def project_council_advisory(advisory: Dict[str, Any]) -> Any:
    """
    Projects richer Ainur council output directly into Valinor, Arda Fabric,
    and Eärendil Flow without requiring conversion into a ChoirVerdict first.
    """
    subject_id = str(advisory.get("principal") or advisory.get("actor") or advisory.get("node_id") or "local-substrate")
    node_id = str(advisory.get("node_id") or subject_id)
    state = canonical_runtime_state_from_advisory(advisory)
    reason = advisory.get("collective_testimony") or advisory.get("overall_recommendation") or "Council projection"
    workload_hash, executable_path = _extract_identity_anchors_from_advisory(advisory)
    return await _apply_projection(
        subject_id=subject_id,
        node_id=node_id,
        state=state,
        reason=str(reason),
        workload_hash=workload_hash,
        executable_path=executable_path,
        epoch=None,
        event_type="council_projection",
    )
