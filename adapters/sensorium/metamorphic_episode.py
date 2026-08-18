from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


class MetamorphicSensoriumError(RuntimeError):
    pass


def load_sensorium_runtime_class(repo_root: str | Path) -> type:
    root = Path(repo_root).resolve()
    beast_root = root / "cross_folder_variants/EdgeK-BEAST/A_CODE"
    if not beast_root.is_dir():
        raise MetamorphicSensoriumError(f"Sensorium root missing: {beast_root}")
    value = str(beast_root)
    if value not in sys.path:
        sys.path.insert(0, value)
    module = importlib.import_module("app.kernel.sensorium.runtime")
    runtime_cls = getattr(module, "SensoriumRuntime", None)
    if runtime_cls is None:
        raise MetamorphicSensoriumError("BEAST SensoriumRuntime unavailable")
    return runtime_cls


def create_runtime(repo_root: str | Path, *, out_dir: str | Path) -> Any:
    Runtime = load_sensorium_runtime_class(repo_root)
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return Runtime(export_root=out / "outbox", boot_id="dio-metamorphic-phase6")


def observe(runtime: Any, *, mission_id: str, event_type: str, payload: dict[str, Any]) -> str:
    receipt = runtime.observe_owned(
        event_type=event_type,
        source="dio_metamorphic_phase6",
        payload_schema="dio.metamorphic.sensorium_event.v1",
        payload=payload,
        mission_id=mission_id,
        workspace_id="dio-metamorphic-m1",
        confidence_method="native_execution_receipt",
    )
    event_id = str(receipt.admitted.event_id)
    if not event_id:
        raise MetamorphicSensoriumError("Sensorium admitted event has no identity")
    return event_id


def close_episode(
    runtime: Any,
    *,
    mission_id: str,
    objective_hash: str,
    initial_state_hash: str,
    outcome: dict[str, Any],
) -> dict[str, Any]:
    episode = runtime.close_episode(
        mission_id,
        objective_hash=objective_hash,
        workspace_identity="dio-metamorphic-m1",
        initial_state_hash=initial_state_hash,
        outcome=outcome,
        resources={},
        export=False,
    )
    payload = episode.to_dict()
    if payload.get("authority") != "evidence_only":
        raise MetamorphicSensoriumError("Sensorium episode authority boundary changed")
    return payload
