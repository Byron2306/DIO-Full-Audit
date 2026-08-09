import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

ACCOUNTABILITY_LEDGER = "/home/byron/Integritas-Mechanicus-clean/Integritas-Mechanicus/evidence/accountability_ledger.jsonl"

class AccountabilityLedger:
    """Permanent record of Constitutional Fractures and Sovereign Accountability."""
    
    @staticmethod
    def log_fracture(encounter_id: str, principal: str, reason: str, intent_hash: str, context: Optional[Dict[str, Any]] = None):
        """Append a fracture event to the ledger."""
        os.makedirs(os.path.dirname(ACCOUNTABILITY_LEDGER), exist_ok=True)
        
        entry = {
            "encounter_id": encounter_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "principal": principal,
            "reason": reason,
            "intent_hash": intent_hash,
            "context": context or {},
            "status": "LOGGED_IN_COVENANT"
        }
        
        with open(ACCOUNTABILITY_LEDGER, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
    @staticmethod
    def hash_intent(text: str) -> str:
        """Create a cryptographic hash of the user's intent for accountability."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
