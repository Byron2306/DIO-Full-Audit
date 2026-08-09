Windows Guest Bootstrap

Purpose

Use this after Windows setup finishes in `metatron-winval-clean-01`. It turns the fresh Windows guest into a usable Atomic validation target for the existing `windows-lab-winrm` runner profile.

What to copy into the guest

- Preferred: copy the vendored repo folders from this workspace into the Windows VM so the guest uses the same Atomic snapshot as the Linux evidence pipeline.
- Copy [atomic-red-team](../atomic-red-team) into `C:\AtomicRedTeam\atomics`
- Copy [tools/invoke-atomicredteam](../tools/invoke-atomicredteam) into `C:\AtomicRedTeam\invoke-atomicredteam`

If you cannot copy the vendored folders, clone the upstream repos inside the guest instead. That is acceptable for bootstrapping, but it will not be the exact same snapshot as the Linux bundle.

Inside the guest

1. Open an elevated PowerShell window.
2. Install PowerShell 7 if `pwsh` is not already present.
3. Place the Atomic folders at:
   `C:\AtomicRedTeam\atomics`
   `C:\AtomicRedTeam\invoke-atomicredteam`
4. Run the bootstrap script from this repo:

```powershell
powershell -ExecutionPolicy Bypass -File C:\path\to\windows_guest_bootstrap.ps1
```

Expected result

- WinRM enabled on TCP `5985`
- `Invoke-AtomicTest` importable from `C:\AtomicRedTeam\invoke-atomicredteam\Invoke-AtomicRedTeam.psd1`
- Atomic YAML files present under `C:\AtomicRedTeam\atomics`

Lab note

- The bootstrap script enables WinRM Basic auth and unencrypted transport for isolated-lab simplicity because the current Linux-side runner uses plain `Invoke-Command -ComputerName ... -Credential ...` semantics and the VM is on the local libvirt network.
- Do not reuse those WinRM settings outside this lab.

Back on the Linux host

1. Get the VM IP:

```bash
sudo virsh domifaddr metatron-winval-clean-01
```

2. Update [config/atomic_powershell.yml](../config/atomic_powershell.yml):
   Set `runner_profiles[].remote_host` for `windows-lab-winrm` to the VM IP.
   Set `runner_profiles[].enabled` for `windows-lab-winrm` to `true` once the guest bootstrap succeeds.

3. Export the password used for the Windows Administrator account:

```bash
export ATOMIC_WINDOWS_LAB_PASSWORD='...'
```

4. Validate remote reachability from the host container or host shell with a simple PowerShell remoting command before running Atomic jobs.

Suggested first validation inside the guest

```powershell
Import-Module C:\AtomicRedTeam\invoke-atomicredteam\Invoke-AtomicRedTeam.psd1
Invoke-AtomicTest T1059 -ShowDetailsBrief -PathToAtomicsFolder C:\AtomicRedTeam\atomics
```

That does not count as execution evidence, but it confirms the module and atomics are wired correctly before you run real tests.