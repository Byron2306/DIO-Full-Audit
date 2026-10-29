from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from products.sonoris_black_metal_governed import (
    compile_black_metal_governed_plan,
)
from products.sonoris_physical_compiler import (
    compile_physical_performance,
)


ROOT = Path(
    __file__
).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seed",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--title",
    )

    parser.add_argument(
        "--bars",
        type=int,
    )

    parser.add_argument(
        "--tonal-center",
        default="D-minor",
    )

    parser.add_argument(
        "--mood",
        default=(
            "icy, sorrowful, hostile, "
            "atmospheric"
        ),
    )

    parser.add_argument(
        "--bpm",
        type=int,
        default=168,
    )

    args = parser.parse_args()

    title = (
        args.title
        or f"Black Metal Seed {args.seed}"
    )

    governed = (
        compile_black_metal_governed_plan(
            seed=args.seed,
            title=title,
            tonal_center=(
                args.tonal_center
            ),
            bars=args.bars,
            mood=args.mood,
            bpm=args.bpm,
        )
    )

    physical = (
        compile_physical_performance(
            governed,
            seed=args.seed,
        )
    )

    out = (
        ROOT
        / "media/sonoris/generated/"
        / "black_metal"
        / f"seed-{args.seed}"
    )

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    governed_path = (
        out
        / "SONORIS_GOVERNED_COMPOSITION_PLAN.json"
    )

    physical_path = (
        out
        / "SONORIS_PHYSICAL_PERFORMANCE_PLAN.json"
    )

    governed_path.write_text(
        json.dumps(
            governed,
            indent=2,
        )
        + "\n"
    )

    physical_path.write_text(
        json.dumps(
            physical,
            indent=2,
        )
        + "\n"
    )

    print(
        json.dumps(
            {
                "state": (
                    "BLACK_METAL_SEED_COMPILED"
                ),
                "seed": args.seed,
                "title": title,
                "bars": governed[
                    "bars"
                ],
                "intro": governed[
                    "black_metal_blueprint"
                ][
                    "intro"
                ],
                "ending": governed[
                    "black_metal_blueprint"
                ][
                    "ending"
                ],
                "atmosphere": governed[
                    "black_metal_blueprint"
                ][
                    "atmosphere"
                ],
                "register": governed[
                    "black_metal_blueprint"
                ][
                    "register_device"
                ],
                "governed_sha256": governed[
                    "sha256"
                ],
                "event_counts": {
                    role: len(events)
                    for role, events
                    in physical[
                        "roles"
                    ].items()
                },
                "output": str(out),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
