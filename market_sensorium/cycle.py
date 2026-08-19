from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .baselines import compile_baselines, write_baselines
from .core import MarketSensoriumStore, TargetFeatures, utc_now
from .ingest import ingest_baselines, ingest_existing_prospects, ingest_hivenance_receipts, ingest_live_market_signals


class MarketSensoriumCycle:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.state_root = self.root / "state" / "market_sensorium"
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_root / "market_sensorium.sqlite"
        self.domain_registry = self.root / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
        self.seed_registry = self.root / "config" / "market_sensorium" / "seed_organisations.csv"
        self.baseline_output = self.state_root / "domain_baseline_candidates.csv"
        self.receipt_path = self.state_root / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"

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

    def compile_baselines(self) -> dict[str, Any]:
        rows, summary = compile_baselines(self.domain_registry, self.seed_registry, per_domain=5)
        write_baselines(self.baseline_output, rows)
        return {
            **summary,
            "output_path": str(self.baseline_output.relative_to(self.root)),
            "output_exists": self.baseline_output.is_file(),
        }

    def run(self, *, refresh_public: bool = False, mode: str = "read_only") -> dict[str, Any]:
        if mode != "read_only":
            raise ValueError("Market Sensorium currently supports read_only mode only.")
        started = utc_now()
        baseline_receipt = self.compile_baselines()
        refresh_receipt = self.refresh_existing_public_intelligence() if refresh_public else {"state": "not_requested"}

        with MarketSensoriumStore(self.db_path) as store:
            baseline_features, baseline_summary = ingest_baselines(
                self.root,
                store,
                self.domain_registry,
                self.seed_registry,
            )
            prospect_features, prospect_summary = ingest_existing_prospects(self.root, store)
            signal_summary = ingest_live_market_signals(self.root, store)
            hivenance_summary = ingest_hivenance_receipts(self.root, store)
            features = self._coalesce_features([*baseline_features, *prospect_features])
            rank_receipts = store.rank(features, observed_at=utc_now())
            rank_movers = sorted(
                [r for r in rank_receipts if r.rank_delta not in {None, 0}],
                key=lambda item: (-abs(item.rank_delta or 0), item.domain_id, item.current_rank),
            )[:50]
            summary = {
                "baseline": baseline_summary,
                "prospects": prospect_summary,
                "live_signals": signal_summary,
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
                "authority_created": False,
                "external_effects": False,
                "market_demand_claimed": False,
                "best_target_claimed": False,
            }
            receipt = store.write_cycle_receipt(started, mode, summary)
        receipt.update(
            {
                "acceptance": "DIO_MARKET_SENSORIUM_READ_ONLY_CYCLE_READY",
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
