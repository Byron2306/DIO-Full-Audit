#!/usr/bin/env python3
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _strip_trailing_slash(value: str) -> str:
    while value.endswith("/"):
        value = value[:-1]
    return value


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    _safe_mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _login(base_api: str, email: str, password: str) -> str:
    r = requests.post(
        f"{base_api}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    tok = str((r.json() or {}).get("access_token") or "")
    if not tok:
        raise RuntimeError("No access_token from /auth/login")
    return tok


def _get_coverage(base_api: str, token: str, refresh: bool = True) -> Dict[str, Any]:
    r = requests.get(
        f"{base_api}/mitre/coverage",
        headers={"Authorization": f"Bearer {token}"},
        params={"refresh": "true" if refresh else "false"},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {"raw": data}


def _pending_s5(coverage: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    techs = coverage.get("techniques") or []
    if not isinstance(techs, list):
        techs = []
    raw_s5 = [t for t in techs if int(t.get("tvr_score") or 0) >= 5]
    pending = [t for t in raw_s5 if not bool(t.get("soar_linked"))]
    return raw_s5, pending


def _respond(base_api: str, token: str, technique_id: str) -> Dict[str, Any]:
    r = requests.post(
        f"{base_api}/soar/techniques/{technique_id}/respond",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {"raw": data}


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger SOAR responses to convert TVR S5 -> TRUE S5 (SOAR-linked).")
    parser.add_argument("--base-api", default=os.environ.get("SERAPH_BASE_API", "http://127.0.0.1:8001/api"))
    parser.add_argument("--email", default=os.environ.get("SERAPH_SWEEP_EMAIL", "sweep@local"))
    parser.add_argument("--password", default=os.environ.get("SERAPH_SWEEP_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--outdir", default=os.environ.get("SERAPH_SWEEP_OUTDIR", "artifacts/live"))
    parser.add_argument("--timestamp", default=_utc_ts())
    parser.add_argument("--limit", type=int, default=int(os.environ.get("SERAPH_S5_PROMOTION_LIMIT", "25")))
    parser.add_argument("--delay-s", type=float, default=float(os.environ.get("SERAPH_S5_PROMOTION_DELAY_S", "0.35")))
    args = parser.parse_args()

    base_api = _strip_trailing_slash(args.base_api)
    outdir = Path(args.outdir) / args.timestamp / "soar-s5-promotions"
    _safe_mkdir(outdir)

    token = _login(base_api, args.email, args.password)
    before = _get_coverage(base_api, token, refresh=True)
    raw_s5, pending = _pending_s5(before)
    _write_json(outdir / "coverage.before.json", before)

    before_true = len([t for t in raw_s5 if bool(t.get("soar_linked"))])
    before_pending = len(pending)

    selected = pending[: max(0, args.limit)]
    _write_json(
        outdir / "plan.json",
        {
            "base_api": base_api,
            "selected_count": len(selected),
            "before": {"raw_s5": len(raw_s5), "true_s5": before_true, "pending_s5": before_pending},
            "selected": [t.get("technique") for t in selected],
        },
    )

    results_dir = outdir / "responses"
    _safe_mkdir(results_dir)
    completed: List[str] = []
    failed: List[Dict[str, str]] = []

    for row in selected:
        tid = str(row.get("technique") or "").strip()
        if not tid:
            continue
        try:
            res = _respond(base_api, token, tid)
            _write_json(results_dir / f"{tid}.json", res)
            completed.append(tid)
        except Exception as exc:
            failed.append({"technique": tid, "error": str(exc)})
            _write_json(results_dir / f"{tid}.error.json", {"technique": tid, "error": str(exc)})
        time.sleep(max(0.0, args.delay_s))

    after = _get_coverage(base_api, token, refresh=True)
    raw_s5_after, pending_after = _pending_s5(after)
    after_true = len([t for t in raw_s5_after if bool(t.get("soar_linked"))])
    _write_json(outdir / "coverage.after.json", after)
    _write_json(
        outdir / "summary.json",
        {
            "completed": completed,
            "failed": failed,
            "counts": {
                "before_raw_s5": len(raw_s5),
                "before_true_s5": before_true,
                "before_pending_s5": before_pending,
                "after_raw_s5": len(raw_s5_after),
                "after_true_s5": after_true,
                "after_pending_s5": len(pending_after),
                "delta_true_s5": after_true - before_true,
            },
        },
    )

    print(str(outdir))
    print(f"TRUE_S5: {before_true} -> {after_true} (delta +{after_true - before_true})")
    print(f"PENDING_S5: {before_pending} -> {len(pending_after)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

