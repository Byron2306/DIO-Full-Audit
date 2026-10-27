from __future__ import annotations

from adapters.lingua.lifecycle import digest_text
from adapters.lingua.document_translation import (
    translate_document,
    translation_checks,
    build_ollama_body,
)


def request(**extra):
    return {
        "source_language": "English",
        "target_language": "Afrikaans",
        "provider": "ollama",
        "ollama_model": "qwen3:4b",
        "protected_tokens": ["BC-42"],
        "preferred_terms": [],
        **extra,
    }


def test_exact_approved_memory_displaces_calls_but_stale_and_machine_units_do_not():
    paragraphs = [
        {"paragraph_id": "P1", "text": "Keep the gate closed."},
        {"paragraph_id": "P2", "text": "Store BC-42 below 7 degrees."},
        {"paragraph_id": "P3", "text": "Call the office."},
    ]
    memory = {
        "approved_units": [
            {
                "unit_id": "P1",
                "source_hash": digest_text(paragraphs[0]["text"]),
                "target_text": "Hou die hek toe.",
                "reviewer": "Existing reviewer",
                "credit_id": "exact",
            },
            {
                "unit_id": "P2",
                "source_hash": digest_text("Store BC-42 below 9 degrees."),
                "target_text": "Bewaar BC-42 onder 9 grade.",
                "reviewer": "Existing reviewer",
                "credit_id": "stale",
            },
        ]
    }
    seen = []

    def generate(system, prompt, **kwargs):
        seen.append(prompt)
        return (
            "Bewaar BC-42 onder 7 grade."
            if "Store BC-42" in prompt
            else "Bel die kantoor."
        ), {"model": "qwen3:4b"}

    result, provider = translate_document(
        request(beast_context=memory, automated_language_critic=False),
        paragraphs,
        generate=generate,
    )
    assert len(seen) == 2
    assert result["translations"][0]["translated"] == "Hou die hek toe."
    assert (
        result["translations"][0]["translation_state"] == "human_approved_crystallized"
    )
    assert result["translations"][1]["translation_state"] == "machine_review_candidate"
    assert result["lingua_translation"]["memory_hits"] == 1
    assert result["lingua_translation"]["stale_memory_units"] == ["P2"]
    assert not result["lingua_translation"]["linguistic_quality_approved"]


def test_validator_flags_english_negation_loss_and_changed_numbers_on_unseen_input():
    issues = translation_checks(
        "Do not open valve BC-42 until 7 minutes have passed.",
        "Open valve BC-42 after 9 minutes.",
        "Afrikaans",
        ["BC-42"],
        [],
    )
    assert {
        "target_language_evidence_missing",
        "source_negation_missing",
        "missing_numbers",
        "added_numbers",
    } <= {i["code"] for i in issues}


def test_critic_cannot_replace_a_fact_preserving_candidate_with_a_broken_revision():
    responses = iter(
        [
            ("Moenie klep BC-42 oopmaak voordat 7 minute verby is nie.", {}),
            (
                '{"translation":"Maak klep BC-42 na 9 minute oop.","issues":[],"verdict":"acceptable"}',
                {},
            ),
        ]
    )

    def generate(*args, **kwargs):
        return next(responses)

    result, _ = translate_document(
        request(automated_language_critic=True, lingua_max_attempts=1),
        [
            {
                "paragraph_id": "P1",
                "text": "Do not open valve BC-42 until 7 minutes have passed.",
            }
        ],
        generate=generate,
    )
    row = result["translations"][0]
    assert row["translated"].startswith("Moenie")
    assert row["critic_revision_rejected"] is True
    assert row["translation_state"] == "machine_review_candidate"


def test_qwen_no_thinking_prompt_is_bounded_and_keeps_explicit_model():
    body = build_ollama_body(
        "qwen3:4b",
        "Translate.",
        "Unseen source.",
        max_predict=280,
        temperature=0.05,
        json_mode=True,
    )
    assert body["model"] == "qwen3:4b"
    assert body["think"] is False
    assert body["format"]["required"] == ["translation"]
    assert body["options"]["num_predict"] == 280


def test_pipeline_routes_localization_through_lingua_after_technical_edit():
    from unittest.mock import patch
    from adapters.document_studio.pipeline import call_provider

    req = request(
        service="edit_and_translate",
        source_language_profile={"prompt_guidance": "English"},
        target_language_profile={"prompt_guidance": "Afrikaans", "status": "review"},
        document_domain="Operations",
        audience="Residents",
        style_standard="Clear",
    )
    paragraphs = [{"paragraph_id": "P1", "text": "The gate are closed."}]
    edit = {
        "edits": [{"paragraph_id": "P1", "revised": "The gate is closed."}],
        "qa_flags": [],
    }
    translated = {
        "translations": [{"paragraph_id": "P1", "translated": "Die hek is toe."}],
        "qa_flags": [],
        "lingua_translation": {},
    }
    with patch(
        "adapters.document_studio.pipeline.invoke_provider",
        return_value=(edit, {"model": "qwen3:4b"}),
    ), patch(
        "adapters.document_studio.pipeline.translate_document",
        return_value=(translated, {"model": "qwen3:4b"}),
    ) as translate:
        result, _ = call_provider(req, paragraphs)
    assert translate.call_args.args[1] == [
        {"paragraph_id": "P1", "text": "The gate is closed."}
    ]
    assert result["edits"] == edit["edits"]


def test_explicit_marian_backend_uses_local_mt_and_does_not_change_declared_llm():
    from unittest.mock import patch

    req = request(
        lingua_translation_backend="marian_local", automated_language_critic=False
    )
    with patch(
        "adapters.lingua.document_translation.marian_generate",
        return_value=(
            '{"translation":"Die hek is toe."}',
            {"provider": "local_marian", "model": "Helsinki-NLP/opus-mt-en-af"},
        ),
    ) as mt:
        result, provider = translate_document(
            req, [{"paragraph_id": "P1", "text": "The gate is closed."}]
        )
    assert mt.call_count == 1
    assert result["translations"][0]["translated"] == "Die hek is toe."
    assert provider["provider"] == "local_marian"
    assert req["ollama_model"] == "qwen3:4b"


def test_local_mt_manifest_rejects_modified_model_file(tmp_path):
    from adapters.lingua.local_mt import verify_model
    import hashlib, json

    (tmp_path / "config.json").write_text("tampered")
    (tmp_path / "DIO_MODEL_MANIFEST.json").write_text(
        json.dumps(
            {
                "repository": "Helsinki-NLP/opus-mt-en-af",
                "revision": "6bb29b2752ad425fae1ecdaba201e2de636ecc24",
                "files": {
                    "config.json": {"sha256": hashlib.sha256(b"original").hexdigest()}
                },
            }
        )
    )
    import pytest

    with pytest.raises(ValueError, match="hash"):
        verify_model(tmp_path)


def test_beast_authority_does_not_overwrite_translation_of_a_revised_source():
    from adapters.document_studio.pipeline import apply_beast_authority

    source = "The gate is closed."
    result = {"translations": [{"paragraph_id": "P1", "translated": "Die hek is toe."}]}
    stale = {
        "approved_units": [
            {
                "unit_id": "P1",
                "source_hash": digest_text("The gate is open."),
                "target_text": "Die hek is oop.",
            }
        ]
    }
    apply_beast_authority(result, stale, [{"paragraph_id": "P1", "text": source}])
    assert result["translations"][0]["translated"] == "Die hek is toe."
    assert result["beast_authority"]["approved_units_applied"] == []


def test_review_template_is_actionable_but_never_grants_human_approval():
    from adapters.lingua.document_translation import build_review_template

    template = build_review_template(
        {
            "semantic_object_id": "DOC-UNSEEN",
            "target_language": "Afrikaans",
            "document_domain": "Facilities",
        },
        [{"paragraph_id": "P1", "text": "Keep the door closed."}],
        {"P1": {"translated": "Hou die deur toe."}},
        [{"paragraph_id": "P1", "issue": "Check door terminology"}],
    )
    assert template["approval_state"] == "pending"
    assert template["reviewer"] == ""
    assert template["units"][0]["approved"] is False
    assert template["units"][0]["source_hash"] == digest_text("Keep the door closed.")
    assert template["units"][0]["flag_resolutions"][0]["resolution"] == "pending"


def test_memory_from_a_different_language_and_machine_state_is_not_reused():
    req = request(
        beast_context={
            "target_language": "isiZulu",
            "approved_units": [
                {
                    "unit_id": "P1",
                    "source_hash": digest_text("Close the door."),
                    "target_text": "Vala umnyango.",
                    "reviewer": "Prior reviewer",
                    "credit_id": "other-language",
                }
            ],
        },
        automated_language_critic=False,
    )
    result, _ = translate_document(
        req,
        [{"paragraph_id": "P1", "text": "Close the door."}],
        generate=lambda *args, **kw: ('{"translation":"Maak die deur toe."}', {}),
    )
    assert result["translations"][0]["translated"] == "Maak die deur toe."
    assert result["lingua_translation"]["memory_hits"] == 0


def test_technical_edit_preserves_supplied_bilingual_terminology_before_translation():
    from unittest.mock import patch
    from adapters.document_studio.pipeline import call_provider

    req = request(
        service="edit_and_translate",
        source_language_profile={"prompt_guidance": "English"},
        target_language_profile={"prompt_guidance": "Afrikaans", "status": "review"},
        document_domain="Operations",
        audience="Residents",
        style_standard="Clear",
        preferred_terms=[{"source": "collection point", "target": "versamelpunt"}],
    )
    source = [
        {
            "paragraph_id": "P1",
            "text": "The Afrikaans term for collection point is 'versamelpunt'.",
        }
    ]
    with patch(
        "adapters.document_studio.pipeline.invoke_provider",
        return_value=(
            {
                "edits": [{"paragraph_id": "P1", "revised": source[0]["text"]}],
                "qa_flags": [],
            },
            {},
        ),
    ) as edit, patch(
        "adapters.document_studio.pipeline.translate_document",
        return_value=(
            {"translations": [], "qa_flags": [], "lingua_translation": {}},
            {},
        ),
    ):
        call_provider(req, source)
    assert "versamelpunt" in edit.call_args.args[0]["protected_tokens"]
    assert "collection point" in edit.call_args.args[0]["protected_tokens"]


def test_mt_masks_protected_names_and_terms_without_forcing_hallucinated_suffixes():
    from adapters.lingua.local_mt import protect_spans, restore_spans

    text = "Protected name: Unseen Hope Link. Confirm the collection point at 10:30."
    masked, spans = protect_spans(
        text,
        ["Unseen Hope Link", "10:30"],
        [{"source": "collection point", "target": "versamelpunt"}],
    )
    assert "Unseen Hope Link" not in masked
    assert "collection point" not in masked
    assert (
        restore_spans(masked, spans)
        == "Protected name: Unseen Hope Link. Confirm the versamelpunt at 10:30."
    )
    import pytest

    with pytest.raises(ValueError, match="protected placeholder"):
        restore_spans("No preserved placeholders", spans)


def test_mt_placeholder_restoration_tolerates_model_case_and_token_spacing():
    from adapters.lingua.local_mt import restore_spans

    assert (
        restore_spans("Die term is ZXq 1.", {"ZXQ1": "versamelpunt"})
        == "Die term is versamelpunt."
    )


def test_sentence_units_preserve_all_instructions_and_do_not_split_decimal_numbers():
    from adapters.lingua.local_mt import split_sentences

    source = "Record 2.5 ml at 07:15. Do not release batch LC-204. Call the supervisor before moving stock."
    units = split_sentences(source)
    assert units == [
        "Record 2.5 ml at 07:15.",
        "Do not release batch LC-204.",
        "Call the supervisor before moving stock.",
    ]
    assert " ".join(units) == source


def test_rejected_mt_generation_gets_one_bounded_resample_without_using_broken_text():
    attempts = []

    def generate(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Offline MT lost protected placeholder")
        return '{"translation":"Hou die hek toe."}', {}

    result, _ = translate_document(
        request(automated_language_critic=False),
        [{"paragraph_id": "P1", "text": "Keep the gate closed."}],
        generate=generate,
    )
    assert len(attempts) == 2
    assert result["translations"][0]["translated"] == "Hou die hek toe."
    assert (
        result["translations"][0]["attempts"][0]["error"]
        == "Offline MT lost protected placeholder"
    )


def test_critic_provenance_reports_actual_reviewer_model_instead_of_translation_model():
    responses = iter(
        [
            (
                '{"translation":"Hou die hek toe."}',
                {"provider": "ollama", "model": "translator-model"},
            ),
            (
                '{"translation":"Hou die hek toe.","issues":[],"verdict":"acceptable"}',
                {"provider": "ollama", "model": "reviewer-model"},
            ),
        ]
    )
    result, _ = translate_document(
        request(automated_language_critic=True),
        [{"paragraph_id": "P1", "text": "Keep the gate closed."}],
        generate=lambda *a, **k: next(responses),
    )
    assert result["translation_critic"]["model"] == "reviewer-model"
    assert result["translation_critic"]["provider"] == "ollama"


def test_local_processing_does_not_invent_remote_consent_or_require_cloud_authority(
    tmp_path,
):
    import pytest
    from adapters.document_studio.pipeline import run_document_studio

    req = request(
        service="translation",
        job_id="LOCAL-CONSENT-001",
        human_language_review_required=True,
        owner_authorized=True,
        remote_processing_approved=False,
        document_path=str(tmp_path / "missing.txt"),
    )
    with pytest.raises(FileNotFoundError):
        run_document_studio(req, tmp_path / "request.json", tmp_path / "outputs")
    assert req["remote_processing_approved"] is False


def test_professional_profile_uses_contextual_terms_without_changing_physical_quarters():
    from adapters.lingua.terminology import prepare_translation_inputs

    req = request(lingua_terminology_profile="professional_af_v1")
    source = "The board has submitted it's report for the next quarter. Turn the valve by a quarter of a turn."
    normalized, terms, receipt = prepare_translation_inputs(req, source)
    assert "submitted its report" in normalized
    assert "a quarter of a turn" in normalized
    assert {
        "source": "next quarter",
        "target": "volgende kwartaal",
        "provenance": "machine_proposed_review_required",
    } in terms
    assert not any(t["source"] == "quarter" for t in terms)
    assert receipt["source_digest"] == digest_text(source)
    assert receipt["human_approved"] is False


def test_professional_profile_keeps_certified_and_sworn_distinct_and_honours_customer_terms():
    from adapters.lingua.terminology import prepare_translation_inputs

    req = request(
        lingua_terminology_profile="professional_af_v1",
        preferred_terms=[
            {
                "source": "working group",
                "target": "taakspan",
                "note": "Customer supplied",
            }
        ],
    )
    _, terms, receipt = prepare_translation_inputs(
        req, "The working group needs a certified translation and a sworn translation."
    )
    terms_by_source = {t["source"]: t["target"] for t in terms}
    assert terms_by_source["certified translation"] == "gesertifiseerde vertaling"
    assert terms_by_source["sworn translation"] == "beëdigde vertaling"
    assert terms_by_source["working group"] == "taakspan"
    assert receipt["human_approved"] is False


def test_professional_profile_requires_explicit_selection_and_remains_source_bound():
    from adapters.lingua.terminology import prepare_translation_inputs

    assert (
        prepare_translation_inputs(request(), "The programme team is ready.")[1] == []
    )
    req = request(lingua_terminology_profile="professional_af_v1")
    first = prepare_translation_inputs(req, "The programme team is ready.")[2]
    changed = prepare_translation_inputs(req, "The programme team is delayed.")[2]
    assert first["source_digest"] != changed["source_digest"]


def test_document_studio_selects_machine_afrikaans_profile_only_on_marian_lane():
    from adapters.document_studio.pipeline import normalize_language_request

    base = {
        "service": "translation",
        "source_language": "English",
        "target_language": "Afrikaans",
        "human_language_review_required": True,
        "lingua_translation_backend": "marian_local",
    }
    selected = normalize_language_request(base)
    assert selected["lingua_terminology_profile"] == "professional_af_v1"
    assert selected["lingua_terminology_profile_selection"] == "document_studio_default"
    assert "lingua_terminology_profile" not in base
    assert normalize_language_request({**base, "lingua_terminology_profile": ""})["lingua_terminology_profile"] == ""
    assert "lingua_terminology_profile" not in normalize_language_request(
        {**base, "lingua_translation_backend": "ollama"}
    )


def test_marian_profile_diagnostics_reject_unseen_certified_sworn_mistranslation():
    from unittest.mock import patch
    from adapters.document_studio.pipeline import validate_result

    source = "Certified or sworn translation is not requested."
    wrong = "Gerugte of geswore vertaling word nie gevra nie."
    profile_term = {
        "source": "certified or sworn translation",
        "target": "gesertifiseerde of beëdigde vertaling",
        "provenance": "machine_proposed_review_required",
    }
    req = request(
        service="translation",
        lingua_translation_backend="marian_local",
        lingua_terminology_profile="professional_af_v1",
        automated_language_critic=False,
        lingua_max_attempts=1,
    )
    rows = [{"paragraph_id": "P1", "text": source}]
    with patch(
        "adapters.lingua.document_translation.marian_generate",
        return_value=(
            '{"translation":"' + wrong + '"}',
            {"provider": "local_marian", "terminology_profile": {"applied_terms": [profile_term]}},
        ),
    ):
        result, _ = translate_document(req, rows)

    assert "preferred_term_missing" in {
        issue["code"] for issue in result["translations"][0]["language_diagnostics"]
    }
    validation = validate_result(req, rows, result)
    assert not validation["passed"]
    assert "gesertifiseerde of beëdigde vertaling" in validation["errors"][0]
    assert result["lingua_translation"]["linguistic_quality_approved"] is False


def test_afrikaans_negation_structures_reject_known_incomplete_forms():
    source = "Certified or sworn translation is not requested."
    broken = translation_checks(
        source, "Gesertifiseerde of beëdigde vertaling is nie gevra.",
        "Afrikaans", [], [],
    )
    assert "afrikaans_negation_incomplete" in {row["code"] for row in broken}
    complete = translation_checks(
        source, "Gesertifiseerde of beëdigde vertaling word nie versoek nie.",
        "Afrikaans", [], [],
    )
    assert "afrikaans_negation_incomplete" not in {row["code"] for row in complete}
    prohibition = translation_checks(
        "Do not release batch LC-204.", "Moenie lot LC-204 vrystel.",
        "Afrikaans", ["LC-204"], [],
    )
    assert "afrikaans_negation_incomplete" in {row["code"] for row in prohibition}
    complete_prohibition = translation_checks(
        "Do not release batch LC-204.", "Moenie lot LC-204 vrystel nie.",
        "Afrikaans", ["LC-204"], [],
    )
    assert "afrikaans_negation_incomplete" not in {
        row["code"] for row in complete_prohibition
    }
    short_negative = translation_checks(
        "I do not understand.", "Ek verstaan nie.", "Afrikaans", [], [],
    )
    assert "afrikaans_negation_incomplete" not in {
        row["code"] for row in short_negative
    }


def test_signed_temperature_requires_same_sign_without_internal_spacing():
    source = "Do not release batch LC-204 above -18 degrees Celsius."
    valid = "Moenie lot LC-204 bo -18 grade Celsius vrystel nie."
    valid_codes = {row["code"] for row in translation_checks(
        source, valid, "Afrikaans", ["LC-204"], [],
    )}
    assert not any(code.startswith("signed_number_") for code in valid_codes)
    assert "afrikaans_negation_incomplete" not in valid_codes
    separated = "Moenie lot LC-204 bo - 18 grade Celsius vrystel nie."
    issues = translation_checks(source, separated, "Afrikaans", ["LC-204"], [])
    assert "signed_number_spacing" in {row["code"] for row in issues}
    lost = "Moenie lot LC-204 bo 18 grade Celsius vrystel nie."
    issues = translation_checks(source, lost, "Afrikaans", ["LC-204"], [])
    assert "signed_number_lost" in {row["code"] for row in issues}
