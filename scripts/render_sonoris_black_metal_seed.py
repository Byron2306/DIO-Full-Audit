from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seed",
        required=True,
        type=int,
    )

    args = parser.parse_args()

    seed_dir = (
        ROOT
        / "media/sonoris/generated/"
        / "black_metal"
        / f"seed-{args.seed}"
    )

    plan = (
        seed_dir
        / "SONORIS_PHYSICAL_PERFORMANCE_PLAN.json"
    )

    if not plan.is_file():
        raise FileNotFoundError(
            f"PHYSICAL_PLAN_MISSING: {plan}"
        )

    renderer_path = (
        ROOT
        / "scripts/"
        / "render_where_pines_physical_v3.py"
    )

    spec = importlib.util.spec_from_file_location(
        "sonoris_bm_renderer",
        renderer_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "RENDERER_IMPORT_FAILED"
        )

    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)

    renderer.OUT = seed_dir
    renderer.PLAN = plan

    print(
        f"BLACK_METAL_RENDER_SEED={args.seed}"
    )
    print(
        f"BLACK_METAL_RENDER_PLAN={plan}"
    )
    print(
        f"BLACK_METAL_RENDER_OUT={seed_dir}"
    )

    renderer.main()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
