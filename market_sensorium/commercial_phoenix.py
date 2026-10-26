from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .core import MarketSensoriumStore, canonical_json, digest_payload, stable_id, utc_now

HYPOTHESIS_TYPES = (
    "BUYER",
    "OFFER",
    "PRICE",
    "CHANNEL",
    "TIMING",
    "HABITAT",
    "COMPETITION",
    "PRODUCT",
    "PIVOT",
)


def _obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _arr(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _schema(store: MarketSensoriumStore) -> None:
    store.connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS commercial_hypothesis_sets (
          hypothesis_set_id TEXT PRIMARY KEY,
          transition_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          organisation TEXT NOT NULL,
          domain_id TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          rival_count INTEGER NOT NULL,
          selected_hypothesis_id TEXT,
          selected_hypothesis_type TEXT,
          selected_test_json TEXT NOT NULL,
          evidence_digest TEXT NOT NULL,
          world_state_digest TEXT NOT NULL,
          truth_state TEXT NOT NULL DEFAULT 'UNPROVED',
          authority_created INTEGER NOT NULL DEFAULT 0,
          market_demand_claimed INTEGER NOT NULL DEFAULT 0,
          external_effects INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS commercial_hypothesis_sets_target_idx
          ON commercial_hypothesis_sets(target_id, observed_at);

        CREATE TABLE IF NOT EXISTS commercial_hypotheses (
          hypothesis_id TEXT PRIMARY KEY,
          hypothesis_set_id TEXT NOT NULL,
          lineage_key TEXT NOT NULL,
          parent_hypothesis_id TEXT,
          transition_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          organisation TEXT NOT NULL,
          domain_id TEXT NOT NULL,
          hypothesis_type TEXT NOT NULL,
          statement TEXT NOT NULL,
          counter_explanation TEXT NOT NULL,
          research_priority_score REAL NOT NULL,
          michael_json TEXT NOT NULL,
          loki_json TEXT NOT NULL,
          metatron_json TEXT NOT NULL,
          bounded_test_json TEXT NOT NULL,
          evidence_refs_json TEXT NOT NULL,
          evidence_digest TEXT NOT NULL,
          world_state_digest TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          hypothesis_state TEXT NOT NULL DEFAULT 'ACTIVE_RESEARCH_HYPOTHESIS',
          truth_state TEXT NOT NULL DEFAULT 'UNPROVED',
          authority_created INTEGER NOT NULL DEFAULT 0,
          market_demand_claimed INTEGER NOT NULL DEFAULT 0,
          execution_performed INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS commercial_hypotheses_lineage_idx
          ON commercial_hypotheses(lineage_key, observed_at);
        CREATE INDEX IF NOT EXISTS commercial_hypotheses_transition_idx
          ON commercial_hypotheses(transition_id, hypothesis_type);
        """
    )
    store.connection.commit()


def _target_evidence(store: MarketSensoriumStore, target_id: str, limit: int = 12) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        """
        SELECT observation_id, observed_at, source_kind, source_ref, provenance_digest,
               entity_kind, entity_id
        FROM observations
        WHERE entity_id=?
        ORDER BY observed_at DESC, observation_id DESC
        LIMIT ?
        """,
        (target_id, int(limit)),
    ).fetchall()
    return [
        {
            "observation_id": row["observation_id"],
            "observed_at": row["observed_at"],
            "source_kind": row["source_kind"],
            "source_ref": row["source_ref"],
            "provenance_digest": row["provenance_digest"],
            "entity_kind": row["entity_kind"],
            "entity_id": row["entity_id"],
        }
        for row in rows
    ]


def _dedupe_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("observation_id") or ""),
            str(row.get("source_ref") or ""),
            str(row.get("provenance_digest") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _crossing_targets(crossings: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in (
        "passed_targets",
        "passed_by_targets",
        "new_entries_ahead",
        "prior_competitors_missing_ahead",
    ):
        for item in crossings.get(key) or []:
            if isinstance(item, dict) and item.get("target_id"):
                rows.append({"crossing_kind": key, **item})
    return rows


def _evidence_bundle(
    store: MarketSensoriumStore,
    transition: Any,
    crossings: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, int]:
    subject = _arr(transition["evidence_refs_json"])
    crossing_rows = _crossing_targets(crossings)
    crossing_evidence: list[dict[str, Any]] = []
    crossing_targets_with_evidence = 0
    for item in crossing_rows:
        rows = _target_evidence(store, str(item.get("target_id") or ""), limit=10)
        if rows:
            crossing_targets_with_evidence += 1
        for row in rows:
            crossing_evidence.append(
                {
                    **row,
                    "evidence_role": "RELATIVE_FIELD_ACTOR",
                    "crossing_kind": item.get("crossing_kind"),
                    "crossing_organisation": item.get("organisation"),
                }
            )
    subject_rows = [
        {**row, "evidence_role": "SUBJECT_TARGET"}
        for row in subject
        if isinstance(row, dict)
    ]
    evidence = _dedupe_evidence([*subject_rows, *crossing_evidence])
    source_units = {
        (
            str(row.get("source_kind") or ""),
            str(row.get("source_ref") or ""),
            str(row.get("provenance_digest") or ""),
        )
        for row in evidence
        if row.get("source_ref") and row.get("provenance_digest")
    }
    return evidence, len(source_units), crossing_targets_with_evidence


def _latest_parent(
    store: MarketSensoriumStore,
    lineage_key: str,
    current_transition_id: str,
) -> str | None:
    row = store.connection.execute(
        """
        SELECT hypothesis_id
        FROM commercial_hypotheses
        WHERE lineage_key=? AND transition_id<>?
        ORDER BY observed_at DESC, rowid DESC
        LIMIT 1
        """,
        (lineage_key, current_transition_id),
    ).fetchone()
    return str(row["hypothesis_id"]) if row else None


def _specs(
    *,
    organisation: str,
    domain_id: str,
    changes: list[dict[str, Any]],
    crossings: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    new_entries = list(crossings.get("new_entries_ahead") or [])
    passed_by = list(crossings.get("passed_by_targets") or [])
    relative = bool(
        new_entries
        or passed_by
        or crossings.get("passed_targets")
        or crossings.get("prior_competitors_missing_ahead")
    )
    source_kinds = {str(row.get("source_kind") or "") for row in evidence}
    has_public_habitat = any(
        any(token in kind.upper() for token in ("YOUTUBE", "RSS", "NEWS", "MARKET_SIGNAL", "DISCOVERY"))
        for kind in source_kinds
    )

    specs: list[dict[str, Any]] = []
    if relative:
        specs.append(
            {
                "type": "COMPETITION",
                "priority": 0.88 if new_entries else 0.76,
                "statement": (
                    f"The priority movement for {organisation} in {domain_id} may be explained by "
                    "a denser relative target field rather than deterioration in the incumbent target's evidence."
                ),
                "counter": "The field movement may be transient or caused by source visibility rather than durable commercial competition.",
                "test_kind": "TRACK_RELATIVE_FIELD_PERSISTENCE",
                "test": "Re-observe the same domain across later source-bound cycles and test whether the crossing organisations remain ahead without altering evidence or outreach state.",
            }
        )
    if new_entries:
        names = ", ".join(str(item.get("organisation") or item.get("target_id")) for item in new_entries[:3])
        specs.append(
            {
                "type": "BUYER",
                "priority": min(0.9, 0.72 + 0.05 * len(new_entries)),
                "statement": (
                    f"New organisation target hypotheses ({names}) may deserve deeper buyer-role research than the incumbent seed prior; "
                    "this does not establish a buyer unit or lead."
                ),
                "counter": "The new organisations may be contextually relevant actors without an applicable buyer role for any DIO offer.",
                "test_kind": "COMPARE_BUYER_ROLE_EVIDENCE",
                "test": "Collect independent public evidence for organisation function, likely workflow ownership and buyer-unit identity; keep buyer-unit verification unresolved unless explicit evidence appears.",
            }
        )
    specs.extend(
        [
            {
                "type": "TIMING",
                "priority": 0.60 + (0.05 if changes else 0.0),
                "statement": "The observed priority shift may be time-sensitive and may decay when fresh public signals age.",
                "counter": "The ordering may persist even after recency effects decay, indicating a more durable structural difference.",
                "test_kind": "REOBSERVE_AFTER_TIME_ELAPSES",
                "test": "Repeat read-only observation after a bounded interval and compare feature, score and rank transition receipts without manufacturing new signals.",
            },
            {
                "type": "CHANNEL",
                "priority": 0.56,
                "statement": "The current connected-source mix may overrepresent organisations that are unusually visible in those channels.",
                "counter": "Independent source families may reproduce the same ordering, reducing the channel-bias explanation.",
                "test_kind": "CROSS_SOURCE_CORROBORATION",
                "test": "Seek read-only corroboration from a distinct permitted public source family and compare entity identity, signal content and rank effects.",
            },
            {
                "type": "PRODUCT",
                "priority": 0.52 if not changes else 0.60,
                "statement": "The rank movement should not yet be interpreted as a change in product or offer fit; target priority and product preference are separate variables.",
                "counter": "Later workflow-specific evidence may show that target movement coincides with materially different capability fit.",
                "test_kind": "COMPARE_WORKFLOW_CAPABILITY_FIT",
                "test": "Compare source-bound workflow/problem evidence against the relevant DIO capability profile without contacting the organisation or claiming product-market fit.",
            },
        ]
    )
    if len(new_entries) >= 2 or len(passed_by) >= 2:
        specs.append(
            {
                "type": "PIVOT",
                "priority": 0.68,
                "statement": "If the newly elevated organisation cluster persists, the target-search frontier may warrant broadening beyond the original curated seed set.",
                "counter": "The cluster may disappear under broader evidence, making a pivot premature.",
                "test_kind": "MAP_ADJACENT_TARGET_CLUSTER",
                "test": "Expand read-only discovery around the observed organisation cluster and require independent entity resolution before admitting any additional target hypotheses.",
            }
        )
    if has_public_habitat:
        specs.append(
            {
                "type": "HABITAT",
                "priority": 0.54,
                "statement": "The signal may primarily describe a public information habitat rather than organisation-level commercial intent.",
                "counter": "Repeated organisation-specific evidence across habitats may weaken the habitat-only explanation.",
                "test_kind": "COMPARE_HABITAT_VS_ORGANISATION_SIGNAL",
                "test": "Separate habitat/source observations from organisation-specific observations and re-rank only with evidence that survives the entity-role boundary.",
            }
        )
    return specs


def _triune(
    *,
    hypothesis_type: str,
    priority: float,
    evidence: list[dict[str, Any]],
    source_diversity: int,
    crossing_targets: int,
    transition_kind: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validation = min(
        0.96,
        0.42
        + min(0.24, source_diversity * 0.04)
        + (0.12 if evidence else 0.0)
        + (0.08 if crossing_targets else 0.0)
        + (0.06 if transition_kind != "UNEXPLAINED_RANK_MOVEMENT" else 0.0),
    )
    michael = {
        "role": "MICHAEL_VALIDATOR",
        "validation_score": round(validation, 6),
        "evidence_refs": len(evidence),
        "source_units": source_diversity,
        "crossing_targets_with_evidence": crossing_targets,
        "admission": "ADMISSIBLE_FOR_RESEARCH" if evidence and transition_kind != "UNEXPLAINED_RANK_MOVEMENT" else "WITHHOLD",
        "authority": "research_validation_only",
    }
    challenges = [
        "rank_change_is_not_market_demand",
        "new_target_hypothesis_is_not_verified_buyer_unit",
        "source_visibility_may_not_generalise_across_channels",
    ]
    if hypothesis_type in {"COMPETITION", "PIVOT"}:
        challenges.append("seed_displacement_is_not_market_share")
    if hypothesis_type == "BUYER":
        challenges.append("organisation_identity_does_not_prove_buyer_role")
    if hypothesis_type == "PRODUCT":
        challenges.append("target_priority_does_not_prove_product_preference")
    loki = {
        "role": "LOKI_ADVERSARY",
        "challenges": challenges,
        "alternative_explanation_required": True,
        "truth_claim_refused": True,
        "authority": "adversarial_research_only",
    }
    synthesis = max(0.0, min(1.0, float(priority) * 0.58 + validation * 0.42 - 0.06))
    metatron = {
        "role": "METATRON_SYNTHESIS",
        "research_priority_score": round(synthesis, 6),
        "verdict": "ADMIT_BOUNDED_RESEARCH_TEST" if michael["admission"] == "ADMISSIBLE_FOR_RESEARCH" else "HOLD",
        "hypothesis_truth_state": "UNPROVED",
        "authority": "research_routing_only",
    }
    return michael, loki, metatron


def run_commercial_phoenix(store: MarketSensoriumStore) -> dict[str, Any]:
    """Generate rival, source-bound commercial explanations for the latest real rank movement.

    This is a Hivenance-style research engine. It proposes read-only tests only. It
    never promotes a hypothesis into market truth, buyer verification, demand,
    outreach permission, publication authority, spend authority or commerce.
    """
    _schema(store)
    latest = store.connection.execute(
        "SELECT MAX(observed_at) AS observed_at FROM rank_transitions WHERE rank_delta IS NOT NULL AND rank_delta<>0"
    ).fetchone()
    observed_at = str(latest["observed_at"] or "") if latest else ""
    if not observed_at:
        return {
            "schema": "dio.market_sensorium.hivenance_commercial_phoenix.v2",
            "observed_at": None,
            "movement_events_examined": 0,
            "hypothesis_sets_created": 0,
            "hypotheses_created": 0,
            "selected_bounded_tests": 0,
            "truth_claims_created": 0,
            "authority_created": False,
            "external_effects": False,
        }

    transitions = store.connection.execute(
        """
        SELECT * FROM rank_transitions
        WHERE observed_at=? AND rank_delta IS NOT NULL AND rank_delta<>0
        ORDER BY ABS(rank_delta) DESC, domain_id, current_rank, target_id
        """,
        (observed_at,),
    ).fetchall()
    counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for transition in transitions:
        counts["movement_events_examined"] += 1
        changes = _arr(transition["feature_changes_json"])
        crossings = _obj(transition["relative_crossings_json"])
        evidence, source_diversity, crossing_targets = _evidence_bundle(store, transition, crossings)
        evidence_digest = digest_payload(evidence)
        world_state_digest = str(transition["world_state_digest"] or "")
        specs = _specs(
            organisation=str(transition["organisation"]),
            domain_id=str(transition["domain_id"]),
            changes=changes,
            crossings=crossings,
            evidence=evidence,
        )
        set_id = stable_id(
            "CHSET",
            transition["transition_id"],
            evidence_digest,
            world_state_digest,
        )
        candidates: list[dict[str, Any]] = []
        for spec in specs:
            hypothesis_type = str(spec["type"])
            if hypothesis_type not in HYPOTHESIS_TYPES:
                continue
            lineage_key = stable_id(
                "CHLINE",
                transition["target_id"],
                transition["domain_id"],
                hypothesis_type,
            )
            parent_id = _latest_parent(store, lineage_key, str(transition["transition_id"]))
            michael, loki, metatron = _triune(
                hypothesis_type=hypothesis_type,
                priority=float(spec["priority"]),
                evidence=evidence,
                source_diversity=source_diversity,
                crossing_targets=crossing_targets,
                transition_kind=str(transition["transition_kind"]),
            )
            bounded_test = {
                "test_kind": spec["test_kind"],
                "instruction": spec["test"],
                "mode": "READ_ONLY_OBSERVATION_OR_RESEARCH",
                "requires_operator_release": False,
                "outreach_permitted": False,
                "publication_permitted": False,
                "spend_permitted": False,
                "join_or_dm_permitted": False,
                "commerce_permitted": False,
                "external_effects": False,
                "authority_created": False,
            }
            hypothesis_id = stable_id(
                "CHYP",
                transition["transition_id"],
                hypothesis_type,
                evidence_digest,
                world_state_digest,
            )
            score = float(metatron["research_priority_score"])
            row = {
                "hypothesis_id": hypothesis_id,
                "hypothesis_set_id": set_id,
                "lineage_key": lineage_key,
                "parent_hypothesis_id": parent_id,
                "transition_id": str(transition["transition_id"]),
                "target_id": str(transition["target_id"]),
                "organisation": str(transition["organisation"]),
                "domain_id": str(transition["domain_id"]),
                "hypothesis_type": hypothesis_type,
                "statement": spec["statement"],
                "counter_explanation": spec["counter"],
                "research_priority_score": score,
                "michael": michael,
                "loki": loki,
                "metatron": metatron,
                "bounded_test": bounded_test,
                "evidence_refs": evidence,
                "evidence_digest": evidence_digest,
                "world_state_digest": world_state_digest,
                "observed_at": observed_at,
                "hypothesis_state": "ACTIVE_RESEARCH_HYPOTHESIS",
                "truth_state": "UNPROVED",
                "market_demand_claimed": False,
                "authority_created": False,
            }
            candidates.append(row)
            store.connection.execute(
                """
                INSERT OR REPLACE INTO commercial_hypotheses (
                  hypothesis_id,hypothesis_set_id,lineage_key,parent_hypothesis_id,
                  transition_id,target_id,organisation,domain_id,hypothesis_type,
                  statement,counter_explanation,research_priority_score,michael_json,
                  loki_json,metatron_json,bounded_test_json,evidence_refs_json,
                  evidence_digest,world_state_digest,observed_at,hypothesis_state,
                  truth_state,authority_created,market_demand_claimed,execution_performed
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0)
                """,
                (
                    hypothesis_id,
                    set_id,
                    lineage_key,
                    parent_id,
                    transition["transition_id"],
                    transition["target_id"],
                    transition["organisation"],
                    transition["domain_id"],
                    hypothesis_type,
                    spec["statement"],
                    spec["counter"],
                    score,
                    canonical_json(michael),
                    canonical_json(loki),
                    canonical_json(metatron),
                    canonical_json(bounded_test),
                    canonical_json(evidence),
                    evidence_digest,
                    world_state_digest,
                    observed_at,
                    "ACTIVE_RESEARCH_HYPOTHESIS",
                    "UNPROVED",
                ),
            )
            counts["hypotheses_created"] += 1
            type_counts[hypothesis_type] += 1
            if evidence:
                counts["source_bound_hypotheses"] += 1
            if michael.get("admission") == "ADMISSIBLE_FOR_RESEARCH":
                counts["michael_validated_hypotheses"] += 1
            if loki.get("truth_claim_refused"):
                counts["loki_challenged_hypotheses"] += 1
            if metatron.get("verdict") == "ADMIT_BOUNDED_RESEARCH_TEST":
                counts["metatron_synthesized_hypotheses"] += 1
            if parent_id:
                counts["lineage_revisions"] += 1

        admitted = [
            row for row in candidates
            if row["metatron"].get("verdict") == "ADMIT_BOUNDED_RESEARCH_TEST"
        ]
        admitted.sort(
            key=lambda row: (
                -float(row["research_priority_score"]),
                str(row["hypothesis_type"]),
            )
        )
        selected = admitted[0] if admitted else None
        selected_test = selected["bounded_test"] if selected else {
            "test_kind": "HOLD",
            "mode": "READ_ONLY_OBSERVATION_OR_RESEARCH",
            "external_effects": False,
            "authority_created": False,
        }
        store.connection.execute(
            """
            INSERT OR REPLACE INTO commercial_hypothesis_sets (
              hypothesis_set_id,transition_id,target_id,organisation,domain_id,
              observed_at,rival_count,selected_hypothesis_id,selected_hypothesis_type,
              selected_test_json,evidence_digest,world_state_digest,truth_state,
              authority_created,market_demand_claimed,external_effects
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'UNPROVED',0,0,0)
            """,
            (
                set_id,
                transition["transition_id"],
                transition["target_id"],
                transition["organisation"],
                transition["domain_id"],
                observed_at,
                len(candidates),
                selected["hypothesis_id"] if selected else None,
                selected["hypothesis_type"] if selected else None,
                canonical_json(selected_test),
                evidence_digest,
                world_state_digest,
            ),
        )
        counts["hypothesis_sets_created"] += 1
        if len(candidates) >= 3:
            counts["rival_sets_with_3plus"] += 1
        if selected:
            counts["selected_bounded_tests"] += 1
        if selected_test.get("external_effects") or selected_test.get("authority_created"):
            counts["unbounded_or_authority_tests"] += 1
        if not evidence:
            counts["sets_without_source_evidence"] += 1

        examples.append(
            {
                "hypothesis_set_id": set_id,
                "transition_id": transition["transition_id"],
                "organisation": transition["organisation"],
                "domain_id": transition["domain_id"],
                "transition_kind": transition["transition_kind"],
                "rank_move": f"{transition['previous_rank']}->{transition['current_rank']}",
                "rival_count": len(candidates),
                "hypothesis_types": [row["hypothesis_type"] for row in candidates],
                "selected_hypothesis_type": selected["hypothesis_type"] if selected else None,
                "selected_research_priority_score": selected["research_priority_score"] if selected else None,
                "selected_test_kind": selected_test.get("test_kind"),
                "source_units": source_diversity,
                "crossing_targets_with_evidence": crossing_targets,
                "truth_state": "UNPROVED",
                "market_demand_claimed": False,
                "authority_created": False,
            }
        )

    store.connection.commit()
    persisted_hypotheses = store.connection.execute(
        "SELECT COUNT(*) FROM commercial_hypotheses"
    ).fetchone()[0]
    persisted_sets = store.connection.execute(
        "SELECT COUNT(*) FROM commercial_hypothesis_sets"
    ).fetchone()[0]
    return {
        "schema": "dio.market_sensorium.hivenance_commercial_phoenix.v2",
        "observed_at": observed_at,
        **dict(sorted(counts.items())),
        "hypothesis_type_counts": dict(sorted(type_counts.items())),
        "hypothesis_types_supported": list(HYPOTHESIS_TYPES),
        "rival_hypotheses_required": True,
        "hypothesis_is_fact": False,
        "selected_hypothesis_is_truth": False,
        "selected_test_is_execution_authority": False,
        "truth_claims_created": 0,
        "persisted_hypothesis_count": int(persisted_hypotheses),
        "persisted_hypothesis_set_count": int(persisted_sets),
        "examples": examples[:10],
        "market_demand_claimed": False,
        "best_target_claimed": False,
        "buyer_unit_verified_by_hypothesis": False,
        "outreach_authority_created": False,
        "publication_authority_created": False,
        "spend_authority_created": False,
        "commerce_authority_created": False,
        "authority_created": False,
        "external_effects": False,
    }


def install_commercial_phoenix_runtime(store_class: type[MarketSensoriumStore]) -> None:
    """Wrap the installed rank runtime so MS-4 runs after MS-3 transitions exist."""
    if getattr(store_class, "_ms4_runtime_installed", False):
        return
    original_rank = store_class.rank
    original_summary = store_class.summary

    def rank(self, features, observed_at=None):
        receipts = original_rank(self, features, observed_at=observed_at)
        self._last_ms4_phoenix_summary = run_commercial_phoenix(self)
        return receipts

    def summary(self):
        payload = original_summary(self)
        payload["commercial_phoenix"] = getattr(
            self,
            "_last_ms4_phoenix_summary",
            {
                "schema": "dio.market_sensorium.hivenance_commercial_phoenix.v2",
                "movement_events_examined": 0,
                "hypothesis_sets_created": 0,
                "hypotheses_created": 0,
                "authority_created": False,
                "external_effects": False,
            },
        )
        return payload

    store_class.rank = rank
    store_class.summary = summary
    store_class._ms4_runtime_installed = True
