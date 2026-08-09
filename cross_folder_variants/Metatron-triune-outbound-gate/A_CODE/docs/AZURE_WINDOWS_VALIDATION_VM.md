# Azure Windows Validation VM

Purpose

Use an Azure-hosted Windows VM as a faster fallback when the local ISO path is blocked by download speed or host resource pressure. This keeps progress moving for Arda Windows validation while still giving you a real Windows environment with Secure Boot and vTPM.

What this enables

- Real Windows execution for the existing `windows-lab-winrm` runner profile.
- Azure Trusted Launch with Secure Boot and TPM 2.0-compatible vTPM.
- RDP for interactive setup and WinRM for automation from the Linux host.
- Reuse of the existing guest bootstrap script at [scripts/windows_guest_bootstrap.ps1](/home/byron/Downloads/Metatron-triune-outbound-gate/scripts/windows_guest_bootstrap.ps1).

What this does not solve by itself

- Physical TPM chip behavior or OEM-specific firmware differences.
- Host-local boot measurements from your own KVM or bare-metal machine.
- Automatic transfer of the vendored Atomic snapshot into the guest.

Recommended Azure shape

- Start with `Standard_D4s_v5`.
- Use a Trusted Launch capable Generation 2 Windows image.
- Keep this VM disposable. Treat it as a validation target, not a durable workstation.

Deployment files

- Bicep template: [infra/azure/windows-validation-vm/main.bicep](/home/byron/Downloads/Metatron-triune-outbound-gate/infra/azure/windows-validation-vm/main.bicep)

Deploy the VM

1. Install Azure CLI and sign in.
2. Create or choose a resource group.
3. Deploy the Bicep template with a narrow source IP range instead of `*`.

```bash
az login
az group create --name metatron-winval-rg --location eastus2
az deployment group create \
  --resource-group metatron-winval-rg \
  --template-file infra/azure/windows-validation-vm/main.bicep \
  --parameters adminPassword='<strong-password>' \
               allowedSourceAddressPrefix='<your-public-ip>/32'
```

After deployment

1. Connect over RDP to the VM public IP.
2. Clone or copy this repo into the guest.
3. Place the Windows-side Atomic content at:
   `C:\AtomicRedTeam\atomics`
   `C:\AtomicRedTeam\invoke-atomicredteam`
4. Open an elevated PowerShell session in the guest.
5. Run [scripts/windows_guest_bootstrap.ps1](/home/byron/Downloads/Metatron-triune-outbound-gate/scripts/windows_guest_bootstrap.ps1).

WinRM note

- The current bootstrap script enables Basic auth and unencrypted WinRM for lab simplicity.
- That is acceptable only for an isolated disposable lab VM with tightly scoped NSG rules.
- Do not leave `5985` open to the internet beyond your own source IP.

Wire the backend to the Azure VM

1. Copy the `windows-lab-winrm` profile from [config/atomic_runner_profiles.example.yml](/home/byron/Downloads/Metatron-triune-outbound-gate/config/atomic_runner_profiles.example.yml) into your active config.
2. Set `remote_host` to the Azure VM public IP or reachable private IP.
3. Export `ATOMIC_WINDOWS_LAB_PASSWORD` with the Administrator password.
4. Enable the profile and run a simple remoting check before invoking Atomic jobs.

Suggested validation order

1. Confirm RDP access.
2. Confirm `Test-WSMan localhost` succeeds in the guest.
3. Confirm host-to-guest WinRM succeeds from Linux.
4. Run the Arda Windows tests or Atomic runner checks.
5. Only after that, compare Azure vTPM results with the local KVM path if you still need parity.

Attestation expectation

- Azure Trusted Launch should let you validate TPM presence, Secure Boot state, and a cloud-backed vTPM boot chain.
- If you later need hardware-specific TPM semantics, keep the local KVM or bare-metal path as a second-stage validation target.
