# Containers & Kubernetes Lab (T1610/T1611/T1613)

This repo includes an Atomic Validation job `container-kubernetes` that targets:
- `T1610` Deploy a container
- `T1611` Escape to host
- `T1613` Container and Resource Discovery

## Important notes

- Many container/k8s atomics assume **systemd** / `systemctl` / privileged host access.
- In this stack, the backend container has access to the host Docker socket (`/var/run/docker.sock`) so Docker-based tests can run, but prereq checks may not reflect host state.
- The job is configured with `skip_prereqs: true` so prerequisite checks don’t cause “skipped” runs.

## Run

- `POST /api/atomic-validation/run` with `{"job_id":"container-kubernetes"}`

## Evidence outputs

- Atomic run JSON: `./artifacts/atomic-validation/run_*.json`
- Runtime telemetry:
  - Falco: `POST /api/integrations/runtime/run` with `{"tool":"falco","params":{"action":"alerts"}}`
  - Trivy: `POST /api/integrations/runtime/run` with `{"tool":"trivy","params":{"action":"status"}}`

