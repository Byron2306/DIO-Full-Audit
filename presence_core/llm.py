from __future__ import annotations
import json, os
from typing import Any
import httpx

INTENTS=["general_info","product_info","pricing_info","intake_request","status_request","translation_info","formatting_info","unknown"]

def classify_with_ollama(text: str, products: list[str]) -> dict[str,Any]|None:
    url=os.getenv("OLLAMA_URL"); model=os.getenv("OLLAMA_MODEL")
    if not url or not model: return None
    prompt=f"Classify this customer message. Return JSON only with intent, product, confidence. Allowed intents: {INTENTS}. Allowed products: {products} or null. Message: {text[:2500]}"
    payload={"model":model,"messages":[{"role":"system","content":"You are a bounded intent classifier. You do not execute tools, make commitments, quote prices, or alter state."},{"role":"user","content":prompt}],"format":"json","stream":False,"think":False,"options":{"temperature":0}}
    try:
        r=httpx.post(url.rstrip("/")+"/api/chat",json=payload,timeout=float(os.getenv("OLLAMA_TIMEOUT","15"))); r.raise_for_status(); obj=r.json(); content=((obj.get("message") or {}).get("content") or "{}"); parsed=json.loads(content)
        if parsed.get("intent") not in INTENTS: return None
        if parsed.get("product") not in products: parsed["product"]=None
        parsed["confidence"]=max(0.0,min(float(parsed.get("confidence",0)),1.0)); return parsed
    except Exception: return None

def draft_with_ollama(decision: dict[str,Any], facts: str, fallback: str) -> str:
    if os.getenv("DIO_PRESENCE_LLM_DRAFTS","0") not in {"1","true","yes"}: return fallback
    url=os.getenv("OLLAMA_URL"); model=os.getenv("OLLAMA_MODEL")
    if not url or not model: return fallback
    system="You are Lilith, DIO's public professional concierge. Warm, concise, lightly witty, never sexual. Preserve the supplied facts exactly. Never invent pricing, payment state, delivery state, authority, legal claims, or capabilities. Never imply an action occurred unless the facts explicitly say it occurred."
    user=f"Decision: {json.dumps(decision)}\nAuthoritative facts: {facts}\nFallback wording: {fallback}\nRewrite as one concise customer-facing reply."
    try:
        r=httpx.post(url.rstrip("/")+"/api/chat",json={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"stream":False,"think":False,"options":{"temperature":0.25}},timeout=float(os.getenv("OLLAMA_TIMEOUT","15"))); r.raise_for_status(); text=((r.json().get("message") or {}).get("content") or "").strip(); return text[:4000] or fallback
    except Exception: return fallback
