import json

from adapters.lingua.conversation_knowledge import (
    load_public_product_knowledge,
    resolve_knowledge_answer,
    retrieve_conversation_knowledge,
)


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_root(tmp_path):
    root = tmp_path
    _write(
        root / "config" / "dio_product_portfolio.json",
        {
            "schema": "dio.product_portfolio.v1",
            "truth_boundary": "Registered profiles are governed workflow knowledge, not external validation or execution authority.",
            "products": [
                {
                    "id": "dio_assurance",
                    "name": "DIO Assurance",
                    "category": "ai_governance_assurance",
                    "status": "architecture_seeded_external_validation_required",
                    "runtime_mode": "review_workflow",
                    "customer_facing": True,
                    "intake_enabled": True,
                    "one_liner": "Turn AI systems, policies, approvals, incidents, and evidence into a continuously reviewable assurance record.",
                    "pain": "AI evidence is fragmented.",
                    "promise": "A governed control-to-evidence review record.",
                    "offer": "AI Assurance Readiness Pilot",
                    "cta": "Choose one bounded AI workflow.",
                    "risk_boundary": "DIO Assurance does not certify legal compliance or issue an audit opinion.",
                    "keywords": ["AI assurance", "AI audit trail"],
                    "route_keywords": ["dio assurance", "ai assurance"],
                    "expected_outputs": ["control-evidence matrix"],
                    "required_authorities": ["assurance_reviewer"],
                    "activation_gates": ["independent pilot"],
                }
            ],
        },
    )
    _write(
        root / "config" / "commercial_campaigns.json",
        {
            "schema": "knowedge.commercial_campaigns.v2",
            "products": {
                "homs": {
                    "name": "HOMS Assessment Desk",
                    "campaign_line": "Assessment work, prepared for educator review.",
                    "audiences": ["educators with a marking backlog"],
                    "offers": [
                        {
                            "id": "marking_relief",
                            "name": "HOMS Marking Relief",
                            "promise": "Receive structured draft marks, feedback, and an educator review pack.",
                            "price": "R950-R1,800 pilot",
                        }
                    ],
                    "proof": ["Controlled marking batches produced review packs."],
                    "claim_boundaries": [
                        "HOMS does not replace an educator or subject expert.",
                        "Generated marks and feedback remain drafts for educator review.",
                    ],
                },
                "evidex": {
                    "name": "Evidex Evidence Pack",
                    "campaign_line": "From scattered proof to a traceable review pack.",
                    "audiences": ["audit and evidence teams"],
                    "offers": [
                        {
                            "id": "starter",
                            "name": "Starter Evidence Pack",
                            "promise": "Map claims, sources, provenance, and gaps for human review.",
                            "price": "R350-R750",
                        }
                    ],
                    "proof": ["Mapped claims retain source references and provenance."],
                    "claim_boundaries": [
                        "Evidex does not guarantee approval, compliance, audit outcomes, or funding."
                    ],
                },
            },
        },
    )
    _write(
        root / "config" / "lingua_product_routes.json",
        {
            "schema": "dio.lingua.product_routes.v1",
            "products": {
                "homs": {
                    "artifact_types": ["assessment", "memorandum", "educator_feedback"],
                    "required_context": ["subject", "grade", "curriculum_concept"],
                    "channels": ["docx", "pdf", "pptx", "video"],
                },
                "evidex": {
                    "artifact_types": ["stakeholder_report", "evidence_narrative", "claim_map"],
                    "required_context": ["domain", "audience"],
                    "channels": ["docx", "pdf", "email"],
                },
            },
            "authority": {
                "communication_invariants": [
                    "translation_does_not_create_consent_commitment_or_send_authority"
                ]
            },
        },
    )
    _write(
        root / "config" / "routes.json",
        {
            "products": {
                "evidex": {
                    "priority": 10,
                    "keywords": ["audit", "evidence", "evidence pack", "proof", "provenance"],
                },
                "homs": {
                    "priority": 30,
                    "keywords": ["marking", "student papers", "rubric", "memo", "gradebook", "feedback", "exam", "assessment"],
                },
            }
        },
    )
    _write(
        root / "config" / "product_class_routes.json",
        {
            "direct_products": {
                "evidex": {"route_kind": "engine", "engine": "evidex", "auto_promotable": True},
                "homs": {"route_kind": "engine", "engine": "homs", "auto_promotable": True},
            },
            "aliases": {"homs_assess": "homs", "evidex_evidenceops": "evidex"},
        },
    )
    return root


def test_public_knowledge_projects_base_product_without_price_leak(tmp_path):
    root = make_root(tmp_path)
    knowledge = load_public_product_knowledge(root)
    homs = knowledge["homs"]
    assert homs["id"] == "homs"
    assert homs["name"] == "HOMS Assessment Desk"
    assert homs["one_liner"] == "Assessment work, prepared for educator review."
    assert "educator" in homs["risk_boundary"].lower()
    assert homs["artifact_types"] == ["assessment", "memorandum", "educator_feedback"]
    assert "offers" not in homs
    assert "price" not in json.dumps(homs).lower()


def test_public_knowledge_projects_new_portfolio_product_without_authority_fields(tmp_path):
    root = make_root(tmp_path)
    knowledge = load_public_product_knowledge(root)
    assurance = knowledge["dio_assurance"]
    assert assurance["id"] == "dio_assurance"
    assert assurance["customer_facing"] is True
    assert assurance["risk_boundary"].startswith("DIO Assurance")
    assert "required_authorities" not in assurance
    assert "activation_gates" not in assurance


def test_audit_need_retrieves_evidex_without_authority(tmp_path):
    root = make_root(tmp_path)
    result = retrieve_conversation_knowledge(
        root,
        "I need evidence for an audit",
        {"candidate_products": [], "selected_product": None},
        limit=4,
    )
    ids = [row["id"] for row in result["products"]]
    assert ids[0] == "evidex"
    assert result["authority_created"] is False


def test_marking_problem_retrieves_homs_without_starting_work(tmp_path):
    root = make_root(tmp_path)
    result = retrieve_conversation_knowledge(
        root,
        "I have 80 student papers and need consistent marking plus evidence if marks are challenged",
        {"candidate_products": [], "selected_product": None},
        limit=4,
    )
    ids = [row["id"] for row in result["products"]]
    assert ids[0] == "homs"
    assert result["authority_created"] is False


def test_clear_product_question_can_answer_without_provider(tmp_path):
    root = make_root(tmp_path)
    knowledge = retrieve_conversation_knowledge(root, "What can HOMS do?", {}, limit=4)
    answer = resolve_knowledge_answer("What can HOMS do?", knowledge)
    assert answer is not None
    assert answer["source"] == "knowledge"
    assert "homs" in answer["candidate_products"]
    assert answer["action_intent"] == "none"
    assert answer["authority_created"] is False
    assert "educator review" in answer["reply"].lower()
