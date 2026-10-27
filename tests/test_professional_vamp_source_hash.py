import hashlib
import sqlite3
from pathlib import Path

from products.professional_evidence_execution import _build_vamp_database
from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_projection import load_packet


def test_professional_vamp_sha1_matches_source_bytes(tmp_path):
    # Use a real hash-bound packet so this regression applies to both the base
    # adapter and the installed compatibility adapter, regardless of test order.
    materialize_customer_packet("VAMP Performance", tmp_path)
    packet_dir = next(tmp_path.glob("*/CUSTOMER_PACKET"))
    enrich_customer_packet("VAMP Performance", packet_dir)
    packet = load_packet(packet_dir)
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
