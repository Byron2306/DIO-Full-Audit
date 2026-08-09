import asyncio
from copy import deepcopy
from types import SimpleNamespace

from backend.services.governance_authority import GovernanceDecisionAuthority


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in (query or {}).items()):
                return deepcopy(doc)
        return None

    async def update_one(self, query, update, upsert=False):
        for idx, doc in enumerate(self.docs):
            if all(doc.get(k) == v for k, v in (query or {}).items()):
                next_doc = deepcopy(doc)
                next_doc.update(update.get("$set", {}))
                self.docs[idx] = next_doc
                return SimpleNamespace(matched_count=1, modified_count=1)
        if upsert:
            self.docs.append(deepcopy(update.get("$set", {})))
        return SimpleNamespace(matched_count=0, modified_count=0)


class FakeDB:
    def __init__(self):
        self.triune_decisions = FakeCollection(
            [
                {
                    "decision_id": "decision-1",
                    "related_queue_id": "queue-1",
                    "status": "pending",
                }
            ]
        )
        self.triune_outbound_queue = FakeCollection(
            [
                {
                    "queue_id": "queue-1",
                    "status": "pending",
                    "payload": {"notation_token_id": "nt-1"},
                    "deception_provenance": {
                        "deception_case_id": "deception-1",
                        "revocation_conditions": [
                            "world_state_hash_drift",
                            "notation_token_revoked",
                            "corroboration_degraded",
                        ],
                        "independent_corroboration": {
                            "required": True,
                            "satisfied": False,
                            "sources": ["aatl"],
                            "missing_sources": ["vns"],
                            "reasons": ["corroboration_pending"],
                        },
                    },
                }
            ]
        )
        self.policy_decisions = FakeCollection([{"decision_id": "decision-1", "status": "pending"}])


def test_deny_decision_records_deception_revocation_triggers(monkeypatch):
    monkeypatch.setattr("backend.services.governance_authority.emit_world_event", None)
    db = FakeDB()
    service = GovernanceDecisionAuthority(db)

    result = asyncio.run(
        service.deny_decision(
            decision_id="decision-1",
            actor="operator:test",
            reason="world_state_hash_drift detected",
        )
    )

    assert result["found"] is True
    decision_doc = asyncio.run(db.triune_decisions.find_one({"decision_id": "decision-1"}))
    queue_doc = asyncio.run(db.triune_outbound_queue.find_one({"queue_id": "queue-1"}))
    provenance = decision_doc["deception_provenance"]

    assert provenance["revocation_triggered"] is True
    assert "world_state_hash_drift" in provenance["revocation_triggers"]
    assert "corroboration_degraded" in provenance["revocation_triggers"]
    assert queue_doc["deception_provenance"]["outbound_queue_status"] == "denied"
