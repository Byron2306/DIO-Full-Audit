"""Original metal rhythm-section realizations from genre-level tab observations.

The cited scores inform density, articulation, role interaction and form only.
No melody, riff, note sequence or recording is transcribed into this generator.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Mapping

from products.sonoris_motif_dna import (
    generate_song_motif_dna,
    select_song_cell,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "config/sonoris/metal_style_models_v1.json"
ROLES = ("harmony", "lead", "bass", "drums", "keys", "folk")
PITCH_CLASS = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}


def metal_models() -> dict[str, Any]:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if model.get("schema") != "dio.sonoris.metal_style_models.v1":
        raise ValueError("unsupported metal style model")
    return model


def event(role: str, beat: float, duration: float, pitch: int, velocity: int, gesture: str,
          section: int, articulation: str = "") -> dict[str, Any]:
    return {"role": role, "beat": round(max(0, beat), 5), "duration": round(max(.06, duration), 5),
            "pitch": max(0, min(127, int(pitch))), "velocity": max(1, min(127, int(velocity))),
            "gesture": gesture, "section": section, "articulation": articulation}


def _drums(rows: list[dict[str, Any]], mode: str, t: float, beats: float, energy: float,
           gesture: str, section: int, bar_in_section: int, rng: random.Random) -> None:
    def hit(offset: float, pitch: int, vel: int, art: str) -> None:
        if 0 <= offset < beats:
            rows.append(event("drums", t+offset, .12, pitch, vel, gesture, section, art))
    velocity = lambda base: min(127, base + int(energy*16) + (0 if mode == "machine_grid" else rng.randint(-5,5)))
    if mode == "blast_breakdown":
        if "BREAKDOWN" in gesture or bar_in_section % 8 >= 6:
            kicks, snares, cymbals = [0,1.5,2.5], [min(2,beats-.25)], [i*.5 for i in range(math.ceil(beats*2))]
        else:
            kicks = [i*.25 for i in range(math.ceil(beats*4))]
            snares = [i*.5+.25 for i in range(math.ceil(beats*2))]
            cymbals = [i*.5 for i in range(math.ceil(beats*2))]
    elif mode == "thrash":
        kicks, snares, cymbals = [0,.5,1.5,2,2.5,3.5], [1,3], [i*.5 for i in range(math.ceil(beats*2))]
    elif mode == "gallop_double_kick":
        kicks, snares, cymbals = [i+sub for i in range(math.ceil(beats)) for sub in (0,.25,.5)], [1,3], [i*.5 for i in range(math.ceil(beats*2))]
    elif mode == "doom_half_time":
        kicks, snares, cymbals = [0, max(0,beats-.75)], [min(2,beats-.25)], [i for i in range(math.ceil(beats))]
    elif mode == "arena_backbeat":
        kicks, snares, cymbals = [0,2,2.75], [1,3], [i*.5 for i in range(math.ceil(beats*2))]
    elif mode == "folk_dance":
        kicks, snares, cymbals = [0,1.5,3], [min(1,beats-.25),min(2.5,beats-.25)], [i*.5 for i in range(math.ceil(beats*2))]
    elif mode == "odd_unison":
        kicks, snares, cymbals = [0,.75,2.25,3.25,4.25], [1.5,3.5], [i*.5 for i in range(math.ceil(beats*2))]
    elif mode == "machine_grid":
        kicks, snares, cymbals = [i for i in range(math.ceil(beats))], [1,3], [i*.25 for i in range(math.ceil(beats*4))]
    elif mode == "quiet_loud":
        heavy = section % 2 == 0
        kicks, snares, cymbals = ([0,1.5,2.5,3] if heavy else [0,2]), ([1,3] if heavy else [min(2,beats-.25)]), [i*(.5 if heavy else 1) for i in range(math.ceil(beats*(2 if heavy else 1)))]
    else:  # half-time syncopated nu metal
        kicks, snares, cymbals = [0,.75,1.75,2.75,3.5], [min(2,beats-.25)], [i*.5 for i in range(math.ceil(beats*2))]
    for k in kicks: hit(k,36,velocity(83),"kick")
    for s in snares: hit(s,38,velocity(86),"snare")
    for i,c in enumerate(cymbals): hit(c,51 if mode in {"doom_half_time","gallop_double_kick"} else 42,velocity(47 if i%2 else 54),"cymbal")
    if bar_in_section % 4 == 0: hit(0,49,velocity(78),"crash")
    if bar_in_section % 8 == 7:
        for k,p in enumerate((48,45,41)): hit(max(0,beats-1.5+k*.5),p,velocity(62),"fill")


def realize_metal(plan: Mapping[str, Any], *, seed: int, tuning: str | None = None) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    model = metal_models()
    genre = plan["grammar"]["primary"]["key"]
    if genre not in model["profiles"]: raise ValueError(f"no tab-informed metal model for {genre}")
    style = model["profiles"][genre]
    tuning = tuning or style["tuning"]
    if tuning not in model["tuning_presets"]: raise ValueError(f"unknown guitar tuning: {tuning}")
    meter = plan["musical_frame"]["meter"]
    numerator, denominator = (int(x) for x in meter.split("/"))
    beats_per_bar = numerator*4/denominator
    tonal_center = str(plan["musical_frame"]["tonal_center"])
    tonic = PITCH_CLASS.get(tonal_center.split("-")[0].upper())
    if tonic is None: raise ValueError("unsupported tonal center")
    open_low = int(model["tuning_presets"][tuning]["low_midi"])
    riff_root = open_low + (tonic-open_low)%12
    variant = (
        plan["grammar"]
        .get("song_type")
        or {}
    ).get("key") or "drive"

    rng = random.Random(seed)

    motif_dna = (
        generate_song_motif_dna(
            genre=genre,
            seed=seed,
            beats_per_bar=beats_per_bar,
        )
    )

    rows: dict[str, list[dict[str, Any]]] = {
        role: []
        for role in ROLES
    }
    section_count = len(plan["sections"])
    for section in plan["sections"]:
        sec = int(section["index"]); gesture = section["gesture"]
        quiet = genre in {"alternative_metal", "prog_metal"} and (sec%2 == 1 or "TEXTURE" in gesture)
        energy = (.64 if variant == "space" else .91 if variant == "drive" else .78)
        energy *= .55 if quiet else 1
        if sec == section_count and "DECAY" in gesture: energy *= .48
        for bar in range(section["start_bar"], section["end_bar"]):
            t = bar*beats_per_bar; bar_in_section=bar-section["start_bar"]
            route = (
                motif_dna.harmonic_route
            )

            harmonic_index = (
                bar // 4
            ) % len(route)

            root = (
                riff_root
                + route[
                    harmonic_index
                ]
            )

            motif_cell = (
                select_song_cell(
                    motif_dna,
                    section_index=sec,
                    bar_in_section=(
                        bar_in_section
                    ),
                    variant=variant,
                )
            )

            onsets = [
                (
                    float(offset),
                    int(degree),
                )
                for offset, degree
                in zip(
                    motif_cell.onsets,
                    motif_cell.degrees,
                )
                if offset
                < beats_per_bar
            ]

            if quiet:
                onsets = onsets[::2]
            if not onsets: onsets=[(0,0)]
            for i,(offset,degree) in enumerate(onsets):
                next_offset = onsets[i+1][0] if i+1<len(onsets) else beats_per_bar
                gap=max(.12,next_offset-offset)
                sustain = genre in {"doom_metal","glam_metal","folk_metal"} or (genre=="power_metal" and degree!=0)
                articulation = "clean" if quiet else "sustain" if sustain or (degree!=0 and i%3==0) else "mute"
                if genre=="industrial_metal": articulation="mute" if i%3 else "sustain"
                duration = min(beats_per_bar-offset,max(.13,gap*(.92 if articulation!="mute" else .6)))
                pitch=root+degree
                velocity=int(68+energy*47+(6 if offset==0 else 0)+(0 if genre=="industrial_metal" else rng.randint(-5,5)))
                chord=(0,7,12) if genre in {"doom_metal","power_metal","glam_metal"} and articulation=="sustain" else (0,7) if articulation=="sustain" else (0,)
                for step in chord:
                    rows["harmony"].append(event("harmony",t+offset,duration,pitch+step,velocity,gesture,sec,articulation))
                # The bass plays a separate, audible low line. The sampled four-string pack is rendered at playable pitch and shifted down one octave.
                if style["bass"] in {"locked_pick","unison_then_counter","synth_unison","locked_low"} or i%2==0:
                    bass_degree=degree if style["bass"]!="counterpoint" else (degree+5 if i%3==2 else degree)
                    rows["bass"].append(event("bass",t+offset,min(gap*.82,1.5),pitch+bass_degree-degree-12,
                                              min(127,velocity-6),gesture,sec,"pick" if style["bass"] in {"locked_pick","unison_then_counter"} else "sustain"))
            _drums(rows["drums"],style["drums"],t,beats_per_bar,energy,gesture,sec,bar_in_section,rng)
            # Lead motifs answer the riff every few bars; power metal adds a harmonized line.
            lead_active=(bar_in_section%4==2 or ("SOLO" in gesture and bar_in_section%2==0)) and not quiet and genre not in {"industrial_metal","nu_metal"}
            if lead_active:
                lead_steps = (
                    motif_dna.lead_pool
                )
                span=2 if genre=="doom_metal" else 4 if genre in {"power_metal","glam_metal","prog_metal"} else 3
                for j in range(span):
                    offset=j*beats_per_bar/span
                    pitch=root+12+lead_steps[(j+sec)%len(lead_steps)]
                    length=beats_per_bar/span*(.9 if genre=="doom_metal" else .7)
                    rows["lead"].append(event("lead",t+offset,length,pitch,int(68+energy*37),gesture,sec,"lead"))
                    if genre=="power_metal": rows["lead"].append(event("lead",t+offset,length,pitch+4,int(62+energy*31),gesture,sec,"harmony_third"))
            if style["extra"]=="folk":
                # Modal reed melody and drone use the same tonic but occupy their own instrument stem.
                folk_root=60+tonic
                if folk_root<65:folk_root+=12
                for j,step in enumerate(style["lead_degrees"][:4]):
                    offset=j*beats_per_bar/4
                    rows["folk"].append(event("folk",t+offset,beats_per_bar/4*.82,folk_root+step,
                                              int(64+energy*31),gesture,sec,"folk_melody"))
                if bar_in_section%4==0:
                    rows["folk"].append(event("folk",t,beats_per_bar*min(4,section["end_bar"]-bar),36+tonic,
                                              int(47+energy*14),gesture,sec,"drone"))
            elif style["extra"]=="keys":
                if genre=="industrial_metal":
                    for offset in (0,1,2,3):
                        if offset<beats_per_bar:rows["keys"].append(event("keys",t+offset,.35,root+24,72,gesture,sec,"machine_pulse"))
                elif genre=="nu_metal":
                    if bar_in_section%2==0:rows["keys"].append(event("keys",t,beats_per_bar*.8,root+24,55,gesture,sec,"texture"))
                else:
                    for step in (0,3 if "minor" in tonal_center else 4,7):
                        rows["keys"].append(event("keys",t,beats_per_bar*.88,root+24+step,int(44+energy*28),gesture,sec,"pad"))
    signature = {
        "schema": (
            "dio.sonoris."
            "metal_pattern_signature.v2"
        ),
        "genre": genre,
        "tuning": tuning,
        "open_low_midi": open_low,
        "root_midi": riff_root,
        "tone_profile": style["tone"],
        "drum_mode": style["drums"],
        "bass_mode": style["bass"],
        "extra_role": style["extra"],

        "motif_dna": (
            motif_dna.as_dict()
        ),

        "composition_source": (
            "generated_song_specific_motif_dna"
        ),

        "source_phrase_reuse": False,

        "research_basis": {
            "kind": (
                "abstract_genre_observation"
            ),
            "observations": style.get(
                "observations",
                "",
            ),
        },

        "originality_boundary": (
            "Genre observations constrain "
            "probabilities and performance "
            "behavior only. Executable riff "
            "cells and harmonic routes are "
            "generated per song seed."
        ),
    }

    return rows, signature
