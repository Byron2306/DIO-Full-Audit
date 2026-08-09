#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    _safe_mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    _safe_mkdir(path.parent)
    path.write_text(text, encoding="utf-8")


def _strip_trailing_slash(value: str) -> str:
    while value.endswith("/"):
        value = value[:-1]
    return value


@dataclass
class AuthContext:
    base_api: str
    token: str


class SeraphClient:
    def __init__(self, base_api: str, token: Optional[str] = None, timeout_s: int = 30):
        self.base_api = _strip_trailing_slash(base_api)
        self.session = requests.Session()
        self.timeout_s = timeout_s
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_api}{path}"

    def get_json(self, path: str, *, params: Optional[Dict[str, Any]] = None, timeout_s: Optional[int] = None) -> Any:
        resp = self.session.get(self._url(path), params=params, timeout=timeout_s or self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    def post_json(self, path: str, *, payload: Optional[Dict[str, Any]] = None, timeout_s: Optional[int] = None) -> Any:
        resp = self.session.post(self._url(path), json=payload or {}, timeout=timeout_s or self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    def get_bytes(self, path: str, timeout_s: Optional[int] = None) -> bytes:
        resp = self.session.get(self._url(path), timeout=timeout_s or self.timeout_s)
        resp.raise_for_status()
        return resp.content


def ensure_auth(*, base_api: str, email: str, password: str, name: str, token: str = "") -> AuthContext:
    if token:
        return AuthContext(base_api=base_api, token=token)

    client = SeraphClient(base_api, token=None)
    try:
        client.post_json("/auth/register", payload={"email": email, "password": password, "name": name})
    except requests.HTTPError as exc:
        # If already registered, login is enough.
        if exc.response is None or exc.response.status_code != 400:
            raise
    login = client.post_json("/auth/login", payload={"email": email, "password": password})
    access_token = str((login or {}).get("access_token") or "")
    if not access_token:
        raise RuntimeError("Login did not return access_token")
    return AuthContext(base_api=base_api, token=access_token)


def poll_integration_job(
    client: SeraphClient,
    job_id: str,
    *,
    poll_s: float = 1.0,
    timeout_s: float = 300.0,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        job = client.get_json(f"/integrations/jobs/{job_id}")
        if isinstance(job, dict):
            last = job
        status = str((job or {}).get("status") or "").lower()
        if status in {"completed", "failed"}:
            return job
        time.sleep(poll_s)
    return last


def download_integration_artifacts(
    client: SeraphClient,
    job_id: str,
    dest_dir: Path,
) -> List[Path]:
    saved: List[Path] = []
    try:
        listing = client.get_json(f"/integrations/artifacts/{job_id}")
    except requests.HTTPError:
        return saved

    artifacts = (listing or {}).get("artifacts") if isinstance(listing, dict) else None
    if not isinstance(artifacts, list):
        return saved

    for name in [str(a) for a in artifacts if str(a).strip()]:
        try:
            content = client.get_bytes(f"/integrations/artifact/{job_id}/{name}")
        except requests.HTTPError:
            continue
        outpath = dest_dir / name
        _safe_mkdir(outpath.parent)
        outpath.write_bytes(content)
        saved.append(outpath)
    return saved


def run_integration_tool(
    client: SeraphClient,
    *,
    tool: str,
    params: Dict[str, Any],
    outdir: Path,
    poll_timeout_s: float = 300.0,
) -> Tuple[str, Dict[str, Any], List[Path]]:
    launch = client.post_json(
        "/integrations/runtime/run",
        payload={"tool": tool, "params": params, "runtime_target": "server"},
    )
    job_id = str((launch or {}).get("job_id") or "")
    if not job_id:
        raise RuntimeError(f"Integration launch for {tool} did not return job_id: {launch}")

    job = poll_integration_job(client, job_id, timeout_s=poll_timeout_s)
    tool_dir = outdir / "integrations" / tool / job_id
    _write_json(tool_dir / "job.json", job)
    saved = download_integration_artifacts(client, job_id, tool_dir / "artifacts")

    if tool == "osquery":
        artifact_dir = tool_dir / "artifacts"
        for saved_path in list(saved):
            if saved_path.name == "osqueryd.results.log":
                try:
                    _write_json(tool_dir / "osquery_artifact_index.json", {"job_id": job_id, "artifact": str(saved_path.relative_to(tool_dir))})
                except Exception:
                    pass
        if not saved:
            try:
                result = (job or {}).get("result") or {}
                osquery_result = (result.get("result") or {}).get("osquery") or {}
                results_log = osquery_result.get("results_log")
                if results_log:
                    _write_text(tool_dir / "results_log.txt", str(results_log))
            except Exception:
                pass

    return job_id, job, saved


def run_atomic_job(client: SeraphClient, job_id: str, *, dry_run: bool, outdir: Path) -> Dict[str, Any]:
    # Atomic runs can legitimately take many minutes (sandbox containers, downloads, etc.).
    result = client.post_json(
        "/atomic-validation/run",
        payload={"job_id": job_id, "dry_run": dry_run},
        timeout_s=1800,
    )
    _write_json(outdir / "atomic-validation" / "runs" / f"{job_id}.json", result)
    return result if isinstance(result, dict) else {"result": result}


def _default_integration_plan(amass_domain: str, yara_target_path: str) -> List[Tuple[str, Dict[str, Any], float]]:
    return [
        ("arkime", {"action": "status"}, 60.0),
        ("bloodhound", {"action": "status"}, 60.0),
        ("velociraptor", {}, 180.0),
        ("trivy", {"action": "status"}, 120.0),
        ("falco", {"action": "status"}, 60.0),
        ("falco", {"action": "alerts", "limit": 50}, 60.0),
        ("osquery", {"action": "status"}, 60.0),
        ("osquery", {"action": "stats"}, 60.0),
        ("osquery", {"action": "results", "limit": 50}, 60.0),
        ("zeek", {"action": "status"}, 60.0),
        ("zeek", {"action": "stats"}, 60.0),
        ("zeek", {"action": "log", "log_type": "conn", "limit": 120}, 60.0),
        ("suricata", {"action": "status"}, 60.0),
        ("suricata", {"action": "alerts", "limit": 300, "return_limit": 60}, 60.0),
        ("yara", {"action": "status"}, 60.0),
        ("yara", {"action": "scan", "rules_path": "/app/yara_rules", "target_path": yara_target_path, "timeout": 120}, 240.0),
        # Optional: can be noisy; included but can be disabled via CLI.
        # Note: runtime launcher treats empty action as a status probe for amass/purplesharp.
        ("amass", {"action": "run", "domain": amass_domain}, 600.0),
        # PurpleSharp typically requires a Windows toolchain; we run it as a best-effort probe to produce an artifact.
        ("purplesharp", {"action": "run", "target": None, "options": {"mode": "local"}}, 120.0),
    ]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Atomic Validation + integration telemetry probes and save evidence under ./artifacts.",
    )
    parser.add_argument("--base-api", default=os.environ.get("SERAPH_BASE_API", "http://127.0.0.1:8001/api"))
    parser.add_argument("--token", default=os.environ.get("SERAPH_TOKEN", ""))
    parser.add_argument("--email", default=os.environ.get("SERAPH_SWEEP_EMAIL", "sweep@local"))
    parser.add_argument("--password", default=os.environ.get("SERAPH_SWEEP_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--name", default=os.environ.get("SERAPH_SWEEP_NAME", "Telemetry Sweep"))
    parser.add_argument("--outdir", default=os.environ.get("SERAPH_SWEEP_OUTDIR", "artifacts/live"))
    parser.add_argument("--timestamp", default=_utc_ts())
    parser.add_argument("--dry-run", action="store_true", help="Do not execute atomics; still collects telemetry probes.")
    parser.add_argument("--skip-atomics", action="store_true")
    parser.add_argument("--skip-integrations", action="store_true")
    parser.add_argument("--skip-amass", action="store_true")
    parser.add_argument("--skip-purplesharp", action="store_true")
    parser.add_argument("--amass-domain", default=os.environ.get("SERAPH_AMASS_DOMAIN", "example.com"))
    parser.add_argument(
        "--yara-target-path",
        default=os.environ.get("SERAPH_YARA_TARGET_PATH", "/tmp"),
        help="Container path for Yara scan (safe default: /tmp).",
    )
    args = parser.parse_args(argv)

    outdir = Path(args.outdir) / args.timestamp
    _safe_mkdir(outdir)
    _write_json(
        outdir / "meta.json",
        {
            "timestamp": args.timestamp,
            "base_api": args.base_api,
            "dry_run": bool(args.dry_run),
            "skip_atomics": bool(args.skip_atomics),
            "skip_integrations": bool(args.skip_integrations),
        },
    )

    auth = ensure_auth(
        base_api=args.base_api,
        email=args.email,
        password=args.password,
        name=args.name,
        token=args.token,
    )
    client = SeraphClient(auth.base_api, token=auth.token, timeout_s=60)

    # Snapshot current status.
    try:
        _write_json(outdir / "auth" / "me.json", client.get_json("/auth/me"))
    except Exception as exc:
        _write_text(outdir / "auth" / "me.error.txt", str(exc))

    if not args.skip_atomics:
        try:
            jobs = client.get_json("/atomic-validation/jobs")
            _write_json(outdir / "atomic-validation" / "jobs.json", jobs)
            job_rows = (jobs or {}).get("jobs") if isinstance(jobs, dict) else []
            atomic_job_ids = [str(j.get("job_id")) for j in job_rows if isinstance(j, dict) and str(j.get("job_id") or "").strip()]
        except Exception as exc:
            _write_text(outdir / "atomic-validation" / "jobs.error.txt", str(exc))
            atomic_job_ids = []

        for job_id in atomic_job_ids:
            try:
                run_atomic_job(client, job_id, dry_run=bool(args.dry_run), outdir=outdir)
            except Exception as exc:
                _write_text(outdir / "atomic-validation" / "runs" / f"{job_id}.error.txt", str(exc))

        try:
            _write_json(outdir / "atomic-validation" / "runs.json", client.get_json("/atomic-validation/runs", params={"limit": 100}))
            _write_json(outdir / "atomic-validation" / "status.json", client.get_json("/atomic-validation/status"))
        except Exception as exc:
            _write_text(outdir / "atomic-validation" / "status.error.txt", str(exc))

    if not args.skip_integrations:
        plan = _default_integration_plan(args.amass_domain, args.yara_target_path)
        if args.skip_amass:
            plan = [item for item in plan if item[0] != "amass"]
        if args.skip_purplesharp:
            plan = [item for item in plan if item[0] != "purplesharp"]

        _write_json(outdir / "integrations" / "plan.json", [{"tool": t, "params": p, "timeout_s": to} for t, p, to in plan])

        for tool, params, timeout_s in plan:
            try:
                run_integration_tool(client, tool=tool, params=params, outdir=outdir, poll_timeout_s=timeout_s)
            except Exception as exc:
                tool_dir = outdir / "integrations" / tool / "errors"
                _write_text(tool_dir / f"{_utc_ts()}.txt", f"{params}\n\n{exc}")

    print(str(outdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
