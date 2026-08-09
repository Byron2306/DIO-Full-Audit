import os
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
import asyncio
import threading
from backend.services.attack_metadata import build_celery_attack_metadata

# Celery configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)


celery_app = Celery('metatron_seraph_tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# Optional: load additional config from env
celery_app.conf.update(
    task_track_started=True,
    accept_content=['json'],
    task_serializer='json',
    result_serializer='json',
    task_soft_time_limit=int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', 3600)),
    task_time_limit=int(os.environ.get('CELERY_TASK_TIME_LIMIT', 4000)),
    worker_send_task_events=True,
    worker_redirect_stdouts_level='INFO'
)

# Import tasks so Celery discovers them when worker starts
try:
    # tasks package
    import backend.tasks.integrations_tasks  # noqa: F401
    import backend.tasks.triune_tasks  # noqa: F401
    import backend.tasks.world_ingest_tasks  # noqa: F401
except Exception:
    # Best-effort import; tasks module may not be present during some operations
    pass


def _emit_celery_world_event(event_type: str, payload: dict, trigger_triune: bool = False):
    try:
        from backend.server import db
        from backend.services.world_events import emit_world_event
    except Exception:
        return

    if db is None:
        return

    task_name = str((payload or {}).get("task_name") or "unknown")
    attack_metadata = build_celery_attack_metadata(
        task_name=task_name,
        event_type=event_type,
        payload=payload or {},
    )
    enriched_payload = dict(payload or {})
    enriched_payload["attack_metadata"] = attack_metadata
    enriched_payload["attack_techniques"] = attack_metadata.get("techniques", [])
    enriched_payload["attack_tactics"] = attack_metadata.get("tactics", [])

    coro = emit_world_event(
        db,
        event_type=event_type,
        entity_refs=[task_name],
        payload=enriched_payload,
        trigger_triune=trigger_triune,
        source="celery_app",
    )

    def _runner():
        try:
            asyncio.run(coro)
        except Exception:
            pass

    threading.Thread(target=_runner, daemon=True).start()


@task_prerun.connect
def _on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **extras):
    _emit_celery_world_event(
        "celery_task_started",
        {"task_id": task_id, "task_name": getattr(task, "name", "unknown")},
        trigger_triune=False,
    )


@task_postrun.connect
def _on_task_postrun(task_id=None, task=None, state=None, retval=None, **extras):
    _emit_celery_world_event(
        "celery_task_completed",
        {"task_id": task_id, "task_name": getattr(task, "name", "unknown"), "state": state},
        trigger_triune=str(state).upper() in {"FAILURE", "RETRY"},
    )


@task_failure.connect
def _on_task_failure(task_id=None, exception=None, sender=None, **extras):
    _emit_celery_world_event(
        "celery_task_failed",
        {"task_id": task_id, "task_name": getattr(sender, "name", "unknown"), "error": str(exception)[:500]},
        trigger_triune=True,
    )
