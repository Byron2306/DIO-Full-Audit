import logging
import os
from typing import Any, Dict, List
from enum import Enum
from backend.arda.ainur.verdicts import ChoirVerdict
from backend.services.arda_fabric import get_arda_fabric
from backend.services.earendil_flow import get_earendil_flow
from backend.valinor.noldor.fingolfin import get_house_fingolfin

logger = logging.getLogger(__name__)

class TulkasPosture(str, Enum):
    RESTRAIN = "restrain" # Soft restraint
    THROTTLE = "throttle" # Network/CPU capping
    CONTAIN = "contain" # Hard containment
    PURGE = "purge"   # Scorched recovery
    EXILE = "exile"   # Persistent exclusion

class TulkasExecutor:
    """
    Tulkas — The Executor of Force
    Operationalizes constitutional verdicts through a ladder of force.
    """
    def __init__(self, world_model: Any):
        self.world_model = world_model

    async def execute_enforcement(self, verdict: ChoirVerdict, node_id: str):
        """
        Determines the enforcement posture and executes the ladder of force.
        Applies Resonant Dominance by attenuating the entity's resonance amplitude.
        """
        if verdict.heralding_allowed:
            logger.info(f"Tulkas: Node {node_id} is in harmony. Resetting failure memory.")
            self.world_model.reset_failure_count()
            
            # Restore to full Harmonic amplitude if it was previously degraded
            from backend.arda.ainur.dissonance import ResonanceMapper
            restored_amplitude = ResonanceMapper.from_choir_state(node_id, "harmonic", "Restored to harmony")
            get_arda_fabric().update_resonance_amplitude(node_id, restored_amplitude)
            
            return "harmony"

        # Increment failure memory
        failures = self.world_model.increment_failure_count()
        logger.warning(f"Tulkas: Node {node_id} failed constitutional check. Failure count: {failures}")

        # Phase 22: Active Challenge Injection
        if any("stale" in r.lower() for r in verdict.reasons):
            logger.info(f"Tulkas: Forcing immediate Secret Fire re-forge for node {node_id} due to staleness.")
            # In real system: await secret_fire_forge.issue_challenge(node_id)
        
        # 1. Determine Posture by merging Choir verdict with Mandos memory
        posture = self._determine_posture(verdict, failures, node_id)
        
        # 2. Execute Actuators
        await self._apply_actuators(posture, node_id, verdict)
        
        if posture == TulkasPosture.EXILE:
            # Persistent record of the fallen
            logger.critical(f"Tulkas: Adding {node_id} to the Eternal Fallen Ledger.")
            # self.world_model.mark_exiled(node_id)

        return posture

    def _determine_posture(self, verdict: ChoirVerdict, failures: int, node_id: str) -> TulkasPosture:
        # Pre-check: Consult Mandos for deep constitutional memory
        from backend.valinor.runtime_hooks import get_valinor_runtime
        valinor = get_valinor_runtime()
        if valinor.taniquetil.mandos and valinor.taniquetil.mandos.is_fallen(node_id):
            logger.critical(f"Tulkas: Mandos declares {node_id} FALLEN due to historical wounds. Bypassing ladder directly to EXILE.")
            return TulkasPosture.EXILE
        
        # 1. Critical Reality/Voice Breaches (Phase VII)
        is_sovereign_dissonance = any(s in r for r in verdict.reasons for s in ["Sovereign Dissonance", "Voice Mismatch", "Lineage Veto"])
        is_fire_breach = any(s in r for r in verdict.reasons for s in ["Secret Fire", "Witnessing failed"])
        
        if is_sovereign_dissonance:
            # Fundamental timeline/linage failure: The witness answered a different reality.
            logger.error(f"Tulkas: SOVEREIGN DISSONANCE detected! Witness lineage is severed.")
            if failures > 0:
                 return TulkasPosture.PURGE
            return TulkasPosture.CONTAIN

        if is_fire_breach:
            logger.error(f"Tulkas: Secret Fire breach detected! Fundamental reality failure.")
            if failures > 1:
                return TulkasPosture.PURGE
            return TulkasPosture.CONTAIN

        # Phase 22: Precision Ladder
        if verdict.overall_state == "vetoed":
            if failures > 5: return TulkasPosture.EXILE
            if failures > 3: return TulkasPosture.PURGE
            return TulkasPosture.CONTAIN
            
        if verdict.overall_state == "withheld":
            if failures > 4: return TulkasPosture.CONTAIN
            if failures > 2: return TulkasPosture.THROTTLE
            return TulkasPosture.RESTRAIN
            
        return TulkasPosture.RESTRAIN

    async def _apply_actuators(self, posture: TulkasPosture, node_id: str, verdict: ChoirVerdict):
        logger.info(f"Tulkas: Engaging {posture.upper()} posture for node {node_id}")

        # 1. Attenuate Resonance Amplitude Globally (Resonant Dominance)
        from backend.arda.ainur.dissonance import ResonanceMapper
        amplitude = ResonanceMapper.from_choir_state(node_id, verdict.overall_state, reason=verdict.reasons[0] if verdict.reasons else "Tulkas enforcement")
        
        fabric = get_arda_fabric()
        fabric.update_resonance_amplitude(node_id, amplitude)
        
        # Phase VII: Eärendil Flow (Global Truth Propagation)
        try:
             earendil = get_earendil_flow()
             await earendil.shine_light(node_id, amplitude, source_reason="Tulkas Enforcement")
        except Exception as e:
             logger.error(f"Tulkas: Failed to shine Eärendil's light: {e}")

        # 1.5 Constitutional → Kernel bridge (Friend vs Foe)
        # Synchronizes choir verdict into the ring-0 harmony map so ARDA LSM
        # can distinguish friend from foe at execve() without a separate config step.
        # Disable with ARDA_CONSTITUTIONAL_KERNEL_BRIDGE=0 only if explicitly needed.
        if os.environ.get("ARDA_CONSTITUTIONAL_KERNEL_BRIDGE", "1").lower() in ("1", "true", "yes"):
            try:
                fabric = get_arda_fabric()
                peer = getattr(fabric, "known_peers", {}).get(node_id) or {}
                executable_path = peer.get("executable_path")
                if executable_path:
                    from backend.services.os_enforcement_service import get_os_enforcement_service
                    svc = get_os_enforcement_service()
                    should_trust = bool(verdict.heralding_allowed)
                    # Only trust on harmonic; distrust only on strong postures.
                    if should_trust:
                        svc.update_workload_harmony(executable_path=executable_path, is_harmonic=True)
                        logger.info(f"Tulkas→Kernel: TRUST {node_id} executable={executable_path}")
                    elif posture in (TulkasPosture.CONTAIN, TulkasPosture.PURGE, TulkasPosture.EXILE):
                        svc.update_workload_harmony(executable_path=executable_path, is_harmonic=False)
                        logger.warning(f"Tulkas→Kernel: DISTRUST {node_id} executable={executable_path}")
            except Exception as e:
                logger.error(f"Tulkas→Kernel: Failed to sync workload harmony: {e}")

        # 2. Apply explicit physical/kernel actuators if necessary
        if posture == TulkasPosture.RESTRAIN:
            await self._actuate_restrain(node_id, amplitude)
        elif posture == TulkasPosture.THROTTLE:
            await self._actuate_throttle(node_id, amplitude)
        elif posture == TulkasPosture.CONTAIN:
            await self._actuate_contain(node_id, amplitude)
        elif posture == TulkasPosture.PURGE:
            await self._actuate_purge(node_id, amplitude)
        elif posture == TulkasPosture.EXILE:
            await self._actuate_exile(node_id, amplitude)

    async def _actuate_restrain(self, node_id: str, amplitude: Any):
        logger.warning(f"Tulkas [RESTRAIN]: {node_id} demoted to '{amplitude.exec_rights}'. Quorum weight: {amplitude.quorum_weight}.")

    async def _actuate_throttle(self, node_id: str, amplitude: Any):
        logger.warning(f"Tulkas [THROTTLE]: Capping resource availability for {node_id}. Network trust: {amplitude.network_trust}.")
        # Use cgroups/tc for real implementation

    async def _actuate_contain(self, node_id: str, amplitude: Any):
        logger.warning(f"Tulkas [CONTAIN]: Revoking protected tokens for {node_id}. Syscall scope limited to '{amplitude.syscall_scope}'.")

    async def _actuate_purge(self, node_id: str, budget: Any):
        logger.error(f"Tulkas [PURGE]: Scorched recovery engaged. Muting node {node_id}.")
        fingolfin = get_house_fingolfin()
        pid = get_arda_fabric().get_pid_for_node(node_id)
        if pid:
            # Close the network gate at ring-0 before killing — prevents last-gasp exfil.
            try:
                from backend.services.os_enforcement_service import get_os_enforcement_service
                get_os_enforcement_service().deny_network_for_pid(pid, True)
            except Exception as e:
                logger.error(f"Tulkas→Kernel: network deny failed for PID {pid}: {e}")
            fingolfin.sever_process(pid, budget, reason="Tulkas Sovereign Purge")

    async def _actuate_exile(self, node_id: str, budget: Any):
        logger.critical(f"Tulkas [EXILE]: Node {node_id} is permanently severed (Fallen).")
        fingolfin = get_house_fingolfin()
        pid = get_arda_fabric().get_pid_for_node(node_id)
        if pid:
            # Close network gate at ring-0 before severance — permanent exile means
            # no outbound reach even if the process somehow survives SIGKILL.
            try:
                from backend.services.os_enforcement_service import get_os_enforcement_service
                get_os_enforcement_service().deny_network_for_pid(pid, True)
            except Exception as e:
                logger.error(f"Tulkas→Kernel: network deny failed for PID {pid}: {e}")
            fingolfin.sever_process(pid, budget, reason="Tulkas Sovereign Exile")
