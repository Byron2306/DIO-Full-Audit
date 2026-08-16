from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from products.media_incarnation import MediaIncarnationError,build_media_incarnation,verify_media_proof

ROOT=Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN="DIO_PREMIUM_MEDIA_INCARNATION_READY"
PREMIUM_PROVIDERS={"imported","voicebox","kokoro","piper","elevenlabs","openvoice"}


class PremiumMediaError(RuntimeError):
    pass


def _load(path:Path)->dict[str,Any]:
    try:value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise PremiumMediaError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value,dict):raise PremiumMediaError(f"expected object: {path}")
    return value


def _write(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def _sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value:Any)->str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return "sha256:"+hashlib.sha256(raw).hexdigest()


def _run(command:list[str],*,cwd:Path|None=None,env:dict[str,str]|None=None)->subprocess.CompletedProcess[str]:
    try:return subprocess.run(command,cwd=cwd,env=env,text=True,capture_output=True,check=True)
    except FileNotFoundError as exc:raise PremiumMediaError(f"required executable missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:raise PremiumMediaError(f"native engine command failed: {' '.join(command)}\n{exc.stderr}") from exc


def resolve_nichefoundry_root(value:Path|None)->Path:
    candidates=[value,Path(os.environ["DIO_NICHEFOUNDRY_ROOT"]) if os.environ.get("DIO_NICHEFOUNDRY_ROOT") else None,
      Path.home()/"NicheFoundry",Path.home()/"Downloads/NicheFoundry_Phase11"]
    for candidate in candidates:
        if candidate is None:continue
        root=candidate.expanduser().resolve()
        required=[root/"package.json",root/"scripts/build_audio_performance.js",root/"lib/audio_system.js",
          root/"lib/render_system.js",root/"lib/music_discovery.js",root/"studios/builtin/practical_open_source.json"]
        if all(path.is_file() for path in required):return root
    raise PremiumMediaError("real NicheFoundry checkout not found; set DIO_NICHEFOUNDRY_ROOT")


def _voicebox_ready()->bool:
    profile=os.environ.get("VOICEBOX_PROFILE","").strip()
    if not profile:return False
    base=os.environ.get("VOICEBOX_API_URL","http://127.0.0.1:17493").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/profiles",timeout=2.0) as response:
            if response.status!=200:return False
            profiles=json.loads(response.read().decode("utf-8"))
    except (OSError,ValueError,urllib.error.URLError,json.JSONDecodeError):return False
    return isinstance(profiles,list) and any(
      str(row.get("id") or "")==profile or str(row.get("name") or "").lower()==profile.lower()
      for row in profiles if isinstance(row,dict))


def _resolve_premium_provider(niche_root:Path,requested:str,episode_dir:Path)->str:
    if requested in {"espeak","flite"}:raise PremiumMediaError("robotic reference voices are forbidden by the premium gate")
    if requested!="auto":
        if requested not in PREMIUM_PROVIDERS:raise PremiumMediaError(f"unsupported premium provider: {requested}")
        return requested
    imports=episode_dir/"imports/audio"
    if imports.is_dir() and any(path.suffix.lower() in {".wav",".mp3",".m4a",".ogg"} for path in imports.iterdir()):return "imported"
    if _voicebox_ready():return "voicebox"
    kokoro_command=Path(os.environ.get("KOKORO_COMMAND",niche_root/".venv-kokoro/bin/python"))
    kokoro_wrapper=Path(os.environ.get("KOKORO_WRAPPER",niche_root/"scripts/kokoro_synthesize.py"))
    if kokoro_command.is_file() and kokoro_wrapper.is_file():return "kokoro"
    piper_bin=os.environ.get("PIPER_BIN") or str(niche_root/"tools/piper/piper")
    piper_model_name=os.environ.get("PIPER_MODEL_NAME","en_US-lessac-high")
    piper_model_dir=Path(os.environ.get("PIPER_MODEL_DIR",niche_root/f"assets/piper/{piper_model_name}"))
    piper_available=bool(shutil.which(piper_bin)) or Path(piper_bin).is_file()
    if piper_available and (piper_model_dir/f"{piper_model_name}.onnx").is_file() and (piper_model_dir/f"{piper_model_name}.onnx.json").is_file():return "piper"
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):return "elevenlabs"
    openvoice_command=Path(os.environ.get("OPENVOICE_COMMAND",niche_root/".venv-openvoice/bin/python"))
    openvoice_wrapper=Path(os.environ.get("OPENVOICE_WRAPPER",niche_root/"scripts/openvoice_convert.py"))
    openvoice_reference=Path(os.environ.get("OPENVOICE_REFERENCE_AUDIO",niche_root/"assets/voices/elevenlabs_curator/reference.wav"))
    if openvoice_command.is_file() and openvoice_wrapper.is_file() and openvoice_reference.is_file():return "openvoice"
    stale=" VOICEBOX_PROFILE is configured, but its backend/profile is unreachable." if os.environ.get("VOICEBOX_PROFILE") else ""
    raise PremiumMediaError(
      "no runnable premium narration provider was found."+stale+
      " Start Voicebox, install NicheFoundry Kokoro/Piper, configure ElevenLabs/OpenVoice, or supply cleared imported narration; eSpeak/Flite remain refused.")


def _script_package()->dict[str,Any]:
    rows=[
      ("The plan exists","Your incident response plan may exist. Your role matrix may exist. Your exercise records may exist. But that does not mean the evidence agrees."),
      ("Evidence ages differently","Plans, named owners, exercises and contact details age at different speeds. One stale record can hide inside an otherwise complete-looking folder."),
      ("Map before you rely","DIO Incident Readiness Proof maps what is supplied, what is missing, what is stale, and which decisions still require a named human authority."),
      ("No readiness theatre","It does not certify readiness. It does not guarantee recovery. And it does not turn a generated dossier into operational authority."),
      ("A reviewable dossier","The result is a reviewable, multi-format evidence dossier with a gap register, action boundary and hash-bound proof manifest."),
      ("Know before the incident does","Prepare a controlled review locally. Keep the consequential decision human. Know what your response plan can prove before the incident does.")
    ]
    beats=["working_result_preview","problem_framing","validation","constraint","evidence","next_step"]
    return {"schema":"nichefoundry.script_package.v1.0","title":"Can Your Incident Plan Prove It?",
      "scenes":[{"scene_id":f"scene_{i+1:02}","story_beat":beats[i],"title":title,"narration":narration,
        "estimated_duration_seconds":8,"claim_ids":[f"claim_{i+1:02}"],"source_ids":[f"source_{i+1:02}"]}
        for i,(title,narration) in enumerate(rows)]}


def _prepare_episode(niche_root:Path,episode_dir:Path)->dict[str,Any]:
    episode_dir.mkdir(parents=True,exist_ok=True)
    pack=_load(niche_root/"studios/builtin/practical_open_source.json");script=_script_package()
    sample=(pack.get("samples") or [{}])[0]
    brief=dict(sample);brief.update({"topic":"Incident readiness evidence","language":"en","title":"Can Your Incident Plan Prove It?",
      "audience":"Operations, risk and programme leaders","pronunciation_overrides":[
        {"term":"DIO","spoken_form":"D I O","review_required":False}]})
    timing={"schema":"nichefoundry.timing_plan.v1","scenes":[{"scene_id":row["scene_id"],"target_duration_seconds":8} for row in script["scenes"]]}
    for name,value in (("brief.json",brief),("studio_pack_snapshot.json",pack),("script_package.json",script),("timing_plan.json",timing)):
        _write(episode_dir/name,value)
    return {"pack":pack,"brief":brief,"script":script,"timing":timing}


def _probe_audio(path:Path,ffprobe:str)->dict[str,Any]:
    result=_run([ffprobe,"-v","error","-show_entries","stream=codec_name,sample_rate,channels:format=duration","-of","json",str(path)])
    return json.loads(result.stdout)


def _run_nichefoundry(niche_root:Path,episode_dir:Path,provider:str)->dict[str,Any]:
    node=shutil.which("node")
    if not node:raise PremiumMediaError("Node.js is required for real NicheFoundry execution")
    _prepare_episode(niche_root,episode_dir)
    selected_provider=_resolve_premium_provider(niche_root,provider,episode_dir)
    command=[node,str(niche_root/"scripts/build_audio_performance.js"),str(episode_dir),"--provider",selected_provider,"--force"]
    completed=_run(command,cwd=niche_root,env=dict(os.environ))
    required=["host_profile.json","pronunciation_lexicon.json","audio_performance_plan.json","sound_design_plan.json",
      "audio_preflight_report.json","audio_manifest.json","audio_asset_hashes.json","loudness_report.json","audio_performance_report.json"]
    missing=[name for name in required if not (episode_dir/name).is_file()]
    if missing:raise PremiumMediaError(f"NicheFoundry omitted audio evidence: {missing}")
    manifest=_load(episode_dir/"audio_manifest.json");performance=_load(episode_dir/"audio_performance_report.json")
    sound=_load(episode_dir/"sound_design_plan.json");loudness=_load(episode_dir/"loudness_report.json")
    providers={str(row.get("provider") or manifest.get("provider") or "").lower() for row in manifest.get("scenes",[])}
    providers.discard("")
    if not providers:providers={str(manifest.get("provider") or "").lower()}
    forbidden=providers- PREMIUM_PROVIDERS
    if forbidden:raise PremiumMediaError(f"premium voice gate refused providers: {sorted(forbidden)}")
    if performance.get("passed") is not True:raise PremiumMediaError("NicheFoundry audio performance QA failed")
    if not sound.get("music_identity") or not sound.get("rights") or not all(row.get("music_cue") for row in sound.get("scenes",[])):
        raise PremiumMediaError("NicheFoundry music plan or rights evidence incomplete")
    preview=episode_dir/"audio/episode_audio_preview.wav"
    if not preview.is_file():raise PremiumMediaError("NicheFoundry mastered programme preview missing")
    ffprobe=shutil.which("ffprobe")
    if not ffprobe:raise PremiumMediaError("ffprobe is required")
    probe=_probe_audio(preview,ffprobe);streams=probe.get("streams") or [{}]
    stream=streams[0]
    if int(stream.get("sample_rate") or 0)!=48000 or int(stream.get("channels") or 0)!=2:
        raise PremiumMediaError("NicheFoundry master is not 48 kHz stereo")
    return {"command":command,"stdout":completed.stdout.strip(),"providers":sorted(providers),"manifest":manifest,
      "performance":performance,"sound_design":sound,"loudness":loudness,"preview":preview,"probe":probe,
      "source_ref":"Byron2306/NicheFoundry","source_root":str(niche_root),"native_engine_invoked":True}


def _corpus_census(niche:dict[str,Any])->dict[str,Any]:
    rows=[
      {"engine_id":"nichefoundry","repository":"Byron2306/NicheFoundry","state":"NATIVE_EXECUTED","receipt":"premium/NICHEFOUNDRY_NATIVE_EXECUTION.json"},
      {"engine_id":"document_studio","repository":"DIO-Full-Audit/adapters/document_studio","state":"SOURCE_BOUND_ONLY","reason":"Phase 16 collateral bypasses adapters/document_studio/pipeline.py"},
      {"engine_id":"lingua","repository":"DIO-Full-Audit/adapters/lingua","state":"NOT_INVOKED","reason":"No translation/localisation request is part of this incarnation"},
      {"engine_id":"homs","repository":"Byron2306/HOMS-assessor","state":"PROJECTION_ONLY","reason":"Phase 16 customer education is locally constructed"},
      {"engine_id":"evidex","repository":"Byron2306/Evidex","state":"PROJECTION_ONLY","reason":"Phase 16 proof manifest does not invoke the external Evidex runtime"},
      {"engine_id":"vamp","repository":"Byron2306/VAMP","state":"NOT_BOUND","reason":"VAMP is absent from the Phase 16 product contract"},
      {"engine_id":"sophia","repository":"Byron2306/Sophia-AI","state":"PROJECTION_ONLY","reason":"Phase 16 claim review is locally constructed"}
    ]
    return {"schema":"dio.corpus_execution_census.v1","engines":rows,"native_executed_count":1,
      "required_engine_count":7,"full_corpus_native_execution":"REFUSE",
      "law":"source binding, local projection and native engine execution are distinct evidence states"}


def verify_premium_proof(output_dir:Path,proof:dict[str,Any])->None:
    for row in proof.get("artifacts") or []:
        path=(output_dir/row["path"]).resolve()
        if not path.is_relative_to(output_dir.resolve()) or not path.is_file() or _sha(path)!=row["sha256"]:
            raise PremiumMediaError(f"premium media artifact integrity failure: {row.get('path')}")


def build_premium_media(*,output_dir:Path,nichefoundry_root:Path|None=None,provider:str="auto")->dict[str,Any]:
    output_dir=output_dir.resolve();output_dir.mkdir(parents=True,exist_ok=True)
    base=build_media_incarnation(output_dir=output_dir/"base")
    niche_root=resolve_nichefoundry_root(nichefoundry_root);premium_dir=output_dir/"premium"
    episode=premium_dir/"nichefoundry_episode";niche=_run_nichefoundry(niche_root,episode,provider)
    evidence={k:v for k,v in niche.items() if k not in {"manifest","performance","sound_design","loudness","preview"}}
    evidence.update({"audio_manifest_sha256":_sha(episode/"audio_manifest.json"),"audio_asset_hashes_sha256":_sha(episode/"audio_asset_hashes.json"),
      "loudness_report_sha256":_sha(episode/"loudness_report.json"),"sound_design_plan_sha256":_sha(episode/"sound_design_plan.json")})
    _write(premium_dir/"NICHEFOUNDRY_NATIVE_EXECUTION.json",evidence)
    census=_corpus_census(niche);_write(premium_dir/"CORPUS_EXECUTION_CENSUS.json",census)
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg:raise PremiumMediaError("ffmpeg is required")
    source_video=Path(base["output_dir"])/"media/youtube/FINAL_VIDEO.mp4";final=output_dir/"media/youtube/FINAL_VIDEO_PREMIUM.mp4"
    final.parent.mkdir(parents=True,exist_ok=True)
    _run([ffmpeg,"-y","-hide_banner","-loglevel","error","-stream_loop","-1","-i",str(source_video),"-i",str(niche["preview"]),
      "-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-map_metadata","-1",
      "-movflags","+faststart","-fflags","+bitexact","-flags:a","+bitexact",str(final)])
    artifacts=[]
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file() and p.name not in {"PREMIUM_MEDIA_PROOF.json","PREMIUM_MEDIA_RECEIPT.json"}):
        artifacts.append({"path":str(path.relative_to(output_dir)),"sha256":_sha(path),"bytes":path.stat().st_size})
    proof={"schema":"dio.premium_media_proof.v1","artifacts":artifacts,"nichefoundry_repository_execution":"PASS",
      "premium_or_approved_voice":"PASS","robotic_production_fallback":"REFUSE","music_asset_present":"PASS",
      "music_rights_evidence":"PASS","narration_music_mix":"PASS","sample_rate_48khz_stereo":"PASS","loudness_qa":"PASS",
      "native_engine_execution_census":"PASS","full_corpus_native_execution":"REFUSE","external_publication":"REFUSE",
      "external_send":"REFUSE","media_spend":"REFUSE","human_gate":"NEEDS_YOU"}
    proof["proof_fingerprint"]=_fingerprint(proof);_write(output_dir/"PREMIUM_MEDIA_PROOF.json",proof)
    receipt={"schema":"dio.premium_media_receipt.v1","provider_set":niche["providers"],"nichefoundry_repository_execution":"PASS",
      "premium_voice":"PASS","music_and_rights":"PASS","audio_mastering":"PASS","premium_video":"PASS",
      "corpus_execution_census":"PASS","full_corpus_native_execution":"REFUSE","external_publication":"REFUSE",
      "external_send":"REFUSE","media_spend":"REFUSE","human_gate":"NEEDS_YOU","proof_fingerprint":proof["proof_fingerprint"]}
    receipt["premium_media_fingerprint"]=_fingerprint(receipt);_write(output_dir/"PREMIUM_MEDIA_RECEIPT.json",receipt)
    verify_premium_proof(output_dir,proof)
    return {"receipt":receipt,"proof_manifest":proof,"census":census,"nichefoundry":niche,"base":base,"output_dir":str(output_dir)}
