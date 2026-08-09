# ARDA OS CORONATION — QUICK REFERENCE

## Before You Start (On Windows Machine)
1. Download: https://cdimage.debian.org/cdimage/unofficial/non-free/cd-including-firmware/current-live/amd64/iso-hybrid/
   → Get `firmware-12.x.x-live-amd64-standard.iso`
2. Flash to USB #1 with Rufus (GPT, FAT32)
3. Copy `coronation_kit/` folder to USB #2

## At the Target Machine

### BIOS Setup
- Enable TPM (Security → Trusted Computing / PTT / fTPM)
- Boot order: USB first
- Note Secure Boot status (either way is fine)

### Boot & Run
```
sudo -i
mount /dev/sdX1 /mnt        # USB #2 with the kit
cd /mnt/coronation_kit
chmod +x scripts/*.sh
./scripts/00_coronation.sh   # THE BIG ONE
```

### If BPF LSM Not Active
```
# At GRUB menu, press 'e', find 'linux' line, add:
# lsm=landlock,lockdown,yama,integrity,bpf
# Press Ctrl+X to boot
# Then re-run 00_coronation.sh
```

### Collect Evidence
```
cp -r evidence/ /mnt/coronation_evidence/
# OR
tar czf /tmp/arda_evidence.tar.gz evidence/
# Copy to USB
```

## Expected Gates
```
GATE 0: Hardware Census     → CPU, kernel, arch check
GATE 1: TPM Verification    → tpm2_getcap, PCR read
GATE 2: AK Enrollment       → Attestation Key creation
GATE 3: Boot Quote           → Silicon-signed TPM quote
GATE 4: eBPF Compilation    → clang → BPF object
GATE 5: eBPF Enforcement    → Real syscall deny test
GATE 6: Attestation Bundle  → Hash-linked evidence
GATE 7: Sovereign Seal      → Final document
```

## If Something Fails
Document it. The failure IS evidence.
Check evidence/ folder — partial bundles are saved.
