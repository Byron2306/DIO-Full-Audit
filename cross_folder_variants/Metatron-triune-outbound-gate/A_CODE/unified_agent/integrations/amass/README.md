# Amass integration

Quickstart to run Amass enumeration and ingest results into the local threat-intel ingestion endpoint.

Prerequisites:
- Docker installed and running
- Python 3 with `requests` installed for the parser (optional ingestion)

Run:

PowerShell:

```
./run_amass.ps1 example.com
```

This will produce a JSON-lines file `amass_example.com_<ts>.json` in the current folder. Use `parse_amass.py` to extract hosts and optionally POST to `THREAT_INTEL_API` environment variable (defaults to `http://localhost:8000/api/threat-intel/ingest`).
