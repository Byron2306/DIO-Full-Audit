import json, os
from pathlib import Path
from presence_core.engine import process_envelope
from presence_core import llm


class _Response:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


def make_root(tmp_path):
    (tmp_path/'config').mkdir(); (tmp_path/'telemetry').mkdir(); (tmp_path/'config'/'routes.json').write_text(json.dumps({'routes':[{'product':'homs','keywords':['homs','assessment']},{'product':'evidex','keywords':['evidex','evidence pack']}]})); return tmp_path

def test_public_intake_is_held(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40); cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}; env={'channel':'telegram','external_user_id':'123','text':'I need HOMS to create an assessment','message_type':'text'}; r=process_envelope(env,root,cfg); assert r['intake']['state']=='pending_operator_review'; assert r['authority']['fulfilment_released'] is False; assert list((root/'state/presence/needs_you').glob('*.json'))

def test_public_status_fails_closed(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40); cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}; r=process_envelope({'channel':'telegram','external_user_id':'123','text':'where is my order?','message_type':'text'},root,cfg); assert 'identity' in r['reply']['text'].lower(); assert r['authority']['executed_external_action'] is False

def test_operator_role_is_server_allowlist(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_OPERATOR_TELEGRAM_IDS','777'); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40); cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}; r=process_envelope({'channel':'telegram','external_user_id':'777','text':'morning lilith','message_type':'text','_trusted_edge_role':'operator'},root,cfg); assert r['role']=='operator' and r['decision']['intent']=='operator_summary'

def test_telegram_start_campaign_hint_flows_to_intake(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_PRESENCE_SHARED_SECRET','s'*40)
    cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    env={'channel':'telegram','external_user_id':'555','text':'I need HOMS to create an assessment','message_type':'text','metadata':{'telegram_start_payload':'MKT-HOMS-42'}}
    r=process_envelope(env,root,cfg)
    assert r['intake']['campaign_hint']=='MKT-HOMS-42'

def test_public_edge_cannot_spoof_operator_even_with_allowlisted_user(tmp_path,monkeypatch):
    root=make_root(tmp_path); monkeypatch.setenv('DIO_OPERATOR_TELEGRAM_IDS','777'); monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT','i'*40)
    cfg={'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    r=process_envelope({'channel':'telegram','external_user_id':'777','text':'morning lilith','message_type':'text','_trusted_edge_role':'public'},root,cfg)
    assert r['role']=='public' and r['decision']['intent']!='operator_summary'


def test_presence_response_does_not_expose_internal_conversation_state(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT', 'i' * 40)
    cfg = {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    response = process_envelope({'channel':'telegram','external_user_id':'123','text':'Tell me about HOMS','message_type':'text'}, root, cfg)
    assert 'conversation_state' not in response
    assert (root/'state/presence'/'conversation_state'/f"{response['conversation_id']}.json").is_file()


def test_presence_core_feeds_prior_exchange_to_ollama_draft(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT', 'i' * 40)
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS', '1')
    monkeypatch.setenv('DIO_PRESENCE_LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('OLLAMA_URL', 'http://ollama.test')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3.5:4b')
    cfg = {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    prompts = []
    replies = iter([
        'HOMS helps prepare governed assessment work for educator review.',
        'Yes. For a large marking batch, we can narrow the workflow before an intake.'
    ])

    def fake_post(url, json, timeout):
        if json.get('format') == 'json':
            return _Response('{"intent":"general_info","product":null,"confidence":0.5}')
        prompts.append(json['messages'][1]['content'])
        return _Response(next(replies))

    monkeypatch.setattr(llm.httpx, 'post', fake_post)

    first = {'channel':'telegram','external_user_id':'123','text':'Tell me about HOMS','message_type':'text'}
    second = {'channel':'telegram','external_user_id':'123','text':'Would that help with 80 papers?','message_type':'text'}
    process_envelope(first, root, cfg)
    process_envelope(second, root, cfg)

    assert len(prompts) == 2
    assert 'Tell me about HOMS' in prompts[1]
    assert 'HOMS helps prepare governed assessment work for educator review.' in prompts[1]
    assert 'Would that help with 80 papers?' in prompts[1]


def test_presence_engine_uses_huggingface_cortex_provider(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT', 'i' * 40)
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS', '1')
    monkeypatch.setenv('DIO_PRESENCE_LLM_PROVIDER', 'hf')
    monkeypatch.setenv('HF_TOKEN', 'hf_test_token')
    monkeypatch.setenv('DIO_PRESENCE_HF_MODEL', 'Qwen/Qwen3.5-9B:deepinfra')
    monkeypatch.delenv('OLLAMA_URL', raising=False)
    monkeypatch.delenv('OLLAMA_MODEL', raising=False)
    cfg = {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    calls = []

    class _HFResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {'choices': [{'message': {'content': 'For that HOMS workflow, I can explain the governed assessment path naturally.'}}]}

    def fake_post(url, json, timeout, headers=None):
        calls.append((url, json, headers))
        return _HFResponse()

    monkeypatch.setattr(llm.httpx, 'post', fake_post)

    response = process_envelope({'channel':'telegram','external_user_id':'123','text':'Tell me about HOMS','message_type':'text'}, root, cfg)

    assert response['reply']['text'].startswith('For that HOMS workflow')
    assert calls and calls[0][0] == 'https://router.huggingface.co/v1/chat/completions'


def test_presence_feeds_governed_product_knowledge_into_cortex(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    (root/'config'/'dio_product_portfolio.json').write_text(json.dumps({
        'truth_boundary': 'Portfolio descriptions are read-only context and create no authority.',
        'products': [{
            'id': 'homs',
            'name': 'HOMS',
            'customer_facing': True,
            'one_liner': 'HOMS_CANON_KNOWLEDGE_MARKER turns rubric-bound marking into a governed educator-review workflow.',
            'risk_boundary': 'Educator judgment remains the final authority.'
        }]
    }))
    monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT', 'i' * 40)
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS', '1')
    monkeypatch.setenv('DIO_PRESENCE_LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('OLLAMA_URL', 'http://ollama.test')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3.5:4b')
    cfg = {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    prompts = []

    def fake_post(url, json, timeout):
        if json.get('format') == 'json':
            return _Response('{"intent":"product_info","product":"homs","confidence":0.95}')
        prompts.append(json['messages'][1]['content'])
        return _Response('For HOMS, I can explain the governed marking path without taking educator authority.')

    monkeypatch.setattr(llm.httpx, 'post', fake_post)
    response = process_envelope({'channel':'telegram','external_user_id':'123','text':'Tell me about HOMS','message_type':'text'}, root, cfg)

    assert prompts
    assert 'HOMS_CANON_KNOWLEDGE_MARKER' in prompts[0]
    assert 'Portfolio descriptions are read-only context and create no authority.' in prompts[0]
    assert response['authority']['executed_external_action'] is False


def test_presence_feeds_verified_beast_crystal_into_cortex_context(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv('DIO_PRESENCE_IDENTITY_SALT', 'i' * 40)
    monkeypatch.setenv('DIO_PRESENCE_LLM_DRAFTS', '1')
    monkeypatch.setenv('DIO_PRESENCE_LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('OLLAMA_URL', 'http://ollama.test')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3.5:4b')
    cfg = {'state_root':'state/presence','event_log':'telemetry/dio_events.jsonl','routes_path':'config/routes.json'}
    prompts = []

    def fake_crystal(**kwargs):
        return {
            'schema': 'dio.vesper.conversation_crystal_reuse.v1',
            'reply': 'VESPER_CRYSTAL_MARKER DIO keeps conversational guidance separate from execution authority.',
            'source': 'lingua_crystal',
            'crystal_id': 'vesper-dio-summary-v1',
            'reuse_receipt_digest': 'receipt-digest',
            'provider_called': False,
            'authority_created': False,
            'external_effects': False,
        }

    def fake_post(url, json, timeout):
        if json.get('format') == 'json':
            return _Response('{"intent":"general_info","product":null,"confidence":0.5}')
        prompts.append(json['messages'][1]['content'])
        return _Response('Yes. DIO keeps the conversational layer separate from governed execution authority.')

    monkeypatch.setattr('presence_core.engine.resolve_conversation_crystal', fake_crystal, raising=False)
    monkeypatch.setattr(llm.httpx, 'post', fake_post)
    response = process_envelope({'channel':'telegram','external_user_id':'123','text':'Tell me about DIO','message_type':'text'}, root, cfg)

    assert prompts
    assert 'VESPER_CRYSTAL_MARKER' in prompts[0]
    assert 'provider_called' in prompts[0]
    assert response['authority']['executed_external_action'] is False


def test_active_commercial_case_outranks_stale_conversation_product(
    tmp_path,
    monkeypatch,
):
    from presence_core.customer_cases import (
        create_or_attach_case,
        find_case_for_conversation,
        update_case,
    )
    from presence_core.engine import process_envelope
    from presence_core.state import (
        load_conversation_state,
        load_or_create_conversation,
        save_conversation_state,
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_IDENTITY_SALT",
        "i" * 40,
    )

    root = make_root(tmp_path)

    # This regression exercises the real 68-product commercial resolver.
    # Seed its immutable historical 53-row canon anchor into the test root.
    source_root = Path(__file__).resolve().parents[1]
    source_crosswalk = (
        source_root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk = (
        root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    test_crosswalk.write_bytes(
        source_crosswalk.read_bytes()
    )

    cfg = {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }

    presence_root = (
        root / "state" / "presence"
    )

    envelope = {
        "channel": "telegram",
        "external_user_id": "123",
        "text": (
            "I'm happy with the R1,000 price. "
            "Please proceed."
        ),
        "message_type": "text",
    }

    # Create the same conversation identity that process_envelope()
    # will resolve.
    conv = load_or_create_conversation(
        presence_root,
        envelope,
        "public",
    )

    conversation_id = conv["conversation_id"]

    # Deliberately poison conversational memory with a stale product.
    conversation_state = load_conversation_state(
        presence_root,
        conversation_id,
    )

    conversation_state[
        "selected_product"
    ] = "document_studio"

    conversation_state[
        "candidate_products"
    ] = ["document_studio"]

    conversation_state[
        "last_route_intent"
    ] = "pricing_info"

    save_conversation_state(
        presence_root,
        conversation_state,
    )

    # Governed case truth says something different and is further
    # along an active commercial lifecycle.
    case = create_or_attach_case(
        presence_root,
        conversation_id=conversation_id,
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Review",
    )

    case = update_case(
        presence_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-SOPHIA-REVIEW",
                    "conversation_id": conversation_id,
                    "state": "quarantined",
                    "sha256": "a" * 64,
                    "size_bytes": 12345,
                    "original_file_name": "article.pdf",
                    "mime_type": "application/pdf",
                    "safe_to_parse": False,
                    "safe_to_execute": False,
                }
            ],
            "scope": {
                "source": "bounded_scope_scan",
                "attachment_id": "ATT-SOPHIA-REVIEW",
                "scope_scan_sha256": "a" * 64,
                "quantity": 27,
                "page_count": 27,
                "primary_scope_unit": (
                    "manuscript_page"
                ),
                "semantic_analysis_performed": False,
                "embedded_content_executed": False,
            },
            "commercial": {
                "pricing_state": "HYPOTHESIS",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": True,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "payment_state": "unverified",
            },
            "authority_created": False,
        },
        evidence_ref=(
            "test:active-commercial-case"
        ),
    )

    response = process_envelope(
        envelope,
        root,
        cfg,
    )

    current_case = (
        find_case_for_conversation(
            presence_root,
            conversation_id,
        )
    )

    current_state = (
        load_conversation_state(
            presence_root,
            conversation_id,
        )
    )

    assert current_case is not None

    # Governed commercial case truth must survive the turn.
    assert (
        current_case["product_id"]
        == "Sophia Review"
    )

    assert (
        current_case["stage"]
        == "PRICE_RECOMMENDED"
    )

    assert (
        current_case["commercial"][
            "recommended_amount_zar"
        ]
        == 1000
    )

    # The stale conversational product must not win.
    commercial = response.get("commercial") or {}

    resolved_product = (
        commercial.get("product") or {}
    ).get("name")

    assert (
        resolved_product
        == "Sophia Review"
    ), {
        "decision": response.get("decision"),
        "commercial": response.get("commercial"),
        "current_selected_product": current_state.get(
            "selected_product"
        ),
        "case_product": current_case.get("product_id"),
        "case_stage": current_case.get("stage"),
    }

    assert (
        current_state.get(
            "selected_product"
        )
        == "Sophia Review"
    )

    # Customer acceptance is evidence/context only.
    # It must not manufacture authority.
    assert (
        response["authority"][
            "financial_commitment_authorized"
        ]
        is False
    )

    assert (
        response["authority"][
            "fulfilment_released"
        ]
        is False
    )

    assert (
        current_case.get(
            "authority_created"
        )
        is False
    )

    reply_text = response["reply"]["text"]

    assert "R1,000" in reply_text
    assert "R450" not in reply_text


def test_explicit_current_turn_product_can_override_active_case_context(
    tmp_path,
    monkeypatch,
):
    from pathlib import Path

    from presence_core.customer_cases import (
        create_or_attach_case,
        update_case,
    )
    from presence_core.engine import process_envelope
    from presence_core.state import (
        load_conversation_state,
        load_or_create_conversation,
        save_conversation_state,
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_IDENTITY_SALT",
        "i" * 40,
    )

    root = make_root(tmp_path)

    source_root = Path(__file__).resolve().parents[1]
    source_crosswalk = (
        source_root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk = (
        root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    test_crosswalk.write_bytes(
        source_crosswalk.read_bytes()
    )

    cfg = {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }

    presence_root = root / "state" / "presence"

    envelope = {
        "channel": "telegram",
        "external_user_id": "123",
        "text": "I want HOMS Assess instead",
        "message_type": "text",
    }

    conv = load_or_create_conversation(
        presence_root,
        envelope,
        "public",
    )

    conversation_id = conv["conversation_id"]

    state = load_conversation_state(
        presence_root,
        conversation_id,
    )
    state["selected_product"] = "document_studio"
    state["candidate_products"] = ["document_studio"]
    save_conversation_state(
        presence_root,
        state,
    )

    case = create_or_attach_case(
        presence_root,
        conversation_id=conversation_id,
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Review",
    )

    update_case(
        presence_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "commercial": {
                "recommended_amount_zar": 1000,
                "pricing_state": "HYPOTHESIS",
                "quote_state": "not_prepared",
                "payment_state": "unverified",
                "operator_review_required": True,
                "quote_issue_authority": False,
            },
            "authority_created": False,
        },
        evidence_ref="test:explicit-product-override",
    )

    response = process_envelope(
        envelope,
        root,
        cfg,
    )

    assert response["decision"]["product"] == "homs"

    commercial = response.get("commercial") or {}
    product = commercial.get("product") or {}

    assert product.get("name") == "HOMS Assess"
    assert product.get("product_id") == "homs_assess"

    from presence_core.customer_cases import find_case_for_conversation

    persisted_case = find_case_for_conversation(
        presence_root,
        conversation_id,
    )

    assert persisted_case is not None
    assert persisted_case["product_id"] == "Sophia Review"
    assert persisted_case["stage"] == "PRICE_RECOMMENDED"

    assert (
        response["authority"][
            "financial_commitment_authorized"
        ]
        is False
    )


def test_public_acceptance_autoissues_bounded_quote(
    tmp_path,
    monkeypatch,
):
    import json
    from pathlib import Path

    from presence_core.customer_cases import (
        create_or_attach_case,
        find_case_for_conversation,
        update_case,
    )
    from presence_core.engine import process_envelope
    from presence_core.state import (
        load_conversation_state,
        load_or_create_conversation,
        save_conversation_state,
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_IDENTITY_SALT",
        "i" * 40,
    )

    root = make_root(tmp_path)

    # Seed the canonical historical 53-row anchor required by
    # the 68-product commercial registry.
    source_root = Path(__file__).resolve().parents[1]
    source_crosswalk = (
        source_root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk = (
        root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )

    test_crosswalk.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    test_crosswalk.write_bytes(
        source_crosswalk.read_bytes()
    )

    cfg = {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }

    presence_root = root / "state" / "presence"

    envelope = {
        "channel": "telegram",
        "external_user_id": "123",
        "text": (
            "I'm happy with the R1,000 price. "
            "Please proceed."
        ),
        "message_type": "text",
    }

    conv = load_or_create_conversation(
        presence_root,
        envelope,
        "public",
    )

    conversation_id = conv["conversation_id"]

    state = load_conversation_state(
        presence_root,
        conversation_id,
    )
    state["selected_product"] = "Sophia Review"
    state["candidate_products"] = ["Sophia Review"]

    save_conversation_state(
        presence_root,
        state,
    )

    case = create_or_attach_case(
        presence_root,
        conversation_id=conversation_id,
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Review",
    )

    case = update_case(
        presence_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-SOPHIA-27",
                    "conversation_id": conversation_id,
                    "original_file_name": "article.pdf",
                    "sha256": "d" * 64,
                }
            ],
            "scope": {
                "quantity": 27,
                "page_count": 27,
                "primary_scope_unit": "manuscript_page",
                "scope_scan_sha256": "d" * 64,
                "semantic_analysis_performed": False,
                "embedded_content_executed": False,
            },
            "commercial": {
                "buyer_class": "C1",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": True,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "custom_discount_requested": False,
                "bespoke_terms_requested": False,
                "regulatory_exception": False,
            },
            "authority_created": False,
        },
        evidence_ref="test:bounded-autoquote-integration",
    )

    response = process_envelope(
        envelope,
        root,
        cfg,
    )

    stored = find_case_for_conversation(
        presence_root,
        conversation_id,
    )

    assert stored is not None
    assert stored["product_id"] == "Sophia Review"

    # Customer acceptance + bounded policy should issue the quote.
    assert stored["stage"] == "QUOTE_READY"

    commercial = stored["commercial"]

    assert commercial["quote_state"] == "approved"
    assert commercial["quote_issue_authority"] is True
    assert commercial["operator_review_required"] is False
    assert commercial["amount"] == 1000

    quote_id = str(
        commercial.get("quote_id") or ""
    )
    assert quote_id

    quote_path = (
        presence_root
        / "customer_cases"
        / "quotes"
        / f"{quote_id}.json"
    )

    assert quote_path.is_file()

    quote = json.loads(
        quote_path.read_text(
            encoding="utf-8"
        )
    )

    assert quote["amount"] == 1000
    assert quote["product_id"] == "Sophia Review"
    assert quote["source_sha256"] == "d" * 64
    assert quote["scope_quantity"] == 27

    assert (
        quote["approval"]["mode"]
        == "bounded_policy"
    )

    assert (
        quote["approval"]["approved_by"]
        == "policy:bounded_quote_authority"
    )

    # Quote authority is not payment or execution authority.
    assert quote["payment_state"] == "not_verified"
    assert (
        quote["fulfilment_authority_created"]
        is False
    )
    assert (
        quote["release_authority_created"]
        is False
    )
    assert quote["authority_created"] is False

    assert (
        response["authority"][
            "financial_commitment_authorized"
        ]
        is False
    )
    assert (
        response["authority"][
            "fulfilment_released"
        ]
        is False
    )


def test_quote_ready_case_reply_uses_issued_quote_not_generic_tier(
    tmp_path,
    monkeypatch,
):
    import json
    from pathlib import Path

    from presence_core.customer_cases import (
        create_or_attach_case,
        update_case,
    )
    from presence_core.customer_quotes import (
        issue_bounded_quote,
    )
    from presence_core.engine import process_envelope
    from presence_core.state import (
        load_or_create_conversation,
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_IDENTITY_SALT",
        "q" * 40,
    )

    root = make_root(tmp_path)

    source_root = Path(__file__).resolve().parents[1]
    source_crosswalk = (
        source_root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk = (
        root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )

    test_crosswalk.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    test_crosswalk.write_bytes(
        source_crosswalk.read_bytes()
    )

    cfg = {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }

    presence_root = root / "state" / "presence"

    envelope = {
        "channel": "telegram",
        "external_user_id": "123",
        "text": (
            "I'm happy with the R1,000 price. "
            "Please proceed."
        ),
        "message_type": "text",
    }

    conv = load_or_create_conversation(
        presence_root,
        envelope,
        "public",
    )

    case = create_or_attach_case(
        presence_root,
        conversation_id=conv["conversation_id"],
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Review",
    )

    case = update_case(
        presence_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-QREADY",
                    "original_file_name": "article.pdf",
                    "sha256": "f" * 64,
                }
            ],
            "scope": {
                "quantity": 27,
                "primary_scope_unit": "manuscript_page",
                "scope_scan_sha256": "f" * 64,
            },
            "commercial": {
                "buyer_scope": "individual_professional",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": False,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "custom_discount_requested": False,
                "bespoke_terms_requested": False,
                "regulatory_exception": False,
            },
        },
        evidence_ref="test:qready-reply",
    )

    issue_bounded_quote(
        root,
        presence_root,
        case_id=case["case_id"],
        quote_id="DIO-Q-QREADY-001",
    )

    response = process_envelope(
        envelope,
        root,
        cfg,
    )

    reply = response["reply"]["text"]

    assert "R1,000" in reply
    assert "quote" in reply.lower()
    assert "R450" not in reply
    assert "payment" in reply.lower()
    assert "fulfilment" in reply.lower()
    assert "release" in reply.lower()


def test_quote_ready_case_reply_uses_issued_quote_not_generic_tier(
    tmp_path,
    monkeypatch,
):
    import json
    from pathlib import Path

    from presence_core.customer_cases import (
        create_or_attach_case,
        update_case,
    )
    from presence_core.customer_quotes import (
        issue_bounded_quote,
    )
    from presence_core.engine import process_envelope
    from presence_core.state import (
        load_or_create_conversation,
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_IDENTITY_SALT",
        "q" * 40,
    )

    root = make_root(tmp_path)

    source_root = Path(__file__).resolve().parents[1]
    source_crosswalk = (
        source_root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )
    test_crosswalk = (
        root
        / "config"
        / "atlas"
        / "dio_meta_incarnation_crosswalk.csv"
    )

    test_crosswalk.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    test_crosswalk.write_bytes(
        source_crosswalk.read_bytes()
    )

    cfg = {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }

    presence_root = root / "state" / "presence"

    envelope = {
        "channel": "telegram",
        "external_user_id": "123",
        "text": (
            "I'm happy with the R1,000 price. "
            "Please proceed."
        ),
        "message_type": "text",
    }

    conv = load_or_create_conversation(
        presence_root,
        envelope,
        "public",
    )

    case = create_or_attach_case(
        presence_root,
        conversation_id=conv["conversation_id"],
        channel="telegram",
        external_user_id="123",
        product_id="Sophia Review",
    )

    case = update_case(
        presence_root,
        case,
        stage="PRICE_RECOMMENDED",
        patch={
            "attachments": [
                {
                    "attachment_id": "ATT-QREADY",
                    "original_file_name": "article.pdf",
                    "sha256": "f" * 64,
                }
            ],
            "scope": {
                "quantity": 27,
                "primary_scope_unit": "manuscript_page",
                "scope_scan_sha256": "f" * 64,
            },
            "commercial": {
                "buyer_scope": "individual_professional",
                "recommended_amount_zar": 1000,
                "scope_quantity": 27,
                "scope_unit": "manuscript_page",
                "pricing_state": "HYPOTHESIS",
                "governed_reference_band_zar": {
                    "min": 450,
                    "max": 1500,
                },
                "operator_review_required": False,
                "quote_state": "not_prepared",
                "quote_issue_authority": False,
                "custom_discount_requested": False,
                "bespoke_terms_requested": False,
                "regulatory_exception": False,
            },
        },
        evidence_ref="test:qready-reply",
    )

    issue_bounded_quote(
        root,
        presence_root,
        case_id=case["case_id"],
        quote_id="DIO-Q-QREADY-001",
    )

    response = process_envelope(
        envelope,
        root,
        cfg,
    )

    reply = response["reply"]["text"]

    assert "R1,000" in reply
    assert "quote" in reply.lower()
    assert "R450" not in reply
    assert "payment" in reply.lower()
    assert "fulfilment" in reply.lower()
    assert "release" in reply.lower()
