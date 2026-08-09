#!/bin/bash
# ARDA OS: True Sovereign Denial via Python ctypes libbpf loader
set -e

echo "=== STEP 1: Generate vmlinux.h ==="
bpftool btf dump file /sys/kernel/btf/vmlinux format c > /tmp/vmlinux.h
echo "vmlinux.h: $(wc -l < /tmp/vmlinux.h) lines"

echo "=== STEP 2: Write BPF program ==="
cat > /tmp/deny_all.c << 'EOF'
#include "/tmp/vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

SEC("lsm/bprm_check_security")
int BPF_PROG(arda_deny_all, struct linux_binprm *bprm, int ret)
{
    return -1;
}

char LICENSE[] SEC("license") = "GPL";
EOF

echo "=== STEP 3: Compile BPF program ==="
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
  -I/usr/include/bpf \
  -c /tmp/deny_all.c -o /tmp/deny_all.o
echo "Compiled OK: $(file /tmp/deny_all.o)"

echo "=== STEP 4: Write Python loader ==="
cat > /tmp/loader.py << 'PYEOF'
#!/usr/bin/env python3
"""
Minimal libbpf loader via ctypes.
Opens deny_all.o, loads it, attaches the LSM program, tests exec, detaches.
"""
import ctypes, ctypes.util, os, subprocess, sys, time

# Load libbpf
libbpf_path = ctypes.util.find_library("bpf")
if not libbpf_path:
    # Try direct path
    for p in ["/usr/lib/x86_64-linux-gnu/libbpf.so.1",
              "/usr/lib/x86_64-linux-gnu/libbpf.so",
              "/usr/lib/libbpf.so.1",
              "/usr/lib/libbpf.so"]:
        if os.path.exists(p):
            libbpf_path = p
            break

if not libbpf_path:
    print("FATAL: Cannot find libbpf.so")
    sys.exit(1)

print(f"[LOADER] Using libbpf: {libbpf_path}")
lib = ctypes.CDLL(libbpf_path)

# Define function signatures
lib.bpf_object__open.restype = ctypes.c_void_p
lib.bpf_object__open.argtypes = [ctypes.c_char_p]

lib.bpf_object__load.restype = ctypes.c_int
lib.bpf_object__load.argtypes = [ctypes.c_void_p]

lib.bpf_object__find_program_by_name.restype = ctypes.c_void_p
lib.bpf_object__find_program_by_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

lib.bpf_program__attach.restype = ctypes.c_void_p
lib.bpf_program__attach.argtypes = [ctypes.c_void_p]

lib.bpf_link__destroy.restype = ctypes.c_int
lib.bpf_link__destroy.argtypes = [ctypes.c_void_p]

lib.bpf_object__close.restype = None
lib.bpf_object__close.argtypes = [ctypes.c_void_p]

# Open
print("[LOADER] Opening /tmp/deny_all.o")
obj = lib.bpf_object__open(b"/tmp/deny_all.o")
if not obj:
    print("FATAL: bpf_object__open failed")
    sys.exit(1)

# Load
print("[LOADER] Loading BPF object into kernel")
err = lib.bpf_object__load(obj)
if err:
    print(f"FATAL: bpf_object__load failed: {err}")
    lib.bpf_object__close(obj)
    sys.exit(1)

# Find program
print("[LOADER] Finding program 'arda_deny_all'")
prog = lib.bpf_object__find_program_by_name(obj, b"arda_deny_all")
if not prog:
    print("FATAL: program not found")
    lib.bpf_object__close(obj)
    sys.exit(1)

# Attach
print("[LOADER] Attaching LSM hook...")
link = lib.bpf_program__attach(prog)
if not link:
    print("FATAL: bpf_program__attach failed")
    lib.bpf_object__close(obj)
    sys.exit(1)

print("[LOADER] *** LSM HOOK ATTACHED — TRUE SOVEREIGN DENIAL ACTIVE ***")
print("[LOADER] All exec() calls should now return -EPERM")
sys.stdout.flush()

# Test: use os.system which calls exec internally
print("[TEST] Attempting: os.system('ls /')")
sys.stdout.flush()
rc = os.system("ls / 2>&1")
print(f"[TEST] os.system returned: {rc}")

# Also try subprocess
print("[TEST] Attempting: subprocess.run(['ls', '/'])")
sys.stdout.flush()
try:
    result = subprocess.run(["ls", "/"], capture_output=True, timeout=3)
    print(f"[TEST] subprocess rc={result.returncode}")
    print(f"[TEST] stdout={result.stdout[:100]}")
    print(f"[TEST] stderr={result.stderr[:100]}")
except PermissionError as e:
    print(f"[TEST] PermissionError: {e}")
    print("[TEST] *** THIS IS THE TRUE SOVEREIGN DENIAL ***")
except OSError as e:
    print(f"[TEST] OSError: {e}")
    print(f"[TEST] errno: {e.errno}")
    if e.errno == 1:  # EPERM
        print("[TEST] *** EPERM CONFIRMED — TRUE SOVEREIGN DENIAL ***")
except Exception as e:
    print(f"[TEST] Exception: {type(e).__name__}: {e}")

# Detach
print("[LOADER] Detaching LSM hook...")
sys.stdout.flush()
lib.bpf_link__destroy(link)
lib.bpf_object__close(obj)
print("[LOADER] Detached. Normal operation restored.")
PYEOF

echo "=== STEP 5: Run Python loader ==="
python3 /tmp/loader.py

echo "=== DONE ==="
