import logging
import os
import signal
from typing import Optional

try:
    from backend.arda.ainur.dissonance import DissonantStateModel
except Exception:
    from backend.services.ainur.dissonance import DissonantStateModel  # type: ignore
from backend.valinor.gurthang_lsm import get_gurthang_lsm

logger = logging.getLogger(__name__)


def _get_process_name(pid: int) -> Optional[str]:
    try:
        with open(f"/proc/{pid}/comm", encoding="utf-8") as handle:
            comm = handle.read().strip()
        if len(comm) == 15:
            try:
                return os.path.basename(os.readlink(f"/proc/{pid}/exe"))
            except Exception:
                pass
        return comm
    except Exception:
        try:
            return os.path.basename(os.readlink(f"/proc/{pid}/exe"))
        except Exception:
            return None


class HouseOfFingolfin:
    """Physical enforcement facade for shield and severance actions."""

    def __init__(self, kernel_bridge=None):
        self.blade = kernel_bridge

    def draw_shield(self) -> bool:
        logger.info("Fingolfin: drawing substrate shield.")
        return True

    def draw_shiel(self) -> bool:
        return self.draw_shield()

    def sever_process(self, pid: int, budget: DissonantStateModel, reason: str = "Resonance Failure") -> bool:
        proc_name = _get_process_name(pid)
        if proc_name:
            try:
                from unified_agent.core.agent import is_trusted_ai_process

                trusted, trust_reason = is_trusted_ai_process(proc_name)
                if trusted:
                    logger.warning("Fingolfin: severance aborted for PID %s (%s): %s", pid, proc_name, trust_reason)
                    return False
            except Exception as exc:
                logger.error("Fingolfin: whitelist check failed for PID %s: %s", pid, exc)
                return False

        lsm = get_gurthang_lsm()
        if budget.constitutional_state == "muted":
            lsm.push_doom(pid, 1)
        elif budget.constitutional_state == "fallen":
            lsm.push_doom(pid, 2)

        try:
            os.kill(pid, signal.SIGKILL)
            logger.warning("Fingolfin: severance complete for PID %s (%s): %s", pid, proc_name, reason)
            return True
        except Exception as exc:
            logger.error("Fingolfin: severance failed for PID %s: %s", pid, exc)
            return False

    def check_boundary_integrity(self) -> bool:
        return True


fingolfin = HouseOfFingolfin()


def get_house_fingolfin() -> HouseOfFingolfin:
    return fingolfin
