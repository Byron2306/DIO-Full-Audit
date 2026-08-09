from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import yaml


DEFAULT_LAYERS: List[Dict[str, Any]] = [
    {
        "id": "layer_1_research_registry",
        "name": "Research Architecture Registry",
        "status": "complete",
        "purpose": "Track external research engines, evidence gates, and integration readiness.",
        "systems": ["freqtrade", "hummingbot", "jesse", "nautilus_trader", "hftbacktest"],
        "gates": ["dry_run_required", "backtest_metrics_required", "queen_review_required"],
    },
    {
        "id": "layer_2_event_config_spine",
        "name": "Event + Config Spine",
        "status": "complete",
        "purpose": "Move hot configuration and critical events behind typed services.",
        "systems": ["config_agent", "redis_streams", "error_monitor"],
        "gates": ["schema_validation", "rollback_snapshot", "operator_audit"],
    },
    {
        "id": "layer_3_backtest_evidence_loop",
        "name": "Backtest Evidence Loop",
        "status": "complete",
        "purpose": "Normalize public bot and Hivenance backtest evidence before promotion.",
        "systems": ["freqtrade", "jesse", "hummingbot", "hftbacktest"],
        "gates": ["walk_forward", "max_drawdown", "minimum_trades", "paper_promotion"],
    },
    {
        "id": "layer_4_ml_research_lab",
        "name": "ML Research Lab",
        "status": "complete",
        "purpose": "Add FreqAI/FinRL-style model training as offline candidates only.",
        "systems": ["freqai", "finrl_crypto", "macrohft", "webcryptoagent"],
        "gates": ["layer3_evidence", "walk_forward", "pbo_check", "leakage_check", "negative_case_replay", "offline_only", "risk_sensitive_eval"],
    },
    {
        "id": "layer_5_execution_parity",
        "name": "Execution Parity",
        "status": "complete",
        "purpose": "Model latency, queue position, slippage, and order state parity.",
        "systems": ["nautilus_trader", "hftbacktest", "hummingbot", "execution_parity"],
        "gates": ["latency_budget", "slippage_budget", "queue_position", "fill_model_audit"],
    },
    {
        "id": "layer_6_signal_marketplace",
        "name": "Signal Marketplace",
        "status": "complete",
        "purpose": "Sandbox Bittensor-style miner/validator signal scoring.",
        "systems": ["vanta_network", "candles_tao", "time_series_subnet", "signal_marketplace"],
        "gates": ["signed_submissions", "plagiarism_check", "drawdown_elimination", "realized_outcome_scoring", "reward_simulation", "sandbox_only"],
    },
]


DEFAULT_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "freqtrade": {
        "role": "Backtesting, optimization, FreqAI adaptive ML sandbox",
        "adapter_status": "public_bot_bridge",
        "risk": "Model leakage and overfitting if promoted without walk-forward evidence",
    },
    "hummingbot": {
        "role": "Market-making and execution orchestration substrate",
        "adapter_status": "plan_and_lifecycle",
        "risk": "Live sidecar must stay gated until operator confirmation and safeguards pass",
    },
    "jesse": {
        "role": "Fast strategy research, optimization, paper/live loop",
        "adapter_status": "planned",
        "risk": "Backtest realism and exchange parity must be verified",
    },
    "nautilus_trader": {
        "role": "Event-driven research/live parity engine",
        "adapter_status": "planned",
        "risk": "Operational complexity and venue adapter correctness",
    },
    "hftbacktest": {
        "role": "Latency and queue-position-aware replay",
        "adapter_status": "planned",
        "risk": "Requires high quality tick/orderbook data",
    },
    "finrl_crypto": {
        "role": "DRL research with walk-forward/PBO discipline",
        "adapter_status": "planned",
        "risk": "Research-to-production gap and overfitting",
    },
    "macrohft": {
        "role": "Memory-augmented regime-aware HFT RL reference",
        "adapter_status": "planned",
        "risk": "Research code, external datasets, no live hardening",
    },
    "webcryptoagent": {
        "role": "Agentic web/context reasoning and decoupled risk reference",
        "adapter_status": "planned",
        "risk": "LLM dependency, reproducibility, offline scope",
    },
    "vanta_network": {
        "role": "Bittensor-style validator/miner signal competition pattern",
        "adapter_status": "planned",
        "risk": "Tokenomics, plagiarism, drawdown elimination rules",
    },
}


class ResearchArchitectureRegistry:
    """Layer-1 registry for research-system integration state and evidence gates."""

    def __init__(self, cfg: Any, path: str | None = None):
        self.cfg = cfg
        self.path = path or getattr(cfg, "research_architecture_path", "config/research_architecture_layers.yaml")

    def snapshot(self) -> Dict[str, Any]:
        custom = self._load_custom()
        layers = custom.get("layers") or DEFAULT_LAYERS
        systems = dict(DEFAULT_SYSTEMS)
        systems.update(custom.get("systems") or {})
        return {
            "ts": time.time(),
            "version": 1,
            "active_layer": self.active_layer(layers),
            "layers": layers,
            "systems": systems,
            "evidence_policy": custom.get("evidence_policy") or self._default_evidence_policy(),
            "next_actions": custom.get("next_actions") or self._default_next_actions(),
        }

    def active_layer(self, layers: List[Dict[str, Any]]) -> Dict[str, Any]:
        for layer in layers:
            if str(layer.get("status") or "").lower() in ("active", "in_progress"):
                return layer
        return layers[0] if layers else {}

    def _load_custom(self) -> Dict[str, Any]:
        if not self.path or not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _default_evidence_policy(self) -> Dict[str, Any]:
        return {
            "profit_claims": "untrusted_until_reproduced",
            "live_promotion": "requires_dry_run_then_paper_then_tiny_live",
            "minimum_gates": [
                "walk_forward_or_retraining_backtest",
                "slippage_and_fee_model",
                "drawdown_limit",
                "queen_review",
                "swarmguard_pass",
            ],
        }

    def _default_next_actions(self) -> List[str]:
        return [
            "Expose registry in integration plane and UI",
            "Attach public-bot backtest records to evidence policy",
            "Add typed config/event spine before more live execution",
        ]
