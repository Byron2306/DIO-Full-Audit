from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from products.media_incarnation import ACCEPTANCE_TOKEN,MediaIncarnationError,build_media_incarnation,verify_media_proof
from products.media_incarnation_gauntlet import run_gauntlet


@pytest.fixture(scope="module")
def built(tmp_path_factory:pytest.TempPathFactory)->dict:
    return build_media_incarnation(output_dir=tmp_path_factory.mktemp("phase16-1")/"media")


def test_dio_nichefoundry_adapter_is_invoked_without_native_claim(built:dict)->None:
    receipt=json.loads((Path(built["output_dir"])/"strategy/NICHEFOUNDRY_ADAPTER_RECEIPT.json").read_text())
    assert receipt["binding_state"]=="DIO_ADAPTER_EXECUTION"
    assert receipt["live_adapter_invoked"] is True
    assert receipt["native_engine_invoked"] is False
    assert receipt["request"]["requested_outputs"]


def test_real_ad_carousel_and_thumbnail_assets_render(built:dict)->None:
    root=Path(built["output_dir"])
    expected={"media/ads/LINKEDIN_1200x628.png":(1200,628),"media/ads/SQUARE_1080x1080.png":(1080,1080),
      "media/youtube/THUMBNAIL.png":(1280,720)}
    for rel,size in expected.items():
        with Image.open(root/rel) as image:assert image.size==size and image.mode=="RGB"
    assert len(list((root/"media/carousel").glob("SLIDE_*.png")))==5


def test_full_script_narration_and_captions_are_material(built:dict)->None:
    root=Path(built["output_dir"]);script=json.loads((root/"strategy/FULL_VIDEO_SCRIPT.json").read_text())
    assert len(script["scenes"])==6
    assert sum(len(row["narration"].split()) for row in script["scenes"])>100
    assert (root/"media/youtube/NARRATION.wav").stat().st_size>1_000_000
    assert (root/"media/youtube/CAPTIONS.srt").read_text().count("-->")==6


def test_final_video_has_real_video_and_audio_streams(built:dict)->None:
    root=Path(built["output_dir"]);video=root/"media/youtube/FINAL_VIDEO.mp4"
    assert video.read_bytes()[4:8]==b"ftyp" and video.stat().st_size>500_000
    streams={row["codec_type"] for row in built["media"]["probe"]["streams"]}
    assert streams=={"video","audio"}
    assert built["media"]["duration_seconds"]>=30


def test_sophia_and_release_boundaries_survive_media_production(built:dict)->None:
    root=Path(built["output_dir"]);review=json.loads((root/"strategy/SOPHIA_MEDIA_REVIEW.json").read_text())
    assert review["review_state"]=="PASS" and review["boundary_language_present"]
    receipt=built["receipt"]
    assert receipt["network_used"] is False
    assert receipt["external_publication"]=="REFUSE"
    assert receipt["media_spend"]=="REFUSE"
    assert receipt["external_send"]=="REFUSE"
    assert receipt["human_gate"]=="NEEDS_YOU"


def test_evidex_manifest_covers_every_media_byte(built:dict)->None:
    root=Path(built["output_dir"]);proof=built["proof_manifest"];verify_media_proof(root,proof)
    observed={row["path"] for row in proof["artifacts"]}
    assert "media/youtube/FINAL_VIDEO.mp4" in observed
    assert "media/youtube/NARRATION.wav" in observed
    assert "media/youtube/THUMBNAIL.png" in observed


def test_media_tampering_refuses_without_dirtying_canonical_output(built:dict,tmp_path:Path)->None:
    source=Path(built["output_dir"]);probe=tmp_path/"probe";shutil.copytree(source,probe)
    target=probe/"media/ads/LINKEDIN_1200x628.png";target.write_bytes(target.read_bytes()+b"TAMPER")
    with pytest.raises(MediaIncarnationError,match="integrity failure"):verify_media_proof(probe,built["proof_manifest"])
    verify_media_proof(source,built["proof_manifest"])


def test_phase16_1_media_gauntlet(tmp_path:Path)->None:
    receipt=run_gauntlet(output_dir=tmp_path/"gauntlet")
    assert receipt["acceptance_token"]==ACCEPTANCE_TOKEN
    assert receipt["nichefoundry_adapter_execution"]=="PASS" and receipt["native_nichefoundry_execution"]=="REFUSE"
    assert receipt["video_rendering"]=="PASS"
    assert receipt["canonical_output_integrity"]=="PASS"
    assert receipt["external_publication"]=="REFUSE"

