from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from backend.services.arda_kernel_projection import (
    KernelProjectionError,
    BpftoolPinnedProjectionSink,
    KernelProjectionReconciler,
    ProjectionGenerationStore,
    SignedVerityManifestV1,
    StrictArdaKernelProjector,
    VerityManifestEntryV1,
    VerifiedKernelProjectionV1,
)
from backend.services.arda_trust_contracts import (
    ArdaAttestationResultV1,
    AttestationStatus,
    BeastCapabilityLeaseV1,
    EvidenceMode,
    canonical_json_bytes,
)


NOW = datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)
DIGEST = "ab" * 32


class SignatureVerifier:
    def __init__(self, valid=True):
        self.valid = valid

    def verify(self, payload, signature, algorithm, verification_material):
        return self.valid and signature == "valid" and algorithm == "ed25519"


class Measurer:
    def __init__(self, result=(1, DIGEST)):
        self.result = result

    def measure(self, path):
        return self.result


def attestation(**changes):
    values = dict(
        result_id="result-1",
        issuer="verifier-1",
        policy_id="policy-1",
        status=AttestationStatus.ACCEPTED,
        issued_at=(NOW - timedelta(seconds=5)).isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
        subject_node_id="node-1",
        subject_workload_digest="sha256:" + "11" * 32,
        evidence_bundle_id="bundle-1",
        evidence_digest="sha256:" + "22" * 32,
        nonce="nonce-1",
        environment="production",
        audience="arda-kernel-projector",
        assurance_class="hardware-attested",
        evidence_mode=EvidenceMode.ENFORCED,
        checks={"quote": True},
        hard_failures=(),
        warnings=(),
        signature_algorithm="ed25519",
        signature="valid",
        verification_material={"key_id": "verifier-1"},
    )
    values.update(changes)
    return ArdaAttestationResultV1(**values)


def manifest(**changes):
    bound_lease = changes.pop("bound_lease", None) or lease()
    lease_digest = "sha256:" + hashlib.sha256(
        canonical_json_bytes(bound_lease.unsigned_payload())
    ).hexdigest()
    values = dict(
        manifest_id="manifest-1",
        generation=7,
        environment="production",
        audience="arda-kernel-projector",
        node_id="node-1",
        attestation_result_id="result-1",
        attestation_evidence_digest="sha256:" + "22" * 32,
        capability_lease_id=bound_lease.lease_id,
        capability_lease_digest=lease_digest,
        policy_digest="sha256:" + "33" * 32,
        policy_generation="policy-generation-7",
        cgroup_id="beast.slice/mission-1",
        cgroup_kernel_id=987654,
        pid_namespace_inode=41001,
        mount_namespace_inode=41002,
        issued_at=(NOW - timedelta(seconds=4)).isoformat(),
        expires_at=(NOW + timedelta(minutes=1)).isoformat(),
        entries=(VerityManifestEntryV1(
            path="/opt/arda/bin/worker",
            algorithm_id=1,
            fsverity_digest=DIGEST,
            workload_digest="sha256:" + "11" * 32,
        ),),
        signature_algorithm="ed25519",
        signature="valid",
        verification_material={"key_id": "manifest-authority"},
    )
    values.update(changes)
    return SignedVerityManifestV1(**values)


def lease(**changes):
    values = dict(
        lease_id="lease-1",
        authority_request_id="request-1",
        authority_request_digest="sha256:" + "55" * 32,
        principal_id="operator-1",
        mission_id="mission-1",
        workspace_id="workspace-1",
        node_id="node-1",
        workload_digest="sha256:" + "11" * 32,
        attestation_result_id="result-1",
        attestation_evidence_digest="sha256:" + "22" * 32,
        capability="kernel.execute",
        parameters_digest="sha256:" + "66" * 32,
        data_scope=("workspace-1",),
        route_scope=(),
        output_scope=("evidence",),
        resource_ceiling={"cpu": 2},
        consequence_ceiling="high",
        policy_generation="policy-generation-7",
        approval_receipt_ids=("approval-1",),
        audience="arda-kernel-projector",
        nonce="lease-nonce-1",
        issued_at=(NOW - timedelta(seconds=3)).isoformat(),
        expires_at=(NOW + timedelta(seconds=90)).isoformat(),
        maximum_uses=1,
        revocation_epoch=7,
        signature_algorithm="ed25519",
        signature="valid",
        verification_material={"key_id": "beast-authority"},
    )
    values.update(changes)
    return BeastCapabilityLeaseV1(**values)


def projector(tmp_path, *, signature=True, attestation_signature=True, measured=(1, DIGEST)):
    return StrictArdaKernelProjector(
        signature_verifier=SignatureVerifier(signature),
        attestation_signature_verifier=SignatureVerifier(attestation_signature),
        capability_signature_verifier=SignatureVerifier(True),
        digest_measurer=Measurer(measured),
        generation_store=ProjectionGenerationStore(str(tmp_path / "generations.sqlite3")),
        environment="production",
    )


def test_projects_kernel_measured_fsverity_identity(tmp_path):
    service = projector(tmp_path)
    result = service.verify(manifest(), attestation(), lease(), now=NOW)
    assert result.enforcement_mode == "fsverity_strict"
    assert result.loader_digest_specs == (f"1:{DIGEST}",)
    service.commit(result)


@pytest.mark.parametrize(
    "manifest_change,attestation_change",
    [
        ({"audience": "wrong"}, {}),
        ({"attestation_result_id": "other"}, {}),
        ({"attestation_evidence_digest": "sha256:" + "44" * 32}, {}),
        ({}, {"status": AttestationStatus.REJECTED, "hard_failures": ("quote",)}),
        ({}, {"audience": "wrong"}),
    ],
)
def test_rejects_broken_attestation_bindings(tmp_path, manifest_change, attestation_change):
    with pytest.raises(KernelProjectionError):
        projector(tmp_path).verify(
            manifest(**manifest_change), attestation(**attestation_change), lease(), now=NOW
        )


def test_rejects_invalid_manifest_or_attestation_signature(tmp_path):
    with pytest.raises(KernelProjectionError, match="manifest_signature"):
        projector(tmp_path, signature=False).verify(manifest(), attestation(), lease(), now=NOW)
    with pytest.raises(KernelProjectionError, match="attestation_signature"):
        projector(tmp_path, attestation_signature=False).verify(manifest(), attestation(), lease(), now=NOW)


def test_rejects_digest_mismatch_or_nonverity_file(tmp_path):
    with pytest.raises(KernelProjectionError, match="digest mismatch"):
        projector(tmp_path, measured=(1, "cd" * 32)).verify(manifest(), attestation(), lease(), now=NOW)


def test_generation_commit_is_atomic_and_replay_safe(tmp_path):
    service = projector(tmp_path)
    result = service.verify(manifest(), attestation(), lease(), now=NOW)
    service.commit(result)
    with pytest.raises(KernelProjectionError, match="stale or replayed"):
        service.verify(manifest(), attestation(), lease(), now=NOW)


def test_rejects_stale_or_future_manifest(tmp_path):
    expired = manifest(
        issued_at=(NOW - timedelta(minutes=10)).isoformat(),
        expires_at=(NOW - timedelta(minutes=1)).isoformat(),
    )
    with pytest.raises(KernelProjectionError, match="freshness"):
        projector(tmp_path).verify(expired, attestation(), lease(), now=NOW)


class ProjectionSink:
    def __init__(self):
        self.events = []

    def stage(self, projection):
        self.events.append(("stage", projection.generation))

    def activate(self, generation):
        self.events.append(("activate", generation))

    def deactivate(self, generation, reason):
        self.events.append(("deactivate", generation, reason))

    def remove(self, generation):
        self.events.append(("remove", generation))


def projection(generation=7, **changes):
    values = dict(
        manifest_id=f"manifest-{generation}",
        manifest_digest="sha256:" + f"{generation:02x}" * 32,
        generation=generation,
        node_id="node-1",
        attestation_result_id="result-1",
        capability_lease_id="lease-1",
        policy_generation="policy-generation-7",
        cgroup_id="beast.slice/mission-1",
        cgroup_kernel_id=987654,
        pid_namespace_inode=41001,
        mount_namespace_inode=41002,
        expires_at=(NOW + timedelta(minutes=1)).isoformat(),
        loader_digest_specs=(f"1:{DIGEST}",),
        verified_paths=("/opt/arda/bin/worker",),
    )
    values.update(changes)
    return VerifiedKernelProjectionV1(**values)


def test_projection_generation_is_staged_then_atomically_activated(tmp_path):
    sink = ProjectionSink()
    generations = ProjectionGenerationStore(str(tmp_path / "generation.sqlite"))
    reconciler = KernelProjectionReconciler(
        str(tmp_path / "projection.sqlite"), sink=sink, generation_store=generations
    )
    reconciler.apply(projection())
    assert sink.events[:2] == [("stage", 7), ("activate", 7)]
    assert reconciler.active("node-1")["generation"] == 7
    with pytest.raises(KernelProjectionError, match="stale or replayed"):
        reconciler.apply(projection())


@pytest.mark.parametrize(
    "revoked,runtime,instant,reason",
    [
        (("lease-1",), {}, NOW, "capability_revoked"),
        ((), {"node-1": ("wrong-cgroup", 41001, 41002)}, NOW, "runtime_binding_drift"),
        ((), {}, NOW + timedelta(minutes=2), "expired"),
    ],
)
def test_projection_reconciliation_removes_revoked_expired_or_drifted_entries(
    tmp_path, revoked, runtime, instant, reason
):
    sink = ProjectionSink()
    reconciler = KernelProjectionReconciler(
        str(tmp_path / f"projection-{reason}.sqlite"),
        sink=sink,
        generation_store=ProjectionGenerationStore(str(tmp_path / f"generation-{reason}.sqlite")),
    )
    reconciler.apply(projection())
    actions = reconciler.reconcile(
        now=instant,
        revoked_lease_ids=revoked,
        runtime_bindings=runtime,
    )
    assert actions == ({"generation": 7, "reason": reason},)
    assert ("deactivate", 7, reason) in sink.events
    assert ("remove", 7) in sink.events
    assert reconciler.active("node-1") == {}


class RecordingBpftoolSink(BpftoolPinnedProjectionSink):
    def __init__(self):
        super().__init__(bpftool="/bin/true")
        self.commands = []

    def _run(self, *args, json_output=False):
        self.commands.append(args)
        return [] if json_output else None


def test_live_sink_stages_then_flips_per_cgroup_generation():
    sink = RecordingBpftoolSink()
    item = projection()
    sink.stage(item)
    sink.activate(item.generation)
    assert any(command[:3] == ("map", "update", "pinned") for command in sink.commands)
    active = sink.commands[-1]
    assert "arda_active_generation_map" in active[3]
    assert "07" in active
