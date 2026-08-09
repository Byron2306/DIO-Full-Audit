# Seraph External Integrations Overview

This document summarizes how the Seraph security suite integrates with external tools, services, and platforms. Seraph uses a multi-layered approach to ensure that integrations are governed, auditable, and operationally reliable.

## 1. CLI Tool Gateway (Policy Enforcement Point)
**Location:** `backend/services/tool_gateway.py`

The CLI Tool Gateway is the primary mechanism for executing external command-line tools. It acts as a **Policy Enforcement Point (PEP)** that prevents raw shell access.

### Key Features:
- **Allowlisted Commands:** Only predefined security tools (like `nmap`, `iptables`, `sha256sum`) can be executed.
- **Parameter Validation:** Inputs are validated against a schema (e.g., IP addresses, integers, specific flags) to prevent command injection.
- **Trust-Based Execution:** Tools can require a minimum trust state (e.g., `trusted`, `degraded`) before they are allowed to run.
- **Audit Logging:** Every execution attempt (success or denial) is logged with the principal, parameters, exit code, and duration.
- **Output Redaction:** Sensitive information (tokens, passwords, private keys) is automatically redacted from the tool's output.

## 2. Unified Agent Integrations
**Location:** `unified_agent/integrations/`

The Unified Agent hosts the "Brawn" of the system, running on target endpoints. It includes a modular integration subsystem for specific security tools.

### Supported Tools Include:
- **Amass:** Passive subdomain enumeration via `run_amass.sh`.
- **ClamAV:** Malware scanning and signature-based detection.
- **Spiderfoot:** OSINT automation for threat intelligence.
- **YARA:** Pattern matching for malware identification using custom rules in `yara_rules/`.
- **Suricata:** Network Threat Detection and IDS with rules in `config/suricata.yaml`.
- **Falco:** Cloud-native runtime security with configurations in `config/falco.yaml`.
- **Osquery:** Performance monitoring and compliance querying via `config/osquery.conf`.
- **Standardized Output:** All integration scripts are designed to return JSON-structured findings for ingestion by the backend.

## 3. SIEM Integration Service
**Location:** `backend/services/siem.py`

Seraph supports enterprise-grade logging by integrating directly with Security Information and Event Management (SIEM) platforms.

### Integration Channels:
- **Elasticsearch:** Direct indexing of security events into `seraph-security` indices.
- **Splunk:** Events sent via Splunk HTTP Event Collector (HEC).
- **Syslog:** Standard CEF (Common Event Format) logging over UDP.
- **Batch Processing:** Events are buffered and flushed at regular intervals to optimize performance.

## 4. Seraph Proxy (Egress Controller)
**Location:** `backend/services/seraph_proxy.py`

The Seraphic Proxy governs all outbound HTTP requests made by the system (e.g., for threat intel lookups or academic research).

### Key Features:
- **Academic Allowlist:** Restricts egress to trusted domains like `arxiv.org`, `scholar.google.com`, etc.
- **Forensic Ledger:** Every request is logged in an accountability ledger for forensic audit.
- **Attestation:** Requests are tagged with attestation markers to ensure they are authorized by the core reasoning engine.

## 5. Unified Sovereign Adapter
**Location:** `backend/services/unified_adapter.py`

This service acts as the bridge between **Sophia (Sophic Reasoning)** and the **Unified Agent (Brawn)**. It allows high-level AI decisions to be translated into low-level security actions, such as:
- Triggering full system scans.
- Querying the "Preflight Gate" to authorize process execution.
- Discovering LAN devices.

## 6. Cuckoo Sandbox Integration
**Location:** `backend/services/cuckoo_sandbox.py`

For deep analysis of suspicious files, Seraph integrates with Cuckoo Sandbox. This allows the system to:
- Submit files for dynamic analysis in a controlled environment.
- Retrieve detailed behavioral reports.
- Use sandbox findings to inform automated remediation decisions.

---
**Document Version:** 1.0  
**Status:** Canonical Reference
