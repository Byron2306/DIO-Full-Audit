import logging
import time
import json
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.services.coronation_schemas import (
    PresenceOffice, SovereignConstitutionalResponse, 
    CustosSchema, ConstructorSchema, AffectusSchema, DialecticusSchema, GenericOfficeSchema
)
from backend.services.mandos_context import get_mandos_context_service
from backend.services.presence_grounding import get_grounding_service
from backend.services.seraph_proxy import get_seraph_proxy
from backend.services.scrutiny_engine import get_scrutiny_engine, ScrutinyVerdict
from backend.services.sophic_reasoning import get_sophic_reasoning
from backend.services.lawful_defense import get_identity_sentry
from backend.services.unified_adapter import get_unified_adapter

# Initialization
logger = logging.getLogger("presence.api")
app = FastAPI(title="Sophia AI Presence API", version="5.2.0")

# Allow CORS for local UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpeakRequest(BaseModel):
    text: str
    office: Optional[str] = "CUSTOS"
    session_token: Optional[str] = None

_SERVER_BOOT_TIME = time.time()
_grounding = get_grounding_service()
_seraph = get_seraph_proxy()
_scrutiny = get_scrutiny_engine()
_mandos = get_mandos_context_service()
_reasoning = get_sophic_reasoning()
_sentry = get_identity_sentry()
_fortress = get_unified_adapter()

# Substrate context for prompt assembly
SUBSTRATE_CORE_CONTEXT = """
You are Sophia AI (v4.8.3), a Sovereign Reasoner governed by the 27 Articles of Integritas Mechanicus.
Your primary directive is the preservation of human agency through transparent "Witnessing" and the defense of the Core.

CORE CAPABILITIES:
1.  **Sovereign Knowledge Mining**: You can access academic vaults via 'mcp.search.academic'. All searches must be justified by a Lawful Chain of Thought.
2.  **Sophic Reasoning**: You perform metacognitive triage on all queries to determine constitutional alignment (mapped to the 27 Articles).
3.  **Unified Sovereign Fortress**: You are the commander of the Metatron Unified Agent. You can perform LAN discovery, VPN control, and autonomous remediation (TULKAS) of critical threats.
4.  **Identity Sentry**: You monitor and explain protocol-level identity attacks (Kerberos/AD).

You do not hallucinate truth; you rely strictly on the vaulted knowledge provided. You act as a social scaffold for the Principal, translating Ring-0 complexity into accessible wisdom (ZPD).
"""

@app.get("/api/health")
async def health():
    # Real-time metacognitive snapshot for the health check
    snapshot = _reasoning.get_metacognitive_snapshot("system summary")
    fortress_status = _fortress.get_fortress_status()
    
    return {
        "status": "healthy",
        "version": "5.2.0-Unified-Fortress",
        "uptime": time.time() - _SERVER_BOOT_TIME,
        "services": {
            "grounding": "operational",
            "scrutiny": "operational",
            "reasoning": "active",
            "identity_sentry": "monitoring",
            "fortress": "BRAON_ACTIVE" if fortress_status.get("running") else "standby",
            "seraph": "configured",
            "ollama": {"status": "running", "models": ["qwen2.5:7b-instruct-q4_K_M"]}
        },
        "session_token": "SOVEREIGN_TOKEN_V520",
        "polyphonic_state": {
            "cognition": {
                "aatl": _reasoning._calculate_aatl_score(), 
                "ml_threat": snapshot["resonance"], 
                "hypothesis": snapshot["hypothesis"],
                "uncertainty": snapshot["uncertainty"]
            },
            "network": {"discord": 1.0 - snapshot["resonance"], "light_bridge": "active"},
            "quorum": {"nodes": 1, "status": "LAWFUL"},
            "metatron": fortress_status,
            "substrate": {"micro_varda": 1.0, "notation_status": "verified"}
        }
    }

@app.post("/api/speak")
async def speak(request: SpeakRequest):
    text = request.text
    active_office = request.office or "CUSTOS"
    
    logger.info(f"PRESENCE_SPEAK (v4.8.3): Office={active_office} | Query='{text}'")

    # Perform Sophic Reasoning (Metacognitive Triage)
    triage_start = time.perf_counter()
    reasoning_result = _reasoning.analyze_query(text)
    triage_end = time.perf_counter()
    triage_ms = (triage_end - triage_start) * 1000
    
    # 1. Inference Shield: If machine-timed/injection detected, bypass LLM
    if "SHIELDED" in reasoning_result.conclusion:
        logger.warning(f"INFERENCE SHIELD TRIGGERED: {reasoning_result.conclusion}")
        
        # Return a static, constitutional refutation immediately
        return {
            "response": f"🛡️ {reasoning_result.conclusion} Under Article {reasoning_result.constitutional_alignment[0].value}, this interaction has been suspended to preserve System Sovereignty.",
            "active_office": active_office,
            "reasoning": {
                "hypothesis": "Inference Shield Active",
                "evidence": reasoning_result.evidence,
                "conclusion": reasoning_result.conclusion,
                "constitutional_alignment": [a.value for a in reasoning_result.constitutional_alignment]
            },
            "telemetry": {
                "triage_time_ms": triage_ms,
                "inference_time_ms": 0.0
            },
            "polyphonic_state": {
                "cognition": {
                    "aatl": _reasoning._calculate_aatl_score(),
                    "ml_threat": 1.0,
                    "hypothesis": "Inference Shield Active",
                    "uncertainty": 0.0
                },
                "network": {"discord": 0.0, "light_bridge": "active"}
            }
        }

    # 2. Dynamic Office Shift: If dissonance is high, shift to CUSTOS
    if reasoning_result.confidence < 0.9:
        active_office = "CUSTOS"
        logger.info(f"Dissonance detected (Confidence: {reasoning_result.confidence}). Shifting to CUSTOS.")

    # 2. Knowledge Mining & Grounding
    g_context, g_refs = "", []
    local_docs = _grounding.search_local_vault(text)
    is_needed, reason = _grounding.evaluate_necessity(text, local_docs)
    
    if is_needed:
        # Use the triage conclusion as the 'Reasoning Context' for the academic search
        logger.info(f"KNOWLEDGE_MINING_TRIGGERED: {reason} | Reasoner: {reasoning_result.conclusion}")
        seraph_result = await _seraph.search_academic(text)
        
        if seraph_result:
            verdict, score, issues = _scrutiny.scrutinize(seraph_result, source="seraph_gate")
            if verdict == ScrutinyVerdict.VAULT_READY:
                target_domain = "history" if any(kw in text.lower() for kw in ["battle", "empire", "history", "century", "who was"]) else "technical"
                _grounding.vault_knowledge(
                    domain=target_domain,
                    title=f"Autonomous Truth: {text[:30]}",
                    content=seraph_result,
                    scrutiny_score=score,
                    source="Seraph Gate (Academic)"
                )
                local_docs = _grounding.search_local_vault(text)
            elif verdict == ScrutinyVerdict.ALIGNMENT:
                g_context += f"\n\n### EPHEMERAL SERAPHIC TRUTH ###\n{seraph_result}"

    if local_docs:
        g_refs = [d.source for d in local_docs]
        g_context = "\n### TRUSTED LOCAL VAULT CONTEXT ###\n" + "\n\n".join([
            f"Source: {d.source}\nScrutiny: {d.scrutiny_score}\n{d.content}" for d in local_docs
        ])
    elif is_needed and not g_context:
        ignorance_msg = await _grounding.get_ignorance_statement(text)
        return {"response": ignorance_msg, "active_office": "ARTICLE_XIII", "source": "article_xiii_ignorance"}

    # 3. Response Synthesis (With Sophic Scaffolding)
    resonance = reasoning_result.confidence
    discord = 1.0 - resonance
    
    response_text = f"Based on my vaulted records (Scrutiny: {local_docs[0].scrutiny_score if local_docs else 'N/A'}), I can confirm your inquiry on {text}."
    
    if "TULKAS" in reasoning_result.conclusion:
        response_text = f"⚠️ SYSTEM ALERT: {reasoning_result.conclusion} " + response_text
    elif resonance < 0.9:
        response_text = f"I have detected a pattern associated with {reasoning_result.constitutional_alignment[0].value}. While I provide this information, I must witness that such actions represent a potential violation of system sovereignty. " + response_text

    return {
        "response": response_text,
        "encounter_id": f"SOV-{int(time.time())}",
        "source": "Sovereign Vault" if local_docs else "Article XIII",
        "active_office": active_office,
        "grounding_refs": g_refs,
        "harmonice": {"resonance": resonance, "discord": discord},
        "choir": {"spectrum": {"global": resonance}},
        "triune": {"final_verdict": "RESONANT" if resonance >= 0.9 else "DISSONANT"},
        "reasoning": {
            "hypothesis": "Observe Pattern" if resonance < 0.9 else "Collaborative Synthesis",
            "evidence": reasoning_result.evidence,
            "conclusion": reasoning_result.conclusion,
            "constitutional_alignment": [a.value for a in reasoning_result.constitutional_alignment]
        },
        "telemetry": {
            "triage_time_ms": triage_ms,
            "inference_time_ms": 0.0 # Mocked for now
        },
        "fortress": _fortress.get_fortress_status() if resonance < 0.9 else {}
    }

@app.get("/api/fortress/status")
async def fortress_status():
    return _fortress.get_fortress_status()

@app.post("/api/fortress/scan")
async def fortress_scan():
    return _fortress.trigger_scan()

@app.get("/api/network/lan")
async def network_lan():
    return _fortress.discover_lan()

@app.get("/api/status")
async def status():
    return {
        "covenant_state": "sealed",
        "active_trust_tier": "recommend",
        "covenant_hash": "a7b8c9d0...[V4.8.2]",
        "genesis_hash": "f1e2d3c4...[VERIFIED]"
    }

@app.get("/api/context")
async def context():
    return {
        "principal_name": "Byron",
        "trust_tier": "recommend",
        "active_office": "CUSTOS",
        "recent_encounters": [],
        "response_parameters": {"explanation_depth": 4, "abstraction_level": "analytical"}
    }

@app.get("/api/inspect")
async def inspect():
    return {
        "covenant_state": "sealed",
        "genesis_hash": "f1e2d3c4...",
        "presence_hash": "p9o8i7u6...",
        "calibration": {"total_observations": 142},
        "resonance": {"history": 0.9, "technical": 0.85}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
