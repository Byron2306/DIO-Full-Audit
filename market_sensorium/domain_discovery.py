from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .core import MarketSensoriumStore


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in ("title", "name", "label", "url", "href"):
                candidate = value.get(nested)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    return ""


def _candidate_score(domain_name: str, record: dict[str, Any]) -> float:
    domain_tokens = {
        token
        for token in str(domain_name).lower().replace("/", " ").replace("-", " ").split()
        if len(token) > 3
    }
    text = " ".join(
        str(record.get(key) or "") for key in ("title", "description", "name", "summary")
    ).lower()
    if not domain_tokens:
        return 0.35
    overlap = sum(token in text for token in domain_tokens)
    return max(0.30, min(0.85, 0.30 + overlap * 0.12))


def ingest_domain_discovery_signals(root: Path, store: MarketSensoriumStore) -> dict[str, Any]:
    """Ingest rotating ATLAS-domain public observations without minting targets.

    Domain search hits remain discovery candidates until separate entity resolution
    and ranking evidence admit them. This is knowledge acquisition, not lead creation.
    """
    signal_root = root / "state" / "market_sensorium" / "domain_signals"
    files = discoveries = habitats = 0
    source_counts: dict[str, int] = defaultdict(int)
    for path in sorted(signal_root.glob("*.json")) if signal_root.exists() else []:
        try:
            payload = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        domain_id = str(payload.get("domain_id") or path.stem)
        domain_name = str(payload.get("domain_name") or domain_id)
        observed_at = payload.get("finished_at") or payload.get("started_at") or None
        source_ref = str(path.relative_to(root))
        store.append_observation(
            source_kind="DOMAIN_PUBLIC_DISCOVERY",
            source_ref=source_ref,
            entity_kind="ATLAS_DOMAIN",
            entity_id=domain_id,
            domain_id=domain_id,
            observed_at=observed_at,
            payload={
                "domain_name": domain_name,
                "query": payload.get("query"),
                "baseline_state": payload.get("baseline_state"),
                "interpretation": payload.get("interpretation") or {},
                "authority_created": False,
            },
        )
        for source_name, source in (payload.get("sources") or {}).items():
            records = source.get("records") or []
            source_counts[source_name] += len(records)
            for record in records:
                title = _first_text(record, "title", "name", "description")
                if not title:
                    continue
                store.record_discovery_candidate(
                    source_kind=f"DOMAIN_{source_name.upper()}",
                    source_ref=source_ref,
                    candidate_kind="PUBLIC_DOMAIN_SIGNAL",
                    display_name=title,
                    domain_id=domain_id,
                    morphology=domain_name,
                    score=_candidate_score(domain_name, record),
                    state="UNRESOLVED_ENTITY",
                    observed_at=observed_at,
                    payload={
                        "record": record,
                        "query": payload.get("query"),
                        "target_created": False,
                        "market_demand_claimed": False,
                        "authority_created": False,
                    },
                )
                discoveries += 1
                if source_name == "youtube":
                    habitat_name = _first_text(record, "channel_title", "channel", "author", "source")
                    habitat_ref = _first_text(record, "channel_url", "url", "webpage_url", "source_url")
                    if habitat_name:
                        store.record_habitat(
                            platform="youtube",
                            canonical_name=habitat_name,
                            source_ref=habitat_ref or source_ref,
                            domain_id=domain_id,
                            access_state="PUBLIC_READ",
                            terms_state="CONNECTOR_GOVERNED",
                            payload={"domain_signal": source_ref, "record": record, "authority_created": False},
                        )
                        habitats += 1
                elif source_name == "google_news_rss":
                    habitat_name = _first_text(record, "publisher", "source", "author")
                    habitat_ref = _first_text(record, "url", "link", "source_url")
                    if habitat_name or habitat_ref:
                        store.record_habitat(
                            platform="news_or_blog",
                            canonical_name=habitat_name or habitat_ref,
                            source_ref=habitat_ref or source_ref,
                            domain_id=domain_id,
                            access_state="PUBLIC_READ",
                            terms_state="SOURCE_SPECIFIC",
                            payload={"domain_signal": source_ref, "record": record, "authority_created": False},
                        )
                        habitats += 1
        files += 1
    return {
        "domain_signal_files": files,
        "public_signal_records": dict(source_counts),
        "unresolved_discovery_candidates_observed": discoveries,
        "market_habitat_observations": habitats,
        "targets_created": 0,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
