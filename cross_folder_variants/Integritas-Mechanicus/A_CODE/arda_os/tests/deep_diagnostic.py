import json
import hashlib
import os
from datetime import datetime, timezone

# [PHASE VII] DEEP FORENSIC SIGNATURE DIAGNOSTIC
# Compares the serialization in AttestationService vs Audit Proof

def diagnostic():
    from backend.services.attestation_service import get_attestation_service
    from backend.services.quantum_security import quantum_security
    
    service = get_attestation_service()
    
    # 1. Create a fresh attestation
    statement_pre = {
        "type": "https://arda.os/attestation/v1",
        "subject": "DIAGNOSTIC_SUBJECT",
        "claim": "https://arda.os/claims/diagnostic",
        "evidence": {"test": 123},
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "issuer": "ARDA-ROOT-PQC-V1"
    }
    
    # Simulate the create_attestation logic
    serialized_signer = json.dumps(statement_pre, sort_keys=True, separators=(",", ":"))
    
    # 2. Sign it
    attestation = service.create_attestation(statement_pre["claim"], statement_pre["subject"], statement_pre["evidence"])
    # Note: create_attestation generates its own 'issued_at'
    
    # Extract what was actually signed
    statement_signed = attestation["statement"]
    serialized_internal = json.dumps(statement_signed, sort_keys=True, separators=(",", ":"))
    
    # 3. Simulate Audit Proof logic
    serialized_audit = json.dumps(statement_signed, sort_keys=True, separators=(",", ":"))
    
    print(f"INTERNAL SERIALIZED: {serialized_internal}")
    print(f"AUDIT SERIALIZED:    {serialized_audit}")
    print(f"MATCH: {serialized_internal == serialized_audit}")
    
    # 4. Verify
    root_key = quantum_security.get_key("arda_root_manifest")
    valid = quantum_security.dilithium_verify(root_key.public_key, serialized_audit.encode(), attestation["signature"])
    print(f"VERIFIED: {valid}")

if __name__ == "__main__":
    diagnostic()
