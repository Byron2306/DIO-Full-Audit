"""Durability tests for CSPM finding status persistence transitions."""

import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"


def _load_cspm_module():
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(ROOT / "backend")]
    sys.modules.setdefault("backend", backend_pkg)

    routers_pkg = types.ModuleType("backend.routers")
    routers_pkg.__path__ = [str(ROUTERS_DIR)]
    sys.modules.setdefault("backend.routers", routers_pkg)

    dependencies_stub = types.ModuleType("backend.routers.dependencies")
    dependencies_stub._db = None
    dependencies_stub.get_db = lambda: dependencies_stub._db
    dependencies_stub.db = None
    dependencies_stub.logger = SimpleNamespace(debug=lambda *_a, **_k: None, info=lambda *_a, **_k: None, warning=lambda *_a, **_k: None, error=lambda *_a, **_k: None)

    async def _fake_get_current_user():
        return {"email": "tester@example.com", "role": "admin"}

    def _fake_check_permission(_permission):
        async def _dep():
            return {"email": "tester@example.com", "role": "admin"}

        return _dep

    dependencies_stub.get_current_user = _fake_get_current_user
    dependencies_stub.check_permission = _fake_check_permission
    sys.modules.setdefault("backend.routers.dependencies", dependencies_stub)

    # Stub cryptography.fernet
    crypto_pkg = types.ModuleType("cryptography")
    fernet_mod = types.ModuleType("cryptography.fernet")

    class _FakeFernet:
        def __init__(self, _key):
            pass

        def encrypt(self, value: bytes) -> bytes:
            return value

        def decrypt(self, token: bytes) -> bytes:
            return token

    fernet_mod.Fernet = _FakeFernet
    sys.modules.setdefault("cryptography", crypto_pkg)
    sys.modules.setdefault("cryptography.fernet", fernet_mod)

    cspm_engine_stub = types.ModuleType("cspm_engine")

    class CloudProvider(str, Enum):
        AWS = "aws"
        AZURE = "azure"
        GCP = "gcp"

    class Severity(str, Enum):
        CRITICAL = "critical"
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        INFO = "informational"

    class ResourceType(str, Enum):
        VIRTUAL_MACHINE = "virtual_machine"

    class ComplianceFramework(str, Enum):
        CIS_AWS_2_0 = "cis_aws_2.0"
        CIS_AZURE_2_0 = "cis_azure_2.0"
        CIS_GCP_2_0 = "cis_gcp_2.0"
        NIST_800_53 = "nist_800_53"
        SOC2 = "soc2"
        PCI_DSS_4_0 = "pci_dss_4.0"

    class FindingStatus(str, Enum):
        OPEN = "open"
        IN_PROGRESS = "in_progress"
        RESOLVED = "resolved"
        SUPPRESSED = "suppressed"
        FALSE_POSITIVE = "false_positive"

    class CloudCredentials:
        def __init__(self, provider: CloudProvider, account_id: str, region: Optional[str] = None, **kwargs):
            self.provider = provider
            self.account_id = account_id
            self.region = region
            for k, v in kwargs.items():
                setattr(self, k, v)

        def validate(self) -> bool:
            return True

    class Finding:
        def __init__(
            self,
            *,
            finding_id: str,
            provider: CloudProvider,
            severity: Severity,
            status: FindingStatus,
            title: str,
            description: str,
            resource_id: str,
            resource_type: str,
            category: str,
            risk_score: int,
        ):
            self.finding_id = finding_id
            self.provider = provider
            self.severity = severity
            self.status = status
            self.title = title
            self.description = description
            self.resource_id = resource_id
            self.resource_type = resource_type
            self.category = category
            self.risk_score = risk_score

        def to_dict(self) -> Dict[str, Any]:
            return {
                "finding_id": self.finding_id,
                "provider": self.provider.value,
                "severity": self.severity.value,
                "status": self.status.value,
                "title": self.title,
                "description": self.description,
                "resource_id": self.resource_id,
                "resource_type": self.resource_type,
                "category": self.category,
                "risk_score": self.risk_score,
                "evidence": {},
            }

    class CloudResource:
        pass

    class ScanResult:
        def __init__(self, *, findings: List[Finding]):
            self.findings = findings

    class _FakeEngine:
        def __init__(self):
            self.scanners = {}
            self.scan_history = []
            self.findings_db = {}
            self.resources_db = {}
            self.stats = {
                "total_scans": 0,
                "total_findings": 0,
                "total_resources": 0,
                "scans_by_provider": {},
                "findings_by_severity": {},
            }

        async def scan_all(self, **_kwargs):
            return {}

        def register_scanner(self, scanner):
            self.scanners[scanner.provider] = scanner

        def suppress_finding(self, finding_id: str, reason: str, updated_by: str):
            finding = self.findings_db.get(finding_id)
            if finding:
                finding.status = FindingStatus.SUPPRESSED

        def resolve_finding(self, finding_id: str, _reason: str):
            finding = self.findings_db.get(finding_id)
            if finding:
                finding.status = FindingStatus.RESOLVED

        def get_security_posture(self):
            return {
                "overall_score": 100.0,
                "grade": "A",
                "total_resources": 0,
                "total_findings": 0,
                "open_findings": 0,
                "severity_breakdown": {},
                "provider_breakdown": {},
                "last_scan": None,
                "trend": "stable",
            }

        def get_compliance_report(self, _framework):
            return {"compliance_percentage": 100.0}

        def export_findings(self, _fmt):
            return []

    fake_engine = _FakeEngine()

    cspm_engine_stub.CSPMEngine = _FakeEngine
    cspm_engine_stub.get_cspm_engine = lambda: fake_engine
    cspm_engine_stub.CloudProvider = CloudProvider
    cspm_engine_stub.Severity = Severity
    cspm_engine_stub.ResourceType = ResourceType
    cspm_engine_stub.ComplianceFramework = ComplianceFramework
    cspm_engine_stub.FindingStatus = FindingStatus
    cspm_engine_stub.CloudCredentials = CloudCredentials
    cspm_engine_stub.Finding = Finding
    cspm_engine_stub.ScanResult = ScanResult
    cspm_engine_stub.CloudResource = CloudResource
    sys.modules.setdefault("cspm_engine", cspm_engine_stub)

    for mod_name, provider in (
        ("cspm_aws_scanner", CloudProvider.AWS),
        ("cspm_azure_scanner", CloudProvider.AZURE),
        ("cspm_gcp_scanner", CloudProvider.GCP),
    ):
        mod = types.ModuleType(mod_name)

        class _Scanner:
            def __init__(self, _credentials):
                self.provider = provider
                self.checks = {}

        if mod_name == "cspm_aws_scanner":
            mod.AWSScanner = _Scanner
        elif mod_name == "cspm_azure_scanner":
            mod.AzureScanner = _Scanner
        else:
            mod.GCPScanner = _Scanner
        sys.modules.setdefault(mod_name, mod)

    module_path = ROUTERS_DIR / "cspm.py"
    spec = importlib.util.spec_from_file_location("backend.routers.cspm", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.cspm")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.cspm"] = module
    spec.loader.exec_module(module)
    return module, dependencies_stub, fake_engine, CloudProvider, Severity, FindingStatus, Finding, ScanResult


cspm, deps, engine, CloudProvider, Severity, FindingStatus, Finding, ScanResult = _load_cspm_module()


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @classmethod
    def _matches(cls, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(doc, option) for option in expected or []):
                    return False
                continue

            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                elif "$exists" in expected:
                    exists = key in doc
                    if exists != bool(expected["$exists"]):
                        return False
                else:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        for doc in self.docs:
            if self._matches(doc, query):
                found = deepcopy(doc)
                if projection:
                    include_keys = {k for k, v in projection.items() if v}
                    if include_keys:
                        found = {k: v for k, v in found.items() if k in include_keys}
                return found
        return None

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        matched = 0
        modified = 0
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                matched += 1
                next_doc = deepcopy(doc)
                if "$set" in update:
                    next_doc.update(deepcopy(update["$set"]))
                if "$setOnInsert" in update and matched == 0:
                    for key, value in update["$setOnInsert"].items():
                        next_doc.setdefault(key, deepcopy(value))
                if "$inc" in update:
                    for key, delta in update["$inc"].items():
                        next_doc[key] = int(next_doc.get(key) or 0) + int(delta)
                if "$push" in update:
                    for key, value in update["$push"].items():
                        arr = list(next_doc.get(key) or [])
                        arr.append(deepcopy(value))
                        next_doc[key] = arr
                self.docs[idx] = next_doc
                modified += 1
                break

        if matched == 0 and upsert:
            doc = {}
            if "$set" in update:
                doc.update(deepcopy(update["$set"]))
            if "$setOnInsert" in update:
                for key, value in update["$setOnInsert"].items():
                    doc.setdefault(key, deepcopy(value))
            self.docs.append(doc)
            matched = 1
            modified = 1

        return SimpleNamespace(matched_count=matched, modified_count=modified)

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        matched = [deepcopy(d) for d in self.docs if self._matches(d, query)]

        if projection:
            include_keys = {k for k, v in projection.items() if v}
            if include_keys:
                matched = [{k: v for k, v in d.items() if k in include_keys} for d in matched]

        class _Cursor:
            def __init__(self, docs):
                self.docs = docs

            async def to_list(self, length: int):
                return self.docs[:length]

        return _Cursor(matched)


class FakeDB:
    def __init__(self, findings: Optional[List[Dict[str, Any]]] = None):
        self.cspm_findings = FakeCollection(findings)
        self.cspm_scans = FakeCollection([])

    def __getitem__(self, name: str):
        return getattr(self, name)


def _set_db(fake_db: FakeDB):
    deps._db = fake_db
    cspm.get_db = lambda: fake_db


def test_persist_scan_findings_initializes_state_fields():
    fake_db = FakeDB(findings=[])
    _set_db(fake_db)

    finding = Finding(
        finding_id="f-1",
        provider=CloudProvider.AWS,
        severity=Severity.HIGH,
        status=FindingStatus.OPEN,
        title="Public S3 bucket",
        description="Bucket allows public read",
        resource_id="bucket-1",
        resource_type="s3_bucket",
        category="storage",
        risk_score=80,
    )
    results = {CloudProvider.AWS: ScanResult(findings=[finding])}

    asyncio.run(cspm._persist_scan_findings(results))

    doc = asyncio.run(fake_db.cspm_findings.find_one({"finding_id": "f-1"}))
    assert doc is not None
    assert doc["status"] == "open"
    assert doc["state_version"] == 1
    transitions = doc.get("state_transition_log") or []
    assert len(transitions) == 1
    assert transitions[0].get("to_status") == "open"


def test_transition_finding_status_rejects_stale_state_version():
    fake_db = FakeDB(
        findings=[
            {
                "finding_id": "f-2",
                "status": "open",
                "state_version": 3,
                "state_transition_log": [{"to_status": "open"}],
            }
        ]
    )
    _set_db(fake_db)

    transitioned = asyncio.run(
        cspm._transition_finding_status(
            "f-2",
            expected_statuses=["open"],
            next_status="resolved",
            actor="tester",
            reason="resolve",
            expected_state_version=2,
        )
    )
    assert transitioned is False


def test_update_finding_status_persists_resolved_transition():
    fake_db = FakeDB(
        findings=[
            {
                "finding_id": "f-3",
                "status": "open",
                "state_version": 1,
                "state_transition_log": [
                    {
                        "from_status": None,
                        "to_status": "open",
                        "actor": "system:cspm",
                        "reason": "finding discovered by scan",
                    }
                ],
                "evidence": {},
            }
        ]
    )
    _set_db(fake_db)

    response = asyncio.run(
        cspm.update_finding_status(
            "f-3",
            cspm.FindingStatusUpdate(
                status=FindingStatus.RESOLVED,
                reason="manually verified",
                updated_by="analyst-1",
            ),
        )
    )

    assert response["status"] == "resolved"
    doc = asyncio.run(fake_db.cspm_findings.find_one({"finding_id": "f-3"}))
    assert doc is not None
    assert doc["status"] == "resolved"
    assert doc["state_version"] == 2
    assert (doc.get("evidence") or {}).get("resolution_note") == "manually verified"
    transitions = doc.get("state_transition_log") or []
    assert transitions[-1].get("from_status") == "open"
    assert transitions[-1].get("to_status") == "resolved"


def test_update_finding_status_rejects_terminal_transitions():
    fake_db = FakeDB(
        findings=[
            {
                "finding_id": "f-4",
                "status": "resolved",
                "state_version": 2,
                "state_transition_log": [
                    {"to_status": "open"},
                    {"to_status": "resolved"},
                ],
                "evidence": {},
            }
        ]
    )
    _set_db(fake_db)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            cspm.update_finding_status(
                "f-4",
                cspm.FindingStatusUpdate(
                    status=FindingStatus.SUPPRESSED,
                    reason="noisy",
                    updated_by="analyst-2",
                ),
            )
        )

    assert exc.value.status_code == 409
    assert "terminal" in str(exc.value.detail).lower()
