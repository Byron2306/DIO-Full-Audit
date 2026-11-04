from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.sonoris_genre_compiler import compile_composition_request
from products.sonoris_physical_compiler import compile_physical_performance


OUT = ROOT / "media/sonoris/releases/black_metal_where_pines_forget_v3"
OUT.mkdir(parents=True, exist_ok=True)

plan = compile_composition_request({
    "genre": "black_metal",
    "title": "Where the Pines Forget",
    "mood": "icy, eerie, relentless, then dissolving",
    "tempo_bpm": 168,
    "meter": "4/4",
    "bars": 52,
    "tonal_center": "D-minor",
})

physical = compile_physical_performance(
    plan,
    seed=661028,
)

(OUT / "SONORIS_GOVERNED_COMPOSITION_PLAN.json").write_text(
    json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
)

(OUT / "SONORIS_PHYSICAL_PERFORMANCE_PLAN.json").write_text(
    json.dumps(physical, indent=2, ensure_ascii=False) + "\n"
)

print(json.dumps({
    "state": "PHYSICAL_PERFORMANCE_COMPILED",
    "output": str(OUT),
    "sha256": physical["sha256"],
    "event_counts": {
        role: len(events)
        for role, events in physical["roles"].items()
    },
}, indent=2))
