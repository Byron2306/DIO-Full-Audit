from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from products.premium_media_federation import (ACCEPTANCE_TOKEN,PREMIUM_PROVIDERS,PremiumMediaError,
    build_premium_media,resolve_nichefoundry_root,verify_premium_proof)
from products.premium_media_gauntlet import run_gauntlet


@pytest.fixture(scope="module")
def settings()->tuple[Path,str]:
    root=resolve_nichefoundry_root(Path(os.environ["DIO_NICHEFOUNDRY_ROOT"]) if os.environ.get("DIO_NICHEFOUNDRY_ROOT") else None)
    return root,os.environ.get("DIO_NICHEFOUNDRY_VOICE_PROVIDER","auto")


@pytest.fixture(scope="module")
def built(tmp_path_factory:pytest.TempPathFactory,settings:tuple[Path,str])->dict:
    root,provider=settings
    return build_premium_media(output_dir=tmp_path_factory.mktemp("phase16-1-1")/"premium",nichefoundry_root=root,provider=provider)


def test_real_nichefoundry_repository_is_executed(built:dict)->None:
    receipt=json.loads((Path(built["output_dir"])/"premium/NICHEFOUNDRY_NATIVE_EXECUTION.json").read_text())
    assert receipt["native_engine_invoked"] is True
    assert receipt["source_ref"]=="Byron2306/NicheFoundry"


def test_premium_voice_gate_refuses_robotic_fallback(built:dict)->None:
    providers=set(built["receipt"]["provider_set"])
    assert providers and providers.issubset(PREMIUM_PROVIDERS)
    assert not providers.intersection({"espeak","flite"})


def test_music_rights_mastering_and_loudness_are_real(built:dict)->None:
    niche=built["nichefoundry"];sound=niche["sound_design"]
    assert sound["music_identity"] and sound["rights"]
    assert all(row["music_cue"] for row in sound["scenes"])
    assert niche["performance"]["passed"] is True
    stream=niche["probe"]["streams"][0]
    assert int(stream["sample_rate"])==48000 and int(stream["channels"])==2
    assert niche["loudness"]["episode"]


def test_premium_video_and_proof_are_material(built:dict)->None:
    root=Path(built["output_dir"]);video=root/"media/youtube/FINAL_VIDEO_PREMIUM.mp4"
    assert video.read_bytes()[4:8]==b"ftyp" and video.stat().st_size>500_000
    verify_premium_proof(root,built["proof_manifest"])


def test_corpus_census_never_confuses_projection_with_execution(built:dict)->None:
    states={row["engine_id"]:row["state"] for row in built["census"]["engines"]}
    assert states["nichefoundry"]=="NATIVE_EXECUTED"
    assert states["document_studio"]=="SOURCE_BOUND_ONLY"
    assert states["lingua"]=="NOT_INVOKED"
    assert states["homs"]=="PROJECTION_ONLY"
    assert states["evidex"]=="PROJECTION_ONLY"
    assert states["vamp"]=="NOT_BOUND"
    assert states["sophia"]=="PROJECTION_ONLY"
    assert built["census"]["full_corpus_native_execution"]=="REFUSE"


def test_premium_tampering_is_refused_without_dirtying_canonical(built:dict,tmp_path:Path)->None:
    source=Path(built["output_dir"]);probe=tmp_path/"probe";shutil.copytree(source,probe)
    target=probe/"media/youtube/FINAL_VIDEO_PREMIUM.mp4";target.write_bytes(target.read_bytes()+b"TAMPER")
    with pytest.raises(PremiumMediaError,match="integrity failure"):verify_premium_proof(probe,built["proof_manifest"])
    verify_premium_proof(source,built["proof_manifest"])


def test_phase16_1_1_premium_gauntlet(tmp_path:Path,settings:tuple[Path,str])->None:
    root,provider=settings;receipt=run_gauntlet(output_dir=tmp_path/"gauntlet",nichefoundry_root=root,provider=provider)
    assert receipt["acceptance_token"]==ACCEPTANCE_TOKEN
    assert receipt["nichefoundry_repository_execution"]=="PASS"
    assert receipt["premium_or_approved_voice"]=="PASS"
    assert receipt["music_rights_evidence"]=="PASS"
    assert receipt["full_corpus_native_execution"]=="REFUSE"

