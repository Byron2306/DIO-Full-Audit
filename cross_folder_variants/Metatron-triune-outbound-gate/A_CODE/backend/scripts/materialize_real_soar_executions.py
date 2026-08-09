import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_PATH = ROOT / "backend" / "data" / "soar_executions_archive.json"
sys.path.insert(0, str(ROOT))


def _serialize_execution(execution) -> dict:
    payload = asdict(execution)
    trigger_event = payload.get("trigger_event")
    if isinstance(trigger_event, dict):
        trigger_event.pop("_id", None)
    return payload


async def main() -> None:
    from backend.soar_engine import soar_engine

    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)

    executions = []
    for playbook in soar_engine.playbooks.values():
        techniques = list(playbook.mitre_techniques or [])
        event = {
            "trigger_type": playbook.trigger.value,
            "playbook_id": playbook.id,
            "playbook_name": playbook.name,
            "host_id": "coverage-host-01",
            "session_id": f"coverage-{playbook.id}",
            "source_ip": "203.0.113.10",
            "user": "coverage-user",
            "pid": 4242,
            "file_path": f"/tmp/{playbook.id}.bin",
            "mitre_techniques": techniques,
            "validated_techniques": techniques,
            "reason": "Materialized real SOAR execution for persisted MITRE evidence",
        }
        execution = await soar_engine.execute_playbook(playbook.id, event)
        executions.append(_serialize_execution(execution))

    ARCHIVE_PATH.write_text(json.dumps(executions, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "archive_path": str(ARCHIVE_PATH),
                "execution_count": len(executions),
                "playbook_count": len(soar_engine.playbooks),
                "sample_playbooks": [execution["playbook_id"] for execution in executions[:10]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
