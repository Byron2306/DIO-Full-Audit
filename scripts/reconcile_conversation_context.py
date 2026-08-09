#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conversation_core.context import build_conversation_context, timestamp, write_conversation_context  # noqa: E402
from conversation_core.outlook import build_outlook_conversation_context  # noqa: E402
from conversation_core.presence import load_presence_turns  # noqa: E402


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _json_files(path: Path) -> list[Path]:
    return sorted(path.glob("*.json")) if path.exists() else []


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)[:180] or "unknown"


def _write_index(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _presence_intake_turns(root: Path, conversation_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _json_files(root / "state" / "presence" / "intakes"):
        intake = _read(path)
        if str(intake.get("conversation_id") or "") != conversation_id:
            continue
        text = str(intake.get("summary") or "").strip()
        if not text:
            continue
        rows.append({
            "source_ref": f"presence_intake:{intake.get('intake_id') or path.stem}",
            "direction": "inbound",
            "delivery_state": "received",
            "observed_at": intake.get("created_at"),
            "text": text,
            "actor_role": "public_user",
        })
    return rows


def reconcile_conversation_contexts(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    target = root / "state" / "conversation_context"
    target.mkdir(parents=True, exist_ok=True)

    mail_ingress = [_read(path) for path in _json_files(root / "state" / "mail_ingress")]
    mail_intents = [_read(path) for path in _json_files(root / "state" / "mail_intents")]
    outlook_ids = sorted({
        str(row.get("conversation_id"))
        for row in [*mail_ingress, *mail_intents]
        if row.get("conversation_id")
    })

    index: dict[str, dict[str, Any]] = {}
    written = 0
    outlook_written = 0
    presence_written = 0

    for conversation_id in outlook_ids:
        context = build_outlook_conversation_context(
            conversation_id=conversation_id,
            mail_ingress=mail_ingress,
            mail_intents=mail_intents,
        )
        if context["thread"]["turn_count"] == 0:
            continue
        path = target / f"{context['context_id']}.json"
        write_conversation_context(path, context)
        index[conversation_id] = {
            "context_id": context["context_id"],
            "channel": context["channel"],
            "path": str(path.relative_to(root)),
            "thread_state": context["thread"]["state"],
        }
        written += 1
        outlook_written += 1

    presence_root = root / "state" / "presence"
    for conv_path in _json_files(presence_root / "conversations"):
        conversation = _read(conv_path)
        conversation_id = str(conversation.get("conversation_id") or "").strip()
        if not conversation_id:
            continue
        turns = load_presence_turns(presence_root, conversation_id)
        known_refs = {str(turn.get("source_ref") or "") for turn in turns}
        for turn in _presence_intake_turns(root, conversation_id):
            if turn["source_ref"] not in known_refs:
                turns.append(turn)
        if not turns:
            continue
        context = build_conversation_context(
            conversation_id=conversation_id,
            channel=str(conversation.get("channel") or "presence"),
            turns=turns,
            source_refs=[f"presence_conversation:{conversation_id}"],
        )
        path = target / f"{context['context_id']}.json"
        write_conversation_context(path, context)
        index[conversation_id] = {
            "context_id": context["context_id"],
            "channel": context["channel"],
            "path": str(path.relative_to(root)),
            "thread_state": context["thread"]["state"],
        }
        written += 1
        presence_written += 1

    index_payload = {
        "schema": "dio.conversation_context_index.v1",
        "updated_at": timestamp(),
        "contexts": index,
    }
    _write_index(target / "INDEX.json", index_payload)
    return {
        "schema": "dio.conversation_context_reconciliation.v1",
        "updated_at": timestamp(),
        "written": written,
        "outlook": outlook_written,
        "presence": presence_written,
        "index": str((target / "INDEX.json").relative_to(root)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bounded cross-channel DIO conversation context artifacts.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(reconcile_conversation_contexts(args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
