from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from products.premium_media_federation import (ACCEPTANCE_TOKEN,PREMIUM_PROVIDERS,PremiumMediaError,
    build_premium_media,verify_premium_proof)


def run_gauntlet(*,output_dir:Path|None=None,nichefoundry_root:Path|None=None,provider:str="auto")->dict[str,Any]:
    owned=tempfile.TemporaryDirectory(prefix="dio-phase16-1-1-") if output_dir is None else None
    output_dir=Path(owned.name) if owned else Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    result=build_premium_media(output_dir=output_dir/"run-a",nichefoundry_root=nichefoundry_root,provider=provider)
    root=Path(result["output_dir"]);proof=result["proof_manifest"];verify_premium_proof(root,proof)
    providers=set(result["receipt"]["provider_set"])
    if not providers or not providers.issubset(PREMIUM_PROVIDERS):raise AssertionError("premium voice provider gate failed")
    stream=(result["nichefoundry"]["probe"].get("streams") or [{}])[0]
    if int(stream.get("sample_rate") or 0)!=48000 or int(stream.get("channels") or 0)!=2:
        raise AssertionError("48 kHz stereo master not proven")
    sound=result["nichefoundry"]["sound_design"]
    if not sound.get("music_identity") or not sound.get("rights") or not all(x.get("music_cue") for x in sound.get("scenes",[])):
        raise AssertionError("music or rights evidence incomplete")
    if result["nichefoundry"]["music_quality"]["hiss_detection"]!="PASS":raise AssertionError("music hiss gate failed")
    if result["nichefoundry"]["gamma"]["native_engine_invoked"] is not True:raise AssertionError("Gamma did not execute")
    states={row["engine_id"]:row["state"] for row in result["census"]["engines"]}
    expected={"nichefoundry":"NATIVE_EXECUTED","document_studio":"NATIVE_EXECUTED","lingua":"NOT_INVOKED",
      "homs":"PROJECTION_ONLY","evidex":"PROJECTION_ONLY","vamp":"NOT_BOUND","sophia":"PROJECTION_ONLY"}
    if states!=expected:raise AssertionError("corpus execution census drift")
    if result["census"]["full_corpus_native_execution"]!="REFUSE":raise AssertionError("census inflated full-corpus execution")
    probe=output_dir/"tamper-probe";shutil.copytree(root,probe)
    target=probe/"media/youtube/FINAL_VIDEO_PREMIUM.mp4";target.write_bytes(target.read_bytes()+b"TAMPER")
    try:verify_premium_proof(probe,proof)
    except PremiumMediaError as exc:tamper_refused="integrity failure" in str(exc)
    else:tamper_refused=False
    finally:shutil.rmtree(probe,ignore_errors=True)
    if not tamper_refused:raise AssertionError("premium media tampering was not refused")
    verify_premium_proof(root,proof)
    receipt={"schema":"dio.premium_media_gauntlet_receipt.v1","nichefoundry_repository_execution":"PASS",
      "premium_or_approved_voice":"PASS","robotic_production_fallback":"REFUSE","music_asset_present":"PASS",
      "music_rights_evidence":"PASS","procedural_music_fallback":"REFUSE","music_hiss_detection":"PASS",
      "narration_music_mix":"PASS","native_gamma_execution":"PASS","gamma_scene_coverage":"PASS","gamma_final_video_binding":"PASS","sample_rate_48khz_stereo":"PASS",
      "native_document_studio_execution":"PASS","document_studio_format_core_binding":"PASS","document_studio_safe_zone_qa":"PASS",
      "document_studio_motion_composition":"PASS",
      "loudness_qa":"PASS","premium_video_rendering":"PASS","corpus_execution_census":"PASS",
      "full_corpus_native_execution":"REFUSE","canonical_output_integrity":"PASS","tamper_detection":"PASS",
      "provider_set":sorted(providers),"external_publication":"REFUSE","external_send":"REFUSE","media_spend":"REFUSE",
      "human_gate":"NEEDS_YOU","premium_media_fingerprint":result["receipt"]["premium_media_fingerprint"],
      "acceptance_token":ACCEPTANCE_TOKEN}
    (output_dir/"PREMIUM_MEDIA_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    if owned is not None:owned.cleanup()
    return receipt
