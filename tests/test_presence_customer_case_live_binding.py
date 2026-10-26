from presence_core.customer_cases import find_case_for_conversation
from presence_core.engine import _bind_live_customer_case


def attachment():
    return {
        "attachment_id": "ATT-TEST123",
        "conversation_id": "CONV-TEST123",
        "state": "quarantined",
        "sha256": "a" * 64,
        "size_bytes": 19738,
        "original_file_name": "sample.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }


def commercial(product):
    return {
        "state": "RESOLVED",
        "product": {"name": product},
        "authority_created": False,
    }


def test_attachment_creates_case_and_preserves_quarantine_boundary(tmp_path):
    case = _bind_live_customer_case(
        presence_root=tmp_path,
        conv={
            "conversation_id": "CONV-TEST123",
            "channel": "telegram",
            "external_user_id": "7741224318",
        },
        correlation="CONV-TEST123",
        envelope={"channel": "telegram", "metadata": {}},
        attachment_record=attachment(),
        commercial=None,
    )

    assert case is not None
    assert case["stage"] == "FILES_RECEIVED_QUARANTINED"
    assert case["customer_identity"]["external_user_ids"] == ["7741224318"]

    row = case["attachments"][0]
    assert row["attachment_id"] == "ATT-TEST123"
    assert row["sha256"] == "a" * 64
    assert row["safe_to_parse"] is False
    assert row["safe_to_execute"] is False


def test_followup_product_resolution_binds_same_case(tmp_path):
    _bind_live_customer_case(
        presence_root=tmp_path,
        conv={
            "conversation_id": "CONV-TEST123",
            "channel": "telegram",
            "external_user_id": "7741224318",
        },
        correlation="CONV-TEST123",
        envelope={"channel": "telegram", "metadata": {}},
        attachment_record=attachment(),
        commercial=None,
    )

    case = _bind_live_customer_case(
        presence_root=tmp_path,
        conv={
            "conversation_id": "CONV-TEST123",
            "channel": "telegram",
            "external_user_id": "7741224318",
        },
        correlation="CONV-TEST123",
        envelope={"channel": "telegram", "metadata": {}},
        attachment_record=None,
        commercial=commercial("Sophia Integrity"),
    )

    assert case["product_id"] == "Sophia Integrity"
    assert case["stage"] == "FILES_RECEIVED_QUARANTINED"

    stored = find_case_for_conversation(tmp_path, "CONV-TEST123")
    assert stored["product_id"] == "Sophia Integrity"
    assert stored["attachments"][0]["attachment_id"] == "ATT-TEST123"


def test_explicit_product_change_is_audited_not_silently_erased(tmp_path):
    conv = {
        "conversation_id": "CONV-TEST123",
        "channel": "telegram",
        "external_user_id": "7741224318",
    }
    envelope = {"channel": "telegram", "metadata": {}}

    _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-TEST123",
        envelope=envelope,
        attachment_record=None,
        commercial=commercial("HOMS Assess"),
    )

    case = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-TEST123",
        envelope=envelope,
        attachment_record=None,
        commercial=commercial("Sophia Integrity"),
    )

    assert case["product_id"] == "Sophia Integrity"
    assert "HOMS Assess" in case["product_history"]
    assert "Sophia Integrity" in case["product_history"]




def test_historical_attachment_advances_case_stage(tmp_path):
    import json

    qdir = tmp_path / "quarantine" / "ATT-HISTORICAL"
    qdir.mkdir(parents=True)

    record = {
        "schema": "dio.presence_attachment.v2",
        "attachment_id": "ATT-HISTORICAL",
        "conversation_id": "CONV-HISTORICAL",
        "state": "quarantined",
        "sha256": "b" * 64,
        "size_bytes": 12345,
        "original_file_name": "historical.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    (qdir / "ATTACHMENT.json").write_text(
        json.dumps(record),
        encoding="utf-8",
    )

    case = _bind_live_customer_case(
        presence_root=tmp_path,
        conv={
            "conversation_id": "CONV-HISTORICAL",
            "channel": "telegram",
            "external_user_id": "12345",
        },
        correlation="CONV-HISTORICAL",
        envelope={"channel": "telegram", "metadata": {}},
        attachment_record=None,
        commercial=commercial("Sophia Integrity"),
    )

    assert case["stage"] == "FILES_RECEIVED_QUARANTINED"
    assert case["attachments"][0]["attachment_id"] == "ATT-HISTORICAL"
    assert case["attachments"][0]["safe_to_parse"] is False
    assert case["attachments"][0]["safe_to_execute"] is False


def test_affirmative_continuation_is_deliberately_narrow():
    from presence_core.engine import _is_affirmative_continuation

    assert _is_affirmative_continuation("Yes please") is True
    assert _is_affirmative_continuation("Go ahead.") is True
    assert _is_affirmative_continuation("Okay") is True

    assert _is_affirmative_continuation(
        "Yes, but use ContractProof instead"
    ) is False

    assert _is_affirmative_continuation(
        "I need a quote for something else"
    ) is False


def test_different_source_after_quote_selects_fresh_successor_case(
    tmp_path,
):
    from presence_core.customer_cases import (
        load_case,
        update_case,
    )

    conv = {
        "conversation_id": "CONV-SUCCESSION-LIVE",
        "channel": "telegram",
        "external_user_id": "7741224318",
    }
    envelope = {
        "channel": "telegram",
        "metadata": {},
    }

    source_a = {
        "attachment_id": "ATT-SOURCE-A",
        "conversation_id": "CONV-SUCCESSION-LIVE",
        "state": "quarantined",
        "sha256": "a" * 64,
        "size_bytes": 1000,
        "original_file_name": "source-a.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    source_b = {
        "attachment_id": "ATT-SOURCE-B",
        "conversation_id": "CONV-SUCCESSION-LIVE",
        "state": "quarantined",
        "sha256": "b" * 64,
        "size_bytes": 2000,
        "original_file_name": "source-b.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    case_a = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-SUCCESSION-LIVE",
        envelope=envelope,
        attachment_record=source_a,
        commercial=commercial("Sophia Review"),
    )

    case_a = update_case(
        tmp_path,
        case_a,
        stage="QUOTE_READY",
        patch={
            "scope": {
                "source": "bounded_scope_scan",
                "attachment_id": "ATT-SOURCE-A",
                "scope_scan_sha256": "a" * 64,
                "page_count": 8,
                "quantity": 8,
                "primary_scope_unit": "manuscript_page",
            },
            "commercial": {
                "quote_state": "approved",
                "quote_id": "DIO-Q-SOURCE-A",
                "quote_recommendation": 750,
                "payment_state": "awaiting_payment",
                "checkout_url": (
                    "https://example.invalid/source-a"
                ),
            },
            "order_ids": [
                "ORDER-SOURCE-A",
            ],
        },
        evidence_ref="scope-and-quote:source-a",
    )

    original_case_id = case_a["case_id"]

    case_b = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-SUCCESSION-LIVE",
        envelope=envelope,
        attachment_record=source_b,
        commercial=commercial("Sophia Review"),
    )

    assert case_b["case_id"] != original_case_id
    assert (
        case_b["predecessor_case_id"]
        == original_case_id
    )

    assert (
        case_b["stage"]
        == "FILES_RECEIVED_QUARANTINED"
    )

    assert case_b["scope"] == {}

    assert (
        case_b["commercial"]["quote_state"]
        == "not_prepared"
    )
    assert (
        case_b["commercial"]["payment_state"]
        == "unverified"
    )
    assert (
        "checkout_url"
        not in case_b["commercial"]
    )
    assert case_b["order_ids"] == []

    assert len(case_b["attachments"]) == 1
    assert (
        case_b["attachments"][0]["attachment_id"]
        == "ATT-SOURCE-B"
    )
    assert (
        case_b["attachments"][0]["sha256"]
        == "b" * 64
    )

    current = find_case_for_conversation(
        tmp_path,
        "CONV-SUCCESSION-LIVE",
    )

    assert current is not None
    assert current["case_id"] == case_b["case_id"]

    stored_a = load_case(
        tmp_path,
        original_case_id,
    )

    assert stored_a is not None
    assert stored_a["stage"] == "QUOTE_READY"
    assert (
        stored_a["scope"]["scope_scan_sha256"]
        == "a" * 64
    )
    assert (
        stored_a["commercial"]["quote_id"]
        == "DIO-Q-SOURCE-A"
    )
    assert (
        stored_a["commercial"]["checkout_url"]
        == "https://example.invalid/source-a"
    )


def test_successor_does_not_backfill_predecessor_source(
    tmp_path,
):
    import json

    from presence_core.customer_cases import (
        update_case,
    )

    conv = {
        "conversation_id": "CONV-SUCCESSION-BACKFILL",
        "channel": "telegram",
        "external_user_id": "7741224318",
    }

    envelope = {
        "channel": "telegram",
        "metadata": {},
    }

    source_a = {
        "schema": "dio.presence_attachment.v2",
        "attachment_id": "ATT-BACKFILL-A",
        "conversation_id": "CONV-SUCCESSION-BACKFILL",
        "state": "quarantined",
        "sha256": "a" * 64,
        "size_bytes": 1000,
        "original_file_name": "source-a.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    source_b = {
        "schema": "dio.presence_attachment.v2",
        "attachment_id": "ATT-BACKFILL-B",
        "conversation_id": "CONV-SUCCESSION-BACKFILL",
        "state": "quarantined",
        "sha256": "b" * 64,
        "size_bytes": 2000,
        "original_file_name": "source-b.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    # Persist historical source A in quarantine so the engine backfill
    # path can see it.
    qa = (
        tmp_path
        / "quarantine"
        / source_a["attachment_id"]
    )
    qa.mkdir(parents=True)
    (qa / "ATTACHMENT.json").write_text(
        json.dumps(source_a),
        encoding="utf-8",
    )

    case_a = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-SUCCESSION-BACKFILL",
        envelope=envelope,
        attachment_record=source_a,
        commercial=commercial("Sophia Review"),
    )

    case_a = update_case(
        tmp_path,
        case_a,
        stage="QUOTE_READY",
        patch={
            "scope": {
                "source": "bounded_scope_scan",
                "attachment_id": "ATT-BACKFILL-A",
                "scope_scan_sha256": "a" * 64,
                "page_count": 8,
            },
            "commercial": {
                "quote_state": "approved",
                "quote_id": "DIO-Q-BACKFILL-A",
                "payment_state": "awaiting_payment",
                "checkout_url": (
                    "https://example.invalid/backfill-a"
                ),
            },
        },
        evidence_ref="scope-and-quote:backfill-a",
    )

    qb = (
        tmp_path
        / "quarantine"
        / source_b["attachment_id"]
    )
    qb.mkdir(parents=True)
    (qb / "ATTACHMENT.json").write_text(
        json.dumps(source_b),
        encoding="utf-8",
    )

    case_b = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-SUCCESSION-BACKFILL",
        envelope=envelope,
        attachment_record=source_b,
        commercial=commercial("Sophia Review"),
    )

    assert (
        case_b["predecessor_case_id"]
        == case_a["case_id"]
    )

    ids = {
        row["attachment_id"]
        for row in case_b["attachments"]
    }

    assert ids == {
        "ATT-BACKFILL-B",
    }


def test_same_source_sha_with_new_attachment_id_stays_on_existing_case(
    tmp_path,
):
    from presence_core.customer_cases import (
        update_case,
    )

    conv = {
        "conversation_id": "CONV-SAME-SHA-CONTINUITY",
        "channel": "telegram",
        "external_user_id": "7741224318",
    }

    envelope = {
        "channel": "telegram",
        "metadata": {},
    }

    source_a = {
        "attachment_id": "ATT-SAME-SHA-A",
        "conversation_id": "CONV-SAME-SHA-CONTINUITY",
        "state": "quarantined",
        "sha256": "c" * 64,
        "size_bytes": 1234,
        "original_file_name": "article-v1.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    same_bytes_new_receipt = {
        "attachment_id": "ATT-SAME-SHA-B",
        "conversation_id": "CONV-SAME-SHA-CONTINUITY",
        "state": "quarantined",
        "sha256": "c" * 64,
        "size_bytes": 1234,
        "original_file_name": "article-uploaded-again.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    case_a = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-SAME-SHA-CONTINUITY",
        envelope=envelope,
        attachment_record=source_a,
        commercial=commercial("Sophia Review"),
    )

    case_a = update_case(
        tmp_path,
        case_a,
        stage="QUOTE_READY",
        patch={
            "scope": {
                "source": "bounded_scope_scan",
                "attachment_id": "ATT-SAME-SHA-A",
                "scope_scan_sha256": "c" * 64,
                "page_count": 8,
                "quantity": 8,
                "primary_scope_unit": "manuscript_page",
            },
            "commercial": {
                "quote_state": "approved",
                "quote_id": "DIO-Q-SAME-SHA",
                "quote_recommendation": 750,
                "payment_state": "awaiting_payment",
                "checkout_url": (
                    "https://example.invalid/same-sha"
                ),
            },
        },
        evidence_ref="scope-and-quote:same-sha",
    )

    original_case_id = case_a["case_id"]

    case_after_reupload = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-SAME-SHA-CONTINUITY",
        envelope=envelope,
        attachment_record=same_bytes_new_receipt,
        commercial=commercial("Sophia Review"),
    )

    assert (
        case_after_reupload["case_id"]
        == original_case_id
    )

    assert (
        "predecessor_case_id"
        not in case_after_reupload
    )

    assert (
        case_after_reupload["stage"]
        == "QUOTE_READY"
    )

    assert (
        case_after_reupload["scope"]["scope_scan_sha256"]
        == "c" * 64
    )

    assert (
        case_after_reupload["commercial"]["quote_id"]
        == "DIO-Q-SAME-SHA"
    )

    assert (
        case_after_reupload["commercial"]["checkout_url"]
        == "https://example.invalid/same-sha"
    )

    attachment_ids = {
        row["attachment_id"]
        for row in case_after_reupload["attachments"]
    }

    assert "ATT-SAME-SHA-A" in attachment_ids
    assert "ATT-SAME-SHA-B" in attachment_ids


def test_different_source_before_scope_stays_on_same_case(
    tmp_path,
):
    conv = {
        "conversation_id": "CONV-MULTIFILE-PRESCOPE",
        "channel": "telegram",
        "external_user_id": "7741224318",
    }

    envelope = {
        "channel": "telegram",
        "metadata": {},
    }

    source_a = {
        "attachment_id": "ATT-PRESCOPE-A",
        "conversation_id": "CONV-MULTIFILE-PRESCOPE",
        "state": "quarantined",
        "sha256": "d" * 64,
        "size_bytes": 1000,
        "original_file_name": "main.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    source_b = {
        "attachment_id": "ATT-PRESCOPE-B",
        "conversation_id": "CONV-MULTIFILE-PRESCOPE",
        "state": "quarantined",
        "sha256": "e" * 64,
        "size_bytes": 2000,
        "original_file_name": "supporting.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    case_a = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-MULTIFILE-PRESCOPE",
        envelope=envelope,
        attachment_record=source_a,
        commercial=commercial("Sophia Review"),
    )

    original_case_id = case_a["case_id"]

    assert case_a["scope"] == {}
    assert (
        case_a["commercial"]["quote_state"]
        == "not_prepared"
    )

    case_after_second_file = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-MULTIFILE-PRESCOPE",
        envelope=envelope,
        attachment_record=source_b,
        commercial=commercial("Sophia Review"),
    )

    assert (
        case_after_second_file["case_id"]
        == original_case_id
    )

    assert (
        "predecessor_case_id"
        not in case_after_second_file
    )

    attachment_ids = {
        row["attachment_id"]
        for row in case_after_second_file["attachments"]
    }

    assert attachment_ids == {
        "ATT-PRESCOPE-A",
        "ATT-PRESCOPE-B",
    }

    assert (
        case_after_second_file["stage"]
        == "FILES_RECEIVED_QUARANTINED"
    )


def test_different_source_before_scope_stays_on_same_case(
    tmp_path,
):
    conv = {
        "conversation_id": "CONV-MULTIFILE-PRESCOPE",
        "channel": "telegram",
        "external_user_id": "7741224318",
    }

    envelope = {
        "channel": "telegram",
        "metadata": {},
    }

    source_a = {
        "attachment_id": "ATT-PRESCOPE-A",
        "conversation_id": "CONV-MULTIFILE-PRESCOPE",
        "state": "quarantined",
        "sha256": "d" * 64,
        "size_bytes": 1000,
        "original_file_name": "main.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    source_b = {
        "attachment_id": "ATT-PRESCOPE-B",
        "conversation_id": "CONV-MULTIFILE-PRESCOPE",
        "state": "quarantined",
        "sha256": "e" * 64,
        "size_bytes": 2000,
        "original_file_name": "supporting.pdf",
        "mime_type": "application/pdf",
        "safe_to_parse": False,
        "safe_to_execute": False,
    }

    case_a = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-MULTIFILE-PRESCOPE",
        envelope=envelope,
        attachment_record=source_a,
        commercial=commercial("Sophia Review"),
    )

    original_case_id = case_a["case_id"]

    assert case_a["scope"] == {}
    assert (
        case_a["commercial"]["quote_state"]
        == "not_prepared"
    )

    case_after_second_file = _bind_live_customer_case(
        presence_root=tmp_path,
        conv=conv,
        correlation="CONV-MULTIFILE-PRESCOPE",
        envelope=envelope,
        attachment_record=source_b,
        commercial=commercial("Sophia Review"),
    )

    assert (
        case_after_second_file["case_id"]
        == original_case_id
    )

    assert (
        "predecessor_case_id"
        not in case_after_second_file
    )

    attachment_ids = {
        row["attachment_id"]
        for row in case_after_second_file["attachments"]
    }

    assert attachment_ids == {
        "ATT-PRESCOPE-A",
        "ATT-PRESCOPE-B",
    }

    assert (
        case_after_second_file["stage"]
        == "FILES_RECEIVED_QUARANTINED"
    )
