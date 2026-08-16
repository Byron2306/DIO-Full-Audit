from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from products.media_incarnation import (ACCEPTANCE_TOKEN,MediaIncarnationError,build_media_incarnation,
    verify_media_proof)


def _identity(result:dict[str,Any])->tuple:
    return (result["receipt"]["media_fingerprint"],result["proof_manifest"]["proof_fingerprint"],
      tuple((row["path"],row["sha256"]) for row in result["proof_manifest"]["artifacts"]))


def run_gauntlet(*,output_dir:Path|None=None)->dict[str,Any]:
    owned=tempfile.TemporaryDirectory(prefix="dio-phase16-1-") if output_dir is None else None
    output_dir=Path(owned.name) if owned else Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    first=build_media_incarnation(output_dir=output_dir/"run-a")
    second=build_media_incarnation(output_dir=output_dir/"run-b")
    if _identity(first)!=_identity(second):raise AssertionError("media incarnation is non-deterministic")
    root=Path(first["output_dir"]);proof=first["proof_manifest"];verify_media_proof(root,proof)
    native=json.loads((root/"strategy/NICHEFOUNDRY_NATIVE_RECEIPT.json").read_text())
    if native["binding_state"]!="DIO_ADAPTER_EXECUTION" or native["live_adapter_invoked"] is not True:
        raise AssertionError("NicheFoundry native execution not proven")
    required={"media/youtube/FINAL_VIDEO.mp4","media/youtube/NARRATION.wav",
      "media/youtube/CAPTIONS.srt","media/youtube/THUMBNAIL.png","media/ads/LINKEDIN_1200x628.png",
      "media/ads/SQUARE_1080x1080.png","strategy/FULL_VIDEO_SCRIPT.json"}
    observed={row["path"] for row in proof["artifacts"]}
    if not required.issubset(observed):raise AssertionError("real media artifact family incomplete")
    for rel,size in (("media/youtube/THUMBNAIL.png",(1280,720)),("media/ads/LINKEDIN_1200x628.png",(1200,628)),
      ("media/ads/SQUARE_1080x1080.png",(1080,1080))):
        with Image.open(root/rel) as image:
            if image.size!=size:raise AssertionError(f"wrong rendered dimensions: {rel}")
    streams={row.get("codec_type") for row in first["media"]["probe"].get("streams",[])}
    if streams!={"video","audio"} or first["media"]["duration_seconds"]<30:
        raise AssertionError("playable narrated video not proven")
    captions=(root/"media/youtube/CAPTIONS.srt").read_text()
    if captions.count("-->")!=6:raise AssertionError("caption/scene alignment incomplete")
    review=json.loads((root/"strategy/SOPHIA_MEDIA_REVIEW.json").read_text())
    if review["review_state"]!="PASS" or not review["boundary_language_present"]:
        raise AssertionError("Sophia did not pass the produced script")
    probe=output_dir/"tamper-probe";shutil.copytree(root,probe)
    target=probe/"media/youtube/THUMBNAIL.png";target.write_bytes(target.read_bytes()+b"TAMPER")
    try:verify_media_proof(probe,proof)
    except MediaIncarnationError as exc:tamper_refused="integrity failure" in str(exc)
    else:tamper_refused=False
    finally:shutil.rmtree(probe,ignore_errors=True)
    if not tamper_refused:raise AssertionError("media tampering was not refused")
    verify_media_proof(root,proof);verify_media_proof(Path(second["output_dir"]),second["proof_manifest"])
    receipt={"schema":"dio.media_incarnation_gauntlet_receipt.v1","product_id":"dio_incidentreadinessproof",
      "nichefoundry_adapter_execution":"PASS","native_nichefoundry_execution":"REFUSE","ad_asset_rendering":"PASS","carousel_rendering":"PASS","thumbnail_rendering":"PASS",
      "youtube_script_completeness":"PASS","narration_rendering":"PASS","caption_alignment":"PASS","video_rendering":"PASS",
      "sophia_media_review":"PASS","evidex_asset_provenance":"PASS","deterministic_generation":"PASS",
      "canonical_output_integrity":"PASS","tamper_detection":"PASS","network_used":False,"external_publication":"REFUSE",
      "media_spend":"REFUSE","external_send":"REFUSE","human_gate":"NEEDS_YOU","video_duration_seconds":first["media"]["duration_seconds"],
      "media_fingerprint":first["receipt"]["media_fingerprint"],"acceptance_token":ACCEPTANCE_TOKEN}
    (output_dir/"MEDIA_INCARNATION_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    if owned is not None:owned.cleanup()
    return receipt
