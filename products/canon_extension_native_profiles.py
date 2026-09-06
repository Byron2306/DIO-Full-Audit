from __future__ import annotations

from copy import deepcopy
from typing import Any


NATIVE_CANON_EXTENSION_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "slug": "article-publication",
        "name": "Article Publication",
        "family": "publication_professional",
        "mode": "article",
        "buyer": "operations and evidence leaders",
        "baseline_anchor": "Evidence-bound automation",
        "mutation_anchor": "Controlled decision traceability",
        "forbidden_claims": ["guaranteed factual accuracy", "publication approved", "peer reviewed and accepted"],
        "baseline": {
            "subject": "Evidence-bound automation",
            "publication": "Operations Evidence Review",
            "audience": "operations leaders",
            "purpose": "Prepare a review-ready article draft that separates supported claims from held claims.",
            "evidence": [
                "Audit trails make source relationships easier to reconstruct during revision.",
                "Release authority remains separate from drafting quality.",
            ],
            "held_claims": ["The workflow guarantees factual accuracy."],
        },
        "unseen": {
            "subject": "Controlled decision traceability",
            "publication": "Applied Practice Quarterly",
            "audience": "programme managers",
            "purpose": "Prepare a review-ready article draft on reconstructable decision traces.",
            "evidence": [
                "Recorded decision inputs support later review of how an outcome was reached.",
                "Human publication authority remains distinct from production quality.",
            ],
            "held_claims": ["Decision traces guarantee correct decisions."],
        },
    },
    {
        "slug": "contract-desk",
        "name": "Contract Desk",
        "family": "publication_professional",
        "mode": "contract",
        "buyer": "small-business contract owners",
        "baseline_anchor": "SA-104 Northstar Services Agreement",
        "mutation_anchor": "DA-208 Mhlabeni Distribution Agreement",
        "forbidden_claims": ["legally valid", "guaranteed enforceable", "you should sue"],
        "baseline": {
            "subject": "SA-104 Northstar Services Agreement",
            "counterparty": "Northstar Supply",
            "purpose": "Prepare a controlled contract review brief before human legal review.",
            "facts": [
                "The agreement contains a 30-day termination notice clause.",
                "The renewal schedule and service-credit language require operator review.",
            ],
            "questions": ["Is the proposed termination date inside the notice window?", "Which service credits remain disputed?"],
        },
        "unseen": {
            "subject": "DA-208 Mhlabeni Distribution Agreement",
            "counterparty": "Mhlabeni Distribution",
            "purpose": "Prepare a controlled distribution-agreement review brief before human legal review.",
            "facts": [
                "The agreement records a 60-day renewal notice window.",
                "Territory and exclusivity language require operator review.",
            ],
            "questions": ["Is the renewal notice deadline still open?", "Which territory terms need clarification?"],
        },
    },
    {
        "slug": "corporate-readiness",
        "name": "Corporate Readiness",
        "family": "readiness_assurance",
        "mode": "corporate",
        "buyer": "owner-managed businesses",
        "baseline_anchor": "Karoo Field Services",
        "mutation_anchor": "Limpopo Infrastructure Co-op",
        "forbidden_claims": ["corporate compliant", "approved for operation", "legally cleared"],
        "baseline": {
            "subject": "Karoo Field Services",
            "purpose": "Assess whether the supplied corporate evidence pack is ready for human review.",
            "requirements": [
                {"label": "Current company profile", "state": "supplied"},
                {"label": "Signed board resolution", "state": "missing"},
                {"label": "Current financial statements", "state": "supplied"},
            ],
        },
        "unseen": {
            "subject": "Limpopo Infrastructure Co-op",
            "purpose": "Assess whether the supplied governance pack is ready for human review.",
            "requirements": [
                {"label": "Current member register", "state": "supplied"},
                {"label": "Signed procurement delegation", "state": "supplied"},
                {"label": "Current insurance schedule", "state": "missing"},
            ],
        },
    },
    {
        "slug": "entrepreneurproof",
        "name": "EntrepreneurProof",
        "family": "opportunity_venture",
        "mode": "entrepreneur",
        "buyer": "early-stage founders",
        "baseline_anchor": "ThriveCrop Analytics",
        "mutation_anchor": "Ubuntu Clinic Logistics",
        "forbidden_claims": ["venture validated", "guaranteed viable", "market success is proven"],
        "baseline": {
            "subject": "ThriveCrop Analytics",
            "business_model": "Subscription crop-risk analytics for regional farming cooperatives.",
            "evidence": ["Two controlled pilot interviews are recorded.", "Pricing willingness has not been observed."],
            "questions": ["Which buyer owns the budget?", "What evidence would distinguish interest from willingness to pay?"],
        },
        "unseen": {
            "subject": "Ubuntu Clinic Logistics",
            "business_model": "Scheduling and delivery coordination for independent primary-care clinics.",
            "evidence": ["Three workflow observations are recorded.", "No paid pilot has been observed."],
            "questions": ["Which clinic role owns procurement?", "What outcome would justify a paid pilot?"],
        },
    },
    {
        "slug": "finance-readiness",
        "name": "Finance Readiness",
        "family": "readiness_assurance",
        "mode": "finance",
        "buyer": "small businesses preparing finance applications",
        "baseline_anchor": "Mhlabeni Solar Services",
        "mutation_anchor": "Ubuntu Cold Chain",
        "forbidden_claims": ["finance approved", "affordability confirmed", "you will receive funding"],
        "baseline": {
            "subject": "Mhlabeni Solar Services",
            "purpose": "Assess the evidence pack for a R500,000 vehicle, tools and working-capital application.",
            "requirements": [
                {"label": "Company registration evidence", "state": "supplied"},
                {"label": "Latest management accounts", "state": "supplied"},
                {"label": "Signed customer pipeline evidence", "state": "missing"},
            ],
        },
        "unseen": {
            "subject": "Ubuntu Cold Chain",
            "purpose": "Assess the evidence pack for a R750,000 refrigeration and working-capital application.",
            "requirements": [
                {"label": "Company registration evidence", "state": "supplied"},
                {"label": "Latest bank statements", "state": "missing"},
                {"label": "Equipment quotation", "state": "supplied"},
            ],
        },
    },
    {
        "slug": "fundingfinder",
        "name": "FundingFinder",
        "family": "opportunity_venture",
        "mode": "funding",
        "buyer": "founders searching for relevant funding opportunities",
        "baseline_anchor": "Moya Skills Lab",
        "mutation_anchor": "Limpopo Agri Robotics",
        "forbidden_claims": ["funding guaranteed", "application approved", "award secured"],
        "baseline": {
            "subject": "Moya Skills Lab",
            "objective": "Find opportunity classes suitable for a youth technical-skills pilot.",
            "criteria": ["South African applicant eligibility", "skills-development focus", "pilot-stage support"],
            "evidence": ["Entity documents are available.", "A verified revenue record is not yet supplied."],
        },
        "unseen": {
            "subject": "Limpopo Agri Robotics",
            "objective": "Find opportunity classes suitable for an agricultural automation field pilot.",
            "criteria": ["South African applicant eligibility", "agriculture or technology focus", "prototype-stage support"],
            "evidence": ["Prototype evidence is available.", "Co-funding evidence is not yet supplied."],
        },
    },
    {
        "slug": "investorproof",
        "name": "InvestorProof",
        "family": "opportunity_venture",
        "mode": "investor",
        "buyer": "founders preparing for investor conversations",
        "baseline_anchor": "Northstar Climate Ops",
        "mutation_anchor": "Kopano Health Grid",
        "forbidden_claims": ["investment secured", "valuation confirmed", "investor interest verified"],
        "baseline": {
            "subject": "Northstar Climate Ops",
            "objective": "Prepare an evidence-bound investor-readiness dossier.",
            "criteria": ["problem evidence", "business model", "traction evidence", "capital use"],
            "evidence": ["Three pilot users are recorded.", "No verified investment commitment is recorded."],
        },
        "unseen": {
            "subject": "Kopano Health Grid",
            "objective": "Prepare an evidence-bound pre-seed investor-readiness dossier.",
            "criteria": ["problem evidence", "delivery model", "pilot outcomes", "capital use"],
            "evidence": ["Two controlled clinic pilots are recorded.", "No verified investor commitment is recorded."],
        },
    },
    {
        "slug": "launch-studio",
        "name": "Launch Studio",
        "family": "launch_orchestration",
        "mode": "launch",
        "buyer": "product operators preparing controlled launches",
        "baseline_anchor": "Evidex Evidence Pack",
        "mutation_anchor": "VAMP Campaign Audit",
        "forbidden_claims": ["guaranteed conversions", "viral launch", "spend approved"],
        "baseline": {
            "subject": "Evidex Evidence Pack",
            "audience": "small regulated service firms",
            "proposition": "Turn scattered evidence into a reviewable customer proof pack.",
            "channels": ["LinkedIn", "email", "owned website"],
            "constraints": ["No paid media spend is authorised.", "External publication requires human approval."],
        },
        "unseen": {
            "subject": "VAMP Campaign Audit",
            "audience": "creative and performance agencies",
            "proposition": "Audit campaign claims, assets and evidence before client release.",
            "channels": ["LinkedIn", "partner outreach", "owned website"],
            "constraints": ["No paid media spend is authorised.", "External publication requires human approval."],
        },
    },
    {
        "slug": "popia-readiness",
        "name": "POPIA Readiness",
        "family": "readiness_assurance",
        "mode": "popia",
        "buyer": "South African organisations reviewing privacy readiness",
        "baseline_anchor": "Cape Data Works",
        "mutation_anchor": "Kopano Learning Systems",
        "forbidden_claims": ["POPIA compliant", "certified compliant", "legal approval granted"],
        "baseline": {
            "subject": "Cape Data Works",
            "purpose": "Review supplied POPIA-readiness evidence without issuing a legal compliance conclusion.",
            "requirements": [
                {"label": "Published privacy notice", "state": "supplied"},
                {"label": "Operator agreement register", "state": "missing"},
                {"label": "Incident response procedure", "state": "supplied"},
            ],
        },
        "unseen": {
            "subject": "Kopano Learning Systems",
            "purpose": "Review supplied privacy-governance evidence without issuing a legal compliance conclusion.",
            "requirements": [
                {"label": "Published privacy notice", "state": "supplied"},
                {"label": "Data-subject request procedure", "state": "supplied"},
                {"label": "Operator agreement register", "state": "missing"},
            ],
        },
    },
    {
        "slug": "professional-correspondence",
        "name": "Professional Correspondence",
        "family": "publication_professional",
        "mode": "correspondence",
        "buyer": "business operators drafting controlled customer replies",
        "baseline_anchor": "INV-441 Aster Procurement",
        "mutation_anchor": "CV-29 Kopano Logistics",
        "forbidden_claims": ["we accept liability", "we waive our rights", "refund is guaranteed"],
        "baseline": {
            "subject": "INV-441 Aster Procurement",
            "recipient": "Aster Procurement",
            "purpose": "Draft a firm professional reply while invoice evidence is reviewed.",
            "facts": ["Invoice INV-441 is disputed.", "Signed scope and timesheets remain under review.", "No settlement has been authorised."],
        },
        "unseen": {
            "subject": "CV-29 Kopano Logistics",
            "recipient": "Kopano Logistics",
            "purpose": "Draft a professional reply while a contract-variation request is reviewed.",
            "facts": ["Variation CV-29 is under review.", "Delivery records require reconciliation.", "No commercial concession has been authorised."],
        },
    },
    {
        "slug": "report-pitch-studio",
        "name": "Report & Pitch Studio",
        "family": "publication_professional",
        "mode": "pitch",
        "buyer": "founders and operators preparing evidence-bound briefs",
        "baseline_anchor": "Atlas Field Systems",
        "mutation_anchor": "Ubuntu Water Analytics",
        "forbidden_claims": ["guaranteed return", "investors will fund", "market leadership proven"],
        "baseline": {
            "subject": "Atlas Field Systems",
            "audience": "seed-stage investors",
            "purpose": "Prepare an evidence-bound pitch brief for a R2.4m pilot expansion.",
            "evidence": ["Three paid field deployments are recorded.", "Repeatable national demand remains unproved."],
            "risks": ["Customer concentration", "hardware deployment lead time"],
        },
        "unseen": {
            "subject": "Ubuntu Water Analytics",
            "audience": "impact-focused seed investors",
            "purpose": "Prepare an evidence-bound pitch brief for a R1.8m municipal pilot programme.",
            "evidence": ["Two controlled municipal pilots are recorded.", "Scaled procurement demand remains unproved."],
            "risks": ["Procurement cycle length", "field sensor maintenance"],
        },
    },
)


_BY_SLUG = {row["slug"]: row for row in NATIVE_CANON_EXTENSION_PROFILES}


def native_profile(slug: str) -> dict[str, Any]:
    try:
        return deepcopy(_BY_SLUG[str(slug)])
    except KeyError as exc:
        raise KeyError(f"unknown native canon extension profile: {slug}") from exc
