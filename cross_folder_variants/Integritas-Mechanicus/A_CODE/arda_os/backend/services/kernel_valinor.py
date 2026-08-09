import logging
import time
from typing import Any

from backend.valinor.runtime_hooks import get_valinor_runtime
from backend.valinor.taniquetil_core import ResonanceEvent

logger = logging.getLogger(__name__)

# Attempt to load the true kernel bridge (Linux eBPF)
# If running on Windows/Mac development environments, we fallback gracefully.
try:
    from bcc import BPF
    KERNEL_MODE_AVAILABLE = True
except ImportError:
    KERNEL_MODE_AVAILABLE = False
    logger.warning("BCC/eBPF not found. Valinor Descent will run in Simulation Mode.")


# ✦ The BPF Program: Valinor Kernel Hooks
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

// Struct to pass event data to userspace
struct data_t {
    u32 event_type; // 0 = execve, 1 = fork, 2 = connect
    u32 pid;
    u32 child_pid;  // used only for fork
    u64 ts;
    char comm[TASK_COMM_LEN];
};

BPF_PERF_OUTPUT(valinor_events);

// ✦ 1. Valmar: Execve Guard
int syscall_execve(struct pt_regs *ctx) {
    struct data_t data = {};
    
    data.event_type = 0;
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.ts = bpf_ktime_get_ns();
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    valinor_events.perf_submit(ctx, &data, sizeof(data));
    return 0; 
}

// ✦ 2. Tirion: Lineage Guard (Fork)
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

// ✦ 3. Alqualondë: Socket/Connect Guard
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
    """
    The True Descent.
    Maps physical OS processes (PIDs) to Valinor Entity IDs and enforces
    Resonant Dominance at Ring-0.
    """
    def __init__(self):
        self.valinor = get_valinor_runtime()
        self.bpf: Any = None
        self.running = False

    def kindle_kernel_light(self):
        """Attaches the Calaquendi (The Eyes of Manwë) to the actual Linux Kernel."""
        if not KERNEL_MODE_AVAILABLE:
            logger.info("Valinor Descent: Simulated Girdle of Melian (Substrate) active.")
            return

        logger.info("Valinor Descent: Compiling eBPF Hooks (The Eyes of Manwë)...")
        self.bpf = BPF(text=bpf_program)
        
        # Attach Valmar (Execve)
        syscall_execve_fn = self.bpf.get_syscall_fnname("execve")
        self.bpf.attach_kprobe(event=syscall_execve_fn, fn_name="syscall_execve")
        logger.info(f"Valmar (The Eye of Execve) attached to {syscall_execve_fn}")
        
        # Attach Alqualondë (Connect)
        syscall_connect_fn = self.bpf.get_syscall_fnname("connect")
        self.bpf.attach_kprobe(event=syscall_connect_fn, fn_name="syscall_connect")
        logger.info(f"Alqualondë (The Eye of Connection) attached to {syscall_connect_fn}")
        
        # Tirion attaches implicitly via TRACEPOINT_PROBE (The Eye of Lineage)
        logger.info("Tirion (The Eye of Lineage) attached to sched:sched_process_fork")
        
        self.running = True
        
        # Setup the perf buffer callback
        self.bpf["valinor_events"].open_perf_buffer(self._handle_valinor_event)

    def _handle_valinor_event(self, cpu, data, size):
        """Bridging the eBPF event into Taniquetil's Unified Decision Matrix."""
        event = self.bpf["valinor_events"].event(data)
        
        entity_id = f"pid:{event.pid}"
        target_name = event.comm.decode('utf-8', 'replace')

        # ✦ 1. Valmar Execve Event (Syscall)
        if event.event_type == 0:
            resonance_event = ResonanceEvent(
                entity_id=entity_id,
                action_type="syscall",
                target="execve",
                metadata={"comm": target_name}
            )
            decision = self.valinor.taniquetil.evaluate(resonance_event)
            
            if not decision["allowed"]:
                state = self.valinor.bridge.get_state(entity_id).constitutional_state
                # Gurthang's Severance: Kill ONLY if fundamentally fractured
                if state in ["muted", "fallen"]:
                     logger.critical(f"KERNEL VALINOR: Execve DENIED & SEVERED for {entity_id} ({target_name}). State: {state.upper()}.")
                     self._gurthang_severance(event.pid)
                else:
                     logger.warning(f"KERNEL VALINOR: Execve DENIED for {entity_id} ({target_name}) but state [{state.upper()}] spares it from Gurthang.")
            else:
                logger.debug(f"KERNEL VALINOR: Execve ALLOWED for {entity_id} ({target_name}). Modifiers: {decision['modifiers']}")

        # ✦ 2. Tirion Fork Event (Spawn)
        elif event.event_type == 1:
            child_id = f"pid:{event.child_pid}"
            resonance_event = ResonanceEvent(
                entity_id=entity_id,
                action_type="spawn",
                metadata={"child_id": child_id, "node_id": "localhost", "comm": target_name}
            )
            decision = self.valinor.taniquetil.evaluate(resonance_event)
            if not decision["allowed"]:
                 state = self.valinor.bridge.get_state(entity_id).constitutional_state
                 if state in ["muted", "fallen"]:
                      logger.critical(f"KERNEL VALINOR: Spawn DENIED & SEVERED for child {child_id} from {entity_id}. Lineage is broken.")
                      self._gurthang_severance(event.child_pid)
                 else:
                      logger.warning(f"KERNEL VALINOR: Spawn Denied for parent {entity_id}. State [{state.upper()}] logs but does not sever.")
            else:
                 logger.debug(f"KERNEL VALINOR: Spawn registered. {child_id} inherits state.")

        # ✦ 3. Alqualondë Connect Event (Flow)
        elif event.event_type == 2:
            resonance_event = ResonanceEvent(
                entity_id=entity_id,
                action_type="socket",
                metadata={"comm": target_name}
            )
            decision = self.valinor.taniquetil.evaluate(resonance_event)
            if not decision["allowed"]:
                 state = self.valinor.bridge.get_state(entity_id).constitutional_state
                 if state in ["muted", "fallen"]:
                      logger.critical(f"KERNEL VALINOR: Connect intent DENIED & SEVERED for {entity_id}. Flow is forbidden.")
                      self._gurthang_severance(event.pid)
                 else:
                      logger.warning(f"KERNEL VALINOR: Connect intent DENIED for {entity_id} ({target_name}). State [{state.upper()}] throttled but spared.")
            else:
                 logger.info(f"KERNEL VALINOR: Connect ALLOWED for {entity_id} ({target_name}).")

    def _gurthang_severance(self, pid: int):
        """Executes Gurthang's Severance (Physical Termination in Ring-3)."""
        try:
            import os, signal
            os.kill(pid, signal.SIGKILL)
            logger.info(f"Gurthang: PID {pid} destroyed physically. Darkness extinguished.")
        except Exception as e:
            logger.error(f"Failed to execute severance on {pid}: {e}")

    def watch(self):
        """Blocking loop to listen to kernel events."""
        if not self.running or not KERNEL_MODE_AVAILABLE:
            logger.info("Valinor Descent: Watch mode bypassed (Simulation active).")
            return
            
        logger.info("Taniquetil is now watching the physical substrate. (Ctrl+C to stop)")
        try:
            while True:
                self.bpf.perf_buffer_poll()
                time.sleep(0.01)
        except KeyboardInterrupt:
            logger.info("Valinor Descent Detached.")
