"""Seed, compile and render controllable Sonoris song candidates.

Genre grammars choose form and behavior. The event seeder realizes those
behaviors as MIDI. FluidSynth/SFZ rendering is a listening sketch; human genre,
performance, instrument-rights and release review remain separate.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import mido

from products.sonoris_black_metal_governed import compile_black_metal_governed_plan
from products.sonoris_black_metal_continuity import apply_black_metal_continuity
from products.sonoris_black_metal_render_intent import compile_black_metal_render_intent
from products.sonoris_genre_compiler import _read_catalog, compile_composition_request, genre_catalog_snapshot
from products.sonoris_metal_patterns import metal_models, realize_metal
from products.sonoris_physical_compiler import compile_physical_performance
from products.sonoris_stem_renderer import mix_stems, render_stems
from products.sonoris_thrash_specialist import compile_thrash_specialist

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "media" / "sonoris" / "studio_jobs"
SEED_ROOT = ROOT / "media" / "sonoris" / "genre_seed_library_v2"
SF2 = Path("/usr/share/sounds/sf2/FluidR3_GM.sf2")
GTX = Path("/home/byron/fusion-instruments/guitar/Metal-GTX/UI_METAL-GTX/Programs/Individual Patchs/SFIZZ_CLEAN/METAL-GTX_Full")
GROWLY = Path("/home/byron/fusion-instruments/bass/Growlybass/Growlybass")
VIRTUOSITY = Path("/home/byron/fusion-instruments/sonoris/virtuosity_drums/Programs/02-full-kit.sfz")
FSBS = Path("/home/byron/fusion-instruments/guitar/FreePats-FSBS-dist2/EGuitarFSBS-dist2 SFZ+FLAC-20220911/EGuitarFSBS-dist2 bridge 20220911.sfz")
FOLK_ROOT = Path("/home/byron/fusion-instruments/folk")
MODULES = {
    "harmony": {
        "off": {
            "label": "No harmony instrument",
            "off": True,
        },
        "gm_clean_guitar": {"label": "GM clean guitar", "program": 27, "instrument_family": "guitar"},
        "gm_overdrive": {"label": "GM overdriven guitar", "program": 29, "instrument_family": "guitar"},
        "gm_distortion": {"label": "GM distorted guitar", "program": 30, "instrument_family": "guitar"},
        "gm_acoustic": {"label": "GM acoustic guitar", "program": 25, "instrument_family": "guitar"},
        "gm_piano": {"label": "GM grand piano", "program": 0},
        "gm_rhodes": {"label": "GM electric piano", "program": 4},
        "gm_synth_pad": {"label": "GM warm synth pad", "program": 89},
        "gm_organ": {"label": "GM rock organ", "program": 18},
        "gtx_sustain": {"label": "Metal GTX sustain SFZ", "sfz": str(GTX / "Sus_Down.sfz"), "instrument_family": "guitar"},
        "gtx_mute": {"label": "Metal GTX palm mute SFZ", "sfz": str(GTX / "Mute_Down.sfz"), "instrument_family": "guitar"},
        "fsbs_distorted": {"label": "FreePats sampled distorted guitar", "sfz": str(FSBS), "processed_source": True, "instrument_family": "guitar"},
    },
    "bass": {
        "off": {
            "label": "No low-end instrument",
            "off": True,
        },
        "gm_electric_bass": {"label": "GM electric bass", "program": 33},
        "gm_acoustic_bass": {"label": "GM upright bass", "program": 32},
        "gm_synth_bass": {"label": "GM synth bass", "program": 38},
        "growly_clean": {"label": "Growlybass clean SFZ", "sfz": str(GROWLY / "growlybass_clean.sfz")},
        "growly_dirty": {"label": "Growlybass dirty SFZ", "sfz": str(GROWLY / "growlybass_dirty.sfz")},
        "growly_vicious": {"label": "Growlybass vicious SFZ", "sfz": str(GROWLY / "growlybass_vicious.sfz")},
    },
    "lead": {
        "off": {"label": "No lead", "off": True},
        "gm_synth_lead": {"label": "GM synth lead", "program": 80},
        "gm_sax": {"label": "GM alto sax", "program": 65},
        "gm_piano": {"label": "GM grand piano", "program": 0},
        "gm_organ": {"label": "GM rock organ", "program": 18},
        "gm_clean_guitar": {"label": "GM clean guitar", "program": 27, "instrument_family": "guitar"},
        "gm_distortion": {"label": "GM distorted guitar", "program": 30, "instrument_family": "guitar"},
        "gtx_sustain": {"label": "Metal GTX sampled lead", "sfz": str(GTX / "Sus_Down.sfz"), "instrument_family": "guitar"},
        "fsbs_distorted": {"label": "FreePats distorted lead", "sfz": str(FSBS), "processed_source": True, "instrument_family": "guitar"},
    },
    "drums": {
        "off": {
            "label": "No percussion",
            "off": True,
        },

        "gm_kit": {
            "label": "FluidR3 standard drum kit",
            "program": None,
            "drum_program": 0,
        },

        "gm_room_kit": {
            "label": "FluidR3 room drum kit",
            "program": None,
            "drum_program": 8,
        },

        "gm_power_kit": {
            "label": "FluidR3 power drum kit",
            "program": None,
            "drum_program": 16,
        },

        "gm_electronic_kit": {
            "label": "FluidR3 electronic drum machine",
            "program": None,
            "drum_program": 24,
        },

        "gm_808_kit": {
            "label": "FluidR3 TR-style electronic kit",
            "program": None,
            "drum_program": 25,
        },
        "salamander": {"label": "Salamander drum SFZ", "sfz": "/home/byron/fusion-instruments/drums/Salamander/Salamander Drumkit.sfz"},
        "virtuosity": {"label": "Virtuosity multisampled full drum kit", "sfz": str(VIRTUOSITY)},
    },
    "keys": {
        "off": {"label": "No keys", "off": True},
        "gm_organ": {"label": "FluidR3 rock organ", "program": 18},
        "gm_synth_pad": {"label": "FluidR3 synth pad", "program": 89},
        "gm_dark_arp": {
            "label": "Dark distorted saw arp",
            "program": 81,
        },
        "native_aggro_triple_saw": {
            "label": "Native Aggro Triple Saw",
            "native_renderer":
                "dark_aggro_triple_saw",
        },
        "gm_choir": {"label": "FluidR3 choir", "program": 52},
        "rock_organ_sampled": {"label": "FreePats sampled rock organ", "sfz": "/home/byron/fusion-instruments/sonoris/rock_organ/RockOrganEmulation-SFZ-20190715/RockOrganEmulation-20190715.sfz"},
        "new_age_pad_sampled": {"label": "FreePats sampled synth pad", "sfz": "/home/byron/fusion-instruments/sonoris/new_age_pad/NewAge SFZ+FLAC-20190730/NewAge 20190730.sfz"},
        "nocturne_v4_funeral_motif": {
            "label": "Nocturne V4 · Funeral Motif",
            "instrument_family": "synth",
            "native_renderer": "nocturne_v4",
            "voice": "motif",
            "timbre": {
                "oscillator_detune_cents": 18,
                "filter_cutoff_hz": 920,
                "filter_envelope": 1.15,
                "drive": 4.5,
                "stereo_drift": 0.006,
                "noise_texture": 0.004,
                "darkness": 0.90,
                "harmonic_grit": 0.90,
                "dread_motion": 0.78,
                "motif_level": 0.34
            }
        },
        "nocturne_v4_machine_choir": {
            "label": "Nocturne V4 · Machine Choir",
            "instrument_family": "synth",
            "native_renderer": "nocturne_v4",
            "voice": "pad",
            "timbre": {
                "oscillator_detune_cents": 21,
                "filter_cutoff_hz": 510,
                "filter_envelope": 1.20,
                "drive": 3.7,
                "stereo_drift": 0.008,
                "noise_texture": 0.006,
                "darkness": 0.94,
                "harmonic_grit": 0.92,
                "dread_motion": 0.86,
                "pad_level": 0.105
            }
        },
        "rhodes_sampled": {"label": "jRhodes sampled electric piano", "sfz": "/home/byron/fusion-instruments/sonoris/jlearman.jRhodes3c/jRhodes3c-looped-flac-sfz/_jRhodes-stereo-looped.sfz"},
    },
    "folk": {
        "off": {"label": "No folk instrument", "off": True},
        "bagpipe_sampled": {"label": "FreePats G bagpipe and drones", "sfz": str(FOLK_ROOT / "bagpipe/Bagpipe small SFZ+FLAC-20260806/Bagpipe small 20260806.sfz")},
        "flute_sampled": {"label": "VSCO2 sampled transverse flute", "sfz": str(FOLK_ROOT / "vsco_flute/FluteSusVib.sfz")},
        "recorder_sampled": {"label": "FreePats wooden recorder", "sfz": str(FOLK_ROOT / "recorder/Recorder-SFZ+FLAC-20201205/Recorder-20201205.sfz")},
        "accordion_sampled": {"label": "FreePats button accordion", "sfz": str(FOLK_ROOT / "accordion/Button Accordion HN SFZ+FLAC-20240329/PRESET Button Accordion HN tuned.sfz")},
    },
}


from products.sonoris_dark_aggro_synthwave import (
    compile_dark_aggro_events,
    compose_dark_aggro_blueprint,
)


def module_snapshot() -> dict[str, Any]:
    return {role: {key: {"label": row["label"], "available": Path(row["sfz"]).is_file() if "sfz" in row else True if row.get("off") else SF2.is_file(),
                          "instrument_family": row.get("instrument_family"),
                          "engine": "sfizz" if "sfz" in row else "none" if row.get("off") else "fluidsynth"}
                   for key, row in choices.items()} for role, choices in MODULES.items()}


def _default_modules(genre: str, family: str) -> dict[str, str]:
    # Drum timbre is part of the genre arrangement, not a one-size-fits-all
    # fallback. Choose locally installed kits that support each style's feel.
    drum_modules = {
        "thrash_metal": "gm_power_kit",
        "death_metal": "virtuosity",
        "power_metal": "virtuosity",
        "doom_metal": "gm_room_kit",
        "folk_metal": "salamander",
        "glam_metal": "gm_power_kit",
        "prog_metal": "virtuosity",
        "industrial_metal": "gm_electronic_kit",
        "alternative_metal": "gm_room_kit",
        "nu_metal": "gm_808_kit",
        "rock": "gm_kit",
        "hard_rock": "gm_power_kit",
        "math_rock": "salamander",
        "post_rock": "gm_room_kit",
        "prog_rock": "virtuosity",
        "folk_rock": "gm_room_kit",
        "indie_rock": "gm_kit",
        "grunge": "gm_room_kit",
    }
    drums = drum_modules.get(genre, "virtuosity")
    if genre == "synthwave":
        return {
            "harmony": "gm_synth_pad",
            "bass": "gm_synth_bass",
            "lead": "gm_synth_lead",
            "drums": "gm_electronic_kit",
            "keys": "off",
            "folk": "off",
        }
    if genre == "ambient":
        return {
            "harmony": "off",
            "bass": "gm_synth_bass",
            "lead": "gm_synth_lead",
            "drums": "off",
            "keys": "new_age_pad_sampled",
            "folk": "off",
        }
    if genre in {"jazz", "jazz_fusion"}: return {"harmony": "gm_rhodes", "bass": "gm_acoustic_bass", "lead": "gm_sax", "drums": "gm_kit", "keys": "off", "folk": "off"}
    if family == "metal":
        if genre == "black_metal": return {"harmony": "gtx_sustain", "bass": "growly_dirty", "lead": "off", "drums": "virtuosity", "keys": "off", "folk": "off"}
        guitar = "fsbs_distorted" if genre in {"doom_metal", "glam_metal", "alternative_metal"} else "gtx_sustain"
        keys = "rock_organ_sampled" if genre in {"power_metal", "glam_metal"} else "rhodes_sampled" if genre == "prog_metal" else "new_age_pad_sampled" if genre in {"industrial_metal", "alternative_metal", "nu_metal"} else "off"
        folk = "bagpipe_sampled" if genre == "folk_metal" else "off"
        lead = "off" if genre in {"industrial_metal", "nu_metal"} else "gtx_sustain"
        bass = "growly_vicious" if genre in {"death_metal", "nu_metal", "industrial_metal"} else "growly_clean" if genre=="glam_metal" else "growly_dirty"
        return {"harmony": guitar, "bass": bass, "lead": lead, "drums": drums, "keys": keys, "folk": folk}
    rock_bands = {
        "rock": {"harmony": "gtx_sustain", "bass": "growly_dirty", "lead": "gtx_sustain", "drums": drum_modules["rock"], "keys": "off", "folk": "off"},
        "hard_rock": {"harmony": "gtx_sustain", "bass": "growly_dirty", "lead": "gtx_sustain", "drums": drum_modules["hard_rock"], "keys": "rock_organ_sampled", "folk": "off"},
        "grunge": {"harmony": "gtx_sustain", "bass": "growly_dirty", "lead": "gtx_sustain", "drums": drum_modules["grunge"], "keys": "off", "folk": "off"},
        "indie_rock": {"harmony": "gtx_sustain", "bass": "growly_clean", "lead": "gtx_sustain", "drums": drum_modules["indie_rock"], "keys": "new_age_pad_sampled", "folk": "off"},
        "math_rock": {"harmony": "gtx_sustain", "bass": "growly_clean", "lead": "gtx_sustain", "drums": drum_modules["math_rock"], "keys": "off", "folk": "off"},
        "post_rock": {"harmony": "gtx_sustain", "bass": "growly_clean", "lead": "gtx_sustain", "drums": drum_modules["post_rock"], "keys": "new_age_pad_sampled", "folk": "off"},
        "prog_rock": {"harmony": "gtx_sustain", "bass": "growly_clean", "lead": "gtx_sustain", "drums": drum_modules["prog_rock"], "keys": "rock_organ_sampled", "folk": "off"},
        "folk_rock": {"harmony": "gm_acoustic", "bass": "growly_clean", "lead": "gtx_sustain", "drums": drum_modules["folk_rock"], "keys": "off", "folk": "flute_sampled"},
    }
    if genre in rock_bands: return dict(rock_bands[genre])
    return {"harmony": "gm_overdrive", "bass": "gm_electric_bass", "lead": "gm_clean_guitar", "drums": "gm_kit", "keys": "off", "folk": "off"}


_NON_METAL_TONE_DEFAULTS = {
    "ambient": "clean_chime",
    "synthwave": "clean_chime",
    "jazz": "clean_chime",
    "jazz_fusion": "clean_chime",
    "rock": "arena_crunch",
    "hard_rock": "arena_crunch",
    "math_rock": "precise_progressive",
    "post_rock": "wide_alternative",
    "prog_rock": "precise_progressive",
    "folk_rock": "folk_crunch",
    "indie_rock": "wide_alternative",
    "grunge": "wide_alternative",
}


def _default_tone(genre: str, metal_profiles: Mapping[str, Any]) -> str:
    if genre in metal_profiles:
        return str(metal_profiles[genre]["tone"])
    if genre == "black_metal":
        return "brutal_low"
    return _NON_METAL_TONE_DEFAULTS.get(genre, "arena_crunch")


def _key_pitch(center: str) -> int:
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    key = str(center).split("-", 1)[0].upper().replace("B♭", "A#").replace("E♭", "D#")
    if key not in names:
        raise ValueError("tonal_center must begin with C, C#, D, D#, E, F, F#, G, G#, A, A# or B")
    return names[key]


def _progression(style: str) -> list[int]:
    return {
        "ii_v_i": [2, 7, 0, 0], "modal_shift": [0, 5, 2, 7], "modal_drone": [0, 0, 5, 2],
        "minor_drone": [0, 0, -2, -5], "minor_pedal": [0, 0, -5, -2],
        "chromatic_minor": [0, -1, -5, -2], "minor_major_lift": [0, -5, 3, 7],
        "modal_major": [0, 5, 7, 0], "major_minor_hook": [0, 5, -3, 7], "blues_rock": [0, 5, 0, 7],
    }.get(style, [0, -5, -7, -3])


def _event(role: str, beat: float, duration: float, pitch: int, velocity: int, gesture: str, section: int) -> dict[str, Any]:
    return {"role": role, "beat": round(beat, 5), "duration": round(max(.05, duration), 5),
            "pitch": max(0, min(127, int(pitch))), "velocity": max(1, min(127, int(velocity))),
            "gesture": gesture, "section": section}


def _seed_events(plan: Mapping[str, Any], seed: int) -> dict[str, list[dict[str, Any]]]:
    genre = plan["grammar"]["primary"]["key"]
    profile = _read_catalog()["profiles"][genre]
    groove = profile.get("rhythm_topology") or {
        "synthwave": "motorik",
        "jazz_fusion": "swing",
        "ambient": "ambient",
        "rock": "backbeat",
    }.get(genre, "backbeat")
    harmony = profile.get("harmony_topology") or {
        "synthwave": "major_minor_hook",
        "jazz_fusion": "ii_v_i",
        "ambient": "modal_drone",
        "rock": "blues_rock",
    }.get(genre, "modal_shift")
    variant = (plan["grammar"].get("song_type") or {}).get("key") or "drive"

    if (
        genre == "synthwave"
        and variant == "dark_aggro"
    ):
        compiled = compile_dark_aggro_events(
            seed=seed,
            bars=int(
                plan["musical_frame"]["bars"]
            ),
            tonal_center=str(
                plan["musical_frame"][
                    "tonal_center"
                ]
            ),
        )

        return compiled["events"]
    # Scheduling grid is not the composition's musical meter.
    # Ambient/free meter retains its canonical grammar while MIDI
    # events use a neutral four-quarter-note coordinate span.
    meter = str(plan["musical_frame"]["meter"]).strip()

    if meter == "free":
        beats_per_bar = 4.0
    else:
        numerator, denominator = meter.split("/")
        beats_per_bar = int(numerator) * 4.0 / int(denominator)
    key = _key_pitch(plan["musical_frame"]["tonal_center"])
    root = 36 + key
    rng = random.Random(seed)
    result: dict[str, list[dict[str, Any]]] = {role: [] for role in MODULES}
    progress = _progression(harmony)
    if genre == "ambient":
        # Ambient form moves through slowly changing fields, with no forced
        # backbeat, recurring guitar chord grid, or constant lead run.
        for section in plan["sections"]:
            section_index = section["index"]
            gesture = section["gesture"]
            for bar in range(section["start_bar"], section["end_bar"], 2):
                span_bars = min(2, section["end_bar"] - bar)
                beat = bar * beats_per_bar
                chord_root = max(36, min(60, root + progress[(bar // 4) % len(progress)] + 24))
                duration = beats_per_bar * span_bars * 0.96
                level = max(24, min(58, 34 + int(10 * section_index / max(1, len(plan["sections"])))))
                for interval in (0, 7, 12, 16):
                    result["keys"].append(_event("keys", beat, duration, chord_root + interval,
                                                  level - (4 if interval == 16 else 0), gesture, section_index))
                result["bass"].append(_event("bass", beat, duration, chord_root - 24,
                                              level + 3, gesture, section_index))
                if bar % 4 == 0:
                    color = (0, 3, 7, 10)[(section_index + bar // 4) % 4]
                    result["lead"].append(_event("lead", beat + beats_per_bar * 0.5,
                                                  duration * 0.78, chord_root + 12 + color,
                                                  max(20, level - 7), gesture, section_index))
        return result
    for section in plan["sections"]:
        section_index = section["index"]
        gesture = section["gesture"]
        energy = (.64 if variant == "space" else .9 if variant == "drive" else .77)
        quiet_section = groove == "quiet_loud" and any(
            marker in gesture.upper() for marker in ("QUIET", "TEXTURE", "SPACE")
        )
        loud_section = groove == "quiet_loud" and any(
            marker in gesture.upper() for marker in ("HEAVY", "HOOK", "BREAKDOWN", "IMPACT", "CHORUS")
        )
        if groove == "quiet_loud":
            if quiet_section:
                energy = min(energy, .34)
            elif loud_section:
                energy = max(energy, 1.0)
        elif groove == "crescendo":
            energy = min(1, .25 + section_index / max(2, len(plan["sections"])) * .72)
        else:
            gesture_tokens = set(gesture.upper().split("_"))
            quiet_gestures = {"INTRO", "INTRODUCE", "TEXTURE", "SUSPEND", "DRIFT", "RELEASE", "DECAY", "AFTERGLOW", "SETTLE", "SPACE", "GLOW"}
            loud_gestures = {"HOOK", "CHORUS", "DROP", "ERUPTION", "LIFT", "ANTHEM", "BLAST", "PANIC", "STOMP", "IMPACT", "HEAVY", "SPRINT", "SOLO"}
            if gesture_tokens & quiet_gestures:
                energy = min(energy, .46)
            elif gesture_tokens & loud_gestures:
                energy = 1.0
            else:
                energy = min(energy, .78)
        if any(word in gesture for word in ("RELEASE", "DECAY", "AFTERGLOW", "TEXTURE")): energy *= .5
        for bar in range(section["start_bar"], section["end_bar"]):
            t = bar * beats_per_bar
            chord_root = root + progress[(bar // 4) % len(progress)]
            chord_root = max(28, min(68, chord_root))
            beat_count = max(1, math.ceil(beats_per_bar))
            # Kick/snare identities differ by groove; all note times stay within the meter.
            if groove == "quiet_loud" and quiet_section:
                kick_offsets, snare_offsets = [0], [min(2, beats_per_bar - .25)]
            elif groove in {"blast", "thrash"}:
                kick_offsets = [i * .5 for i in range(int(beats_per_bar * 2))]
                snare_offsets = [i * .5 + .25 for i in range(int(beats_per_bar * 2))] if groove == "blast" else [1, min(3, beats_per_bar - .5)]
            elif groove in {"doom", "crescendo"}:
                kick_offsets, snare_offsets = [0], [min(2, beats_per_bar - .5)]
            elif groove in {"gallop", "dance", "folk"}:
                kick_offsets, snare_offsets = [0, .75, 1.5], [min(2, beats_per_bar - .5)]
            elif groove in {"syncopated", "odd"}:
                kick_offsets, snare_offsets = [0, min(1.5, beats_per_bar - .25)], [min(1, beats_per_bar - .25)]
            else:
                kick_offsets, snare_offsets = [0, min(2, beats_per_bar - .25)], [min(1, beats_per_bar - .25), min(3, beats_per_bar - .25)]
            for offset in kick_offsets:
                if 0 <= offset < beats_per_bar: result["drums"].append(_event("drums", t+offset, .12, 36, int(72+energy*34), gesture, section_index))
            snare_pitch = 37 if quiet_section else 38  # side-stick keeps the quiet verse behind the heavy hook
            for offset in snare_offsets:
                if 0 <= offset < beats_per_bar: result["drums"].append(_event("drums", t+offset, .12, snare_pitch, int(65+energy*35), gesture, section_index))
            hats = 4 if groove in {"doom", "crescendo"} or quiet_section else 8 if groove not in {"blast", "thrash"} else 16
            hat_offsets = ([beat + subdivision for beat in range(beat_count) for subdivision in (0, 2/3)]
                           if groove == "swing" else [beats_per_bar * i / hats for i in range(hats)])
            for i, offset in enumerate(hat_offsets):
                if offset >= beats_per_bar: continue
                result["drums"].append(_event("drums", t+offset, .08, 42 if groove != "swing" else 51,
                                               int(36+energy*22+(i%2)*5), gesture, section_index))
            # Walking bass in jazz, root/fifth locks elsewhere; space variant leaves breathing room.
            bass_steps = beat_count if groove == "swing" else (max(1, int(beats_per_bar*2)) if groove in {"motorik", "machine", "blast", "thrash"} else 2)
            if quiet_section: bass_steps = 1
            if variant == "space": bass_steps = max(1, bass_steps // 2)
            for i in range(bass_steps):
                offset = beats_per_bar * i / bass_steps
                note = chord_root - 12 + ([0, 4, 7, 9][i%4] if groove == "swing" else [0, 7, 0, 5][i%4])
                result["bass"].append(_event("bass", t+offset, beats_per_bar/bass_steps*.8, note, int(55+energy*38), gesture, section_index))
            # Harmony is a voiced gesture, not a hard-coded verse/chorus chord loop.
            interval = [0, 4, 7, 10] if groove == "swing" else [0, 3, 7] if "minor" in harmony or "chromatic" in harmony else [0, 4, 7]
            if profile["family"] == "metal": interval = [0, 7, 12]
            if groove in {"swing", "machine", "blast", "thrash", "jangle", "backbeat", "quiet_loud", "syncopated", "gallop", "dance", "folk", "arena", "odd"}:
                if groove == "swing":
                    offsets = [0, min(1.5, beats_per_bar-.25), min(3, beats_per_bar-.25)]
                elif groove == "gallop":
                    offsets = [beat + sub for beat in range(0, beat_count, 2) for sub in (0, .5, .75)]
                elif groove == "odd":
                    offsets = [0, .75, 1.5, 2.5, 3.25, 4.5]
                elif groove in {"dance", "folk"}:
                    offsets = [0, .75, 1.5, 2.25, 3]
                elif groove == "syncopated":
                    offsets = [0, .75, 1.5, 2.75, 3.5]
                elif groove == "quiet_loud" and quiet_section:
                    offsets = [0]
                else:
                    hit_count = 8 if groove in {"blast", "thrash", "jangle"} else 4
                    offsets = [beats_per_bar * i / hit_count for i in range(hit_count)]
                offsets = [offset for offset in offsets if offset < beats_per_bar]
                if variant == "space": offsets = offsets[::2]
                for offset in offsets:
                    for step in (interval[:2] if profile["family"] == "metal" else interval if groove == "swing" else interval[:3]):
                        hit_duration = beats_per_bar * .82 if quiet_section else min(.55, beats_per_bar / max(1,len(offsets))*.72)
                        result["harmony"].append(_event("harmony", t+offset, hit_duration, chord_root+step,
                                                        int(49+energy*40), gesture, section_index))
            else:
                for step in interval:
                    result["harmony"].append(_event("harmony", t, beats_per_bar*.82, chord_root+step,
                                                    int(48+energy*35), gesture, section_index))
            # Lead answers the ensemble; motif transposes by section but does not quote repertoire.
            if not quiet_section and bar % (2 if variant == "space" else 1) == 0 and energy > .3:
                contour = [0, 3, 7, 5] if "minor" in harmony else [0, 4, 7, 9]
                shift = (section_index % 3) * 2 + rng.choice([0, 0, 1])
                for i, step in enumerate(contour):
                    offset = beats_per_bar * i / 4
                    result["lead"].append(_event("lead", t+offset, beats_per_bar/4*.72,
                                                  chord_root+12+step+shift, int(45+energy*35), gesture, section_index))
            if genre == "folk_rock":
                # Give the folk lead its own sampled flute line that answers
                # the guitar phrase instead of leaving the selected module silent.
                folk_contours = ([0, 2, 4, 7, 5, 4, 2, 0], [4, 5, 7, 9, 7, 5, 4, 2])
                folk_contour = folk_contours[(section_index + bar) % len(folk_contours)]
                for i, step in enumerate(folk_contour):
                    offset = beats_per_bar * i / len(folk_contour)
                    result["folk"].append(_event("folk", t+offset, beats_per_bar/len(folk_contour)*.82,
                                                  chord_root+24+step, int(48+energy*34), gesture, section_index))
    return result


def _physical_events(
    physical: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:

    mapped = {
        role: []
        for role in MODULES
    }

    for source_role, target_role in (
        ("rhythm_guitar", "harmony"),
        ("bass", "bass"),
        ("drums", "drums"),
    ):
        for row in physical["roles"].get(
            source_role,
            [],
        ):
            authored_articulation = str(
                row.get("articulation")
                or ""
            )

            if target_role == "harmony":
                if "PALM_MUTE" in authored_articulation:
                    renderer_articulation = "mute"
                elif "CLEAN" in authored_articulation:
                    renderer_articulation = "clean"
                else:
                    renderer_articulation = "sustain"
            else:
                renderer_articulation = (
                    authored_articulation
                    or "default"
                )

            for pitch in (
                row.get("pitches")
                or [row["pitch"]]
            ):
                event = _event(
                    target_role,
                    row["tick"] / 480,
                    row["duration"] / 480,
                    pitch,
                    row["velocity"],
                    row["gesture"],
                    int(
                        row.get(
                            "section_index",
                            0,
                        )
                    ),
                )

                event["articulation"] = (
                    renderer_articulation
                )

                event[
                    "physical_articulation"
                ] = authored_articulation

                for key in (
                    "stroke",
                    "function",
                    "phrase_id",
                    "shape_type",
                ):
                    if row.get(key) is not None:
                        event[key] = row[key]

                mapped[target_role].append(
                    event
                )

    return mapped


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


_SEED_MANIFEST_LOCK = threading.Lock()
_SEED_MANIFEST_FIELDS = (
    "job_id", "genre", "song_type", "title", "tempo_bpm", "meter", "bars",
    "midi_sha256", "audio_state",
)


def _sync_seed_manifest(receipt: Mapping[str, Any]) -> None:
    """Keep the public seed-library index aligned with its job receipts."""
    manifest_path = SEED_ROOT / "LIBRARY_MANIFEST.json"
    with _SEED_MANIFEST_LOCK:
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            document = {
                "schema": "dio.sonoris.genre_seed_library.v2",
                "songs": [],
                "claim_boundary": "Original algorithmic MIDI sketches; genre quality and rights require listening and review.",
            }
        if document.get("schema") != "dio.sonoris.genre_seed_library.v2" or not isinstance(document.get("songs"), list):
            raise ValueError("Sonoris seed library manifest has an unsupported schema.")

        row = {key: receipt.get(key) for key in _SEED_MANIFEST_FIELDS}
        if not row.get("job_id"):
            raise ValueError("Rendered Sonoris seed receipt has no job_id.")
        rows = document["songs"]
        found = False
        for index, existing in enumerate(rows):
            if isinstance(existing, dict) and existing.get("job_id") == row["job_id"]:
                rows[index] = row
                found = True
                break
        if not found:
            rows.append(row)
        document["song_count"] = len(rows)
        document["genre_count"] = len({str(item.get("genre")) for item in rows if isinstance(item, dict) and item.get("genre")})

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=manifest_path.parent,
                                             prefix=".sonoris-library-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, manifest_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def _midi(path: Path, events: Mapping[str, list[dict[str, Any]]], bpm: int, modules: Mapping[str, str], *,
          single_role: str | None = None, gm_only: bool = False, pitch_shift: int = 0,
          time_shift: float = 0, velocity_shift: int = 0) -> None:
    midi = mido.MidiFile(ticks_per_beat=480)
    meta = mido.MidiTrack(); meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0)); midi.tracks.append(meta)
    for role, rows in events.items():
        if single_role is not None and role != single_role: continue
        module = MODULES[role][modules[role]]
        if module.get("off") or not rows: continue
        if gm_only and "sfz" in module: continue
        track = mido.MidiTrack(); midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=role, time=0))
        channel = 9 if role == "drums" and "sfz" not in module else 0 if single_role else {"harmony": 0, "bass": 1, "lead": 2, "drums": 9, "keys": 3, "folk": 4}[role]
        fallback = {"harmony": 30, "bass": 33, "lead": 30, "keys": 89, "folk": 73}
        if role == "drums":
            drum_program = module.get(
                "drum_program"
            )

            if drum_program is not None:
                track.append(
                    mido.Message(
                        "program_change",
                        channel=channel,
                        program=int(
                            drum_program
                        ),
                        time=0,
                    )
                )

        else:
            program = module.get(
                "program",
                fallback[role],
            )

            track.append(
                mido.Message(
                    "program_change",
                    channel=channel,
                    program=program,
                    time=0,
                )
            )
        messages = []
        for row in rows:
            start = max(0, round((row["beat"]+time_shift)*480)); end = max(start+1, round((row["beat"]+time_shift+row["duration"])*480))
            pitch=max(0,min(127,row["pitch"]+pitch_shift))
            messages.append((start, 1, pitch, max(1,min(127,row["velocity"]+velocity_shift))))
            messages.append((end, 0, pitch, 0))
        cursor = 0
        for tick, on, pitch, velocity in sorted(messages, key=lambda item: (item[0], item[1])):
            track.append(mido.Message("note_on" if on else "note_off", note=pitch, velocity=velocity,
                                      channel=channel, time=tick-cursor))
            cursor=tick
    midi.save(path)



BM_KEYS_DEFAULTS = {
    "enabled": False,
    "kind": "NONE",
    "level_db": -18.0,
    "register": "MID",
    "motion": "STATIC",
    "density": "SPARSE",
}



def _apply_lament_motion_v2(
    events: list[dict[str, Any]],
    *,
    register: str,
) -> list[dict[str, Any]]:
    """
    Voice-lead LAMENT_KEYS through the actual physical guitar harmony.

    Law:
        no independent melody is invented.

    Every resulting pitch class must already exist in the physical
    harmonic source attached to that key event.

    Motion is intentionally slow:
        - prefer another legal voice near the previous lament pitch
        - prefer moderate movement over large jumps
        - occasionally allow octave migration
        - preserve the requested register
    """

    register_ranges = {
        "LOW": (36, 55),
        "MID": (48, 67),
        "HIGH": (60, 79),
    }

    low, high = register_ranges.get(
        str(register).upper(),
        register_ranges["MID"],
    )

    previous_pitch = None
    lament_index = 0

    result = []

    for original in events:
        row = dict(original)

        if (
            row.get("function")
            != "LAMENT_KEYS"
        ):
            result.append(row)
            continue

        source = dict(
            row.get("harmonic_source")
            or {}
        )

        source_pitches = [
            int(value)
            for value
            in (
                source.get("pitches")
                or []
            )
        ]

        if not source_pitches:
            result.append(row)
            continue

        root = int(
            source.get(
                "root",
                source_pitches[0],
            )
        )

        pitch_classes = sorted({
            value % 12
            for value in source_pitches
        })

        candidates = []

        for midi in range(
            low,
            high + 1,
        ):
            if (
                midi % 12
                in pitch_classes
            ):
                candidates.append(midi)

        if not candidates:
            result.append(row)
            continue

        original_pitch = int(
            row["pitch"]
        )

        # First lament event keeps the generator's original
        # harmonic/register reading when possible.
        if previous_pitch is None:
            chosen = min(
                candidates,
                key=lambda value: (
                    abs(
                        value
                        - original_pitch
                    ),
                    value % 12
                    == root % 12,
                    value,
                ),
            )

        else:
            different = [
                value
                for value in candidates
                if value != previous_pitch
            ]

            pool = (
                different
                or candidates
            )

            def score(
                value: int,
            ):
                distance = abs(
                    value
                    - previous_pitch
                )

                # Ideal lament movement:
                # roughly a minor/major 2nd through fifth.
                moderate_penalty = (
                    0
                    if 2 <= distance <= 7
                    else (
                        2
                        if distance <= 12
                        else 5
                    )
                )

                # Continue preferring the expressive/non-root voice.
                root_penalty = (
                    1
                    if (
                        value % 12
                        == root % 12
                    )
                    else 0
                )

                # Every fourth lament event permits a wider
                # register migration if harmony allows it.
                octave_migration = (
                    lament_index > 0
                    and lament_index % 4 == 0
                )

                migration_penalty = (
                    0
                    if (
                        octave_migration
                        and distance >= 5
                    )
                    else (
                        1
                        if octave_migration
                        else 0
                    )
                )

                return (
                    moderate_penalty,
                    migration_penalty,
                    root_penalty,
                    distance,
                    abs(
                        value
                        - original_pitch
                    ),
                    value,
                )

            chosen = min(
                pool,
                key=score,
            )

        row["pitch"] = chosen

        row[
            "lament_motion"
        ] = {
            "schema":
                "dio.sonoris.lament_motion.v2",

            "index":
                lament_index,

            "previous_pitch":
                previous_pitch,

            "generator_pitch":
                original_pitch,

            "realized_pitch":
                chosen,

            "physical_pitch_classes":
                pitch_classes,

            "physical_pitches":
                source_pitches,

            "root":
                root,

            "register":
                str(register).upper(),
        }

        previous_pitch = chosen
        lament_index += 1

        result.append(row)

    return result



def _apply_lament_arpeggiation_v1(
    events: list[dict[str, Any]],
    *,
    cfg: Mapping[str, Any],
    register: str,
) -> list[dict[str, Any]]:
    """
    Evil black-metal lament arpeggiation.

    No alternating nursery-rhyme contour.

    Laws:
      - all pitch classes remain derived from physical guitar harmony
      - prefer descending motion
      - avoid immediate ABA ping-pong
      - allow octave burial
      - notes overlap slightly into a dark wash
      - velocity decays through the figure
    """

    note_count = max(
        1,
        min(
            8,
            int(cfg.get("arp_notes", 1)),
        ),
    )

    step_beats = max(
        0.125,
        min(
            4.0,
            float(
                cfg.get(
                    "arp_step_beats",
                    1.0,
                )
            ),
        ),
    )

    shape = str(
        cfg.get("arp_shape")
        or "ABYSSAL_DESCENT"
    ).upper()

    if note_count <= 1:
        return events

    register_ranges = {
        "LOW": (32, 55),
        "MID": (43, 67),
        "HIGH": (55, 79),
    }

    low, high = register_ranges.get(
        str(register).upper(),
        register_ranges["MID"],
    )

    result = []

    for source_event in events:

        if (
            source_event.get("function")
            != "LAMENT_KEYS"
        ):
            result.append(source_event)
            continue

        source = dict(
            source_event.get("harmonic_source")
            or {}
        )

        physical_pitches = [
            int(x)
            for x in (
                source.get("pitches")
                or []
            )
        ]

        if not physical_pitches:
            result.append(source_event)
            continue

        pcs = sorted({
            x % 12
            for x in physical_pitches
        })

        legal = [
            midi
            for midi in range(
                low,
                high + 1,
            )
            if midi % 12 in pcs
        ]

        if not legal:
            result.append(source_event)
            continue

        anchor = int(
            source_event["pitch"]
        )

        first = min(
            legal,
            key=lambda n: (
                abs(n - anchor),
                n,
            ),
        )

        sequence = [first]

        while len(sequence) < note_count:

            previous = sequence[-1]

            candidates = [
                n
                for n in legal
                if n != previous
            ]

            if not candidates:
                candidates = legal[:]

            # Do not immediately bounce A-B-A.
            if len(sequence) >= 2:
                no_pingpong = [
                    n
                    for n in candidates
                    if n != sequence[-2]
                ]

                if no_pingpong:
                    candidates = no_pingpong

            index = len(sequence)

            def score(n: int):
                delta = n - previous
                distance = abs(delta)

                # Descending motion is the default gravity.
                descent_penalty = (
                    0 if delta < 0 else 4
                )

                # Favor semitone, tone, minor third,
                # tritone-ish and fifth-sized movement.
                evil_interval_penalty = min(
                    abs(distance - target)
                    for target in (
                        1,
                        2,
                        3,
                        6,
                        7,
                        12,
                    )
                )

                # Every fourth note strongly invites
                # an octave burial if available.
                burial_penalty = (
                    0
                    if (
                        index % 4 == 3
                        and delta <= -7
                    )
                    else (
                        3
                        if index % 4 == 3
                        else 0
                    )
                )

                if shape == "TENSION_RISE":
                    descent_penalty = (
                        0 if delta > 0 else 3
                    )

                elif shape == "GRAVE_CRAWL":
                    evil_interval_penalty = min(
                        abs(distance - target)
                        for target in (
                            1,
                            2,
                            3,
                        )
                    )

                return (
                    descent_penalty,
                    burial_penalty,
                    evil_interval_penalty,
                    distance,
                    n,
                )

            chosen = min(
                candidates,
                key=score,
            )

            sequence.append(chosen)

        source_beat = float(
            source_event["beat"]
        )

        source_duration = float(
            source_event["duration"]
        )

        for index, pitch in enumerate(
            sequence
        ):
            offset = (
                index
                * step_beats
            )

            if offset >= source_duration:
                break

            row = dict(source_event)

            row["beat"] = (
                source_beat
                + offset
            )

            # Overlap instead of little detached bleeps.
            row["duration"] = min(
                step_beats * 1.35,
                source_duration - offset,
            )

            row["pitch"] = pitch

            base_velocity = int(
                source_event.get(
                    "velocity",
                    58,
                )
            )

            row["velocity"] = max(
                34,
                base_velocity
                - index * 4,
            )

            row["lament_arpeggio"] = {
                "schema":
                    "dio.sonoris.lament_arpeggio.v2",

                "shape":
                    shape,

                "index":
                    index,

                "notes_requested":
                    note_count,

                "step_beats":
                    step_beats,

                "sequence":
                    sequence,

                "physical_pitch_classes":
                    pcs,
            }

            result.append(row)

    return result


def _black_metal_key_events(
    governed: Mapping[str, Any],
    *,
    physical: Mapping[str, Any],
    request: Mapping[str, Any],
    bpm: int,
    tonal_center: str,
) -> list[dict[str, Any]]:
    """
    Generate ONE atmospheric keyboard layer locked to the
    realized black-metal guitar harmony.

    Important law:

        keys do NOT run on an independent clock.

    Every key entrance occurs at a guitar harmonic boundary.
    The key pitch is derived from the physical guitar voicing,
    so it reinforces the song instead of laying an unrelated
    melody over it.
    """

    cfg = dict(
        request.get("atmospheric_keys")
        or {}
    )

    if not cfg.get("enabled"):
        return []

    kind = str(
        cfg.get("kind")
        or "LAMENT_KEYS"
    )

    register = str(
        cfg.get("register")
        or "MID"
    )

    motion = str(
        cfg.get("motion")
        or "SLOW_CHAIN"
    )

    density = str(
        cfg.get("density")
        or "SPARSE"
    )

    guitar = list(
        physical.get(
            "roles",
            {}
        ).get(
            "rhythm_guitar",
            []
        )
    )

    if not guitar:
        return []

    TPQ = 480
    BAR_TICKS = TPQ * 4

    bars = int(
        governed["bars"]
    )

    # --------------------------------------------------------
    # 1. Find the physical harmonic state active in each bar.
    # --------------------------------------------------------

    by_bar: dict[int, list[dict[str, Any]]] = {}

    for row in guitar:
        bar = int(
            row["tick"]
            // BAR_TICKS
        )

        by_bar.setdefault(
            bar,
            [],
        ).append(row)

    bar_states = []

    previous = None

    for bar in range(bars):
        rows = by_bar.get(
            bar,
            []
        )

        if rows:
            first = min(
                rows,
                key=lambda row:
                    row["tick"],
            )

            pitches = tuple(
                int(x)
                for x in (
                    first.get("pitches")
                    or [
                        first["pitch"]
                    ]
                )
            )

            state = {
                "bar": bar,
                "root": int(
                    first["pitch"]
                ),
                "pitches": pitches,
                "shape_type": str(
                    first.get(
                        "shape_type"
                    )
                    or ""
                ),
                "function": str(
                    first.get(
                        "function"
                    )
                    or ""
                ),
            }

            previous = state

        elif previous is not None:
            state = dict(
                previous
            )

            state["bar"] = bar

        else:
            continue

        bar_states.append(
            state
        )

    if not bar_states:
        return []

    # --------------------------------------------------------
    # 2. Collapse identical neighboring harmony into spans.
    # --------------------------------------------------------

    spans = []

    current = None

    for state in bar_states:
        signature = (
            state["root"] % 12,
            tuple(
                p % 12
                for p
                in state["pitches"]
            ),
            state["shape_type"],
        )

        if (
            current is None
            or signature
            != current["signature"]
        ):
            if current is not None:
                current["end_bar"] = (
                    state["bar"]
                )

                spans.append(
                    current
                )

            current = {
                "signature": signature,
                "start_bar":
                    state["bar"],
                "end_bar":
                    state["bar"] + 1,
                "state": state,
            }

        else:
            current["end_bar"] = (
                state["bar"] + 1
            )

    if current is not None:
        spans.append(
            current
        )

    # --------------------------------------------------------
    # 3. Register mapping.
    #
    # Preserve pitch class while moving the note into the
    # requested atmospheric register.
    # --------------------------------------------------------

    register_center = {
        "LOW": 48,
        "MID": 60,
        "HIGH": 72,
    }.get(
        register,
        60,
    )

    def nearest_pitch(
        pitch_class: int,
    ) -> int:

        candidates = [
            pitch_class
            + 12 * octave
            for octave in range(
                2,
                8,
            )
        ]

        return min(
            candidates,
            key=lambda pitch:
                abs(
                    pitch
                    - register_center
                ),
        )

    # --------------------------------------------------------
    # 4. Voice-selection law.
    #
    # Every chosen pitch comes from the guitar's actual chord
    # or tremolo shape.
    #
    # Therefore the key layer cannot accidentally imply a
    # different harmony.
    # --------------------------------------------------------

    def atmospheric_pitch(
        state: Mapping[str, Any],
    ) -> int:

        pitches = tuple(
            int(x)
            for x in state[
                "pitches"
            ]
        )

        root = int(
            state["root"]
        )

        if kind == "COLD_DRONE":
            source = root

        elif kind == "CHOIR_SHADOW":
            # Upper guitar voice produces the spectral /
            # dissonant shadow where one exists.
            source = (
                max(pitches)
                if len(pitches) > 1
                else root
            )

        elif kind == "SUBLIMINAL_PAD":
            # Stay closer to the body of the harmony.
            ordered = sorted(
                pitches
            )

            source = (
                ordered[
                    len(ordered) // 2
                ]
                if ordered
                else root
            )

        else:
            # LAMENT_KEYS:
            #
            # Prefer the non-root voice of the physical
            # guitar shape. It inherits the song's minor
            # second / minor third / tritone / sixth dialect
            # automatically.
            non_root = [
                pitch
                for pitch in pitches
                if (
                    pitch % 12
                    != root % 12
                )
            ]

            source = (
                non_root[-1]
                if non_root
                else root
            )

        return nearest_pitch(
            source % 12
        )

    # --------------------------------------------------------
    # 5. Density controls WHICH harmonic states speak.
    #
    # It never creates a second independent harmonic clock.
    # --------------------------------------------------------

    if density == "SPARSE":
        selected = [
            span
            for index, span
            in enumerate(spans)
            if index % 2 == 0
        ]

    else:
        selected = spans

    events = []

    for ordinal, span in enumerate(
        selected
    ):
        start_bar = int(
            span["start_bar"]
        )

        end_bar = int(
            span["end_bar"]
        )

        span_beats = max(
            1.0,
            (
                end_bar
                - start_bar
            )
            * 4.0,
        )

        # Leave real darkness at the end of each harmonic span.
        if density == "SPARSE":
            gap_beats = min(
                1.5,
                span_beats * 0.35,
            )

        elif density == "BREATHING":
            gap_beats = min(
                0.75,
                span_beats * 0.20,
            )

        else:
            gap_beats = 0.12

        # SLOW_CHAIN now means:
        #
        # "follow the slow harmonic chain"
        #
        # not:
        #
        # "run a second metronome measured in seconds".
        duration = max(
            0.5,
            span_beats
            - gap_beats,
        )

        pitch = atmospheric_pitch(
            span["state"]
        )

        velocity = {
            "COLD_DRONE": 54,
            "SUBLIMINAL_PAD": 50,
            "CHOIR_SHADOW": 56,
            "LAMENT_KEYS": 58,
        }.get(
            kind,
            56,
        )

        events.append({
            "role": "keys",
            "beat": (
                start_bar
                * 4.0
            ),
            "duration": round(
                duration,
                5,
            ),
            "pitch": pitch,
            "velocity": velocity,
            "gesture":
                "ATMOSPHERIC_KEYS",
            "section": 0,
            "articulation":
                "ATMOSPHERIC_SUSTAIN",
            "function": kind,
            "phrase_id": (
                f"BM_HARMONY_SHADOW_"
                f"{ordinal}"
            ),
            "harmonic_source": {
                "root": span[
                    "state"
                ][
                    "root"
                ],
                "pitches": list(
                    span[
                        "state"
                    ][
                        "pitches"
                    ]
                ),
                "shape_type": span[
                    "state"
                ][
                    "shape_type"
                ],
                "function": span[
                    "state"
                ][
                    "function"
                ],
                "start_bar":
                    start_bar,
                "end_bar":
                    end_bar,
            },
        })

    if kind == "LAMENT_KEYS":
        events = _apply_lament_motion_v2(
            events,
            register=register,
        )

        events = _apply_lament_arpeggiation_v1(
            events,
            cfg=cfg,
            register=register,
        )

    return events

def _section_performance_audit(
    plan: Mapping[str, Any],
    events: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Summarize measurable part behavior by authored section, without scoring genre quality."""
    meter = str(plan.get("musical_frame", {}).get("meter", "4/4"))
    if meter == "free":
        beats_per_bar = 4.0
    else:
        numerator, denominator = (int(value) for value in meter.split("/", 1))
        beats_per_bar = numerator * 4.0 / denominator
    section_rows: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for section in plan.get("sections") or []:
        section_rows[int(section["index"])] = {role: [] for role in events}
    plan_sections = list(plan.get("sections") or [])
    for role, rows in events.items():
        for row in rows:
            matched_index = None
            try:
                bar = int(float(row["beat"]) // beats_per_bar)
                matched = next((section for section in plan_sections
                                if int(section["start_bar"]) <= bar < int(section["end_bar"])), None)
                if matched is not None:
                    matched_index = int(matched["index"])
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                pass
            if matched_index is None:
                try:
                    candidate = int(row.get("section", row.get("section_index", -1)))
                    if candidate in section_rows:
                        matched_index = candidate
                    elif candidate + 1 in section_rows:
                        matched_index = candidate + 1
                except (TypeError, ValueError):
                    pass
            if matched_index in section_rows:
                section_rows[matched_index][role].append(row)

    sections = []
    for section in plan.get("sections") or []:
        section_index = int(section["index"])
        bars = max(1, int(section["bars"]))
        roles = {}
        for role, rows in section_rows[section_index].items():
            selected = rows
            articulations: dict[str, int] = {}
            pitches: dict[str, int] = {}
            for row in selected:
                name = str(row.get("articulation") or "").strip()
                if name:
                    articulations[name] = articulations.get(name, 0) + 1
                if row.get("pitch") is not None:
                    pitch = str(int(row["pitch"]))
                    pitches[pitch] = pitches.get(pitch, 0) + 1
            roles[role] = {
                "event_count": len(selected),
                "events_per_bar": round(len(selected) / bars, 2),
                "mean_velocity": round(
                    sum(int(row.get("velocity", 0)) for row in selected) / len(selected), 2
                ) if selected else None,
                "articulations": dict(sorted(articulations.items())),
                "midi_pitch_counts": dict(sorted(pitches.items(), key=lambda item: int(item[0]))),
            }
        sections.append({
            "index": section_index,
            "name": section.get("name") or section.get("gesture") or f"Section {section_index}",
            "gesture": section.get("gesture"),
            "bars": bars,
            "roles": roles,
        })
    return {
        "schema": "dio.sonoris.section_performance_audit.v1",
        "measurement_boundary": "Counts, density, velocities, and authored articulations are measured from the compiled event plan; genre quality and audible result require human review.",
        "sections": sections,
    }


def compile_song(request: Mapping[str, Any], *, output_root: Path = OUTPUT_ROOT, job_id: str | None = None) -> dict[str, Any]:

    request = dict(request)

    if request.get("genre") == "black_metal":
        keys = dict(BM_KEYS_DEFAULTS)
        keys.update(
            request.get("atmospheric_keys")
            or {}
        )
        request["atmospheric_keys"] = keys

    genre = str(request.get("genre") or "")
    catalog = _read_catalog()
    if genre not in catalog["profiles"]: raise ValueError(f"unknown Sonoris genre: {genre}")
    profile = catalog["profiles"][genre]
    metal_profile = metal_models()["profiles"].get(genre)
    seed = int(request.get("seed", 2306))
    if not 0 <= seed <= 2**31-1: raise ValueError("seed must be between 0 and 2147483647")
    gain_db = float(request.get("gain_db") or 0)
    if not -18 <= gain_db <= 12: raise ValueError("gain_db must be between -18 and +12")
    center = str(request.get("tonal_center") or (metal_profile["tonal_center"] if metal_profile else "D-minor" if profile["family"] in {"metal", "ambient"} else "C-major"))
    _key_pitch(center)
    title = str(request.get("title") or f"{profile['label']} · {request.get('song_type') or 'study'}").strip()[:120]
    brief = {"genre": genre, "song_type": request.get("song_type"), "title": title,
             "tempo_bpm": request.get("tempo_bpm"), "meter": request.get("meter"),
             "bars": request.get("bars"), "tonal_center": center, "mood": request.get("mood") or "genre study"}
    if genre == "black_metal" and brief["bars"] is None:
        brief["bars"] = {"drive": 88, "space": 96, "fracture": 104}.get(str(request.get("song_type") or ""), 88)
    brief = {key: value for key, value in brief.items() if value is not None and value != ""}
    plan = compile_composition_request(brief)

    if (
        str(request.get("genre") or "")
        == "synthwave"
        and str(
            request.get("song_type")
            or ""
        )
        == "dark_aggro"
    ):
        dark_blueprint = (
            compose_dark_aggro_blueprint(
                seed=seed,
                bars=int(
                    plan[
                        "musical_frame"
                    ][
                        "bars"
                    ]
                ),
                tonal_center=str(
                    plan[
                        "musical_frame"
                    ][
                        "tonal_center"
                    ]
                ),
            )
        )

        plan[
            "musical_frame"
        ][
            "tempo_bpm"
        ] = dark_blueprint.bpm
    black_metal_production = str(
        request.get(
            "black_metal_production"
        )
        or "TERMINAL_DISEASE_V1"
    )

    if black_metal_production not in {
        "TERMINAL_DISEASE_V1",
        "STANDARD",
    }:
        raise ValueError(
            "unsupported black metal production: "
            + black_metal_production
        )

    modules = _default_modules(genre, profile["family"])
    if genre == "folk_metal":
        modules["folk"] = {"drive":"bagpipe_sampled", "space":"flute_sampled", "fracture":"accordion_sampled"}.get(str(request.get("song_type") or "drive"), "bagpipe_sampled")
    supplied_modules = dict(
        request.get("modules")
        or {}
    )

    modules.update(
        supplied_modules
    )

    song_type = str(
        request.get("song_type")
        or ""
    )

    if (
        genre == "synthwave"
        and song_type == "dark_aggro"
    ):
        dark_defaults = {
            "harmony": "gm_synth_pad",
            "bass": "gm_synth_bass",
            "lead": "gm_synth_lead",
            "drums": "gm_electronic_kit",
            "keys": "native_aggro_triple_saw",
            "folk": "off",
        }

        # Apply specialist defaults only where the operator
        # did not explicitly choose something else.
        for role, module_id in (
            dark_defaults.items()
        ):
            if role not in supplied_modules:
                modules[role] = module_id

    if genre == "black_metal":
        keys_cfg = dict(
            request.get("atmospheric_keys")
            or {}
        )

        if keys_cfg.get("enabled"):
            kind = str(
                keys_cfg.get("kind")
                or "LAMENT_KEYS"
            )

            if modules.get("keys") == "off":
                modules["keys"] = (
                    "gm_choir"
                    if kind == "CHOIR_SHADOW"
                    else "gm_synth_pad"
                )
    for role, module_id in modules.items():
        if role not in MODULES or module_id not in MODULES[role]: raise ValueError(f"unsupported {role} module: {module_id}")
        if "sfz" in MODULES[role][module_id] and not Path(MODULES[role][module_id]["sfz"]).is_file():
            raise ValueError(f"selected {role} SFZ module is not installed")
    metal_models_data = metal_models()
    tone_profiles = metal_models_data["tone_profiles"]
    selected_tone_profile = str(request.get("tone_profile") or _default_tone(genre, metal_models_data["profiles"]))
    if selected_tone_profile not in tone_profiles: raise ValueError(f"unknown guitar tone profile: {selected_tone_profile}")
    has_guitar = any(
        MODULES[role].get(module_id, {}).get("instrument_family") == "guitar"
        for role, module_id in modules.items()
        if role in {"harmony", "lead"}
    )
    tone_profile = selected_tone_profile if has_guitar else "clean_chime"
    guitar_drive_value = float(request.get("guitar_drive") if request.get("guitar_drive") is not None else tone_profiles[tone_profile]["drive"])
    if not 0 <= guitar_drive_value <= 1: raise ValueError("guitar_drive must be between 0 and 1")
    guitar_drive = guitar_drive_value if has_guitar else None
    mix_levels = {"harmony": .78, "lead": .58, "bass": .95, "drums": 1.15, "keys": .42, "folk": .8}
    mix_levels.update(
        dict(
            request.get("mix_levels")
            or {}
        )
    )

    if genre == "black_metal":
        keys_cfg = dict(
            request.get("atmospheric_keys")
            or {}
        )

        if keys_cfg.get("enabled"):
            level_db = float(
                keys_cfg.get(
                    "level_db",
                    -14.0,
                )
            )

            mix_levels["keys"] = (
                10.0
                ** (
                    level_db / 20.0
                )
            )
    if set(mix_levels)-set(MODULES) or any(not 0 <= float(value) <= 2 for value in mix_levels.values()):
        raise ValueError("mix levels must be between 0 and 2 for known roles")
    mix_levels = {key: float(value) for key,value in mix_levels.items()}
    tuning = str(request.get("tuning") or (metal_profile["tuning"] if metal_profile else "D_standard" if genre=="black_metal" else "E_standard"))
    if tuning not in metal_models()["tuning_presets"]: raise ValueError(f"unknown tuning: {tuning}")
    if genre == "black_metal":
        governed = compile_black_metal_governed_plan(seed=seed,title=title,tonal_center=center,bars=plan["musical_frame"]["bars"],
                                                      mood=brief["mood"],bpm=plan["musical_frame"]["tempo_bpm"])
        governed = (
            apply_black_metal_continuity(
                governed
            )
        )

        physical = compile_physical_performance(
            governed,
            seed=seed,
        )

        events = _physical_events(
            physical
        )

        render_intent = (
            compile_black_metal_render_intent(
                governed
            )
        )

        events["keys"] = (
            _black_metal_key_events(
                governed,
                physical=physical,
                request=request,
                bpm=int(
                    plan[
                        "musical_frame"
                    ][
                        "tempo_bpm"
                    ]
                ),
                tonal_center=center,
            )
        )

        metal_signature = None
    elif genre == "thrash_metal":
        governed = physical = render_intent = None

        thrash_specialist = (
            compile_thrash_specialist(
                seed=seed,
            )
        )

        plan["musical_frame"]["tempo_bpm"] = (
            thrash_specialist[
                "tempo_bpm"
            ]
        )

        plan["musical_frame"]["meter"] = (
            thrash_specialist[
                "meter"
            ]
        )

        plan["musical_frame"]["bars"] = (
            thrash_specialist[
                "bars"
            ]
        )

        events = (
            thrash_specialist[
                "events"
            ]
        )

        metal_signature = {
            "schema":
                "dio.sonoris.thrash_specialist_signature.v1",

            "engine":
                thrash_specialist[
                    "engine"
                ],

            "seed":
                seed,

            "event_counts":
                thrash_specialist[
                    "event_counts"
                ],
        }

    elif metal_profile:
        governed = physical = render_intent = None
        thrash_specialist = None

        events, metal_signature = realize_metal(
            plan,
            seed=seed,
            tuning=tuning,
        )
        if genre == "folk_metal" and modules["folk"] != "bagpipe_sampled":
            events["folk"] = [row for row in events["folk"] if row.get("articulation") != "drone"]
    else:
        governed = physical = render_intent = None
        events = _seed_events(plan,seed)
        metal_signature = None
    guitar_attack = float(request.get("guitar_attack") if request.get("guitar_attack") is not None else 1)
    drum_intensity = float(request.get("drum_intensity") if request.get("drum_intensity") is not None else 1)
    if not .25 <= guitar_attack <= 1.5: raise ValueError("guitar_attack must be between 0.25 and 1.5")
    if not .25 <= drum_intensity <= 1.5: raise ValueError("drum_intensity must be between 0.25 and 1.5")
    for role, factor in (("harmony", guitar_attack), ("lead", guitar_attack), ("drums", drum_intensity)):
        if role in {"harmony", "lead"} and MODULES[role].get(modules[role], {}).get("instrument_family") != "guitar":
            continue
        for note in events[role]:
            note["velocity"] = max(1, min(127, round(note["velocity"] * factor)))
    job_id = job_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    if not all(ch.isalnum() or ch in "-_" for ch in job_id) or len(job_id)>80: raise ValueError("invalid job_id")
    out = output_root.resolve() / job_id
    out.mkdir(parents=True, exist_ok=False)
    _json(out / "COMPOSITION_PLAN.json", plan)
    _json(out / "SONG_EVENTS.json", events)
    section_audit = _section_performance_audit(plan, events)
    _json(out / "SECTION_PERFORMANCE_AUDIT.json", section_audit)
    if governed is not None:
        _json(out / "BLACK_METAL_GOVERNED_PLAN.json", governed)
        _json(out / "BLACK_METAL_PHYSICAL_PLAN.json", physical)
        _json(out / "BLACK_METAL_RENDER_INTENT.json", render_intent)
    if metal_signature is not None:
        _json(out / "METAL_PATTERN_SIGNATURE.json", metal_signature)
    _midi(out / "SONG_CANDIDATE.mid", events, plan["musical_frame"]["tempo_bpm"], modules)
    receipt = {"schema": "dio.sonoris.studio_song.v1", "job_id": job_id, "state": "COMPILED",
               "composition_engine": ("CHAINSAW_DIPLOMACY" if genre == "thrash_metal" else "BLACK_METAL_GOVERNED" if genre == "black_metal" else "DARK_AGGRO_SPECIALIST" if genre == "synthwave" and song_type == "dark_aggro" else "REALIZE_METAL" if metal_profile else "GENERIC_SEED_EVENTS"),
               "genre": genre, "song_type": (plan["grammar"].get("song_type") or {}).get("key"),
               "title": title, "seed": seed, "tempo_bpm": plan["musical_frame"]["tempo_bpm"],
               "gain_db": gain_db,
               "meter": plan["musical_frame"]["meter"], "bars": plan["musical_frame"]["bars"],
               "tonal_center": center, "tuning": tuning if has_guitar else None, "tone_profile": tone_profile if has_guitar else None,
               "guitar_drive": guitar_drive, "guitar_attack": guitar_attack if has_guitar else None,
               "drum_intensity": drum_intensity, "mix_levels": mix_levels,
               "black_metal_production": black_metal_production,
               "atmospheric_keys": dict(
                   request.get("atmospheric_keys")
                   or {}
               ),
               "modules": modules, "metal_pattern_signature": metal_signature,
               "event_counts": {role:len(rows) for role,rows in events.items()},
               "section_performance_audit": {
                   "path": "SECTION_PERFORMANCE_AUDIT.json",
                   "schema": section_audit["schema"],
                   "sha256": hashlib.sha256((out/"SECTION_PERFORMANCE_AUDIT.json").read_bytes()).hexdigest(),
               },
               "plan_sha256": hashlib.sha256((out/"COMPOSITION_PLAN.json").read_bytes()).hexdigest(),
               "events_sha256": hashlib.sha256((out/"SONG_EVENTS.json").read_bytes()).hexdigest(),
               "midi_sha256": hashlib.sha256((out/"SONG_CANDIDATE.mid").read_bytes()).hexdigest(),
               "audio_state": "NOT_RENDERED", "human_listening_review_required": True,
               "release_authorized": False, "commercial_rights_verified": False,
               "claim_boundary": "A composition and MIDI candidate, not a verified genre master or release."}
    _json(out / "SONORIS_STUDIO_RECEIPT.json", receipt)
    return receipt


def render_song(job_id: str, *, output_root: Path = OUTPUT_ROOT, force: bool = False) -> dict[str, Any]:
    if not job_id or not all(ch.isalnum() or ch in "-_" for ch in job_id): raise ValueError("invalid job_id")
    sync_seed_library = output_root.resolve() == SEED_ROOT.resolve()
    out = output_root.resolve() / job_id
    receipt_path = out / "SONORIS_STUDIO_RECEIPT.json"
    if not receipt_path.is_file(): raise FileNotFoundError(job_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["audio_state"] == "RENDERED" and not force:
        if sync_seed_library:
            _sync_seed_manifest(receipt)
        return receipt
    events = json.loads((out/"SONG_EVENTS.json").read_text(encoding="utf-8"))
    if not SF2.is_file(): raise FileNotFoundError(SF2)
    if receipt.get("audio_state")=="RENDERED":
        receipt["previous_audio_sha256"]=(receipt.get("audio") or {}).get("mp3_sha256")
    stems=render_stems(out,events,receipt,MODULES,SF2,_midi)
    last_beat=max((row["beat"]+row["duration"] for rows in events.values() for row in rows),default=0)
    duration_seconds=last_beat*60/float(receipt["tempo_bpm"])+2.5
    final_wav,mp3=mix_stems(out,stems,master_gain_db=float(receipt.get("gain_db") or 0),duration_seconds=duration_seconds)
    receipt["audio_state"]="RENDERED"
    receipt["audio_processing"]={"method":"ffmpeg_loudnorm_one_pass", "target_lufs":-16,
                                  "true_peak_db":-1.5, "master_gain_db":float(receipt.get("gain_db") or 0)}
    receipt["audio_engine"]="sampled_stems_guitarix_v2"
    receipt["stems"]=[{"role":s["role"],"path":s["path"].name,"sha256":hashlib.sha256(s["path"].read_bytes()).hexdigest(),
                       "module":s["module"],"pan":s["pan"],"gain":s["gain"],"articulation":s.get("articulation")}
                      for s in stems]
    receipt["audio"]={"wav":"SONG_CANDIDATE.wav","wav_sha256":hashlib.sha256(final_wav.read_bytes()).hexdigest(),
                      "mp3":"SONG_CANDIDATE.mp3","mp3_sha256":hashlib.sha256(mp3.read_bytes()).hexdigest()}
    _json(receipt_path,receipt)
    if sync_seed_library:
        _sync_seed_manifest(receipt)
    for temporary in out.glob("*.raw.wav"):
        temporary.unlink(missing_ok=True)
    for suffix in ("*.di.wav", "*.amp.wav", "*.fuzz.wav"):
        for temporary in out.glob(suffix): temporary.unlink(missing_ok=True)
    for temporary in out.glob("*.mid"):
        if temporary.name != "SONG_CANDIDATE.mid": temporary.unlink(missing_ok=True)
    return receipt



SONORIS_GENRE_MATURITY = {
    "black_metal": {
        "state": "SPECIALIST",
        "engine": "black_metal_governed",
        "musical_reference": True,
    },

    "synthwave": {
        "state": "MIXED",
        "engine": "generic_plus_dark_aggro",
        "musical_reference": False,
        "specialist_song_types": [
            "dark_aggro",
        ],
    },

    # These currently compile through the generic Sonoris
    # seed-event grammar. They are useful integration fixtures,
    # NOT validated musical genre references.
    "thrash_metal": {
        "state": "GENERIC_FIXTURE",
        "engine": "generic_seed_events",
        "musical_reference": False,
    },

    "death_metal": {
        "state": "GENERIC_FIXTURE",
        "engine": "generic_seed_events",
        "musical_reference": False,
    },

    "doom_metal": {
        "state": "GENERIC_FIXTURE",
        "engine": "generic_seed_events",
        "musical_reference": False,
    },

    "folk_metal": {
        "state": "GENERIC_FIXTURE",
        "engine": "generic_seed_events",
        "musical_reference": False,
    },
}


def _genre_maturity(
    genre: str,
) -> dict[str, Any]:
    return dict(
        SONORIS_GENRE_MATURITY.get(
            genre,
            {
                "state": "GENERIC_FIXTURE",
                "engine": "generic_seed_events",
                "musical_reference": False,
            },
        )
    )


def studio_catalog() -> dict[str, Any]:
    snapshot=genre_catalog_snapshot()
    profiles=_read_catalog()["profiles"]
    metal=metal_models()
    genres={}
    for key,row in snapshot["genres"].items():
        profile=profiles[key]
        variants=profile.get("song_types") or []
        default_frame=compile_composition_request({"genre":key})["musical_frame"]
        song_type_defaults={}
        for variant in variants:
            frame=compile_composition_request({"genre":key,"song_type":variant["key"]})["musical_frame"]
            if key == "black_metal":
                frame["bars"] = {"drive": 88, "space": 96, "fracture": 104}.get(variant["key"], frame["bars"])
            song_type_defaults[variant["key"]]={"tempo_bpm":frame["tempo_bpm"],"meter":frame["meter"],"bars":frame["bars"]}
        if key == "black_metal":
            default_frame["bars"] = 88
        genres[key]=dict(row,meters=profile["meters"],tempo_ranges_bpm=profile.get("tempo_ranges") or [[profile["tempo_bpm"][0],profile["tempo_bpm"][3]]],
                         default_meter=default_frame["meter"],default_tempo_bpm=default_frame["tempo_bpm"],default_bars=default_frame["bars"],
                         preferred_bpm=profile["preferred_bpm"],song_type_defaults=song_type_defaults,
                         default_modules=_default_modules(key,profile["family"]),
                         default_tonal_center=metal["profiles"][key]["tonal_center"] if key in metal["profiles"] else "D-minor" if key=="black_metal" else "C-major",
                         default_tuning=metal["profiles"][key]["tuning"] if key in metal["profiles"] else "D_standard" if key=="black_metal" else "E_standard",
                         default_tone=_default_tone(key,metal["profiles"]),
                         style_observations=metal["profiles"][key]["observations"] if key in metal["profiles"] else "")
    for genre_key in genres:
        genres[genre_key]["maturity"] = (
            _genre_maturity(
                genre_key
            )
        )

    return {"schema":"dio.sonoris.studio_catalog.v1","genres":genres,"modules":module_snapshot(),
            "tunings":metal["tuning_presets"],"tone_profiles":metal["tone_profiles"],
            "catalog_sha256":snapshot["catalog_sha256"],"seed_library_path":str(SEED_ROOT),
            "render_state":"SAMPLED_STEMS_GUITARIX_V2","human_review_required":True}
