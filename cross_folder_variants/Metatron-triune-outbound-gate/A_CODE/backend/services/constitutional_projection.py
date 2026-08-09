from dataclasses import dataclass
from typing import Optional, Dict, Any

from backend.arda.ainur.verdicts import ChoirVerdict
from backend.arda.ainur.dissonance import ResonanceMapper
from backend.valinor.runtime_hooks import get_valinor_runtime
from backend.services.arda_fabric import get_arda_fabric
from backend.services.earendil_flow import get_earendil_flow

@dataclass
class ProjectionSubject:
    subject_id: str
    node_id: str
    parent_id: Optional[str] = None
    pid: Optional[int] = None

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

async def project_choir_truth(verdict: ChoirVerdict):
    """
    Every choir sweep must end in this canonical projection step.
    Bridges Choir truth to Valinor LightBridge, Arda Fabric, and Eärendil Flow.
    """
    subject_id = verdict.subject_id or verdict.node_id or "local-substrate"
    node_id = verdict.node_id or subject_id

    state = canonical_runtime_state(verdict)
    reason = verdict.reasons[0] if verdict.reasons else "Choir projection"
    
    # Decouple Subject and Node amplitudes (Internal identity must match registry key)
    subject_amplitude = ResonanceMapper.from_choir_state(subject_id, state, reason=reason)
    
    valinor = get_valinor_runtime()
    valinor.bridge.update_state(subject_id, subject_amplitude)

    node_amplitude = subject_amplitude
    if node_id != subject_id:
        node_amplitude = ResonanceMapper.from_choir_state(node_id, state, reason=reason)
        valinor.bridge.update_state(node_id, node_amplitude)

    fabric = get_arda_fabric()
    
    # Phase C: Extract workload identity anchors from evidence if available
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

    fabric.ensure_subject(node_id, workload_hash=workload_hash, executable_path=executable_path)
    fabric.update_resonance_amplitude(node_id, node_amplitude)

    # Propagate dual-scoped truth across the fabric
    flow = get_earendil_flow()
    await flow.shine_light(subject_id, subject_amplitude, source_reason="Choir projection")
    if node_id != subject_id:
        await flow.shine_light(node_id, node_amplitude, source_reason="Choir projection (Node Scope)")

    # Record in Mandos Ledger if available
    if hasattr(valinor, "taniquetil") and hasattr(valinor.taniquetil, "mandos") and valinor.taniquetil.mandos:
        valinor.taniquetil.mandos.record_event(
            entity_id=subject_id,
            event_type="choir_projection",
            state=subject_amplitude.constitutional_state,
            reason=reason,
            epoch=verdict.epoch,
        )

    return subject_amplitude
