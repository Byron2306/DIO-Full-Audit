# MITRE ATT&CK Technique Inventory (237) and 639-Coverage Expansion Plan

This document lists every ATT&CK technique/sub-technique ID currently referenced in backend and unified agent Python code (`backend/**/*.py`, `unified_agent/**/*.py`).

- Total unique technique IDs detected: **237**
- Extraction method: static regex sweep for `T####` and `T####.###` identifiers

## Technique list (237)

- T1003, T1003.001, T1003.002, T1003.003, T1003.004, T1003.005, T1003.006, T1005, T1012, T1014, T1016, T1018
- T1021, T1021.001, T1021.002, T1021.004, T1021.006, T1027, T1036, T1036.003, T1036.005, T1039, T1040, T1041
- T1046, T1047, T1048, T1048.001, T1048.003, T1053, T1053.005, T1055, T1055.001, T1055.012, T1056, T1056.001
- T1057, T1059, T1059.001, T1059.003, T1059.004, T1059.005, T1059.006, T1068, T1069, T1069.002, T1070, T1070.001
- T1070.004, T1070.006, T1071, T1071.001, T1071.002, T1071.004, T1074, T1078, T1078.001, T1078.002, T1078.003, T1078.004
- T1080, T1081, T1082, T1083, T1087, T1087.002, T1091, T1095, T1098, T1105, T1106, T1110
- T1110.001, T1110.003, T1112, T1113, T1115, T1123, T1125, T1127, T1127.001, T1133, T1134, T1134.001
- T1134.002, T1134.005, T1136, T1140, T1176, T1185, T1187, T1189, T1190, T1195, T1195.002, T1197
- T1199, T1200, T1202, T1203, T1204, T1204.002, T1205, T1207, T1210, T1218, T1218.001, T1218.002
- T1218.003, T1218.004, T1218.005, T1218.007, T1218.008, T1218.009, T1218.010, T1218.011, T1218.014, T1219, T1222, T1222.001
- T1398, T1439, T1444, T1465, T1482, T1484, T1484.001, T1485, T1486, T1489, T1490, T1491
- T1491.002, T1495, T1496, T1497, T1505.003, T1528, T1530, T1533, T1534, T1537, T1538, T1539
- T1542, T1542.001, T1542.002, T1542.003, T1543, T1543.003, T1546.003, T1546.010, T1546.011, T1546.012, T1546.015, T1547
- T1547.001, T1547.005, T1547.006, T1547.010, T1548, T1548.001, T1548.002, T1548.003, T1550, T1550.002, T1550.003, T1552
- T1552.001, T1552.003, T1552.004, T1552.005, T1553, T1553.002, T1553.006, T1555, T1555.003, T1555.004, T1556, T1556.001
- T1556.006, T1557, T1557.001, T1558, T1558.001, T1558.002, T1558.003, T1558.004, T1559.001, T1560, T1560.001, T1561
- T1562, T1562.001, T1562.002, T1562.004, T1562.008, T1563, T1563.002, T1564, T1564.001, T1564.004, T1566, T1566.001
- T1566.002, T1567, T1567.002, T1568, T1568.001, T1568.002, T1569, T1569.002, T1570, T1571, T1572, T1573
- T1573.002, T1574, T1574.001, T1574.002, T1574.006, T1574.007, T1574.011, T1580, T1583, T1587, T1589, T1590.002
- T1590.004, T1592, T1595, T1598, T1598.003, T1601, T1601.001, T1649, T1660

## Roadmap to expand from 237 toward 639 ATT&CK techniques

> Practical note: 639 spans Enterprise ATT&CK techniques+sub-techniques and requires broader telemetry depth than regex-referenced IDs alone. The plan below is grouped by ATT&CK strategy/tactic domains to close that gap with concrete integrations.

### 1) Initial Access + Resource Development (TA0001, TA0042, TA0043)
- **External Attack Surface Management (EASM) integration**: continuous CT logs, ASN drift, cloud asset misconfiguration exposure, typosquatting and package impersonation feeds.
- **Mail + web ingress enrichment**: MTA headers, DMARC/SPF failures, browser exploit telemetry, attachment behavior detonation pipelines.
- **Supply-chain provenance**: Sigstore/Cosign attestations, SBOM drift checks, CI artifact policy enforcement.

### 2) Execution + Persistence + Privilege Escalation (TA0002, TA0003, TA0004)
- **Kernel-native telemetry**: eBPF/Sysmon parity on Linux/macOS/Windows for process ancestry, token changes, module loads.
- **Persistence artifact collectors**: comprehensive autostart ext points (ASEPs), launch agents, scheduled tasks, service config drift, WMI subscriptions.
- **Identity privilege graphing**: AD/AzureAD role chain exposure + risky delegation paths.

### 3) Defense Evasion + Credential Access (TA0005, TA0006)
- **Memory and LSASS hardening visibility**: ETW/Sysmon + EDR memory access event normalization.
- **Credential stores and browser vault instrumentation**: endpoint-level decryption-attempt signals and secret exfil heuristics.
- **Anti-tamper observability**: sensor disable attempts, security policy rollback detection, trust store poisoning.

### 4) Discovery + Lateral Movement (TA0007, TA0008)
- **Identity-aware east/west traffic**: Zeek + flow telemetry + identity/session context for RDP/SMB/WinRM/SSH movement graphs.
- **Graph attack path correlation**: unify attack-path service with endpoint detections to raise real-world movement confidence.
- **Remote execution lenses**: PsExec/WMI/PowerShell remoting command lineage capture.

### 5) Collection + C2 + Exfiltration (TA0009, TA0011, TA0010)
- **Protocol-aware C2 detection**: JA3/JA4, SNI entropy, DNS tunneling, DoH/DoT anomaly classification.
- **DLP extension**: endpoint clipboard/screenshot/archive staging + cloud egress channels.
- **Encrypted channel analytics**: traffic shape modeling and beacon periodicity scoring in graph-risk pipeline.

### 6) Impact (TA0040)
- **Ransomware behavior depth**: file entropy bursts, shadow copy operations, mass rename/delete sequence models.
- **Recovery control telemetry**: immutable backup verification + restore tamper alerts.
- **Business-impact scoring**: crown-jewel aware blast-radius model tied to response playbooks.

### 7) Cross-cutting integrations to increase ATT&CK sub-technique depth
- **Cloud-native**: AWS GuardDuty/CloudTrail, Azure Defender/Entra ID, GCP SCC logs.
- **SaaS/Identity**: Okta, Entra ID sign-in risk, Google Workspace admin audit, M365 Defender incidents.
- **Network/Perimeter**: Suricata/Zeek unification, WAF/CDN logs, VPN auth telemetry.
- **OT/IoT/mobile**: MDM/EDR mobile parity, IoT protocol decoders, device trust posture events.

### 8) Engineering approach to make 639 achievable
1. Build a canonical ATT&CK catalog table (technique + sub-technique + tactic links).
2. Store per-technique evidence provenance (`source`, `last_seen`, `validation_level`, `playbook_linked`).
3. Split coverage into: **Implemented**, **Observed**, **Validated**, **Automated Response**.
4. Gate new detections with Atomic validation and auto-create coverage deltas in dashboard.
5. Add monthly “net-new ATT&CK depth” KPI by tactic to prevent regressions.


## Focused addendum: audit logging, browser isolation, Celery app, and container security

### Audit logging (telemetry chain + security services)
Current state:
- Strong local audit chain concepts exist (hash-linked records, principal/action/result lineage).
- Multiple services already emit auditable events, but evidence normalization is still uneven across domains.

Recommended integrations to increase ATT&CK depth:
- Add unified ATT&CK annotation on every audit record (`technique_id`, `tactic_id`, `confidence`, `evidence_ref`).
- Forward audit chain records to SIEM with tamper-evident hash checkpoints and periodic notarization.
- Add ATT&CK-aware audit queries for: credential access, privilege changes, defense evasion events, and policy bypass attempts.

### Browser isolation
Current state:
- Browser isolation service exists and can provide high-value telemetry for web-driven initial access/execution chains.

Recommended integrations to increase ATT&CK depth:
- Capture browser process tree + downloaded artifact lineage and map to techniques (drive-by compromise, malicious scripts, phishing follow-ons).
- Integrate detonation verdicts into world events and triune scoring loop with explicit ATT&CK tags.
- Correlate browser isolation sessions with identity risk and outbound C2/exfil patterns.

### Celery app and async task pipeline
Current state:
- Celery task modules exist for world ingest, triune tasks, and integration collectors.
- Background tasks are a major source of “observed” ATT&CK evidence but currently mixed in reliability and environment assumptions.

Recommended integrations to increase ATT&CK depth:
- Add standardized task-level ATT&CK metadata envelope (`source`, `techniques`, `tactics`, `validation_level`).
- Add dead-letter queue + retry policy metrics as security telemetry (failed ingestion can hide ATT&CK evidence).
- Add periodic ATT&CK reconciliation task that compares implemented techniques vs observed-in-last-N-days to detect blind spots.

### Container security (`container_security.py` + runtime tooling)
Current state:
- Container/runtime visibility exists across Trivy/Falco/Suricata and related routes/tooling, but ATT&CK mapping should be more explicit and unified.

Recommended integrations to increase ATT&CK depth:
- Normalize container findings into ATT&CK technique/sub-technique IDs at ingest time.
- Add runtime drift detection for container escape, privileged execution, and suspicious syscall patterns.
- Correlate container findings with kube/cloud control-plane logs for lateral movement and persistence coverage.

### Priority implementation order for these four domains
1. **Audit logging normalization** (fastest multiplier for trustworthy ATT&CK coverage accounting).
2. **Celery metadata envelope** (stabilizes background evidence quality and triune analytics).
3. **Container ATT&CK normalization** (major expansion of modern attack-surface coverage).
4. **Browser isolation enrichment** (high signal for initial access/execution chains).
