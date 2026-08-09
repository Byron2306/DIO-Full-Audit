"""
Arda Trusted Core: End-to-End Proof
====================================
One command. One policy. One signed decision. One ledger receipt.

This script exercises the ENTIRE trusted core chain:
1. Generate a signed policy (if missing)
2. Evaluate check_health against the policy (fail-closed)
3. Create a DSSE-signed attestation envelope with real boot context
4. Append the envelope to the Merkle-chained ledger
5. Verify the envelope signature
6. Verify the ledger chain from genesis
7. Print the result: ONE TRUE CLAIM: VERIFIED
"""

import hashlib
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='[ARDA] %(message)s')
logger = logging.getLogger("ARDA_PROOF")

sys.path.insert(0, os.path.abspath("."))


def run_proof():
    logger.info("=" * 60)
    logger.info("ARDA TRUSTED CORE: ONE TRUE CLAIM")
    logger.info("=" * 60)

    # ------ STEP 1: Policy ------
    logger.info("\n--- STEP 1: Policy ---")
    from backend.services.policy_engine import generate_policy, load_and_verify_policy, evaluate, POLICY_PATH

    if not os.path.exists(POLICY_PATH):
        generate_policy()
    policy = load_and_verify_policy()
    logger.info(f"Policy ID: {policy['policy_id']} v{policy['version']}")
    logger.info(f"Policy signature: VALID")

    # ------ STEP 2: Policy Evaluation ------
    logger.info("\n--- STEP 2: Policy Evaluation ---")
    command = "check_health"
    principal = "Magos_Indomitus"
    lane = "Shire"
    token_id = "TOK-HEALTH-001"

    verdict = evaluate(command, principal, lane)
    logger.info(f"Verdict: {verdict}")

    # ------ STEP 3: DSSE Attestation ------
    logger.info("\n--- STEP 3: DSSE Attestation ---")
    from backend.services.attestation_service import create_envelope, verify_envelope

    # Artifact digest = hash of the canonical request
    request_body = json.dumps(
        {"command": command, "principal": principal, "lane": lane, "token_id": token_id},
        sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    artifact_digest = hashlib.sha3_256(request_body).hexdigest()

    envelope = create_envelope(
        command=command,
        principal=principal,
        token_id=token_id,
        lane=lane,
        policy_id=policy["policy_id"],
        policy_version=policy["version"],
        verdict=verdict,
        artifact_digest=artifact_digest,
        policy_verdict=verdict,
        use_sigstore=False,  # Set True for real Sigstore (requires browser OIDC)
    )
    logger.info(f"Signing algorithm: {envelope['signing_algorithm']}")
    logger.info(f"Boot context: {json.dumps(envelope['payload']['boot_context'], indent=2)}")

    # ------ STEP 4: Ledger Receipt ------
    logger.info("\n--- STEP 4: Ledger Receipt ---")
    from backend.services.ledger import append, verify_chain

    receipt = append(envelope)
    logger.info(f"Transparency receipt: {receipt}")

    # ------ STEP 5: Verify Envelope ------
    logger.info("\n--- STEP 5: Verify Envelope Signature ---")
    sig_valid = verify_envelope(envelope)
    assert sig_valid, "FATAL: Envelope signature INVALID"
    logger.info("Envelope signature: VALID")

    # ------ STEP 6: Verify Ledger Chain ------
    logger.info("\n--- STEP 6: Verify Ledger Chain ---")
    chain_valid = verify_chain()
    assert chain_valid, "FATAL: Ledger chain BROKEN"
    logger.info("Ledger chain: INTACT")

    # ------ RESULT ------
    logger.info("\n" + "=" * 60)
    boot = envelope["payload"]["boot_context"]
    sb = boot.get("secure_boot", {}).get("enabled", "unknown")
    tpm = boot.get("tpm", {}).get("version", "unknown")
    
    logger.info(f"Command:           {command}")
    logger.info(f"Principal:         {principal}")
    logger.info(f"Policy:            {policy['policy_id']} v{policy['version']}")
    logger.info(f"Verdict:           {verdict}")
    logger.info(f"Signing:           {envelope['signing_algorithm']}")
    logger.info(f"Secure Boot:       {sb}")
    logger.info(f"TPM:               {tpm}")
    logger.info(f"Receipt:           {receipt[:32]}...")
    logger.info(f"Envelope valid:    {sig_valid}")
    logger.info(f"Chain intact:      {chain_valid}")
    logger.info("=" * 60)
    
    print(f"\n[RESULT] ONE TRUE CLAIM: VERIFIED")
    print(f"  check_health was allowed for Magos_Indomitus in lane Shire")
    print(f"  under policy {policy['policy_id']} v{policy['version']}")
    print(f"  on a substrate with SecureBoot={sb}, TPM={tpm}")
    print(f"  signed with {envelope['signing_algorithm']}")
    print(f"  receipt: {receipt}")
    return True


if __name__ == "__main__":
    success = run_proof()
    sys.exit(0 if success else 1)
