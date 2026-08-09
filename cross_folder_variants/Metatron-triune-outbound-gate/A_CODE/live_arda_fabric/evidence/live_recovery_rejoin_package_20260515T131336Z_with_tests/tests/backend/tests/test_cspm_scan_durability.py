"""Durability tests for CSPM scan lifecycle persistence transitions."""

import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"


def _load_cspm_module():
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(ROOT / "backend")]
    sys.modules.setdefault("backend", backend_pkg)

    routers_pkg = types.ModuleType("backend.routers")
    routers_pkg.__path__ = [str(ROUTERS_DIR)]
    sys.modules.setdefault("backend.routers", routers_pkg)

    # Stub dependencies
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

    # Stub CSPM engine module
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
        pass

    class CloudResource:
        pass

    class ScanResult:
        def __init__(
            self,
            *,
            scan_id: str,
            provider: CloudProvider,
            status: str,
            started_at: str,
            completed_at: Optional[str],
            resources_scanned: int,
            findings_count: int,
            critical_count: int,
            high_count: int,
            medium_count: int,
            low_count: int,
            error_message: Optional[str] = None,
            findings: Optional[List[Any]] = None,
        ):
            self.scan_id = scan_id
            self.provider = provider
            self.status = status
            self.started_at = started_at
            self.completed_at = completed_at
            self.resources_scanned = resources_scanned
            self.findings_count = findings_count
            self.critical_count = critical_count
            self.high_count = high_count
            self.medium_count = medium_count
            self.low_count = low_count
            self.error_message = error_message
            self.findings = findings or []

        def to_dict(self) -> Dict[str, Any]:
            return {
                "scan_id": self.scan_id,
                "provider": self.provider.value,
                "status": self.status,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
            }

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
            self._next_results = {}

        async def scan_all(self, **_kwargs):
            return self._next_results

        def register_scanner(self, scanner):
            self.scanners[scanner.provider] = scanner

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

    # Stub scanner modules
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
    return module, dependencies_stub, fake_engine, CloudProvider, ScanResult


cspm, deps, engine, CloudProvider, ScanResult = _load_cspm_module()


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @classmethod
    def _matches(cls, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(doc, opt) for opt in expected or []):
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
                    next_doc.update(update["$set"])
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

            def sort(self, field: str, direction: int):
                reverse = int(direction) < 0
                self.docs = sorted(self.docs, key=lambda d: d.get(field, ""), reverse=reverse)
                return self

            def limit(self, value: int):
                self.docs = self.docs[:value]
                return self

            async def to_list(self, length: int):
                return self.docs[:length]

        return _Cursor(matched)

    async def count_documents(self, query: Dict[str, Any]):
        return len([d for d in self.docs if self._matches(d, query)])


class FakeDB:
    def __init__(self, scans: Optional[List[Dict[str, Any]]] = None):
        self.cspm_scans = FakeCollection(scans)

    def __getitem__(self, name: str):
        return getattr(self, name)


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))


def _set_db(fake_db: FakeDB):
    deps._db = fake_db
    cspm.get_db = lambda: fake_db


def test_create_scan_record_sets_state_version_and_transition_log():
    fake_db = FakeDB(scans=[])
    _set_db(fake_db)

    request = cspm.ScanRequest(providers=[CloudProvider.AWS])
    asyncio.run(cspm._create_scan_record("scan-1", request, ["aws"]))

    doc = asyncio.run(fake_db.cspm_scans.find_one({"scan_id": "scan-1"}))
    assert doc is not None
    assert doc["status"] == "started"
    assert doc["state_version"] == 1
    assert len(doc.get("state_transition_log") or []) == 1
    assert doc["state_transition_log"][0].get("to_status") == "started"


def test_transition_scan_state_rejects_stale_version_conflict():
    fake_db = FakeDB(
        scans=[
            {
                "scan_id": "scan-2",
                "status": "running",
                "state_version": 3,
                "state_transition_log": [{"to_status": "running"}],
            }
        ]
    )
    _set_db(fake_db)

    transitioned = asyncio.run(
        cspm._transition_scan_state(
            "scan-2",
            expected_statuses=["running"],
            next_status="completed",
            actor="tester",
            reason="complete",
            expected_state_version=2,
        )
    )
    assert transitioned is False


def test_start_scan_persists_running_to_completed_lifecycle():
    fake_db = FakeDB(scans=[])
    _set_db(fake_db)

    async def _noop_load(force: bool = False):
        return None

    cspm._load_providers_from_db = _noop_load
    engine.scanners = {CloudProvider.AWS: SimpleNamespace(provider=CloudProvider.AWS, checks={})}
    engine._next_results = {
        CloudProvider.AWS: ScanResult(
            scan_id="provider-scan-1",
            provider=CloudProvider.AWS,
            status="completed",
            started_at="2026-03-07T00:00:00+00:00",
            completed_at="2026-03-07T00:05:00+00:00",
            resources_scanned=10,
            findings_count=4,
            critical_count=1,
            high_count=1,
            medium_count=1,
            low_count=1,
        )
    }

    bg = FakeBackgroundTasks()
    response = asyncio.run(cspm.start_scan(cspm.ScanRequest(providers=[CloudProvider.AWS]), bg))

    assert response["status"] == "started"
    assert len(bg.tasks) == 1

    fn, args, kwargs = bg.tasks[0]
    asyncio.run(fn(*args, **kwargs))

    doc = asyncio.run(fake_db.cspm_scans.find_one({"scan_id": response["scan_id"]}))
    assert doc is not None
    assert doc["status"] == "completed"
    assert doc["state_version"] == 3
    assert doc["resources_scanned"] == 10
    assert doc["findings_count"] == 4
    transitions = doc.get("state_transition_log") or []
    assert transitions[0].get("to_status") == "started"
    assert transitions[1].get("to_status") == "running"
    assert transitions[2].get("to_status") == "completed"
