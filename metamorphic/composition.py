"""Deterministic composition DAG for DIO Metamorphic Phase 5.

The DAG is a plan, not execution. Nodes keep the selected unit's immutable
identity and native executor/evidence/quality bindings. Edges express declared
outcome dependencies. Cycles and missing dependencies fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contracts import digest_payload


class CompositionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedNode:
    node_id: str
    capability: str
    unit_id: str
    unit_digest: str
    semantic_law_digest: str
    executor_id: str
    executor_digest: str
    evidence_contract_digest: str
    quality_contract_digest: str
    authority_ceiling: str

    @property
    def node_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "capability": self.capability,
            "unit_id": self.unit_id,
            "unit_digest": self.unit_digest,
            "semantic_law_digest": self.semantic_law_digest,
            "executor_id": self.executor_id,
            "executor_digest": self.executor_digest,
            "evidence_contract_digest": self.evidence_contract_digest,
            "quality_contract_digest": self.quality_contract_digest,
            "authority_ceiling": self.authority_ceiling,
            "node_digest": self.node_digest,
        }


@dataclass(frozen=True, slots=True)
class CompositionEdge:
    source_node: str
    target_node: str
    relation: str = "depends_on"

    @property
    def edge_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node": self.source_node,
            "target_node": self.target_node,
            "relation": self.relation,
            "edge_digest": self.edge_digest,
        }


@dataclass(frozen=True, slots=True)
class CompositionDAG:
    composition_name: str
    intent_digest: str
    world_lease_digest: str
    nodes: tuple[ResolvedNode, ...]
    edges: tuple[CompositionEdge, ...]
    topological_order: tuple[str, ...]
    authority: Mapping[str, Any]
    schema: str = "dio.metamorphic.composition_dag.v1"

    @property
    def composition_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "composition_name": self.composition_name,
            "intent_digest": self.intent_digest,
            "world_lease_digest": self.world_lease_digest,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "topological_order": list(self.topological_order),
            "authority": dict(self.authority),
            "composition_digest": self.composition_digest,
        }


def _topological_order(node_ids: Sequence[str], edges: Sequence[CompositionEdge]) -> tuple[str, ...]:
    unique = tuple(dict.fromkeys(node_ids))
    if len(unique) != len(tuple(node_ids)):
        raise CompositionError("composition node ids must be unique")
    nodes = set(unique)
    incoming = {node_id: 0 for node_id in unique}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in unique}
    for edge in edges:
        if edge.source_node not in nodes or edge.target_node not in nodes:
            raise CompositionError(
                f"composition edge references missing node: {edge.source_node}->{edge.target_node}"
            )
        if edge.source_node == edge.target_node:
            raise CompositionError(f"composition self-cycle: {edge.source_node}")
        outgoing[edge.source_node].append(edge.target_node)
        incoming[edge.target_node] += 1

    ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for target in sorted(outgoing[current]):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    if len(ordered) != len(unique):
        unresolved = sorted(node_id for node_id, count in incoming.items() if count > 0)
        raise CompositionError(f"composition dependency cycle detected: {unresolved}")
    return tuple(ordered)


def build_composition_dag(
    *,
    composition_name: str,
    intent_digest: str,
    world_lease_digest: str,
    nodes: Sequence[ResolvedNode],
    dependencies: Mapping[str, Sequence[str]],
    authority: Mapping[str, Any],
) -> CompositionDAG:
    if not str(composition_name).strip():
        raise CompositionError("composition_name is required")
    node_tuple = tuple(nodes)
    if not node_tuple:
        raise CompositionError("composition requires at least one node")
    by_id = {node.node_id: node for node in node_tuple}
    if len(by_id) != len(node_tuple):
        raise CompositionError("composition node ids must be unique")

    edges: list[CompositionEdge] = []
    seen_edges: set[tuple[str, str]] = set()
    for target, sources in sorted(dependencies.items()):
        if target not in by_id:
            raise CompositionError(f"dependency target is missing: {target}")
        for source in sources:
            if source not in by_id:
                raise CompositionError(f"dependency source is missing: {source}")
            key = (source, target)
            if key not in seen_edges:
                edges.append(CompositionEdge(source_node=source, target_node=target))
                seen_edges.add(key)

    edge_tuple = tuple(sorted(edges, key=lambda row: (row.source_node, row.target_node)))
    order = _topological_order(tuple(by_id), edge_tuple)
    return CompositionDAG(
        composition_name=str(composition_name).strip(),
        intent_digest=intent_digest,
        world_lease_digest=world_lease_digest,
        nodes=tuple(sorted(node_tuple, key=lambda row: row.node_id)),
        edges=edge_tuple,
        topological_order=order,
        authority=dict(authority),
    )
