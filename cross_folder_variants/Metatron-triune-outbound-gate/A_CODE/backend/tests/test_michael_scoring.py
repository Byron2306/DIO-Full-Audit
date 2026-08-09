import pytest
import os
import sys

# Ensure `backend` package directory is on sys.path for imports during pytest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib.util
import pathlib

# Import MichaelService directly from file to avoid importing package-level dependencies
mod_path = pathlib.Path(__file__).resolve().parents[1] / "triune" / "michael.py"
spec = importlib.util.spec_from_file_location("triune_michael", str(mod_path))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
MichaelService = mod.MichaelService


class FakeColl:
    def __init__(self, doc=None):
        self.doc = doc

    async def find_one(self, q, *args, **kwargs):
        return self.doc


class FakeDB:
    def __init__(self, world_entities=None):
        self.world_entities = world_entities


def test_rank_basic_keywords():
    import asyncio
    ms = MichaelService(db=None)
    candidates = [
        "isolate:host1",
        "monitor:host1",
        "kill:process1",
        "require_2fa:user1",
        "force_password_reset:user2",
    ]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ranked = loop.run_until_complete(ms.rank_responses(candidates))
    loop.close()
    assert isinstance(ranked, list)
    assert len(ranked) == len(candidates)
    # top candidate should be one with aggressive remediation
    top = ranked[0]["candidate"]
    assert ("kill" in top) or ("isolate" in top)


def test_rank_with_entity_risk():
    import asyncio
    doc = {"id": "host123", "attributes": {"risk_score": 0.9}}
    fake_coll = FakeColl(doc=doc)
    fake_db = FakeDB(world_entities=fake_coll)
    ms = MichaelService(db=fake_db)
    candidates = ["monitor:host123", "isolate:host123"]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ranked = loop.run_until_complete(ms.rank_responses(candidates))
    loop.close()
    assert ranked[0]["candidate"].startswith("isolate")
    assert ranked[0]["score"] >= ranked[1]["score"]
