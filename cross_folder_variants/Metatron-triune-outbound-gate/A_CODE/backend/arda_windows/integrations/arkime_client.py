"""
ArkimeElasticsearchClient
==========================
Thin wrapper around Arkime's Elasticsearch session store using the
`requests` library directly (avoids elasticsearch-py 9.x / ES 8.x
product-check incompatibility).

Arkime v5 schema highlights used in this client
------------------------------------------------
  firstPacket / lastPacket   millisecond epoch timestamps
  source.ip / source.port    originator side
  destination.ip / destination.port  responder side
  network.bytes / network.packets    combined flow totals
  ipProtocol                 6=TCP, 17=UDP, 1=ICMP
  tcpflags.*                 syn, syn-ack, ack, psh, fin, rst, urg
  tags                       keyword array — Arkime auto-tags + manual
  node                       capture node name
  network.community_id       IANA Community ID flow fingerprint
  length                     session duration in milliseconds
  srcPayload8 / dstPayload8  first 8 payload bytes (hex)

Environment variables (all optional, have defaults)
-----------------------------------------------------
  ARKIME_ES_URL     Elasticsearch base URL  (default: http://127.0.0.1:9200)
  ARKIME_ES_INDEX   Index pattern           (default: arkime_sessions3-*)
  ARKIME_ES_USER    Basic-auth username     (default: empty)
  ARKIME_ES_PASS    Basic-auth password     (default: empty)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# Arkime anomaly tags emitted automatically by capture:
ANOMALY_TAGS = frozenset(
    [
        "incomplete-tcp",
        "acked-unseen-segment-src",
        "acked-unseen-segment-dst",
        "out-of-order-src",
        "out-of-order-dst",
        "dns:qdcount-not-1",
        "cert:certificate-authority",
        "bad-checksum",
        "reassembly-ok",
    ]
)

# Tags that imply a human/rule-based threat verdict
THREAT_TAGS = frozenset(
    [
        "threat",
        "malware",
        "c2",
        "exfiltration",
        "lateral-movement",
        "suspicious",
        "blocked",
    ]
)


class ArkimeElasticsearchClient:
    """
    Read-only query interface to Arkime's Elasticsearch session store.
    Uses `requests` directly to avoid elasticsearch-py version conflicts.
    """

    def __init__(
        self,
        es_url: Optional[str] = None,
        index_pattern: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 15,
    ):
        self._base = (es_url or os.environ.get("ARKIME_ES_URL", "http://127.0.0.1:9200")).rstrip("/")
        self._index = index_pattern or os.environ.get("ARKIME_ES_INDEX", "arkime_sessions3-*")
        _user = username or os.environ.get("ARKIME_ES_USER", "")
        _pass = password or os.environ.get("ARKIME_ES_PASS", "")
        self._auth: Optional[HTTPBasicAuth] = HTTPBasicAuth(_user, _pass) if _user else None
        self._timeout = timeout
        self._session = requests.Session()
        if self._auth:
            self._session.auth = self._auth
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _get(self, path: str, **kwargs) -> Optional[Dict[str, Any]]:
        try:
            r = self._session.get(f"{self._base}{path}", timeout=self._timeout, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.debug("ES GET %s failed: %s", path, exc)
            return None

    def _post(self, path: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            r = self._session.post(
                f"{self._base}{path}",
                json=body,
                timeout=self._timeout,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.debug("ES POST %s failed: %s", path, exc)
            return None

    def is_reachable(self) -> bool:
        """Return True if Elasticsearch is up and the sessions index exists."""
        health = self._get("/_cluster/health")
        if not health:
            return False
        # Confirm the Arkime session index exists
        idx = self._get(f"/{self._index}")
        return idx is not None

    # ------------------------------------------------------------------
    # Session queries — Ulmo (network flow)
    # ------------------------------------------------------------------

    def query_recent_sessions(
        self,
        lookback_seconds: int = 300,
        size: int = 500,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (lookback_seconds * 1000)

        query: Dict[str, Any] = {
            "range": {"firstPacket": {"gte": since_ms, "lte": now_ms}}
        }
        if extra_filter:
            query = {"bool": {"must": [query, extra_filter]}}

        body = {
            "query": query,
            "size": size,
            "_source": [
                "firstPacket", "lastPacket", "length", "ipProtocol",
                "source.ip", "source.port", "source.bytes", "source.packets",
                "destination.ip", "destination.port", "destination.bytes", "destination.packets",
                "network.bytes", "network.packets", "network.community_id",
                "tcpflags", "tags", "node",
            ],
            "sort": [{"firstPacket": {"order": "desc"}}],
        }
        resp = self._post(f"/{self._index}/_search", body)
        if not resp:
            return []
        return [self._flatten_session(h["_source"]) for h in resp.get("hits", {}).get("hits", [])]

    def aggregate_top_talkers(
        self,
        lookback_seconds: int = 300,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (lookback_seconds * 1000)

        body = {
            "query": {"range": {"firstPacket": {"gte": since_ms}}},
            "size": 0,
            "aggs": {
                "src_ips": {
                    "terms": {"field": "source.ip", "size": top_n},
                    "aggs": {"total_bytes": {"sum": {"field": "network.bytes"}}},
                },
                "dst_ips": {
                    "terms": {"field": "destination.ip", "size": top_n},
                    "aggs": {"total_bytes": {"sum": {"field": "network.bytes"}}},
                },
                "protocols": {"terms": {"field": "ipProtocol", "size": 10}},
                "total_bytes": {"sum": {"field": "network.bytes"}},
                "total_packets": {"sum": {"field": "network.packets"}},
            },
        }
        resp = self._post(f"/{self._index}/_search", body)
        if not resp:
            return {}
        aggs = resp.get("aggregations", {})
        return {
            "src_ips": [
                {"ip": b["key"], "sessions": b["doc_count"], "bytes": int(b["total_bytes"]["value"])}
                for b in aggs.get("src_ips", {}).get("buckets", [])
            ],
            "dst_ips": [
                {"ip": b["key"], "sessions": b["doc_count"], "bytes": int(b["total_bytes"]["value"])}
                for b in aggs.get("dst_ips", {}).get("buckets", [])
            ],
            "protocols": {
                str(b["key"]): b["doc_count"]
                for b in aggs.get("protocols", {}).get("buckets", [])
            },
            "total_bytes": int(aggs.get("total_bytes", {}).get("value", 0)),
            "total_packets": int(aggs.get("total_packets", {}).get("value", 0)),
            "session_count": resp.get("hits", {}).get("total", {}).get("value", 0),
        }

    # ------------------------------------------------------------------
    # Threat queries — Mandos
    # ------------------------------------------------------------------

    def query_tagged_threats(
        self,
        lookback_seconds: int = 3600,
        size: int = 200,
    ) -> List[Dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (lookback_seconds * 1000)

        body = {
            "query": {
                "bool": {
                    "must": [
                        {"range": {"firstPacket": {"gte": since_ms}}},
                        {"terms": {"tags": sorted(THREAT_TAGS)}},
                    ]
                }
            },
            "size": size,
            "_source": ["firstPacket", "source.ip", "destination.ip", "tags", "network.bytes", "node"],
            "sort": [{"firstPacket": {"order": "desc"}}],
        }
        resp = self._post(f"/{self._index}/_search", body)
        if not resp:
            return []
        return [self._flatten_session(h["_source"]) for h in resp.get("hits", {}).get("hits", [])]

    def query_anomaly_sessions(
        self,
        lookback_seconds: int = 600,
        size: int = 200,
    ) -> List[Dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (lookback_seconds * 1000)

        body = {
            "query": {
                "bool": {
                    "must": [
                        {"range": {"firstPacket": {"gte": since_ms}}},
                        {"terms": {"tags": sorted(ANOMALY_TAGS)}},
                    ]
                }
            },
            "size": size,
            "_source": [
                "firstPacket", "lastPacket",
                "source.ip", "source.port",
                "destination.ip", "destination.port",
                "ipProtocol", "network.bytes", "network.packets",
                "tcpflags", "tags", "node",
            ],
            "sort": [{"firstPacket": {"order": "desc"}}],
        }
        resp = self._post(f"/{self._index}/_search", body)
        if not resp:
            return []
        return [self._flatten_session(h["_source"]) for h in resp.get("hits", {}).get("hits", [])]

    def aggregate_tag_counts(
        self,
        lookback_seconds: int = 3600,
        top_n: int = 30,
    ) -> Dict[str, int]:
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (lookback_seconds * 1000)

        body = {
            "query": {"range": {"firstPacket": {"gte": since_ms}}},
            "size": 0,
            "aggs": {"tags": {"terms": {"field": "tags", "size": top_n}}},
        }
        resp = self._post(f"/{self._index}/_search", body)
        if not resp:
            return {}
        return {
            b["key"]: b["doc_count"]
            for b in resp.get("aggregations", {}).get("tags", {}).get("buckets", [])
        }

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten_session(src: Dict[str, Any]) -> Dict[str, Any]:
        s = src.get("source", {})
        d = src.get("destination", {})
        net = src.get("network", {})
        flags = src.get("tcpflags", {})
        return {
            "first_packet_ms": src.get("firstPacket"),
            "last_packet_ms": src.get("lastPacket"),
            "duration_ms": src.get("length"),
            "protocol": src.get("ipProtocol"),
            "src_ip": s.get("ip"),
            "src_port": s.get("port"),
            "src_bytes": s.get("bytes"),
            "src_packets": s.get("packets"),
            "dst_ip": d.get("ip"),
            "dst_port": d.get("port"),
            "dst_bytes": d.get("bytes"),
            "dst_packets": d.get("packets"),
            "total_bytes": net.get("bytes"),
            "total_packets": net.get("packets"),
            "community_id": net.get("community_id"),
            "tcp_syn": flags.get("syn"),
            "tcp_rst": flags.get("rst"),
            "tcp_fin": flags.get("fin"),
            "tags": src.get("tags", []),
            "node": src.get("node"),
        }

    @staticmethod
    def protocol_name(proto_num: Optional[int]) -> str:
        _MAP = {1: "ICMP", 6: "TCP", 17: "UDP", 47: "GRE", 50: "ESP", 58: "ICMPv6"}
        return _MAP.get(proto_num, str(proto_num) if proto_num is not None else "unknown")
