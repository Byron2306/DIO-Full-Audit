from datetime import timezone
#!/usr/bin/env python3
"""
Lane 2 Kernel Enforcement Proof — HONEST VERSION

WHAT THIS PROVES:
  Ring-0 coercive enforcement via kprobe + bpf_send_signal(9)

WHAT THIS DOES NOT PROVE:
  Ring-0 pre-exec denial via LSM hook returning -EPERM

The enforcer returns 0 (allow) from the hook, then sends SIGKILL.
This is "kill-at-kernel-level", NOT "deny-before-manifest".
"""
import os, sys, subprocess
from datetime import datetime

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", flush=True)

def main():
    log("=== ARDA OS: RING-0 COERCIVE ENFORCEMENT PROOF ===")
    log("NOTE: This proves kernel-level KILL, not pre-exec DENIAL")

    BPF_SRC = "/opt/arda/backend/services/bpf/arda_kprobe_enforcer.c"
    if not os.path.exists(BPF_SRC):
        log(f"FATAL: Source missing at {BPF_SRC}")
        return 1

    try:
        from bcc import BPF
        log("Importing BCC... OK")
    except Exception as e:
        log(f"FATAL: Could not import BCC: {e}")
        return 1

    log(f"Loading KPROBE Enforcer from {BPF_SRC}...")
    try:
        b = BPF(src_file=BPF_SRC)
        log("KPROBE Enforcer Loaded (kprobe on security_bprm_check)")
        log("  Mechanism: bpf_send_signal(9) — async SIGKILL")
        log("  Return value: 0 (allow) — NOT -EPERM")
    except Exception as e:
        log(f"KPROBE Load failed: {e}")
        return 1

    # Create test binary
    UNKNOWN_BIN = "/opt/arda/testbins/unknown.sh"
    os.makedirs(os.path.dirname(UNKNOWN_BIN), exist_ok=True)
    with open(UNKNOWN_BIN, "w") as f:
        f.write("#!/bin/sh\necho UNKNOWN_EXEC\n")
    os.chmod(UNKNOWN_BIN, 0o755)

    log(f"Executing test binary: {UNKNOWN_BIN}...")
    try:
        rc = subprocess.call(["/bin/sh", UNKNOWN_BIN])
        log(f"Result: rc={rc}")
        if rc == -9 or rc == 137:
            log("RESULT: Process killed by SIGKILL (rc=137)")
            log("  This proves: kernel CAN enforce on Arda's behalf")
            log("  This does NOT prove: pre-exec denial (-EPERM)")
            log("  Remaining gap: replace SIGKILL with synchronous -EPERM return")
            return 0
        else:
            log("RESULT: Binary was allowed to execute (no enforcement)")
            return 1
    except Exception as e:
        log(f"Execution error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
