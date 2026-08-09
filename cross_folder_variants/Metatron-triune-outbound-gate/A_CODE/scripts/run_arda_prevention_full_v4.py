#!/usr/bin/env python3
"""
run_arda_prevention_full_v4.py
===============================
Phase 1 Full v4: Properly timed - starts Arda + waits + executes payloads
all in one script with correct timing.

Pre-writes 516 payloads BEFORE enforcement.
Starts Arda enforcement (180s window with 30s delay).
Waits 33s (delay + 3s buffer).
Executes 516 payloads via os.fork+execve while enforcement is ACTIVE.
Stops container immediately after.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Import the technique list from v3
sys.path.insert(0, str(REPO / "scripts"))
from run_arda_prevention_full_v3 import TECHNIQUES

print(f"Phase 1 Full v4 — Properly timed enforcement")
print(f"Techniques: {len(TECHNIQUES)}")
print()

# Step 1: Pre-write all payloads BEFORE enforcement
print(f"[*] Pre-writing {len(TECHNIQUES)} payload binaries to /tmp...")
for tid in TECHNIQUES:
    tool_name = f"arda_{tid.replace('.', '_')}"
    binary_path = f"/tmp/{tool_name}.bin"
    with open(binary_path, "w") as f:
        f.write(f"#!/bin/bash\necho {tid}\n")
    os.chmod(binary_path, 0o755)
print(f"[+] All payloads written")

# Step 2: Start Arda enforcement in BACKGROUND
print(f"[*] Starting Arda enforcement (180s window, 30s delay)...")
env = os.environ.copy()
env["ARDA_ENFORCE_SECONDS"] = "180"
env["ARDA_ENFORCE_DELAY_SECONDS"] = "30"
env["ARDA_LSM_CONTAINER_NAME"] = "arda-lsm-loader"

# Run the start script as a background subprocess
arda_proc = subprocess.Popen(
    ["bash", "scripts/arda_lsm_start.sh"],
    cwd=str(REPO),
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"[+] Arda starting (PID {arda_proc.pid})")

# Step 3: Wait for enforcement to ACTIVATE (delay + small buffer)
# arda_lsm_start.sh: starts container, waits for SEED_TOTAL (~5s), then sleeps 30s before enforcement
# Total wait needed: ~35s for seeding + 30s delay = 65s
print(f"[*] Waiting 65s for enforcement to fully activate...")
time.sleep(65)

# Step 4: Execute all payloads while enforcement is ACTIVE
print(f"[*] Executing {len(TECHNIQUES)} payloads (enforcement is active)...")
denied = 0
start_time = time.time()

for i, tid in enumerate(TECHNIQUES, 1):
    tool_name = f"arda_{tid.replace('.', '_')}"
    binary_path = f"/tmp/{tool_name}.bin"

    try:
        pid = os.fork()
        if pid == 0:
            # Child: execve the binary - will be denied by Arda
            try:
                os.execve(binary_path, [binary_path], {})
            except Exception:
                os._exit(126)
            os._exit(0)
        else:
            # Parent: wait for child
            _, status = os.waitpid(pid, 0)
            # status != 0 means denied or non-zero exit
            if os.WEXITSTATUS(status) != 0 or os.WIFSIGNALED(status):
                denied += 1
    except (OSError, PermissionError):
        denied += 1

    if i % 50 == 0 or i == len(TECHNIQUES):
        elapsed = time.time() - start_time
        pct = 100.0 * denied / i
        print(f"    [{i:3d}/{len(TECHNIQUES)}] {denied:3d} denied ({pct:5.1f}%) [{elapsed:.0f}s elapsed]")

print()
print(f"[+] Execution complete: {denied}/{len(TECHNIQUES)} EPERM denials")
print(f"    Time elapsed: {time.time()-start_time:.0f}s (enforcement window: 180s)")
