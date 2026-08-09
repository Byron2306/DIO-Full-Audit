import asyncio
import hashlib
import json
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Any, Tuple, List, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
import uvicorn


def now_ms() -> int:
  return int(time.time() * 1000)


def ensure_dir(p: str) -> None:
  os.makedirs(p, exist_ok=True)


def jsonl_append(path: str, obj: Dict[str, Any]) -> None:
  with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")


class TokenBucket:
  def __init__(self, rate_per_sec: float, burst: int):
    self.rate = float(rate_per_sec)
    self.capacity = int(burst)
    self.tokens = float(burst)
    self.last = time.time()

  def take(self, n: float = 1.0) -> bool:
    now = time.time()
    elapsed = now - self.last
    self.last = now
    self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
    if self.tokens >= n:
      self.tokens -= n
      return True
    return False


@dataclass
class RouteDecision:
  route: str
  score: int
  reasons: List[str]


class SelfHealState:
  def __init__(self, circuit_breaker_ms: int):
    self.upstream_healthy = True
    self.cb_open_until_ms = 0
    self.circuit_breaker_ms = circuit_breaker_ms
    self.last_health_status: Optional[int] = None
    self.last_health_check_ms: int = 0

  def circuit_open(self) -> bool:
    return now_ms() < self.cb_open_until_ms

  def trip(self) -> None:
    self.cb_open_until_ms = now_ms() + self.circuit_breaker_ms


class RateLimiter:
  def __init__(self, cfg: Dict[str, Any]):
    rl = cfg["rate_limit"]
    self.per_ip: Dict[str, TokenBucket] = {}
    self.per_ip_path: Dict[str, TokenBucket] = {}
    self.banned_until: Dict[str, float] = {}
    self.per_ip_rps = float(rl["per_ip_rps"])
    self.per_ip_burst = int(rl["per_ip_burst"])
    self.per_ip_path_rps = float(rl["per_ip_path_rps"])
    self.per_ip_path_burst = int(rl["per_ip_path_burst"])

  def _bucket(self, store: Dict[str, TokenBucket], key: str, rps: float, burst: int) -> TokenBucket:
    b = store.get(key)
    if not b:
      b = TokenBucket(rps, burst)
      store[key] = b
    return b

  def check(self, ip: str, path: str) -> Tuple[bool, bool]:
    now = time.time()
    until = self.banned_until.get(ip, 0)
    if now < until:
      return False, True

    ip_ok = self._bucket(self.per_ip, ip, self.per_ip_rps, self.per_ip_burst).take(1.0)
    ipp_ok = self._bucket(self.per_ip_path, f"{ip}|{path}", self.per_ip_path_rps, self.per_ip_path_burst).take(1.0)

    return (ip_ok and ipp_ok), False


class RiskScorer:
  def __init__(self, cfg: Dict[str, Any]):
    self.cfg = cfg
    self.weights = cfg["scoring"]["weights"]
    self.allow = set(cfg["scoring"].get("allowlist_ips", []))
    self.block = set(cfg["scoring"].get("blocklist_ips", []))
    self.trap_prefix = tuple(cfg["routing"]["trap_paths_prefix"])

  def score(self, ip: str, path: str, headers: Dict[str, str], rate_pressure: bool) -> RouteDecision:
    if ip in self.allow:
      return RouteDecision("PASS_THROUGH", 0, ["allowlist_ip"])
    if ip in self.block:
      return RouteDecision("TRAP_SINK", 100, ["blocklist_ip"])

    score = 0
    reasons: List[str] = []

    ua = (headers.get("user-agent") or "").strip()
    if len(ua) < 8:
      score += self.weights.get("bad_user_agent", 0)
      reasons.append("bad_user_agent")

    needed = ["accept", "accept-language"]
    missing = [h for h in needed if not headers.get(h)]
    if missing:
      score += self.weights.get("missing_headers", 0)
      reasons.append("missing_headers:" + ",".join(missing))

    if rate_pressure:
      score += self.weights.get("rate_pressure", 0)
      reasons.append("rate_pressure")

    if path.startswith(self.trap_prefix):
      score += self.weights.get("suspicious_path", 0)
      reasons.append("suspicious_path")

    score = max(0, min(100, score))

    trap_min = int(self.cfg["trap_sink"]["min_score"])
    if self.cfg["trap_sink"]["enabled"] and score >= trap_min:
      return RouteDecision("TRAP_SINK", score, reasons)

    if self.cfg["friction"]["enabled"] and score >= int(self.cfg["friction"]["challenge_on_score_at_least"]):
      return RouteDecision("FRICTION", score, reasons)

    return RouteDecision("PASS_THROUGH", score, reasons)


def load_config(path: str) -> Dict[str, Any]:
  with open(path, "r", encoding="utf-8") as f:
    return json.load(f)


CFG = load_config(os.environ.get("CAS_SHIELD_CONFIG", "./config/cas_shield_config.json"))

ensure_dir(CFG["service"]["log_dir"])
AUDIT_FILE = CFG["service"]["audit_file"]
TEL_FILE = CFG["service"]["telemetry_file"]

up_env = CFG["upstream"].get("cas_base_url_env", "CAS_BASE_URL")
UPSTREAM_BASE = (os.environ.get(up_env) or CFG["upstream"]["cas_base_url"]).rstrip("/")
HEALTH_PATH = CFG["upstream"]["health_path"]
CHECK_INTERVAL = float(CFG["upstream"].get("check_interval_sec", 5))
CB_MS = int(CFG["upstream"].get("circuit_breaker_ms", 15000))

state = SelfHealState(circuit_breaker_ms=CB_MS)
limiter = RateLimiter(CFG)
scorer = RiskScorer(CFG)

timeout = httpx.Timeout(
  connect=float(CFG["upstream"]["connect_timeout_sec"]),
  read=float(CFG["upstream"]["read_timeout_sec"]),
  write=10.0,
  pool=10.0
)
client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

PEBBLES = CFG.get("pebbles", {"enabled": False})
PEBBLES_SALT = os.environ.get(PEBBLES.get("campaign_salt_env", "PEBBLES_SALT"), "")

MYSTIQUE = CFG.get("mystique", {"enabled": False})

counters: Dict[str, int] = defaultdict(int)

campaign_counts: Dict[str, int] = defaultdict(int)
trap_hits: Dict[str, int] = defaultdict(int)

campaign_profiles = defaultdict(lambda: {
  "events": 0,
  "trap": 0,
  "friction": 0,
  "pass": 0,
  "last_seen_ms": 0,
  "friction_multiplier": 1.0,
  "tarpit_multiplier": 1.0,
  "sink_score_override": None
})


def h(s: str) -> str:
  return hashlib.sha256(s.encode("utf-8")).hexdigest()


def fingerprint_id(headers: Dict[str, str]) -> str:
  fields = PEBBLES.get("fingerprint_fields", [])
  base = "|".join([f"{k}:{headers.get(k, '')}" for k in fields])
  return h(base)[:16]


def campaign_id(ip: str, fp: str, path: str) -> str:
  window_min = int(PEBBLES.get("campaign_window_minutes", 120))
  bucket = int(time.time() // (window_min * 60))
  salt = PEBBLES_SALT or "UNSET_SALT"
  return h(f"{salt}|{bucket}|{ip}|{fp}|{path[:24]}")[:16]


def pebble_trace_value(trace_id: str, camp_id: str) -> str:
  return f"{camp_id}.{trace_id[:8]}"


def audit(event: Dict[str, Any]) -> None:
  jsonl_append(AUDIT_FILE, event)


def telem(event: Dict[str, Any]) -> None:
  jsonl_append(TEL_FILE, event)


def client_ip(req: Request) -> str:
  xff = req.headers.get("x-forwarded-for")
  if xff:
    return xff.split(",")[0].strip()
  return req.client.host if req.client else "unknown"


def friction_delay_ms(score: int, camp_id: str) -> int:
  base = int(CFG["friction"]["base_delay_ms"])
  mx = int(CFG["friction"]["max_delay_ms"])
  d = base + int((score / 100) * (mx - base))
  mult = 1.0
  if MYSTIQUE.get("enabled", False) and camp_id:
    mult = campaign_profiles[camp_id]["friction_multiplier"]
  d = int(d * mult)
  max_mult = float(MYSTIQUE.get("max_friction_multiplier", 2.5))
  return max(base, min(int(mx * max_mult), d))


def tarpit_delay_ms(camp_id: str) -> int:
  base = int(CFG["trap_sink"]["tarpit_delay_ms"])
  mult = 1.0
  if MYSTIQUE.get("enabled", False) and camp_id:
    mult = campaign_profiles[camp_id]["tarpit_multiplier"]
  d = int(base * mult)
  max_mult = float(MYSTIQUE.get("max_tarpit_multiplier", 2.0))
  return max(base, min(int(base * max_mult), d))


def mystique_update(camp_id: str) -> None:
  if not MYSTIQUE.get("enabled", False) or not camp_id:
    return
  prof = campaign_profiles[camp_id]
  n = int(MYSTIQUE.get("adapt_every_n_events", 25))
  promote = int(MYSTIQUE.get("campaign_promote_threshold", 30))
  if prof["events"] < promote:
    return
  if prof["events"] % n != 0:
    return

  trap_ratio = prof["trap"] / max(1, prof["events"])
  if trap_ratio >= 0.4:
    prof["friction_multiplier"] = min(float(MYSTIQUE.get("max_friction_multiplier", 2.5)), prof["friction_multiplier"] + 0.25)
    prof["tarpit_multiplier"] = min(float(MYSTIQUE.get("max_tarpit_multiplier", 2.0)), prof["tarpit_multiplier"] + 0.10)
    floor = int(MYSTIQUE.get("min_sink_score_floor", 60))
    current = prof["sink_score_override"]
    if current is None:
      current = int(CFG["trap_sink"]["min_score"])
    prof["sink_score_override"] = max(floor, min(90, current - 5))


def maybe_stonewall(ip: str, camp_id: str, route: str) -> None:
  if not PEBBLES.get("enabled", False) or not camp_id:
    return
  st = PEBBLES.get("stonewall", {})
  if not st.get("enable_auto_ban", True):
    return

  campaign_counts[camp_id] += 1
  if route == "TRAP_SINK":
    trap_hits[camp_id] += 1

  repeat_threshold = int(st.get("repeat_threshold", 20))
  ban_first = int(st.get("ban_seconds_first", 1800))
  ban_repeat = int(st.get("ban_seconds_repeat", 21600))
  block_after_trap = int(st.get("trap_hits_to_blocklist", 50))

  if campaign_counts[camp_id] == repeat_threshold:
    limiter.banned_until[ip] = time.time() + ban_first

  if campaign_counts[camp_id] > repeat_threshold and (campaign_counts[camp_id] % repeat_threshold == 0):
    limiter.banned_until[ip] = time.time() + ban_repeat

  if trap_hits[camp_id] >= block_after_trap:
    scorer.block.add(ip)


async def forward_to_cas(req: Request) -> Response:
  # Only PASS_THROUGH or approved FRICTION calls this.
  url = UPSTREAM_BASE + req.url.path
  if req.url.query:
    url = url + "?" + req.url.query

  headers = dict(req.headers)
  headers.pop("host", None)

  body = await req.body()

  r = await client.request(
    method=req.method,
    url=url,
    headers=headers,
    content=body
  )

  out_headers = dict(r.headers)
  out_headers.pop("transfer-encoding", None)
  return Response(content=r.content, status_code=r.status_code, headers=out_headers)


app = FastAPI()


async def upstream_health_check_loop():
  while True:
    state.last_health_check_ms = now_ms()
    try:
      if state.circuit_open():
        await asyncio.sleep(1.0)
        continue
      r = await client.get(UPSTREAM_BASE + HEALTH_PATH)
      state.last_health_status = r.status_code
      state.upstream_healthy = (200 <= r.status_code < 500)
    except Exception:
      state.last_health_status = None
      state.upstream_healthy = False
      state.trip()
    await asyncio.sleep(CHECK_INTERVAL)


@app.on_event("startup")
async def on_startup():
  asyncio.create_task(upstream_health_check_loop())


@app.get("/__shield/status")
async def status():
  return JSONResponse({
    "service": CFG["service"]["name"],
    "upstream_base": UPSTREAM_BASE,
    "upstream_healthy": state.upstream_healthy,
    "circuit_open": state.circuit_open(),
    "last_health_status": state.last_health_status,
    "last_health_check_ms": state.last_health_check_ms,
    "counters": dict(counters),
    "blocklist_size": len(scorer.block),
    "banlist_size": len(limiter.banned_until),
    "pebbles_salt_set": bool(PEBBLES_SALT)
  })


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def shield(full_path: str, req: Request):
  rid = str(uuid.uuid4())
  ip = client_ip(req)
  path = "/" + full_path
  hdrs = {k.lower(): v for k, v in req.headers.items()}

  fp = fingerprint_id(hdrs) if PEBBLES.get("enabled", False) else ""
  camp = campaign_id(ip, fp, path) if PEBBLES.get("enabled", False) else ""
  trace_id = rid

  # Canary endpoints: safe telemetry, never forward.
  if PEBBLES.get("enabled", False) and PEBBLES.get("canary_endpoints", {}).get("enabled", False):
    canary_paths = set(PEBBLES.get("canary_endpoints", {}).get("paths", []))
    if path in canary_paths:
      counters["canary_hits"] += 1
      event = {
        "ts_ms": now_ms(),
        "request_id": rid,
        "trace_id": trace_id,
        "campaign_id": camp,
        "fingerprint_id": fp,
        "ip": ip,
        "path": path,
        "route": "TRAP_SINK",
        "score": 95,
        "reasons": ["canary_hit"],
        "action": "sink",
        "status": 204
      }
      audit(event)
      telem(event)
      maybe_stonewall(ip, camp, "TRAP_SINK")

      prof = campaign_profiles[camp]
      prof["events"] += 1
      prof["trap"] += 1
      prof["last_seen_ms"] = now_ms()
      mystique_update(camp)

      resp = Response(status_code=204)
      if "TRAP_SINK" in PEBBLES.get("echo_on_routes", []):
        resp.headers[PEBBLES.get("echo_header", "X-Pebble-Trace")] = pebble_trace_value(trace_id, camp)
      return resp

  ok, banned = limiter.check(ip, path)
  rate_pressure = (not ok)

  if banned:
    counters["banned_denies"] += 1
    event = {
      "ts_ms": now_ms(),
      "request_id": rid,
      "trace_id": trace_id,
      "campaign_id": camp,
      "fingerprint_id": fp,
      "ip": ip,
      "path": path,
      "route": "TRAP_SINK",
      "score": 100,
      "reasons": ["ip_banned"],
      "action": "deny",
      "status": 403
    }
    audit(event)
    resp = PlainTextResponse("Forbidden", status_code=403)
    if "TRAP_SINK" in PEBBLES.get("echo_on_routes", []):
      resp.headers[PEBBLES.get("echo_header", "X-Pebble-Trace")] = pebble_trace_value(trace_id, camp)
    return resp

  decision = scorer.score(ip, path, hdrs, rate_pressure)

  # Mystique sink override (bounded)
  if MYSTIQUE.get("enabled", False) and camp:
    prof = campaign_profiles[camp]
    override = prof.get("sink_score_override")
    if override is not None and decision.route != "TRAP_SINK" and decision.score >= int(override):
      decision = RouteDecision("TRAP_SINK", decision.score, decision.reasons + ["mystique_sink_override"])

  # Upstream unhealthy: 503 with evidence.
  if not state.upstream_healthy or state.circuit_open():
    counters["upstream_503"] += 1
    event = {
      "ts_ms": now_ms(),
      "request_id": rid,
      "trace_id": trace_id,
      "campaign_id": camp,
      "fingerprint_id": fp,
      "ip": ip,
      "path": path,
      "route": "FRICTION",
      "score": 90,
      "reasons": ["upstream_unhealthy_or_circuit_open"],
      "action": "service_unavailable",
      "status": 503
    }
    audit(event)
    resp = PlainTextResponse("Service Unavailable", status_code=503)
    if "FRICTION" in PEBBLES.get("echo_on_routes", []):
      resp.headers[PEBBLES.get("echo_header", "X-Pebble-Trace")] = pebble_trace_value(trace_id, camp)
    return resp

  if decision.route == "TRAP_SINK":
    counters["trap_sink"] += 1
    await asyncio.sleep(tarpit_delay_ms(camp) / 1000.0)

    event = {
      "ts_ms": now_ms(),
      "request_id": rid,
      "trace_id": trace_id,
      "campaign_id": camp,
      "fingerprint_id": fp,
      "ip": ip,
      "path": path,
      "route": "TRAP_SINK",
      "score": decision.score,
      "reasons": decision.reasons,
      "action": "sink",
      "status": 403
    }
    audit(event)
    telem(event)
    maybe_stonewall(ip, camp, "TRAP_SINK")

    if camp:
      prof = campaign_profiles[camp]
      prof["events"] += 1
      prof["trap"] += 1
      prof["last_seen_ms"] = now_ms()
      mystique_update(camp)

    resp = PlainTextResponse("Forbidden", status_code=403)
    if "TRAP_SINK" in PEBBLES.get("echo_on_routes", []):
      resp.headers[PEBBLES.get("echo_header", "X-Pebble-Trace")] = pebble_trace_value(trace_id, camp)
    return resp

  if decision.route == "FRICTION":
    counters["friction"] += 1
    dms = friction_delay_ms(decision.score, camp)
    await asyncio.sleep(dms / 1000.0)

    event = {
      "ts_ms": now_ms(),
      "request_id": rid,
      "trace_id": trace_id,
      "campaign_id": camp,
      "fingerprint_id": fp,
      "ip": ip,
      "path": path,
      "route": "FRICTION",
      "score": decision.score,
      "reasons": decision.reasons,
      "action": "delay_then_forward",
      "delay_ms": dms
    }
    audit(event)

    if camp:
      prof = campaign_profiles[camp]
      prof["events"] += 1
      prof["friction"] += 1
      prof["last_seen_ms"] = now_ms()
      mystique_update(camp)

    try:
      resp = await forward_to_cas(req)
      if "FRICTION" in PEBBLES.get("echo_on_routes", []):
        resp.headers[PEBBLES.get("echo_header", "X-Pebble-Trace")] = pebble_trace_value(trace_id, camp)
      maybe_stonewall(ip, camp, "FRICTION")
      return resp
    except Exception as e:
      state.trip()
      counters["forward_503"] += 1
      err = {
        "ts_ms": now_ms(),
        "request_id": rid,
        "trace_id": trace_id,
        "campaign_id": camp,
        "fingerprint_id": fp,
        "ip": ip,
        "path": path,
        "route": "FRICTION",
        "score": decision.score,
        "reasons": decision.reasons + ["forward_error"],
        "error": str(e),
        "status": 503
      }
      audit(err)
      return PlainTextResponse("Service Unavailable", status_code=503)

  counters["pass_through"] += 1
  event = {
    "ts_ms": now_ms(),
    "request_id": rid,
    "trace_id": trace_id,
    "campaign_id": camp,
    "fingerprint_id": fp,
    "ip": ip,
    "path": path,
    "route": "PASS_THROUGH",
    "score": decision.score,
    "reasons": decision.reasons,
    "action": "forward"
  }
  audit(event)

  if camp:
    prof = campaign_profiles[camp]
    prof["events"] += 1
    prof["pass"] += 1
    prof["last_seen_ms"] = now_ms()
    mystique_update(camp)

  try:
    return await forward_to_cas(req)
  except Exception as e:
    state.trip()
    counters["forward_503"] += 1
    err = {
      "ts_ms": now_ms(),
      "request_id": rid,
      "trace_id": trace_id,
      "campaign_id": camp,
      "fingerprint_id": fp,
      "ip": ip,
      "path": path,
      "route": "PASS_THROUGH",
      "score": decision.score,
      "reasons": decision.reasons + ["forward_error"],
      "error": str(e),
      "status": 503
    }
    audit(err)
    return PlainTextResponse("Service Unavailable", status_code=503)


if __name__ == "__main__":
  uvicorn.run(
    app,
    host=CFG["service"]["listen_host"],
    port=int(CFG["service"]["listen_port"]),
    log_level="info"
  )
