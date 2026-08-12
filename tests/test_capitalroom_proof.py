from __future__ import annotations
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from capitalroom import ProofRoomError, build_capitalroom
from capitalroom.proof_room import PRODUCT_IDS
from tests.capitalroom_fixtures import GENERATED, incarnation, make_room, phase0, portfolio, vertical_registry, wave_receipts

def test_capitalroom_config_schema():
    schema=json.loads(Path("schemas/dio_capitalroom.schema.json").read_text())
    payload=json.loads(Path("config/dio_capitalroom.json").read_text())
    Draft202012Validator.check_schema(schema); Draft202012Validator(schema).validate(payload)

def test_builds_four_proof_sections():
    assert set(make_room()["proof_sections"])=={"architecture_proof","operational_proof","refusal_proof","product_proof"}

def test_requires_phase0_ready():
    bad=phase0(); bad["overall_state"]="BLOCKED"
    with pytest.raises(ProofRoomError,match="Phase 0"):
        build_capitalroom(phase0_snapshot=bad,incarnation_receipt=incarnation(),wave_receipts=wave_receipts(),product_portfolio=portfolio(),vertical_registry=vertical_registry(),generated_at=GENERATED)

def test_requires_incarnation_ready():
    bad=incarnation(); bad["state"]="BLOCKED"
    with pytest.raises(ProofRoomError,match="Incarnation"):
        build_capitalroom(phase0_snapshot=phase0(),incarnation_receipt=bad,wave_receipts=wave_receipts(),product_portfolio=portfolio(),vertical_registry=vertical_registry(),generated_at=GENERATED)

def test_requires_exact_waves():
    receipts=wave_receipts(); receipts.pop(3)
    with pytest.raises(ProofRoomError,match="exactly Fusion Wave"):
        build_capitalroom(phase0_snapshot=phase0(),incarnation_receipt=incarnation(),wave_receipts=receipts,product_portfolio=portfolio(),vertical_registry=vertical_registry(),generated_at=GENERATED)

def test_rejects_wrong_wave_state():
    receipts=wave_receipts(); receipts[5]["state"]="BLOCKED"
    with pytest.raises(ProofRoomError,match="Wave 5"):
        build_capitalroom(phase0_snapshot=phase0(),incarnation_receipt=incarnation(),wave_receipts=receipts,product_portfolio=portfolio(),vertical_registry=vertical_registry(),generated_at=GENERATED)

def test_rejects_wave_blockers():
    receipts=wave_receipts(); receipts[7]["blockers"]=["bad"]
    with pytest.raises(ProofRoomError,match="contains blockers"):
        build_capitalroom(phase0_snapshot=phase0(),incarnation_receipt=incarnation(),wave_receipts=receipts,product_portfolio=portfolio(),vertical_registry=vertical_registry(),generated_at=GENERATED)

def test_chain_has_eight_proven_receipts():
    chain=make_room()["proof_sections"]["operational_proof"]["host_acceptance_chain"]
    assert len(chain)==8 and all(row["status"]=="PROVEN" for row in chain)

def test_paths_are_redacted():
    text=json.dumps(make_room())
    assert "/home/byron" not in text and "<redacted-local-path>" in text

def test_receipts_have_source_hashes():
    chain=make_room()["proof_sections"]["operational_proof"]["host_acceptance_chain"]
    assert all(len(row["receipt_sha256"])==64 for row in chain)

def test_valinor_and_arda_are_preserved():
    room=make_room()
    assert room["authority"]["kernel_authority"]=="Valinor"
    assert room["authority"]["execution_identity_authority"]=="ARDA"

def test_capitalroom_has_no_authority_execution_or_release():
    authority=make_room()["authority"]
    assert authority["capitalroom_has_authority"] is False
    assert authority["capitalroom_can_execute"] is False
    assert authority["external_release_authorized"] is False

def test_nine_products_are_exposed():
    products=make_room()["proof_sections"]["product_proof"]["products"]
    assert len(products)==9 and {row["id"] for row in products}==set(PRODUCT_IDS)

def test_commercial_products_are_registered_not_proven():
    products=make_room()["proof_sections"]["product_proof"]["products"]
    assert all(row["proof_state"]=="REGISTERED_NOT_PROVEN" for row in products if row["id"]!="dio_capitalroom")
