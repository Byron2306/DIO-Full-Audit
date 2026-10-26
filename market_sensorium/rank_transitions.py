from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from typing import Any, Iterable

from .core import DEFAULT_WEIGHTS, MarketSensoriumStore, RankReceipt, TargetFeatures, canonical_json, digest_payload, stable_id

POSITIVE = tuple(DEFAULT_WEIGHTS)
PENALTIES = ("silence_penalty", "rejection_penalty", "authority_penalty", "stale_signal_penalty")
NUMERIC = POSITIVE + PENALTIES


def _obj(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _schema(store: MarketSensoriumStore) -> None:
    store.connection.executescript("""
    CREATE TABLE IF NOT EXISTS rank_transitions (
      transition_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, organisation TEXT NOT NULL,
      domain_id TEXT NOT NULL, transition_kind TEXT NOT NULL, previous_rank INTEGER,
      current_rank INTEGER NOT NULL, rank_delta INTEGER, previous_score REAL,
      current_score REAL NOT NULL, score_delta REAL, previous_rank_receipt_id TEXT,
      current_rank_receipt_id TEXT NOT NULL, previous_feature_digest TEXT,
      current_feature_digest TEXT NOT NULL, previous_features_json TEXT NOT NULL,
      current_features_json TEXT NOT NULL, feature_changes_json TEXT NOT NULL,
      relative_crossings_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
      evidence_digest TEXT NOT NULL, world_state_digest TEXT NOT NULL,
      explanation_factors_json TEXT NOT NULL, observed_at TEXT NOT NULL,
      history_preserved INTEGER NOT NULL DEFAULT 1, authority_created INTEGER NOT NULL DEFAULT 0,
      market_demand_claimed INTEGER NOT NULL DEFAULT 0, execution_performed INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS rank_transitions_target_idx ON rank_transitions(target_id, observed_at);
    CREATE INDEX IF NOT EXISTS rank_transitions_domain_idx ON rank_transitions(domain_id, observed_at);
    """)
    store.connection.commit()


def capture_rank_snapshot(store: MarketSensoriumStore, features: Iterable[TargetFeatures]) -> dict[str, Any]:
    domains = sorted({item.domain_id for item in features})
    out: dict[str, Any] = {"schema": "dio.market_sensorium.rank_snapshot.v1", "targets": {}, "domains": {}, "authority_created": False}
    if not domains:
        return out
    q = ",".join("?" for _ in domains)
    rows = store.connection.execute(
        f"SELECT * FROM target_memory WHERE domain_id IN ({q}) ORDER BY domain_id, current_rank, target_id", domains
    ).fetchall()
    for row in rows:
        tid = str(row["target_id"])
        meta = _obj(row["metadata_json"])
        prior = store.connection.execute(
            "SELECT receipt_id, observed_at FROM rank_receipts WHERE target_id=? ORDER BY observed_at DESC, rowid DESC LIMIT 1", (tid,)
        ).fetchone()
        out["targets"][tid] = {
            "rank": row["current_rank"], "score": row["current_score"], "metadata": meta,
            "features": meta.get("rank_features") if isinstance(meta.get("rank_features"), dict) else {},
            "rank_receipt_id": prior["receipt_id"] if prior else None,
            "rank_observed_at": prior["observed_at"] if prior else None,
        }
        if row["current_rank"] is not None:
            out["domains"].setdefault(str(row["domain_id"]), []).append({
                "target_id": tid, "organisation": row["organisation"], "rank": row["current_rank"], "score": row["current_score"]
            })
    return out


def _changes(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for name in NUMERIC:
        try:
            before, after = float(previous.get(name, 0)), float(current.get(name, 0))
        except (TypeError, ValueError):
            continue
        delta = round(after - before, 6)
        if abs(delta) < 0.000001:
            continue
        effect = round(delta * DEFAULT_WEIGHTS.get(name, 0), 6) if name in POSITIVE else round(-delta, 6)
        result.append({"feature": name, "previous": round(before, 6), "current": round(after, 6), "delta": delta,
                       "score_effect": effect, "score_direction": "UP" if effect > 0 else "DOWN"})
    return sorted(result, key=lambda x: (-abs(float(x["score_effect"])), x["feature"]))


def _evidence(store: MarketSensoriumStore, target_id: str) -> list[dict[str, Any]]:
    rows = store.connection.execute("""
      SELECT observation_id, observed_at, source_kind, source_ref, provenance_digest, entity_kind
      FROM observations WHERE entity_id=? ORDER BY observed_at DESC, observation_id DESC LIMIT 24
    """, (target_id,)).fetchall()
    return [{k: row[k] for k in ("observation_id", "observed_at", "source_kind", "source_ref", "provenance_digest", "entity_kind")} for row in rows]


def _current_domains(receipts: list[RankReceipt]) -> dict[str, list[dict[str, Any]]]:
    out: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in receipts:
        out[r.domain_id].append({"target_id": r.target_id, "organisation": r.organisation, "rank": r.current_rank, "score": r.score})
    for rows in out.values():
        rows.sort(key=lambda x: (int(x["rank"]), str(x["target_id"])))
    return dict(out)


def _crossings(target_id: str, previous_rank: int | None, current_rank: int, prior: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    p, c = {str(x["target_id"]): x for x in prior}, {str(x["target_id"]): x for x in current}
    passed, passed_by, new_ahead, missing_ahead = [], [], [], []
    if previous_rank is not None:
        for oid, old in p.items():
            if oid == target_id:
                continue
            new = c.get(oid)
            if new is None:
                if int(old["rank"]) < previous_rank:
                    missing_ahead.append({"target_id": oid, "organisation": old["organisation"], "previous_rank": old["rank"]})
                continue
            if int(old["rank"]) < previous_rank and int(new["rank"]) > current_rank:
                passed.append({"target_id": oid, "organisation": new["organisation"], "previous_rank": old["rank"], "current_rank": new["rank"]})
            if int(old["rank"]) > previous_rank and int(new["rank"]) < current_rank:
                passed_by.append({"target_id": oid, "organisation": new["organisation"], "previous_rank": old["rank"], "current_rank": new["rank"]})
        for oid, new in c.items():
            if oid != target_id and oid not in p and int(new["rank"]) < current_rank:
                new_ahead.append({"target_id": oid, "organisation": new["organisation"], "current_rank": new["rank"]})
    return {"passed_targets": passed, "passed_by_targets": passed_by, "new_entries_ahead": new_ahead,
            "prior_competitors_missing_ahead": missing_ahead, "prior_field_size": len(prior), "current_field_size": len(current)}


def _kind(previous_rank: int | None, rank_delta: int | None, score_delta: float | None, changes: list[dict[str, Any]], crossings: dict[str, Any]) -> str:
    if previous_rank is None:
        return "INITIAL_RANK_ENTRY"
    moved = rank_delta not in {None, 0}
    score_moved = score_delta is not None and abs(float(score_delta)) >= 0.000001
    relative = any(crossings[k] for k in ("passed_targets", "passed_by_targets", "new_entries_ahead", "prior_competitors_missing_ahead"))
    if moved and changes and relative:
        return "FEATURE_AND_RELATIVE_FIELD_MOVEMENT"
    if moved and changes:
        return "FEATURE_DRIVEN_RANK_MOVEMENT"
    if moved and relative:
        return "RELATIVE_FIELD_RANK_MOVEMENT"
    if moved and score_moved:
        return "SCORE_DRIVEN_RANK_MOVEMENT"
    if moved:
        return "UNEXPLAINED_RANK_MOVEMENT"
    if changes or score_moved:
        return "SCORE_OR_FEATURE_CHANGE_RANK_STABLE"
    return "NO_MATERIAL_CHANGE"


def _factors(changes: list[dict[str, Any]], crossings: dict[str, Any], rank_delta: int | None) -> list[str]:
    out = [f"{x['feature']}_{'increase' if x['delta'] > 0 else 'decrease'}:score_effect={x['score_effect']:+.6f}" for x in changes]
    labels = (("passed_targets", "passed_targets"), ("passed_by_targets", "passed_by_targets"),
              ("new_entries_ahead", "new_entries_ahead"), ("prior_competitors_missing_ahead", "prior_competitors_missing_ahead"))
    out.extend(f"{label}:{len(crossings[key])}" for key, label in labels if crossings[key])
    if rank_delta not in {None, 0} and not out:
        return ["UNEXPLAINED_RANK_MOVEMENT"]
    return out or ["NO_MATERIAL_CHANGE"]


def _restore_metadata(store: MarketSensoriumStore, target_id: str, prior: dict[str, Any]) -> None:
    row = store.connection.execute("SELECT metadata_json FROM target_memory WHERE target_id=?", (target_id,)).fetchone()
    if row is None:
        return
    merged = dict(prior); merged.update(_obj(row["metadata_json"]))
    store.connection.execute("UPDATE target_memory SET metadata_json=? WHERE target_id=?", (canonical_json(merged), target_id))


def _ledger(store: MarketSensoriumStore) -> dict[str, Any]:
    rows = store.connection.execute("SELECT observation_id, provenance_digest FROM observations ORDER BY observation_id").fetchall()
    payload = [{"observation_id": x["observation_id"], "provenance_digest": x["provenance_digest"]} for x in rows]
    return {"count": len(payload), "digest": digest_payload(payload)}


def record_rank_transitions(store: MarketSensoriumStore, *, prior_snapshot: dict[str, Any], features: Iterable[TargetFeatures], rank_receipts: Iterable[RankReceipt], observed_at: str) -> dict[str, Any]:
    _schema(store)
    features_by_id = {x.target_id: x for x in features}
    receipts = list(rank_receipts)
    current_domains, prior_targets, prior_domains = _current_domains(receipts), prior_snapshot.get("targets") or {}, prior_snapshot.get("domains") or {}
    counts: defaultdict[str, int] = defaultdict(int); examples = []
    for r in receipts:
        old = prior_targets.get(r.target_id) or {}
        if isinstance(old.get("metadata"), dict):
            _restore_metadata(store, r.target_id, old["metadata"])
        feature = features_by_id.get(r.target_id)
        if feature is None:
            continue
        current = asdict(feature); previous = old.get("features") if isinstance(old.get("features"), dict) else {}
        changes = _changes(previous, current) if previous else []
        crossings = _crossings(r.target_id, r.previous_rank, r.current_rank, list(prior_domains.get(r.domain_id) or []), list(current_domains.get(r.domain_id) or []))
        kind, evidence = _kind(r.previous_rank, r.rank_delta, r.score_delta, changes, crossings), _evidence(store, r.target_id)
        factors = _factors(changes, crossings, r.rank_delta)
        prev_digest, cur_digest, evidence_digest = (digest_payload(previous) if previous else None), digest_payload(current), digest_payload(evidence)
        world_digest = digest_payload({"target_id": r.target_id, "domain_id": r.domain_id, "features": current, "evidence_digest": evidence_digest})
        transition_id = stable_id("RTRANS", r.target_id, old.get("rank_receipt_id") or "NONE", r.receipt_id, prev_digest or "NONE", cur_digest, evidence_digest)
        store.connection.execute("""
          INSERT OR REPLACE INTO rank_transitions (
            transition_id,target_id,organisation,domain_id,transition_kind,previous_rank,current_rank,rank_delta,
            previous_score,current_score,score_delta,previous_rank_receipt_id,current_rank_receipt_id,
            previous_feature_digest,current_feature_digest,previous_features_json,current_features_json,
            feature_changes_json,relative_crossings_json,evidence_refs_json,evidence_digest,world_state_digest,
            explanation_factors_json,observed_at,history_preserved,authority_created,market_demand_claimed,execution_performed
          ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0,0,0)
        """, (transition_id,r.target_id,r.organisation,r.domain_id,kind,r.previous_rank,r.current_rank,r.rank_delta,
               r.previous_score,r.score,r.score_delta,old.get("rank_receipt_id"),r.receipt_id,prev_digest,cur_digest,
               canonical_json(previous),canonical_json(current),canonical_json(changes),canonical_json(crossings),
               canonical_json(evidence),evidence_digest,world_digest,canonical_json(factors),observed_at))
        counts["transitions_recorded"] += 1; counts[f"kind_{kind}"] += 1
        if r.previous_rank is not None: counts["historical_transitions"] += 1
        if r.rank_delta not in {None, 0}: counts["rank_movement_transitions"] += 1
        if changes: counts["feature_changed_transitions"] += 1
        if evidence:
            counts["evidence_bound_transitions"] += 1
            if r.rank_delta not in {None, 0}: counts["rank_movement_evidence_bound_transitions"] += 1
        if kind == "UNEXPLAINED_RANK_MOVEMENT": counts["unexplained_rank_movements"] += 1
        if r.previous_rank is not None and old.get("rank_receipt_id"): counts["prior_rank_receipt_bound"] += 1
        if r.rank_delta not in {None, 0}:
            examples.append({"transition_id":transition_id,"target_id":r.target_id,"organisation":r.organisation,"domain_id":r.domain_id,
              "transition_kind":kind,"previous_rank":r.previous_rank,"current_rank":r.current_rank,"rank_delta":r.rank_delta,
              "previous_score":r.previous_score,"current_score":r.score,"score_delta":r.score_delta,"feature_changes":changes[:8],
              "relative_crossings":crossings,"evidence_refs":evidence[:8],"explanation_factors":factors,
              "previous_rank_receipt_id":old.get("rank_receipt_id"),"current_rank_receipt_id":r.receipt_id,
              "history_preserved":True,"market_demand_claimed":False,"authority_created":False})
    store.connection.commit()
    examples.sort(key=lambda x:(-abs(int(x.get("rank_delta") or 0)),str(x.get("domain_id") or ""),int(x.get("current_rank") or 0)))
    historical, prior_bound = int(counts.get("historical_transitions",0)), int(counts.get("prior_rank_receipt_bound",0))
    return {"schema":"dio.market_sensorium.dynamic_rank_movement.v1","observed_at":observed_at,**dict(sorted(counts.items())),
      "rank_movement_observed":int(counts.get("rank_movement_transitions",0))>0,"history_preserved":historical==0 or prior_bound==historical,
      "rank_learning_mutated_evidence":False,"evidence_source_bound":True,"unexplained_rank_movements":int(counts.get("unexplained_rank_movements",0)),
      "examples":examples[:20],"market_demand_claimed":False,"best_target_claimed":False,"authority_created":False,"external_effects":False}


def install_rank_transition_runtime(store_class: type[MarketSensoriumStore]) -> None:
    if getattr(store_class, "_ms3_runtime_installed", False):
        return
    original_rank, original_summary = store_class.rank, store_class.summary
    def rank(self, features, observed_at=None):
        rows = list(features); prior = capture_rank_snapshot(self, rows); before = _ledger(self)
        receipts = original_rank(self, rows, observed_at=observed_at); timestamp = receipts[0].observed_at if receipts else str(observed_at or "")
        result = record_rank_transitions(self, prior_snapshot=prior, features=rows, rank_receipts=receipts, observed_at=timestamp)
        after = _ledger(self); self._ms3_summary = {**result,"evidence_ledger_before":before,"evidence_ledger_after":after,"rank_learning_mutated_evidence":before!=after}
        return receipts
    def summary(self):
        result = original_summary(self); _schema(self); current = getattr(self,"_ms3_summary",None)
        if current is None:
            current={"schema":"dio.market_sensorium.dynamic_rank_movement.v1","transitions_recorded":0,"rank_movement_transitions":0,
              "rank_movement_observed":False,"history_preserved":True,"rank_learning_mutated_evidence":False,"evidence_source_bound":True,
              "unexplained_rank_movements":0,"examples":[],"market_demand_claimed":False,"authority_created":False}
        count=int(self.connection.execute("SELECT COUNT(*) FROM rank_transitions").fetchone()[0]); result["rank_transitions"]={**current,"persisted_transition_count":count}; return result
    store_class.rank, store_class.summary, store_class._ms3_runtime_installed = rank, summary, True
