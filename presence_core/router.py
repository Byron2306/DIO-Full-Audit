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
    low=text.lower()
    extra={"homs":["lesson plan","worksheet","powerpoint","slides","lesson video","caps"],"sophia":["research review","academic review","guided learning"],"evidex":["evidence pack","donor report"],"vamp":["annual review","performance review"],"document_studio":["technical editing","document editing","formatting","translation","translate","localisation","localization"]}
    best_product: str|None=None
    best_score: tuple[int,int,int,int]=(0,0,0,-10**9)
    best_hits=0
    for route in routes:
        product=str(route.get("product"))
        terms=[str(value).strip().lower() for value in (list(route.get("keywords",[]))+extra.get(product,[])) if str(value).strip()]
        matched=[term for term in terms if term in low]
        if not matched:
            continue
        hits=len(matched)
        longest_words=max(len(term.split()) for term in matched)
        longest_chars=max(len(term) for term in matched)
        try:
            priority=int(route.get("priority",10**6))
        except (TypeError,ValueError):
            priority=10**6
        score=(hits,longest_words,longest_chars,-priority)
        if score>best_score:
            best_score=score
            best_product=product
            best_hits=hits
    if not best_product:
        return None,0.0
    specificity_bonus=max(0,best_score[1]-1)*0.03
    return best_product,min(0.55+best_hits*0.12+specificity_bonus,0.98)

def _looks_like_product_request(low: str, product: str|None) -> bool:
    if not product:
        return False
    request_terms=["i need","i want","can you make","can you create","prepare","build me","help me with","send me","make me","create me"]
    if any(x in low for x in request_terms) or low.startswith("create "):
        return True
    polite_prefixes=("please ","can you ","could you ","would you ")
    candidate=low
    for prefix in polite_prefixes:
        if candidate.startswith(prefix):
            candidate=candidate[len(prefix):].lstrip()
            break
    imperative_verbs=(
        "assess ","evaluate ","review ","analyse ","analyze ","turn ",
        "draft ","write ","convert ","summarise ","summarize ","prepare ",
    )
    return candidate.startswith(imperative_verbs)

def _route_capital_operator(low: str) -> Decision | None:
    capital_words=("capital","funding","fund","investor","investment","grant","donor","sponsor","patron","accelerator","prize","opportunity","opportunities")
    has_capital=any(x in low for x in capital_words) or "opp-" in low
    if ("missing proof" in low or ("proof" in low and "missing" in low)) and "opp-" in low:
        return Decision("capital_missing_proof",None,0.99,"deterministic","operator capital proof-gap query")
    if "opp-" in low and any(x in low for x in ("move in rank","moved in rank","rank move","rank movement","ranking change","rank change")):
        return Decision("capital_rank_move",None,0.99,"deterministic","operator capital rank-movement explanation")
    if has_capital and any(x in low for x in ("deadline","deadlines","due soon","closing soon","close soon")):
        return Decision("capital_deadlines",None,0.99,"deterministic","operator capital deadline query")
    if has_capital and "domain" in low:
        return Decision("capital_find_domain",None,0.99,"deterministic","operator Atlas-domain capital query")
    geography_terms=("south africa","africa","global","worldwide","europe","european union","united states","usa","united kingdom","uk","asia","latin america","middle east")
    if has_capital and any(term in low for term in geography_terms) and any(x in low for x in ("find","show","which","targets","opportunities")):
        return Decision("capital_find_geography",None,0.99,"deterministic","operator geography capital query")
    if low.startswith("explain_recommendation") or ("ranked" in low and any(x in low for x in ("why", "explain"))):
        return Decision("capital_explain",None,0.99,"deterministic","operator capital rank explanation")
    if any(x in low for x in ("draft an email", "draft email", "draft outreach", "write an email")) and has_capital:
        return Decision("capital_draft",None,0.99,"deterministic","operator governed capital draft")
    if any(x in low for x in ("patreon", "patronage", "patron proposition", "supporter tier")):
        return Decision("capital_patronage",None,0.99,"deterministic","operator patronage proposition query")
    if "grant" in low and any(x in low for x in ("find", "show", "which", "education", "oer", "funding")):
        return Decision("capital_grants",None,0.99,"deterministic","operator grant discovery query")
    generic_type_terms=("investor","donor","sponsor","accelerator","prize")
    if any(term in low for term in generic_type_terms) and any(x in low for x in ("find","show","which","opportunities","targets")):
        return Decision("capital_find_type",None,0.99,"deterministic","operator capital type query")
    if any(x in low for x in ("who should i approach", "who should we approach", "funding priority", "capital priority", "best funding targets", "who should i contact")):
        return Decision("capital_priority",None,0.99,"deterministic","operator capital priority query")
    return None

def route_message(text: str, role: str, routes_path: Path) -> Decision:
    low=" ".join(text.lower().split()); routes=load_routes(routes_path); product,pconf=detect_product(low,routes)
    if low in {"/help","help","commands","/commands"}:
        return Decision("help",None,0.99,"deterministic","help command")
    if role=="operator":
        capital=_route_capital_operator(low)
        if capital is not None:
            return capital
    if role=="operator" and (low in {"/start","/morning","/summary","/status","morning lilith","morning vesper","status vesper","status"} or any(x in low for x in ["what's happening","whats happening","give me the summary","system summary"])):
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
    if _looks_like_product_request(low,product):
        return Decision("intake_request",product,max(0.9,pconf),"deterministic","product request")
    if any(x in low for x in ["translate","translation","afrikaans","isizulu","xhosa","multilingual","localise","localize"]): return Decision("translation_info",product,0.93,"deterministic","translation phrase")
    if any(x in low for x in ["formatting","format this","technical format","template","page layout","powerpoint master","docx"]): return Decision("formatting_info",product,0.92,"deterministic","formatting phrase")
    if low.startswith("/start") or any(x in low for x in ["what is dio","what do you do","who are you","what can you do","hello","hi vesper","hey vesper","hi lilith","hey lilith"]): return Decision("general_info",product,0.9,"deterministic","general information")
    if product: return Decision("product_info",product,max(0.8,pconf),"deterministic","product keyword")
    proposal=classify_with_ollama(text,[str(r.get("product")) for r in routes if r.get("product")])
    if proposal and proposal.get("confidence",0)>=0.7: return Decision(str(proposal["intent"]),proposal.get("product"),float(proposal["confidence"]),"ollama_advisory","bounded classifier proposal")
    return Decision("unknown",None,0.25,"deterministic","no safe classification")
