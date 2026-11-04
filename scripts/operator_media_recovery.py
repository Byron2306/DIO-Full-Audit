"""Production Studio, bounded media-only recovery for existing marketing runs.

No semantic regeneration, release authority, or writes to historical operator receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RUN_BASE = ROOT / 'state/operator_production/marketing'
RUN_ID = re.compile(r'^MKT-\d{8}T\d{6}Z-[A-Z0-9]{6,16}$')
FAMILY_SUBPATH = Path('operator-diligenceroom/operator-audience')  # only used for display, not lookup
STATUS_NAME = 'MEDIA_RECOVERY_STATUS.json'
RECOVERY_NAME = 'MEDIA_RECOVERY_RECEIPT.json'
LOCK_NAME = '.media-recovery.lock'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path):
    with path.open('rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.tmp.{os.getpid()}')
    with temp.open('w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=True)
        fh.write('\n')
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, path)


def run_path(run_id: str):
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError('Invalid marketing run ID')
    folder = (RUN_BASE / run_id).resolve(strict=True)
    if not folder.is_dir() or not folder.is_relative_to(RUN_BASE.resolve()):
        raise ValueError('Marketing run is outside the approved production root')
    return folder


def locate(run: Path):
    receipt_path = run / 'OPERATOR_MARKETING_RECEIPT.json'
    if not receipt_path.is_file():
        raise ValueError('Historical operator marketing receipt not found')
    orig = load(receipt_path)
    if orig.get('run_id') != run.name:
        raise ValueError('Marketing receipt run ID mismatch')
    candidates = list(run.glob('*/operator-audience/NICHEFOUNDRY_PRODUCTION_REQUEST.json'))
    # Support arbitrary audience folder naming while requiring exactly one request.
    if not candidates:
        candidates = list(run.glob('*/*/NICHEFOUNDRY_PRODUCTION_REQUEST.json'))
    if len(candidates) != 1:
        raise ValueError(f'Expected exactly one production request, got {len(candidates)}')
    req_path = candidates[0].resolve(strict=True)
    if not req_path.is_relative_to(run):
        raise ValueError('Production request escapes the run directory')
    request = load(req_path)
    if request.get('schema') != 'nichefoundry.dio_campaign_production_request.v3':
        raise ValueError('Unsupported NicheFoundry request schema')
    if request.get('release', {}).get('state') != 'held' or request.get('release', {}).get('spend') != 'disabled':
        raise ValueError('Media request does not retain publication/spend holds')
    variants = request.get('variants') or {}
    if set(variants) != {'vertical_short', 'landscape_explainer'}:
        raise ValueError('Production request must have both video variants')
    family = orig.get('family') or {}
    semantic = request.get('semantic_law') or {}
    projection = request.get('projection') or {}
    for key, expected in (
        ('semantic_law_hash', (family.get('semantic_law') or {}).get('semantic_law_hash')),
        ('projection_hash', (family.get('creative_projection') or {}).get('projection_hash')),
        ('creative_fingerprint', (family.get('creative_projection') or {}).get('creative_fingerprint')),
    ):
        observed = (semantic if key == 'semantic_law_hash' else projection).get(key)
        if not expected or not observed or observed != expected:
            raise ValueError(f'Original marketing identity mismatch: {key}')
    for surface, variant in variants.items():
        scenes = (variant.get('story') or {}).get('scenes') or []
        images = variant.get('scene_images_fallback') or []
        if not scenes or len(scenes) != len(images):
            raise ValueError(f'Incomplete scene-to-image binding: {surface}')
        for value in images:
            path = Path(str(value)).expanduser().resolve(strict=True)
            if not path.is_file() or not path.is_relative_to(run):
                raise ValueError(f'Unexpected scene input outside run: {surface}')
        voice = variant.get('voice') or {}
        if not (voice.get('provider') == 'pocket_tts' and voice.get('voice') == 'vera'
                and voice.get('remote_tts_allowed') is False):
            raise ValueError(f'Approved local Vera voice contract failed: {surface}')
        output = Path(str((variant.get('output') or {}).get('path') or '')).expanduser().resolve()
        if not output.is_relative_to(run):
            raise ValueError(f'Output outside original run: {surface}')
    return receipt_path, orig, req_path, request


def media_receipt_path(req_path):
    return req_path.parent / 'media/CAMPAIGN_MEDIA_RECEIPT.json'


def verify_completed_media(req_path, request):
    media_path = media_receipt_path(req_path)
    if not media_path.is_file():
        return None
    media = load(media_path)
    if media.get('schema') != 'dio.campaign_media_receipt.v3' or media.get('state') != 'ready':
        raise ValueError('Media receipt is not a ready v3 Document Studio receipt')
    if media.get('request_hash') != request.get('request_hash'):
        raise ValueError('Media receipt request hash mismatch')
    if media.get('semantic_law_hash') != request['semantic_law']['semantic_law_hash']:
        raise ValueError('Media receipt semantic law mismatch')
    for k in ('projection_hash', 'creative_fingerprint'):
        if media.get(k) != request['projection'][k]:
            raise ValueError(f'Media receipt {k} mismatch')
    governance = media.get('governance') or {}
    if governance.get('spend') != 'disabled' or governance.get('authority_created') is not False:
        raise ValueError('Media receipt governance hold invalid')
    if governance.get('publication') != 'held_for_operator_approval':
        raise ValueError('Media receipt publication not held')
    outputs = media.get('outputs') or {}
    checked = {}
    for surface, key in (('vertical_short', 'vertical_reel'), ('landscape_explainer', 'long_form_explainer')):
        row = outputs.get(key) or {}
        path = Path(str(row.get('path') or '')).expanduser().resolve(strict=True)
        expected_output = Path(str(request['variants'][surface]['output']['path'])).expanduser().resolve()
        if path != expected_output or not path.is_file() or not path.is_relative_to(req_path.parent.parent.parent):
            raise ValueError(f'Output path mismatch: {key}')
        digest = sha(path)
        if digest != row.get('sha256') or path.stat().st_size < 10000:
            raise ValueError(f'Output file integrity mismatch: {key}')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                '-of', 'default=nokey=1:noprint_wrappers=1', str(path)],
                               capture_output=True, text=True, timeout=20)
        if probe.returncode or float(probe.stdout.strip()) <= 0:
            raise ValueError(f'Invalid playable output: {key}')
        checked[key] = {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}
    return {'media_receipt': str(media_path), 'media_receipt_sha256': sha(media_path), 'outputs': checked}


def inspect_run(run_id: str):
    run = run_path(run_id)
    historic_path, historic, req_path, request = locate(run)
    state_path = run / STATUS_NAME
    recovery_path = run / RECOVERY_NAME
    state = load(state_path) if state_path.is_file() else {}
    ready = None
    error = None
    try:
        ready = verify_completed_media(req_path, request)
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        error = str(exc)
    return {
        'run_id': run_id,
        'incarnation': historic.get('incarnation'),
        'original_voice_state': (historic.get('family') or {}).get('voice', {}).get('state'),
        'original_receipt_sha256': sha(historic_path),
        'media_ready': ready is not None,
        'verified_media': ready,
        'media_validation_error': error,
        'recovery_receipt_exists': recovery_path.is_file(),
        'recovery_receipt': str(recovery_path) if recovery_path.is_file() else None,
        'job': state,
        'retry_running': (run / LOCK_NAME).exists(),
        'publication_authorized': False,
        'spend_authorized': False,
    }


def reconcile_run(run_id: str):
    run = run_path(run_id)
    orig_path, orig, req_path, request = locate(run)
    completed = verify_completed_media(req_path, request)
    if completed is None:
        raise ValueError('No completed Document Studio media receipt exists for reconciliation')
    recovery_path = run / RECOVERY_NAME
    if recovery_path.exists():
        prior = load(recovery_path)
        if prior.get('media_receipt_sha256') != completed['media_receipt_sha256']:
            raise ValueError('Existing recovery receipt conflicts with current media')
        return inspect_run(run_id)
    write_atomic(recovery_path, {
        'schema': 'dio.operator_production.marketing_media_recovery.v1',
        'run_id': run_id, 'mode': 'reconciled_existing_media', 'created_at': now(),
        'historical_receipt': str(orig_path), 'historical_receipt_sha256': sha(orig_path),
        'production_request': str(req_path), 'production_request_sha256': sha(req_path),
        'semantic_law_hash': request['semantic_law']['semantic_law_hash'],
        'projection_hash': request['projection']['projection_hash'],
        'creative_fingerprint': request['projection']['creative_fingerprint'],
        'media_receipt': completed['media_receipt'],
        'media_receipt_sha256': completed['media_receipt_sha256'],
        'outputs': completed['outputs'], 'publication': 'held', 'spend': 'disabled',
        'authority_created': False,
    })
    return inspect_run(run_id)


def launch_retry(run_id: str):
    run = run_path(run_id)
    orig_path, orig, req_path, request = locate(run)
    if verify_completed_media(req_path, request) is not None:
        raise ValueError('Valid completed media already exists. Use Reconcile instead of retrying')
    if media_receipt_path(req_path).exists():
        raise ValueError('Existing media receipt failed validation: manual investigation required')
    media_dir = req_path.parent / 'media'
    if media_dir.exists() and any(p.is_file() for p in media_dir.rglob('*')):
        raise ValueError('Partial media artifacts exist. Preserve/inspect them before retry')
    lock = run / LOCK_NAME
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Media recovery is already running or has a stale lock')
    try:
        with os.fdopen(fd, 'w') as fh:
            fh.write(f'launcher_pid={os.getpid()}\ncreated={now()}\n')
        write_atomic(run / STATUS_NAME, {'state': 'queued', 'run_id': run_id, 'created_at': now()})
        log = run / 'MEDIA_RECOVERY_WORKER.log'
        with log.open('ab') as out:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', run_id],
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                    cwd=str(ROOT), start_new_session=True, close_fds=True)
        write_atomic(run / STATUS_NAME, {'state': 'started', 'run_id': run_id, 'pid': proc.pid,
                                         'created_at': now(), 'log': str(log)})
    except Exception:
        lock.unlink(missing_ok=True)
        raise
    return inspect_run(run_id)



def verify_or_refresh_vera_inventory():
    """Refresh only stale PID/start observations; never relax command/file hashes."""
    from presence_core.voice import verified_vera_runtime_inventory
    try:
        return verified_vera_runtime_inventory(ROOT)
    except RuntimeError as exc:
        if str(exc) not in {'observed local Vera service is unavailable',
                            'observed local Vera service command changed'}:
            raise
    path = Path(os.getenv('DIO_VESPER_RUNTIME_INVENTORY') or
                (ROOT / 'state/presence/voice_verification/vera_runtime_inventory.json'))
    inventory = load(path)
    if (inventory.get('schema') != 'dio.vesper.local_verified_runtime_inventory.v1'
            or inventory.get('evidence_class') != 'LOCAL_VERIFIED_RUNTIME_INVENTORY'):
        raise ValueError('Vera inventory schema/evidence class invalid')
    service = inventory.get('service') or {}
    base = (os.getenv('DIO_VESPER_POCKET_TTS_URL') or 'http://127.0.0.1:8000').rstrip('/')
    if service.get('endpoint') != base + '/tts':
        raise ValueError('Vera service endpoint changed: refuse automatic refresh')
    result = subprocess.run(['systemctl', '--user', 'show', 'dio-vera-tts.service',
                             '-p', 'MainPID', '--value'], text=True, capture_output=True, timeout=10, check=True)
    pid = int(result.stdout.strip())
    if pid <= 0:
        raise ValueError('Vera systemd service has no active main process')
    proc = Path(f'/proc/{pid}')
    def observed():
        command = proc.joinpath('cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
        start = proc.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19]
        return command, start
    command, ticks = observed()
    if not command or command != service.get('command'):
        raise ValueError('Vera systemd command changed: refuse automatic refresh')
    for row in inventory.get('files') or []:
        file = Path(str(row.get('path') or ''))
        if not file.is_file() or sha(file) != row.get('sha256'):
            raise ValueError('Vera runtime file changed: ' + str(row.get('role')))
    roles = {r.get('role'): r for r in inventory.get('files') or []}
    provenance = inventory.get('model_provenance') or {}
    if (provenance.get('voice_id') != 'vera'
            or (roles.get('model') or {}).get('sha256') != provenance.get('model_sha256')
            or (roles.get('voice') or {}).get('sha256') != provenance.get('voice_sha256')):
        raise ValueError('Vera model or voice integrity failed')
    if observed() != (command, ticks):
        raise ValueError('Vera process changed during verification')
    old = path.read_bytes()
    backup = path.with_name(path.name + '.before-recovery-' +
                            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') +
                            f'-{os.getpid()}')
    with backup.open('xb') as out:
        out.write(old)
    service['pid'] = pid
    service['command'] = command
    service['process_start_ticks'] = ticks
    inventory['observed_at'] = now()
    write_atomic(path, inventory)
    return verified_vera_runtime_inventory(ROOT)


def worker(run_id: str):
    run = run_path(run_id)
    orig_path, orig, req_path, request = locate(run)
    before = {str(p): sha(p) for p in (orig_path, req_path,
              run / 'SEMANTIC_MARKETING_BRIEF.json') if p.is_file()}
    try:
        write_atomic(run / STATUS_NAME, {'state': 'rendering', 'run_id': run_id, 'pid': os.getpid(), 'updated_at': now()})
        verify_or_refresh_vera_inventory()
        from scripts.nichefoundry_visual_spine import render_art_directed_campaign_media
        render_art_directed_campaign_media(req_path)
        for name, digest in before.items():
            if sha(Path(name)) != digest:
                raise ValueError('Production source or historical receipt changed during recovery: ' + name)
        completed = verify_completed_media(req_path, request)
        if completed is None:
            raise ValueError('Renderer did not produce a complete media receipt')
        recovery_path = run / RECOVERY_NAME
        if recovery_path.exists():
            raise ValueError('Recovery receipt already exists; refuse overwrite')
        write_atomic(recovery_path, {
            'schema': 'dio.operator_production.marketing_media_recovery.v1',
            'run_id': run_id, 'mode': 'media_only_retry', 'created_at': now(),
            'historical_receipt': str(orig_path), 'historical_receipt_sha256': sha(orig_path),
            'production_request': str(req_path), 'production_request_sha256': sha(req_path),
            'semantic_law_hash': request['semantic_law']['semantic_law_hash'],
            'projection_hash': request['projection']['projection_hash'],
            'creative_fingerprint': request['projection']['creative_fingerprint'],
            'media_receipt': completed['media_receipt'],
            'media_receipt_sha256': completed['media_receipt_sha256'],
            'outputs': completed['outputs'], 'publication': 'held', 'spend': 'disabled',
            'authority_created': False,
        })
        write_atomic(run / STATUS_NAME, {'state': 'ready', 'run_id': run_id, 'updated_at': now()})
        print('MEDIA_RECOVERY=PASS', flush=True)
    except Exception as exc:
        traceback.print_exc()
        write_atomic(run / STATUS_NAME, {'state': 'failed', 'run_id': run_id,
                                         'updated_at': now(), 'error': str(exc)})
        raise
    finally:
        (run / LOCK_NAME).unlink(missing_ok=True)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: operator_media_recovery.py status|reconcile|worker RUN_ID')
    action, run_id = sys.argv[1:]
    if action == 'status':
        print(json.dumps(inspect_run(run_id), indent=2))
    elif action == 'reconcile':
        print(json.dumps(reconcile_run(run_id), indent=2))
    elif action == 'worker':
        worker(run_id)
    else:
        raise SystemExit('Unsupported action')
