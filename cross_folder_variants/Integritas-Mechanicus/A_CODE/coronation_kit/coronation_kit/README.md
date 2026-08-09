# ARDA OS — Sovereign Coronation Kit

## The Silicon Truth Protocol

This kit transforms a standard Debian 12 Live USB into a sovereign Arda OS kernel
with real TPM attestation and real eBPF enforcement. No mock mode. No simulation.

**What you will produce:**
- A TPM 2.0 hardware attestation quote signed by the machine's silicon
- A live eBPF LSM enforcement proof against a real syscall
- A tamper-evident audit bundle committed to the covenant chain
- Evidence that nobody can call "mock mode"

**What you need:**
- A machine with BIOS/UEFI access and a TPM 2.0 chip
- Two USB drives: one for Debian Live, one for this kit (or internet to clone from GitHub)
- About 30 minutes
- Willingness to document failure honestly if something breaks

---

## PHASE 0: Create the Bootable Debian USB (On Your Windows Machine)

### Step 1: Download Debian 12 Live ISO

Download the **Debian 12 Live ISO with non-free firmware** (important for hardware compatibility):

```
https://cdimage.debian.org/cdimage/unofficial/non-free/cd-including-firmware/current-live/amd64/iso-hybrid/
```

Get the **GNOME or Standard** variant:
- `firmware-12.x.x-live-amd64-standard.iso` (minimal, ~1GB, recommended)
- `firmware-12.x.x-live-amd64-gnome.iso` (desktop, ~3GB, if you want a GUI)

### Step 2: Flash to USB with Rufus

1. Download Rufus: https://rufus.ie
2. Insert USB drive #1 (8GB+ recommended)
3. Select the Debian ISO
4. Partition scheme: **GPT** (for UEFI boot with TPM)
5. File system: FAT32
6. Click START
7. When prompted, choose "Write in ISO Image mode"

### Step 3: Copy this Kit to USB #2

Copy the entire `coronation_kit/` folder to a second USB drive.
Or you can clone from GitHub once booted:

```bash
git clone https://github.com/Byron2306/Integritas-Mechanicus.git
cd Integritas-Mechanicus
git checkout arda-os-desktop
cd coronation_kit
```

---

## PHASE 1: Boot the Target Machine

### Step 4: Enter BIOS/UEFI

1. Insert USB #1 (Debian Live)
2. Power on, press F2/F12/DEL (varies by manufacturer) to enter BIOS
3. **Verify TPM is ENABLED** in Security settings
4. Set boot order: USB first
5. Ensure **Secure Boot** is either:
   - Enabled with Microsoft keys (will measure into PCR 7)
   - Disabled (PCR 7 will be all zeros — still valid, just different)
6. Save and reboot

### Step 5: Boot into Debian Live

Select "Debian Live" from the boot menu. You'll land in a terminal or desktop.

Open a terminal and become root:

```bash
sudo -i
```

### Step 6: Mount the Kit

If you copied to USB #2:

```bash
# Find the USB
lsblk
# Mount it (adjust sdX as needed)
mkdir -p /mnt/kit
mount /dev/sdX1 /mnt/kit
cd /mnt/kit/coronation_kit
```

Or clone from GitHub:

```bash
apt update && apt install -y git
git clone https://github.com/Byron2306/Integritas-Mechanicus.git
cd Integritas-Mechanicus && git checkout arda-os-desktop
cd coronation_kit
```

---

## PHASE 2: Run the Coronation

### Step 7: Execute

```bash
chmod +x scripts/00_coronation.sh
./scripts/00_coronation.sh
```

This single script runs all phases in order:

1. **GATE 0: Hardware Census** — Detects TPM, checks kernel version, verifies BPF LSM support
2. **GATE 1: TPM Verification** — `tpm2_getcap properties-fixed`, reads PCR bank
3. **GATE 2: AK Enrollment** — Creates the Attestation Key identity anchor
4. **GATE 3: Boot Quote** — Generates a TPM2 quote with nonce, captures PCR values
5. **GATE 4: eBPF Compilation** — Compiles `arda_physical_lsm.c` with clang/BPF target
6. **GATE 5: eBPF Load & Enforcement** — Loads the LSM, runs a real deny test
7. **GATE 6: Attestation Bundle** — Assembles the evidence and hashes it
8. **GATE 7: Sovereign Seal** — Writes the final audit event

Each gate will either:
- **PASS** — proceed to next gate
- **FAIL** — stop, document exactly why, and save partial evidence

**Both outcomes are valuable.** A documented failure tells you the exact gap between design and hardware.

---

## PHASE 3: Collect Evidence

After the script completes, all evidence is in `evidence/`:

```
evidence/
├── 00_hardware_census.json       # CPU, kernel, TPM detection
├── 01_tpm_properties.txt         # Raw tpm2_getcap output
├── 02_pcr_values.json            # PCR 0,1,7,11 readings
├── 03_ak_public.pem              # Attestation Key (public)
├── 04_tpm_quote.bin              # Raw TPM quote blob
├── 04_tpm_quote_sig.bin          # Quote signature
├── 04_quote_nonce.txt            # Nonce used
├── 05_ebpf_compile.log           # eBPF compilation output
├── 06_enforcement_test.log       # Real deny/allow test results
├── 07_sovereign_attestation.json # Final bundle with all hashes
└── CORONATION_SEAL.md            # Human-readable seal document
```

### Step 8: Copy Evidence Out

```bash
# Copy to the kit USB
cp -r evidence/ /mnt/kit/coronation_evidence_$(date +%Y%m%d)/

# Or create a tarball
tar czf /tmp/arda_coronation_$(date +%Y%m%d_%H%M%S).tar.gz evidence/
```

---

## What If Something Fails

### "TPM not detected"
- Enter BIOS, confirm TPM is enabled
- Some machines have TPM under "Security" → "Trusted Computing"
- Intel machines: look for "PTT" (Platform Trust Technology)
- AMD machines: look for "fTPM"
- Run `dmesg | grep -i tpm` to see kernel messages

### "BPF LSM not supported"
- Debian 12 kernel 6.1 has BPF compiled in but BPF LSM may not be in boot params
- The coronation script will attempt to add `lsm=landlock,lockdown,yama,integrity,bpf` 
  to kernel params and reboot
- If that fails: the kernel may need CONFIG_BPF_LSM=y recompile (documented in failure log)

### "eBPF compilation fails"
- Missing packages: the script tries to install `clang`, `libbpf-dev`, `linux-headers-$(uname -r)`
- Live USB may not have all packages cached — internet is required for this step
- Evidence will include the exact compiler error

### "eBPF loads but enforcement test doesn't deny"
- This is a meaningful result — document it
- The BPF LSM hook may be registered but the map not populated
- Check `bpftool prog list` and `bpftool map dump` output

### "Everything passes"
- You have silicon-rooted proof. Commit the evidence bundle to the repo.
- This is the moment mock mode dies.

---

## What This Proves (When It Works)

| Evidence | What It Means |
|----------|--------------|
| TPM PCR quote | The boot chain is measured by silicon. Nobody can forge this. |
| AK-signed attestation | The machine's identity is anchored to a hardware key. |
| eBPF LSM deny log | A real syscall was blocked by constitutional enforcement code. |
| Hash-linked bundle | The evidence chain is tamper-evident. Modify any piece and the hash breaks. |

This is not a claim. It is not a simulation. It is a machine, measured by its own silicon,
enforcing a constitution against a real process, with cryptographic proof of every step.

---

*Probatio ante laudem. Lex ante actionem. Veritas ante vanitatem.*

*Proof before praise. Law before action. Truth before vanity.*
