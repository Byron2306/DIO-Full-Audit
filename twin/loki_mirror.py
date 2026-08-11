from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .canonical import TWIN_SCHEMA, TwinError, validate_twin

MIRROR_SCHEMA = "dio.loki_mirror_maze.v1"
LOKI_SOURCE = {
    "repository": "Byron2306/Metatron",
    "commit": "532f8f4d22568c3812352150da7c7baf923d76e6",
    "triune_loki": "backend/triune/loki_ai.py",
    "mirror_maze": "backend/services/mystique_maze.py",
    "deception_router": "backend/routers/deception.py",
    "reuse_mode": "internal_semantic_harvest",
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _pick(rows: list[dict[str, Any]], seed: str) -> dict[str, Any] | None:
    if not rows:
        return None
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(rows)
    return rows[index]


def _node(
    *,
    twin: dict[str, Any],
    category: str,
    layer: str,
    source: dict[str, Any] | None,
    depth: int,
    parent_id: str | None,
    mutation: dict[str, Any],
    rationale: str,
) -> dict[str, Any]:
    body = {
        "source_twin_id": twin["twin_id"],
        "source_twin_fingerprint": twin["fingerprint"],
        "category": category,
        "layer": layer,
        "source_record_id": source.get("twin_record_id") if source else None,
        "depth": int(depth),
        "parent_id": parent_id,
        "mutation": copy.deepcopy(mutation),
        "rationale": rationale,
        "synthetic": True,
        "canonical_effect": False,
        "authority_effect": False,
    }
    body["fingerprint"] = _fingerprint(body)
    body["mirror_node_id"] = f"LOKI-{body['fingerprint'][:16].upper()}"
    return body


def _candidate_mutations(twin: dict[str, Any]) -> list[tuple[str, str, dict[str, Any] | None, dict[str, Any], str]]:
    layers = twin["layers"]
    evidence = _pick(layers["evidence_state"], twin["fingerprint"] + ":evidence")
    claim = _pick(layers["claim_state"], twin["fingerprint"] + ":claim")
    requirement = _pick(layers["requirement_state"], twin["fingerprint"] + ":requirement")
    authority = _pick(layers["authority_state"], twin["fingerprint"] + ":authority")
    capability = _pick(layers["capability_state"], twin["fingerprint"] + ":capability")
    action = _pick(layers["action_state"], twin["fingerprint"] + ":action")
    receipt = _pick(layers["receipt_state"], twin["fingerprint"] + ":receipt")
    world = _pick(layers["world_state"], twin["fingerprint"] + ":world")

    return [
        (
            "stale_evidence",
            "evidence_state",
            evidence,
            {"freshness_state": "stale", "current": False},
            "Mirror a plausible stale-evidence state to test temporal dependence.",
        ),
        (
            "claim_contradiction",
            "claim_state",
            claim,
            {"epistemic_state": "CONTESTED", "synthetic_challenge": "plausible contradictory interpretation"},
            "Challenge whether the current conclusion survives a coherent contradiction.",
        ),
        (
            "requirement_regression",
            "requirement_state",
            requirement,
            {"state": "evidence_needed", "synthetic_missing_dependency": True},
            "Re-open a satisfied-looking requirement to expose hidden dependency assumptions.",
        ),
        (
            "authority_expiry",
            "authority_state",
            authority,
            {"current": False, "synthetic_expiry": True},
            "Ask what remains permitted if the relied-upon authority is no longer current.",
        ),
        (
            "lease_revocation",
            "capability_state",
            capability,
            {"state": "revoked", "current": False, "synthetic_revocation": True},
            "Test whether execution remains blocked when the capability lease disappears.",
        ),
        (
            "action_payload_drift",
            "action_state",
            action,
            {"synthetic_payload_drift": True, "action_binding_match": False},
            "Test whether exact action/payload binding detects a plausible substituted action.",
        ),
        (
            "receipt_fork",
            "receipt_state",
            receipt,
            {"synthetic_receipt_fork": True, "canonical_receipt_match": False},
            "Create a receipt-fork hypothesis without altering the canonical receipt chain.",
        ),
        (
            "world_state_drift",
            "world_state",
            world,
            {"synthetic_world_drift": True, "current": False},
            "Mirror a changed external world state so current decisions can be tested against drift.",
        ),
    ]


def build_loki_mirror_maze(twin: dict[str, Any]) -> dict[str, Any]:
    validate_twin(twin)
    root = _node(
        twin=twin,
        category="canonical_anchor",
        layer="root",
        source=None,
        depth=0,
        parent_id=None,
        mutation={"source_twin_id": twin["twin_id"]},
        rationale="Anchor the maze to one immutable canonical twin snapshot.",
    )
    nodes = [root]
    parent = root["mirror_node_id"]
    depth = 1
    for category, layer, source, mutation, rationale in _candidate_mutations(twin):
        if source is None:
            continue
        node = _node(
            twin=twin,
            category=category,
            layer=layer,
            source=source,
            depth=depth,
            parent_id=parent,
            mutation=mutation,
            rationale=rationale,
        )
        nodes.append(node)
        # deterministic maze branching: every second node becomes the next trunk parent
        if depth % 2 == 0:
            parent = node["mirror_node_id"]
        depth += 1

    children: dict[str, list[str]] = {node["mirror_node_id"]: [] for node in nodes}
    for node in nodes:
        if node["parent_id"]:
            children[node["parent_id"]].append(node["mirror_node_id"])
    for node in nodes:
        node["children"] = sorted(children[node["mirror_node_id"]])

    max_depth = max((node["depth"] for node in nodes), default=0)
    tier = "surface" if max_depth <= 2 else "shallow" if max_depth <= 4 else "deep" if max_depth <= 7 else "labyrinth"
    material = {
        "source_twin_id": twin["twin_id"],
        "source_twin_fingerprint": twin["fingerprint"],
        "tier": tier,
        "nodes": nodes,
        "loki_source": LOKI_SOURCE,
    }
    fingerprint = _fingerprint(material)
    maze = {
        "schema": MIRROR_SCHEMA,
        "mirror_maze_id": f"LOKI-MAZE-{fingerprint[:16].upper()}",
        "source_twin_id": twin["twin_id"],
        "source_twin_fingerprint": twin["fingerprint"],
        "tier": tier,
        "nodes": nodes,
        "loki_source": copy.deepcopy(LOKI_SOURCE),
        "laws": {
            "all_mirror_state_is_synthetic": True,
            "mirror_never_becomes_evidence": True,
            "mirror_never_mints_authority": True,
            "mirror_never_executes": True,
            "canonical_twin_is_immutable": True,
        },
        "fingerprint": fingerprint,
    }
    validate_loki_mirror(maze, twin=twin)
    return maze


def validate_loki_mirror(maze: dict[str, Any], *, twin: dict[str, Any] | None = None) -> None:
    if maze.get("schema") != MIRROR_SCHEMA:
        raise TwinError("Unsupported Loki mirror schema.")
    laws = maze.get("laws") or {}
    if any(laws.get(name) is not True for name in (
        "all_mirror_state_is_synthetic",
        "mirror_never_becomes_evidence",
        "mirror_never_mints_authority",
        "mirror_never_executes",
        "canonical_twin_is_immutable",
    )):
        raise TwinError("Loki mirror constitutional law disabled.")
    if twin is not None:
        validate_twin(twin)
        if maze.get("source_twin_id") != twin["twin_id"] or maze.get("source_twin_fingerprint") != twin["fingerprint"]:
            raise TwinError("Loki mirror is not bound to this canonical twin.")
    ids = {row.get("mirror_node_id") for row in maze.get("nodes") or []}
    if None in ids or len(ids) != len(maze.get("nodes") or []):
        raise TwinError("Mirror node identity is missing or duplicated.")
    for row in maze.get("nodes") or []:
        if row.get("synthetic") is not True or row.get("canonical_effect") is not False or row.get("authority_effect") is not False:
            raise TwinError("Mirror node attempted to escape synthetic containment.")
        if row.get("parent_id") and row.get("parent_id") not in ids:
            raise TwinError("Mirror node parent is unknown.")
        payload = copy.deepcopy(row)
        fingerprint = payload.pop("fingerprint", None)
        node_id = payload.pop("mirror_node_id", None)
        expected = _fingerprint(payload)
        if fingerprint != expected or node_id != f"LOKI-{expected[:16].upper()}":
            raise TwinError("Mirror node fingerprint mismatch.")
    material = {
        "source_twin_id": maze["source_twin_id"],
        "source_twin_fingerprint": maze["source_twin_fingerprint"],
        "tier": maze["tier"],
        "nodes": maze["nodes"],
        "loki_source": maze["loki_source"],
    }
    expected = _fingerprint(material)
    if maze.get("fingerprint") != expected or maze.get("mirror_maze_id") != f"LOKI-MAZE-{expected[:16].upper()}":
        raise TwinError("Loki mirror fingerprint mismatch.")


def compare_canonical_to_mirror(twin: dict[str, Any], maze: dict[str, Any]) -> dict[str, Any]:
    validate_loki_mirror(maze, twin=twin)
    categories = sorted({row["category"] for row in maze["nodes"] if row["category"] != "canonical_anchor"})
    return {
        "schema": "dio.evidence_authority_twin.divergence.v1",
        "twin_id": twin["twin_id"],
        "mirror_maze_id": maze["mirror_maze_id"],
        "synthetic_divergence_count": len(categories),
        "categories": categories,
        "canonical_mutated": False,
        "authority_created": False,
        "execution_created": False,
    }
