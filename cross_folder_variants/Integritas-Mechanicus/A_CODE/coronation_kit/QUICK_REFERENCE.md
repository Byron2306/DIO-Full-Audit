# ARDA OS CORONATION — QUICK REFERENCE

## Before You Start (On Windows Machine)
1. Download Debian 12 Live (with firmware):
   https://cdimage.debian.org/cdimage/unofficial/non-free/cd-including-firmware/current-live/amd64/iso-hybrid/
   → Get `firmware-12.x.x-live-amd64-standard.iso`
2. Flash to USB #1 with Rufus (GPT, FAT32)
3. Copy `coronation_kit/` folder to USB #2 (or use GitHub)

## At the Target Machine

### BIOS Setup
- Enable TPM (Security → Trusted Computing / PTT / fTPM)
- Boot order: USB first
- Note Secure Boot state

### Boot Debian & Get the Kit
```bash
sudo -i

# Option A: From USB #2
mount /dev/sdX1 /mnt
cd /mnt/coronation_kit

# Option B: From GitHub (needs internet)
apt update && apt install -y git
git clone https://github.com/Byron2306/Integritas-Mechanicus.git
cd Integritas-Mechanicus && git checkout arda-os-desktop
cd coronation_kit
```

### Run These THREE Scripts (In Order)

```bash
chmod +x scripts/*.sh

# 1. INSTALL EVERYTHING (Python, Ollama, TPM tools, eBPF toolchain)
sudo ./scripts/02_install_arda_stack.sh

# 2. SILICON CORONATION (TPM proof + eBPF enforcement)
sudo ./scripts/00_coronation.sh

# 3. (If Gate 5 warns about BPF LSM)
sudo ./scripts/01_enable_bpf_lsm.sh
# Then reboot and re-run 00_coronation.sh
```

### Launch the Live Desktop
```bash
sudo /opt/arda/launch_arda.sh
# Open http://localhost:8080
# Run the gauntlet with LIVE Qwen witnesses
```

### Collect Evidence
```bash
cp -r evidence/ /mnt/coronation_evidence/
# OR
tar czf /tmp/arda_evidence.tar.gz evidence/
```

## Expected Gates (00_coronation.sh)
```
GATE 0: Hardware Census     → CPU, kernel, arch
GATE 1: TPM Verification    → tpm2_getcap, PCR read (REAL SILICON)
GATE 2: AK Enrollment       → Attestation Key creation
GATE 3: Boot Quote           → Silicon-signed TPM quote
GATE 4: eBPF Compilation    → clang → BPF object
GATE 5: eBPF Enforcement    → Real syscall deny test
GATE 6: Attestation Bundle  → Hash-linked evidence
GATE 7: Sovereign Seal      → Final document
```

## If Something Fails
Document it. The failure IS evidence.
The `evidence/` folder always gets partial bundles.
