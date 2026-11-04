from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PHYSICAL_PLAN = (
    ROOT
    / "media/sonoris/releases/"
    / "black_metal_where_pines_forget_v3/"
    / "SONORIS_PHYSICAL_PERFORMANCE_PLAN.json"
)

OUT = (
    ROOT
    / "media/sonoris/releases/"
    / "black_metal_where_pines_full_v1"
)

DEST = (
    OUT
    / "SONORIS_FULL_PHYSICAL_PERFORMANCE_PLAN.json"
)

TPQ = 480
BAR_TICKS = TPQ * 4
BPM = 168


# ============================================================
# ORIGINAL GOVERNED SONG GEOMETRY
#
# This is not inferred from sparse physical events.
# It is the canonical 52-bar composition contract:
#
#   1 Frost breath       4 bars
#   2 Tremor identity    8 bars
#   3 Black wind         8 bars
#   4 Rooted storm       8 bars
#   5 Ashen gap          4 bars
#   6 Night opens        8 bars
#   7 Return as ruin     8 bars
#   8 Dissolution        4 bars
# ============================================================

CANONICAL_BARS = {
    1: 4,
    2: 8,
    3: 8,
    4: 8,
    5: 4,
    6: 8,
    7: 8,
    8: 4,
}


# Long-form arrangement.
#
# Deliberately not verse / chorus.
SEQUENCE = [
    # ACT I
    1, 2, 3, 4, 6, 7,

    # ACT II
    2, 3, 5, 6, 3, 7,

    # ACT III
    1, 2, 6, 7, 8,
]


def sha256_payload(payload: dict) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def discover_governed_plan() -> Path | None:
    candidates = [
        PHYSICAL_PLAN.parent
        / "SONORIS_GOVERNED_COMPOSITION_PLAN.json",

        ROOT
        / "media/sonoris/releases/"
        / "black_metal_where_pines_forget_v3/"
        / "SONORIS_GOVERNED_COMPOSITION_PLAN.json",

        ROOT
        / "media/sonoris/"
        / "SONORIS_GOVERNED_COMPOSITION_PLAN.json",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    matches = sorted(
        ROOT.glob(
            "**/*GOVERNED*COMPOSITION*PLAN*.json"
        )
    )

    return matches[0] if matches else None


def canonical_geometry_from_fallback():
    """
    Build the known governed 52-bar structure when the governed
    JSON is not physically present in this checkout.
    """
    sections = []

    cursor = 0

    names = {
        1: ("Frost breath", "TRANCE"),
        2: ("Tremor identity", "SPRINT"),
        3: ("Black wind", "PANIC"),
        4: ("Rooted storm", "STOMP"),
        5: ("Ashen gap", "COLLAPSE"),
        6: ("Night opens", "TRANCE"),
        7: ("Return as ruin", "HOOK"),
        8: ("Dissolution", "RELEASE"),
    }

    for index in range(1, 9):
        bars = CANONICAL_BARS[index]
        name, gesture = names[index]

        sections.append({
            "index": index,
            "section": name,
            "gesture": gesture,
            "bars": bars,
            "start_bar": cursor,
            "end_bar": cursor + bars,
        })

        cursor += bars

    assert cursor == 52

    return sections


def load_structural_sections():
    governed = discover_governed_plan()

    if governed is None:
        print(
            "GOVERNED_PLAN=NOT_FOUND "
            "(using canonical 52-bar contract)"
        )

        return (
            canonical_geometry_from_fallback(),
            None,
        )

    print(
        f"GOVERNED_PLAN={governed}"
    )

    payload = json.loads(
        governed.read_text(
            encoding="utf-8",
        )
    )

    rows = payload.get("sections")

    if not isinstance(rows, list):
        raise RuntimeError(
            "GOVERNED_PLAN_SECTIONS_MISSING"
        )

    sections = []

    cursor = 0

    for ordinal, row in enumerate(
        rows,
        start=1,
    ):
        bars = int(
            row.get(
                "bars",
                CANONICAL_BARS.get(ordinal, 0),
            )
        )

        if bars <= 0:
            raise RuntimeError(
                f"INVALID_GOVERNED_BARS: section={ordinal}"
            )

        start = int(
            row.get(
                "start_bar",
                cursor,
            )
        )

        end = int(
            row.get(
                "end_bar",
                start + bars,
            )
        )

        if end - start != bars:
            raise RuntimeError(
                "GOVERNED_SECTION_GEOMETRY_MISMATCH: "
                f"section={ordinal} "
                f"start={start} end={end} bars={bars}"
            )

        normalized = deepcopy(row)

        normalized["index"] = ordinal
        normalized["bars"] = bars
        normalized["start_bar"] = start
        normalized["end_bar"] = end

        sections.append(normalized)

        cursor = end

    if cursor != 52:
        raise RuntimeError(
            f"GOVERNED_TOTAL_BARS_REFUSE: {cursor}"
        )

    return sections, governed


def main() -> None:
    if not PHYSICAL_PLAN.is_file():
        raise FileNotFoundError(
            f"PHYSICAL_PLAN_MISSING: {PHYSICAL_PLAN}"
        )

    physical = json.loads(
        PHYSICAL_PLAN.read_text(
            encoding="utf-8",
        )
    )

    roles = physical.get("roles")

    if not isinstance(roles, dict):
        raise RuntimeError(
            "PHYSICAL_PLAN_ROLES_MISSING"
        )

    governed_sections, governed_path = (
        load_structural_sections()
    )

    by_index = {
        int(row["index"]): row
        for row in governed_sections
    }

    print()
    print("=== SOURCE SECTION MAP ===")

    for index in sorted(by_index):
        row = by_index[index]

        print(
            f"{index}:",
            row.get("section", "UNKNOWN"),
            f"gesture={row.get('gesture')}",
            f"bars={row['start_bar']}:{row['end_bar']}",
            f"length={row['bars']}",
        )

    missing = sorted(
        set(SEQUENCE) - set(by_index)
    )

    if missing:
        raise RuntimeError(
            "ARRANGEMENT_REFERENCES_MISSING_SECTIONS: "
            + repr(missing)
        )

    # ========================================================
    # Copy physical performances according to structural time.
    # ========================================================

    out_roles = {
        role: []
        for role in roles
    }

    arranged_sections = []

    destination_bar = 0

    for full_index, source_index in enumerate(
        SEQUENCE,
        start=1,
    ):
        source_section = by_index[
            source_index
        ]

        source_start = int(
            source_section["start_bar"]
        )

        source_end = int(
            source_section["end_bar"]
        )

        bars = int(
            source_section["bars"]
        )

        source_lo = (
            source_start
            * BAR_TICKS
        )

        source_hi = (
            source_end
            * BAR_TICKS
        )

        destination_lo = (
            destination_bar
            * BAR_TICKS
        )

        shift = (
            destination_lo
            - source_lo
        )

        copied_counts = {}

        for role, events in roles.items():
            count = 0

            for event in events:
                tick = int(
                    event["tick"]
                )

                if not (
                    source_lo
                    <= tick
                    < source_hi
                ):
                    continue

                row = deepcopy(event)

                row["tick"] = (
                    tick + shift
                )

                row[
                    "source_section_index"
                ] = source_index

                row[
                    "full_song_section_index"
                ] = full_index

                out_roles[role].append(
                    row
                )

                count += 1

            copied_counts[role] = count

        arranged = deepcopy(
            source_section
        )

        arranged["index"] = full_index

        arranged[
            "source_section_index"
        ] = source_index

        arranged["start_bar"] = (
            destination_bar
        )

        arranged["end_bar"] = (
            destination_bar + bars
        )

        arranged["bars"] = bars

        arranged[
            "copied_event_counts"
        ] = copied_counts

        arranged_sections.append(
            arranged
        )

        print(
            f"ARRANGE {full_index:02d}: "
            f"source={source_index} "
            f"bars={destination_bar}:"
            f"{destination_bar + bars} "
            f"events={copied_counts}"
        )

        destination_bar += bars

    # Stable event ordering.
    for role, events in out_roles.items():
        events.sort(
            key=lambda event: (
                int(event["tick"]),
                int(
                    event.get(
                        "pitch",
                        -1,
                    )
                ),
                str(
                    event.get(
                        "function",
                        "",
                    )
                ),
            )
        )

    musical_seconds = (
        destination_bar
        * 4
        * 60
        / BPM
    )

    payload = {
        "schema": (
            "dio.sonoris."
            "full_physical_performance.v1"
        ),
        "title": "Where the Pines Forget",
        "version": "FULL_V1",
        "tempo_bpm": BPM,
        "meter": "4/4",
        "bars": destination_bar,
        "ticks_per_beat": TPQ,
        "musical_seconds": musical_seconds,
        "source_physical_plan": str(
            PHYSICAL_PLAN
        ),
        "source_governed_plan": (
            str(governed_path)
            if governed_path
            else None
        ),
        "arrangement_sequence": SEQUENCE,
        "sections": arranged_sections,
        "roles": out_roles,
    }

    payload["sha256"] = (
        sha256_payload(payload)
    )

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    DEST.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=== FULL SONG PLAN ===")

    print(
        json.dumps(
            {
                "state": (
                    "FULL_SONG_PLAN_READY"
                ),
                "bars": destination_bar,
                "musical_seconds": round(
                    musical_seconds,
                    3,
                ),
                "minutes": round(
                    musical_seconds / 60,
                    3,
                ),
                "sha256": payload[
                    "sha256"
                ],
                "plan": str(DEST),
                "event_counts": {
                    role: len(events)
                    for role, events
                    in out_roles.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
