import logging
import os
import signal
from typing import Any, Optional, Dict
from backend.valinor.gurthang_lsm import get_gurthang_lsm
from backend.arda.ainur.dissonance import DissonantStateModel

logger = logging.getLogger(__name__)


def _get_process_name(pid: int) -> Optional[str]:
    """
    Read the process name for a PID.
    Tries /proc/<pid>/comm first (fast, but truncated to 15 chars by the kernel).
    Falls back to the basename of /proc/<pid>/exe for longer names.
    """
    try:
        with open(f"/proc/{pid}/comm") as f:
            comm = f.read().strip()
        # comm is truncated at 15 chars — if it looks truncated, try exe
        if len(comm) == 15:
            try:
                exe = os.readlink(f"/proc/{pid}/exe")
                return os.path.basename(exe)
            except Exception:
                pass
        return comm
    except Exception:
        # Last resort: basename of exe symlink
        try:
            exe = os.readlink(f"/proc/{pid}/exe")
            return os.path.basename(exe)
        except Exception:
            return None

class HouseOfFingolfin:
    """
    House of Fingolfin (The House of Valor).
    Manages the Girdle of Melian (The Shield) and Gurthang's Severance (The Sword).
    This house is responsible for physical, real-time enforcement in the kernel.
    """
    def __init__(self, kernel_bridge=None):
        self.blade = kernel_bridge # Reference to KernelValinor
        
    def draw_shiel(self):
        """Activates the Girdle of Melian (Physical substrate isolation)."""
        logger.info("Fingolfin: Drawing the Girdle of Melian (Substrate Shield).")
        # Logic to enable cgroups or LKM filters for isolation
        pass

    def sever_process(self, pid: int, budget: DissonantStateModel, reason: str = "Resonance Failure"):
        """Executes Gurthang's Severance (LSM + SIGKILL) against a pid."""
        # Whitelist check — never kill trusted processes regardless of verdict
        proc_name = _get_process_name(pid)
        if proc_name:
            try:
                from unified_agent.core.agent import is_trusted_ai_process
                trusted, trust_reason = is_trusted_ai_process(proc_name)
                if trusted:
                    logger.warning(
                        f"Fingolfin: Severance ABORTED for PID {pid} ({proc_name}) — whitelisted: {trust_reason}"
                    )
                    return False
            except Exception as e:
                logger.error(f"Fingolfin: Whitelist check failed for PID {pid}: {e}. Aborting severance as safe default.")
                return False

        logger.critical(f"Fingolfin: {reason} Detected. Sealing darkness in PID {pid} ({proc_name}).")

        # 1. Push to Native LSM Accelerator (Phase XIII: The Great Armament)
        lsm = get_gurthang_lsm()
        if budget.constitutional_state == "muted":
             lsm.push_doom(pid, 1) # Exec Deny
        elif budget.constitutional_state == "fallen":
             lsm.push_doom(pid, 2) # Total Severance

        # 2. Traditional Termination (Tulkas fallback)
        try:
             os.kill(pid, signal.SIGKILL)
             logger.warning(f"Fingolfin: Severance complete for PID {pid}. Entity destroyed.")
             return True
        except Exception as e:
             logger.error(f"Fingolfin: Severance FAILED for PID {pid}: {e}")
             return False

    def check_boundary_integrity(self) -> bool:
        """Verifies if the Girdle is holding by checking for illegal cross-covenant syscalls."""
        # Simulated check for now
        return True

# Instance of the House
fingolfin = HouseOfFingolfin()

def get_house_fingolfin():
    return fingolfin
