import hashlib
import sqlite3
from pathlib import Path

from products.professional_evidence_execution import _build_vamp_database


def test_professional_vamp_sha1_matches_source_bytes(tmp_path, monkeypatch):
    import products.professional_evidence_execution as execution

    monkeypatch.setattr(
        execution,
        "evidence_rows",
        lambda packet: [
            {"customer_supplied_record": "Controlled source evidence"}
        ],
    )

    packet = {"packet_fingerprint": "test-fingerprint"}
    db_path = tmp_path / "projection" / "progress.db"
    db_path.parent.mkdir(parents=True)

    _build_vamp_database(packet, db_path)

    with sqlite3.connect(db_path) as connection:
        recorded_hash, source_path = connection.execute(
            "SELECT sha1, file_path FROM evidence"
        ).fetchone()

    source_bytes = Path(source_path).read_bytes()

    assert recorded_hash == hashlib.sha1(source_bytes).hexdigest()
    assert recorded_hash != hashlib.sha256(source_bytes).hexdigest()[:40]
