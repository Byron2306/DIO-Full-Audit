import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class OsqueryFleetIntegration:
    def __init__(self):
        self.fleet_base_url = os.environ.get("FLEET_BASE_URL", "").strip().rstrip("/")
        self.fleet_api_token = os.environ.get("FLEET_API_TOKEN", "").strip()
        self.results_log = Path(os.environ.get("OSQUERY_RESULTS_LOG", "/var/log/osquery/osqueryd.results.log"))
        demo_mode_raw = os.environ.get("OSQUERY_DEMO_MODE")
        if demo_mode_raw is None:
            self.demo_mode = not (self.fleet_api_token or self.results_log.exists())
        else:
            self.demo_mode = demo_mode_raw.strip().lower() in {"1", "true", "yes", "on"}
        self.generated_catalog_path = Path(
            os.environ.get(
                "OSQUERY_BUILTIN_QUERY_CATALOG",
                str(Path(__file__).resolve().parent / "data" / "generated_osquery_builtin_queries.json"),
            )
        )

        self.builtin_queries = [
            {
                "name": "suspicious_startup_items",
                "description": "Detect suspicious startup persistence artifacts",
                "sql": "SELECT * FROM startup_items LIMIT 200;",
                "attack_techniques": ["T1547", "T1547.001"],
            },
            {
                "name": "encoded_powershell",
                "description": "Find encoded PowerShell invocations in process arguments",
                "sql": "SELECT pid, name, cmdline FROM processes WHERE lower(name)='powershell.exe' AND (cmdline LIKE '% -enc %' OR cmdline LIKE '% -encodedcommand %') LIMIT 200;",
                "attack_techniques": ["T1059.001", "T1027"],
            },
            {
                "name": "credential_files",
                "description": "Find likely plaintext credential files",
                "sql": "SELECT path, filename FROM file WHERE path LIKE '%password%' OR path LIKE '%credential%' LIMIT 200;",
                "attack_techniques": ["T1552.001"],
            },
            {
                "name": "list_usb_devices",
                "description": "Enumerate removable media devices",
                "sql": "SELECT * FROM usb_devices LIMIT 200;",
                "attack_techniques": ["T1091", "T1200"],
            },
            {
                "name": "open_network_listeners",
                "description": "Identify local listening sockets for suspicious exposure",
                "sql": "SELECT pid, address, port, protocol, family FROM listening_ports LIMIT 500;",
                "attack_techniques": ["T1046", "T1018"],
            },
        ]
        self.builtin_queries.extend(self._load_generated_builtin_queries())

    def _load_generated_builtin_queries(self) -> List[Dict]:
        if not self.generated_catalog_path.exists():
            return []

        try:
            payload = json.loads(self.generated_catalog_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read generated osquery catalog from %s", self.generated_catalog_path)
            return []

        if not isinstance(payload, list):
            return []

        queries: List[Dict] = []
        seen_names = {query["name"] for query in self.builtin_queries}
        for row in payload:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            sql = str(row.get("sql") or "").strip()
            if not name or not sql or name in seen_names:
                continue
            seen_names.add(name)
            queries.append(
                {
                    "name": name,
                    "description": str(row.get("description") or "").strip(),
                    "sql": sql,
                    "attack_techniques": [
                        str(technique).strip()
                        for technique in (row.get("attack_techniques") or [])
                        if str(technique).strip()
                    ],
                }
            )
        return queries

    def _fleet_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.fleet_api_token:
            headers["Authorization"] = f"Bearer {self.fleet_api_token}"
        return headers

    def _fleet_get(self, path: str, params: Optional[Dict] = None) -> Tuple[Dict, str]:
        if not self.fleet_base_url or not self.fleet_api_token:
            # [SIMULATION FALLBACK] Keep dashboard operational when Fleet credentials are absent.
            if self.demo_mode:
                logger.info("FLEET_OSQUERY: [DEMO MODE] Providing simulated response for path: %s", path)
                if "health" in path:
                    return {"status": "ok", "mode": "demo"}, ""
                if "hosts" in path:
                    return {
                        "hosts": [
                            {"id": 1, "hostname": "WS-ADMIN-01", "status": "online", "os_version": "Debian 12", "last_seen": datetime.now(timezone.utc).isoformat()},
                            {"id": 2, "hostname": "SRV-DB-01", "status": "online", "os_version": "Ubuntu 22.04", "last_seen": datetime.now(timezone.utc).isoformat()},
                            {"id": 3, "hostname": "WS-DEV-05", "status": "offline", "os_version": "Windows 11", "last_seen": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}
                        ]
                    }, ""
                if "queries" in path:
                    return {
                        "queries": [
                            {
                                "name": "fleet_demo_suspicious_processes",
                                "description": "Demo Fleet query",
                                "query": "SELECT pid, name, cmdline FROM processes LIMIT 25;"
                            }
                        ]
                    }, ""
                return {}, ""
            
            if not self.fleet_base_url:
                return {}, "Fleet URL not configured. Please set FLEET_BASE_URL in your .env file."
            return {}, "Fleet API token not configured. Please set FLEET_API_TOKEN in your .env file."

        try:
            url = f"{self.fleet_base_url}{path}"
            resp = requests.get(url, headers=self._fleet_headers(), params=params or {}, timeout=8)
            if resp.status_code >= 400:
                return {}, f"Fleet API error {resp.status_code}: {resp.text[:200]}"
            return resp.json(), ""
        except Exception as exc:
            return {}, str(exc)

    def _fleet_post(self, path: str, payload: Dict) -> Tuple[Dict, str]:
        if not self.fleet_base_url:
            return {}, "Fleet URL not configured. Please set FLEET_BASE_URL in your .env file."
        if not self.fleet_api_token:
            return {}, "Fleet API token not configured. Please set FLEET_API_TOKEN in your .env file."

        try:
            url = f"{self.fleet_base_url}{path}"
            resp = requests.post(url, headers=self._fleet_headers(), json=payload, timeout=12)
            if resp.status_code >= 400:
                return {}, f"Fleet API error {resp.status_code}: {resp.text[:240]}"
            return resp.json(), ""
        except Exception as exc:
            return {}, str(exc)

    def _parse_results_log(self, limit: int = 100) -> List[Dict]:
        if not self.results_log.exists():
            return []

        rows: List[Dict] = []
        try:
            with open(self.results_log, "r", encoding="utf-8", errors="ignore") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return []

        return list(reversed(rows))[:limit]

    def ingest_results(self, records: List[Dict], *, source: str = "api") -> Dict[str, str | int]:
        """Append osquery JSON records to the configured results log.

        This enables external hosts (e.g., a Windows laptop) to push osquery
        telemetry into the Seraph backend without standing up Fleet.
        """
        if not isinstance(records, list):
            return {"ingested": 0, "path": str(self.results_log)}

        safe_records = [r for r in records if isinstance(r, dict)]
        if not safe_records:
            return {"ingested": 0, "path": str(self.results_log)}

        try:
            self.results_log.parent.mkdir(parents=True, exist_ok=True)
            ingested = 0
            now = datetime.now(timezone.utc).isoformat()
            with open(self.results_log, "a", encoding="utf-8") as handle:
                for row in safe_records[:2000]:
                    payload = dict(row)
                    payload.setdefault("ingested_at", now)
                    payload.setdefault("ingest_source", source)
                    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    ingested += 1
            return {"ingested": ingested, "path": str(self.results_log)}
        except Exception as exc:
            logger.warning("Failed to ingest osquery results: %s", exc)
            return {"ingested": 0, "path": str(self.results_log)}

    def _hosts_from_results_log(self, limit: int = 50) -> List[Dict]:
        hosts: Dict[str, Dict] = {}
        for record in self._parse_results_log(limit=2000):
            host_identifier = record.get("hostIdentifier") or record.get("host_identifier")
            if not host_identifier:
                continue
            existing = hosts.get(host_identifier)
            seen_at = record.get("calendarTime") or record.get("timestamp") or datetime.now(timezone.utc).isoformat()
            candidate = {
                "id": host_identifier,
                "hostname": host_identifier,
                "platform": record.get("platform") or "local-osquery",
                "os_version": record.get("os_version") or record.get("platform") or "unknown",
                "last_seen": seen_at,
                "status": "online",
            }
            if existing is None or str(candidate["last_seen"]) > str(existing.get("last_seen")):
                hosts[host_identifier] = candidate
        return list(hosts.values())[:limit]

    def get_status(self) -> Dict:
        fleet_reachable = self.demo_mode
        fleet_error = ""

        if self.fleet_base_url and self.fleet_api_token:
            data, err = self._fleet_get("/api/latest/fleet/health")
            fleet_reachable = self.demo_mode or (not err and isinstance(data, dict))
            fleet_error = err

        configured = bool(self.fleet_base_url and self.fleet_api_token) or self.demo_mode
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "fleet": {
                "configured": configured,
                "base_url": self.fleet_base_url or None,
                "reachable": fleet_reachable,
                "error": fleet_error,
            },
            "environment": {
                "expected": ["FLEET_BASE_URL", "FLEET_API_TOKEN", "OSQUERY_RESULTS_LOG"],
                "FLEET_BASE_URL_set": bool(self.fleet_base_url),
                "FLEET_API_TOKEN_set": bool(self.fleet_api_token),
                "OSQUERY_RESULTS_LOG": str(self.results_log),
                "OSQUERY_DEMO_MODE": self.demo_mode,
            },
            "osquery": {
                "results_log": str(self.results_log),
                "results_log_exists": self.results_log.exists(),
                "builtin_query_count": len(self.builtin_queries),
            },
        }

    def get_stats(self) -> Dict:
        results = self._parse_results_log(limit=1500)
        host_ids = set()
        query_names: Dict[str, int] = {}

        for rec in results:
            host_identifier = rec.get("hostIdentifier") or rec.get("host_identifier")
            if host_identifier:
                host_ids.add(host_identifier)

            qn = rec.get("name") or rec.get("query_name") or "unnamed_query"
            query_names[qn] = query_names.get(qn, 0) + 1

        top_queries = sorted(query_names.items(), key=lambda kv: kv[1], reverse=True)[:10]

        return {
            "result_events": len(results),
            "unique_hosts": len(host_ids),
            "top_queries": [{"name": n, "count": c} for n, c in top_queries],
        }

    def get_results(self, limit: int = 100) -> Dict:
        records = self._parse_results_log(limit=limit)
        return {
            "count": len(records),
            "records": records,
        }

    def list_queries(self, limit: int = 50, query: str = "") -> Dict:
        lowered = (query or "").strip().lower()
        local = self.builtin_queries
        if lowered:
            local = [
                q for q in local
                if lowered in q["name"].lower()
                or lowered in q["description"].lower()
                or lowered in q["sql"].lower()
                or any(lowered in t.lower() for t in q.get("attack_techniques", []))
            ]

        fleet_queries = []
        fleet_error = ""

        if self.fleet_base_url and self.fleet_api_token:
            data, err = self._fleet_get("/api/latest/fleet/queries", params={"per_page": min(max(limit, 1), 100)})
            fleet_error = err
            if not err and isinstance(data, dict):
                rows = data.get("queries") or data.get("results") or []
                for row in rows:
                    fleet_queries.append(
                        {
                            "name": row.get("name") or row.get("query_name") or "fleet_query",
                            "description": row.get("description") or "",
                            "sql": row.get("query") or "",
                            "attack_techniques": row.get("attack_techniques") or [],
                            "source": "fleet",
                        }
                    )

        all_queries = [{**q, "source": "builtin"} for q in local] + fleet_queries

        return {
            "count": len(all_queries[:limit]),
            "queries": all_queries[:limit],
            "fleet_error": fleet_error,
        }

    def list_hosts(self, limit: int = 50) -> Dict:
        data, err = self._fleet_get("/api/latest/fleet/hosts", params={"per_page": min(max(limit, 1), 100)})
        if err:
            fallback_hosts = self._hosts_from_results_log(limit=limit)
            return {
                "count": len(fallback_hosts),
                "hosts": fallback_hosts,
                "fleet_error": err,
            }

        rows = data.get("hosts") or data.get("results") or []
        hosts = []
        for row in rows[:limit]:
            hosts.append(
                {
                    "id": row.get("id"),
                    "hostname": row.get("hostname"),
                    "platform": row.get("platform"),
                    "os_version": row.get("os_version"),
                    "last_seen": row.get("seen_time") or row.get("last_enrolled_at") or row.get("updated_at"),
                    "status": row.get("status") or row.get("distributed_interval") or "unknown",
                }
            )

        return {
            "count": len(hosts),
            "hosts": hosts,
            "fleet_error": "",
        }

    def run_live_query(self, sql: str, selected: Optional[Dict] = None) -> Dict:
        sql = (sql or "").strip()
        if not sql:
            return {"ok": False, "message": "SQL query is required"}

        payload = {
            "query": sql,
            "selected": selected or {},
        }

        data, err = self._fleet_post("/api/latest/fleet/queries/run", payload)
        if err:
            return {
                "ok": False,
                "message": err,
                "response": {},
            }

        return {
            "ok": True,
            "message": "Query dispatched to Fleet",
            "response": data,
        }


osquery_fleet = OsqueryFleetIntegration()
