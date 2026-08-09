#!/bin/bash
set -x

echo "=== SUBSTRATE ==="
uname -r
cat /sys/kernel/security/lsm
ls /sys/kernel/btf/vmlinux

echo "=== GENERATE VMLINUX.H ==="
bpftool btf dump file /sys/kernel/btf/vmlinux format c > /tmp/vmlinux.h
echo "vmlinux.h lines: $(wc -l < /tmp/vmlinux.h)"

echo "=== WRITE MINIMAL LSM DENY-ALL ==="
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

echo "=== COMPILE ==="
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
  -I/usr/include/bpf \
  -c /tmp/deny_all.c -o /tmp/deny_all.o 2>&1
echo "COMPILE_RC=$?"

echo "=== INSPECT ==="
bpftool prog show 2>&1 | head -5
file /tmp/deny_all.o

echo "=== LOAD (FULL VERIFIER OUTPUT) ==="
bpftool prog load /tmp/deny_all.o /sys/fs/bpf/arda_deny_all 2>&1
echo "LOAD_RC=$?"

echo "=== IF LOADED, CHECK ==="
bpftool prog show 2>&1 | grep -i lsm
ls -la /sys/fs/bpf/arda_deny_all 2>&1

echo "=== DONE ==="
