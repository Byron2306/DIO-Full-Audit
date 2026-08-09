# Windows Validation VM

Purpose

Use a dedicated Windows VM to execute Windows-only Atomic Red Team techniques that cannot run inside the Linux sibling sandbox.

What this enables

- Real execution evidence for Windows-only techniques.
- Routing from the backend via the `winrm` runner profile implemented in [backend/atomic_validation.py](../backend/atomic_validation.py).
- Reuse of the same atomic-validation result pipeline and evidence bundle generation.

What this does not solve by itself

- Techniques with no Atomic Red Team test at all.
- Cloud or SaaS techniques that require provider-native accounts and tooling.
- macOS techniques, which still need a macOS host.

Prerequisites

- Either a Windows ISO you are licensed to use or an official Microsoft developer VM archive.
- `sudo` on the Linux host.
- Hardware virtualization available via `/dev/kvm`.

Fast fallback path

- If the local ISO path is blocked by bandwidth or host capacity, use the Azure Trusted Launch runbook in [docs/AZURE_WINDOWS_VALIDATION_VM.md](/home/byron/Downloads/Metatron-triune-outbound-gate/docs/AZURE_WINDOWS_VALIDATION_VM.md).
- That path reuses the same `windows-lab-winrm` runner profile and guest bootstrap flow, but swaps the local guest for an Azure-hosted Windows VM with Secure Boot and vTPM.

Recommended path for this environment

- Prefer a clean Windows 11 ISO install over the imported Hyper-V developer image.
- Use generic SATA storage and an `e1000e` NIC for the initial install so Windows Setup does not depend on extra virtio drivers.
- Keep the guest at `4096` MiB RAM and `2` vCPUs on this host.

Provision the VM

1. If using an ISO, copy [config/windows_validation_vm.env.example](../config/windows_validation_vm.env.example) to a clean env file such as `config/windows_validation_vm_clean.env` and set `WINDOWS_ISO_PATH`.
2. If using the official Microsoft developer VM archive, use [config/windows_validation_vm.env](../config/windows_validation_vm.env) as prepared and wait for the Hyper-V zip download to finish.
3. For the developer VM archive path, convert the Microsoft VHDX into qcow2:

```bash
sudo ./scripts/import_windows_dev_vm.sh
```

1. Create or import the VM:

```bash
ATOMIC_VM_ENV_FILE=config/windows_validation_vm_clean.env sudo ./scripts/setup_windows_validation_vm.sh
```

1. Open the console and complete Windows setup if needed:

```bash
sudo virt-viewer metatron-winval-clean-01
```

1. After Windows setup finishes, follow the guest bootstrap guide in [docs/WINDOWS_GUEST_BOOTSTRAP.md](../docs/WINDOWS_GUEST_BOOTSTRAP.md).

Guest setup

Install inside the Windows VM:

- PowerShell 7+
- Atomic Red Team atomics
- Invoke-AtomicRedTeam
- WinRM enabled for remote PowerShell execution

An example guest bootstrap script is provided at [scripts/windows_guest_bootstrap.ps1](../scripts/windows_guest_bootstrap.ps1).

Recommended install paths inside the guest:

- `C:/AtomicRedTeam/atomics`
- `C:/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1`

Wire the backend to the VM

1. Copy the `windows-lab-winrm` profile from [config/atomic_runner_profiles.example.yml](../config/atomic_runner_profiles.example.yml) into [config/atomic_powershell.yml](../config/atomic_powershell.yml).
1. Set `remote_host` to the Windows VM IP from:

```bash
sudo virsh domifaddr metatron-winval-clean-01
```

1. Export the WinRM password used by `password_env` before starting the backend.

Validation approach

- Keep Linux jobs on the `linux-sandbox` profile.
- Add Windows job groups for the remaining Windows techniques and set `runner_profile: windows-lab-winrm`.
- Run those jobs through the existing atomic validation flow.

Current hard blockers in this environment

- A licensed Windows ISO is required for the recommended clean-install path.

Current status in this environment

- The QEMU/libvirt/OVMF/swtpm stack is installed.
- The clean ISO-based VM `metatron-winval-clean-01` has been created successfully and is the preferred Windows validation target.
- The previous imported Hyper-V image exists under `/home/byron/Downloads/windows-vm-downloads`, but it has proven unstable as a validation base.
