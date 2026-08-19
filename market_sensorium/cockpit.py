from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .core import MarketSensoriumStore, canonical_json, digest_payload, stable_id, utc_now

MS7_VERIFIED = "DIO_MARKET_SENSORIUM_LEARNED_DISCOVERY_QUERIES_VERIFIED"
MS2_ACTIVE_STATES = {
    "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE",
    "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_AND_REPLY_TRUTH_VERIFIED",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_rows(store: MarketSensoriumStore, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    try:
        return store.connection.execute(sql, params).fetchall()
    except Exception:
        return []


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


def _phase_status(root: Path) -> dict[str, Any]:
    state_root = root / "state" / "market_sensorium"
    cycle = _read_json(state_root / "MARKET_SENSORIUM_CYCLE_RECEIPT.json")
    phases: dict[str, Any] = {}
    for number in range(1, 8):
        key = f"ms{number}_acceptance"
        specific = _read_json(state_root / f"MARKET_SENSORIUM_MS{number}_RECEIPT.json")
        value = specific.get(key) or cycle.get(key) or "UNAVAILABLE"
        truth = specific.get(f"ms{number}_truth") or cycle.get(f"ms{number}_truth") or {}
        phases[f"MS-{number}"] = {
            "acceptance": value,
            "truth_class": "VERIFIED_CAPABILITY" if "VERIFIED" in str(value) else (
                "ACTIVE_OBSERVATION" if "OBSERVATION_ACTIVE" in str(value) else "PENDING_OR_REFUSED"
            ),
            "truth": truth,
        }
    return phases


def _ranked_targets(store: MarketSensoriumStore, limit: int = 30) -> list[dict[str, Any]]:
    rows = _safe_rows(
        store,
        """
        SELECT target_id, organisation, domain_id, current_rank, current_score,
               previous_rank, previous_score, reply_state, consent_state,
               silence_state, silence_penalty, next_recommended_action,
               metadata_json, updated_at
        FROM target_memory
        WHERE current_rank IS NOT NULL
        ORDER BY current_score DESC, domain_id, current_rank, target_id
        LIMIT ?
        """,
        (int(limit),),
    )
    result = []
    for row in rows:
        metadata = _obj(row["metadata_json"])
        result.append({
            "target_id": row["target_id"],
            "organisation": row["organisation"],
            "domain_id": row["domain_id"],
            "current_rank": row["current_rank"],
            "current_score": row["current_score"],
            "previous_rank": row["previous_rank"],
            "previous_score": row["previous_score"],
            "reply_state": row["reply_state"],
            "consent_state": row["consent_state"],
            "silence_state": row["silence_state"],
            "silence_penalty": row["silence_penalty"],
            "next_recommended_action": row["next_recommended_action"],
            "buyer_unit": metadata.get("buyer_unit"),
            "identity_state": metadata.get("identity_state") or metadata.get("resolution_state"),
            "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
            "best_target_claimed": False,
            "market_demand_claimed": False,
            "authority_created": False,
            "updated_at": row["updated_at"],
        })
    return result


def _rank_movements(store: MarketSensoriumStore, limit: int = 20) -> list[dict[str, Any]]:
    rows = _safe_rows(
        store,
        """
        SELECT transition_id,target_id,organisation,domain_id,transition_kind,
               previous_rank,current_rank,rank_delta,previous_score,current_score,
               score_delta,evidence_digest,world_state_digest,explanation_factors_json,
               relative_crossings_json,observed_at,history_preserved,authority_created,
               market_demand_claimed
        FROM rank_transitions
        WHERE rank_delta IS NOT NULL AND rank_delta<>0
        ORDER BY observed_at DESC, ABS(rank_delta) DESC, domain_id, current_rank
        LIMIT ?
        """,
        (int(limit),),
    )
    return [
        {
            "transition_id": row["transition_id"],
            "target_id": row["target_id"],
            "organisation": row["organisation"],
            "domain_id": row["domain_id"],
            "transition_kind": row["transition_kind"],
            "previous_rank": row["previous_rank"],
            "current_rank": row["current_rank"],
            "rank_delta": row["rank_delta"],
            "previous_score": row["previous_score"],
            "current_score": row["current_score"],
            "score_delta": row["score_delta"],
            "explanation_factors": _arr(row["explanation_factors_json"]),
            "relative_crossings": _obj(row["relative_crossings_json"]),
            "evidence_digest": row["evidence_digest"],
            "world_state_digest": row["world_state_digest"],
            "truth_class": "OBSERVED_RANK_TRANSITION",
            "history_preserved": bool(row["history_preserved"]),
            "market_demand_claimed": bool(row["market_demand_claimed"]),
            "authority_created": bool(row["authority_created"]),
            "observed_at": row["observed_at"],
        }
        for row in rows
    ]


def _hypothesis_sets(store: MarketSensoriumStore, limit: int = 20) -> list[dict[str, Any]]:
    rows = _safe_rows(
        store,
        """
        SELECT hypothesis_set_id,transition_id,target_id,organisation,domain_id,
               observed_at,rival_count,selected_hypothesis_id,selected_hypothesis_type,
               selected_test_json,evidence_digest,world_state_digest,truth_state,
               authority_created,market_demand_claimed,external_effects
        FROM commercial_hypothesis_sets
        ORDER BY observed_at DESC, rowid DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    return [
        {
            "hypothesis_set_id": row["hypothesis_set_id"],
            "transition_id": row["transition_id"],
            "target_id": row["target_id"],
            "organisation": row["organisation"],
            "domain_id": row["domain_id"],
            "rival_count": row["rival_count"],
            "selected_hypothesis_id": row["selected_hypothesis_id"],
            "selected_hypothesis_type": row["selected_hypothesis_type"],
            "selected_test": _obj(row["selected_test_json"]),
            "evidence_digest": row["evidence_digest"],
            "world_state_digest": row["world_state_digest"],
            "truth_state": row["truth_state"],
            "truth_class": "UNPROVED_HYPOTHESIS",
            "market_demand_claimed": bool(row["market_demand_claimed"]),
            "authority_created": bool(row["authority_created"]),
            "external_effects": bool(row["external_effects"]),
            "observed_at": row["observed_at"],
        }
        for row in rows
    ]


def _offers(store: MarketSensoriumStore, limit: int = 20) -> list[dict[str, Any]]:
    rows = _safe_rows(
        store,
        """
        SELECT offer_key,seller,seller_role,domain_id,morphology,canonical_headline,
               first_seen_at,last_seen_at,observation_count,distinct_source_count,
               distinct_content_count,latest_price_state,latest_price_value,
               latest_price_currency,latest_price_basis,persistence_state,
               payload_json,authority_created
        FROM competitive_offer_memory
        ORDER BY last_seen_at DESC, observation_count DESC, offer_key
        LIMIT ?
        """,
        (int(limit),),
    )
    result = []
    for row in rows:
        payload = _obj(row["payload_json"])
        result.append({
            "offer_key": row["offer_key"],
            "seller": row["seller"],
            "seller_role": row["seller_role"],
            "domain_id": row["domain_id"],
            "headline": row["canonical_headline"],
            "observation_count": row["observation_count"],
            "distinct_source_count": row["distinct_source_count"],
            "price_state": row["latest_price_state"],
            "price_value": row["latest_price_value"],
            "price_currency": row["latest_price_currency"],
            "price_basis": row["latest_price_basis"],
            "persistence_state": row["persistence_state"],
            "truth_class": "OBSERVED_ADVERTISED_OFFER",
            "advertised_price_is_market_price": bool(payload.get("advertised_price_is_market_price", False)),
            "advertised_price_is_realised_price": bool(payload.get("advertised_price_is_realised_price", False)),
            "willingness_to_pay_proved": bool(payload.get("willingness_to_pay_proved", False)),
            "market_demand_claimed": bool(payload.get("market_demand_claimed", False)),
            "authority_created": bool(row["authority_created"]),
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
        })
    return result


def _habitats(store: MarketSensoriumStore, limit: int = 20) -> list[dict[str, Any]]:
    rows = _safe_rows(
        store,
        """
        SELECT habitat_key,platform,habitat_kind,canonical_name,source_ref,domain_id,
               first_seen_at,last_seen_at,observation_count,access_state,
               permission_ladder_state,operator_membership_state,posting_authority,
               dm_authority,read_authority,seller_association_state,intelligence_score,
               recommended_action,payload_json,authority_created
        FROM market_habitat_memory_v2
        ORDER BY intelligence_score DESC, observation_count DESC, last_seen_at DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    result = []
    for row in rows:
        payload = _obj(row["payload_json"])
        result.append({
            "habitat_key": row["habitat_key"],
            "platform": row["platform"],
            "habitat_kind": row["habitat_kind"],
            "name": row["canonical_name"],
            "source_ref": row["source_ref"],
            "domain_id": row["domain_id"],
            "permission": row["permission_ladder_state"],
            "membership": row["operator_membership_state"],
            "posting_authority": row["posting_authority"],
            "dm_authority": row["dm_authority"],
            "read_authority": row["read_authority"],
            "seller_association": row["seller_association_state"],
            "intelligence_score": row["intelligence_score"],
            "recommended_action": row["recommended_action"],
            "truth_class": "OBSERVED_MARKET_HABITAT",
            "public_visibility_is_consent": bool(payload.get("public_visibility_is_consent", False)),
            "participant_inference_allowed": bool(payload.get("participant_inference_allowed", False)),
            "member_scraping_allowed": bool(payload.get("member_scraping_allowed", False)),
            "habitat_is_demand": bool(payload.get("habitat_is_demand", False)),
            "authority_created": bool(row["authority_created"]),
        })
    return result


def _learned_queries(store: MarketSensoriumStore, limit: int = 8) -> list[dict[str, Any]]:
    rows = _safe_rows(
        store,
        """
        SELECT domain_id,selected_query_id,selected_query_text,query_kind,
               previous_query_text,evidence_digest,source_driver_count,novelty_score,
               updated_at,execution_authority,authority_created
        FROM learned_query_memory
        ORDER BY updated_at DESC, domain_id
        LIMIT ?
        """,
        (int(limit),),
    )
    return [
        {
            "domain_id": row["domain_id"],
            "query_id": row["selected_query_id"],
            "query": row["selected_query_text"],
            "query_kind": row["query_kind"],
            "previous_query": row["previous_query_text"],
            "evidence_digest": row["evidence_digest"],
            "source_driver_count": row["source_driver_count"],
            "novelty_score": row["novelty_score"],
            "execution_authority": row["execution_authority"],
            "truth_class": "PROPOSED_DISCOVERY_QUERY",
            "query_execution_performed": False,
            "query_is_market_truth": False,
            "search_hit_is_lead": False,
            "market_demand_claimed": False,
            "authority_created": bool(row["authority_created"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def _authority_matrix() -> dict[str, Any]:
    return {
        "truth_class": "AUTHORITY_BOUNDARY",
        "read_public_sources": "GOVERNED_READ_ONLY_LANE",
        "outreach": "NOT_AUTHORISED",
        "publication": "NOT_AUTHORISED",
        "spend": "NOT_AUTHORISED",
        "membership": "NOT_AUTHORISED",
        "posting": "NOT_AUTHORISED",
        "dm": "NOT_AUTHORISED",
        "commerce": "NOT_AUTHORISED_BY_SENSORIUM",
        "followup_from_silence": "NOT_AUTHORISED",
        "authority_created": False,
        "external_effects": False,
    }


def _truth_violations(cockpit: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for row in cockpit.get("rank_movements") or []:
        if row.get("authority_created") or row.get("market_demand_claimed"):
            violations.append(f"rank_transition:{row.get('transition_id')}")
    for row in cockpit.get("hypotheses") or []:
        if row.get("truth_state") != "UNPROVED":
            violations.append(f"hypothesis_truth:{row.get('hypothesis_set_id')}")
        if row.get("authority_created") or row.get("market_demand_claimed") or row.get("external_effects"):
            violations.append(f"hypothesis_authority:{row.get('hypothesis_set_id')}")
    for row in cockpit.get("offers") or []:
        if any(bool(row.get(key)) for key in (
            "advertised_price_is_market_price",
            "advertised_price_is_realised_price",
            "willingness_to_pay_proved",
            "market_demand_claimed",
            "authority_created",
        )):
            violations.append(f"offer_truth:{row.get('offer_key')}")
    for row in cockpit.get("habitats") or []:
        if any(bool(row.get(key)) for key in (
            "public_visibility_is_consent",
            "participant_inference_allowed",
            "member_scraping_allowed",
            "habitat_is_demand",
            "authority_created",
        )):
            violations.append(f"habitat_truth:{row.get('habitat_key')}")
    for row in cockpit.get("learned_queries") or []:
        if row.get("authority_created") or row.get("query_execution_performed") or row.get("query_is_market_truth") or row.get("search_hit_is_lead") or row.get("market_demand_claimed"):
            violations.append(f"query_truth:{row.get('query_id')}")
    return violations


def _badge(label: str, cls: str) -> str:
    return f'<span class="badge {cls}">{html.escape(label)}</span>'


def _render_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return '<div class="empty">No evidence in this section yet.</div>'
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(value if value is not None else ''))}</td>" for value in row) + "</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def render_commercial_cockpit(cockpit: dict[str, Any]) -> str:
    phases = cockpit.get("phase_status") or {}
    phase_cards = "".join(
        f"<div class='phase'><b>{html.escape(name)}</b>{_badge(str(item.get('truth_class')), 'good' if item.get('truth_class') == 'VERIFIED_CAPABILITY' else 'warn')}<span>{html.escape(str(item.get('acceptance')))}</span></div>"
        for name, item in phases.items()
    )
    temporal = cockpit.get("commercial_time") or {}
    authority = cockpit.get("authority") or {}
    truth = cockpit.get("truth_summary") or {}

    target_rows = [[r.get("organisation"), r.get("domain_id"), r.get("current_rank"), r.get("current_score"), r.get("reply_state"), r.get("silence_state")] for r in cockpit.get("ranked_targets") or []]
    movement_rows = [[r.get("organisation"), r.get("domain_id"), f"{r.get('previous_rank')}→{r.get('current_rank')}", r.get("transition_kind"), "; ".join(r.get("explanation_factors") or [])] for r in cockpit.get("rank_movements") or []]
    hypothesis_rows = [[r.get("organisation"), r.get("domain_id"), r.get("selected_hypothesis_type"), r.get("rival_count"), (r.get("selected_test") or {}).get("test_kind"), r.get("truth_state")] for r in cockpit.get("hypotheses") or []]
    offer_rows = [[r.get("seller"), r.get("domain_id"), r.get("headline"), r.get("price_state"), r.get("price_value"), r.get("price_basis")] for r in cockpit.get("offers") or []]
    habitat_rows = [[r.get("name"), r.get("platform"), r.get("domain_id"), r.get("permission"), r.get("read_authority"), r.get("posting_authority"), r.get("dm_authority")] for r in cockpit.get("habitats") or []]
    query_rows = [[r.get("domain_id"), r.get("query_kind"), r.get("query"), r.get("novelty_score"), r.get("source_driver_count"), r.get("execution_authority")] for r in cockpit.get("learned_queries") or []]

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DIO Market Sensorium Commercial Cockpit</title>
<style>
:root{{--bg:#090d0f;--surface:#111719;--line:#293438;--ink:#edf3f2;--muted:#91a0a4;--green:#70d69f;--amber:#e5b65d;--red:#ff7d73;--blue:#67c8ed}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:24px;display:grid;gap:18px}}h1{{margin:0;font-size:24px}}.sub{{color:var(--muted);font-size:13px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}}.phase,.card,.panel{{background:var(--surface);border:1px solid var(--line);border-radius:7px}}.phase{{padding:13px;display:grid;gap:8px}}.phase span:last-child{{font-size:10px;color:var(--muted);word-break:break-word}}.badge{{display:inline-block;width:max-content;border-radius:999px;padding:3px 7px;font-size:9px;font-weight:800;border:1px solid var(--line)}}.badge.good{{color:var(--green)}}.badge.warn{{color:var(--amber)}}.badge.bad{{color:var(--red)}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}.card{{padding:14px}}.card b{{display:block;font-size:22px;margin-top:5px}}.card span{{color:var(--muted);font-size:10px;text-transform:uppercase}}.panel h2{{font-size:14px;margin:0;padding:13px 15px;border-bottom:1px solid var(--line)}}.table-wrap{{overflow:auto;max-height:430px}}table{{width:100%;border-collapse:collapse;font-size:11px}}th,td{{padding:9px 11px;border-bottom:1px solid #202a2e;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#151e22;color:#aab7ba;text-transform:uppercase;font-size:9px}}.truth{{display:flex;gap:8px;flex-wrap:wrap;padding:14px}}.empty{{padding:18px;color:var(--muted)}}code{{color:var(--blue)}}
</style></head><body><main>
<div><h1>DIO Market Sensorium · Commercial Cockpit</h1><div class="sub">Read-only epistemic surface. Priority ≠ best target. Hypothesis ≠ fact. Advertised offer ≠ demand. Public visibility ≠ permission.</div></div>
<div class="grid">{phase_cards}</div>
<div class="cards">
<div class="card"><span>Ranked targets shown</span><b>{len(cockpit.get('ranked_targets') or [])}</b></div>
<div class="card"><span>Rank movements</span><b>{len(cockpit.get('rank_movements') or [])}</b></div>
<div class="card"><span>Hypothesis sets</span><b>{len(cockpit.get('hypotheses') or [])}</b></div>
<div class="card"><span>Competitive offers</span><b>{len(cockpit.get('offers') or [])}</b></div>
<div class="card"><span>Market habitats</span><b>{len(cockpit.get('habitats') or [])}</b></div>
<div class="card"><span>Learned queries</span><b>{len(cockpit.get('learned_queries') or [])}</b></div>
</div>
<div class="panel"><h2>Commercial time</h2><div class="truth">{_badge(str(temporal.get('coverage_state') or 'UNAVAILABLE'),'good' if temporal.get('coverage_state')=='CONTINUOUS' else 'warn')}<code>continuous_from={html.escape(str(temporal.get('continuous_from') or ''))}</code><code>last_sync={html.escape(str(temporal.get('last_successful_sync_at') or ''))}</code><code>replies={html.escape(str(temporal.get('reply_observed') or 0))}</code><code>no_reply_observed={html.escape(str(temporal.get('no_reply_observed') or 0))}</code></div></div>
<div class="panel"><h2>Current ranked priority surface</h2>{_render_table(['Organisation','Domain','Rank','Score','Reply','Temporal state'],target_rows)}</div>
<div class="panel"><h2>Dynamic rank movements</h2>{_render_table(['Organisation','Domain','Move','Kind','Why'],movement_rows)}</div>
<div class="panel"><h2>Hivenance hypotheses · UNPROVED</h2>{_render_table(['Organisation','Domain','Selected rival','Rivals','Bounded test','Truth'],hypothesis_rows)}</div>
<div class="panel"><h2>Competitive offer intelligence</h2>{_render_table(['Seller','Domain','Offer','Price state','Value','Basis'],offer_rows)}</div>
<div class="panel"><h2>Market habitats and permission</h2>{_render_table(['Habitat','Platform','Domain','Permission','Read','Post','DM'],habitat_rows)}</div>
<div class="panel"><h2>Learned discovery query plan</h2>{_render_table(['Domain','Driver','Query','Novelty','Drivers','Execution authority'],query_rows)}</div>
<div class="panel"><h2>Truth and authority boundary</h2><div class="truth">{_badge('truth separation valid' if truth.get('truth_separation_valid') else 'truth violation','good' if truth.get('truth_separation_valid') else 'bad')}<code>violations={html.escape(str(truth.get('truth_class_violations') or 0))}</code><code>outreach={html.escape(str(authority.get('outreach')))}</code><code>publication={html.escape(str(authority.get('publication')))}</code><code>spend={html.escape(str(authority.get('spend')))}</code><code>membership={html.escape(str(authority.get('membership')))}</code><code>DM={html.escape(str(authority.get('dm')))}</code></div></div>
</main></body></html>"""


def build_commercial_cockpit(root: Path, store: MarketSensoriumStore) -> dict[str, Any]:
    root = Path(root).resolve()
    state_root = root / "state" / "market_sensorium"
    state_root.mkdir(parents=True, exist_ok=True)
    phases = _phase_status(root)
    commercial_time = dict(((phases.get("MS-2") or {}).get("truth") or {}))

    cockpit: dict[str, Any] = {
        "schema": "dio.market_sensorium.commercial_cockpit.v1",
        "created_at": utc_now(),
        "phase_status": phases,
        "commercial_time": commercial_time,
        "ranked_targets": _ranked_targets(store),
        "rank_movements": _rank_movements(store),
        "hypotheses": _hypothesis_sets(store),
        "offers": _offers(store),
        "habitats": _habitats(store),
        "learned_queries": _learned_queries(store),
        "authority": _authority_matrix(),
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
    violations = _truth_violations(cockpit)
    linked_transition_ids = {str(row.get("transition_id") or "") for row in cockpit["rank_movements"]}
    linked_hypotheses = sum(1 for row in cockpit["hypotheses"] if str(row.get("transition_id") or "") in linked_transition_ids)
    section_counts = {
        "ranked_targets": len(cockpit["ranked_targets"]),
        "rank_movements": len(cockpit["rank_movements"]),
        "hypotheses": len(cockpit["hypotheses"]),
        "offers": len(cockpit["offers"]),
        "habitats": len(cockpit["habitats"]),
        "learned_queries": len(cockpit["learned_queries"]),
    }
    cockpit["truth_summary"] = {
        "truth_separation_valid": not violations,
        "truth_class_violations": len(violations),
        "violations": violations,
        "linked_hypothesis_sets_to_visible_movements": linked_hypotheses,
        "section_counts": section_counts,
        "operator_surface_complete": all(value > 0 for value in section_counts.values()),
        "ms7_verified": (phases.get("MS-7") or {}).get("acceptance") == MS7_VERIFIED,
        "ms2_observation_active_or_verified": (phases.get("MS-2") or {}).get("acceptance") in MS2_ACTIVE_STATES,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    source_payload = {
        "phase_status": phases,
        "commercial_time": commercial_time,
        "section_counts": section_counts,
        "rank_transition_ids": [row["transition_id"] for row in cockpit["rank_movements"]],
        "hypothesis_set_ids": [row["hypothesis_set_id"] for row in cockpit["hypotheses"]],
        "offer_keys": [row["offer_key"] for row in cockpit["offers"]],
        "habitat_keys": [row["habitat_key"] for row in cockpit["habitats"]],
        "query_ids": [row["query_id"] for row in cockpit["learned_queries"]],
    }
    cockpit["source_digest"] = digest_payload(source_payload)
    cockpit["snapshot_id"] = stable_id("MS8", cockpit["source_digest"], cockpit["created_at"])

    json_path = state_root / "COMMERCIAL_COCKPIT.json"
    html_path = state_root / "COMMERCIAL_COCKPIT.html"
    cockpit["artifacts"] = {
        "json": str(json_path.relative_to(root)),
        "html": str(html_path.relative_to(root)),
    }
    json_path.write_text(json.dumps(cockpit, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    html_path.write_text(render_commercial_cockpit(cockpit), encoding="utf-8")
    return cockpit
