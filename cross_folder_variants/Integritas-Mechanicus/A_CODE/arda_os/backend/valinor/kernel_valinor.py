import logging
import signal
import time
from typing import Any

from backend.valinor.runtime_hooks import get_valinor_runtime
from backend.valinor.taniquetil_core import ResonanceEvent

logger = logging.getLogger(__name__)

try:
    from bcc import BPF

    KERNEL_MODE_AVAILABLE = True
except ImportError:
    BPF = None
    KERNEL_MODE_AVAILABLE = False


bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

struct data_t {
    u32 event_type;
    u32 pid;
    u32 child_pid;
    u64 ts;
    char comm[TASK_COMM_LEN];
};

BPF_PERF_OUTPUT(valinor_events);

int syscall_execve(struct pt_regs *ctx) {
    struct data_t data = {};
    data.event_type = 0;
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.ts = bpf_ktime_get_ns();
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    valinor_events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

TRACEPOINT_PROBE(sched, sched_process_fork) {
    struct data_t data = {};
    data.event_type = 1;
    data.pid = args->parent_pid;
    data.child_pid = args->child_pid;
    data.ts = bpf_ktime_get_ns();
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    valinor_events.perf_submit(args, &data, sizeof(data));
    return 0;
}

int syscall_connect(struct pt_regs *ctx) {
    struct data_t data = {};
    data.event_type = 2;
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.ts = bpf_ktime_get_ns();
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    valinor_events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}
"""


class KernelValinor:
    """Optional BCC bridge from kernel events into the Valinor runtime."""

    def __init__(self):
        self.valinor = get_valinor_runtime()
        self.bpf: Any = None
        self.running = False

    def kindle_kernel_light(self) -> bool:
        if not KERNEL_MODE_AVAILABLE:
            logger.info("Valinor Descent: BCC unavailable; simulation mode active.")
            return False

        self.bpf = BPF(text=bpf_program)
        self.bpf.attach_kprobe(event=self.bpf.get_syscall_fnname("execve"), fn_name="syscall_execve")
        self.bpf.attach_kprobe(event=self.bpf.get_syscall_fnname("connect"), fn_name="syscall_connect")
        self.bpf["valinor_events"].open_perf_buffer(self._handle_valinor_event)
        self.running = True
        return True

    def _handle_valinor_event(self, cpu, data, size) -> None:
        event = self.bpf["valinor_events"].event(data)
        entity_id = f"pid:{event.pid}"
        target_name = event.comm.decode("utf-8", "replace")

        if event.event_type == 0:
            decision = self.valinor.taniquetil.evaluate(
                ResonanceEvent(
                    entity_id=entity_id,
                    action_type="syscall",
                    target="execve",
                    metadata={"comm": target_name},
                )
            )
            if not decision["allowed"]:
                self._maybe_sever(event.pid, entity_id, "execve")
        elif event.event_type == 1:
            child_id = f"pid:{event.child_pid}"
            decision = self.valinor.taniquetil.evaluate(
                ResonanceEvent(
                    entity_id=entity_id,
                    action_type="spawn",
                    metadata={"child_id": child_id, "node_id": "localhost", "comm": target_name},
                )
            )
            if not decision["allowed"]:
                self._maybe_sever(event.child_pid, child_id, "spawn")
        elif event.event_type == 2:
            decision = self.valinor.taniquetil.evaluate(
                ResonanceEvent(entity_id=entity_id, action_type="socket", metadata={"comm": target_name})
            )
            if not decision["allowed"]:
                self._maybe_sever(event.pid, entity_id, "connect")

    def _maybe_sever(self, pid: int, entity_id: str, action: str) -> None:
        state = self.valinor.bridge.get_state(entity_id).constitutional_state
        if state in ["muted", "fallen"]:
            logger.critical("KernelValinor: %s denied and severed for %s", action, entity_id)
            self._gurthang_severance(pid)
        else:
            logger.warning("KernelValinor: %s denied for %s but state %s spared severance", action, entity_id, state)

    def _gurthang_severance(self, pid: int) -> None:
        try:
            import os

            os.kill(pid, signal.SIGKILL)
        except Exception as exc:
            logger.error("KernelValinor: severance failed for PID %s: %s", pid, exc)

    def watch(self) -> None:
        if not self.running or not KERNEL_MODE_AVAILABLE:
            logger.info("Valinor Descent: watch bypassed; simulation mode active.")
            return
        while True:
            self.bpf.perf_buffer_poll()
            time.sleep(0.01)
