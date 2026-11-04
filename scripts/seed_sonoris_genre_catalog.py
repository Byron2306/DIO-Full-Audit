#!/usr/bin/env python3
"""Seed researched Sonoris genre grammars without changing black-metal canon.

Reference artists are listening landmarks, never templates for copying notes,
melodies, arrangements, performances, or recordings.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "config/sonoris/genre_grammars_v1.json"

SOURCES = {
    "synthwave": "https://www.berklee.edu/berklee-now/news/electronic-music-genres-a-guide-to-the-most-influential-styles",
    "jazz": "https://online.berklee.edu/courses/jazz-composition",
    "jazz_modal": "https://online.berklee.edu/takenote/harmonic-considerations-modal-harmony/",
    "metal": "https://academic.oup.com/book/62310/chapter/552774426",
    "metal_taxonomy": "https://digitalspace.bradfordcollege.ac.uk/10633466/wp-content/uploads/sites/568/2025/01/ConsideringGenreinMetalMusicFINAL.pdf",
    "rock": "https://academic.oup.com/book/6294/chapter-abstract/149978188",
    "prog_rock": "https://academic.oup.com/book/49450/chapter-abstract/422323295",
    "grunge": "https://rockhall.com/inductees/soundgarden/",
}

# bpm=(allowed low, preferred low, preferred high, allowed high)
# groove and harmony are executable seeder vocabularies, not just descriptions.
STYLES = {
    "jazz": ("Jazz", "jazz", (65, 90, 155, 225), ["4/4", "3/4", "5/4"], "swing", "ii_v_i", "piano,bass,drums,sax", "head,solo,trade,head_return", "Duke Ellington,Miles Davis,John Coltrane", "swing head|modal conversation|late night ballad", "jazz"),
    "death_metal": ("Death metal", "metal", (125, 160, 225, 250), ["4/4", "6/8"], "blast", "chromatic_minor", "guitar,bass,drums", "riff,blast,breakdown,mutation", "Death,Morbid Angel,Cannibal Corpse", "technical assault|melodic descent|cavernous crush", "metal_taxonomy"),
    "folk_metal": ("Folk metal", "metal", (95, 120, 175, 205), ["4/4", "6/8", "3/4"], "dance", "modal_minor", "guitar,bass,drums,folk_lead", "folk_theme,heavy_riff,dance_return,ritual_coda", "Korpiklaani,Eluveitie,Ensiferum", "festival dance|epic march|acoustic rite", "metal_taxonomy"),
    "power_metal": ("Power metal", "metal", (115, 145, 195, 225), ["4/4", "6/8"], "gallop", "minor_major_lift", "guitar,bass,drums,keys", "gallop,anthem,solo,final_lift", "Helloween,Blind Guardian,DragonForce", "heroic gallop|anthemic ascent|neoclassical chase", "metal_taxonomy"),
    "thrash_metal": ("Thrash metal", "metal", (140, 175, 230, 260), ["4/4", "5/4"], "thrash", "chromatic_minor", "guitar,bass,drums", "downpick_riff,speed_run,stop_start,return", "Metallica,Slayer,Megadeth", "speed assault|midtempo stomp|crossover sprint", "metal"),
    "doom_metal": ("Doom metal", "metal", (45, 60, 105, 125), ["4/4", "6/8"], "doom", "minor_drone", "guitar,bass,drums,organ", "weight,slow_turn,feedback,decay", "Black Sabbath,Candlemass,Electric Wizard", "funeral crawl|traditional lament|stoner hypnosis", "metal_taxonomy"),
    "industrial_metal": ("Industrial metal", "metal", (85, 105, 155, 180), ["4/4"], "machine", "chromatic_minor", "guitar,synth_bass,drums,noise", "machine_loop,metal_intrusion,drop,mechanical_return", "Ministry,Nine Inch Nails,Rammstein", "machine march|dystopian pulse|noise collapse", "metal_taxonomy"),
    "nu_metal": ("Nu metal", "metal", (75, 90, 135, 155), ["4/4"], "syncopated", "minor_pedal", "guitar,bass,drums,texture", "groove,space,impact,hook", "Korn,Deftones,Slipknot", "low groove|quiet impact|percussive bounce", "metal_taxonomy"),
    "glam_metal": ("Glam metal", "metal", (85, 105, 155, 180), ["4/4", "6/8"], "arena", "major_minor_hook", "guitar,bass,drums,keys", "hook,verse,solo,final_hook", "Def Leppard,Mötley Crüe,Poison", "arena anthem|power ballad|shuffle strut", "metal_taxonomy"),
    "prog_metal": ("Progressive metal", "metal", (75, 95, 175, 220), ["4/4", "5/4", "7/8"], "odd", "modal_shift", "guitar,bass,drums,keys", "asymmetry,unison,development,return", "Dream Theater,Opeth,Tool", "polymetric engine|atmospheric suite|technical dialogue", "metal"),
    "alternative_metal": ("Alternative metal", "metal", (75, 95, 155, 190), ["4/4", "7/8"], "syncopated", "minor_pedal", "guitar,bass,drums,texture", "texture,groove,rupture,hook", "Faith No More,System of a Down,Tool", "angular groove|atmospheric weight|dissonant hook", "metal_taxonomy"),
    "hard_rock": ("Hard rock", "rock", (90, 110, 160, 190), ["4/4", "6/8"], "backbeat", "blues_rock", "guitar,bass,drums,organ", "riff,verse,chorus,solo", "Led Zeppelin,AC/DC,Deep Purple", "blues riff|arena drive|slow burn", "rock"),
    "math_rock": ("Math rock", "rock", (75, 100, 165, 205), ["5/4", "7/8", "4/4"], "odd", "modal_shift", "clean_guitar,bass,drums", "angular_motif,displacement,interlock,return", "Don Caballero,Battles,American Football", "angular interlock|clean tapping|stop start", "rock"),
    "post_rock": ("Post-rock", "rock", (55, 75, 130, 155), ["4/4", "6/8"], "crescendo", "modal_drone", "clean_guitar,bass,drums,keys", "texture,slow_build,eruption,afterglow", "Mogwai,Godspeed You! Black Emperor,Explosions in the Sky", "slow crescendo|ambient drift|rhythmic swell", "rock"),
    "prog_rock": ("Progressive rock", "rock", (75, 95, 165, 195), ["4/4", "5/4", "7/8", "6/8"], "odd", "modal_shift", "guitar,bass,drums,organ", "overture,theme,development,reprise", "King Crimson,Yes,Genesis", "miniature suite|organ dialogue|pastoral arc", "prog_rock"),
    "folk_rock": ("Folk rock", "rock", (70, 90, 135, 160), ["4/4", "3/4", "6/8"], "folk", "modal_major", "acoustic_guitar,bass,drums,folk_lead", "story,verse,refrain,return", "The Byrds,Fairport Convention,Jethro Tull", "acoustic narrative|electric folk|waltz refrain", "rock"),
    "indie_rock": ("Indie rock", "rock", (85, 105, 155, 185), ["4/4", "6/8"], "jangle", "major_minor_hook", "clean_guitar,bass,drums,keys", "motif,verse,hook,contrast", "Pavement,The Strokes,Arctic Monkeys", "jangle hook|lofi push|wide chorus", "rock"),
    "grunge": ("Grunge", "rock", (70, 90, 145, 175), ["4/4", "6/8"], "quiet_loud", "minor_pedal", "guitar,bass,drums", "quiet_verse,heavy_hook,breakdown,return", "Nirvana,Soundgarden,Alice in Chains", "quiet loud|sludge weight|punk surge", "grunge"),
}


def make_profile(key: str, data: tuple) -> dict:
    label, family, bpm, meters, groove, harmony, roles, arc, artists, song_types, source = data
    sections = [x.strip().replace('_', ' ').title() for x in arc.split(',')]
    gestures = [x.strip().upper() for x in arc.split(',')]
    form = [{"section": name, "gesture": gesture, "bars": 4 if i in (0, len(sections)-1) else 8}
            for i, (name, gesture) in enumerate(zip(sections, gestures))]
    types = [x.strip() for x in song_types.split('|')]
    variants = [
        {"key": "drive", "label": types[0], "tempo_factor": 1.12, "energy": 0.86, "bar_factor": 1.0},
        {"key": "space", "label": types[1], "tempo_factor": 0.83, "energy": 0.55, "bar_factor": 1.2},
        {"key": "fracture", "label": types[2], "tempo_factor": 1.0, "energy": 0.73, "bar_factor": 1.4},
    ]
    return {
        "id": key.upper(), "label": label, "family": family, "tempo_bpm": list(bpm),
        "preferred_bpm": (bpm[1]+bpm[2])//2, "tempo_ranges": [[bpm[0],bpm[3]]],
        "meters": meters, "default_meter": meters[0],
        "structural_laws": {"motif_development_required": True, "section_contrast_required": True,
                            "instrument_interaction_required": True, "human_performance_review_required": True},
        "harmony": {"center": "minor" if "minor" in harmony or "chromatic" in harmony or "drone" in harmony else "modal",
                    "behaviors": [harmony, "motif_harmonic_variation"], "avoid": ["unchanging one-bar loop as the only form"]},
        "performance": {"groove": [groove], "ensemble": ["role interplay", "phrase variation", "dynamic contrast"]},
        "production": [f"{family} timbre contrast", "section-specific dynamics", "human review of tone and articulation"],
        "roles": {"lead_and_harmony": [x.strip() for x in roles.split(',')], "rhythm_section": ["bass", "drums"]},
        "gestures": {gesture: f"{label} {name.lower()} with {groove} pulse and {harmony} harmony"
                     for name, gesture in zip(sections, gestures)},
        "form": form, "rhythm_topology": groove, "harmony_topology": harmony,
        "reference_artists": [x.strip() for x in artists.split(',')],
        "research_source": SOURCES[source], "song_types": variants,
        "reference_boundary": "Study structural traits only; do not reproduce an artist's melody, riff, recording or performance.",
    }


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for key, data in STYLES.items():
        catalog["profiles"][key] = make_profile(key, data)
    catalog["profiles"]["synthwave"]["song_types"] = [
        {"key": "drive", "label": "Outrun pursuit", "tempo_factor": 1.10, "energy": .88, "bar_factor": 1.0},
        {"key": "space", "label": "Dreamwave nocturne", "tempo_factor": .80, "energy": .48, "bar_factor": 1.2},
        {"key": "fracture", "label": "Darkwave descent", "tempo_factor": .95, "energy": .74, "bar_factor": 1.3},
    ]
    catalog["profiles"]["synthwave"]["reference_artists"] = ["Tangerine Dream", "Vangelis", "The Midnight"]
    catalog["profiles"]["synthwave"]["research_source"] = SOURCES["synthwave"]
    catalog["profiles"]["black_metal"]["song_types"] = [
        {"key": "drive", "label": "Frost assault", "tempo_factor": 1.05, "energy": .92, "bar_factor": 1.0},
        {"key": "space", "label": "Lament and winter", "tempo_factor": .91, "energy": .69, "bar_factor": 1.2},
        {"key": "fracture", "label": "War ascent", "tempo_factor": 1.0, "energy": .84, "bar_factor": 1.3},
    ]
    catalog["profiles"]["jazz_fusion"]["song_types"] = [
        {"key": "drive", "label": "Electric pocket", "tempo_factor": 1.08, "energy": .82, "bar_factor": 1.0},
        {"key": "space", "label": "Modal glide", "tempo_factor": .85, "energy": .55, "bar_factor": 1.2},
        {"key": "fracture", "label": "Odd meter exchange", "tempo_factor": 1.0, "energy": .75, "bar_factor": 1.3},
    ]
    catalog["profiles"]["rock"]["song_types"] = [
        {"key": "drive", "label": "Riff drive", "tempo_factor": 1.08, "energy": .83, "bar_factor": 1.0},
        {"key": "space", "label": "Open road", "tempo_factor": .86, "energy": .56, "bar_factor": 1.2},
        {"key": "fracture", "label": "Bridge break", "tempo_factor": 1.0, "energy": .73, "bar_factor": 1.3},
    ]
    catalog["research_sources"] = SOURCES
    catalog["compiler_version"] = "0.2.0"
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"profiles": len(catalog["profiles"]), "seeded": len(STYLES), "variants": sum(len(p.get("song_types") or []) for p in catalog["profiles"].values())}))


if __name__ == "__main__":
    main()
