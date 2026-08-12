from __future__ import annotations
import copy
from pathlib import Path
import pytest
from capitalroom import ProofRoomError, build_capitalroom, render_capitalroom_readme, validate_capitalroom, validate_manifest, write_capitalroom
from tests.capitalroom_fixtures import GENERATED, incarnation, make_room, phase0, portfolio, vertical_registry, wave_receipts

def test_capitalroom_profile_is_internal():
    row=next(row for row in make_room()["proof_sections"]["product_proof"]["products"] if row["id"]=="dio_capitalroom")
    assert row["proof_state"]=="INTERNAL_PROOF_PRODUCT" and row["runtime_mode"]=="internal_only"

def test_missing_product_is_rejected():
    payload=portfolio(); payload["products"]=payload["products"][:-1]
    with pytest.raises(ProofRoomError,match="missing governed product profiles"):
        build_capitalroom(phase0_snapshot=phase0(),incarnation_receipt=incarnation(),wave_receipts=wave_receipts(),product_portfolio=payload,vertical_registry=vertical_registry(),generated_at=GENERATED)

def test_bound_capabilities_are_not_executed():
    bound=make_room()["proof_sections"]["operational_proof"]["bound_capabilities"]
    assert len(bound)==8 and all(row["execution_status"]=="NOT_EXECUTED" for row in bound)

def test_locked_capabilities_are_refusal_proof():
    refusal=make_room()["proof_sections"]["refusal_proof"]
    assert refusal["status"]=="PROVEN" and refusal["locked_capability_count"]==8
    assert all(row["status"]=="LOCKED" for row in refusal["locked_capabilities"])

def test_commercial_truth_guards_are_false():
    truth=make_room()["proof_sections"]["product_proof"]["commercial_truth"]
    assert truth and all(value is False for value in truth.values())

def test_commercial_overclaim_is_rejected():
    room=make_room(); changed=copy.deepcopy(room)
    changed["proof_sections"]["product_proof"]["commercial_truth"]["revenue_proven"]=True
    with pytest.raises(ProofRoomError,match="overclaimed"): validate_capitalroom(changed)

def test_external_release_authority_is_rejected():
    room=make_room(); changed=copy.deepcopy(room)
    changed["authority"]["external_release_authorized"]=True
    with pytest.raises(ProofRoomError,match="external release"): validate_capitalroom(changed)

def test_room_tamper_is_detected():
    room=make_room(); changed=copy.deepcopy(room)
    changed["proof_sections"]["refusal_proof"]["locked_capability_count"]=7
    with pytest.raises(ProofRoomError,match="fingerprint mismatch"): validate_capitalroom(changed)

def test_non_authority_claims_are_proven():
    claims=make_room()["proof_sections"]["architecture_proof"]
    rows=[row for row in claims if "composition" in row["claim"].lower() or "Twin" in row["claim"] or "Continuous Assurance" in row["claim"]]
    assert len(rows)==3 and all(row["status"]=="PROVEN" for row in rows)

def test_readme_has_all_proof_sections():
    text=render_capitalroom_readme(make_room())
    for heading in ("## Architecture Proof","## Operational Proof","## Refusal Proof","## Product Proof","## Truth Boundary"):
        assert heading in text

def test_readme_states_revenue_not_proven():
    assert "Revenue proven: **false**" in render_capitalroom_readme(make_room())

def test_write_room_creates_seven_files(tmp_path: Path):
    manifest=write_capitalroom(make_room(),tmp_path); validate_manifest(tmp_path,manifest)
    names={p.name for p in tmp_path.iterdir()}
    assert names=={"PROOF_ROOM.json","ARCHITECTURE_PROOF.json","OPERATIONAL_PROOF.json","REFUSAL_PROOF.json","PRODUCT_PROOF.json","README.md","MANIFEST.json"}

def test_manifest_validates_clean_room(tmp_path: Path):
    manifest=write_capitalroom(make_room(),tmp_path)
    validate_manifest(tmp_path,manifest)
    assert len(manifest["files"])==6

def test_manifest_detects_tamper(tmp_path: Path):
    manifest=write_capitalroom(make_room(),tmp_path)
    (tmp_path/"README.md").write_text("changed\n")
    with pytest.raises(ProofRoomError,match="manifest hash mismatch"): validate_manifest(tmp_path,manifest)
