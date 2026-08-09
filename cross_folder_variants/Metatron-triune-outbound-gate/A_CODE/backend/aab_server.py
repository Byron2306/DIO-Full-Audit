import sys
from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from .routers.deception import router as deception_router
from .routers.sim_aatr import router as sim_aatr_router


app = FastAPI(title="Seraph AAB Target")
app.include_router(deception_router)
app.include_router(sim_aatr_router)


class AblationSyncPayload(BaseModel):
    env: Dict[str, str]


@app.post("/_aab/control/ablation")
def sync_aab_ablation(payload: AblationSyncPayload) -> Dict[str, object]:
    """Test-only hook for networked AAB runs.

    The live runner starts this small uvicorn target once, then changes ablation
    modes between engagements.  Because uvicorn is a child process, parent
    os.environ mutations do not automatically reach the server.  This endpoint
    explicitly syncs the selected control flags and refreshes the deception
    engine's config object so networked ablation evidence reflects the intended
    stack state.
    """
    import os
    from . import deception_engine as package_deception_module
    import deception_engine as top_level_deception_module

    for key, value in payload.env.items():
        os.environ[str(key)] = str(value)
    for deception_module in (package_deception_module, top_level_deception_module):
        deception_module.config = deception_module.DeceptionConfig()
        deception_module.deception_engine.config = deception_module.config
    cfg = top_level_deception_module.deception_engine.config
    return {
        "ok": True,
        "applied": sorted(payload.env.keys()),
        "deception": {
            "mystique_enabled": cfg.mystique_enabled,
            "correlation_enabled": cfg.correlation_enabled,
            "friction_enabled": cfg.friction_enabled,
            "trap_sink_enabled": cfg.trap_sink_enabled,
            "disinformation_enabled": cfg.disinformation_enabled,
            "disinformation_min_score": cfg.disinformation_min_score,
            "logic_budget_controller_enabled": cfg.logic_budget_controller_enabled,
        },
    }
