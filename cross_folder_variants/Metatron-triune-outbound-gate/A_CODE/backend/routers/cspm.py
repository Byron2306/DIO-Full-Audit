"""
CSPM (Cloud Security Posture Management) API Router
====================================================
REST API endpoints for multi-cloud security posture management.

Endpoints:
- POST /api/v1/cspm/scan - Start a new scan
- GET /api/v1/cspm/scans - List scan history
- GET /api/v1/cspm/scans/{scan_id} - Get scan details
- GET /api/v1/cspm/posture - Get overall security posture
- GET /api/v1/cspm/findings - List all findings
- GET /api/v1/cspm/findings/{finding_id} - Get finding details
- PUT /api/v1/cspm/findings/{finding_id}/status - Update finding status
- GET /api/v1/cspm/resources - List discovered resources
- GET /api/v1/cspm/compliance/{framework} - Get compliance report
- GET /api/v1/cspm/providers - List configured providers
- POST /api/v1/cspm/providers - Configure a provider
- DELETE /api/v1/cspm/providers/{provider} - Remove provider
- GET /api/v1/cspm/checks - List available security checks
- PUT /api/v1/cspm/checks/{check_id} - Enable/disable check
- GET /api/v1/cspm/export - Export findings
- GET /api/v1/cspm/dashboard - Dashboard statistics
"""

import logging
import os
import base64
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from enum import Enum
from cryptography.fernet import Fernet

from cspm_engine import (
    CSPMEngine, get_cspm_engine,
    CloudProvider, Severity, ResourceType, ComplianceFramework,
    FindingStatus, CloudCredentials, Finding, ScanResult, CloudResource
)
from cspm_aws_scanner import AWSScanner
from cspm_azure_scanner import AzureScanner
from cspm_gcp_scanner import GCPScanner
from .dependencies import get_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cspm", tags=["CSPM"])


def _normalize_framework(framework: str) -> Optional[ComplianceFramework]:
    """Accept common shorthand values from clients and map to canonical framework enums."""
    key = framework.strip().lower().replace("-", "_").replace(" ", "")
    aliases = {
        "cis": ComplianceFramework.CIS_AWS_2_0,
        "cisaws": ComplianceFramework.CIS_AWS_2_0,
        "cisazure": ComplianceFramework.CIS_AZURE_2_0,
        "cisgcp": ComplianceFramework.CIS_GCP_2_0,
        "nist": ComplianceFramework.NIST_800_53,
        "nist80053": ComplianceFramework.NIST_800_53,
        "nistcsf": ComplianceFramework.NIST_CSF,
        "soc2": ComplianceFramework.SOC2,
        "pcidss": ComplianceFramework.PCI_DSS_4_0,
        "pcidss4": ComplianceFramework.PCI_DSS_4_0,
        "hipaa": ComplianceFramework.HIPAA,
        "gdpr": ComplianceFramework.GDPR,
        "iso27001": ComplianceFramework.ISO_27001,
    }

    if key in aliases:
        return aliases[key]

    for fw in ComplianceFramework:
        normalized = fw.value.lower().replace("-", "_").replace(" ", "")
        if key == normalized:
            return fw

    return None


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ProviderConfig(BaseModel):
    """Cloud provider configuration"""
    provider: CloudProvider
    account_id: str
    region: Optional[str] = None
    
    # AWS
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_role_arn: Optional[str] = None
    
    # Azure
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    
    # GCP
    gcp_project_id: Optional[str] = None
    gcp_service_account_key_path: Optional[str] = None


class ScanRequest(BaseModel):
    """Request to start a CSPM scan"""
    providers: Optional[List[CloudProvider]] = None
    regions: Optional[List[str]] = None
    resource_types: Optional[List[ResourceType]] = None
    check_ids: Optional[List[str]] = None
    severity_filter: Optional[List[Severity]] = None


class FindingStatusUpdate(BaseModel):
    """Update finding status"""
    status: FindingStatus
    reason: Optional[str] = None
    updated_by: str = "system"


class CheckToggle(BaseModel):
    """Enable/disable a check"""
    enabled: bool
    auto_remediate: bool = False


class PostureResponse(BaseModel):
    """Security posture response"""
    overall_score: float
    grade: str
    total_resources: int
    total_findings: int
    open_findings: int
    severity_breakdown: Dict[str, int]
    provider_breakdown: Dict[str, int]
    last_scan: Optional[str]
    trend: str


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    posture: PostureResponse
    recent_scans: List[Dict[str, Any]]
    top_risks: List[Dict[str, Any]]
    compliance_summary: Dict[str, float]
    resource_counts: Dict[str, int]
    findings_by_category: Dict[str, int]


# =============================================================================
# STATE
# =============================================================================

# In-memory state (would use database in production)
_configured_providers: Dict[CloudProvider, CloudCredentials] = {}
_active_scans: Dict[str, ScanResult] = {}
_providers_loaded_from_db = False

_SCAN_COLLECTION = "cspm_scans"
_SCAN_TERMINAL_STATUSES = {"completed", "failed"}
_FINDING_COLLECTION = "cspm_findings"
_FINDING_TERMINAL_STATUSES = {"resolved", "suppressed", "false_positive"}

_PROVIDER_COLLECTION = "cspm_provider_configs"
_ENC_PREFIX = "enc:v1:"

_SECRET_FIELDS = {
    CloudProvider.AWS: {"aws_secret_key", "aws_session_token"},
    CloudProvider.AZURE: {"azure_client_secret"},
    CloudProvider.GCP: {"gcp_service_account_key"},
}


def _scan_transition_entry(
    from_status: Optional[str],
    to_status: str,
    actor: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor,
        "reason": reason,
    }
    if metadata:
        entry["metadata"] = metadata
    return entry


def _finding_transition_entry(
    from_status: Optional[str],
    to_status: str,
    actor: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor,
        "reason": reason,
    }
    if metadata:
        entry["metadata"] = metadata
    return entry


def _finding_doc_from_finding(finding: Finding) -> Dict[str, Any]:
    data = finding.to_dict()
    status = str(data.get("status") or FindingStatus.OPEN.value)
    now = datetime.now(timezone.utc).isoformat()
    data.update(
        {
            "state_version": int(data.get("state_version") or 1),
            "state_transition_log": data.get("state_transition_log")
            or [
                _finding_transition_entry(
                    from_status=None,
                    to_status=status,
                    actor="system:cspm",
                    reason="finding discovered by scan",
                )
            ],
            "updated_at": now,
        }
    )
    return data


async def _persist_scan_findings(results: Dict[CloudProvider, ScanResult]) -> None:
    db = get_db()
    if db is None:
        return

    for _provider, result in results.items():
        for finding in result.findings:
            doc = _finding_doc_from_finding(finding)
            await db[_FINDING_COLLECTION].update_one(
                {"finding_id": doc.get("finding_id")},
                {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )


async def _get_finding_record(finding_id: str) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        return {}
    return await db[_FINDING_COLLECTION].find_one({"finding_id": finding_id}, {"_id": 0}) or {}


async def _ensure_finding_state_fields(
    finding_id: str,
    *,
    actor: str,
    reason: str,
) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        return {}

    finding = await db[_FINDING_COLLECTION].find_one({"finding_id": finding_id}, {"_id": 0})
    if not finding:
        return {}

    if finding.get("state_version") is not None and finding.get("state_transition_log") is not None:
        return finding

    current_status = str(finding.get("status") or FindingStatus.OPEN.value)
    bootstrap = {
        "state_version": int(finding.get("state_version") or 1),
        "state_transition_log": finding.get("state_transition_log")
        or [
            _finding_transition_entry(
                from_status=None,
                to_status=current_status,
                actor=actor,
                reason=reason,
            )
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[_FINDING_COLLECTION].update_one({"finding_id": finding_id}, {"$set": bootstrap})
    return await db[_FINDING_COLLECTION].find_one({"finding_id": finding_id}, {"_id": 0}) or {}


async def _transition_finding_status(
    finding_id: str,
    *,
    expected_statuses: List[str],
    next_status: str,
    actor: str,
    reason: str,
    expected_state_version: Optional[int] = None,
    transition_metadata: Optional[Dict[str, Any]] = None,
    extra_updates: Optional[Dict[str, Any]] = None,
) -> bool:
    db = get_db()
    if db is None:
        return False

    finding = await db[_FINDING_COLLECTION].find_one({"finding_id": finding_id}, {"_id": 0})
    if not finding:
        return False

    from_status = str(finding.get("status") or "").lower().strip()
    if from_status not in expected_statuses:
        return False

    resolved_version = expected_state_version
    if resolved_version is None:
        resolved_version = int(finding.get("state_version") or 0)

    query: Dict[str, Any] = {
        "finding_id": finding_id,
        "status": {"$in": expected_statuses},
    }
    if resolved_version <= 0:
        query["$or"] = [{"state_version": {"$exists": False}}, {"state_version": 0}]
    else:
        query["state_version"] = resolved_version

    set_doc = {
        "status": next_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_updates:
        set_doc.update(extra_updates)

    result = await db[_FINDING_COLLECTION].update_one(
        query,
        {
            "$set": set_doc,
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": _finding_transition_entry(
                    from_status=from_status,
                    to_status=next_status,
                    actor=actor,
                    reason=reason,
                    metadata=transition_metadata,
                )
            },
        },
    )
    return bool(getattr(result, "modified_count", 0))


async def _get_scan_record(scan_id: str) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        return {}
    return await db[_SCAN_COLLECTION].find_one({"scan_id": scan_id}, {"_id": 0}) or {}


async def _create_scan_record(scan_id: str, request: ScanRequest, providers: List[str]) -> None:
    db = get_db()
    if db is None:
        return

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "scan_id": scan_id,
        "providers": providers,
        "regions": request.regions or [],
        "resource_types": [r.value for r in (request.resource_types or [])],
        "check_ids": request.check_ids or [],
        "severity_filter": [s.value for s in (request.severity_filter or [])],
        "status": "started",
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "error_message": None,
        "provider_results": [],
        "resources_scanned": 0,
        "findings_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "state_version": 1,
        "state_transition_log": [
            _scan_transition_entry(
                from_status=None,
                to_status="started",
                actor="system:cspm",
                reason="scan requested",
                metadata={"providers": providers},
            )
        ],
    }
    await db[_SCAN_COLLECTION].update_one({"scan_id": scan_id}, {"$set": doc}, upsert=True)


def _generate_demo_cspm_data() -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    provider = CloudProvider.AWS
    resource = CloudResource(
        resource_id="demo-s3-public-bucket",
        resource_type=ResourceType.STORAGE_BUCKET,
        provider=provider,
        region="us-east-1",
        account_id="demo-account",
        name="public-asset-bucket",
        arn="arn:aws:s3:::public-asset-bucket",
        tags={"environment": "demo", "owner": "security-team"},
        created_at=now,
        is_public=True,
        is_encrypted=False,
    )

    finding = Finding(
        finding_id="demo-finding-1",
        title="Publicly exposed S3 bucket",
        description="A storage bucket is publicly accessible and may expose sensitive data.",
        severity=Severity.HIGH,
        provider=provider,
        resource=resource,
        check_id="cspm-aws-001",
        check_title="Public S3 Bucket",
        category="storage",
        subcategory="storage_bucket",
        mitre_techniques=["T1537"],
        status=FindingStatus.OPEN,
        risk_score=81,
        evidence={"policy": "PublicRead", "issue": "bucket acl allows public read"},
    )

    scan_result = ScanResult(
        scan_id=f"demo-scan-{uuid.uuid4()}",
        provider=provider,
        account_id="demo-account",
        regions=["us-east-1"],
        started_at=now,
        completed_at=now,
        resources_scanned=1,
        findings_count=1,
        critical_count=0,
        high_count=1,
        medium_count=0,
        low_count=0,
        findings=[finding],
        resources=[resource],
        compliance_scores={"CIS_AWS_2_0": 65.0},
        status="completed",
    )

    return {
        "resources": [resource],
        "findings": [finding],
        "scan_result": scan_result,
    }


async def _persist_demo_scan(scan_result: ScanResult) -> None:
    db = get_db()
    if db is None:
        return

    await db[_SCAN_COLLECTION].update_one(
        {"scan_id": scan_result.scan_id},
        {"$set": scan_result.to_dict()},
        upsert=True,
    )

    for finding in scan_result.findings:
        doc = _finding_doc_from_finding(finding)
        await db[_FINDING_COLLECTION].update_one(
            {"finding_id": doc.get("finding_id")},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )


async def _transition_scan_state(
    scan_id: str,
    *,
    expected_statuses: List[str],
    next_status: str,
    actor: str,
    reason: str,
    expected_state_version: Optional[int] = None,
    extra_updates: Optional[Dict[str, Any]] = None,
    transition_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    db = get_db()
    if db is None:
        return False

    scan = await db[_SCAN_COLLECTION].find_one({"scan_id": scan_id}, {"_id": 0})
    if not scan:
        return False

    from_status = str(scan.get("status") or "").lower().strip()
    if from_status not in expected_statuses:
        return False

    resolved_version = expected_state_version
    if resolved_version is None:
        resolved_version = int(scan.get("state_version") or 0)

    query: Dict[str, Any] = {
        "scan_id": scan_id,
        "status": {"$in": expected_statuses},
    }
    if resolved_version <= 0:
        query["$or"] = [{"state_version": {"$exists": False}}, {"state_version": 0}]
    else:
        query["state_version"] = resolved_version

    set_doc = {
        "status": next_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if next_status in _SCAN_TERMINAL_STATUSES:
        set_doc["completed_at"] = datetime.now(timezone.utc).isoformat()
    if extra_updates:
        set_doc.update(extra_updates)

    result = await db[_SCAN_COLLECTION].update_one(
        query,
        {
            "$set": set_doc,
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": _scan_transition_entry(
                    from_status=from_status,
                    to_status=next_status,
                    actor=actor,
                    reason=reason,
                    metadata=transition_metadata,
                )
            },
        },
    )
    return bool(getattr(result, "modified_count", 0))


def _get_fernet() -> Fernet:
    """Build an encryption helper from env; falls back to JWT secret for dev compatibility."""
    material = (os.environ.get("CSPM_CONFIG_ENCRYPTION_KEY") or os.environ.get("JWT_SECRET") or "dev-cspm-key").encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)


def _encrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if isinstance(value, str) and value.startswith(_ENC_PREFIX):
        return value
    token = _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def _decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if not isinstance(value, str) or not value.startswith(_ENC_PREFIX):
        return value
    token = value[len(_ENC_PREFIX):]
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.warning("Failed to decrypt CSPM provider secret; leaving value unset")
        return None


def _mask_value(value: Optional[str], keep_tail: int = 4) -> Optional[str]:
    if not value:
        return None
    if len(value) <= keep_tail:
        return "*" * len(value)
    return "*" * (len(value) - keep_tail) + value[-keep_tail:]


def _scanner_for(provider: CloudProvider, credentials: CloudCredentials):
    if provider == CloudProvider.AWS:
        return AWSScanner(credentials)
    if provider == CloudProvider.AZURE:
        return AzureScanner(credentials)
    if provider == CloudProvider.GCP:
        return GCPScanner(credentials)
    return None


async def _load_providers_from_db(force: bool = False) -> None:
    """Load persisted provider configs into memory and scanner registry."""
    global _providers_loaded_from_db
    if _providers_loaded_from_db and not force:
        return

    db = get_db()
    if db is None:
        return

    docs = await db[_PROVIDER_COLLECTION].find({}, {"_id": 0}).to_list(100)
    _configured_providers.clear()

    engine = get_cspm_engine()
    engine.scanners.clear()

    for doc in docs:
        provider_raw = doc.get("provider")
        if not provider_raw:
            continue
        try:
            provider = CloudProvider(provider_raw)
        except ValueError:
            continue

        # Decrypt only fields we consider secrets.
        for field_name in _SECRET_FIELDS.get(provider, set()):
            if field_name in doc:
                doc[field_name] = _decrypt_secret(doc.get(field_name))

        try:
            creds = CloudCredentials(
                provider=provider,
                account_id=doc.get("account_id"),
                region=doc.get("region"),
                aws_access_key=doc.get("aws_access_key"),
                aws_secret_key=doc.get("aws_secret_key"),
                aws_role_arn=doc.get("aws_role_arn"),
                azure_tenant_id=doc.get("azure_tenant_id"),
                azure_client_id=doc.get("azure_client_id"),
                azure_client_secret=doc.get("azure_client_secret"),
                azure_subscription_id=doc.get("azure_subscription_id"),
                gcp_project_id=doc.get("gcp_project_id"),
                gcp_service_account_key=doc.get("gcp_service_account_key"),
            )
        except Exception as exc:
            logger.warning(f"Skipping invalid persisted CSPM provider config for {provider_raw}: {exc}")
            continue

        if not creds.validate():
            logger.warning(f"Skipping persisted CSPM provider config for {provider.value}: validation failed")
            continue

        _configured_providers[provider] = creds
        scanner = _scanner_for(provider, creds)
        if scanner:
            engine.register_scanner(scanner)

    _providers_loaded_from_db = True


async def _persist_provider_to_db(provider: CloudProvider, credentials: CloudCredentials) -> None:
    db = get_db()
    if db is None:
        return

    doc = {
        "provider": provider.value,
        "account_id": credentials.account_id,
        "region": credentials.region,
        "aws_access_key": credentials.aws_access_key,
        "aws_secret_key": credentials.aws_secret_key,
        "aws_role_arn": credentials.aws_role_arn,
        "azure_tenant_id": credentials.azure_tenant_id,
        "azure_client_id": credentials.azure_client_id,
        "azure_client_secret": credentials.azure_client_secret,
        "azure_subscription_id": credentials.azure_subscription_id,
        "gcp_project_id": credentials.gcp_project_id,
        "gcp_service_account_key": credentials.gcp_service_account_key,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Encrypt only secret values before storing.
    for field_name in _SECRET_FIELDS.get(provider, set()):
        if field_name in doc:
            doc[field_name] = _encrypt_secret(doc.get(field_name))

    await db[_PROVIDER_COLLECTION].update_one(
        {"provider": provider.value},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


def _provider_summary(provider: CloudProvider, creds: CloudCredentials) -> Dict[str, Any]:
    """Return a safe provider summary for API responses (no plaintext secrets)."""
    summary = {
        "provider": provider.value,
        "account_id": creds.account_id,
        "configured": True,
    }

    if provider == CloudProvider.AWS:
        summary["details"] = {
            "aws_access_key": _mask_value(creds.aws_access_key),
            "aws_role_arn": creds.aws_role_arn,
            "has_secret_key": bool(creds.aws_secret_key),
        }
    elif provider == CloudProvider.AZURE:
        summary["details"] = {
            "azure_tenant_id": _mask_value(creds.azure_tenant_id),
            "azure_client_id": _mask_value(creds.azure_client_id),
            "azure_subscription_id": _mask_value(creds.azure_subscription_id),
            "has_client_secret": bool(creds.azure_client_secret),
        }
    elif provider == CloudProvider.GCP:
        summary["details"] = {
            "gcp_project_id": creds.gcp_project_id,
            "has_service_account_key": bool(creds.gcp_service_account_key),
        }

    return summary


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/providers", summary="Configure a cloud provider")
async def configure_provider(config: ProviderConfig) -> Dict[str, Any]:
    """
    Configure credentials for a cloud provider.
    
    - **provider**: Cloud provider (aws, azure, gcp)
    - **account_id**: Account/subscription/project identifier
    - **credentials**: Provider-specific credentials
    """
    await _load_providers_from_db()

    credentials = CloudCredentials(
        provider=config.provider,
        account_id=config.account_id,
        region=config.region,
        aws_access_key=config.aws_access_key,
        aws_secret_key=config.aws_secret_key,
        aws_role_arn=config.aws_role_arn,
        azure_tenant_id=config.azure_tenant_id,
        azure_client_id=config.azure_client_id,
        azure_client_secret=config.azure_client_secret,
        azure_subscription_id=config.azure_subscription_id,
        gcp_project_id=config.gcp_project_id,
        gcp_service_account_key=config.gcp_service_account_key_path,
    )
    
    if not credentials.validate():
        raise HTTPException(status_code=400, detail="Invalid credentials for provider")
    
    # Store credentials
    _configured_providers[config.provider] = credentials

    # Persist provider config with encrypted secrets.
    await _persist_provider_to_db(config.provider, credentials)
    
    # Register scanner with engine
    engine = get_cspm_engine()
    scanner = _scanner_for(config.provider, credentials)
    if scanner:
        engine.register_scanner(scanner)
    
    logger.info(f"Configured provider: {config.provider.value}")
    
    return {
        "status": "configured",
        "provider": config.provider.value,
        "account_id": config.account_id,
        "secrets_stored": "encrypted",
    }


@router.get("/providers", summary="List configured providers")
async def list_providers() -> List[Dict[str, Any]]:
    """Get list of configured cloud providers"""
    await _load_providers_from_db()
    return [_provider_summary(provider, creds) for provider, creds in _configured_providers.items()]


@router.delete("/providers/{provider}", summary="Remove provider configuration")
async def remove_provider(provider: CloudProvider) -> Dict[str, str]:
    """Remove a cloud provider configuration"""
    await _load_providers_from_db()
    if provider in _configured_providers:
        del _configured_providers[provider]
        engine = get_cspm_engine()
        if provider in engine.scanners:
            del engine.scanners[provider]

        db = get_db()
        if db is not None:
            await db[_PROVIDER_COLLECTION].delete_one({"provider": provider.value})
        return {"status": "removed", "provider": provider.value}
    raise HTTPException(status_code=404, detail="Provider not configured")


@router.post("/scan", summary="Start a CSPM scan")
async def start_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Start a new cloud security posture scan.
    
    - **providers**: List of providers to scan (default: all configured)
    - **regions**: Specific regions to scan (default: all)
    - **resource_types**: Filter by resource types
    - **check_ids**: Specific checks to run
    - **severity_filter**: Filter findings by severity
    """
    await _load_providers_from_db()
    engine = get_cspm_engine()
    
    if not engine.scanners:
        demo_data = _generate_demo_cspm_data()
        demo_scan = demo_data["scan_result"]
        engine.findings_db.update({f.finding_id: f for f in demo_data["findings"]})
        engine.resources_db.update({r.resource_id: r for r in demo_data["resources"]})
        engine.scan_history.append(demo_scan)

        await _persist_demo_scan(demo_scan)

        return {
            "status": "demo_completed",
            "scan_id": demo_scan.scan_id,
            "providers": [demo_scan.provider.value],
            "started_at": demo_scan.started_at,
            "completed_at": demo_scan.completed_at,
            "message": "Demo cloud scan completed. Sample posture and findings have been populated.",
        }

    # Generate scan ID
    scan_id = str(uuid.uuid4())
    selected_providers = [p.value for p in (request.providers or list(engine.scanners.keys()))]
    await _create_scan_record(scan_id, request, selected_providers)
    
    # Start scan in background
    async def run_scan():
        try:
            started_record = await _get_scan_record(scan_id)
            transitioned = await _transition_scan_state(
                scan_id,
                expected_statuses=["started"],
                next_status="running",
                actor="system:cspm",
                reason="scan worker started",
                expected_state_version=int(started_record.get("state_version") or 0),
            )
            if not transitioned:
                logger.warning("CSPM scan %s could not transition to running due to state conflict", scan_id)
                return

            results = await engine.scan_all(
                providers=request.providers,
                regions=request.regions,
                resource_types=request.resource_types,
                check_ids=request.check_ids,
                severity_filter=request.severity_filter,
            )
            # Store results
            for provider, result in results.items():
                _active_scans[result.scan_id] = result

            await _persist_scan_findings(results)

            provider_results = []
            resources_scanned = 0
            findings_count = 0
            critical_count = 0
            high_count = 0
            medium_count = 0
            low_count = 0
            for provider, result in results.items():
                provider_results.append(
                    {
                        "provider": provider.value,
                        "scan_id": result.scan_id,
                        "status": result.status,
                        "error_message": result.error_message,
                        "resources_scanned": result.resources_scanned,
                        "findings_count": result.findings_count,
                        "critical_count": result.critical_count,
                        "high_count": result.high_count,
                        "medium_count": result.medium_count,
                        "low_count": result.low_count,
                        "started_at": result.started_at,
                        "completed_at": result.completed_at,
                    }
                )
                resources_scanned += int(result.resources_scanned or 0)
                findings_count += int(result.findings_count or 0)
                critical_count += int(result.critical_count or 0)
                high_count += int(result.high_count or 0)
                medium_count += int(result.medium_count or 0)
                low_count += int(result.low_count or 0)

            running_record = await _get_scan_record(scan_id)
            await _transition_scan_state(
                scan_id,
                expected_statuses=["running"],
                next_status="completed",
                actor="system:cspm",
                reason="scan worker completed",
                expected_state_version=int(running_record.get("state_version") or 0),
                extra_updates={
                    "provider_results": provider_results,
                    "resources_scanned": resources_scanned,
                    "findings_count": findings_count,
                    "critical_count": critical_count,
                    "high_count": high_count,
                    "medium_count": medium_count,
                    "low_count": low_count,
                },
            )
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            running_record = await _get_scan_record(scan_id)
            await _transition_scan_state(
                scan_id,
                expected_statuses=["started", "running"],
                next_status="failed",
                actor="system:cspm",
                reason="scan worker failed",
                expected_state_version=int(running_record.get("state_version") or 0),
                extra_updates={"error_message": str(e)},
            )
    
    background_tasks.add_task(run_scan)
    
    return {
        "status": "started",
        "scan_id": scan_id,
        "providers": selected_providers,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/scans", summary="List scan history")
async def list_scans(
    limit: int = Query(20, ge=1, le=100),
    provider: Optional[CloudProvider] = None,
) -> Dict[str, Any]:
    """Get list of historical scans"""
    db = get_db()
    if db is not None:
        query: Dict[str, Any] = {}
        if provider:
            query["providers"] = {"$in": [provider.value]}

        records = await db[_SCAN_COLLECTION].find(query, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)
        return {
            "scans": records,
            "count": len(records),
        }

    engine = get_cspm_engine()
    scans = engine.scan_history[-limit:]
    
    if provider:
        scans = [s for s in scans if s.provider == provider]
    
    items = [
        {
            "scan_id": s.scan_id,
            "provider": s.provider.value,
            "status": s.status,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "error_message": s.error_message,
            "resources_scanned": s.resources_scanned,
            "findings_count": s.findings_count,
            "critical_count": s.critical_count,
            "high_count": s.high_count,
        }
        for s in reversed(scans)
    ]

    return {
        "scans": items,
        "count": len(items),
    }


@router.get("/scans/{scan_id}", summary="Get scan details")
async def get_scan(scan_id: str) -> Dict[str, Any]:
    """Get detailed results of a specific scan"""
    db = get_db()
    if db is not None:
        record = await db[_SCAN_COLLECTION].find_one({"scan_id": scan_id}, {"_id": 0})
        if record:
            return record

    engine = get_cspm_engine()
    
    for scan in engine.scan_history:
        if scan.scan_id == scan_id:
            return scan.to_dict()
    
    if scan_id in _active_scans:
        return _active_scans[scan_id].to_dict()
    
    raise HTTPException(status_code=404, detail="Scan not found")


@router.get("/posture", summary="Get security posture")
async def get_posture() -> PostureResponse:
    """Get overall cloud security posture summary"""
    engine = get_cspm_engine()
    posture = engine.get_security_posture()
    return PostureResponse(**posture)


@router.get("/findings", summary="List findings")
async def list_findings(
    severity: Optional[Severity] = None,
    provider: Optional[CloudProvider] = None,
    status: Optional[FindingStatus] = Query(FindingStatus.OPEN),
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """
    List security findings with filtering.
    
    - **severity**: Filter by severity level
    - **provider**: Filter by cloud provider
    - **status**: Filter by status (default: open)
    - **category**: Filter by category (iam, storage, network, etc.)
    """
    db = get_db()
    if db is not None:
        query: Dict[str, Any] = {}
        if severity:
            query["severity"] = severity.value
        if provider:
            query["provider"] = provider.value
        if status:
            query["status"] = status.value
        if category:
            query["category"] = category

        docs = await db[_FINDING_COLLECTION].find(query, {"_id": 0}).to_list(5000)
        severity_rank = {
            Severity.CRITICAL.value: 0,
            Severity.HIGH.value: 1,
            Severity.MEDIUM.value: 2,
            Severity.LOW.value: 3,
            Severity.INFO.value: 4,
        }
        docs.sort(key=lambda d: (severity_rank.get(str(d.get("severity")), 5), -int(d.get("risk_score") or 0)))

        total = len(docs)
        docs = docs[offset:offset + limit]
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "findings": docs,
        }

    engine = get_cspm_engine()
    findings = list(engine.findings_db.values())

    # Apply filters
    if severity:
        findings = [f for f in findings if f.severity == severity]
    if provider:
        findings = [f for f in findings if f.provider == provider]
    if status:
        findings = [f for f in findings if f.status == status]
    if category:
        findings = [f for f in findings if f.category.lower() == category.lower()]

    # Sort by severity (critical first)
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 5), f.risk_score), reverse=False)

    total = len(findings)
    findings = findings[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "findings": [f.to_dict() for f in findings],
    }


@router.get("/findings/{finding_id}", summary="Get finding details")
async def get_finding(finding_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific finding"""
    durable = await _get_finding_record(finding_id)
    if durable:
        return durable

    engine = get_cspm_engine()
    
    if finding_id in engine.findings_db:
        return engine.findings_db[finding_id].to_dict()
    
    raise HTTPException(status_code=404, detail="Finding not found")


@router.put("/findings/{finding_id}/status", summary="Update finding status")
async def update_finding_status(
    finding_id: str,
    update: FindingStatusUpdate
) -> Dict[str, Any]:
    """
    Update the status of a finding.
    
    - **status**: New status (resolved, suppressed, false_positive, in_progress)
    - **reason**: Reason for status change (required for suppression)
    - **updated_by**: User making the change
    """
    if update.status == FindingStatus.SUPPRESSED and not update.reason:
        raise HTTPException(status_code=400, detail="Reason required for suppression")

    # Durable DB-backed path
    db = get_db()
    if db is not None:
        finding = await _ensure_finding_state_fields(
            finding_id,
            actor=update.updated_by,
            reason="bootstrap cspm finding durability fields",
        )
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        current_status = str(finding.get("status") or FindingStatus.OPEN.value)
        target_status = update.status.value
        if current_status == target_status:
            raise HTTPException(status_code=409, detail=f"Finding already in status={target_status}")

        allowed_targets = {
            FindingStatus.OPEN.value: {
                FindingStatus.IN_PROGRESS.value,
                FindingStatus.RESOLVED.value,
                FindingStatus.SUPPRESSED.value,
                FindingStatus.FALSE_POSITIVE.value,
            },
            FindingStatus.IN_PROGRESS.value: {
                FindingStatus.RESOLVED.value,
                FindingStatus.SUPPRESSED.value,
                FindingStatus.FALSE_POSITIVE.value,
            },
        }
        if current_status in _FINDING_TERMINAL_STATUSES:
            raise HTTPException(status_code=409, detail=f"Finding already terminal (status={current_status})")
        if target_status not in allowed_targets.get(current_status, set()):
            raise HTTPException(
                status_code=409,
                detail=f"Invalid finding transition {current_status} -> {target_status}",
            )

        reason = update.reason or f"status updated to {target_status}"
        extra_updates: Dict[str, Any] = {}
        evidence = dict(finding.get("evidence") or {})
        if target_status == FindingStatus.SUPPRESSED.value:
            evidence["suppression_reason"] = reason
            evidence["suppressed_by"] = update.updated_by
            evidence["suppressed_at"] = datetime.now(timezone.utc).isoformat()
        elif target_status == FindingStatus.RESOLVED.value:
            evidence["resolution_note"] = reason
            evidence["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if evidence:
            extra_updates["evidence"] = evidence

        transitioned = await _transition_finding_status(
            finding_id,
            expected_statuses=[current_status],
            next_status=target_status,
            actor=update.updated_by,
            reason=reason,
            expected_state_version=int(finding.get("state_version") or 0),
            transition_metadata={"updated_by": update.updated_by},
            extra_updates=extra_updates,
        )
        if not transitioned:
            refreshed = await _get_finding_record(finding_id)
            if not refreshed:
                raise HTTPException(status_code=404, detail="Finding not found")
            if str(refreshed.get("status") or "") == target_status:
                raise HTTPException(status_code=409, detail=f"Finding already in status={target_status}")
            raise HTTPException(status_code=409, detail="Finding update conflict; state changed concurrently")

        return {
            "finding_id": finding_id,
            "status": target_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Fallback in-memory path
    engine = get_cspm_engine()

    if finding_id not in engine.findings_db:
        raise HTTPException(status_code=404, detail="Finding not found")

    if update.status == FindingStatus.SUPPRESSED:
        engine.suppress_finding(finding_id, update.reason, update.updated_by)
    elif update.status == FindingStatus.RESOLVED:
        engine.resolve_finding(finding_id, update.reason or "Manually resolved")
    else:
        engine.findings_db[finding_id].status = update.status

    return {
        "finding_id": finding_id,
        "status": update.status.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/resources", summary="List discovered resources")
async def list_resources(
    provider: Optional[CloudProvider] = None,
    resource_type: Optional[ResourceType] = None,
    is_public: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """List discovered cloud resources with filtering"""
    engine = get_cspm_engine()
    resources = list(engine.resources_db.values())
    
    if provider:
        resources = [r for r in resources if r.provider == provider]
    if resource_type:
        resources = [r for r in resources if r.resource_type == resource_type]
    if is_public is not None:
        resources = [r for r in resources if r.is_public == is_public]
    
    total = len(resources)
    resources = resources[offset:offset + limit]
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "resources": [r.to_dict() for r in resources],
    }


@router.get("/compliance/{framework}", summary="Get compliance report")
async def get_compliance_report(framework: str) -> Dict[str, Any]:
    """
    Get compliance report for a specific framework.
    
    Supported frameworks:
    - CIS AWS/Azure/GCP benchmarks
    - NIST 800-53, NIST CSF
    - SOC2, PCI-DSS 4.0, HIPAA, GDPR
    - ISO 27001
    """
    engine = get_cspm_engine()
    normalized = _normalize_framework(framework)
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unsupported compliance framework: {framework}",
                "supported": [f.value for f in ComplianceFramework],
            },
        )

    return engine.get_compliance_report(normalized)


@router.get("/checks", summary="List security checks")
async def list_checks(
    provider: Optional[CloudProvider] = None,
    category: Optional[str] = None,
    enabled_only: bool = False,
) -> List[Dict[str, Any]]:
    """List available security checks"""
    engine = get_cspm_engine()
    checks = []
    
    for scanner in engine.scanners.values():
        if provider and scanner.provider != provider:
            continue
        
        for check in scanner.checks.values():
            if enabled_only and not check.enabled:
                continue
            if category and check.category.lower() != category.lower():
                continue
            
            checks.append({
                "check_id": check.check_id,
                "title": check.title,
                "description": check.description,
                "severity": check.severity.value,
                "provider": scanner.provider.value,
                "category": check.category,
                "subcategory": check.subcategory,
                "enabled": check.enabled,
                "auto_remediate": check.auto_remediate,
                "cis_controls": check.cis_controls,
                "mitre_techniques": check.mitre_techniques,
            })
    
    return checks


@router.put("/checks/{check_id}", summary="Toggle security check")
async def toggle_check(check_id: str, toggle: CheckToggle) -> Dict[str, Any]:
    """Enable or disable a security check"""
    engine = get_cspm_engine()
    
    for scanner in engine.scanners.values():
        if check_id in scanner.checks:
            scanner.checks[check_id].enabled = toggle.enabled
            scanner.checks[check_id].auto_remediate = toggle.auto_remediate
            return {
                "check_id": check_id,
                "enabled": toggle.enabled,
                "auto_remediate": toggle.auto_remediate,
            }
    
    raise HTTPException(status_code=404, detail="Check not found")


@router.get("/export", summary="Export findings")
async def export_findings(
    format: str = Query("json", pattern="^(json|csv)$"),
    severity: Optional[Severity] = None,
    provider: Optional[CloudProvider] = None,
) -> Dict[str, Any]:
    """
    Export findings in JSON or CSV format.
    
    - **format**: Export format (json or csv)
    - **severity**: Filter by severity
    - **provider**: Filter by provider
    """
    engine = get_cspm_engine()
    
    # Apply filters before export
    findings = list(engine.findings_db.values())
    if severity:
        findings = [f for f in findings if f.severity == severity]
    if provider:
        findings = [f for f in findings if f.provider == provider]
    
    # Temporarily replace findings for export
    original_findings = engine.findings_db
    engine.findings_db = {f.finding_id: f for f in findings}
    
    try:
        export_data = engine.export_findings(format)
    finally:
        engine.findings_db = original_findings
    
    return {
        "format": format,
        "count": len(findings),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "data": export_data,
    }


@router.get("/dashboard", summary="Get dashboard statistics")
async def get_dashboard() -> DashboardStats:
    """Get comprehensive dashboard statistics"""
    await _load_providers_from_db()
    engine = get_cspm_engine()
    posture = engine.get_security_posture()

    # If posture has no data (engine freshly started), supplement from DB
    if posture.get("total_findings", 0) == 0 and posture.get("total_resources", 0) == 0:
        db = get_db()
        if db is not None:
            db_scans = await db[_SCAN_COLLECTION].find({"status": "completed"}, {"_id": 0}).sort("started_at", -1).limit(20).to_list(20)
            if db_scans:
                total_findings = sum(s.get("findings_count", 0) for s in db_scans)
                total_resources = sum(s.get("resources_scanned", 0) for s in db_scans)
                critical_total = sum(s.get("critical_count", 0) for s in db_scans)
                high_total = sum(s.get("high_count", 0) for s in db_scans)
                score = max(0.0, 100.0 - (critical_total * 5) - (high_total * 2))
                posture["total_findings"] = total_findings
                posture["open_findings"] = total_findings
                posture["total_resources"] = total_resources
                posture["overall_score"] = round(score, 1)
                posture["grade"] = "A" if score >= 90 else "B" if score >= 75 else "C"
                posture["last_scan"] = db_scans[0].get("completed_at") or db_scans[0].get("started_at")
                posture["severity_breakdown"] = {"critical": critical_total, "high": high_total}
    
    # Recent scans — prefer in-memory engine history, fall back to DB
    recent_scans = [
        {
            "scan_id": s.scan_id,
            "provider": s.provider.value,
            "status": s.status,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "error_message": s.error_message,
            "resources_scanned": s.resources_scanned,
            "findings_count": s.findings_count,
        }
        for s in engine.scan_history[-5:]
    ]
    if not recent_scans:
        db = get_db()
        if db is not None:
            db_scans = await db[_SCAN_COLLECTION].find({}, {"_id": 0}).sort("started_at", -1).limit(5).to_list(5)
            recent_scans = [
                {
                    "scan_id": s.get("scan_id"),
                    "provider": s.get("providers", ["unknown"])[0] if isinstance(s.get("providers"), list) else s.get("provider", "unknown"),
                    "status": s.get("status"),
                    "started_at": s.get("started_at"),
                    "completed_at": s.get("completed_at"),
                    "error_message": s.get("error_message"),
                    "resources_scanned": s.get("resources_scanned", 0),
                    "findings_count": s.get("findings_count", 0),
                }
                for s in db_scans
            ]
    
    # Top risks (highest risk score findings)
    open_findings = [f for f in engine.findings_db.values() if f.status == FindingStatus.OPEN]
    top_risks = sorted(open_findings, key=lambda f: f.risk_score, reverse=True)[:10]
    
    # Compliance summary
    compliance_summary = {}
    compliance_map = {
        "CIS": ComplianceFramework.CIS_AWS_2_0,
        "NIST": ComplianceFramework.NIST_800_53,
        "SOC2": ComplianceFramework.SOC2,
        "PCI_DSS": ComplianceFramework.PCI_DSS_4_0,
    }
    for label, framework in compliance_map.items():
        report = engine.get_compliance_report(framework)
        compliance_summary[label] = report.get("compliance_percentage", 100)
    
    # Resource counts by type
    resource_counts = {}
    for resource in engine.resources_db.values():
        rt = resource.resource_type.value
        resource_counts[rt] = resource_counts.get(rt, 0) + 1
    
    # Findings by category
    findings_by_category = {}
    for finding in open_findings:
        cat = finding.category
        findings_by_category[cat] = findings_by_category.get(cat, 0) + 1
    
    return DashboardStats(
        posture=PostureResponse(**posture),
        recent_scans=recent_scans,
        top_risks=[
            {
                "finding_id": f.finding_id,
                "title": f.title,
                "provider": f.provider.value,
                "severity": f.severity.value,
                "risk_score": f.risk_score,
                "resource_id": f.resource.resource_id,
                "resource_type": f.resource.resource_type.value,
                "affected_resources": 1,
            }
            for f in top_risks
        ],
        compliance_summary=compliance_summary,
        resource_counts=resource_counts,
        findings_by_category=findings_by_category,
    )


@router.get("/stats", summary="Get CSPM statistics")
async def get_stats() -> Dict[str, Any]:
    """Get CSPM engine statistics"""
    engine = get_cspm_engine()

    active_scan_count = len(_active_scans)
    db = get_db()
    if db is not None:
        active_scan_count = await db[_SCAN_COLLECTION].count_documents(
            {"status": {"$in": ["started", "running"]}}
        )

    return {
        "total_scans": engine.stats["total_scans"],
        "total_findings": engine.stats["total_findings"],
        "total_resources": engine.stats["total_resources"],
        "scans_by_provider": dict(engine.stats["scans_by_provider"]),
        "findings_by_severity": dict(engine.stats["findings_by_severity"]),
        "configured_providers": len(_configured_providers),
        "active_scans": active_scan_count,
    }


@router.post("/demo-seed", summary="Seed demo CSPM findings/resources")
async def seed_demo_cspm_data(count: int = Query(12, ge=1, le=200)) -> Dict[str, Any]:
    """Populate synthetic CSPM data for UI validation when real cloud credentials are unavailable."""
    engine = get_cspm_engine()

    demo_resources = [
        CloudResource(
            resource_id="i-demo-001",
            resource_type=ResourceType.VIRTUAL_MACHINE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="111122223333",
            name="prod-web-01",
            is_public=True,
        ),
        CloudResource(
            resource_id="stgacctdemo01",
            resource_type=ResourceType.STORAGE_BUCKET,
            provider=CloudProvider.AZURE,
            region="eastus",
            account_id="sub-demo-001",
            name="stgacctdemo01",
            is_public=True,
        ),
        CloudResource(
            resource_id="gke-demo-cluster",
            resource_type=ResourceType.KUBERNETES_CLUSTER,
            provider=CloudProvider.GCP,
            region="us-central1",
            account_id="demo-project",
            name="gke-demo-cluster",
            is_public=False,
        ),
    ]

    templates = [
        ("Public VM Exposed to Internet", "Critical VM has open ingress from 0.0.0.0/0", Severity.CRITICAL, CloudProvider.AWS, "Network", "Security Groups", demo_resources[0]),
        ("Storage Account Public Access Enabled", "Blob/container public access is enabled", Severity.HIGH, CloudProvider.AZURE, "Storage", "Access Control", demo_resources[1]),
        ("GKE Cluster Missing Network Policy", "Cluster allows unrestricted pod-to-pod traffic", Severity.MEDIUM, CloudProvider.GCP, "Containers", "Network", demo_resources[2]),
    ]

    seeded = 0
    for i in range(min(count, len(templates) * 10)):
        title, desc, sev, provider, category, subcategory, resource = templates[i % len(templates)]
        finding = Finding(
            finding_id=f"demo-{uuid.uuid4().hex[:12]}",
            title=title,
            description=desc,
            severity=sev,
            provider=provider,
            resource=resource,
            check_id=f"demo-check-{(i % len(templates)) + 1}",
            check_title=title,
            category=category,
            subcategory=subcategory,
            risk_score=95 if sev == Severity.CRITICAL else (82 if sev == Severity.HIGH else 64),
        )
        engine.findings_db[finding.finding_id] = finding
        engine.resources_db[resource.resource_id] = resource
        seeded += 1

    return {
        "status": "seeded",
        "findings_added": seeded,
        "resources_total": len(engine.resources_db),
        "note": "Synthetic demo data only. Not from live cloud APIs.",
    }
