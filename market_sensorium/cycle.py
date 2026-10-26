from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .baselines import compile_baselines, write_baselines
from .core import MarketSensoriumStore, TargetFeatures, utc_now
from .domain_discovery import ingest_domain_discovery_signals
from .ingest import ingest_baselines, ingest_existing_prospects, ingest_hivenance_receipts, ingest_live_market_signals
from .queries import mark_refreshed, select_domain_query_batch
from .resolution import resolve_discovery_candidates


class MarketSensoriumCycle:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.state_root = self.root / "state" / "market_sensorium"
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_root / "market_sensorium.sqlite"
        self.domain_registry = self.root / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
        self.seed_registry = self.root / "config" / "market_sensorium" / "seeds"
        self.baseline_output = self.state_root / "domain_baseline_candidates.csv"
        self.receipt_path = self.state_root / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"
        self.query_batch_path = self.state_root / "DOMAIN_DISCOVERY_QUERY_BATCH.json"
        self.query_history_path = self.state_root / "domain_query_history.json"

    def refresh_existing_public_intelligence(self) -> dict[str, Any]:
        script = self.root / "scripts" / "refresh_all_market_intelligence.py"
        if not script.is_file():
            return {"state": "missing", "script": str(script)}
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        if completed.returncode != 0:
            return {
                "state": "failed",
                "script": str(script.relative_to(self.root)),
                "returncode": completed.returncode,
                "error": (completed.stderr or completed.stdout)[-4000:],
            }
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"stdout": completed.stdout[-4000:]}
        return {
            "state": "refreshed",
            "script": str(script.relative_to(self.root)),
            "receipt": payload,
            "authority_created": False,
            "external_effects": False,
        }

    def refresh_domain_public_discovery(self, weak_domain_ids: set[str], limit: int = 8) -> dict[str, Any]:
        script = self.root / "scripts" / "refresh_market_sensorium_domain_signals.js"
        if not script.is_file():
            return {"state": "missing", "script": str(script), "authority_created": False}
        batch = select_domain_query_batch(
            self.domain_registry,
            self.query_history_path,
            weak_domain_ids=weak_domain_ids,
            limit=limit,
        )
        self.query_batch_path.write_text(json.dumps(batch, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        completed = subprocess.run(
            ["node", str(script), f"--batch={self.query_batch_path}"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        if completed.returncode != 0:
            return {
                "state": "failed",
                "batch": batch,
                "returncode": completed.returncode,
                "error": (completed.stderr or completed.stdout)[-4000:],
                "authority_created": False,
            }
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = {"results": [], "stdout": completed.stdout[-4000:]}
        mark_refreshed(self.query_history_path, batch, result)
        return {
            "state": "refreshed",
            "batch_size": len(batch.get("domains") or []),
            "batch_path": str(self.query_batch_path.relative_to(self.root)),
            "receipt": result,
            "authority_created": False,
            "external_effects": False,
        }

    def refresh_mail_ingress(self) -> dict[str, Any]:
        """Pull inbound Outlook replies when Graph is already configured.

        This is a read-only observation refresh. Missing credentials do not block the
        rest of the Sensorium cycle.
        """
        config_path = self.root / "config" / "microsoft_graph.local.json"
        script = self.root / "scripts" / "sync_outlook_mail.py"
        if not config_path.is_file() or not script.is_file():
            return {"state": "not_configured", "authority_created": False}
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"state": "config_invalid", "authority_created": False}
        client_id = str(config.get("client_id") or "")
        token_cache_raw = str(config.get("token_cache_path") or "")
        token_cache = Path(token_cache_raw).expanduser() if token_cache_raw else None
        if not client_id or client_id.startswith("REPLACE_") or token_cache is None or not token_cache.exists():
            return {"state": "not_configured", "authority_created": False}
        completed = subprocess.run(
            [sys.executable, str(script), "pull"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            return {
                "state": "failed",
                "returncode": completed.returncode,
                "error": (completed.stderr or completed.stdout)[-3000:],
                "authority_created": False,
            }
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"stdout": completed.stdout[-3000:]}
        return {
            "state": "refreshed",
            "receipt": payload,
            "authority_created": False,
            "external_effects": False,
        }

    def compile_baselines(self) -> dict[str, Any]:
        rows, summary = compile_baselines(self.domain_registry, self.seed_registry, per_domain=5)
        write_baselines(self.baseline_output, rows)
        return {
            **summary,
            "output_path": str(self.baseline_output.relative_to(self.root)),
            "output_exists": self.baseline_output.is_file(),
        }

    def run(self, *, refresh_public: bool = False, refresh_mail: bool = False, mode: str = "read_only") -> dict[str, Any]:
        if mode != "read_only":
            raise ValueError("Market Sensorium currently supports read_only mode only.")
        started = utc_now()
        baseline_receipt = self.compile_baselines()
        weak_domain_ids = set(baseline_receipt.get("family_fallback_only_domains") or [])
        refresh_receipt = self.refresh_existing_public_intelligence() if refresh_public else {"state": "not_requested"}
        domain_refresh = self.refresh_domain_public_discovery(weak_domain_ids) if refresh_public else {"state": "not_requested"}
        mail_refresh = self.refresh_mail_ingress() if refresh_mail else {"state": "not_requested"}

        with MarketSensoriumStore(self.db_path) as store:
            baseline_features, baseline_summary = ingest_baselines(
                self.root,
                store,
                self.domain_registry,
                self.seed_registry,
            )
            prospect_features, prospect_summary = ingest_existing_prospects(self.root, store)
            signal_summary = ingest_live_market_signals(self.root, store)
            domain_signal_summary = ingest_domain_discovery_signals(self.root, store)
            hivenance_summary = ingest_hivenance_receipts(self.root, store)

            # MS-1: source-bound discoveries may become rankable organisation
            # hypotheses only when the resolver can establish an organisation
            # identity. Buyer-unit verification, lead status, demand and authority
            # remain explicitly unproved.
            discovered_features, resolution_summary = resolve_discovery_candidates(store)

            features = self._coalesce_features([
                *baseline_features,
                *prospect_features,
                *discovered_features,
            ])
            rank_receipts = store.rank(features, observed_at=utc_now())
            rank_movers = sorted(
                [r for r in rank_receipts if r.rank_delta not in {None, 0}],
                key=lambda item: (-abs(item.rank_delta or 0), item.domain_id, item.current_rank),
            )[:50]
            seed_supersession = self._seed_supersession(
                rank_receipts,
                baseline_features=baseline_features,
                discovered_features=discovered_features,
            )
            summary = {
                "baseline": baseline_summary,
                "prospects": prospect_summary,
                "live_signals": signal_summary,
                "domain_discovery": domain_signal_summary,
                "discovery_resolution": resolution_summary,
                "seed_supersession": seed_supersession,
                "hivenance": hivenance_summary,
                "store": store.summary(),
                "ranked_targets": len(rank_receipts),
                "rank_movers": [
                    {
                        "target_id": item.target_id,
                        "organisation": item.organisation,
                        "domain_id": item.domain_id,
                        "previous_rank": item.previous_rank,
                        "current_rank": item.current_rank,
                        "rank_delta": item.rank_delta,
                        "score": item.score,
                        "causes": list(item.causes),
                    }
                    for item in rank_movers
                ],
                "public_refresh": refresh_receipt,
                "domain_public_refresh": domain_refresh,
                "mail_ingress_refresh": mail_refresh,
                "authority_created": False,
                "external_effects": False,
                "market_demand_claimed": False,
                "best_target_claimed": False,
            }
            receipt = store.write_cycle_receipt(started, mode, summary)
        receipt.update(
            {
                "acceptance": "DIO_MARKET_SENSORIUM_READ_ONLY_CYCLE_READY",
                "ms1_acceptance": "DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_READY",
                "baseline_compiler": baseline_receipt,
                "state_db": str(self.db_path.relative_to(self.root)),
                "authority_created": False,
                "external_effects": False,
                "publication": "not_authorised",
                "outreach": "not_authorised",
                "spend": "not_authorised",
                "join": "not_authorised",
                "dm": "not_authorised",
            }
        )
        self.receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return receipt

    @staticmethod
    def _seed_supersession(
        rank_receipts: list[Any],
        *,
        baseline_features: list[TargetFeatures],
        discovered_features: list[TargetFeatures],
    ) -> dict[str, Any]:
        baseline_ids = {item.target_id for item in baseline_features}
        discovered_ids = {item.target_id for item in discovered_features}
        receipt_by_id = {item.target_id: item for item in rank_receipts}
        seeds_by_domain: dict[str, list[Any]] = {}
        for item in rank_receipts:
            if item.target_id in baseline_ids:
                seeds_by_domain.setdefault(item.domain_id, []).append(item)

        examples: list[dict[str, Any]] = []
        outranked_seed_ids: set[str] = set()
        domains: set[str] = set()
        for target_id in sorted(discovered_ids):
            discovered = receipt_by_id.get(target_id)
            if discovered is None:
                continue
            worse_seeds = [
                seed for seed in seeds_by_domain.get(discovered.domain_id, [])
                if seed.current_rank > discovered.current_rank
            ]
            if not worse_seeds:
                continue
            worse_seeds.sort(key=lambda item: item.current_rank)
            domains.add(discovered.domain_id)
            outranked_seed_ids.update(seed.target_id for seed in worse_seeds)
            first_seed = worse_seeds[0]
            examples.append(
                {
                    "domain_id": discovered.domain_id,
                    "discovered_target_id": discovered.target_id,
                    "discovered_organisation": discovered.organisation,
                    "discovered_rank": discovered.current_rank,
                    "discovered_score": discovered.score,
                    "outranked_seed_target_id": first_seed.target_id,
                    "outranked_seed_organisation": first_seed.organisation,
                    "outranked_seed_rank": first_seed.current_rank,
                    "authority_created": False,
                }
            )

        return {
            "discovered_targets_ranked": sum(1 for target_id in discovered_ids if target_id in receipt_by_id),
            "seed_targets_outranked": len(outranked_seed_ids),
            "domains_with_seed_supersession": len(domains),
            "seed_supersession_observed": bool(outranked_seed_ids),
            "examples": examples[:20],
            "interpretation": (
                "Fresh source-bound discovered target hypotheses outranked one or more curated seed priors."
                if outranked_seed_ids
                else "No discovered target hypothesis outranked a curated seed prior in this observation set."
            ),
            "best_target_claimed": False,
            "market_demand_claimed": False,
            "authority_created": False,
        }

    @staticmethod
    def _coalesce_features(items: list[TargetFeatures]) -> list[TargetFeatures]:
        """Keep the strongest evidence row for a target without inventing evidence."""
        by_key: dict[tuple[str, str], TargetFeatures] = {}
        for item in items:
            key = (item.domain_id, item.target_id)
            current = by_key.get(key)
            if current is None:
                by_key[key] = item
                continue
            current_evidence = (
                current.problem_signal_strength
                + current.signal_recency
                + current.route_quality
                + current.prior_engagement
            )
            item_evidence = (
                item.problem_signal_strength
                + item.signal_recency
                + item.route_quality
                + item.prior_engagement
            )
            if item_evidence > current_evidence:
                by_key[key] = item
        return list(by_key.values())
