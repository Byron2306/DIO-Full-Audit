from __future__ import annotations
import fcntl, hashlib, json, secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def timestamp() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

def emit_event(event_log: Path, event: str, severity: str, entity_type: str, entity_id: str, data: dict[str,Any], correlation_id: str|None=None) -> dict[str,Any]:
    event_log.parent.mkdir(parents=True,exist_ok=True)
    with event_log.open("a+",encoding="utf-8") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX); handle.seek(0)
        lines=[line for line in handle.read().splitlines() if line.strip()]
        previous=json.loads(lines[-1]).get("event_sha256") if lines else None
        payload={"schema":"dio.event.v1","event_id":f"EVT-{secrets.token_hex(8).upper()}","event":event,"occurred_at":timestamp(),"severity":severity,"entity_type":entity_type,"entity_id":entity_id,"source":"dio_presence","correlation_id":correlation_id,"data":data,"previous_event_sha256":previous}
        payload["event_sha256"]=canonical_hash(payload)
        handle.seek(0,2); handle.write(json.dumps(payload,separators=(",",":"),ensure_ascii=True)+"\n"); handle.flush(); fcntl.flock(handle,fcntl.LOCK_UN)
    return payload
