# Arkime (Moloch) integration

This folder contains helpers to run Arkime (Moloch) and parse exported session data for IOC extraction and ingestion into the threat-intel pipeline.

Quick notes:
- Arkime stores session/index data and exports JSON from its viewer or `moloch-capture`. Use the exported JSON (sessions or pcap metadata) as input to the parser.
- Parser will extract IP addresses, observed hostnames, and domains and optionally POST to `THREAT_INTEL_API` (defaults to `http://localhost:8000/api/threat-intel/ingest`).

Run (Docker example):

PowerShell (simple helper, assumes Elasticsearch reachable at localhost:9200):

```
./run_arkime.ps1
```

Export sessions from Arkime UI or use Arkime API to save JSON, then run the parser:

```
python parse_arkime.py arkime_sessions_export.json
```

The parser writes a `.indicators.json` file next to the input and will attempt to POST to `THREAT_INTEL_API` if set.
