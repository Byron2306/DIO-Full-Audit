"""Offline sample, amp and stem rendering for Sonoris listening candidates."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from products.sonoris_metal_patterns import metal_models
from products.sonoris_dark_synth_renderer import (
    render_dark_aggro_triple_saw,
)

AMP_URI = "http://guitarix.sourceforge.net/plugins/gxmetal_head#metal_head"
FUZZ_URI = "http://guitarix.sourceforge.net/plugins/gx_fuzz_#fuzz_"
GTX_MUTE = Path("/home/byron/fusion-instruments/guitar/Metal-GTX/UI_METAL-GTX/Programs/Individual Patchs/SFIZZ_CLEAN/METAL-GTX_Full/Mute_Down.sfz")
GTX_SUSTAIN = GTX_MUTE.with_name("Sus_Down.sfz")


def _run(args: list[str]) -> None:
    result=subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=900)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed: {result.stderr[-1000:]}")


def _ffmpeg(source: Path, dest: Path, filter_chain: str, *, mono: bool = True) -> None:
    command=["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(source),"-af",filter_chain]
    if mono: command += ["-ac","1"]
    command += ["-ar","44100","-c:a","pcm_s16le",str(dest)]
    _run(command)


def _sample_role(out: Path, role: str, rows: list[dict[str, Any]], module_id: str,
                 module: Mapping[str, Any], bpm: int, modules: Mapping[str, str], sf2: Path,
                 midi_writer: Callable[..., None], *, name: str, shift: float = 0, velocity: int = 0) -> Path:
    midi=out/f"{name}.mid"; raw=out/f"{name}.raw.wav"
    selected=dict(modules);selected[role]=module_id
    pitch_shift=12 if role=="bass" and "sfz" in module else 0
    midi_writer(midi,{role:rows},bpm,selected,single_role=role,pitch_shift=pitch_shift,time_shift=shift,velocity_shift=velocity)
    if "sfz" in module:
        _run(["sfizz_render","--sfz",module["sfz"],"--midi",str(midi),"--wav",str(raw),"--samplerate","44100"])
    else:
        _run(["fluidsynth","-ni","-F",str(raw),"-r","44100",str(sf2),str(midi)])
    return raw


def _guitar_fx(raw: Path, out: Path, tone: Mapping[str, Any], *, drive: float,
               processed_source: bool, clean: bool, doom: bool, lead: bool) -> None:
    mono=out.with_suffix(".di.wav")
    _ffmpeg(raw,mono,"aformat=sample_fmts=flt",mono=True)
    signal=mono
    if not processed_source and not clean:
        if doom and shutil.which("lv2apply"):
            fuzz=out.with_suffix(".fuzz.wav")
            _run(["lv2apply","-i",str(signal),"-o",str(fuzz),"-c","DRIVE","0.74","-c","TONE","0.38",FUZZ_URI])
            signal=fuzz
        amp=out.with_suffix(".amp.wav")
        if shutil.which("lv2apply"):
            _run(["lv2apply","-i",str(signal),"-o",str(amp),"-c","DRIVE",str(drive),
                  "-c","TONE",str(tone["tone"]),"-c","PREGAIN",str(tone["pregain"]),
                  "-c","GAIN1","3","-c","HIGHGAIN","1",AMP_URI])
        else:
            _ffmpeg(signal,amp,"volume=4,asoftclip=type=tanh:threshold=0.6")
        signal=amp
    high=110 if clean else tone["highpass_hz"]
    low=7500 if clean else tone["lowpass_hz"]
    filt=f"highpass=f={high},lowpass=f={low},acompressor=threshold=0.11:ratio=2.8:attack=4:release=90"
    room=float(tone.get("room",0))
    if room>0: filt+=f",aecho=0.86:0.12:68:{min(.35,room)}"
    if lead: filt+=",aecho=0.8:0.3:115:0.12"
    elif clean: filt+=",aecho=0.8:0.25:170:0.07"
    _ffmpeg(signal,out,filt)




def _thrash_caps_amp(
    source: Path,
    target: Path,
) -> None:
    """
    Proven Chainsaw Diplomacy thrash amp/cab stage.

    Composition and articulation remain Sonoris-owned.
    This stage supplies the established Chainsaw guitar
    production identity.
    """

    script = (
        Path.home()
        / "polly-grunge-rocker"
        / "scripts"
        / "run_caps_thr_amp.py"
    )

    if not script.is_file():
        raise RuntimeError(
            "THRASH_CAPS_AMP_SCRIPT_MISSING:"
            + str(script)
        )

    _run([
        "python3",
        str(script),
        "--input",
        str(source),
        "--output",
        str(target),
    ])

    if (
        not target.is_file()
        or target.stat().st_size == 0
    ):
        raise RuntimeError(
            "THRASH_CAPS_AMP_EMPTY_OUTPUT"
        )


def _black_metal_terminal_disease(
    source: Path,
    dest: Path,
) -> None:
    """
    Black-metal terminal-disease wall.

    The source guitar remains the harmonic carrier.
    Additional layers deliberately obscure it:

      - burial fuzz
      - guitar-derived feedback ghost
      - broadband hiss
      - narrow-band static rot

    This is intentionally ugly.
    """

    graph = (
        "[0:a]"
        "highpass=f=105,"
        "lowpass=f=6400,"
        "equalizer=f=350:t=q:w=1.0:g=-3,"
        "equalizer=f=1450:t=q:w=1.0:g=4,"
        "equalizer=f=2350:t=q:w=1.1:g=6,"
        "equalizer=f=3900:t=q:w=1.2:g=4,"
        "volume=11dB,"
        "asoftclip="
        "type=hard:"
        "threshold=0.20:"
        "output=0.72:"
        "oversample=8,"
        "acrusher="
        "bits=11:"
        "mix=0.10:"
        "aa=0.85,"
        "acompressor="
        "threshold=0.16:"
        "ratio=3.2:"
        "attack=3:"
        "release=135,"
        "volume=-2.5dB"
        "[MAIN];"

        "[0:a]"
        "highpass=f=650,"
        "lowpass=f=9200,"
        "equalizer=f=1250:t=q:w=0.8:g=5,"
        "equalizer=f=2200:t=q:w=0.7:g=9,"
        "equalizer=f=3400:t=q:w=0.8:g=10,"
        "equalizer=f=5600:t=q:w=1.0:g=7,"
        "volume=19dB,"
        "asoftclip="
        "type=hard:"
        "threshold=0.075:"
        "output=0.48:"
        "oversample=16,"
        "acrusher="
        "bits=8.5:"
        "mix=0.22:"
        "aa=0.65,"
        "aecho="
        "0.94:0.82:"
        "47|83|151|269|487|731:"
        "0.78|0.67|0.54|0.42|0.29|0.18,"
        "tremolo=f=0.23:d=0.38,"
        "acompressor="
        "threshold=0.055:"
        "ratio=8:"
        "attack=12:"
        "release=620,"
        "volume=-9dB"
        "[FB];"

        "[1:a]"
        "highpass=f=2800,"
        "lowpass=f=12800,"
        "equalizer=f=4200:t=q:w=0.8:g=5,"
        "equalizer=f=7200:t=q:w=1.0:g=3,"
        "acrusher="
        "bits=10:"
        "mix=0.16:"
        "aa=0.7,"
        "volume=0.14"
        "[HISS];"

        "[2:a]"
        "highpass=f=900,"
        "lowpass=f=6200,"
        "equalizer=f=1850:t=q:w=0.7:g=5,"
        "equalizer=f=2750:t=q:w=0.65:g=8,"
        "equalizer=f=3900:t=q:w=0.9:g=6,"
        "asoftclip="
        "type=hard:"
        "threshold=0.18:"
        "output=0.65,"
        "acrusher="
        "bits=7.5:"
        "mix=0.28:"
        "aa=0.55,"
        "tremolo=f=0.41:d=0.23,"
        "volume=0.10"
        "[ROT];"

        "[MAIN][FB][HISS][ROT]"
        "amix="
        "inputs=4:"
        "duration=first:"
        "normalize=0,"
        "highpass=f=65,"
        "lowpass=f=12200,"
        "acompressor="
        "threshold=0.16:"
        "ratio=2.4:"
        "attack=22:"
        "release=440,"
        "alimiter=limit=0.93"
        "[OUT]"
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",

        "-i",
        str(source),

        "-f",
        "lavfi",
        "-i",
        (
            "anoisesrc="
            "color=white:"
            "amplitude=0.045:"
            "sample_rate=44100"
        ),

        "-f",
        "lavfi",
        "-i",
        (
            "anoisesrc="
            "color=pink:"
            "amplitude=0.075:"
            "sample_rate=44100"
        ),

        "-filter_complex",
        graph,

        "-map",
        "[OUT]",

        "-ac",
        "1",

        "-ar",
        "44100",

        "-c:a",
        "pcm_s16le",

        str(dest),
    ]

    _run(command)



def _render_nocturne_v4_keys(
    out: Path,
    rows,
    receipt,
    module_id: str,
    module,
) -> Path:
    """
    Render Sonoris-authored key events through isolated Nocturne V4.

    Composition authority stays with Sonoris.
    Nocturne owns timbre only.
    """

    import json
    import os
    import subprocess

    root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    python = (
        root
        / ".venv-nocturne"
        / "bin"
        / "python"
    )

    bridge = (
        root
        / "scripts"
        / "render_sonoris_nocturne_keys.py"
    )

    if not python.is_file():
        raise RuntimeError(
            "NOCTURNE_VENV_MISSING:"
            + str(python)
        )

    if not bridge.is_file():
        raise RuntimeError(
            "NOCTURNE_KEY_BRIDGE_MISSING:"
            + str(bridge)
        )

    request_path = (
        out
        / "keys.nocturne_v4.request.json"
    )

    output = (
        out
        / "keys.wav"
    )

    payload = {
        "schema":
            "dio.sonoris.nocturne_key_render.v1",

        "module":
            module_id,

        "voice":
            module["voice"],

        "timbre":
            dict(module["timbre"]),

        "bpm":
            float(
                receipt["tempo_bpm"]
            ),

        "bars":
            int(
                receipt["bars"]
            ),

        "seed":
            int(
                receipt.get(
                    "seed",
                    1993,
                )
            ),

        "events":
            list(rows),
    }

    request_path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n"
    )

    env = dict(
        os.environ
    )

    env["PYTHONPATH"] = str(
        root
    )

    subprocess.run(
        [
            str(python),
            str(bridge),
            "--request",
            str(request_path),
            "--output",
            str(output),
        ],
        cwd=str(root),
        env=env,
        check=True,
    )

    if (
        not output.is_file()
        or output.stat().st_size == 0
    ):
        raise RuntimeError(
            "NOCTURNE_KEY_RENDER_EMPTY"
        )

    return output


def render_stems(out: Path, events: Mapping[str,list[dict[str,Any]]], receipt: Mapping[str,Any],
                 modules_def: Mapping[str,Mapping[str,Mapping[str,Any]]], sf2: Path,
                 midi_writer: Callable[...,None]) -> list[dict[str,Any]]:
    modules=receipt["modules"]
    bpm=int(receipt["tempo_bpm"])
    genre=str(receipt["genre"])
    song_type=str(
        receipt.get("song_type")
        or ""
    )
    tone=metal_models()["tone_profiles"][receipt.get("tone_profile") or "clean_chime"]
    drive=float(receipt["guitar_drive"] if receipt.get("guitar_drive") is not None else tone["drive"])
    levels=receipt.get("mix_levels") or {}
    is_metal=genre.endswith("_metal") or genre=="black_metal"
    stems=[]
    for role,rows in events.items():
        if not rows: continue
        module_id=modules.get(role,"off")
        module=modules_def[role][module_id]
        if module.get("off"): continue
        if role=="harmony" and is_metal and "sfz" in module:
            for articulation in ("mute","sustain","clean"):
                part=[row for row in rows if row.get("articulation", "sustain")==articulation]
                if not part: continue
                selected_id="gtx_mute" if articulation=="mute" and module_id.startswith("gtx_") and GTX_MUTE.is_file() else module_id
                if articulation=="clean" and module_id=="fsbs_distorted" and GTX_SUSTAIN.is_file():
                    selected_id="gtx_sustain"
                selected=modules_def[role][selected_id]
                for side,shift in (("left",0),("right",.017)):
                    name=f"guitar_{articulation}_{side}"
                    raw=_sample_role(out,role,part,selected_id,selected,bpm,modules,sf2,midi_writer,name=name,shift=shift,velocity=0 if side=="left" else -4)
                    processed=out/f"{name}.wav"
                    _guitar_fx(
                        raw,
                        processed,
                        tone,
                        drive=drive,
                        processed_source=bool(
                            selected.get(
                                "processed_source"
                            )
                        ),
                        clean=(
                            articulation
                            == "clean"
                        ),
                        doom=(
                            genre
                            == "doom_metal"
                        ),
                        lead=False,
                    )

                    if (
                        genre
                        == "thrash_metal"
                        and articulation
                        != "clean"
                    ):
                        caps = (
                            out
                            / (
                                f"{name}"
                                ".thrash_caps.wav"
                            )
                        )

                        _thrash_caps_amp(
                            processed,
                            caps,
                        )

                        processed = caps

                        production_identity = (
                            "THRASH_CAPS_AMP_V1"
                        )

                    if (
                        genre
                        == "black_metal"
                        and articulation
                        != "clean"
                        and str(
                            receipt.get(
                                "black_metal_production"
                            )
                            or "TERMINAL_DISEASE_V1"
                        )
                        == "TERMINAL_DISEASE_V1"
                    ):
                        diseased = (
                            out
                            / (
                                f"{name}"
                                ".terminal_disease.wav"
                            )
                        )

                        _black_metal_terminal_disease(
                            processed,
                            diseased,
                        )

                        processed = diseased

                        production_identity = (
                            "TERMINAL_DISEASE_V1"
                        )

                    stems.append({"role":role,"path":processed,"pan":-.88 if side=="left" else .88,
                                  "gain":float(levels.get(role,.78))*(
                                      .95
                                      if role == "harmony"
                                      else .72
                                  ),
                                  "module":selected_id,
                                  "articulation":articulation,
                                  "production_identity":(
                                      production_identity
                                      if "production_identity" in locals()
                                      else None
                                  )})
        else:
            if (
                module.get(
                    "native_renderer"
                )
                == "dark_aggro_triple_saw"
            ):
                processed = (
                    out
                    / f"{role}.wav"
                )

                render_dark_aggro_triple_saw(
                    processed,
                    rows,
                    bpm=bpm,
                    drum_events=events.get(
                        "drums",
                        (),
                    ),
                    sample_rate=48000,
                )

                stems.append({
                    "role": role,
                    "path": processed,
                    "pan": 0.0,
                    "gain": float(
                        levels.get(
                            role,
                            0.82,
                        )
                    ),
                    "module": module_id,
                    "articulation":
                        "DISTORTED_POWER_SYNTH",
                })

                continue

            if (
                role == "keys"
                and module.get(
                    "native_renderer"
                ) == "nocturne_v4"
            ):
                processed = (
                    _render_nocturne_v4_keys(
                        out,
                        rows,
                        receipt,
                        module_id,
                        module,
                    )
                )

                if (
                    module_id
                    == "nocturne_v4_funeral_motif"
                ):
                    present = (
                        out
                        / "keys.nocturne_v4.funeral_presence.wav"
                    )

                    _ffmpeg(
                        processed,
                        present,
                        (
                            "highpass=f=170,"
                            "equalizer="
                            "f=1250:t=q:w=0.9:g=5,"
                            "equalizer="
                            "f=1750:t=q:w=1.0:g=4,"
                            "equalizer="
                            "f=3000:t=q:w=1.2:g=-2,"
                            "lowpass=f=6900,"
                            "acompressor="
                            "threshold=0.12:"
                            "ratio=2.3:"
                            "attack=12:"
                            "release=180,"
                            "volume=3dB"
                        ),
                        mono=False,
                    )

                    processed = present

                stems.append({
                    "role":
                        role,

                    "path":
                        processed,

                    "pan":
                        0,

                    "gain":
                        float(
                            levels.get(
                                role,
                                .78,
                            )
                        ),

                    "module":
                        module_id,

                    "articulation":
                        (
                            "NOCTURNE_V4_"
                            + str(
                                module["voice"]
                            ).upper()
                        ),
                })

                continue

            raw=_sample_role(out,role,rows,module_id,module,bpm,modules,sf2,midi_writer,name=role)
            processed=out/f"{role}.wav"
            if role in {"harmony", "lead"} and module.get("instrument_family") == "guitar":
                clean_module = module_id in {"gm_clean_guitar", "gm_acoustic"}
                _guitar_fx(raw,processed,tone,drive=max(.3,drive-.09) if role == "lead" else drive,
                           processed_source=bool(module.get("processed_source")), clean=clean_module,
                           doom=genre=="doom_metal",lead=role=="lead")
            elif (
                genre == "synthwave"
                and song_type == "dark_aggro"
                and role == "keys"
                and module_id == "gm_dark_arp"
            ):
                _ffmpeg(
                    raw,
                    processed,
                    (
                        "highpass=f=55,"
                        "lowpass=f=2600,"
                        "equalizer=f=120:t=q:w=1:g=5,"
                        "equalizer=f=480:t=q:w=1:g=3,"
                        "volume=7dB,"
                        "asoftclip=type=tanh:threshold=0.52,"
                        "acompressor="
                        "threshold=0.11:"
                        "ratio=5:"
                        "attack=2:"
                        "release=80,"
                        "aecho=0.82:0.30:105:0.10"
                    ),
                )

            elif (
                genre == "synthwave"
                and song_type == "dark_aggro"
                and role == "harmony"
            ):
                _ffmpeg(
                    raw,
                    processed,
                    (
                        "highpass=f=70,"
                        "lowpass=f=3400,"
                        "volume=4dB,"
                        "asoftclip=type=tanh:threshold=0.62,"
                        "acompressor="
                        "threshold=0.13:"
                        "ratio=3.5:"
                        "attack=10:"
                        "release=180,"
                        "aecho=0.88:0.38:310|690:0.13|0.06"
                    ),
                )

            elif (
                genre == "synthwave"
                and song_type == "dark_aggro"
                and role == "bass"
            ):
                _ffmpeg(
                    raw,
                    processed,
                    (
                        "highpass=f=28,"
                        "lowpass=f=3000,"
                        "equalizer=f=82:t=q:w=1:g=5,"
                        "volume=6dB,"
                        "asoftclip=type=tanh:threshold=0.50,"
                        "acompressor="
                        "threshold=0.10:"
                        "ratio=5:"
                        "attack=3:"
                        "release=100"
                    ),
                )

            elif role=="bass":
                pitch="rubberband=pitch=0.5," if "sfz" in module else ""
                _ffmpeg(raw,processed,pitch+"highpass=f=32,lowpass=f=3400,acompressor=threshold=0.1:ratio=3:attack=7:release=120")
            elif role=="drums":
                drum_filter="highpass=f=30,acompressor=threshold=0.18:ratio=2.6:attack=7:release=90"
                if genre=="industrial_metal":
                    drum_filter += (
                        ",agate=threshold=0.028:"
                        "ratio=4:attack=2:release=55,"
                        "asoftclip=type=tanh:"
                        "threshold=0.78"
                    )

                elif genre=="death_metal":
                    drum_filter += (
                        ",acompressor="
                        "threshold=0.13:"
                        "ratio=3.5:"
                        "attack=3:"
                        "release=65"
                    )

                elif genre=="doom_metal":
                    drum_filter += (
                        ",aecho="
                        "0.8:0.2:195:0.08"
                    )

                elif (
                    genre == "synthwave"
                    and song_type == "dark_aggro"
                ):
                    drum_filter += (
                        ",highpass=f=38,"
                        "equalizer="
                        "f=72:t=q:w=1:g=4,"
                        "equalizer="
                        "f=3200:t=q:w=1:g=3,"
                        "acompressor="
                        "threshold=0.10:"
                        "ratio=5:"
                        "attack=2:"
                        "release=90,"
                        "aecho="
                        "0.82:0.38:"
                        "72|118:"
                        "0.20|0.10,"
                        "agate="
                        "threshold=0.018:"
                        "ratio=7:"
                        "attack=1:"
                        "release=95,"
                        "asoftclip="
                        "type=tanh:"
                        "threshold=0.70"
                    )

                elif genre=="synthwave":
                    drum_filter += (
                        ",equalizer="
                        "f=70:t=q:w=1:g=4,"
                        "equalizer="
                        "f=190:t=q:w=1.2:g=-2,"
                        "equalizer="
                        "f=5200:t=q:w=1:g=3,"
                        "acompressor="
                        "threshold=0.11:"
                        "ratio=4:"
                        "attack=2:"
                        "release=70,"
                        "asoftclip="
                        "type=tanh:"
                        "threshold=0.82"
                    )
                _ffmpeg(raw,processed,drum_filter)
            elif role=="folk":
                _ffmpeg(raw,processed,"highpass=f=110,lowpass=f=9500,aecho=0.8:0.2:180:0.07")
            elif role == "keys":
                keys_cfg = (
                    receipt.get(
                        "atmospheric_keys"
                    )
                    or {}
                )

                kind = str(
                    keys_cfg.get(
                        "kind",
                        "NONE",
                    )
                )

                if (
                    receipt.get("genre")
                    == "black_metal"
                ):
                    if kind == "CHOIR_SHADOW":
                        filt = (
                            "highpass=f=150,"
                            "lowpass=f=6200,"
                            "aecho=0.88:0.52:"
                            "420|910|1430:"
                            "0.22|0.11|0.05,"
                            "loudnorm=I=-14:TP=-2:LRA=7"
                        )

                    elif kind == "COLD_DRONE":
                        filt = (
                            "highpass=f=90,"
                            "lowpass=f=4800,"
                            "aecho=0.90:0.56:"
                            "610|1280:"
                            "0.22|0.09,"
                            "loudnorm=I=-14:TP=-2:LRA=7"
                        )

                    else:
                        filt = (
                            "highpass=f=120,"
                            "lowpass=f=6000,"
                            "aecho=0.88:0.48:"
                            "470|980|1510:"
                            "0.20|0.10|0.04,"
                            "loudnorm=I=-14:TP=-2:LRA=7"
                        )

                    _ffmpeg(
                        raw,
                        processed,
                        filt,
                    )

                else:
                    _ffmpeg(
                        raw,
                        processed,
                        "highpass=f=120,"
                        "lowpass=f=9000",
                    )
            else:
                _ffmpeg(raw,processed,"highpass=f=65,lowpass=f=7500")
            stems.append({"role":role,"path":processed,"pan":0.12 if role in {"lead","folk"} else 0,
                          "gain":float(levels.get(role,1)),"module":module_id})
    if not stems: raise RuntimeError("No active instrument stems were rendered")
    return stems


def mix_stems(out: Path, stems: list[dict[str,Any]], *, master_gain_db: float,
              duration_seconds: float) -> tuple[Path,Path]:
    wav=out/"SONG_CANDIDATE.wav";mp3=out/"SONG_CANDIDATE.mp3"
    command=["ffmpeg","-hide_banner","-loglevel","error","-y"]
    for stem in stems:command += ["-i",str(stem["path"])]
    filters=[]
    for i,stem in enumerate(stems):
        pan=float(stem["pan"]);gain=float(stem["gain"])
        left=round(gain*(1-pan)/2,4);right=round(gain*(1+pan)/2,4)
        filters.append(f"[{i}:a]aformat=channel_layouts=mono,pan=stereo|c0={left}*c0|c1={right}*c0[s{i}]")
    joined=''.join(f'[s{i}]' for i in range(len(stems)))
    filters.append(f"{joined}amix=inputs={len(stems)}:duration=longest:normalize=0,highpass=f=25,loudnorm=I=-16:TP=-1.5:LRA=11,volume={master_gain_db}dB,alimiter=limit=0.92:level=false[out]")
    command += ["-filter_complex",";".join(filters),"-map","[out]","-t",str(round(duration_seconds,3)),
                "-ar","44100","-c:a","pcm_s16le",str(wav)]
    _run(command)
    _run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(wav),"-codec:a","libmp3lame","-q:a","4",str(mp3)])
    return wav,mp3
