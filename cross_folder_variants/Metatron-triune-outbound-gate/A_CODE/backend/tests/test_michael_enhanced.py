import asyncio
import pathlib
import sys
# ensure repo root on path for test import resolution
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.triune.michael import MichaelService


def test_michael_enhanced_scoring():
    # fake DB/collections
    class FakeColl(dict):
        async def find_one(self, q, *a, **k):
            return self.get(q.get("id"))

        async def count_documents(self, q):
            # simplistic counting for edges
            # q may be {'$or': [{'source': id}, {'target': id}]}
            orq = q.get("$or") or []
            cnt = 0
            for cond in orq:
                if "source" in cond:
                    val = cond.get("source")
                else:
                    val = cond.get("target")
                for e in list(self.values()):
                    if e.get("source") == val or e.get("target") == val:
                        cnt += 1
            return cnt

    fake_wm = type("Wm", (), {})()
    fake_wm.entities = FakeColl()
    fake_wm.edges = FakeColl()

    # populate entity ent1: high risk, recent
    fake_wm.entities["ent1"] = {"id": "ent1", "attributes": {"risk_score": 0.9, "last_seen": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}}
    # ent2: low risk, old
    old = __import__("datetime").datetime.now(__import__("datetime").timezone.utc) - __import__("datetime").timedelta(days=30)
    fake_wm.entities["ent2"] = {"id": "ent2", "attributes": {"risk_score": 0.1, "last_seen": old.isoformat()}}
    # edges: ent1 has 6 connections, ent2 has 1
    for i in range(6):
        fake_wm.edges[f"e{i}"] = {"source": "ent1", "target": f"n{i}"}
    fake_wm.edges["e_last"] = {"source": "ent2", "target": "nX"}

    svc = MichaelService(db=None)
    # inject fake world model
    svc.wm = fake_wm

    candidates = ["isolate:ent1", "monitor:ent2", "password_reset"]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res = loop.run_until_complete(svc.rank_responses(candidates))

    # expect isolate:ent1 to score highest due to keywords + high risk + recency + degree
    assert res[0]["candidate"] == "isolate:ent1"
    assert res[0]["score"] >= res[1]["score"]
    # each result should include components and score in 0..1
    for r in res:
        assert 0.0 <= r["score"] <= 1.0
        assert "components" in r
        comps = r["components"]
        assert set(comps.keys()) >= {"base", "keyword", "risk", "recency", "degree"}
