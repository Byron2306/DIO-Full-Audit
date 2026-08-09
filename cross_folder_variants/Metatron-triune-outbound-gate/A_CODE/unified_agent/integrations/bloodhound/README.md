# BloodHound integration

This folder contains helpers to run BloodHound / SharpHound collection and parse exported BloodHound JSON for ingestion into the threat-intel pipeline.

Notes:
- SharpHound collectors produce JSON with nodes and relationships. Typical node types: `Computer`, `User`, `Group`, `Domain`.
- For detection enrichment and lateral movement planning, extract `Computer` node names, hostnames, and user principals as indicators.

Run SharpHound on a target AD and export JSON files, or use BloodHound UI to export data. Then run the parser:

```
python parse_bloodhound.py bloodhound_owned.json
```

The parser writes a `.indicators.json` file and will attempt to POST to `THREAT_INTEL_API` if set.
