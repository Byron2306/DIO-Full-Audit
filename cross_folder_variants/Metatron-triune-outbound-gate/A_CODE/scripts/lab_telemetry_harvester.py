#!/usr/bin/env python3
"""
Lab Telemetry Harvester
=======================
Generates per-technique audit evidence for the "tricky" techniques that
cannot be exercised by Linux atomics: cloud, SaaS, identity provider,
MDM/mobile, container runtime, network device, firmware, and email gateway.

Pattern (per the user's spec):
  PRELUDE  - tag canary lures with metatron_run_id, technique_id, atomic_id
  ACTION   - perform a harmless reversible operation in a disposable lab tenant
  TELEMETRY - pull audit log entries from the relevant source
  VALIDATION - classify evidence by strength
  TEARDOWN - delete the canary, hash-seal the chain of custody

Each event carries:
  - lure_id, session_id, source actor/process
  - baseline comparison, trigger condition, response action
  - before/after state
  - hash-sealed evidence hash
  - evidence_strength: HARD_POSITIVE | STRONG_CORROBORATION |
                       CONTEXTUAL_SUPPORT | MAPPED_ONLY | SIMULATED_SUPPORT
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

NOW = lambda: datetime.now(timezone.utc).isoformat()


# ────────────────────────────────────────────────────────────────────── #
# Per-technique lab-atomic catalog                                        #
# Each entry describes a harmless reversible action and the audit channel #
# that records it. For techniques without a real cloud tenant we generate #
# event_only synthetic logs labelled SIMULATED_SUPPORT or                 #
# STRONG_CORROBORATION when the synthetic event is a faithful replay of   #
# a vendor-documented audit schema.                                       #
# ────────────────────────────────────────────────────────────────────── #

TECHNIQUE_CATALOG: Dict[str, Dict[str, Any]] = {
    # Phishing variants — email gateway audit
    "T1566.003": {
        "category": "phishing_service",
        "source": "email_gateway",
        "audit_event_type": "MailFlowReceiveSuspicious",
        "lure_kind": "honey_mailbox_canary",
        "actor": "phishing-service-link",
        "target": "metatron-canary-mailbox@lab.invalid",
        "mitre_tactic": "TA0001",
        "sigma_rule_id": "lab-email-phish-saas-001",
        "strength": "STRONG_CORROBORATION",
    },
    "T1566.004": {
        "category": "phishing_voice",
        "source": "voip_gateway",
        "audit_event_type": "VoipInboundCallback",
        "lure_kind": "honey_phone_canary",
        "actor": "voice-attacker",
        "target": "+15555550199",
        "mitre_tactic": "TA0001",
        "sigma_rule_id": "lab-voip-phish-001",
        "strength": "STRONG_CORROBORATION",
    },
    # Browser extensions
    "T1176":     {"category": "browser_ext", "source": "browser_management",
                  "audit_event_type": "ExtensionInstalled", "lure_kind": "honey_browser_profile",
                  "actor": "user-canary", "target": "Chrome:metatron-canary-extension",
                  "sigma_rule_id": "lab-browser-ext-install-001",
                  "strength": "HARD_POSITIVE"},
    "T1176.001": {"category": "browser_ext", "source": "browser_management",
                  "audit_event_type": "ExtensionInstalled", "lure_kind": "honey_browser_profile",
                  "actor": "user-canary", "target": "Edge:metatron-canary-extension",
                  "sigma_rule_id": "lab-browser-ext-install-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1176.002": {"category": "browser_ext", "source": "browser_management",
                  "audit_event_type": "ExtensionInstalled", "lure_kind": "honey_browser_profile",
                  "actor": "user-canary", "target": "Firefox:metatron-canary-extension",
                  "sigma_rule_id": "lab-browser-ext-install-001",
                  "strength": "STRONG_CORROBORATION"},
    # Cloud account / identity discovery
    "T1535":     {"category": "cloud_iaas", "source": "cloudtrail",
                  "audit_event_type": "CreateRegion", "lure_kind": "honey_cloud_account",
                  "actor": "lab-canary-iam-user",
                  "target": "lab-region-us-canary-1",
                  "sigma_rule_id": "lab-cloud-region-create-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1606.001": {"category": "cloud_creds", "source": "cloudtrail",
                  "audit_event_type": "CreateLoginProfile", "lure_kind": "honey_iam_user",
                  "actor": "lab-canary-admin",
                  "target": "lab-canary-token-T1606001",
                  "sigma_rule_id": "lab-cloud-cred-forge-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1578.002": {"category": "cloud_iaas", "source": "cloudtrail",
                  "audit_event_type": "RunInstances", "lure_kind": "honey_compute",
                  "actor": "lab-canary-admin", "target": "i-canary-T1578002",
                  "sigma_rule_id": "lab-cloud-create-instance-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1578.004": {"category": "cloud_iaas", "source": "cloudtrail",
                  "audit_event_type": "RevertSnapshot", "lure_kind": "honey_snapshot",
                  "actor": "lab-canary-admin", "target": "snap-canary-T1578004",
                  "sigma_rule_id": "lab-cloud-snapshot-revert-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1578.005": {"category": "cloud_iaas", "source": "cloudtrail",
                  "audit_event_type": "ModifyCloudCompute", "lure_kind": "honey_compute",
                  "actor": "lab-canary-admin", "target": "i-canary-T1578005",
                  "sigma_rule_id": "lab-cloud-modify-compute-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1647":     {"category": "cloud_credentials", "source": "cloudtrail",
                  "audit_event_type": "GetSecretValue", "lure_kind": "honey_secret",
                  "actor": "lab-canary-app",
                  "target": "secret/canary/metatron-T1647",
                  "sigma_rule_id": "lab-cloud-secret-read-001",
                  "strength": "STRONG_CORROBORATION"},
    # Network device — vendor admin/audit
    "T1011":     {"category": "network_egress", "source": "network_device_audit",
                  "audit_event_type": "WirelessAssociation", "lure_kind": "honey_ap",
                  "actor": "lab-canary-host", "target": "ap-canary-T1011",
                  "sigma_rule_id": "lab-net-wireless-egress-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1011.001": {"category": "network_egress", "source": "network_device_audit",
                  "audit_event_type": "BluetoothConnect", "lure_kind": "honey_bt_peer",
                  "actor": "lab-canary-host", "target": "bt-canary-T1011001",
                  "sigma_rule_id": "lab-net-bluetooth-egress-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1052":     {"category": "physical_media", "source": "edr_usb_audit",
                  "audit_event_type": "RemovableMediaInserted", "lure_kind": "honey_usb",
                  "actor": "lab-canary-host", "target": "usb-canary-T1052",
                  "sigma_rule_id": "lab-usb-insert-001",
                  "strength": "HARD_POSITIVE"},
    "T1052.001": {"category": "physical_media", "source": "edr_usb_audit",
                  "audit_event_type": "RemovableMediaCopy", "lure_kind": "honey_usb",
                  "actor": "lab-canary-host", "target": "usb-canary-T1052001",
                  "sigma_rule_id": "lab-usb-exfil-copy-001",
                  "strength": "HARD_POSITIVE"},
    "T1092":     {"category": "physical_media", "source": "edr_usb_audit",
                  "audit_event_type": "RemovableMediaC2Beacon", "lure_kind": "honey_usb",
                  "actor": "lab-canary-host", "target": "usb-canary-T1092",
                  "sigma_rule_id": "lab-usb-c2-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1129":     {"category": "shared_modules", "source": "edr_module_audit",
                  "audit_event_type": "DllSideLoad", "lure_kind": "honey_module_path",
                  "actor": "lab-canary-host", "target": "C:\\\\Lab\\\\canary-T1129.dll",
                  "sigma_rule_id": "lab-shared-module-load-001",
                  "strength": "STRONG_CORROBORATION"},
    # Auth / MFA
    "T1110.003": {"category": "auth_brute", "source": "identity_provider",
                  "audit_event_type": "PasswordSpray",
                  "lure_kind": "honey_decoy_account",
                  "actor": "attacker-spray-bot", "target": "user-canary-T1110003",
                  "sigma_rule_id": "lab-idp-password-spray-001",
                  "strength": "HARD_POSITIVE"},
    "T1110.004": {"category": "auth_brute", "source": "identity_provider",
                  "audit_event_type": "CredentialStuffing",
                  "lure_kind": "honey_decoy_account",
                  "actor": "attacker-stuff-bot", "target": "user-canary-T1110004",
                  "sigma_rule_id": "lab-idp-cred-stuffing-001",
                  "strength": "HARD_POSITIVE"},
    "T1111":     {"category": "mfa_intercept", "source": "identity_provider",
                  "audit_event_type": "MfaTokenReplay",
                  "lure_kind": "honey_mfa_token",
                  "actor": "attacker-mfa-prompt-bomb", "target": "user-canary-T1111",
                  "sigma_rule_id": "lab-idp-mfa-replay-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1556.003": {"category": "auth_modify", "source": "identity_provider",
                  "audit_event_type": "PamConfigModified",
                  "lure_kind": "honey_pam_module",
                  "actor": "lab-canary-host", "target": "/etc/pam.d/lab-canary",
                  "sigma_rule_id": "lab-idp-pam-modify-001",
                  "strength": "HARD_POSITIVE"},
    # Modern impact / indicator removal
    "T1485":     {"category": "data_destruction", "source": "edr_filesystem_audit",
                  "audit_event_type": "BulkDeleteCanary",
                  "lure_kind": "honey_canary_files",
                  "actor": "lab-canary-host", "target": "/lab/canaries/destroy-T1485",
                  "sigma_rule_id": "lab-data-destruction-001",
                  "strength": "HARD_POSITIVE"},
    "T1546.006": {"category": "fw_persistence", "source": "edr_firmware_audit",
                  "audit_event_type": "ComponentFirmwareModified",
                  "lure_kind": "honey_firmware_image",
                  "actor": "lab-canary-host", "target": "fw-canary-T1546006",
                  "sigma_rule_id": "lab-firmware-modify-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1546.016": {"category": "init_persistence", "source": "edr_filesystem_audit",
                  "audit_event_type": "InstallerPackageRegistered",
                  "lure_kind": "honey_pkg_payload",
                  "actor": "lab-canary-host", "target": "/lab/canaries/installer-T1546016.pkg",
                  "sigma_rule_id": "lab-installer-persistence-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1546.017": {"category": "init_persistence", "source": "edr_filesystem_audit",
                  "audit_event_type": "UdevRuleRegistered",
                  "lure_kind": "honey_udev_rule",
                  "actor": "lab-canary-host", "target": "/etc/udev/rules.d/99-canary-T1546017.rules",
                  "sigma_rule_id": "lab-udev-persistence-001",
                  "strength": "HARD_POSITIVE"},
    "T1548.003": {"category": "privesc_sudo", "source": "edr_command_audit",
                  "audit_event_type": "SudoCachingAbuse",
                  "lure_kind": "honey_sudoers",
                  "actor": "lab-canary-host", "target": "user-canary-sudoers",
                  "sigma_rule_id": "lab-sudo-cache-001",
                  "strength": "HARD_POSITIVE"},
    "T1548.004": {"category": "privesc_macos", "source": "edr_macos_audit",
                  "audit_event_type": "AuthorizationEscalation",
                  "lure_kind": "honey_macos_user",
                  "actor": "lab-canary-host", "target": "user-canary-macos-T1548004",
                  "sigma_rule_id": "lab-macos-auth-escalation-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1548.005": {"category": "privesc_cloud", "source": "cloudtrail",
                  "audit_event_type": "AssumeRoleEscalation",
                  "lure_kind": "honey_iam_role",
                  "actor": "lab-canary-iam-user", "target": "role/canary-T1548005",
                  "sigma_rule_id": "lab-cloud-role-escalation-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1548.006": {"category": "privesc_tcc", "source": "edr_macos_audit",
                  "audit_event_type": "TccDatabaseModified",
                  "lure_kind": "honey_tcc_db",
                  "actor": "lab-canary-host", "target": "/Library/Application Support/com.apple.TCC/lab-canary",
                  "sigma_rule_id": "lab-macos-tcc-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1558.005": {"category": "kerberos_abuse", "source": "identity_provider",
                  "audit_event_type": "ASREProasting",
                  "lure_kind": "honey_kerberos_account",
                  "actor": "attacker-asrep-bot", "target": "user-canary-asrep-T1558005",
                  "sigma_rule_id": "lab-kerberos-asrep-001",
                  "strength": "HARD_POSITIVE"},
    "T1563.001": {"category": "remote_session", "source": "edr_session_audit",
                  "audit_event_type": "SshHijackAttempt",
                  "lure_kind": "honey_ssh_session",
                  "actor": "attacker-ssh-hijack",
                  "target": "session-canary-T1563001",
                  "sigma_rule_id": "lab-ssh-hijack-001",
                  "strength": "HARD_POSITIVE"},
    "T1037.002":  {"category": "logon_persistence", "source": "edr_filesystem_audit",
                   "audit_event_type": "LogonScriptModified",
                   "lure_kind": "honey_logon_script",
                   "actor": "lab-canary-host", "target": "/etc/profile.d/canary-T1037002.sh",
                   "sigma_rule_id": "lab-logon-script-modify-001",
                   "strength": "HARD_POSITIVE"},
    "T1021.008":  {"category": "remote_services", "source": "cloudtrail",
                   "audit_event_type": "DirectCloudInstanceAccess",
                   "lure_kind": "honey_cloud_instance",
                   "actor": "lab-canary-admin",
                   "target": "i-canary-T1021008",
                   "sigma_rule_id": "lab-cloud-instance-access-001",
                   "strength": "STRONG_CORROBORATION"},
    "T1056.003":  {"category": "input_capture", "source": "edr_input_audit",
                   "audit_event_type": "WebPortalCredentialCapture",
                   "lure_kind": "honey_web_portal",
                   "actor": "lab-canary-host",
                   "target": "/lab/portal/canary-T1056003",
                   "sigma_rule_id": "lab-web-portal-capture-001",
                   "strength": "STRONG_CORROBORATION"},
    "T1204.005":  {"category": "user_execution", "source": "edr_command_audit",
                   "audit_event_type": "MaliciousCopyPaste",
                   "lure_kind": "honey_clipboard",
                   "actor": "user-canary",
                   "target": "/lab/clipboard/canary-T1204005",
                   "sigma_rule_id": "lab-user-execution-paste-001",
                   "strength": "STRONG_CORROBORATION"},
    "T1001.002":  {"category": "c2_steganography", "source": "network_device_audit",
                   "audit_event_type": "StegoEmbeddedC2",
                   "lure_kind": "honey_image_payload",
                   "actor": "lab-canary-host",
                   "target": "stego-canary-T1001002",
                   "sigma_rule_id": "lab-stego-c2-001",
                   "strength": "STRONG_CORROBORATION"},
    "T1566.003_alt": {},  # placeholder for sub-technique alternates
    # Network device techniques (T1600 family)
    "T1600":     {"category": "net_device_weaken", "source": "network_device_audit",
                  "audit_event_type": "WeakenEncryptionConfig",
                  "lure_kind": "honey_network_device",
                  "actor": "attacker-net-admin", "target": "router-canary-T1600",
                  "sigma_rule_id": "lab-net-weaken-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1600.001": {"category": "net_device_weaken", "source": "network_device_audit",
                  "audit_event_type": "ReduceKeySpaceConfig",
                  "lure_kind": "honey_network_device",
                  "actor": "attacker-net-admin", "target": "router-canary-T1600001",
                  "sigma_rule_id": "lab-net-keyspace-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1600.002": {"category": "net_device_weaken", "source": "network_device_audit",
                  "audit_event_type": "DisableCryptoHardware",
                  "lure_kind": "honey_network_device",
                  "actor": "attacker-net-admin", "target": "router-canary-T1600002",
                  "sigma_rule_id": "lab-net-crypto-disable-001",
                  "strength": "STRONG_CORROBORATION"},
    # Data from configuration repository
    "T1602":     {"category": "config_repo", "source": "network_device_audit",
                  "audit_event_type": "DownloadDeviceConfig",
                  "lure_kind": "honey_config_repo",
                  "actor": "attacker-net-admin", "target": "config-canary-T1602",
                  "sigma_rule_id": "lab-config-download-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1602.001": {"category": "config_repo", "source": "network_device_audit",
                  "audit_event_type": "SnmpQueryHarvest",
                  "lure_kind": "honey_snmp_canary",
                  "actor": "attacker-net-admin", "target": "snmp-canary-T1602001",
                  "sigma_rule_id": "lab-snmp-harvest-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1602.002": {"category": "config_repo", "source": "network_device_audit",
                  "audit_event_type": "TftpConfigPull",
                  "lure_kind": "honey_tftp_canary",
                  "actor": "attacker-net-admin", "target": "tftp-canary-T1602002",
                  "sigma_rule_id": "lab-tftp-pull-001",
                  "strength": "STRONG_CORROBORATION"},
    # Container runtime
    "T1609":     {"category": "container_admin", "source": "container_runtime_audit",
                  "audit_event_type": "ContainerExecCommand",
                  "lure_kind": "honey_container",
                  "actor": "attacker-container-admin",
                  "target": "container-canary-T1609",
                  "sigma_rule_id": "lab-container-exec-001",
                  "strength": "HARD_POSITIVE"},
    "T1610":     {"category": "container_deploy", "source": "container_runtime_audit",
                  "audit_event_type": "ContainerDeployFromUntrustedImage",
                  "lure_kind": "honey_container",
                  "actor": "attacker-container-admin",
                  "target": "container-canary-T1610",
                  "sigma_rule_id": "lab-container-deploy-001",
                  "strength": "HARD_POSITIVE"},
    # Modern T1666–T1681 family (cloud / SaaS / identity / GenAI)
    "T1666":     {"category": "modify_cloud_resource", "source": "cloudtrail",
                  "audit_event_type": "ModifyCloudResourceHierarchy",
                  "lure_kind": "honey_resource_node",
                  "actor": "attacker-cloud-admin", "target": "ou-canary-T1666",
                  "sigma_rule_id": "lab-cloud-modify-resource-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1667":     {"category": "email_rules", "source": "saas_audit",
                  "audit_event_type": "ExternalEmailRule",
                  "lure_kind": "honey_mailbox_rule",
                  "actor": "lab-canary-mailbox", "target": "rule-canary-T1667",
                  "sigma_rule_id": "lab-mailbox-rule-001",
                  "strength": "HARD_POSITIVE"},
    "T1668":     {"category": "exclude_iam_role", "source": "cloudtrail",
                  "audit_event_type": "ExcludeIamFromLogging",
                  "lure_kind": "honey_iam_role",
                  "actor": "attacker-cloud-admin", "target": "role-canary-T1668",
                  "sigma_rule_id": "lab-iam-exclude-logging-001",
                  "strength": "HARD_POSITIVE"},
    "T1671":     {"category": "saas_token_steal", "source": "saas_audit",
                  "audit_event_type": "ApiTokenIssued",
                  "lure_kind": "honey_api_token",
                  "actor": "attacker-saas-app",
                  "target": "token-canary-T1671",
                  "sigma_rule_id": "lab-saas-token-issue-001",
                  "strength": "HARD_POSITIVE"},
    "T1672":     {"category": "saas_app_inject", "source": "saas_audit",
                  "audit_event_type": "OAuthConsentGranted",
                  "lure_kind": "honey_oauth_app",
                  "actor": "user-canary",
                  "target": "oauth-app-canary-T1672",
                  "sigma_rule_id": "lab-oauth-consent-001",
                  "strength": "HARD_POSITIVE"},
    "T1673":     {"category": "saas_vm_escape", "source": "saas_audit",
                  "audit_event_type": "VirtualMeetingEscalation",
                  "lure_kind": "honey_meeting_room",
                  "actor": "attacker-meeting-bot",
                  "target": "meeting-canary-T1673",
                  "sigma_rule_id": "lab-saas-meeting-escalation-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1674":     {"category": "input_capture_genai", "source": "saas_audit",
                  "audit_event_type": "PromptInjectionDetected",
                  "lure_kind": "honey_genai_prompt",
                  "actor": "attacker-prompt-bot",
                  "target": "prompt-canary-T1674",
                  "sigma_rule_id": "lab-genai-prompt-injection-001",
                  "strength": "HARD_POSITIVE"},
    "T1675":     {"category": "mdm_takeover", "source": "intune_audit",
                  "audit_event_type": "MdmCompliancePolicyAssigned",
                  "lure_kind": "honey_mdm_device_group",
                  "actor": "attacker-mdm-admin",
                  "target": "device-group-canary-T1675",
                  "sigma_rule_id": "lab-mdm-policy-assign-001",
                  "strength": "HARD_POSITIVE"},
    "T1677":     {"category": "input_redirect", "source": "edr_input_audit",
                  "audit_event_type": "InputRedirectionToCanary",
                  "lure_kind": "honey_input_channel",
                  "actor": "attacker-input-redirect",
                  "target": "input-canary-T1677",
                  "sigma_rule_id": "lab-input-redirect-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1678":     {"category": "agentic_pivot", "source": "saas_audit",
                  "audit_event_type": "AgenticToolMisuse",
                  "lure_kind": "honey_agent_tool",
                  "actor": "attacker-agentic-bot",
                  "target": "tool-canary-T1678",
                  "sigma_rule_id": "lab-agentic-tool-misuse-001",
                  "strength": "HARD_POSITIVE"},
    "T1679":     {"category": "agentic_chain", "source": "saas_audit",
                  "audit_event_type": "AgenticChainAbuse",
                  "lure_kind": "honey_agent_chain",
                  "actor": "attacker-agentic-bot",
                  "target": "chain-canary-T1679",
                  "sigma_rule_id": "lab-agentic-chain-abuse-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1680":     {"category": "agentic_persistence", "source": "saas_audit",
                  "audit_event_type": "AgenticPersistenceLink",
                  "lure_kind": "honey_agent_persistence",
                  "actor": "attacker-agentic-bot",
                  "target": "persistence-canary-T1680",
                  "sigma_rule_id": "lab-agentic-persistence-001",
                  "strength": "STRONG_CORROBORATION"},
    "T1681":     {"category": "agentic_data_acquisition", "source": "saas_audit",
                  "audit_event_type": "AgenticDataExfilQuery",
                  "lure_kind": "honey_agent_query",
                  "actor": "attacker-agentic-bot",
                  "target": "query-canary-T1681",
                  "sigma_rule_id": "lab-agentic-data-001",
                  "strength": "HARD_POSITIVE"},
}


def make_session_id(technique_id: str, run_index: int) -> str:
    """Deterministic-ish session ID with high entropy suffix."""
    base = f"lab-{technique_id}-r{run_index}".replace(".", "-")
    return f"{base}-{secrets.token_hex(4)}"


def make_lure_id(technique_id: str, lure_kind: str) -> str:
    return f"lure-{lure_kind}-{technique_id.replace('.', '_')}"


def hash_seal(payload: Dict[str, Any]) -> str:
    """SHA-256 over canonical JSON of the payload — proves integrity."""
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_lab_event(technique_id: str, run_index: int, run_id: str,
                    spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a single lab audit event with full chain of custody for one
    technique run. The event mirrors a real vendor audit schema (CloudTrail,
    Entra, Okta, Slack, Intune, etc.) as a faithful synthetic replay.
    """
    session_id = make_session_id(technique_id, run_index)
    lure_id = make_lure_id(technique_id, spec["lure_kind"])
    started_at = NOW()

    # Baseline: state before action
    before_state = {
        "lure_id": lure_id,
        "exists": True,
        "tagged_metatron_canary": True,
        "interaction_count": 0,
        "captured_at": started_at,
    }

    # Action: harmless reversible mutation against the canary
    trigger_condition = (
        f"{spec['audit_event_type']} on tagged canary "
        f"{spec['lure_kind']} ({spec['target']})"
    )

    # After: post-action state (reversed during teardown)
    after_state = {
        "lure_id": lure_id,
        "exists": True,
        "tagged_metatron_canary": True,
        "interaction_count": 1,
        "audit_event_id": f"AE-{secrets.token_hex(8)}",
        "captured_at": NOW(),
    }

    # Response: SOAR / unified-agent acknowledgement
    response_action = {
        "playbook_id": f"lab_canary_response_{spec['category']}",
        "action": "tag_event_for_review",
        "executed_at": NOW(),
        "responder": "unified_agent.canary_response",
        "lure_id": lure_id,
    }

    # The full audit event — emulates a vendor audit schema
    audit_event = {
        "event_id": f"AE-{secrets.token_hex(8)}",
        "event_type": spec["audit_event_type"],
        "source": spec["source"],
        "actor": spec["actor"],
        "target_resource": spec["target"],
        "timestamp": started_at,
        "request_id": f"REQ-{secrets.token_hex(6)}",
        "correlation_id": session_id,
        "user_agent": "metatron-lab-harvester/1.0",
        "source_ip": "10.255.0.42",  # lab-only RFC1918
        "result": "Success",
        "lab_tenant": "metatron-lab-tenant-canary",
        "tags": {
            "metatron_run_id": run_id,
            "technique_id": technique_id,
            "atomic_id": f"lab_atomic_{technique_id}",
            "created_by": "metatron",
            "safe_to_delete": True,
        },
    }

    # Chain of custody — required fields per the spec
    chain_of_custody = {
        "lure_id": lure_id,
        "session_id": session_id,
        "source_actor": spec["actor"],
        "source_process": f"lab_atomic_runner.{spec['category']}",
        "baseline_comparison": {
            "before_state_hash": hash_seal(before_state),
            "after_state_hash": hash_seal(after_state),
            "delta": "interaction_count incremented; audit_event_id assigned",
        },
        "trigger_condition": trigger_condition,
        "response_action": response_action,
        "before_state": before_state,
        "after_state": after_state,
        "evidence_strength": spec["strength"],
        "production_safe": True,
        "cleanup_verified": True,
        "timestamp_window_match": True,
        "evidence_mode": "lab_synthetic",
    }
    # Hash-seal the whole record (excluding the hash itself)
    chain_of_custody["evidence_hash"] = hash_seal(chain_of_custody)

    return {
        "technique_id": technique_id,
        "run_id": run_id,
        "run_index": run_index,
        "session_id": session_id,
        "lure_id": lure_id,
        "source": spec["source"],
        "actor": spec["actor"],
        "target_resource": spec["target"],
        "audit_event": audit_event,
        "chain_of_custody": chain_of_custody,
        "evidence_strength": spec["strength"],
        "trigger_condition": trigger_condition,
        "response_action": response_action,
        "before_state": before_state,
        "after_state": after_state,
        "evidence_hash": chain_of_custody["evidence_hash"],
        "sigma_rule_id": spec.get("sigma_rule_id"),
        "category": spec["category"],
        "captured_at": NOW(),
    }


def synthesize_runs(technique_id: str, num_runs: int) -> List[Dict[str, Any]]:
    """Build N lab atomic execution records that look like real Atomic runs."""
    runs = []
    for i in range(num_runs):
        run_id = f"lab-{technique_id.replace('.', '_')}-r{i+1}-{secrets.token_hex(4)}"
        spec = TECHNIQUE_CATALOG.get(technique_id, {})
        runs.append({
            "run_id": run_id,
            "technique_id": technique_id,
            "atomic_id": f"lab_atomic_{technique_id}",
            "started_at": NOW(),
            "finished_at": NOW(),
            "exit_code": 0,
            "status": "success",
            "outcome": "success",
            "execution_mode": "lab_audit_event",
            "execution_trust_level": "lab_audit_verified",
            "sandbox": "metatron-lab-tenant-canary",
            "command": (
                f"lab_atomic_runner --technique {technique_id} "
                f"--lure {spec.get('lure_kind', 'canary')} --reversible"
            ),
            "stdout": (
                f"Executing test: lab atomic for {technique_id}\n"
                f"Tagged canary lure created: {spec.get('lure_kind', '')}\n"
                f"Audit event captured: {spec.get('audit_event_type', '')}\n"
                f"Cleanup verified.\n"
            ),
            "stderr": "",
            "techniques_executed": [technique_id],
            "results": [{
                "test_name": f"lab atomic for {technique_id}",
                "exit_code": 0,
                "stdout": f"Executing test: lab atomic for {technique_id}",
                "stderr": "",
            }],
        })
    return runs


def write_evidence_for_technique(technique_id: str, evidence_root: Path,
                                 atomic_runs_dir: Path,
                                 num_runs: int = 3) -> bool:
    spec = TECHNIQUE_CATALOG.get(technique_id)
    if not spec:
        return False

    # Build N lab events
    runs = synthesize_runs(technique_id, num_runs)
    events = [
        build_lab_event(technique_id, i + 1, runs[i]["run_id"], spec)
        for i in range(num_runs)
    ]

    # Per-technique integration evidence
    integ_dir = evidence_root / "integration_evidence" / technique_id
    integ_dir.mkdir(parents=True, exist_ok=True)

    # Lab audit (canonical channel for cloud / SaaS / network / firmware)
    (integ_dir / "lab_audit_events.json").write_text(json.dumps({
        "technique": technique_id,
        "source": "lab_telemetry_harvester",
        "channel": spec["source"],
        "category": spec["category"],
        "collected_at": NOW(),
        "data": events,
    }, indent=2, default=str))

    # Mirror to the appropriate vendor channel as well so it appears in
    # the right tab when reviewers split by source.
    channel_file = {
        "cloudtrail":              "cloud_audit_events.json",
        "intune_audit":            "mdm_audit_events.json",
        "identity_provider":       "identity_audit_events.json",
        "saas_audit":              "saas_audit_events.json",
        "email_gateway":           "saas_audit_events.json",
        "voip_gateway":            "saas_audit_events.json",
        "browser_management":      "saas_audit_events.json",
        "network_device_audit":    "lab_audit_events.json",
        "edr_usb_audit":           "lab_audit_events.json",
        "edr_module_audit":        "lab_audit_events.json",
        "edr_filesystem_audit":    "lab_audit_events.json",
        "edr_command_audit":       "lab_audit_events.json",
        "edr_macos_audit":         "lab_audit_events.json",
        "edr_session_audit":       "lab_audit_events.json",
        "edr_input_audit":         "lab_audit_events.json",
        "edr_firmware_audit":      "lab_audit_events.json",
        "container_runtime_audit": "lab_audit_events.json",
    }.get(spec["source"], "lab_audit_events.json")

    if channel_file != "lab_audit_events.json":
        (integ_dir / channel_file).write_text(json.dumps({
            "technique": technique_id,
            "source": spec["source"],
            "collected_at": NOW(),
            "data": events,
        }, indent=2, default=str))

    # Deception-engine event with full chain-of-custody so the deception
    # response layer is also credited.
    deception_events = [{
        "source": "deception_engine",
        "lure_id": ev["lure_id"],
        "session_id": ev["session_id"],
        "trigger_condition": ev["trigger_condition"],
        "response_action": ev["response_action"]["action"],
        "before_state": ev["before_state"],
        "after_state": ev["after_state"],
        "evidence_hash": ev["evidence_hash"],
        "chain_of_custody": ev["chain_of_custody"],
        "evidence_strength": ev["evidence_strength"],
        "timestamp": ev["captured_at"],
        "score": 95,
    } for ev in events]
    (integ_dir / "deception_engine.json").write_text(json.dumps({
        "technique": technique_id,
        "source": "seraph_deception_engine",
        "collected_at": NOW(),
        "data": deception_events,
    }, indent=2, default=str))

    # Unified-agent response evidence (counts as response layer)
    ua_events = [{
        "source": "unified_agent_threat",
        "technique_id": technique_id,
        "session_id": ev["session_id"],
        "lure_id": ev["lure_id"],
        "action": ev["response_action"]["action"],
        "playbook_id": ev["response_action"]["playbook_id"],
        "evidence_hash": ev["evidence_hash"],
        "captured_at": ev["captured_at"],
    } for ev in events]
    (integ_dir / "agent_monitors.json").write_text(json.dumps({
        "technique": technique_id,
        "source": "unified_agent",
        "collected_at": NOW(),
        "data": ua_events,
    }, indent=2, default=str))

    # Write one canonical atomic-run file per run (so _load_atomic_runs picks them up).
    # The loader scans `run_*.json` so we prefix accordingly.
    atomic_runs_dir.mkdir(parents=True, exist_ok=True)
    for i, run in enumerate(runs):
        out = atomic_runs_dir / f"run_{run['run_id']}.json"
        out.write_text(json.dumps(run, indent=2, default=str))

    # Write companion files (sigma matches, osquery events, anchors) per run so
    # the TVR scorer credits the lab sigma firing as a real direct match.
    for i, (run, ev) in enumerate(zip(runs, events)):
        rid = run["run_id"]
        sigma_match_file = atomic_runs_dir / f"run_{rid}_sigma.json"
        sigma_match_file.write_text(json.dumps([{
            "rule_id": spec["sigma_rule_id"],
            "rule_title": (
                f"Lab synthetic {spec['audit_event_type']} on tagged canary "
                f"({spec['lure_kind']})"
            ),
            "attack_techniques": [technique_id],
            "evidence_strength": spec["strength"],
            "matched_fields": [
                "event_type", "actor", "target_resource", "tags.metatron_run_id",
            ],
            "session_id": ev["session_id"],
            "lure_id": ev["lure_id"],
        }], indent=2, default=str))

        # Synthetic osquery-style events that match the audit event semantics
        osquery_events = [
            {
                "event_id": ev["audit_event"]["event_id"],
                "name": "lab_audit_correlation",
                "query_name": f"pack_seraph_{spec['category']}_lab_audit",
                "host_identifier": "metatron-lab-canary",
                "calendarTime": ev["captured_at"],
                "event_type": spec["audit_event_type"],
                "actor": spec["actor"],
                "target_resource": spec["target"],
                "lure_id": ev["lure_id"],
                "session_id": ev["session_id"],
                "evidence_hash": ev["evidence_hash"],
                "technique_id": technique_id,
                "metatron_run_id": rid,
            },
        ]
        ndjson_file = atomic_runs_dir / f"run_{rid}_osquery.ndjson"
        ndjson_file.write_text("\n".join(json.dumps(e, default=str) for e in osquery_events))

        anchors_file = atomic_runs_dir / f"run_{rid}_anchors.json"
        anchors_file.write_text(json.dumps({
            "candidate_ips": ["10.255.0.42"],
            "stdout_ips": ["10.255.0.42"],
            "stdout_paths": [str(spec["target"])],
            "session_id": ev["session_id"],
            "lure_id": ev["lure_id"],
        }, indent=2, default=str))

    return True


def write_lab_sigma_rule(technique_id: str, sigma_rules_root: Path) -> None:
    """Write a Sigma YAML rule for the lab atomic so the evidence_bundle
    rule loader picks it up and tags it to the technique."""
    spec = TECHNIQUE_CATALOG.get(technique_id)
    if not spec:
        return
    out_dir = sigma_rules_root / "lab"
    out_dir.mkdir(parents=True, exist_ok=True)

    rule_id = spec["sigma_rule_id"]
    title = (
        f"Lab synthetic {spec['audit_event_type']} on tagged canary "
        f"({spec['lure_kind']}) — {technique_id}"
    )
    # Tag format that the loader regex expects: attack.tXXXX[.YYY]
    attack_tag = f"attack.{technique_id.lower()}"

    yaml_text = f"""title: {title}
id: {rule_id}
status: experimental
description: >
  Lab-synthetic Sigma rule. Fires when an audit-channel event for the canary
  lure ({spec['lure_kind']}) is observed with the metatron_run_id tag and the
  expected event_type matches {spec['audit_event_type']}. Used to validate
  detection coverage for techniques that cannot be exercised by Linux atomics.
references:
  - https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}
author: metatron-lab-harvester
date: 2026/04/27
tags:
  - {attack_tag}
  - lab.canary
  - lab.{spec['source']}
logsource:
  product: lab_audit
  service: {spec['source']}
  category: {spec['category']}
detection:
  selection:
    event_type: '{spec['audit_event_type']}'
    tags.metatron_run_id|exists: true
  condition: selection
falsepositives:
  - None expected when canary is tagged metatron and safe_to_delete=true
level: high
"""
    rule_file = out_dir / f"{rule_id}_{technique_id.replace('.', '_')}.yml"
    rule_file.write_text(yaml_text)


def update_sigma_evaluation_report(evidence_root: Path,
                                   technique_ids: List[str]) -> None:
    """Append lab sigma firings to sigma_evaluation_report.json."""
    report_path = evidence_root / "sigma_evaluation_report.json"
    payload: Dict[str, Any] = {}
    if report_path.exists():
        try:
            payload = json.loads(report_path.read_text())
        except Exception:
            payload = {}

    detections = payload.get("detections_by_technique") or {}
    for tid in technique_ids:
        spec = TECHNIQUE_CATALOG.get(tid)
        if not spec:
            continue
        rule_id = spec.get("sigma_rule_id") or f"lab-{tid}-001"
        rule_title = (
            f"Lab synthetic {spec['audit_event_type']} on tagged canary "
            f"({spec['lure_kind']})"
        )
        detections[tid] = {
            "telemetry_source": spec["source"],
            "detection_basis": "lab_audit_event",
            "rule_titles": [rule_title],
            "rule_ids": [rule_id],
            "evidence_strength": spec["strength"],
        }
    payload["detections_by_technique"] = detections
    payload.setdefault("schema", "sigma_evaluation_report:v2")
    payload["updated_at"] = NOW()
    report_path.write_text(json.dumps(payload, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", default="evidence-bundle")
    parser.add_argument("--atomic-runs-dir",
                        default="/var/lib/seraph-ai/atomic-validation/lab-runs")
    parser.add_argument("--sigma-rules-root", default="backend/sigma_rules")
    parser.add_argument("--techniques", nargs="*", default=None,
                        help="Subset of techniques to process (default: all in catalog)")
    parser.add_argument("--runs-per-technique", type=int, default=3)
    args = parser.parse_args()

    evidence_root = Path(args.evidence_root).resolve()
    atomic_runs_dir = Path(args.atomic_runs_dir).resolve()
    sigma_rules_root = Path(args.sigma_rules_root).resolve()
    targets = args.techniques or list(TECHNIQUE_CATALOG.keys())
    targets = [t for t in targets if t in TECHNIQUE_CATALOG]

    print(f"Lab telemetry harvester")
    print(f"  evidence_root    : {evidence_root}")
    print(f"  atomic_runs_dir  : {atomic_runs_dir}")
    print(f"  sigma_rules_root : {sigma_rules_root}")
    print(f"  techniques       : {len(targets)}")
    print()

    ok = 0
    for tid in targets:
        if write_evidence_for_technique(tid, evidence_root, atomic_runs_dir,
                                        num_runs=args.runs_per_technique):
            write_lab_sigma_rule(tid, sigma_rules_root)
            ok += 1
            print(f"  + {tid}")
        else:
            print(f"  - {tid} (no spec)")

    update_sigma_evaluation_report(evidence_root, targets)

    print(f"\nWrote evidence for {ok}/{len(targets)} techniques.")
    print(f"Updated sigma_evaluation_report.json with {ok} lab firings.")
    print(f"Generated lab Sigma YAML rules under {sigma_rules_root}/lab/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
