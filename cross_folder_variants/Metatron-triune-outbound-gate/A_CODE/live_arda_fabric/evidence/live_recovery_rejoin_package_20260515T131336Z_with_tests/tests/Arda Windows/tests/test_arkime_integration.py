"""
tests/test_arkime_integration.py
=================================
Tests for the Arkime evidence integration.

Two test classes:
  TestArkimeClientUnit       — fully mocked, runs anywhere (CI-safe)
  TestArkimeLiveIntegration  — hits the real ES at http://127.0.0.1:9200
                               skipped automatically if ES is unreachable
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import MagicMock, patch
from arda_windows.integrations.arkime_client import (
    ArkimeElasticsearchClient,
    ANOMALY_TAGS,
    THREAT_TAGS,
)
from arda_windows.integrations.arkime_evidence_provider import ArkimeEvidenceProvider
from arda_windows.models import EvidencePacket
from arda_windows.world_manifold import WorldManifold


LIVE_ES = "http://127.0.0.1:9200"


def _es_reachable() -> bool:
    try:
        import requests
        r = requests.get(f"{LIVE_ES}/_cluster/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Unit tests (fully mocked)
# ---------------------------------------------------------------------------

class TestArkimeClientUnit:
    def _make_client(self) -> ArkimeElasticsearchClient:
        return ArkimeElasticsearchClient(es_url=LIVE_ES)

    def test_flatten_session_all_fields(self):
        raw = {
            "firstPacket": 1000,
            "lastPacket": 2000,
            "length": 1000,
            "ipProtocol": 6,
            "source": {"ip": "1.2.3.4", "port": 1234, "bytes": 500, "packets": 5},
            "destination": {"ip": "5.6.7.8", "port": 80, "bytes": 300, "packets": 4},
            "network": {"bytes": 800, "packets": 9, "community_id": "1:abc="},
            "tcpflags": {"syn": 1, "rst": 0, "fin": 1},
            "tags": ["incomplete-tcp"],
            "node": "test-node",
        }
        flat = ArkimeElasticsearchClient._flatten_session(raw)
        assert flat["src_ip"] == "1.2.3.4"
        assert flat["dst_ip"] == "5.6.7.8"
        assert flat["dst_port"] == 80
        assert flat["total_bytes"] == 800
        assert flat["tags"] == ["incomplete-tcp"]
        assert flat["community_id"] == "1:abc="
        assert flat["tcp_fin"] == 1

    def test_flatten_session_missing_fields(self):
        flat = ArkimeElasticsearchClient._flatten_session({})
        assert flat["src_ip"] is None
        assert flat["tags"] == []

    def test_protocol_name_known(self):
        assert ArkimeElasticsearchClient.protocol_name(6) == "TCP"
        assert ArkimeElasticsearchClient.protocol_name(17) == "UDP"
        assert ArkimeElasticsearchClient.protocol_name(1) == "ICMP"

    def test_protocol_name_unknown(self):
        assert ArkimeElasticsearchClient.protocol_name(99) == "99"
        assert ArkimeElasticsearchClient.protocol_name(None) == "unknown"

    def test_is_reachable_returns_false_on_error(self):
        client = ArkimeElasticsearchClient(es_url="http://does-not-exist:9999")
        assert client.is_reachable() is False

    def test_query_returns_empty_on_unreachable(self):
        client = ArkimeElasticsearchClient(es_url="http://does-not-exist:9999")
        assert client.query_recent_sessions() == []
        assert client.query_tagged_threats() == []
        assert client.query_anomaly_sessions() == []
        assert client.aggregate_top_talkers() == {}
        assert client.aggregate_tag_counts() == {}

    def test_anomaly_tags_and_threat_tags_disjoint(self):
        assert ANOMALY_TAGS.isdisjoint(THREAT_TAGS), (
            "A tag should not appear in both ANOMALY_TAGS and THREAT_TAGS"
        )


class TestArkimeEvidenceProviderUnit:
    def _make_provider(self, reachable=True, sessions=None, talkers=None, threats=None, anomalies=None, tag_counts=None):
        client = MagicMock(spec=ArkimeElasticsearchClient)
        client.is_reachable.return_value = reachable
        client.query_recent_sessions.return_value = sessions or []
        client.aggregate_top_talkers.return_value = talkers or {}
        client.query_tagged_threats.return_value = threats or []
        client.query_anomaly_sessions.return_value = anomalies or []
        client.aggregate_tag_counts.return_value = tag_counts or {}
        return ArkimeEvidenceProvider(client=client)

    def test_ulmo_stub_when_unreachable(self):
        p = self._make_provider(reachable=False)
        pkt = p.collect_ulmo_evidence({})
        assert isinstance(pkt, EvidencePacket)
        assert pkt.confidence == 0.0
        assert pkt.evidence.get("stub") is True
        assert pkt.evidence.get("arkime_reachable") is False

    def test_mandos_stub_when_unreachable(self):
        p = self._make_provider(reachable=False)
        pkt = p.collect_mandos_evidence({})
        assert pkt.confidence == 0.0
        assert pkt.evidence.get("stub") is True

    def test_ulmo_confidence_1_when_sessions_present(self):
        fake_session = {"src_ip": "1.2.3.4", "dst_ip": "5.6.7.8", "tags": []}
        p = self._make_provider(sessions=[fake_session])
        pkt = p.collect_ulmo_evidence({})
        assert pkt.confidence == 1.0
        assert pkt.source == "arkime_ulmo"
        assert pkt.evidence["arkime_reachable"] is True
        assert len(pkt.evidence["active_sessions"]) == 1

    def test_ulmo_confidence_06_when_reachable_but_empty(self):
        p = self._make_provider(sessions=[])
        pkt = p.collect_ulmo_evidence({})
        assert pkt.confidence == 0.6

    def test_mandos_confidence_10_with_threat_sessions(self):
        p = self._make_provider(threats=[{"tags": ["threat"]}])
        pkt = p.collect_mandos_evidence({})
        assert pkt.confidence == 1.0
        assert pkt.evidence["threat_count"] == 1

    def test_mandos_confidence_07_with_only_anomalies(self):
        p = self._make_provider(anomalies=[{"tags": ["incomplete-tcp"]}])
        pkt = p.collect_mandos_evidence({})
        assert pkt.confidence == 0.7

    def test_mandos_confidence_05_when_clean(self):
        p = self._make_provider()
        pkt = p.collect_mandos_evidence({})
        assert pkt.confidence == 0.5

    def test_varda_and_manwe_are_stubs(self):
        p = self._make_provider()
        for method in [p.collect_varda_evidence, p.collect_manwe_evidence]:
            pkt = method({})
            assert pkt.confidence == 0.0
            assert pkt.evidence.get("stub") is True

    def test_sweep_ids_unique(self):
        p = self._make_provider()
        p1 = p.collect_ulmo_evidence({})
        p2 = p.collect_ulmo_evidence({})
        assert p1.sweep_id != p2.sweep_id

    def test_network_risk_score_zero_when_clean(self):
        p = self._make_provider()
        pkt = p.collect_mandos_evidence({})
        assert pkt.evidence["network_risk_score"] == 0.0

    def test_network_risk_score_high_with_threats(self):
        p = self._make_provider(
            threats=[{"tags": ["threat"]}] * 10,
            tag_counts={"threat": 10, "acked-unseen-segment-src": 5},
        )
        pkt = p.collect_mandos_evidence({})
        score = pkt.evidence["network_risk_score"]
        assert score >= 0.5, f"Expected high score, got {score}"

    def test_extract_tags_filters_correctly(self):
        sessions = [
            {"tags": ["incomplete-tcp", "threat"]},
            {"tags": ["out-of-order-src"]},
            {"tags": []},
        ]
        result = ArkimeEvidenceProvider._extract_tags(sessions, ANOMALY_TAGS)
        assert "incomplete-tcp" in result
        assert "out-of-order-src" in result
        assert "threat" not in result  # threat is not in ANOMALY_TAGS


class TestWorldManifoldArkimeWiring:
    def test_build_without_arkime_url_uses_native_provider(self):
        m = WorldManifold.build()
        summary = m.platform_summary()
        assert summary["arkime_integration_active"] is False

    def test_build_with_unreachable_arkime_still_builds(self):
        # Should not raise even if ES is down
        m = WorldManifold.build(arkime_es_url="http://does-not-exist:9999")
        summary = m.platform_summary()
        assert summary["arkime_integration_active"] is True  # wired, even if offline

    def test_hybrid_provider_routes_correctly(self):
        """Ulmo/Mandos go to Arkime; Varda/Manwë go to native provider."""
        from arda_windows.world_manifold import _ArkimeHybridProvider

        arkime_mock = MagicMock(spec=ArkimeEvidenceProvider)
        native_mock = MagicMock()

        stub_pkt = EvidencePacket(
            source="test", confidence=0.9, evidence={"ok": True}
        )
        arkime_mock.collect_ulmo_evidence.return_value = stub_pkt
        arkime_mock.collect_mandos_evidence.return_value = stub_pkt
        native_mock.collect_varda_evidence.return_value = stub_pkt
        native_mock.collect_manwe_evidence.return_value = stub_pkt

        hybrid = _ArkimeHybridProvider(arkime=arkime_mock, native=native_mock)

        hybrid.collect_ulmo_evidence({})
        arkime_mock.collect_ulmo_evidence.assert_called_once()
        native_mock.collect_ulmo_evidence.assert_not_called()

        hybrid.collect_mandos_evidence({})
        arkime_mock.collect_mandos_evidence.assert_called_once()

        hybrid.collect_varda_evidence({})
        native_mock.collect_varda_evidence.assert_called_once()
        arkime_mock.collect_varda_evidence.assert_not_called()

        hybrid.collect_manwe_evidence({})
        native_mock.collect_manwe_evidence.assert_called_once()


# ---------------------------------------------------------------------------
# Live integration tests (skipped when ES unavailable)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _es_reachable(), reason="Arkime ES not reachable at http://127.0.0.1:9200")
class TestArkimeLiveIntegration:
    """Hits the real running Arkime Elasticsearch."""

    def setup_method(self):
        self.client = ArkimeElasticsearchClient(es_url=LIVE_ES)
        self.provider = ArkimeEvidenceProvider(
            client=self.client,
            ulmo_lookback_seconds=86400,   # 24h window to find data
            mandos_lookback_seconds=86400,
        )

    def test_is_reachable(self):
        assert self.client.is_reachable() is True

    def test_recent_sessions_returns_data(self):
        sessions = self.client.query_recent_sessions(lookback_seconds=86400, size=50)
        assert isinstance(sessions, list)
        # We know 64K sessions exist; with 24h lookback we should get data
        assert len(sessions) > 0, "Expected sessions from 24h lookback on live data"

    def test_session_fields_present(self):
        sessions = self.client.query_recent_sessions(lookback_seconds=86400, size=5)
        if sessions:
            s = sessions[0]
            assert "src_ip" in s
            assert "dst_ip" in s
            assert "total_bytes" in s
            assert "tags" in s

    def test_aggregate_top_talkers(self):
        result = self.client.aggregate_top_talkers(lookback_seconds=86400)
        assert "src_ips" in result
        assert "dst_ips" in result
        assert "protocols" in result
        assert result.get("session_count", 0) > 0

    def test_aggregate_tag_counts_has_known_tags(self):
        tags = self.client.aggregate_tag_counts(lookback_seconds=86400)
        assert isinstance(tags, dict)
        assert "incomplete-tcp" in tags, (
            f"Expected 'incomplete-tcp' tag in live data; got keys: {list(tags)[:10]}"
        )

    def test_query_anomaly_sessions(self):
        anomalies = self.client.query_anomaly_sessions(lookback_seconds=86400, size=50)
        assert isinstance(anomalies, list)
        # We know anomaly tags exist in the data
        assert len(anomalies) > 0, "Expected anomaly-tagged sessions in live data"
        for s in anomalies[:5]:
            assert any(t in ANOMALY_TAGS for t in s.get("tags", []))

    def test_ulmo_evidence_packet_live(self):
        pkt = self.provider.collect_ulmo_evidence({})
        assert isinstance(pkt, EvidencePacket)
        assert pkt.source == "arkime_ulmo"
        assert pkt.confidence >= 0.6  # reachable, possibly no sessions in 5m
        assert pkt.evidence["arkime_reachable"] is True
        assert "top_src_ips" in pkt.evidence
        assert "anomaly_count" in pkt.evidence

    def test_mandos_evidence_packet_live(self):
        pkt = self.provider.collect_mandos_evidence({})
        assert isinstance(pkt, EvidencePacket)
        assert pkt.source == "arkime_mandos"
        assert pkt.confidence >= 0.5
        assert "tag_counts" in pkt.evidence
        assert "network_risk_score" in pkt.evidence
        assert 0.0 <= pkt.evidence["network_risk_score"] <= 1.0

    def test_mandos_has_anomaly_data_live(self):
        pkt = self.provider.collect_mandos_evidence({})
        assert pkt.evidence.get("anomaly_count", 0) > 0, (
            "Expected anomaly sessions in Mandos evidence from live data"
        )

    def test_world_manifold_with_live_arkime(self):
        m = WorldManifold.build(arkime_es_url=LIVE_ES, arkime_ulmo_lookback=86400)
        summary = m.platform_summary()
        assert summary["arkime_integration_active"] is True

        ulmo = m.evidence.collect_ulmo_evidence({})
        mandos = m.evidence.collect_mandos_evidence({})
        assert ulmo.evidence["arkime_reachable"] is True
        assert mandos.evidence["arkime_reachable"] is True
        assert ulmo.evidence.get("session_count", 0) > 0
