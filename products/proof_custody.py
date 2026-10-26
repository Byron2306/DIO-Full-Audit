"""Freeze completed local ingress state for proof, without sealing live WAL files."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_ingress_custody(case_root: Path) -> set[str]:
    """Return only the live ledger paths replaced by verified immutable snapshots.

    Called after the web turn completes and before the case receipt is sealed.
    A snapshot records that boundary; it does not assert later live state is equal.
    Existing snapshots are validated and never silently refreshed.
    """
    root = Path(case_root).resolve()
    chat = root / 'VESPER_WEB_CHAT'
    ledgers = sorted((chat / 'sessions').glob('*/INGRESS.sqlite'))
    if not ledgers:
        return set()
    proof = chat / 'PROOF_CUSTODY'
    if proof.is_symlink():
        raise ValueError('ingress custody directory is a symlink')
    for db in ledgers:
        if db.is_symlink() or not db.resolve().is_relative_to(root):
            raise ValueError('ingress custody source escapes case')
    if not proof.exists():
        temporary = Path(tempfile.mkdtemp(prefix='.ingress-custody-', dir=chat))
        try:
            rows = []
            for db in ledgers:
                target = temporary / db.parent.name / 'INGRESS.sqlite'
                target.parent.mkdir()
                src = sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=5)
                dst = sqlite3.connect(target)
                try:
                    src.backup(dst)
                    dst.execute('PRAGMA journal_mode=DELETE')
                    if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('ingress custody snapshot integrity failed')
                    pending = dst.execute("SELECT count(*) FROM ingress_receipts WHERE state IS NULL OR state!='completed'").fetchone()[0]
                    count = dst.execute('SELECT count(*) FROM ingress_receipts').fetchone()[0]
                    if pending or not count:
                        raise ValueError('incomplete ingress cannot be sealed')
                finally:
                    dst.close();src.close()
                rows.append({'source_path':str(db.relative_to(root)),
                             'path':str((proof/db.parent.name/'INGRESS.sqlite').relative_to(root)),
                             'sha256':_hash(target),'bytes':target.stat().st_size,
                             'completed_events':count})
            manifest = {'schema':'dio.professional_evidence.ingress_custody.v1',
                        'boundary':'completed_web_turn_before_product_receipt',
                        'snapshot_method':'sqlite_online_backup',
                        'live_journals_are_not_proof_artifacts':True,
                        'authority_created':False,'snapshots':rows}
            (temporary/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
            os.rename(temporary,proof)
        finally:
            if temporary.exists(): shutil.rmtree(temporary)
    manifest_path = proof/'MANIFEST.json'
    if manifest_path.is_symlink(): raise ValueError('ingress custody manifest is a symlink')
    manifest = json.loads(manifest_path.read_text())
    rows = manifest.get('snapshots',[])
    if {r['source_path'] for r in rows} != {str(p.relative_to(root)) for p in ledgers}:
        raise ValueError('ingress custody source set changed')
    excluded = set()
    for row in rows:
        p = root/row['path']
        if p.is_symlink() or not p.resolve().is_relative_to(proof.resolve()) or not p.is_file() or p.stat().st_size != row['bytes'] or _hash(p) != row['sha256']:
            raise ValueError('ingress custody snapshot changed')
        excluded.update(row['source_path']+suffix for suffix in ('','-wal','-shm'))
    return excluded
