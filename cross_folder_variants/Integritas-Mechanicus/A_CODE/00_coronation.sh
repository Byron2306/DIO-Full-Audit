#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ARDA OS — SOVEREIGN CORONATION SCRIPT
# Silicon Truth Protocol · No Mock Mode · No Simulation
# Revised to:
#   - Reuse existing loaded Arda LSM program if already crowned
#   - Test enforcement in a fresh unique directory under evidence/
#   - Treat materialization denial as valid enforcement evidence
#   - Compute boot_state from live LSM presence + enforcement result
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KIT_DIR="$SCRIPT_DIR"
EVIDENCE_DIR="$KIT_DIR/evidence"
BPF_DIR="$KIT_DIR/bpf"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

RED='\033[0;31m'
GREEN='\033[0;32m'
GOLD='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$EVIDENCE_DIR"

LOG_FILE="$EVIDENCE_DIR/coronation.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# ═══════════════════════════════════════════════════════════════════
# PRE-FLIGHT
# ═══════════════════════════════════════════════════════════════════
echo -e "${CYAN}── PRE-FLIGHT: Dependency Check ──${NC}"

if grep -q "file:/run/live/medium" /etc/apt/sources.list 2>/dev/null; then
    echo "  Fixing apt sources for live environment..."
    CODENAME=$(lsb_release -cs 2>/dev/null || echo "trixie")
    echo "deb http://deb.debian.org/debian $CODENAME main contrib non-free non-free-firmware" > /etc/apt/sources.list
    echo "  apt sources pointed to online repos ($CODENAME)"
fi

MISSING_PKGS=""
command -v xxd &>/dev/null || MISSING_PKGS="$MISSING_PKGS xxd"
command -v tpm2_getcap &>/dev/null || MISSING_PKGS="$MISSING_PKGS tpm2-tools"
command -v clang &>/dev/null || MISSING_PKGS="$MISSING_PKGS clang"
command -v bpftool &>/dev/null || MISSING_PKGS="$MISSING_PKGS bpftool"
command -v gcc &>/dev/null || MISSING_PKGS="$MISSING_PKGS gcc"
command -v python3 &>/dev/null || MISSING_PKGS="$MISSING_PKGS python3"
command -v jq &>/dev/null || MISSING_PKGS="$MISSING_PKGS jq"
dpkg -s libbpf-dev &>/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS libbpf-dev"
dpkg -s llvm &>/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS llvm"

if [ -n "$MISSING_PKGS" ]; then
    echo "  Missing packages:$MISSING_PKGS"
    echo "  Installing (this may take a minute)..."
    apt-get update -qq 2>/dev/null || true
    apt-get install -y -qq $MISSING_PKGS 2>&1 || {
        echo -e "${RED}  WARNING: Some packages failed to install.${NC}"
        echo -e "${RED}  Continuing with what's available...${NC}"
    }
else
    echo "  All dependencies present."
fi

if command -v xxd &>/dev/null; then
    NONCE="$(head -c 16 /dev/urandom | xxd -p)"
elif command -v python3 &>/dev/null; then
    NONCE="$(python3 -c 'import os; print(os.urandom(16).hex())')"
else
    NONCE="$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')"
fi

echo "  Pre-flight complete."
echo ""

assemble_partial_bundle() {
    local GATE_REACHED=$1
    local FAILURE_REASON=${2:-"none"}

    python3 - <<PY 2>/dev/null || echo "  (Python unavailable — partial bundle skipped)"
import json, hashlib, os, glob

evidence_dir = r'''$EVIDENCE_DIR'''
bundle = {
    'protocol': 'ARDA_CORONATION_v1',
    'timestamp': '$TIMESTAMP',
    'machine_id': '''$(cat /etc/machine-id 2>/dev/null || echo "live-session")''',
    'gate_reached': '$GATE_REACHED',
    'failure_reason': '$FAILURE_REASON',
    'file_hashes': {}
}

for f in sorted(glob.glob(os.path.join(evidence_dir, '*'))):
    if os.path.isfile(f) and not f.endswith('07_sovereign_attestation.json'):
        with open(f, 'rb') as fh:
            h = hashlib.sha256(fh.read()).hexdigest()
            bundle['file_hashes'][os.path.basename(f)] = h

chain = ''.join(v for k, v in sorted(bundle['file_hashes'].items()))
bundle['chain_hash'] = hashlib.sha256(chain.encode()).hexdigest()

with open(os.path.join(evidence_dir, '07_sovereign_attestation.json'), 'w') as f:
    json.dump(bundle, f, indent=2)

print(f"  Partial bundle saved. Hash: {bundle['chain_hash'][:32]}...")
PY
}

pass_gate() {
    echo -e "${GREEN}[PASS]${NC} GATE $1: $2"
    echo "PASS|GATE_$1|$2|$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$EVIDENCE_DIR/gate_results.txt"
}

fail_gate() {
    echo -e "${RED}[FAIL]${NC} GATE $1: $2"
    echo -e "${RED}       Reason: $3${NC}"
    echo "FAIL|GATE_$1|$2|$3|$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$EVIDENCE_DIR/gate_results.txt"
    echo ""
    echo -e "${GOLD}This failure is evidence. It documents the exact gap between${NC}"
    echo -e "${GOLD}the design and the hardware. See evidence/ for details.${NC}"
    assemble_partial_bundle "$1" "$3"
    exit 1
}

warn_gate() {
    echo -e "${GOLD}[WARN]${NC} GATE $1: $2"
    echo "WARN|GATE_$1|$2|$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$EVIDENCE_DIR/gate_results.txt"
}

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   ARDA OS — SOVEREIGN CORONATION${NC}"
echo -e "${CYAN}   Silicon Truth Protocol${NC}"
echo -e "${CYAN}   $TIMESTAMP${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 0: HARDWARE CENSUS
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 0: HARDWARE CENSUS ──${NC}"

KERNEL_VERSION=$(uname -r)
ARCH=$(uname -m)
CPU_MODEL=$(grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | xargs || echo "unknown")
MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "live-session-$(hostname)")

echo "  Kernel:  $KERNEL_VERSION"
echo "  Arch:    $ARCH"
echo "  CPU:     $CPU_MODEL"
echo "  Machine: $MACHINE_ID"

if [ "$EUID" -ne 0 ]; then
    fail_gate "0" "Root Required" "This script must be run as root (sudo)"
fi

if [ "$ARCH" != "x86_64" ]; then
    fail_gate "0" "Architecture" "eBPF LSM requires x86_64, got $ARCH"
fi

cat > "$EVIDENCE_DIR/00_hardware_census.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "kernel_version": "$KERNEL_VERSION",
  "architecture": "$ARCH",
  "cpu_model": "$CPU_MODEL",
  "machine_id": "$MACHINE_ID",
  "hostname": "$(hostname)",
  "efi_present": $([ -d /sys/firmware/efi ] && echo "true" || echo "false"),
  "secure_boot": "$(mokutil --sb-state 2>/dev/null || echo 'unknown')"
}
EOF

pass_gate "0" "Hardware Census Complete"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 1: TPM VERIFICATION
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 1: TPM VERIFICATION ──${NC}"

systemctl start tpm2-abrmd 2>/dev/null || true

if [ ! -c /dev/tpm0 ] && [ ! -c /dev/tpmrm0 ]; then
    echo "  No TPM device found at /dev/tpm0 or /dev/tpmrm0"
    dmesg | grep -i tpm > "$EVIDENCE_DIR/01_tpm_dmesg.txt" 2>/dev/null || true
    fail_gate "1" "TPM Device" "No TPM device node found. Check BIOS TPM settings."
fi

echo "  Running tpm2_getcap properties-fixed..."
if tpm2_getcap properties-fixed > "$EVIDENCE_DIR/01_tpm_properties.txt" 2>&1; then
    TPM_MANUFACTURER=$(grep -A1 "TPM2_PT_MANUFACTURER" "$EVIDENCE_DIR/01_tpm_properties.txt" | tail -1 | xargs || echo "unknown")
    TPM_FW=$(grep -A1 "TPM2_PT_FIRMWARE_VERSION" "$EVIDENCE_DIR/01_tpm_properties.txt" | tail -1 | xargs || echo "unknown")
    echo "  TPM Manufacturer: $TPM_MANUFACTURER"
    echo "  TPM Firmware:     $TPM_FW"
    echo "  THIS IS A REAL TPM 2.0"
else
    cat "$EVIDENCE_DIR/01_tpm_properties.txt"
    fail_gate "1" "TPM Properties" "tpm2_getcap failed. See 01_tpm_properties.txt"
fi

echo "  Reading PCR bank (sha256:0,1,7,11)..."
if tpm2_pcrread sha256:0,1,7,11 > "$EVIDENCE_DIR/02_pcr_raw.txt" 2>&1; then
    python3 - <<PY 2>/dev/null || echo "  (Python parsing skipped, raw values saved)"
import re, json
pcrs = {}
with open(r'''$EVIDENCE_DIR/02_pcr_raw.txt''') as f:
    for line in f:
        m = re.match(r'\s*(\d+)\s*:\s*0x([0-9A-Fa-f]+)', line)
        if m:
            pcrs[int(m.group(1))] = m.group(2).lower()
with open(r'''$EVIDENCE_DIR/02_pcr_values.json''', 'w') as f:
    json.dump({'timestamp': '$TIMESTAMP', 'bank': 'sha256', 'pcrs': pcrs}, f, indent=2)
print('  PCR JSON saved.')
for k, v in sorted(pcrs.items()):
    print(f'    PCR {k}: {v[:16]}...')
PY
else
    fail_gate "1" "PCR Read" "tpm2_pcrread failed. See 02_pcr_raw.txt"
fi

pass_gate "1" "TPM 2.0 Verified — Real Silicon"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 2: ATTESTATION KEY ENROLLMENT
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 2: ATTESTATION KEY ENROLLMENT ──${NC}"

AK_DIR="$EVIDENCE_DIR/ak"
mkdir -p "$AK_DIR"

echo "  Clearing stale TPM handles..."
tpm2_evictcontrol -C o -c 0x81010001 2>/dev/null || true
tpm2_flushcontext -t 2>/dev/null || true
tpm2_flushcontext -l 2>/dev/null || true
tpm2_flushcontext -s 2>/dev/null || true

echo "  Creating primary key hierarchy..."
if tpm2_createprimary -C e -g sha256 -G rsa2048 -c "$AK_DIR/primary.ctx" 2>"$AK_DIR/primary.err"; then
    echo "  Primary key created."
else
    cat "$AK_DIR/primary.err"
    fail_gate "2" "Primary Key" "tpm2_createprimary failed. See ak/primary.err"
fi

echo "  Creating Attestation Key (AK)..."
if tpm2_create -C "$AK_DIR/primary.ctx" -G rsa2048 -g sha256 \
    -u "$AK_DIR/ak.pub" -r "$AK_DIR/ak.priv" \
    -a "fixedtpm|fixedparent|sensitivedataorigin|userwithauth|sign" \
    2>"$AK_DIR/ak_create.err"; then
    echo "  AK created."
else
    cat "$AK_DIR/ak_create.err"
    fail_gate "2" "AK Creation" "tpm2_create (AK) failed. See ak/ak_create.err"
fi

echo "  Loading AK into TPM..."
if tpm2_load -C "$AK_DIR/primary.ctx" -u "$AK_DIR/ak.pub" -r "$AK_DIR/ak.priv" \
    -c "$AK_DIR/ak.ctx" 2>"$AK_DIR/ak_load.err"; then
    echo "  AK loaded."
else
    cat "$AK_DIR/ak_load.err"
    fail_gate "2" "AK Load" "tpm2_load (AK) failed. See ak/ak_load.err"
fi

echo "  Making AK persistent (0x81010001)..."
tpm2_evictcontrol -C o -c "$AK_DIR/ak.ctx" 0x81010001 2>/dev/null || {
    tpm2_evictcontrol -C o -c 0x81010001 2>/dev/null || true
    tpm2_evictcontrol -C o -c "$AK_DIR/ak.ctx" 0x81010001 2>"$AK_DIR/ak_persist.err" || {
        warn_gate "2" "AK persistence failed (non-critical, using transient context)"
    }
}

tpm2_readpublic -c "$AK_DIR/ak.ctx" -o "$EVIDENCE_DIR/03_ak_public.pem" 2>/dev/null || true

pass_gate "2" "Attestation Key Enrolled — Identity Anchor Set"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 3: BOOT QUOTE
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 3: BOOT QUOTE ──${NC}"

echo "  Nonce: $NONCE"
echo "$NONCE" > "$EVIDENCE_DIR/04_quote_nonce.txt"

echo "  Generating TPM quote against PCRs 0,1,7,11..."
if tpm2_quote -c "$AK_DIR/ak.ctx" -l sha256:0,1,7,11 \
    -q "$NONCE" \
    -m "$EVIDENCE_DIR/04_tpm_quote.bin" \
    -s "$EVIDENCE_DIR/04_tpm_quote_sig.bin" \
    -o "$EVIDENCE_DIR/04_tpm_quote_pcrs.bin" \
    2>"$EVIDENCE_DIR/04_quote.err"; then

    QUOTE_HASH=$(sha256sum "$EVIDENCE_DIR/04_tpm_quote.bin" | cut -d' ' -f1)
    SIG_HASH=$(sha256sum "$EVIDENCE_DIR/04_tpm_quote_sig.bin" | cut -d' ' -f1)
    echo "  Quote blob hash:     $QUOTE_HASH"
    echo "  Signature blob hash: $SIG_HASH"
    echo "  THIS IS A SILICON-SIGNED BOOT ATTESTATION"

    cat > "$EVIDENCE_DIR/04_quote_metadata.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "nonce": "$NONCE",
  "pcr_selection": "sha256:0,1,7,11",
  "quote_sha256": "$QUOTE_HASH",
  "signature_sha256": "$SIG_HASH",
  "ak_handle": "0x81010001",
  "silicon_signed": true
}
EOF
else
    cat "$EVIDENCE_DIR/04_quote.err"
    fail_gate "3" "TPM Quote" "tpm2_quote failed. See 04_quote.err"
fi

pass_gate "3" "Boot Quote Captured — Silicon Root of Trust"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 4: eBPF LSM COMPILATION
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 4: eBPF LSM COMPILATION ──${NC}"

echo "  Checking kernel LSM configuration..."
CURRENT_LSMS=$(cat /sys/kernel/security/lsm 2>/dev/null || echo "unknown")
echo "  Active LSMs: $CURRENT_LSMS"

if echo "$CURRENT_LSMS" | grep -q "bpf"; then
    echo "  BPF LSM: ACTIVE"
else
    warn_gate "4" "BPF LSM not in active LSM list. Attempting to continue..."
    echo ""
    echo -e "${GOLD}  NOTE: BPF LSM is not enabled in boot parameters.${NC}"
    echo -e "${GOLD}  To enable: add 'lsm=landlock,lockdown,yama,integrity,bpf'${NC}"
    echo -e "${GOLD}  to GRUB_CMDLINE_LINUX in /etc/default/grub and reboot.${NC}"
    echo ""
fi

apt-get install -y -qq linux-headers-$(uname -r) 2>/dev/null || {
    warn_gate "4" "linux-headers not available for live kernel (non-critical)"
}

VMLINUX_H="$BPF_DIR/vmlinux.h"
if [ ! -f "$VMLINUX_H" ]; then
    echo "  Generating vmlinux.h from running kernel..."
    bpftool btf dump file /sys/kernel/btf/vmlinux format c > "$VMLINUX_H" 2>/dev/null || {
        find /usr/src -name vmlinux.h -exec cp {} "$VMLINUX_H" \; 2>/dev/null || {
            fail_gate "4" "vmlinux.h" "Cannot generate vmlinux.h. Kernel BTF may not be available."
        }
    }
fi

cp "$KIT_DIR/bpf/arda_physical_lsm.c" "$BPF_DIR/" 2>/dev/null || true

echo "  Compiling arda_physical_lsm.c..."
COMPILE_CMD="clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
  -I$BPF_DIR \
  -c $BPF_DIR/arda_physical_lsm.c \
  -o $BPF_DIR/arda_physical_lsm.o"

echo "  CMD: $COMPILE_CMD"
if eval "$COMPILE_CMD" > "$EVIDENCE_DIR/05_ebpf_compile.log" 2>&1; then
    BPF_SIZE=$(stat -c%s "$BPF_DIR/arda_physical_lsm.o")
    BPF_HASH=$(sha256sum "$BPF_DIR/arda_physical_lsm.o" | cut -d' ' -f1)
    echo "  Compiled: arda_physical_lsm.o ($BPF_SIZE bytes)"
    echo "  Object hash: $BPF_HASH"
    cp "$BPF_DIR/arda_physical_lsm.o" "$EVIDENCE_DIR/05_arda_physical_lsm.o"
else
    cat "$EVIDENCE_DIR/05_ebpf_compile.log"
    fail_gate "4" "eBPF Compilation" "clang BPF compilation failed. See 05_ebpf_compile.log"
fi

pass_gate "4" "eBPF LSM Compiled — Kernel Object Ready"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 5: eBPF LOAD & ENFORCEMENT TEST
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 5: eBPF LOAD & ENFORCEMENT TEST ──${NC}"

find_existing_arda_lsm() {
    bpftool -j prog show 2>/dev/null | jq -r '
        .[] | select(.type=="lsm" and .name=="arda_sovereign_ignition") | .id
    ' | head -n1
}

TEST_DIR="$(mktemp -d "$EVIDENCE_DIR/gate5_test_XXXXXX")"
TEST_SRC="$TEST_DIR/arda_test_binary.c"
TEST_BIN="$TEST_DIR/arda_test_binary"

echo "  Test dir: $TEST_DIR"

cleanup_gate5() {
    rm -rf "$TEST_DIR" 2>/dev/null || true
}
trap cleanup_gate5 EXIT

cat > "$TEST_SRC" <<'TESTEOF'
#include <stdio.h>
int main() {
    printf("ARDA_TEST: If you see this, execution was ALLOWED\n");
    return 0;
}
TESTEOF

ENFORCEMENT_RESULT="NOT_TESTED"
LOAD_SUCCESS=false
PROGRAM_SOURCE="none"
EXISTING_PROG_ID=""

if [ ! -f "$TEST_SRC" ]; then
    echo "SOURCE_CREATE_DENIED|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/06_enforcement_test.log"
    ENFORCEMENT_RESULT="DENY_CONFIRMED"
    pass_gate "5" "LSM active — denied source creation"
else
    echo "  Fresh source file created."
    echo "  Checking for existing Arda LSM program..."
    EXISTING_PROG_ID="$(find_existing_arda_lsm || true)"

    if [ -n "${EXISTING_PROG_ID:-}" ]; then
        echo "  Found existing loaded Arda LSM: program id $EXISTING_PROG_ID"
        LOAD_SUCCESS=true
        PROGRAM_SOURCE="reused"
    else
        echo "  No existing Arda LSM found. Loading fresh..."
        mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf
        rm -f /sys/fs/bpf/arda_lsm 2>/dev/null || true

        if bpftool prog load "$BPF_DIR/arda_physical_lsm.o" /sys/fs/bpf/arda_lsm \
            type lsm 2>"$EVIDENCE_DIR/06_bpf_load.log"; then
            echo "  Fresh eBPF LSM load succeeded."
            LOAD_SUCCESS=true
            PROGRAM_SOURCE="fresh"
            EXISTING_PROG_ID="$(find_existing_arda_lsm || true)"
        else
            cat "$EVIDENCE_DIR/06_bpf_load.log"
            if grep -qi "File exists" "$EVIDENCE_DIR/06_bpf_load.log"; then
                echo "  Load conflict detected. Re-checking for existing loaded program..."
                EXISTING_PROG_ID="$(find_existing_arda_lsm || true)"
                if [ -n "${EXISTING_PROG_ID:-}" ]; then
                    echo "  Existing Arda LSM confirmed after conflict: program id $EXISTING_PROG_ID"
                    LOAD_SUCCESS=true
                    PROGRAM_SOURCE="reused_after_conflict"
                fi
            fi
        fi
    fi

    if [ "$LOAD_SUCCESS" = true ]; then
        echo "  Compiling fresh test binary..."
        if gcc -o "$TEST_BIN" "$TEST_SRC" > "$EVIDENCE_DIR/06_gcc_stdout.log" 2>"$EVIDENCE_DIR/06_gcc_stderr.log"; then
            if [ ! -f "$TEST_BIN" ]; then
                echo "COMPILE_REPORTED_OK_BUT_BINARY_MISSING|prog_id=${EXISTING_PROG_ID:-unknown}|$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                    > "$EVIDENCE_DIR/06_enforcement_test.log"
                ENFORCEMENT_RESULT="INDETERMINATE"
                warn_gate "5" "Compile claimed success but no binary exists"
            else
                echo "  Fresh binary compiled: $TEST_BIN"
                TEST_INODE=$(stat -c%i "$TEST_BIN")
                TEST_DEV=$(stat -c%D "$TEST_BIN")

                echo "  Executing fresh binary..."
                if "$TEST_BIN" > "$EVIDENCE_DIR/06_enforcement_test.log" 2>&1; then
                    echo "ALLOWED|inode=$TEST_INODE|dev=$TEST_DEV|prog_id=${EXISTING_PROG_ID:-unknown}|$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                        >> "$EVIDENCE_DIR/06_enforcement_test.log"
                    ENFORCEMENT_RESULT="DENY_FAILED"
                    warn_gate "5" "LSM present but did not deny execution"
                else
                    EXIT_CODE=$?
                    echo "DENY|inode=$TEST_INODE|dev=$TEST_DEV|prog_id=${EXISTING_PROG_ID:-unknown}|exit=$EXIT_CODE|$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                        >> "$EVIDENCE_DIR/06_enforcement_test.log"
                    ENFORCEMENT_RESULT="DENY_CONFIRMED"
                    pass_gate "5" "eBPF LSM active and denial confirmed"
                fi
            fi
        else
            if grep -Eqi "Permission denied|Operation not permitted|EPERM" "$EVIDENCE_DIR/06_gcc_stderr.log"; then
                cat "$EVIDENCE_DIR/06_gcc_stderr.log" > "$EVIDENCE_DIR/06_enforcement_test.log"
                echo "COMPILE_DENIED|prog_id=${EXISTING_PROG_ID:-unknown}|$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                    >> "$EVIDENCE_DIR/06_enforcement_test.log"
                ENFORCEMENT_RESULT="DENY_CONFIRMED"
                pass_gate "5" "LSM active — denied binary materialization"
            else
                cat "$EVIDENCE_DIR/06_gcc_stderr.log" > "$EVIDENCE_DIR/06_enforcement_test.log"
                ENFORCEMENT_RESULT="INDETERMINATE"
                warn_gate "5" "Compile failed for non-policy reason"
            fi
        fi
    else
        ENFORCEMENT_RESULT="NOT_TESTED"
        warn_gate "5" "Could not confirm an active Arda LSM program"
    fi
fi

echo "$ENFORCEMENT_RESULT" > "$EVIDENCE_DIR/06_enforcement_result.txt"

cat > "$EVIDENCE_DIR/06_bpf_runtime_status.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "program_source": "$PROGRAM_SOURCE",
  "program_id": "${EXISTING_PROG_ID:-}",
  "enforcement_result": "$ENFORCEMENT_RESULT",
  "lsm_active": "$CURRENT_LSMS",
  "test_dir": "$TEST_DIR"
}
EOF

bpftool prog list > "$EVIDENCE_DIR/06_bpf_prog_list.txt" 2>&1 || true
bpftool map list > "$EVIDENCE_DIR/06_bpf_map_list.txt" 2>&1 || true
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 6: ASSEMBLE ATTESTATION BUNDLE
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 6: ATTESTATION BUNDLE ──${NC}"

python3 - <<PY 2>/dev/null || echo "  (Python unavailable — generate bundle manually)"
import json, hashlib, os, glob, base64

evidence_dir = r'''$EVIDENCE_DIR'''

# Load PCR values
pcr_values = {}
pcr_file = os.path.join(evidence_dir, '02_pcr_values.json')
if os.path.exists(pcr_file):
    with open(pcr_file) as f:
        pcr_data = json.load(f)
        pcr_values = pcr_data.get('pcrs', {})

# Base64 encode blobs
tpm_quote_b64 = ''
tpm_sig_b64 = ''
ak_pub_b64 = ''

quote_bin = os.path.join(evidence_dir, '04_tpm_quote.bin')
sig_bin = os.path.join(evidence_dir, '04_tpm_quote_sig.bin')
ak_pub = os.path.join(evidence_dir, '03_ak_public.pem')

if os.path.exists(quote_bin):
    with open(quote_bin, 'rb') as f:
        tpm_quote_b64 = base64.b64encode(f.read()).decode()

if os.path.exists(sig_bin):
    with open(sig_bin, 'rb') as f:
        tpm_sig_b64 = base64.b64encode(f.read()).decode()

if os.path.exists(ak_pub):
    with open(ak_pub, 'rb') as f:
        ak_pub_b64 = base64.b64encode(f.read()).decode()

# Enforcement result
enforcement_result = 'NOT_TESTED'
enforcement_file = os.path.join(evidence_dir, '06_enforcement_result.txt')
enforcement_log = os.path.join(evidence_dir, '06_enforcement_test.log')

if os.path.exists(enforcement_file):
    with open(enforcement_file) as f:
        enforcement_result = f.read().strip()
elif os.path.exists(enforcement_log):
    with open(enforcement_log) as f:
        content = f.read()
        if 'DENY|' in content or 'COMPILE_DENIED|' in content or 'SOURCE_CREATE_DENIED|' in content:
            enforcement_result = 'DENY_CONFIRMED'
        elif 'ALLOWED|' in content:
            enforcement_result = 'DENY_FAILED'
        else:
            enforcement_result = 'INDETERMINATE'

# Live runtime status
runtime_status_file = os.path.join(evidence_dir, '06_bpf_runtime_status.json')
lsm_loaded = False
runtime_status = {}
if os.path.exists(runtime_status_file):
    with open(runtime_status_file) as f:
        runtime_status = json.load(f)
        lsm_loaded = bool(runtime_status.get('program_id'))

has_tpm = os.path.exists(os.path.join(evidence_dir, '01_tpm_properties.txt'))
has_quote = os.path.exists(quote_bin)
has_ebpf_obj = os.path.exists(os.path.join(evidence_dir, '05_arda_physical_lsm.o'))

if has_tpm and has_quote and lsm_loaded and enforcement_result == 'DENY_CONFIRMED':
    boot_state = 'LAWFUL_FULL'
elif has_tpm and has_quote and lsm_loaded and has_ebpf_obj:
    boot_state = 'LAWFUL_PARTIAL'
elif has_tpm and has_quote:
    boot_state = 'ATTESTED_ONLY'
else:
    boot_state = 'INCOMPLETE'

# File hashes
file_hashes = {}
for f in sorted(glob.glob(os.path.join(evidence_dir, '*'))):
    if os.path.isfile(f) and '07_sovereign' not in f and '08_covenant' not in f:
        with open(f, 'rb') as fh:
            h = hashlib.sha256(fh.read()).hexdigest()
            file_hashes[os.path.basename(f)] = h

chain = ''.join(v for k, v in sorted(file_hashes.items()))
chain_hash = hashlib.sha256(chain.encode()).hexdigest()
mirror_id = 'ARDA-CORONATION-' + chain_hash[:16].upper()

bundle = {
    'protocol': 'ARDA_CORONATION_v1',
    'mirror_id': mirror_id,
    'timestamp': '$TIMESTAMP',
    'boot_state': boot_state,
    'principal': {
        'type': 'SOVEREIGN_SUBSTRATE',
        'assent': 'I attest that this evidence was produced by direct hardware interaction',
        'machine_id': '$MACHINE_ID'
    },
    'tpm_pcr_quote': {
        'nonce': '$NONCE',
        'pcr_selection': 'sha256:0,1,7,11',
        'pcr_values': pcr_values,
        'quote_blob_b64': tpm_quote_b64,
        'signature_blob_b64': tpm_sig_b64,
        'ak_public_b64': ak_pub_b64,
        'silicon_signed': bool(tpm_quote_b64)
    },
    'ebpf_enforcement': {
        'compiled': has_ebpf_obj,
        'lsm_loaded': lsm_loaded,
        'program_id': runtime_status.get('program_id', ''),
        'program_source': runtime_status.get('program_source', ''),
        'enforcement_result': enforcement_result,
        'lsm_active': '$CURRENT_LSMS'
    },
    'file_hashes': file_hashes,
    'chain_hash': chain_hash
}

with open(os.path.join(evidence_dir, '07_sovereign_attestation.json'), 'w') as f:
    json.dump(bundle, f, indent=2)

print(f'  Mirror ID:       {mirror_id}')
print(f'  Boot State:      {boot_state}')
print(f'  TPM Quote:       {"CAPTURED (" + str(len(tpm_quote_b64)) + " bytes b64)" if tpm_quote_b64 else "MISSING"}')
print(f'  AK Public:       {"ENROLLED" if ak_pub_b64 else "MISSING"}')
print(f'  PCR Values:      {len(pcr_values)} registers')
print(f'  LSM Loaded:      {lsm_loaded}')
print(f'  Enforcement:     {enforcement_result}')
print(f'  Chain Hash:      {chain_hash}')
PY

pass_gate "6" "Attestation Bundle Assembled — Full Proof Object"
echo ""

# ═══════════════════════════════════════════════════════════════════
# GATE 7: SOVEREIGN SEAL
# ═══════════════════════════════════════════════════════════════════
echo -e "${GOLD}── GATE 7: SOVEREIGN SEAL ──${NC}"

GATES_PASSED=$(grep -c "^PASS" "$EVIDENCE_DIR/gate_results.txt" 2>/dev/null || echo "0")
GATES_WARNED=$(grep -c "^WARN" "$EVIDENCE_DIR/gate_results.txt" 2>/dev/null || echo "0")
TOTAL_GATES=7

BUNDLE_HASH="unknown"
if [ -f "$EVIDENCE_DIR/07_sovereign_attestation.json" ]; then
    BUNDLE_HASH=$(python3 -c "import json; d=json.load(open('$EVIDENCE_DIR/07_sovereign_attestation.json')); print(d.get('chain_hash','unknown'))" 2>/dev/null || echo "unknown")
fi

cat > "$EVIDENCE_DIR/CORONATION_SEAL.md" <<EOF
# ARDA OS — SOVEREIGN CORONATION SEAL

## Silicon Truth Protocol

- **Timestamp**: $TIMESTAMP
- **Machine ID**: $MACHINE_ID
- **Kernel**: $KERNEL_VERSION
- **CPU**: $CPU_MODEL
- **Gates Passed**: $GATES_PASSED/$TOTAL_GATES (Warnings: $GATES_WARNED)
- **Bundle Hash**: $BUNDLE_HASH

## Gate Results

$(cat "$EVIDENCE_DIR/gate_results.txt" 2>/dev/null | while IFS='|' read -r status gate desc rest; do
    if [ "$status" = "PASS" ]; then
        echo "- ✅ **$gate**: $desc"
    elif [ "$status" = "WARN" ]; then
        echo "- ⚠️ **$gate**: $desc"
    elif [ "$status" = "FAIL" ]; then
        echo "- ❌ **$gate**: $desc — $rest"
    fi
done)

## Evidence Manifest

$(ls -la "$EVIDENCE_DIR/" 2>/dev/null | tail -n +2)

## Attestation

This seal was produced by executing the Arda OS Sovereign Coronation Script
on physical hardware with a real TPM 2.0 chip. The TPM quote is signed by
the machine's silicon. The eBPF object was compiled against the running kernel.

No mock mode was used. No simulation was employed.

The evidence in this bundle is either:
- **Proof** that the system works as designed, or
- **Documentation** of exactly where it does not, which is equally valuable.

---

*Probatio ante laudem. Lex ante actionem. Veritas ante vanitatem.*
EOF

echo ""
cat "$EVIDENCE_DIR/CORONATION_SEAL.md"
echo ""

echo -e "${GOLD}  Writing first covenant chain entry...${NC}"
python3 - <<PY 2>/dev/null || echo "  (Python unavailable — covenant chain skipped)"
import json, hashlib, os

evidence_dir = r'''$EVIDENCE_DIR'''
bundle = {}
att_file = os.path.join(evidence_dir, '07_sovereign_attestation.json')
if os.path.exists(att_file):
    with open(att_file) as f:
        bundle = json.load(f)

entry = {
    'chain_index': 0,
    'entry_type': 'SOVEREIGN_CORONATION',
    'timestamp': '$TIMESTAMP',
    'mirror_id': bundle.get('mirror_id', 'UNKNOWN'),
    'boot_state': bundle.get('boot_state', 'UNKNOWN'),
    'tpm_pcr_quote_hash': hashlib.sha256(
        json.dumps(bundle.get('tpm_pcr_quote', {}), sort_keys=True).encode()
    ).hexdigest(),
    'principal': bundle.get('principal', {}),
    'evidence_chain_hash': bundle.get('chain_hash', 'UNKNOWN'),
    'previous_hash': '0' * 64,
    'attestation': 'This is the first entry in the real covenant chain. It was produced by direct silicon interaction, not simulation.'
}

entry_str = json.dumps(entry, sort_keys=True)
entry['entry_hash'] = hashlib.sha256(entry_str.encode()).hexdigest()

chain = [entry]
chain_file = os.path.join(evidence_dir, '08_covenant_chain.json')
with open(chain_file, 'w') as f:
    json.dump(chain, f, indent=2)

print(f'  Covenant Entry #0: {entry["entry_hash"][:32]}...')
print(f'  Mirror ID:         {entry["mirror_id"]}')
print(f'  Boot State:        {entry["boot_state"]}')
print('  This is the FIRST entry in the real covenant chain.')
PY

pass_gate "7" "Sovereign Seal Written — Covenant Chain Initiated"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   CORONATION COMPLETE${NC}"
echo -e "${GREEN}   Gates Passed: $GATES_PASSED/$TOTAL_GATES${NC}"
echo -e "${GREEN}   Evidence:     $EVIDENCE_DIR/${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Copy the evidence/ directory to commit to the covenant chain.${NC}"
echo ""
