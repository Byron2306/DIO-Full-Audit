from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


# Explicit product overlays are commercial copy inputs, not generated maturity claims.
# Tuple: decision maker, buyer job, primary deliverable, product-specific acceptance check.
PRODUCT_OFFER_OVERLAYS: dict[str, tuple[str, str, str, str]] = {
    "Accessible Publish": ("Publication owners", "publish material people can use with assistive technology", "accessible publication pack", "accessibility checks and reading order are recorded"),
    "Agent Authority": ("AI governance owners", "define what each agent may do and who can approve it", "agent authority register", "every action class has a typed authority rule"),
    "AI IncidentRoom": ("AI incident leads", "reconstruct an AI incident without losing evidence or accountability", "AI incident evidence room", "events, actors, evidence, and decisions are time-linked"),
    "Article Publication": ("Authors and editors", "turn an approved article into a controlled publication", "article publication bundle", "the published structure matches the approved manuscript"),
    "Article Publication Studio": ("Editorial teams", "prepare a complete article package for channel review", "article studio package", "copy, visuals, metadata, and channel files reconcile"),
    "AssuranceRoom": ("Assurance leaders", "assemble controls and evidence for governed review", "assurance evidence room", "each control links to current evidence and an owner"),
    "AuditProof": ("Audit teams", "show which controls are supported and where gaps remain", "audit proof pack", "control evidence is traceable and gaps are explicit"),
    "Campaign Lab": ("Campaign owners", "translate an approved offer into coherent campaign materials", "campaign concept pack", "audience, message, evidence, and approvals align"),
    "CertificationProof": ("Certification owners", "prepare requirement evidence before a certification review", "certification readiness pack", "every requirement has evidence, a gap, or a named action"),
    "ChangeProof": ("Change managers", "prove what changed, why, and under whose authority", "change proof record", "before-and-after state and approvals are linked"),
    "Contract Desk": ("Contract owners", "review contract clauses and decisions in one controlled workspace", "contract review desk pack", "clauses, issues, owners, and decisions reconcile"),
    "ContractProof": ("Contract assurance teams", "demonstrate obligations and supporting evidence clause by clause", "contract obligation proof pack", "each material clause has an evidence or escalation state"),
    "ControlDrift": ("Control owners", "detect when operating controls diverge from their approved state", "control drift report", "changes are compared to a dated control baseline"),
    "Corporate Readiness": ("Corporate operations leaders", "prepare institutional evidence for a defined readiness decision", "corporate readiness dossier", "every readiness requirement has an owner and status"),
    "CPDProof": ("Professionals and CPD reviewers", "organise continuing-development records for credible review", "CPD evidence portfolio", "activities, dates, outcomes, and evidence reconcile"),
    "CriticalAI Assurance": ("Critical-system assurance leads", "evaluate an AI system against safety and authority obligations", "critical AI assurance dossier", "hazards, controls, evidence, and residual gaps are linked"),
    "CyberAssurance": ("Cyber risk owners", "turn cyber controls and evidence into a reviewable assurance position", "cyber assurance pack", "control coverage and evidence freshness are explicit"),
    "DiligenceRoom": ("Transaction and diligence leads", "organise diligence material for a bounded decision", "diligence evidence room", "documents, questions, findings, and access history reconcile"),
    "DIO AI Assurance": ("AI assurance leaders", "assess an AI system across governance, risk, and evidence", "AI assurance report", "claims are tied to controls, tests, and stated limitations"),
    "DIO RegOps": ("Regulatory operations teams", "translate obligations into owned, evidenced operating work", "regulatory operations register", "each obligation has applicability, owner, action, and evidence state"),
    "Document Studio Edit": ("Document owners", "improve clarity and consistency without changing approved meaning", "controlled edited document", "edits preserve source meaning and tracked decisions"),
    "Document Studio Localize": ("Localization owners", "adapt approved content for a named language and audience", "localized document bundle", "language approval and layout expansion checks are recorded"),
    "Document Studio Publish": ("Publication teams", "turn approved content into exact requested formats", "multi-format publication bundle", "semantic content is complete across every requested format"),
    "DonorProof": ("Programme and donor-reporting leads", "substantiate donor-facing claims with source evidence", "donor evidence pack", "each reported claim has a source binding and review state"),
    "DORA Vendor Assurance": ("ICT risk and procurement leads", "assess regulated vendor evidence against DORA obligations", "DORA vendor assurance pack", "vendor evidence maps to applicable DORA requirements"),
    "DossierOps": ("Dossier owners", "assemble a controlled dossier from distributed source material", "indexed dossier bundle", "every dossier item has provenance, version, and inclusion status"),
    "EntrepreneurProof": ("Founders and venture reviewers", "test venture claims against available operating evidence", "venture claim evidence pack", "claims are separated into proven, declared, and missing evidence"),
    "Evidex EvidenceOps": ("Evidence and reporting teams", "convert scattered records into a defensible evidence package", "source-bound evidence pack", "claims, sources, gaps, and review states reconcile"),
    "Finance Readiness": ("Finance leaders", "identify what is ready and missing for a finance decision", "finance readiness assessment", "requirements, supplied records, and unresolved gaps are explicit"),
    "Finance Readiness Studio": ("Finance teams and advisors", "prepare a customer-ready finance package from approved records", "finance readiness presentation pack", "figures, narratives, and source records reconcile"),
    "FundingFinder": ("Funding leads", "screen funding opportunities against real eligibility and timing", "funding opportunity shortlist", "eligibility, evidence grade, deadline, and fit are recorded"),
    "GrantProof": ("Grant managers", "show that grant obligations and reported performance are supported", "grant compliance proof pack", "requirements, claims, and evidence bind at item level"),
    "HOMS Accreditation": ("Accreditation teams", "prepare programme evidence against accreditation requirements", "accreditation evidence matrix", "each criterion has evidence, ownership, and gap status"),
    "HOMS Assess": ("Educators and assessment teams", "evaluate learner work consistently while preserving educator judgement", "assessment support pack", "rubric use, evidence, and human decisions are visible"),
    "HOMS Curriculum": ("Curriculum leaders", "map curriculum intent into teachable, reviewable units", "curriculum alignment pack", "outcomes, content, activities, and assessment links reconcile"),
    "HOMS Exam": ("Exam setters and moderators", "prepare a balanced assessment package from approved scope", "exam construction pack", "coverage, marks, cognitive demand, and memorandum align"),
    "HOMS Learning Studio": ("Learning designers", "produce coherent learning assets for a defined topic and audience", "learning topic bundle", "objectives, explanations, activities, and checks align"),
    "HOMS Moderate": ("Assessment moderators", "review assessment consistency across a defined batch", "moderation findings pack", "sampling, rubric application, exceptions, and decisions are recorded"),
    "ImpactProof": ("Impact and evaluation leads", "substantiate outcome claims with traceable evidence", "impact evidence pack", "outcome claims distinguish contribution, evidence, and uncertainty"),
    "IncidentProof": ("Incident and assurance leads", "reconstruct an incident and preserve accountable decisions", "incident proof pack", "timeline, evidence, actors, and decisions reconcile"),
    "InvestorProof": ("Founders and investment teams", "prepare investor claims for evidence-based scrutiny", "investor readiness evidence pack", "traction, market, finance, and risk claims show evidence state"),
    "Launch Studio": ("Launch owners", "coordinate an approved offer across launch channels", "launch orchestration pack", "channel assets, owners, dates, approvals, and spend gates align"),
    "Market Radar": ("Commercial decision-makers", "monitor a defined market segment using graded evidence", "market signal brief", "signals identify source, freshness, confidence, and implication"),
    "ModelProof": ("Model risk owners", "document model purpose, tests, limits, and approvals", "model evidence dossier", "model claims bind to tests, versions, limits, and owners"),
    "Offer Lab": ("Offer owners", "compare offer variants before committing commercial resources", "offer experiment brief", "audience, problem, promise, evidence, and test criteria are explicit"),
    "Opportunity Foundry": ("Growth and strategy teams", "turn raw signals into a reviewable opportunity thesis", "opportunity assessment pack", "fit, evidence, uncertainty, effort, and next test are recorded"),
    "PermitProof": ("Permit and operations teams", "prepare evidence against permit conditions", "permit compliance pack", "each permit condition has applicability, evidence, and exception status"),
    "PolicyProof": ("Policy owners", "show how approved policy clauses translate into evidenced practice", "policy implementation proof pack", "clauses map to controls, owners, evidence, and gaps"),
    "POPIA Readiness": ("Privacy and information officers", "assess operational readiness against POPIA requirements", "POPIA readiness pack", "privacy requirements map to evidence, owners, and remediation"),
    "Professional Correspondence": ("Professional service teams", "prepare precise correspondence from controlled facts", "review-ready correspondence", "facts, tone, requested action, and authority boundary are checked"),
    "Professional Correspondence Studio": ("Client-service teams", "produce a coordinated correspondence set for a live case", "correspondence case pack", "messages remain consistent across recipients, facts, and actions"),
    "ProgrammeProof": ("Programme leaders", "connect programme indicators and decisions to current evidence", "programme performance proof pack", "indicators, periods, sources, variance, and decisions reconcile"),
    "ProjectProof": ("Project leaders", "assemble project delivery evidence for a defined review", "project evidence pack", "milestones, outputs, decisions, and supporting records are linked"),
    "PromotionProof": ("Professionals and promotion panels", "organise promotion claims into a reviewable evidence record", "promotion evidence portfolio", "each claim links to dated evidence and declared context"),
    "QualityProof": ("Quality managers", "demonstrate that quality controls operated as intended", "quality control proof pack", "control execution, exceptions, evidence, and corrective action reconcile"),
    "ReleaseProof": ("Release and change owners", "show that a release met its gates before approval", "release evidence pack", "tests, approvals, changes, risks, and rollback evidence are linked"),
    "Report & Pitch Studio": ("Report and proposal owners", "turn approved evidence into a decision-ready narrative", "report and pitch bundle", "claims, figures, narrative, and source references reconcile"),
    "Site Studio": ("Service and product owners", "publish a credible site from approved positioning and evidence", "responsive website bundle", "content, navigation, accessibility, forms, and evidence claims are checked"),
    "Sophia Integrity": ("Academic integrity teams", "review a manuscript for integrity risks without replacing human judgement", "integrity review report", "flagged passages, sources, reasons, and reviewer actions are traceable"),
    "Sophia Research": ("Researchers", "organise sources and claims for a bounded research question", "research evidence map", "sources, claims, methods, limitations, and gaps are explicit"),
    "Sophia Review": ("Authors and reviewers", "obtain anchored feedback without surrendering authorship", "anchored manuscript review", "each comment points to text, rationale, and suggested action"),
    "Sophia Supervisor": ("Research supervisors", "review milestone progress against agreed research expectations", "supervision milestone pack", "progress, evidence, concerns, decisions, and next actions are recorded"),
    "Sophia Tutor": ("Learners and educators", "receive guided support on a defined learning topic", "guided learning review pack", "explanations, checks, sources, and human feedback boundaries are clear"),
    "SupplierCyberProof": ("Supply-chain cyber risk teams", "assess supplier cyber evidence before a sourcing decision", "supplier cyber assurance pack", "supplier claims map to controls, evidence freshness, and gaps"),
    "TenderProof": ("Bid and tender teams", "prepare a compliant tender response evidence base", "tender compliance matrix", "every requirement maps to response content, evidence, owner, and status"),
    "VAMP Performance": ("Professionals and performance reviewers", "organise performance claims before consequential review", "performance evidence snapshot", "objectives, claims, evidence, periods, and reviewer boundaries reconcile"),
    "VendorProof": ("Procurement and vendor-risk teams", "assess vendor claims against required evidence", "vendor due-diligence proof pack", "requirements, vendor evidence, freshness, exceptions, and owners are explicit"),
    "Vesper Desk": ("Customer-service operators", "turn conversations into controlled, followable customer cases", "customer case record", "conversation lineage, scope, next action, owner, and approval state are present"),
}


def _hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def build_canonical_offer_contract(
    *,
    product: dict[str, Any],
    intake: dict[str, Any],
    archetype: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    try:
        decision_maker, buyer_job, primary_deliverable, specific_check = (
            PRODUCT_OFFER_OVERLAYS[str(product["name"])]
        )
    except KeyError as exc:
        raise ValueError(
            f"offer proposition is missing for product: {product.get('name')}"
        ) from exc
    name = str(product["name"])
    scope_unit = str(product["primary_scope_unit"]).replace("_", " ")
    contract = {
        "schema": "dio.canonical_offer_contract.v1",
        "product_id": str(product["product_id"]),
        "product_name": name,
        "buyer": {
            "classes": deepcopy(product["buyer_classes"]),
            "labels": deepcopy(product["buyer_class_labels"]),
        },
        "problem": {
            "statement": f"For {name}: {decision_maker} need to {buyer_job}.",
            "evidence_state": "MARKET_HYPOTHESIS",
        },
        "promised_outcome": {
            "statement": (
                f"A {primary_deliverable} prepared for human review across the "
                f"agreed scope of one {scope_unit}."
            ),
            "commitment_class": "BOUNDED_DELIVERABLE_COMMITMENT",
            "customer_result_guaranteed": False,
        },
        "deliverables": [
            {
                "artifact_family": primary_deliverable,
                "acceptance_criteria": [
                    specific_check,
                    "the agreed scope is complete and exclusions are stated",
                    "customer-facing claims remain traceable to supplied sources",
                    "the requested output format passes semantic and file validation",
                ],
                "release_conditions": deepcopy(archetype["release_conditions"]),
                "release_state": "HELD_PENDING_APPROVAL",
            }
        ],
        "proof": {
            "route_execution_proof": {
                "scope": "ROUTE_FAMILY_EXECUTION",
                "state": route["proof_state"],
                "ref": deepcopy(route["proof_ref"]),
            },
            "product_artifact_proof": {
                "scope": "NAMED_PRODUCT_CUSTOMER_ARTIFACT",
                "state": "UNPROVED",
                "ref": None,
            },
            "source_maturity": product.get("source_maturity") or "NOT_RECORDED",
            "commercial_validation": product["commercial_validation"],
            "customers_will_pay": product["customers_will_pay"],
        },
        "price": {
            "model": product["pricing_model"],
            "reference_band_zar": deepcopy(product["reference_band_zar"]),
            "pricing_state": product["pricing_state"],
            "quote_authority": deepcopy(product["quote_authority"]),
        },
        "cta": {
            "label": f"Scope the {primary_deliverable}",
            "action": "BEGIN_GOVERNED_INTAKE",
            "required_inputs": deepcopy(intake["required_inputs"]),
            "quote_authority_created": False,
            "invoice_authority_created": False,
            "release_authority_created": False,
            "external_send_authority": False,
        },
        "offer_state": "PROFESSIONALLY_STRUCTURED_HYPOTHESIS",
        "authority_created": False,
        "external_effects": False,
    }
    contract["offer_contract_sha256"] = _hash(contract)
    return contract

