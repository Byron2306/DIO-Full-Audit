#!/usr/bin/env python3
"""Update symbol memory stages from recent paper/live trade stats."""

import argparse
import json
import os
import sqlite3
from collections import defaultdict


STAGES = ("paper", "tiny_live", "normal")


def next_stage(stage):
    try:
        idx = STAGES.index(stage)
    except ValueError:
        return "paper"
    return STAGES[min(idx + 1, len(STAGES) - 1)]


def load_memory(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    return {}


def promote(db_path, memory_path, min_trades, min_win_rate, max_drawdown):
    memory = load_memory(memory_path)
    stats = defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT symbol, side, quantity, price FROM trades ORDER BY timestamp ASC").fetchall()
        except sqlite3.Error:
            rows = []
        inventory = defaultdict(lambda: {"qty": 0.0, "cost": 0.0})
        for row in rows:
            symbol = (row["symbol"] or "").upper()
            if not symbol:
                continue
            base = symbol.split("/")[0]
            side = (row["side"] or "").upper()
            qty = float(row["quantity"] or 0)
            price = float(row["price"] or 0)
            if qty <= 0 or price <= 0:
                continue
            stats[base]["trades"] += 1
            inv = inventory[base]
            if side == "BUY":
                inv["cost"] += qty * price
                inv["qty"] += qty
            elif side == "SELL" and inv["qty"] > 0:
                avg = inv["cost"] / inv["qty"] if inv["qty"] else price
                pnl = (price - avg) * min(qty, inv["qty"])
                stats[base]["pnl"] += pnl
                if pnl > 0:
                    stats[base]["wins"] += 1
                else:
                    stats[base]["losses"] += 1
                inv["qty"] = max(0.0, inv["qty"] - qty)
                inv["cost"] = max(0.0, inv["cost"] - avg * qty)

    for base, s in stats.items():
        sells = s["wins"] + s["losses"]
        win_rate = (s["wins"] / sells) if sells else 0.5
        current = memory.setdefault(base, {})
        current["win_rate"] = round(win_rate, 4)
        current.setdefault("avg_slippage_pct", 0.0)
        current.setdefault("rejects_24h", 0)
        current.setdefault("max_drawdown_pct", 0.0)
        current.setdefault("stage", "paper")
        if s["trades"] >= min_trades and win_rate >= min_win_rate and float(current.get("max_drawdown_pct") or 0.0) <= max_drawdown:
            current["stage"] = next_stage(current.get("stage", "paper"))
        current["last_eval"] = {
            "trades": s["trades"],
            "wins": s["wins"],
            "losses": s["losses"],
            "pnl_est": round(s["pnl"], 8),
        }

    os.makedirs(os.path.dirname(memory_path) or ".", exist_ok=True)
    with open(memory_path, "w") as f:
        json.dump(memory, f, indent=2, sort_keys=True)
    print(f"wrote {memory_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/swarm_data.db")
    parser.add_argument("--memory", default="data/symbol_memory.json")
    parser.add_argument("--min-trades", type=int, default=25)
    parser.add_argument("--min-win-rate", type=float, default=0.52)
    parser.add_argument("--max-drawdown", type=float, default=5.0)
    args = parser.parse_args()
    promote(args.db, args.memory, args.min_trades, args.min_win_rate, args.max_drawdown)


if __name__ == "__main__":
    main()
