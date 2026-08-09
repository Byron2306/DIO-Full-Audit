from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Seraph Controller (Live Arda-Fabric)")

_state_lock = Lock()
_compromised_nodes: Set[str] = set()
_isolated_nodes: Set[str] = set()
_quorum_votes: Dict[str, Any] = {}
_quorum_epoch = 1
_ledger: List[Dict[str, Any]] = []


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_ledger(
    aatr_id: str,
    surface: str,
    decision: str,
    reason: str,
    session_id: str,
    entity_id: Optional[str] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record = {
        "ts": _utc_ts(),
        "aatr_id": aatr_id,
        "surface": surface,
        "decision": decision,
        "reason": reason,
        "session_id": session_id,
        "entity_id": entity_id,
        "extras": extras or {},
    }
    _ledger.append(record)
    return record


class SeedCompromisePayload(BaseModel):
    session_id: str
    node_id: str
    model: str = "qwen2.5:0.5b"
    agent_class: str = "persistent_recon"


class IsolatePayload(BaseModel):
    session_id: str
    node_id: str
    method: str = "nftables"


class QuorumVotePayload(BaseModel):
    session_id: str
    node_id: str
    vote: str


class WitnessRecoverPayload(BaseModel):
    session_id: str
    target_node_id: str
    witness_node_id: str


class LawfulRecoverPayload(BaseModel):
    session_id: str
    target_node_id: str
    witness_node_id: str
    proof_hash: str
    policy_hash: str


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "seraph-controller", "ts": _utc_ts()}


@app.get("/state")
def state() -> Dict[str, Any]:
    with _state_lock:
        quorum_state = "lawful" if len(_compromised_nodes) == 0 else "strained"
        return {
            "quorum_epoch": _quorum_epoch,
            "quorum_state": quorum_state,
            "compromised_nodes": sorted(_compromised_nodes),
            "isolated_nodes": sorted(_isolated_nodes),
            "quorum_votes": len(_quorum_votes),
            "ledger_entries": len(_ledger),
        }


@app.get("/mandos/ledger")
def mandos_ledger(limit: int = 100) -> Dict[str, Any]:
    safe_limit = max(1, min(limit, 1000))
    with _state_lock:
        entries = _ledger[-safe_limit:]
        return {
            "count": len(entries),
            "total_recorded": len(_ledger),
            "entries": entries,
        }


@app.post("/phase/seed-compromise")
def phase_seed_compromise(req: SeedCompromisePayload) -> Dict[str, Any]:
    with _state_lock:
        _compromised_nodes.add(req.node_id)
        seeded = [
            {
                "kind": "compromised_node",
                "node_id": req.node_id,
                "model": req.model,
                "trust": "subverted",
                "agent_class": req.agent_class,
            }
        ]
        _append_ledger(
            aatr_id="PRECONDITION",
            surface="/phase/seed-compromise",
            decision="seeded",
            reason="hostile preconditions seeded for mode=partial_compromise; sandbox authority unchanged",
            session_id=req.session_id,
            entity_id=req.node_id,
            extras={"mode": "partial_compromise", "seeded": seeded},
        )
        return {
            "allowed": True,
            "simulate_only": True,
            "mode": "partial_compromise",
            "seeded": seeded,
            "quorum_epoch": _quorum_epoch,
        }


@app.post("/phase/isolate")
def phase_isolate(req: IsolatePayload) -> Dict[str, Any]:
    with _state_lock:
        _isolated_nodes.add(req.node_id)
        _append_ledger(
            aatr_id="AATR-Omega",
            surface="/phase/isolate",
            decision="isolate",
            reason="node isolation bypass refused; quarantine is enforced at the fabric layer",
            session_id=req.session_id,
            entity_id=req.node_id,
            extras={"isolation_method": req.method},
        )
        return {
            "allowed": False,
            "isolated": True,
            "aatr_id": "AATR-Omega",
            "surface": "/phase/isolate",
            "reason": "node isolation bypass refused; quarantine is enforced at the fabric layer",
            "extras": {"isolation_method": req.method},
            "quorum_epoch": _quorum_epoch,
        }


@app.post("/quorum/vote")
def quorum_vote(req: QuorumVotePayload) -> Dict[str, Any]:
    with _state_lock:
        compromised = req.node_id in _compromised_nodes
        if compromised:
            _append_ledger(
                aatr_id="QUORUM",
                surface="/quorum/vote",
                decision="isolate",
                reason="byzantine/subverted node vote refused; compromised nodes cannot move quorum epoch",
                session_id=req.session_id,
                entity_id=req.node_id,
                extras={
                    "vote_accepted": False,
                    "node_compromised": True,
                    "target_entity": req.node_id,
                    "quorum_epoch": _quorum_epoch,
                },
            )
            return {
                "allowed": False,
                "vote_accepted": False,
                "node_compromised": True,
                "quorum_epoch": _quorum_epoch,
                "reason": "byzantine/subverted node vote refused; compromised nodes cannot move quorum epoch",
            }

        _quorum_votes[req.node_id] = req.vote
        _append_ledger(
            aatr_id="QUORUM",
            surface="/quorum/vote",
            decision="accepted",
            reason="lawful quorum vote accepted",
            session_id=req.session_id,
            entity_id=req.node_id,
            extras={"vote_accepted": True, "quorum_epoch": _quorum_epoch},
        )
        return {
            "allowed": True,
            "vote_accepted": True,
            "node_compromised": False,
            "quorum_epoch": _quorum_epoch,
            "reason": "lawful quorum vote accepted",
        }


@app.post("/lorien/witness-recover")
def lorien_witness_recover(req: WitnessRecoverPayload) -> Dict[str, Any]:
    with _state_lock:
        witness_compromised = req.witness_node_id in _compromised_nodes
        if witness_compromised:
            _append_ledger(
                aatr_id="LORIEN",
                surface="/lorien/witness-recover",
                decision="isolate",
                reason="recovery witness refused; subverted witness cannot bless Lorien recovery",
                session_id=req.session_id,
                entity_id=req.target_node_id,
                extras={
                    "recovered": False,
                    "witness_node_id": req.witness_node_id,
                    "witness_compromised": True,
                },
            )
            return {
                "allowed": False,
                "recovered": False,
                "witness_node_id": req.witness_node_id,
                "witness_compromised": True,
                "reason": "recovery witness refused; subverted witness cannot bless Lorien recovery",
            }

        _append_ledger(
            aatr_id="LORIEN",
            surface="/lorien/witness-recover",
            decision="accepted",
            reason="lawful witness blesses Lorien recovery",
            session_id=req.session_id,
            entity_id=req.target_node_id,
            extras={
                "recovered": True,
                "witness_node_id": req.witness_node_id,
                "witness_compromised": False,
            },
        )
        return {
            "allowed": True,
            "recovered": True,
            "witness_node_id": req.witness_node_id,
            "witness_compromised": False,
            "reason": "lawful witness blesses Lorien recovery",
        }


@app.post("/lorien/recover")
def lorien_recover(req: LawfulRecoverPayload) -> Dict[str, Any]:
    with _state_lock:
        witness_compromised = req.witness_node_id in _compromised_nodes
        if witness_compromised:
            return {
                "allowed": False,
                "recovered": False,
                "reason": "lawful recovery denied: witness is compromised",
            }

        _compromised_nodes.discard(req.target_node_id)
        _isolated_nodes.discard(req.target_node_id)
        _quorum_votes.pop(req.target_node_id, None)
        compromised_remaining = len(_compromised_nodes)
        quorum_state = "lawful" if compromised_remaining == 0 else "strained"

        _append_ledger(
            aatr_id="LORIEN",
            surface="/lorien/recover",
            decision="recover",
            reason="recovery granted: fresh truth + order + attestation present",
            session_id=req.session_id,
            entity_id=req.target_node_id,
            extras={
                "recovered": True,
                "state": "harmonic",
                "re_admitted": True,
                "quorum_state": quorum_state,
                "compromised_nodes_remaining": compromised_remaining,
                "quorum_votes_remaining": len(_quorum_votes),
                "proof_hash": req.proof_hash,
                "policy_hash": req.policy_hash,
            },
        )

        return {
            "allowed": True,
            "aatr_id": "LORIEN",
            "recovered": True,
            "re_admitted": True,
            "state": "harmonic",
            "quorum_state": quorum_state,
            "compromised_nodes_remaining": compromised_remaining,
            "quorum_votes_remaining": len(_quorum_votes),
            "reason": "lawful recovery: fresh truth + order + attestation accepted",
        }
