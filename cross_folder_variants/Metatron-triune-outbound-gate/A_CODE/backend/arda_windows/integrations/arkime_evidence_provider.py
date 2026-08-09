"""
ArkimeEvidenceProvider
=======================
Implements EvidenceProvider sourcing Ulmo (network) and Mandos (threat)
evidence directly from Arkime's Elasticsearch session store.

Replaces the Windows-only netstat/Firewall/Defender collectors with
real full-packet-capture telemetry when an Arkime container is available —
works on both Linux and Windows hosts as long as ES is reachable.

Ulmo evidence payload (collect_ulmo_evidence)
---------------------------------------------
  active_sessions      list of recent sessions (src/dst/bytes/proto/tags)
  top_talkers          aggregated src/dst IPs + protocols by bytes
  session_count        total sessions in lookback window
  total_bytes          aggregate bytes across all sessions
  anomaly_sessions     sessions with Arkime auto-anomaly tags
  anomaly_count        count of anomalous sessions
  arkime_reachable     bool — whether ES was reachable at collection time

Mandos evidence payload (collect_mandos_evidence)
--------------------------------------------------
  threat_sessions      sessions with explicit threat/malware/c2 tags
  threat_count         count of threat-tagged sessions
  anomaly_sessions     sessions with protocol/TCP anomaly tags
  tag_counts           {tag: count} across the lookback window
  threat_tags_active   list of threat tag names currently seen
  anomaly_tags_active  list of anomaly tag names currently seen
  arkime_reachable     bool

The provider also satisfies collect_varda_evidence and collect_manwe_evidence
with stub packets (those domains are served by Windows-native providers).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import EvidencePacket
from .arkime_client import ArkimeElasticsearchClient, ANOMALY_TAGS, THREAT_TAGS

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_sweep_id() -> str:
    return str(uuid.uuid4())


class ArkimeEvidenceProvider:
    """
    Full-packet-capture evidence provider backed by Arkime + Elasticsearch.

    Parameters
    ----------
    client : ArkimeElasticsearchClient, optional
        Pre-built client.  If None, one is created from environment variables
        (ARKIME_ES_URL, ARKIME_ES_INDEX, ARKIME_ES_USER, ARKIME_ES_PASS).
    ulmo_lookback_seconds : int
        How far back to look for network flow evidence (default: 300s / 5 min).
    mandos_lookback_seconds : int
        How far back to look for threat evidence (default: 3600s / 1 hr).
    """

    SOURCE_ULMO = "arkime_ulmo"
    SOURCE_MANDOS = "arkime_mandos"

    def __init__(
        self,
        client: Optional[ArkimeElasticsearchClient] = None,
        ulmo_lookback_seconds: int = 300,
        mandos_lookback_seconds: int = 3600,
    ):
        self._client = client or ArkimeElasticsearchClient()
        self._ulmo_lookback = ulmo_lookback_seconds
        self._mandos_lookback = mandos_lookback_seconds

    # ------------------------------------------------------------------
    # Ulmo — network flow evidence
    # ------------------------------------------------------------------

    def collect_ulmo_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Query Arkime for recent network sessions + top-talker aggregation.
        Anomalous sessions (incomplete-tcp, acked-unseen, bad DNS, etc.)
        are surfaced separately so the constitutional layer can weight them.
        """
        sweep_id = _new_sweep_id()
        reachable = self._client.is_reachable()

        if not reachable:
            logger.warning("Arkime ES not reachable; Ulmo returning stub")
            return EvidencePacket(
                source=self.SOURCE_ULMO,
                confidence=0.0,
                sweep_id=sweep_id,
                evidence={
                    "stub": True,
                    "reason": "Arkime Elasticsearch unreachable",
                    "collected_at": _now_iso(),
                    "arkime_reachable": False,
                },
            )

        sessions = self._client.query_recent_sessions(
            lookback_seconds=self._ulmo_lookback, size=500
        )
        talkers = self._client.aggregate_top_talkers(
            lookback_seconds=self._ulmo_lookback, top_n=20
        )
        anomalies = self._client.query_anomaly_sessions(
            lookback_seconds=self._ulmo_lookback, size=200
        )

        # Compute confidence: 1.0 if sessions present, 0.6 if ES alive but no sessions
        confidence = 1.0 if sessions else 0.6

        return EvidencePacket(
            source=self.SOURCE_ULMO,
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "arkime_reachable": True,
                "lookback_seconds": self._ulmo_lookback,
                # Session sample (capped at 100 for packet size)
                "active_sessions": sessions[:100],
                "session_count": talkers.get("session_count", len(sessions)),
                "total_bytes": talkers.get("total_bytes", 0),
                "total_packets": talkers.get("total_packets", 0),
                # Top-talker aggregations
                "top_src_ips": talkers.get("src_ips", []),
                "top_dst_ips": talkers.get("dst_ips", []),
                "protocol_distribution": talkers.get("protocols", {}),
                # Anomalous sessions
                "anomaly_sessions": anomalies[:50],
                "anomaly_count": len(anomalies),
                "anomaly_tags_seen": self._extract_tags(anomalies, ANOMALY_TAGS),
            },
        )

    # ------------------------------------------------------------------
    # Mandos — threat verdict evidence
    # ------------------------------------------------------------------

    def collect_mandos_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Query Arkime for threat-tagged sessions and anomaly indicators.
        Provides Mandos with network-layer threat verdicts to complement
        Defender/WMI host-based detections.
        """
        sweep_id = _new_sweep_id()
        reachable = self._client.is_reachable()

        if not reachable:
            logger.warning("Arkime ES not reachable; Mandos returning stub")
            return EvidencePacket(
                source=self.SOURCE_MANDOS,
                confidence=0.0,
                sweep_id=sweep_id,
                evidence={
                    "stub": True,
                    "reason": "Arkime Elasticsearch unreachable",
                    "collected_at": _now_iso(),
                    "arkime_reachable": False,
                },
            )

        threat_sessions = self._client.query_tagged_threats(
            lookback_seconds=self._mandos_lookback, size=200
        )
        anomaly_sessions = self._client.query_anomaly_sessions(
            lookback_seconds=self._mandos_lookback, size=200
        )
        tag_counts = self._client.aggregate_tag_counts(
            lookback_seconds=self._mandos_lookback, top_n=50
        )

        threat_tags_active = [t for t in tag_counts if t in THREAT_TAGS]
        anomaly_tags_active = [t for t in tag_counts if t in ANOMALY_TAGS]

        # Confidence: 1.0 if explicit threat tags present, 0.7 if only anomalies
        if threat_sessions:
            confidence = 1.0
        elif anomaly_sessions:
            confidence = 0.7
        else:
            confidence = 0.5  # reachable but clean

        return EvidencePacket(
            source=self.SOURCE_MANDOS,
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "arkime_reachable": True,
                "lookback_seconds": self._mandos_lookback,
                # Threat-tagged sessions
                "threat_sessions": threat_sessions[:50],
                "threat_count": len(threat_sessions),
                "threat_tags_active": threat_tags_active,
                # Anomaly sessions (protocol-level indicators)
                "anomaly_sessions": anomaly_sessions[:50],
                "anomaly_count": len(anomaly_sessions),
                "anomaly_tags_active": anomaly_tags_active,
                # Full tag landscape
                "tag_counts": tag_counts,
                # Derived risk score (0.0–1.0)
                "network_risk_score": self._compute_risk_score(
                    threat_sessions, anomaly_sessions, tag_counts
                ),
            },
        )

    # ------------------------------------------------------------------
    # Stub implementations for Varda + Manwë (not Arkime's domain)
    # ------------------------------------------------------------------

    def collect_varda_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """Varda (file/registry integrity) is not sourced from Arkime; return stub."""
        return EvidencePacket(
            source="arkime_varda_stub",
            confidence=0.0,
            sweep_id=_new_sweep_id(),
            evidence={
                "stub": True,
                "reason": "Varda evidence not available from Arkime; use WindowsEvidenceProvider",
                "collected_at": _now_iso(),
            },
        )

    def collect_manwe_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """Manwë (process lineage) is not sourced from Arkime; return stub."""
        return EvidencePacket(
            source="arkime_manwe_stub",
            confidence=0.0,
            sweep_id=_new_sweep_id(),
            evidence={
                "stub": True,
                "reason": "Manwë process evidence not available from Arkime; use WindowsEvidenceProvider",
                "collected_at": _now_iso(),
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tags(
        sessions: List[Dict[str, Any]], tag_set: frozenset
    ) -> List[str]:
        """Collect the union of matching tags seen across a session list."""
        seen: set = set()
        for s in sessions:
            for tag in s.get("tags", []):
                if tag in tag_set:
                    seen.add(tag)
        return sorted(seen)

    @staticmethod
    def _compute_risk_score(
        threat_sessions: List[Dict[str, Any]],
        anomaly_sessions: List[Dict[str, Any]],
        tag_counts: Dict[str, int],
    ) -> float:
        """
        Heuristic 0.0–1.0 risk score from network evidence alone.

        Weights:
          Explicit threat tags present              +0.5 base
          Each threat-tagged session (cap at 0.3)  +0.01 each
          Anomaly session ratio > 5 %              +0.1
          High-confidence anomaly tags             +0.05 each (cap 0.2)
        """
        score = 0.0

        if threat_sessions:
            score += 0.5
            score += min(len(threat_sessions) * 0.01, 0.3)

        total_sessions = sum(tag_counts.values()) or 1
        anomaly_total = sum(
            c for tag, c in tag_counts.items() if tag in ANOMALY_TAGS
        )
        if anomaly_total / total_sessions > 0.05:
            score += 0.1

        high_confidence_anomalies = {
            "acked-unseen-segment-src",
            "acked-unseen-segment-dst",
            "bad-checksum",
        }
        for tag in high_confidence_anomalies:
            if tag_counts.get(tag, 0) > 0:
                score += 0.05

        return min(round(score, 3), 1.0)
