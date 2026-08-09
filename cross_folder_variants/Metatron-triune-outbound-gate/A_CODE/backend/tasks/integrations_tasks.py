import os
import subprocess
import json
import re
from datetime import datetime
try:
    from celery.utils.log import get_task_logger
    from celery import shared_task
    logger = get_task_logger(__name__)
except Exception:
    # Celery not installed in lightweight test environments; provide fallbacks
    def get_task_logger(name):
        import logging as _logging
        return _logging.getLogger(name)

    def shared_task(**kwargs):
        # decorator passthrough that returns the function unchanged
        def _decorator(fn):
            return fn
        return _decorator

    logger = get_task_logger(__name__)

import requests
try:
    from services.attack_metadata import build_celery_attack_metadata
except Exception:
    from backend.services.attack_metadata import build_celery_attack_metadata

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None


def _emit_task_event(db, event_type: str, entity_refs=None, payload=None, task_name: str = ""):
    if emit_world_event is None or db is None:
        return
    attack_metadata = build_celery_attack_metadata(
        task_name=task_name or "backend.tasks.integrations_tasks.run_velociraptor_task",
        event_type=event_type,
        payload=payload or {},
    )
    enriched_payload = dict(payload or {})
    enriched_payload["attack_metadata"] = attack_metadata
    enriched_payload["attack_techniques"] = attack_metadata.get("techniques", [])
    enriched_payload["attack_tactics"] = attack_metadata.get("tactics", [])
    import asyncio
    try:
        asyncio.run(
            emit_world_event(
                db,
                event_type=event_type,
                entity_refs=entity_refs or [],
                payload=enriched_payload,
                trigger_triune=None,
                source="task.integrations",
            )
        )
    except Exception:
        pass

# Endpoint config for central ingestion API
API_URL = os.environ.get('API_URL', 'http://localhost:8001').rstrip('/')
INGEST_ENDPOINT = f"{API_URL}/api/integrations/ingest/direct"
INTERNAL_TOKEN = os.environ.get('INTEGRATION_API_KEY', '')


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}, soft_time_limit=3600, time_limit=4000)
def run_velociraptor_task(self, job_id: str, collection_name: str = None):
    """Celery task to run Velociraptor collection and POST extracted indicators to central ingestion API."""
    # mark running via API / DB update handled by integrations_manager earlier
    db_for_events = None
    try:
        from backend.server import db as _db
        db_for_events = _db
    except Exception:
        db_for_events = None
    task_name = getattr(self, "name", "backend.tasks.integrations_tasks.run_velociraptor_task")
    start_payload = {"collection_name": collection_name}
    _emit_task_event(
        db_for_events,
        "integrations_velociraptor_task_started",
        [job_id],
        start_payload,
        task_name=task_name,
    )

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    integrations_dir = os.environ.get('INTEGRATIONS_DIR', '/tmp/integrations')
    outdir = os.path.join(integrations_dir, f"velociraptor_{ts}")
    os.makedirs(outdir, exist_ok=True)

    if collection_name:
        cli_cmd = f"velociraptor --config /config/config.yaml collect --collection {collection_name} --output /data/collection_{ts}.json"
    else:
        cli_cmd = f"velociraptor --config /config/config.yaml collect --output /data/collection_{ts}.json"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{outdir}:/data",
        "wlambert/velociraptor:latest",
        "/opt/velociraptor/linux/velociraptor",
        "--config",
        "/config/config.yaml",
        "collect",
    ]
    if collection_name:
        cmd.extend(["--collection", collection_name])
    cmd.extend(["--output", f"/data/collection_{ts}.json"])

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        logger.error(f"Velociraptor failed: {proc.stderr}")
        failure_payload = {"error": proc.stderr[:500]}
        _emit_task_event(
            db_for_events,
            "integrations_velociraptor_task_failed",
            [job_id],
            failure_payload,
            task_name=task_name,
        )
        attack_metadata = build_celery_attack_metadata(
            task_name=task_name,
            event_type="integrations_velociraptor_task_failed",
            payload=failure_payload,
        )
        try:
            from pymongo import MongoClient
            MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
            DB_NAME = os.environ.get('DB_NAME', 'metatron')
            client = MongoClient(MONGO_URL)
            db = client[DB_NAME]
            db.integrations_jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "failed",
                    "attack_metadata": attack_metadata,
                    "updated_at": datetime.utcnow().isoformat(),
                }},
            )
        except Exception:
            logger.exception('Failed to persist failed job ATT&CK metadata')
        # raise to trigger retry
        raise RuntimeError(f"Velociraptor failed: {proc.stderr}")

    # find collection file
    collection_file = None
    artifacts = []
    for fn in os.listdir(outdir):
        artifacts.append(fn)
        if fn.startswith('collection_') and fn.endswith('.json'):
            collection_file = os.path.join(outdir, fn)
            break

    indicators = []
    if collection_file:
        indicators = extract_indicators_from_collection(collection_file)

    ingested = 0
    result = {'ingested': 0, 'artifacts': artifacts, 'artifact_dir': outdir}

    if indicators:
        # Post to central ingestion API
        try:
            headers = {'Content-Type': 'application/json'}
            if INTERNAL_TOKEN:
                headers['X-Internal-Token'] = INTERNAL_TOKEN
            payload = {'source': 'velociraptor', 'indicators': indicators}
            r = requests.post(INGEST_ENDPOINT, json=payload, headers=headers, timeout=30)
            if r.status_code == 200:
                j = r.json()
                ingested = j.get('result', {}).get('ingested', 0) if isinstance(j, dict) else 0
                result['ingested'] = ingested
            else:
                logger.error(f"Ingest API returned {r.status_code}: {r.text}")
        except Exception as e:
            logger.exception(f"Failed to POST indicators to ingestion API: {e}")
            _emit_task_event(
                db_for_events,
                "integrations_velociraptor_ingest_post_failed",
                [job_id],
                {"error": str(e)[:500]},
                task_name=task_name,
            )

    # Update job document via direct DB (best-effort) if API not used by integrations_manager
    completion_payload = {"ingested": ingested, "artifact_count": len(artifacts), "indicator_count": len(indicators)}
    attack_metadata = build_celery_attack_metadata(
        task_name=task_name,
        event_type="integrations_velociraptor_task_completed",
        payload=completion_payload,
    )
    try:
        from pymongo import MongoClient
        MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        DB_NAME = os.environ.get('DB_NAME', 'metatron')
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        db.integrations_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "completed",
                "result": {**result, "attack_metadata": attack_metadata},
                "attack_metadata": attack_metadata,
                "updated_at": datetime.utcnow().isoformat(),
            }},
        )
    except Exception:
        logger.exception('Failed to update job document in DB')

    logger.info(f"Velociraptor job {job_id} completed, ingested {ingested}")
    _emit_task_event(
        db_for_events,
        "integrations_velociraptor_task_completed",
        [job_id],
        completion_payload,
        task_name=task_name,
    )


def extract_indicators_from_collection(collection_file: str):
    """Extract IPs, domains, hashes from a collection file and optionally run Yara rules.
    Returns list of indicator dicts.
    """
    indicators = []
    try:
        text = open(collection_file, 'r', encoding='utf-8', errors='ignore').read()
        ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", text))
        domains = set(re.findall(r"\b([a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})\b", text))
        sha256s = set(re.findall(r"\b[a-fA-F0-9]{64}\b", text))
        for ip in ips:
            indicators.append({'type': 'ip', 'value': ip, 'confidence': 60})
        for d in domains:
            indicators.append({'type': 'domain', 'value': d, 'confidence': 50})
        for h in sha256s:
            indicators.append({'type': 'sha256', 'value': h, 'confidence': 60})
    except Exception as e:
        logger.exception(f"Failed to parse collection file: {e}")

    # Optional Yara rules
    yara_rules_dir = os.environ.get('YARA_RULES_DIR')
    if yara_rules_dir:
        # try yara-python first
        try:
            import yara
            rules = yara.compile(filepath=yara_rules_dir) if os.path.isfile(yara_rules_dir) else yara.compile(filepaths={})
            matches = rules.match(collection_file)
            for m in matches:
                indicators.append({'type': 'yara', 'value': m.rule, 'confidence': 80, 'tags': ['yara']})
        except Exception:
            # fallback to command-line yara
            try:
                yc = subprocess.run(
                    ["yara", "-r", yara_rules_dir, collection_file],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if yc.returncode == 0 and yc.stdout:
                    for line in yc.stdout.splitlines():
                        parts = line.strip().split()
                        if not parts:
                            continue
                        rule_name = parts[0]
                        indicators.append({'type': 'yara', 'value': rule_name, 'confidence': 80, 'tags': ['yara']})
            except Exception:
                logger.exception('Yara scan failed')

    return indicators
