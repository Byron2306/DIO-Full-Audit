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

def route_message(text: str, role: str, routes_path: Path) -> Decision:
    low=" ".join(text.lower().split()); routes=load_routes(routes_path); product,pconf=detect_product(low,routes)
    if low in {"/help","help","commands","/commands"}:
        return Decision("help",None,0.99,"deterministic","help command")
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


def _explicit_conversation_confirmation(text: str) -> bool:
    low = " ".join(str(text or "").lower().split())
    patterns = (
        r"\byes\b.*\b(start|begin)\b",
        r"\byes\b.*\bdo that\b",
        r"\bgo ahead\b(?:.*\b(that|it)\b)?",
        r"\b(start|begin) that\b",
        r"\bplease (start|begin)\b",
    )
    return any(re.search(pattern, low) for pattern in patterns)


def decision_from_conversation_action(
    *,
    resolution,
    state,
    text: str,
    role: str,
    routes_path: Path,
) -> Decision | None:
    action = str((resolution or {}).get("action_intent") or "none")
    if action == "none":
        return None

    confidence = max(0.0, min(float((resolution or {}).get("confidence") or 0.0), 1.0))
    product_raw = (resolution or {}).get("action_product")
    product = str(product_raw).strip() if product_raw is not None else None
    if product == "":
        product = None

    if action == "begin_intake":
        if not product or not _explicit_conversation_confirmation(text):
            return None
        route_products = {
            str(row.get("product"))
            for row in load_routes(routes_path)
            if row.get("product")
        }
        if product not in route_products:
            return None
        proposal = (state or {}).get("action_proposal")
        if not isinstance(proposal, dict):
            return None
        if proposal.get("intent") != "begin_intake" or proposal.get("product") != product:
            return None
        selected = (state or {}).get("selected_product")
        if selected is not None and str(selected) != product:
            return None
        return Decision(
            "intake_request",
            product,
            confidence,
            "conversation_bridge",
            "explicit confirmation of pending conversational intake proposal",
        )

    if action == "status_lookup":
        current = route_message(text, role, routes_path)
        if current.intent != "status_request" or current.source != "deterministic":
            return None
        if product is not None and current.product not in {None, product}:
            return None
        return Decision(
            "status_request",
            product or current.product,
            confidence,
            "conversation_bridge",
            "explicit current-turn status request",
        )

    if action == "operator_summary":
        if role != "operator":
            return None
        current = route_message(text, role, routes_path)
        if current.intent != "operator_summary" or current.source != "deterministic":
            return None
        return Decision(
            "operator_summary",
            None,
            confidence,
            "conversation_bridge",
            "explicit operator summary request",
        )

    return None
