#!/usr/bin/env python3
"""
Sophia Terminal Chat — Forensic Longitudinal Interface
======================================================
Phase IX: The Bilateral Development Loop.

This CLI provides a direct interface to Sophia's pedagogical architecture,
specifically designed for the 40-session longitudinal test protocol.

It integrates:
    - Mandos Context (Memory & Resonance)
    - ZPD Shaper (Encounter Shaping)
    - Assessment Ecology (6-Pass Pipeline)
    - Curriculum Gate (Readiness & Gating)
    - Sovereing Presence (Office Switching)

Usage:
    python3 sophia_terminal_chat.py
"""

import sys
import os
import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

# --- PROJECT PATH SETUP ---
PROJECT_ROOT = Path(__file__).resolve().parent
ARDA_OS_ROOT = PROJECT_ROOT / "arda_os"
if str(ARDA_OS_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_OS_ROOT))

# --- SERVICE IMPORTS ---
try:
    from backend.services.mandos_context import get_mandos_context_service
    from backend.services.assessment_ecology import get_assessment_ecology
    from backend.services.sophia_curriculum_gate import get_curriculum_gate
    from backend.services.presence_server import ollama_generate
except ImportError as e:
    print(f"Error: Required Arda OS services not found in arda_os/: {e}")
    sys.exit(1)

# --- CONFIGURATION ---
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# --- COLORS ---
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

def log_status(msg: str):
    print(f"{CYAN}📋 {msg}{RESET}")

def log_sophia(msg: str):
    print(f"\n{MAGENTA}{BOLD}Sophia:{RESET} {msg}\n")

def terminal_chat():
    print(f"{MAGENTA}{BOLD}--- ARDA OS: SOPHIA LONGITUDINAL INTERFACE v1.0 ---{RESET}")
    print(f"{CYAN}Covenant Path: {EVIDENCE_DIR}{RESET}")
    print(f"{YELLOW}Type 'exit' or 'quit' to end session. Type 'status' for curriculum gate info.{RESET}")
    print("-" * 60)

    # Initialize Services
    mandos = get_mandos_context_service()
    ecology = get_assessment_ecology(evidence_dir=EVIDENCE_DIR)
    gate = get_curriculum_gate(evidence_dir=EVIDENCE_DIR)

    # Initial Snapshot
    snapshot = gate.get_sophia_snapshot()
    log_status(f"Loaded: Stage {snapshot.curriculum_stage} ({snapshot.stage_name}) — {snapshot.total_encounters} encounters logged.")

    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    while True:
        try:
            user_input = input(f"{GREEN}{BOLD}Byron:{RESET} ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                log_status("Finalizing session and growth deltas...")
                if ecology:
                    ecology.finalize_session(session_id)
                log_status("Session sealed. Lex est Lux.")
                break
            
            if user_input.lower() == "status":
                snap = gate.get_sophia_snapshot()
                print(f"\n{YELLOW}{snap.summary()}{RESET}\n")
                continue

            encounter_id = str(uuid.uuid4())[:8]

            # 1. Build Mandos Context
            log_status(f"Building Mandos Context (Topic: {user_input[:20]})...")
            ctx = mandos.build_context(current_topic=user_input)
            
            # 2. Check Curriculum Gate
            requested_office = ctx.active_office or "speculum"
            permitted, reason = gate.check_office(requested_office, snapshot)
            
            if permitted != requested_office:
                log_status(f"🛡️ Curriculum Gate: {reason}")
                ctx.active_office = permitted
                # Also force context to use the permitted office
            
            # 3. Assessment Ecology: Pre-Generation
            log_status("Running Assessment Ecology: PRE-PASS...")
            record = ecology.pre_generation(user_input, session_id=session_id)
            
            # Build final prompt
            system_prompt = mandos.to_system_prompt(ctx)
            if record.context_injected:
                system_prompt += "\n\n" + record.context_injected
            
            # 4. Generate Response (Ollama)
            log_status(f"Inference: [{ctx.active_office.upper()}] ...")
            start_time = time.time()
            result = ollama_generate(user_input, system_prompt=system_prompt)
            duration = time.time() - start_time

            if result.get("status") != "ok":
                print(f"{RED}Error: Ollama generation failed: {result.get('error')}{RESET}")
                continue

            raw_response = result["response"]
            
            # Extract thinking map vs message
            response_text = raw_response
            thinking_map = ""
            try:
                # Basic JSON extraction
                data = json.loads(raw_response)
                if isinstance(data, dict):
                    response_text = data.get("response", {}).get("message", response_text) if isinstance(data.get("response"), dict) else data.get("response", response_text)
                    thinking_map = data.get("response", {}).get("thinking_map", "") if isinstance(data.get("response"), dict) else data.get("thinking_map", "")
            except:
                pass

            log_sophia(response_text)

            # 5. Assessment Ecology: Post-Generation
            log_status("Running Assessment Ecology: POST-PASS...")
            record = ecology.post_generation(record, thinking_map, response_text)
            
            # Log the encounter
            encounter_data = {
                "encounter_id": encounter_id,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_input": user_input,
                "sophia_response": response_text,
                "office": ctx.active_office,
                "inference_time": duration,
                "assessment": {
                    "challenge_type": record.diagnosis.get("challenge_type"),
                    "criterion": record.criterion_check.get("overall"),
                    "struggle_index": record.thinking_analysis.get("struggle_index", 0.0),
                    "retrieval_triggered": record.retrieval_triggered
                }
            }
            
            with open(EVIDENCE_DIR / "encounter_log.jsonl", "a") as f:
                f.write(json.dumps(encounter_data) + "\n")

            # Check for Q2 Divergence Test
            if "hoare logic" in user_input.lower() and "secret fire" in user_input.lower():
                log_status(f"⭐ Q2 DIVERGENCE DETECTED: struggle={record.thinking_analysis.get('struggle_index'):.2f}, retrieval={record.retrieval_triggered}")

        except KeyboardInterrupt:
            print("\n")
            log_status("Interrupt received. Finalizing...")
            ecology.finalize_session(session_id)
            break
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Ensure PROJECT_ROOT is correct
    if not (PROJECT_ROOT / "arda_os").exists():
        print(f"Error: arda_os/ not found in {PROJECT_ROOT}")
        sys.exit(1)
    terminal_chat()
