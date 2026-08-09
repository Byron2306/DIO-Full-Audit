from backend.services.measured_identity import MeasuredProjectionGenerationStore


def _projection(manifest_id: str, generation: int) -> dict:
    return {
        "manifest_id": manifest_id,
        "manifest_digest": f"sha256:{generation:064x}"[-71:],
        "generation": generation,
        "node_id": "debian",
        "policy_generation": "ARDA-POLICY-V1@1.1.0",
        "enforcement_mode": "fsverity_strict",
        "loader_digest_specs": ["1:" + ("a" * 64)],
        "checked_paths": ["/usr/bin/python3"],
        "cgroup_id": "/user.slice/user-1000.slice/app.scope",
        "cgroup_kernel_id": 4026531835,
        "pid_namespace_inode": 4026531836,
        "mount_namespace_inode": 4026531841,
        "expires_at": "2026-07-30T00:00:00+00:00",
    }


def test_compact_active_records_keeps_latest_generation(tmp_path):
    store = MeasuredProjectionGenerationStore(str(tmp_path / "measured.sqlite3"))
    try:
        store.stage(_projection("measured-1", 1))
        store.activate("measured-1")
        store.stage(_projection("measured-2", 2))
        store.activate("measured-2")

        store._db.execute(  # noqa: SLF001 - intentional fixture setup for compaction coverage
            "UPDATE arda_measured_staging SET state = 'active', deactivated_at = NULL, failure_reason = NULL WHERE manifest_id = ?",
            ("measured-1",),
        )

        result = store.compact_active_records(node_id="debian", cgroup_id="/user.slice/user-1000.slice/app.scope")
        records = {record["manifest_id"]: record for record in store.list_records()}
    finally:
        store.close()

    assert result["kept_manifest_id"] == "measured-2"
    assert result["compacted_count"] == 1
    assert records["measured-1"]["state"] == "deactivated"
    assert records["measured-1"]["failure_reason"] == "compacted_older_active_generation"
    assert records["measured-2"]["state"] == "active"
