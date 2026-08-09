import logging
import os

logger = logging.getLogger(__name__)

try:
    from bcc import BPF
except ImportError:
    BPF = None


class GurthangLSMInterface:
    """
    Native-denial interface for Valinor.

    This remains simulation-backed unless an explicit BPF implementation is
    loaded. That keeps imports safe while preserving the API for enforcement
    callers.
    """

    def __init__(self):
        self.bpf = None
        self.resonance_map: dict[int, int] = {}
        self.is_armed = False
        if BPF and os.uname().sysname == "Linux":
            logger.info("Gurthang LSM: BPF available; native armament remains explicitly gated.")

    def push_doom(self, pid: int, state_level: int) -> None:
        if self.is_armed:
            logger.info("Gurthang LSM: native doom pushed for PID %s [level=%s]", pid, state_level)
            return
        self.resonance_map[pid] = state_level
        logger.debug("Gurthang LSM simulation: doom recorded for PID %s [level=%s]", pid, state_level)

    def clear_doom(self, pid: int) -> None:
        if pid in self.resonance_map:
            del self.resonance_map[pid]
            logger.info("Gurthang LSM: cleared doom for PID %s", pid)


gurthang_armament = GurthangLSMInterface()


def get_gurthang_lsm() -> GurthangLSMInterface:
    return gurthang_armament
