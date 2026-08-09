# SpiderFoot OSINT integration

Quickstart (Docker):

1. Start SpiderFoot (web UI/API):

PowerShell:

```
./run_spiderfoot.ps1
```

2. Open http://localhost:5001 to create scans, or use the SpiderFoot API to schedule scans and export JSON results.

Notes:
- SpiderFoot can enumerate many OSINT sources (whois, DNS, cert transparency, web indexing). Use results to enrich `threat-intel` and SIEM.
- For automation, configure API keys in SpiderFoot and call the API to start scans, then export JSON and ingest via the same ingestion endpoint used for Amass.
