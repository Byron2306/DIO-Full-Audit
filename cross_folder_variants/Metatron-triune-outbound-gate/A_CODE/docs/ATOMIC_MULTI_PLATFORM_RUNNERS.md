Atomic Multi-Platform Runners

The Linux sibling sandbox container can only execute Linux-capable atomics. It cannot provide a real Windows or macOS kernel, service model, registry, or userland. For non-Linux techniques, the backend must route execution to an external validation host.

Implemented runner types in [backend/atomic_validation.py](../backend/atomic_validation.py):

- `docker`: Linux sibling container sandbox on the current host.
- `local`: direct PowerShell execution inside the backend container.
- `ssh`: remote host execution over SSH.
- `winrm`: remote Windows host execution over WinRM.

Configuration

- Copy the schema from [config/atomic_runner_profiles.example.yml](../config/atomic_runner_profiles.example.yml).
- Set `default_runner_profile` to your Linux sandbox profile.
- Add `runner_profile` on jobs that must execute on Windows or macOS.
- Provide secrets through environment variables referenced by `password_env`.

Recommended topology

- Linux techniques: `docker` profile to `seraph-sandbox-tools:latest`.
- Windows techniques: `winrm` profile to a disposable Windows lab VM with Atomic Red Team installed.
- macOS techniques: `ssh` profile to a disposable macOS validation host.
- Cloud techniques: define dedicated jobs that execute on provider-aware hosts with `aws`, `az`, or `gcloud` tooling and mapped credentials.

Important constraint

If a technique has no Atomic Red Team test for the target platform, routing alone will not validate it. Those techniques still require either:

- a custom emulation procedure, or
- a different execution source than Atomic Red Team.