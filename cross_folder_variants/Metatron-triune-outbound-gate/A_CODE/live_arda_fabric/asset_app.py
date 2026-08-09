import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="Arda Fabric Asset")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": os.getenv("ASSET_NAME", "asset"),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
