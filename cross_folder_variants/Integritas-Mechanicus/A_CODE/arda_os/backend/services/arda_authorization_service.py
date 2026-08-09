"""Minimal ARDA authorization surface; verification roots remain external."""
from __future__ import annotations

import os
import re
import base64, json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from backend.services.guardian_operation_authority import authorize_guardian_operation


class CrystalAuthorization(BaseModel):
    crystal_id: str
    action: str
    evidence_digest: str
    attestation_evidence_digest: str
    capability_lease_id: str
    workload_digest: str
    policy_generation: str


app = FastAPI(title="ARDA Crystal Authorization")


@app.post("/authorize/crystal")
def authorize_crystal(req: CrystalAuthorization) -> Dict[str, Any]:
    mode = os.environ.get("ARDA_CRYSTAL_AUTHORIZATION_MODE", "deny").strip().lower()
    digests = (req.evidence_digest, req.attestation_evidence_digest, req.workload_digest)
    bound = len(set(digests)) == 1 and all(re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in digests)
    allowed = mode == "allow-listed" and bound and bool(req.capability_lease_id and req.policy_generation)
    result = {
        "allowed": allowed,
        "authority": "arda",
        "reason": "bound evidence accepted" if allowed else "attestation/capability policy denied",
        "evidence_bound": bound,
    }
    key_path = os.environ.get("ARDA_CRYSTAL_DECISION_PRIVATE_KEY", "")
    if not allowed or not key_path or not Path(key_path).is_file():
        result["allowed"] = False
        return result
    result.update({"policy_generation": req.policy_generation, "nonce": req.capability_lease_id, "verification_material": {"key_id": "arda-crystal"}})
    unsigned = {"authority": "arda", "allowed": True, "request_digest": req.evidence_digest, "policy_generation": req.policy_generation, "nonce": req.capability_lease_id, "key_id": "arda-crystal"}
    result["request_digest"] = req.evidence_digest
    result["signature"] = base64.b64encode(serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None).sign(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode())).decode()
    return result


@app.post("/authorize/socket-guardian")
def authorize_socket_guardian(
    req: Dict[str, Any], authorization: str = Header(default="")
) -> Dict[str, Any]:
    """Issue only exact, signed, short-lived Guardian operation authority."""

    try:
        return authorize_guardian_operation(req, authorization)
    except (KeyError, TypeError, ValueError, RuntimeError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
