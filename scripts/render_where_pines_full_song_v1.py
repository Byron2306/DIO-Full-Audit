from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RENDERER = (
    ROOT
    / "scripts/"
    / "render_where_pines_physical_v3.py"
)

FULL_DIR = (
    ROOT
    / "media/sonoris/releases/"
    / "black_metal_where_pines_full_v1"
)

FULL_PLAN = (
    FULL_DIR
    / "SONORIS_FULL_PHYSICAL_PERFORMANCE_PLAN.json"
)


if not RENDERER.is_file():
    raise FileNotFoundError(
        f"RENDERER_MISSING: {RENDERER}"
    )

if not FULL_PLAN.is_file():
    raise FileNotFoundError(
        f"FULL_PLAN_MISSING: {FULL_PLAN}"
    )


spec = importlib.util.spec_from_file_location(
    "sonoris_where_pines_renderer",
    RENDERER,
)

if spec is None or spec.loader is None:
    raise RuntimeError(
        "RENDERER_IMPORT_FAILED"
    )

renderer = importlib.util.module_from_spec(
    spec
)

spec.loader.exec_module(
    renderer
)

# Redirect the existing proven renderer onto the full arrangement.
renderer.OUT = FULL_DIR
renderer.PLAN = FULL_PLAN

print(f"FULL_RENDER_PLAN={FULL_PLAN}")
print(f"FULL_RENDER_OUT={FULL_DIR}")

renderer.main()
