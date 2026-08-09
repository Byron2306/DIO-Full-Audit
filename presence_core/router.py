from __future__ import annotations
import json, re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from .llm import classify_with_ollama

@dataclass
class Decision:
    intent: str; product: str|None; confidence: float; source: str; reason: str
    def as_dict(self): return asdict(self)

def load_routes(path: Path) -> list[dict[str,Any]]:
    return json.loads(path.read_text(encoding="utf-8")).get("routes",[])

def detect_product(text: str, routes: list[dict[str,Any]]) -> tuple[str|None,float]:
    low=text.lower(); best=(None,0)
    extra={"homs":["lesson plan","worksheet","powerpoint","slides","lesson video","caps"],"sophia":["research review","academic review","guided learning"],"evidex":["evidence pack","donor report"],"vamp":["annual review","performance review"],"document_studio":["technical editing","document editing","formatting","translation","translate","localisation","localization"]}
    for route in routes:
        product=str(route.get("product")); terms=list(route.get("keywords",[]))+extra.get(product,[]); hits=sum(1 for k in terms if str(k).lower() in low)
        if hits>best[1]: best=(product,hits)
    return (best[0],min(0.55+best[1]*0.12,0.98)) if best[1] else (None,0.0)

def route_message(text: str, role: str, routes_path: Path) -> Decision:
    low=" ".join(text.lower().split()); routes=load_routes(routes_path); product,pconf=detect_product(low,routes)
    if low in {"/help","help","commands","/commands"}:
        return Decision("help",None,0.99,"deterministic","help command")
    if role=="operator" and (low in {"/start","/morning","/summary","/status","morning vesper","morning lilith","status"} or any(x in low for x in ["what's happening","whats happening","give me the summary","system summary"])):
        return Decision("operator_summary",None,0.99,"deterministic","operator summary phrase")
    if role=="operator" and (low in {"/market","/campaigns","/marketing"} or any(x in low for x in ["campaign status","market command","marketing status","campaign summary","lead engine"])):
        return Decision("campaign_summary",None,0.99,"deterministic","operator market phrase")
    if role=="operator" and (low in {"/commerce","/revenue","/payments"} or any(x in low for x in ["revenue","commerce","payment summary","paid orders","paypal"])):
        return Decision("revenue_summary",None,0.99,"deterministic","operator commerce phrase")
    if role=="operator" and (low in {"/mail","/drafts"} or any(x in low for x in ["mail status","pending mail","outbound mail","drafts waiting"])):
        return Decision("mail_summary",None,0.99,"deterministic","operator mail phrase")
    if role=="operator" and (low in {"/jobs","/work"} or any(x in low for x in ["job status","jobs summary","delivery drafts","work queue"])):
        return Decision("job_summary",None,0.99,"deterministic","operator job phrase")
    if role=="operator" and (low in {"/needs","/attention"} or any(x in low for x in ["needs me","needs you","need me","attention queue"])): return Decision("needs_you",None,0.99,"deterministic","operator attention phrase")
    if any(x in low for x in ["how much","price","pricing","cost","quote"]): return Decision("pricing_info",product,0.94,"deterministic","commercial question")
    if any(x in low for x in ["where is my","order status","payment status","job status","already paid","my order"]): return Decision("status_request",product,0.94,"deterministic","status question")
    request_terms=["i need","i want","can you make","can you create","prepare","build me","help me with","send me","make me","create me"]
    if product and (any(x in low for x in request_terms) or low.startswith("create ")):
        return Decision("intake_request",product,max(0.9,pconf),"deterministic","product request")
    if any(x in low for x in ["translate","translation","afrikaans","isizulu","xhosa","multilingual","localise","localize"]): return Decision("translation_info",product,0.93,"deterministic","translation phrase")
    if any(x in low for x in ["formatting","format this","technical format","template","page layout","powerpoint master","docx"]): return Decision("formatting_info",product,0.92,"deterministic","formatting phrase")
    if low.startswith("/start") or any(x in low for x in ["what is dio","what do you do","who are you","what can you do","hello","hi vesper","hey vesper","hi lilith","hey lilith"]): return Decision("general_info",product,0.9,"deterministic","general information")
    if product: return Decision("product_info",product,max(0.8,pconf),"deterministic","product keyword")
    proposal=classify_with_ollama(text,[str(r.get("product")) for r in routes if r.get("product")])
    if proposal and proposal.get("confidence",0)>=0.7: return Decision(str(proposal["intent"]),proposal.get("product"),float(proposal["confidence"]),"ollama_advisory","bounded classifier proposal")
    return Decision("unknown",None,0.25,"deterministic","no safe classification")
