# macOS Lab (Atomic + Seraph)

This repo’s Atomic Validation runner supports **Linux sandbox (Docker)** and **Windows (WinRM)** out of the box. To stop macOS coverage from being “skipped”, you need a real macOS execution target and a runner profile.

## What gets executed

- Atomic jobs `macos-persistence`, `macos-execution`, `macos-credential-access` are configured in `config/atomic_powershell.yml`.
- They run via **SSH** using runner profile `macos-lab-ssh` (disabled by default).

## Prereqs on the macOS host

1. Enable SSH: System Settings → General → Sharing → **Remote Login** (Allow your lab user).
2. Install Homebrew (if needed).
3. Install PowerShell:
   - `brew install --cask powershell`
4. Prepare Atomic Red Team + Invoke-AtomicRedTeam:
   - Choose a shared location, example:
     - Atomics: `/Users/Shared/AtomicRedTeam/atomics`
     - Module: `/Users/Shared/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1`
   - You can clone and copy to that layout, or use your preferred method.

## Configure the backend runner

1. Create (or reuse) an SSH key on your host and ensure it can log into the macOS lab user.
2. Provide these env vars to the backend container (via `.env` / shell env):

```
MACOS_LAB_HOST=192.0.2.10
MACOS_LAB_USER=seraph
MACOS_LAB_PORT=22
MACOS_SSH_KEY_PATH=/app/secrets/ssh/id_ed25519
MACOS_ATOMIC_ROOT=/Users/Shared/AtomicRedTeam/atomics
MACOS_INVOKE_ATOMICREDTEAM_MODULE_PATH=/Users/Shared/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1
```

3. Mount the SSH key into the backend container at the path you set above.

## Enable the runner profile

- Edit `config/atomic_powershell.yml` and set:
  - `runner_profiles[].enabled: true` for `profile_id: macos-lab-ssh`

## Run the jobs

- From the UI or API:
  - `POST /api/atomic-validation/run` with `{"job_id":"macos-persistence"}`
  - `POST /api/atomic-validation/run` with `{"job_id":"macos-execution"}`
  - `POST /api/atomic-validation/run` with `{"job_id":"macos-credential-access"}`

Results persist under `./artifacts/atomic-validation/run_*.json` (host path via `docker-compose.yml`).

