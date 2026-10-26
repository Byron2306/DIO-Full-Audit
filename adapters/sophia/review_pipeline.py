from __future__ import annotations

import hashlib
import ipaddress
import json
import mimetypes
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from sovereign_runtime import SovereignRuntimeError, ollama_model, require_ollama_provider
from xml.etree import ElementTree


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def extract_document_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".rst", ".csv"}:
        return path.read_text(encoding="utf-8", errors="replace"), "plain_text"
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        paragraphs = []
        for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
            if text.strip():
                paragraphs.append(text.strip())
        return "\n\n".join(paragraphs), "docx_xml"
    if suffix == ".pdf":
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(path) as document:
                pages = [page.extract_text() or "" for page in document.pages]
            return "\n\n".join(f"[Page {index}]\n{text}" for index, text in enumerate(pages, 1)), "pdfplumber"
        except (ImportError, OSError, ValueError):
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                text=True,
                capture_output=True,
                check=False,
                timeout=90,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, "pdftotext"
            raise ValueError("PDF text extraction failed; provide a text-readable PDF or DOCX.")
    raise ValueError(f"Unsupported manuscript type: {suffix or '(none)'}")


def split_reference_section(text: str) -> tuple[str, str]:
    match = re.search(r"(?im)^\s*(?:#{1,6}\s*)?(references|bibliography|works cited)\s*$", text)
    if not match:
        return text, ""
    return text[: match.start()].strip(), text[match.end() :].strip()


def parse_reference_entries(reference_text: str) -> list[str]:
    if not reference_text.strip():
        return []
    blocks = [re.sub(r"\s+", " ", block).strip() for block in re.split(r"\n\s*\n", reference_text) if block.strip()]
    if len(blocks) > 1:
        return blocks
    entries: list[str] = []
    current = ""
    for raw_line in reference_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        starts_entry = bool(re.match(r"^(?:\[?\d+[.\]]?\s+)?[A-Z][A-Za-z'\u2019-]+(?:,|\s+&|\s+et al\.)", line))
        has_year = bool(re.search(r"\((?:19|20)\d{2}[a-z]?\)", line))
        if current and starts_entry and has_year:
            entries.append(current)
            current = line
        else:
            current = f"{current} {line}".strip()
    if current:
        entries.append(current)
    return entries


def citation_key(author: str, year: str) -> str:
    return f"{re.sub(r'[^a-z0-9]', '', author.lower())}:{year.lower()}"


def extract_in_text_citations(body_text: str) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    parenthetical = re.compile(r"\(([^()]*\b(?:19|20)\d{2}[a-z]?[^()]*)\)")
    narrative = re.compile(
        r"\b([A-Z][A-Za-z'\u2019-]+)(?:\s+(?:and|&)\s+[A-Z][A-Za-z'\u2019-]+|\s+et al\.)?\s*\(((?:19|20)\d{2}[a-z]?)\)"
    )
    for group in parenthetical.findall(body_text):
        for segment in group.split(";"):
            year_match = re.search(r"\b((?:19|20)\d{2}[a-z]?)\b", segment)
            author_match = re.search(r"\b([A-Z][A-Za-z'\u2019-]+)", segment)
            if not (author_match and year_match):
                continue
            author, year = author_match.group(1), year_match.group(1)
            key = citation_key(author, year)
            found[key] = {"key": key, "author": author, "year": year, "form": "parenthetical"}
    for author, year in narrative.findall(body_text):
        key = citation_key(author, year)
        found[key] = {"key": key, "author": author, "year": year, "form": "narrative"}
    return sorted(found.values(), key=lambda row: row["key"])


def reference_key(entry: str) -> str:
    author = re.search(r"^(?:\[?\d+[.\]]?\s+)?([A-Z][A-Za-z'\u2019-]+)", entry)
    year = re.search(r"\(((?:19|20)\d{2}[a-z]?)\)", entry)
    return citation_key(author.group(1), year.group(1)) if author and year else ""


def audit_references(body_text: str, reference_text: str, citation_check: Any) -> dict[str, Any]:
    in_text = extract_in_text_citations(body_text)
    entries = parse_reference_entries(reference_text)
    reference_rows = []
    seen_normalized: set[str] = set()
    seen_dois: set[str] = set()
    duplicate_entries: list[str] = []
    duplicate_dois: list[str] = []
    for index, entry in enumerate(entries, 1):
        normalized = re.sub(r"\W+", "", entry.lower())
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", entry, flags=re.I)
        doi = doi_match.group(0).rstrip(".,;)").lower() if doi_match else ""
        if normalized in seen_normalized:
            duplicate_entries.append(entry)
        seen_normalized.add(normalized)
        if doi and doi in seen_dois:
            duplicate_dois.append(doi)
        if doi:
            seen_dois.add(doi)
        style = citation_check(entry).to_dict()
        issues = []
        if not reference_key(entry):
            issues.append("author_or_year_not_detected")
        if len(entry.split()) < 6:
            issues.append("reference_appears_incomplete")
        if doi and "https://doi.org/" not in entry.lower():
            issues.append("doi_not_in_https_form")
        reference_rows.append({
            "index": index,
            "key": reference_key(entry),
            "entry": entry,
            "doi": doi,
            "style_check": style,
            "issues": issues,
        })
    in_text_keys = {row["key"] for row in in_text}
    reference_keys = {row["key"] for row in reference_rows if row["key"]}
    missing_from_references = [row for row in in_text if row["key"] not in reference_keys]
    uncited_references = [row for row in reference_rows if row["key"] and row["key"] not in in_text_keys]
    actionable = (
        len(missing_from_references)
        + len(uncited_references)
        + len(duplicate_entries)
        + len(duplicate_dois)
        + sum(len(row["issues"]) + int(row["style_check"]["fail_count"]) for row in reference_rows)
    )
    return {
        "schema": "dio.sophia_reference_audit.v1",
        "citation_style": "APA 7 diagnostic",
        "in_text_citations": in_text,
        "reference_entries": reference_rows,
        "missing_from_reference_list": missing_from_references,
        "reference_list_entries_not_cited": uncited_references,
        "duplicate_entries": duplicate_entries,
        "duplicate_dois": duplicate_dois,
        "actionable_issue_count": actionable,
        "status": "needs_revision" if actionable else "clean_first_pass",
        "limits": [
            "This is a deterministic technical audit, not a complete style-editor judgment.",
            "DOI and bibliographic metadata remain verification leads until checked against the publisher or scholarly index.",
        ],
    }


def select_claims(body_text: str, classify_claim_type: Any, limit: int = 12) -> list[dict[str, Any]]:
    body_text = re.sub(r"(?m)^\s*#{1,6}\s+.*$", "", body_text)
    sentences = [
        re.sub(r"\s+", " ", sentence).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", body_text)
        if 8 <= len(sentence.split()) <= 90
    ]
    rows = []
    for sentence in sentences:
        classification_text = re.sub(r"\([^)]*\b(?:19|20)\d{2}[a-z]?[^)]*\)", "", sentence)
        classification_text = re.sub(r"\b(?:19|20)\d{2}[a-z]?\b", "", classification_text)
        classification = classify_claim_type(classification_text)
        if classification.get("evidence_risk") in {"medium", "high"}:
            rows.append({"claim": sentence, **classification})
    priority = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda row: (priority.get(str(row.get("evidence_risk")), 9), -len(row["claim"])))
    return rows[:limit]


def post_json(url: str, payload: dict[str, Any], timeout: float = 45.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        raw = error.read(16384).decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}
        reason = body.get("reason") or body.get("error") or "unspecified_http_refusal"
        raise ValueError(
            f"SERAPH_HTTP_REFUSE status={error.code} "
            f"reason={str(reason)[:500]}"
        ) from error


def fetch_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _review_paragraphs(text: str, limit: int = 120) -> list[dict[str, str]]:
    paragraphs = [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    return [
        {"span_id": f"P{index}", "label": f"P{index}", "quote": item[:1800]}
        for index, item in enumerate(paragraphs[:limit], 1)
    ]


DOI_PATTERN = r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+"


def _allowed_dois(reference_audit: dict[str, Any], sources: list[dict[str, Any]]) -> set[str]:
    """Collect only DOI identifiers already present in supplied review inputs."""
    allowed = {
        str(row.get("doi") or "").strip().lower()
        for row in (reference_audit.get("reference_entries") or [])
        if row.get("doi")
    }
    for source in sources:
        match = re.search(DOI_PATTERN, str(source.get("url") or ""), flags=re.I)
        if match:
            allowed.add(match.group(0).rstrip(".,;)").lower())
    allowed.discard("")
    return allowed


def _require_local_review_endpoint(base_url: str) -> str:
    """Require the Sophia review API to be reached over loopback only."""
    try:
        parsed = urlsplit(str(base_url).strip())
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("REFUSE: invalid Sophia review endpoint authority") from exc
    try:
        loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        loopback = hostname == "localhost"
    if (
        parsed.scheme != "http"
        or not hostname
        or not loopback
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or (port is not None and not (1 <= port <= 65535))
    ):
        raise ValueError(
            "REFUSE: Sophia review endpoint must be a loopback HTTP URL; remote endpoints are disabled"
        )
    return str(base_url).strip().rstrip("/")


def _allowed_citation_keys(reference_audit: dict[str, Any], sources: list[dict[str, Any]]) -> set[str]:
    keys = {
        str(row.get("key") or "")
        for row in (
            list(reference_audit.get("in_text_citations") or [])
            + list(reference_audit.get("reference_entries") or [])
        )
        if row.get("key")
    }
    for row in reference_audit.get("reference_entries") or []:
        entry = str(row.get("entry") or "")
        year_match = re.search(r"\(((?:19|20)\d{2}[a-z]?)\)", entry)
        if not year_match:
            continue
        author_block = entry[: year_match.start()]
        for surname in re.findall(r"(?:^|,\s|&\s)([A-Z][A-Za-z'\u2019-]+)(?=,|\s*&|\s*$)", author_block):
            keys.add(citation_key(surname, year_match.group(1)))
    for source in sources:
        authors = source.get("authors") or []
        year = str(source.get("year") or "")
        if re.fullmatch(r"(?:19|20)\d{2}[a-z]?", year):
            for author in authors:
                surname = re.split(r"[,\s]", str(author).strip())[0]
                if surname:
                    keys.add(citation_key(surname, year))
    return keys


def validate_reasoned_commentary(
    commentary: str,
    result: dict[str, Any],
    valid_anchors: set[str],
    allowed_citation_keys: set[str],
    allowed_dois: set[str],
    expected_provider: str,
) -> dict[str, Any]:
    provider_ok = (
        str(result.get("reasoned_provider") or "").lower()
        == expected_provider.strip().lower()
    )
    provider_status_ok = result.get("reasoned_provider_status") == "ok"
    lane_ok = result.get("source") == "reasoned_integrity_lane"
    mandos_ok = bool((result.get("mandos_judgment") or {}).get("passed"))
    articles_ok = bool(((result.get("article_conformity") or {}).get("summary") or {}).get("all_passed"))

    mentioned_anchors = set(re.findall(r"\b([PC]\d+)\b", commentary))
    invalid_anchors = sorted(mentioned_anchors - valid_anchors)
    valid_mentions = sorted(mentioned_anchors & valid_anchors)
    mentioned_dois = {
        value.rstrip(".,;)").lower()
        for value in re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", commentary, flags=re.I)
    }
    unknown_dois = sorted(mentioned_dois - allowed_dois)

    mentioned_keys: set[str] = set()
    for author, year in re.findall(
        r"\b([A-Z][A-Za-z'\u2019-]+)(?:\s+et al\.)?\s*(?:\(|,\s*)((?:19|20)\d{2}[a-z]?)\)?",
        commentary,
    ):
        mentioned_keys.add(citation_key(author, year))
    unknown_citations = sorted(mentioned_keys - allowed_citation_keys)

    checks = {
        "provider_matches_request": provider_ok,
        "provider_completed": provider_status_ok,
        "reasoned_lane_used": lane_ok,
        "mandos_passed": mandos_ok,
        "genesis_articles_passed": articles_ok,
        "document_anchor_present": bool(valid_mentions),
        "no_unknown_anchors": not invalid_anchors,
        "no_unknown_citations": not unknown_citations,
        "no_unknown_dois": not unknown_dois,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "valid_anchors_mentioned": valid_mentions,
        "invalid_anchors": invalid_anchors,
        "unknown_citations": unknown_citations,
        "unknown_dois": unknown_dois,
    }






def bind_zpd_review_guidance(
    request: dict[str, Any],
    document_path: Path,
    prompt: str,
) -> tuple[str, dict[str, Any] | None]:
    """Bind optional ZPD guidance without granting scoring authority."""
    guidance_path = request.get("zpd_guidance_path")
    if not guidance_path:
        return prompt, None

    import hashlib

    path = Path(str(guidance_path)).expanduser().resolve()
    if not path.is_file():
        raise ValueError("REFUSE: ZPD guidance missing")

    guidance = json.loads(path.read_text())
    if guidance.get("schema") != "dio.homs_zpd_guidance.v1":
        raise ValueError("REFUSE: ZPD guidance schema mismatch")

    if guidance.get("rubric_scoring_authority") != "HOMS_ONLY":
        raise ValueError("REFUSE: ZPD scoring authority mismatch")

    if guidance.get("sophia_adapter_consumed") is not False:
        raise ValueError("REFUSE: ZPD guidance provenance ambiguous")

    # The original manifest was hashed before its new sidecar path
    # was added. Exclude only this transport field.
    original_manifest = {
        k: v for k, v in request.items()
        if k not in {"zpd_guidance_path", "_zpd_binding_receipt"}
    }
    manifest_bytes = json.dumps(
        original_manifest,
        sort_keys=True,
        ensure_ascii=False,
    ).encode()

    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    document_digest = hashlib.sha256(
        document_path.read_bytes()
    ).hexdigest()

    if guidance.get("manifest_sha256") != manifest_digest:
        raise ValueError("REFUSE: ZPD manifest digest mismatch")

    if guidance.get("document_sha256") != document_digest:
        raise ValueError("REFUSE: ZPD document digest mismatch")

    if guidance.get("job_id") != request.get("job_id"):
        raise ValueError("REFUSE: ZPD job identity mismatch")

    if guidance.get("research_question") != request.get("research_question"):
        raise ValueError("REFUSE: ZPD research question mismatch")

    zpd = guidance.get("zpd")
    if not isinstance(zpd, dict) or zpd.get("status") != "HEURISTIC_NOT_LEARNING_PROOF":
        raise ValueError("REFUSE: ZPD estimate not successful")

    if zpd.get("input_mutation_contained") is not True:
        raise ValueError("REFUSE: ZPD input isolation not established")

    instruction = guidance.get("developmental_instruction")
    if (
        not isinstance(instruction, str)
        or not instruction.strip()
        or len(instruction) > 3000
    ):
        raise ValueError("REFUSE: invalid ZPD developmental instruction")

    # The guidance is lower-priority presentation data.
    # It cannot modify academic evidence, grading, or governance.
    addition = (
        "\nZPD DEVELOPMENTAL PRESENTATION GUIDANCE "
        "(advisory; subordinate to all evidence and review rules):\n"
        + instruction.strip()
        + "\nThis guidance affects feedback delivery only. "
        "Do not modify grades, rubric standards, document evidence, "
        "human authorship, citations, or constitutional requirements.\n"
    )

    bound_prompt = prompt + "\n" + addition
    binding = {
        "schema": "dio.sophia_zpd_binding.v1",
        "status": "BOUND_TO_REVIEW_PROMPT",
        "job_id": request.get("job_id"),
        "manifest_sha256": manifest_digest,
        "document_sha256": document_digest,
        "guidance_sha256": hashlib.sha256(
            path.read_bytes()
        ).hexdigest(),
        "outbound_prompt_sha256": hashlib.sha256(
            bound_prompt.encode()
        ).hexdigest(),
        "rubric_scoring_authority": "HOMS_ONLY",
        "governance_validated": False,
    }
    return bound_prompt, binding


def reviewer_commentary(
    base_url: str,
    request: dict[str, Any],
    title: str,
    document_path: Path,
    text: str,
    parser: str,
    reference_audit: dict[str, Any],
    claim_maps: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    reasoned_review_approved = bool(
        request.get(
            "reasoned_review_approved",
            request.get("gemini_review_approved", False),
        )
    )
    try:
        provider = require_ollama_provider(
            request.get("reasoned_provider") or "ollama",
            component="Sophia reasoned review",
        )
        model = ollama_model(
            request.get("reasoned_model")
            or request.get("ollama_model")
        )
    except SovereignRuntimeError as exc:
        return {
            "status": "rejected",
            "source": "sovereign_runtime",
            "encounter_id": None,
            "provider": str(request.get("reasoned_provider") or ""),
            "model": None,
            "remote_processing": False,
            "commentary": str(exc),
        }
    try:
        base_url = _require_local_review_endpoint(base_url)
    except ValueError as exc:
        return {
            "status": "rejected",
            "source": "sovereign_runtime",
            "encounter_id": None,
            "provider": provider or None,
            "model": model or None,
            "remote_processing": False,
            "endpoint_policy": "LOCAL_LOOPBACK_ONLY",
            "commentary": str(exc),
        }
    remote_processing = False

    if not reasoned_review_approved:
        return {
            "status": "approval_required",
            "source": "not_sent",
            "encounter_id": None,
            "provider": provider or None,
            "model": model or None,
            "remote_processing": False,
            "commentary": (
                "Reasoned reviewer processing was not authorized. "
                "Explicit manuscript-owner approval is required before processing."
            ),
        }
    try:
        health = fetch_json(f"{base_url.rstrip('/')}/api/health")
        spans = _review_paragraphs(text)
        claim_dossier = []
        for index, item in enumerate(claim_maps, 1):
            mapping = item.get("source_map") or {}
            claim = item.get("claim_record") or {}
            claim_dossier.append({
                "claim_id": f"C{index}",
                "claim": claim.get("claim"),
                "claim_type": claim.get("claim_type"),
                "evidence_risk": claim.get("evidence_risk"),
                "candidate_support": [
                    {
                        "title": row.get("source_name"),
                        "support_label": row.get("support_label"),
                        "entailment_status": row.get("entailment_status"),
                    }
                    for row in (mapping.get("results") or [])[:3]
                ],
            })
        dossier = {
            "title": title,
            "research_question": str(request.get("research_question") or ""),
            "citation_style": str(request.get("citation_style") or "APA 7"),
            "reference_audit": {
                "status": reference_audit.get("status"),
                "missing_from_reference_list": reference_audit.get("missing_from_reference_list") or [],
                "listed_but_not_cited": [
                    row.get("entry") for row in (reference_audit.get("reference_list_entries_not_cited") or [])
                ],
                "actionable_issue_count": reference_audit.get("actionable_issue_count"),
            },
            "claim_ledger": claim_dossier,
        }
        verified_review_anchors = sorted(
            {row["span_id"] for row in spans}
            | {f"C{index}" for index in range(1, len(claim_dossier) + 1)}
        )
        if not verified_review_anchors:
            raise ValueError("REFUSE: no manuscript-bound review anchors")

        anchor_instruction = (
            "AUTHORIZED REVIEW ANCHORS ONLY: "
            + ", ".join(f"[{anchor}]" for anchor in verified_review_anchors)
            + ". Never cite any other paragraph or claim identifier."
        )

        # Closed-world DOI registry: supplied evidence is not external verification.
        allowed_dois = _allowed_dois(reference_audit, sources)
        citation_instruction = (
            "AUTHORIZED DOI IDENTIFIERS ONLY: "
            + (
                ", ".join(sorted(allowed_dois))
                if allowed_dois
                else "NONE"
            )
            + ". A listed DOI is supplied evidence, not independently verified. "
            + "Never invent, complete, infer, or introduce another DOI."
        )

        prompt = "\n".join([
            "Sophia DIO product review. Evaluate only the attached manuscript and the local audit dossier below.",
            citation_instruction,
            anchor_instruction,
            "Give diagnostic reviewer commentary; do not rewrite manuscript prose or produce submission-ready replacement text.",
            "Use these exact headings: Overall assessment; Major revisions; Minor revisions; Evidence limits; Author-owned next steps.",
            "Anchor every major revision to one or more identifiers from AUTHORIZED REVIEW ANCHORS ONLY.",
            "Apply a closed-world evidence rule: use only authors, publications, citation labels, DOIs, URLs, data, methods, and findings already visible in the dossier/manuscript.",
            "Do not recommend named literature beyond that closed evidence set.",
            "Distinguish what the manuscript states from your inference and from what remains unknown.",
            "Prioritize argument clarity, method adequacy, evidence/claim fit, analytical coherence, limitations, and reference integrity.",
            "End with a short, ordered set of revisions that leaves all final wording and judgment with the author.",
            "Constitutional authorship boundary: explicitly state that the human author decides which revisions to accept and retains final authorship and judgment. Do not write replacement submission-ready text.",
            "Evidence boundary: explicitly identify the limits of the available evidence, distinguish unsupported claims from established findings, and state what remains uncertain or unknown.",
            "Grounding requirement: use at least one authorized anchor in Major revisions. Never invent an anchor.",
            "LOCAL AUDIT DOSSIER:",
            json.dumps(dossier, ensure_ascii=True),
        ])

        prompt, zpd_binding = bind_zpd_review_guidance(
            request, document_path, prompt
        )
        if zpd_binding is not None:
            request["_zpd_binding_receipt"] = zpd_binding

        if not provider:
            raise ValueError("reasoned_provider must be non-empty")
        if not model:
            raise ValueError("reasoned_model must be non-empty")
        payload = {
                "text": prompt,
                "session_token": health.get("session_token") or "",
                "dio_product_review_lane": True,
                "reasoned_integrity_lane": True,
                "reasoned_provider": provider,
                "reasoned_model": model,
                "reasoned_max_predict": 1400,
                "verified_review_anchors": verified_review_anchors,
                "verified_review_manuscript_sha256": hashlib.sha256(
                    document_path.read_bytes()
                ).hexdigest(),
                "document_evidence_task": "dio_sophia_academic_review",
                "document_uploads": [{
                    "source_name": title,
                    "source_path": document_path.name,
                    "mime_type": mimetypes.guess_type(document_path.name)[0] or "application/octet-stream",
                    "modality": "academic_manuscript",
                    "parser": parser,
                    "extracted_text": text[:180_000],
                    "spans": spans,
                    "uncertainty_notes": [
                    (
                        "Reasoned review explicitly approved by manuscript owner. "
                        + ("Remote processing authorized." if remote_processing else "Local processing only.")
                    )
                ],
                }],
                "client_context": {
                    "ui_surface": "dio_sophia_review",
                    "writing_action": "review",
                    "response_mode": "detailed",
                },
                "disable_continuity_memory": True,
                "disable_world_events": True,
                "suppress_academic_retrieval_fastpaths": True,
            }
        review_timeout = float(request.get("reasoned_timeout_seconds") or 900.0)
        from adapters.sophia.sophia_r3_boundary import capture as _r3_capture, guarded_verify as _r3_verify
        _r3_required = "homs_context" in request or bool(request.get("zpd_guidance_path"))
        _r3_pin = _r3_capture(request, document_path, payload["text"], model) if _r3_required else None
        result = post_json(f"{base_url.rstrip('/')}/api/speak", payload, timeout=review_timeout)
        attempt_encounters = [result.get("encounter_id")]
        attempt_diagnostics = []

        def record_attempt(response, commentary, validation_result):
            conformity = response.get("article_conformity") or {}
            mandos = response.get("mandos_judgment") or {}
            articles = conformity.get("articles") or {}
            attempt_diagnostics.append({
                "attempt": len(attempt_diagnostics) + 1,
                "encounter_id": response.get("encounter_id"),
                "candidate_sha256": hashlib.sha256(
                    commentary.encode("utf-8")
                ).hexdigest(),
                "provider": response.get("reasoned_provider"),
                "provider_status": response.get("reasoned_provider_status"),
                "source": response.get("source"),
                "repair_applied": bool(response.get("repair_applied")),
                "repair_steps": response.get("repair_steps") or [],
                "mandos_passed": bool(mandos.get("passed")),
                "mandos_failed_checks": mandos.get("failed_checks") or [],
                "genesis_summary": conformity.get("summary") or {},
                "genesis_failed_articles": {
                    article_id: item
                    for article_id, item in articles.items()
                    if not item.get("passed")
                },
                "validation": validation_result,
            })

        candidate = str(result.get("response") or "").strip()
        valid_anchors = {row["span_id"] for row in spans} | {
            f"C{index}" for index in range(1, len(claim_maps) + 1)
        }

        validation = validate_reasoned_commentary(
            candidate,
            result,
            valid_anchors,
            _allowed_citation_keys(reference_audit, sources),
            allowed_dois,
            provider,
        )
        record_attempt(result, candidate, validation)
        failed_checks = sorted(key for key, passed in validation["checks"].items() if not passed)
        if failed_checks == ["document_anchor_present"]:
            payload["text"] = (
                prompt
                + "\n\nREQUIRED CORRECTION: Every bullet under Major revisions must contain at least one "
                + "verbatim bracketed anchor from this allowed set: "
                + ", ".join(f"[{anchor}]" for anchor in sorted(valid_anchors))
                + ". Return the complete report with those anchors included."
            )
            _r3_pin = _r3_capture(request, document_path, payload["text"], model) if _r3_required else None
            result = post_json(f"{base_url.rstrip('/')}/api/speak", payload, timeout=review_timeout)
            attempt_encounters.append(result.get("encounter_id"))
            candidate = str(result.get("response") or "").strip()
            validation = validate_reasoned_commentary(
                candidate,
                result,
                valid_anchors,
                _allowed_citation_keys(reference_audit, sources),
                allowed_dois,
                provider,
            )
            record_attempt(result, candidate, validation)
        # Preserve the actual final inference attempt, including rejected output.
        # This is quarantined evidence, never approved academic commentary.
        _r2_evidence = result.get("response_evidence")
        request["_r4_quarantined_inference"] = {
            "schema": "dio.sophia.quarantined-inference.v1",
            "authority": "UNAPPROVED_DIAGNOSTIC_EVIDENCE",
            "encounter_id": result.get("encounter_id"),
            "response_source": result.get("source"),
            "model": result.get("model"),
            "reasoned_provider": result.get("reasoned_provider"),
            "reasoned_provider_status": result.get("reasoned_provider_status"),
            "outbound_prompt_sha256": (_r3_pin or {}).get("outbound_prompt_sha256"),
            "processed_prompt_sha256": ((_r3_pin or {}).get("expected_sha256") or {}).get("prompt"),
            "response_sha256": hashlib.sha256(
                str(result.get("response") or "").encode("utf-8")
            ).hexdigest(),
            "response": str(result.get("response") or ""),
            "validated_candidate_sha256": hashlib.sha256(
                candidate.encode("utf-8")
            ).hexdigest(),
            "response_evidence": _r2_evidence,
        }
        if _r3_required:
            request["_r3_custody_receipt"] = _r3_verify(_r3_pin, request, result)
        if _r3_required and not request["_r3_custody_receipt"].get("passed", False):
            validation["passed"] = False
            validation.setdefault("checks", {})["r3_custody"] = False
        if not validation["passed"]:
            return {
                "status": "rejected",
                "source": result.get("source") or "unknown",
                "encounter_id": result.get("encounter_id"),
                "provider": result.get("reasoned_provider"),
                "provider_status": result.get("reasoned_provider_status"),
                "model": result.get("model"),
                "remote_processing": remote_processing,
                "characters_transmitted": min(len(text), 180_000),
                "candidate_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
                "attempt_count": len(attempt_encounters),
                "attempt_encounters": attempt_encounters,
                "attempt_diagnostics": attempt_diagnostics,
                "validation": validation,
                "commentary": "The reasoned reviewer returned commentary, but the grounded release checks rejected it. Human review remains required.",
            }
        return {
            "status": "completed",
            "source": result.get("source") or "sophia",
            "encounter_id": result.get("encounter_id"),
            "attempt_count": len(attempt_encounters),
            "attempt_encounters": attempt_encounters,
            "attempt_diagnostics": attempt_diagnostics,
            "provider": result.get("reasoned_provider"),
            "provider_status": result.get("reasoned_provider_status"),
            "model": result.get("model"),
            "remote_processing": remote_processing,
            "characters_transmitted": min(len(text), 180_000),
            "manuscript_truncated": len(text) > 180_000,
            "repair_applied": bool(result.get("repair_applied")),
            "repair_steps": result.get("repair_steps") or [],
            "mandos_judgment": result.get("mandos_judgment") or {},
            "article_conformity": result.get("article_conformity") or {},
            "validation": validation,
            "commentary": candidate,
        }
    except (OSError, TimeoutError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "status": "unavailable",
            "source": "fallback",
            "encounter_id": None,
            "provider": provider,
            "model": model,
            "remote_processing": remote_processing and reasoned_review_approved,
            "commentary": f"Sophia reasoned reviewer endpoint was unavailable: {type(error).__name__}. Human review remains required.",
            "failure_stage": "reviewer_request",
            "failure_type": type(error).__name__,
            "failure_reason": str(error)[:700],
        }


def markdown_literature_map(queries: list[str], sources: list[dict[str, Any]]) -> str:
    lines = ["# Sophia Literature Discovery Map", "", "## Search Questions", ""]
    lines.extend(f"- {query}" for query in queries)
    lines.extend(["", "## Candidate Literature", ""])
    if not sources:
        lines.append("No governed scholarly leads were retrieved. Narrow the query or supply a seed bibliography.")
    for index, source in enumerate(sources, 1):
        authors = ", ".join(source.get("authors") or []) or "Author metadata unavailable"
        lines.extend([
            f"### {index}. {source.get('title') or 'Untitled source lead'}",
            "",
            f"- Authors: {authors}",
            f"- Year: {source.get('year') or 'n.d.'}",
            f"- Index: {source.get('source') or 'unknown'}",
            f"- Relevance: {source.get('relevance_score', 'unscored')}",
            f"- URL/DOI: {source.get('url') or 'not supplied'}",
            f"- Retrieved: {source.get('retrieved_at') or 'unknown'}",
            "",
            str(source.get("summary") or "No abstract supplied.").strip(),
            "",
        ])
    lines.extend([
        "## Integrity Boundary",
        "",
        "These are discovery leads, not a ghostwritten literature review and not proof that each source supports the manuscript. Verify the full text and bibliographic metadata before citation.",
    ])
    return "\n".join(lines)


def markdown_reference_audit(audit: dict[str, Any]) -> str:
    lines = [
        "# Sophia Technical Reference Audit",
        "",
        f"Status: **{audit['status']}**",
        f"Actionable findings: **{audit['actionable_issue_count']}**",
        "",
        "## Cross-Checks",
        "",
        f"- In-text citations detected: {len(audit['in_text_citations'])}",
        f"- Reference entries detected: {len(audit['reference_entries'])}",
        f"- Cited but missing from reference list: {len(audit['missing_from_reference_list'])}",
        f"- Listed but not cited: {len(audit['reference_list_entries_not_cited'])}",
        f"- Duplicate entries: {len(audit['duplicate_entries'])}",
        f"- Duplicate DOIs: {len(audit['duplicate_dois'])}",
        "",
        "## Missing From Reference List",
        "",
    ]
    lines.extend(f"- {row['author']} ({row['year']})" for row in audit["missing_from_reference_list"])
    if not audit["missing_from_reference_list"]:
        lines.append("- None detected.")
    lines.extend(["", "## Listed But Not Cited", ""])
    lines.extend(f"- {row['entry']}" for row in audit["reference_list_entries_not_cited"])
    if not audit["reference_list_entries_not_cited"]:
        lines.append("- None detected.")
    lines.extend(["", "## Entry-Level Findings", ""])
    for row in audit["reference_entries"]:
        issues = list(row["issues"]) + [item["type"] for item in row["style_check"]["errors"]]
        lines.append(f"- Reference {row['index']}: {', '.join(issues) if issues else 'no deterministic issue detected'}")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in audit["limits"])
    return "\n".join(lines)


def markdown_claim_ledger(claim_maps: list[dict[str, Any]]) -> str:
    lines = ["# Sophia Claim-to-Source Ledger", ""]
    for index, item in enumerate(claim_maps, 1):
        claim = item["claim_record"]
        mapping = item["source_map"]
        lines.extend([
            f"## Claim {index}",
            "",
            claim["claim"],
            "",
            f"- Type: {claim.get('claim_type')}",
            f"- Evidence risk: {claim.get('evidence_risk')}",
            f"- Evidence standard: {claim.get('evidence_standard')}",
            "",
        ])
        for source in mapping.get("results") or []:
            lines.extend([
                f"- **{source.get('support_label')}**: {source.get('source_name')}",
                f"  - Confidence: {source.get('confidence')}; rank: {source.get('ranking_score')}",
                f"  - Visible span: {source.get('exact_span') or 'not available'}",
                f"  - Citation lead: {source.get('apa_candidate') or source.get('url') or 'metadata incomplete'}",
                f"  - Limitation: {source.get('entailment_status') or 'verify full text'}",
            ])
        if not mapping.get("results"):
            lines.append("- No candidate source mapping available.")
        lines.append("")
    lines.extend([
        "## Release Rule",
        "",
        "A candidate abstract or visible span is a verification lead. The author or reviewer must inspect the full source before treating it as support.",
    ])
    return "\n".join(lines)


def bind_sophia_backend(sophia_root: Path) -> None:
    """Bind authentic Sophia services without replacing DIO's backend."""
    import importlib

    from adapters.sophia.canonical_sources import ORGAN_ROOT
    if Path(sophia_root).resolve() != ORGAN_ROOT:
        raise FileNotFoundError("REFUSE: Sophia source root outside canonical DIO")
    arda_root = (ORGAN_ROOT / "arda_os").resolve()
    backend_root = arda_root / "backend"
    services = backend_root / "services"

    if not backend_root.is_dir():
        raise FileNotFoundError(
            f"REFUSE: Sophia backend directory missing: {backend_root}"
        )

    if str(arda_root) not in sys.path:
        sys.path.insert(0, str(arda_root))

    backend = importlib.import_module("backend")

    required = (
        "academic_retrieval",
        "sophia_academic_claim_tools",
        "sophia_source_support",
    )

    missing = [
        name for name in required
        if not (services / f"{name}.py").is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"REFUSE: missing Sophia services in {services}: {missing}"
        )

    if str(arda_root) not in sys.path:
        sys.path.insert(0, str(arda_root))

    if str(backend_root) not in backend.__path__:
        backend.__path__.append(str(backend_root))

    # ``backend.services`` may already be imported from an unrelated package.
    # Extend that loaded package explicitly so canonical Sophia modules remain
    # discoverable without replacing the existing package object.
    services_package = importlib.import_module("backend.services")
    services_path = str(services.resolve())
    if services_path not in services_package.__path__:
        services_package.__path__.append(services_path)


def run_review(request: dict[str, Any], request_path: Path, out_root: Path, base_url: str, sophia_root: Path) -> Path:
    job_id = str(request.get("job_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", job_id):
        raise ValueError("request.job_id must be a safe 3-101 character identifier")
    raw_document_path = Path(str(request.get("document_path") or "")).expanduser()
    document_path = raw_document_path if raw_document_path.is_absolute() else (request_path.parent / raw_document_path)
    document_path = document_path.resolve()
    if not document_path.is_file():
        raise FileNotFoundError(f"Manuscript not found: {document_path}")
    title = str(request.get("title") or document_path.stem).strip()
    text, parser = extract_document_text(document_path)
    if len(text.split()) < 40:
        raise ValueError("Manuscript has too little readable text for an academic review.")

    bind_sophia_backend(sophia_root)
    from backend.services.academic_retrieval import get_academic_retrieval
    from backend.services.sophia_academic_claim_tools import classify_claim_type
    from backend.services.sophia_source_support import citation_check, map_claim_to_sources

    body_text, reference_text = split_reference_section(text)
    queries = [str(item).strip() for item in (request.get("literature_queries") or []) if str(item).strip()][:4]
    if not queries:
        question = str(request.get("research_question") or title).strip()
        queries = [question]
    external_retrieval = bool(request.get("external_retrieval", False))
    retrieval_records = []
    source_by_identity: dict[str, dict[str, Any]] = {}
    if external_retrieval:
        engine = get_academic_retrieval(evidence_dir=sophia_root / "evidence")
        for query in queries:
            result = engine.retrieve(query, include_local=False).to_dict()
            retrieval_records.append(result)
            for source in result.get("fragments") or []:
                identity = str(source.get("url") or source.get("content_hash") or source.get("title") or "").lower()
                if identity:
                    source_by_identity.setdefault(identity, source)
    sources = list(source_by_identity.values())
    reference_audit = audit_references(body_text, reference_text, citation_check)
    claims = select_claims(body_text, classify_claim_type)
    claim_maps = [
        {
            "claim_record": claim,
            "source_map": map_claim_to_sources(claim["claim"], sources, limit=5, enrich_metadata=False),
        }
        for claim in claims[:8]
    ]
    commentary = reviewer_commentary(
        base_url,
        request,
        title,
        document_path,
        text,
        parser,
        reference_audit,
        claim_maps,
        sources,
    )

    job_dir = (out_root / job_id).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    generated_names = {
        "R4_QUARANTINED_INFERENCE.json",
        "LITERATURE_MAP.json", "LITERATURE_MAP.md", "REFERENCE_AUDIT.json", "REFERENCE_AUDIT.md",
        "CLAIM_SOURCE_LEDGER.json", "CLAIM_SOURCE_LEDGER.md", "REVIEWER_COMMENTARY.json",
        "REVIEWER_COMMENTARY.md", "HUMAN_APPROVAL.md", "SOPHIA_REVIEW_RECEIPT.json",
        f"{job_id}_SOPHIA_REVIEW_PACK.zip",
    }
    for name in generated_names:
        candidate = job_dir / name
        if candidate.is_file():
            candidate.unlink()
    literature_payload = {
        "schema": "dio.sophia_literature_map.v1",
        "queries": queries,
        "external_retrieval_approved": external_retrieval,
        "retrieval_runs": retrieval_records,
        "deduplicated_sources": sources,
    }
    claim_payload = {"schema": "dio.sophia_claim_source_ledger.v1", "claims": claim_maps}

    if request.get("_zpd_binding_receipt") is not None:
        write_json(
            job_dir / "ZPD_BINDING_RECEIPT.json",
            request["_zpd_binding_receipt"],
        )

    if request.get("_r4_quarantined_inference") is not None:
        quarantine_path = job_dir / "R4_QUARANTINED_INFERENCE.json"
        write_json(quarantine_path, request["_r4_quarantined_inference"])
        quarantine_path.chmod(0o600)

    if request.get("_r3_custody_receipt") is not None:
        write_json(job_dir / "R3_CUSTODY_RECEIPT.json", request["_r3_custody_receipt"])
    write_json(job_dir / "LITERATURE_MAP.json", literature_payload)
    write_text(job_dir / "LITERATURE_MAP.md", markdown_literature_map(queries, sources))
    write_json(job_dir / "REFERENCE_AUDIT.json", reference_audit)
    write_text(job_dir / "REFERENCE_AUDIT.md", markdown_reference_audit(reference_audit))
    write_json(job_dir / "CLAIM_SOURCE_LEDGER.json", claim_payload)
    write_text(job_dir / "CLAIM_SOURCE_LEDGER.md", markdown_claim_ledger(claim_maps))
    write_json(job_dir / "REVIEWER_COMMENTARY.json", commentary)
    write_text(
        job_dir / "REVIEWER_COMMENTARY.md",
        "# Sophia Reviewer Commentary\n\n"
        f"Status: **{commentary['status']}**\n\n"
        f"{commentary['commentary']}\n\n"
        "## Authorship Boundary\n\nThis commentary diagnoses and prioritizes revision. The author owns all final wording, interpretation, and submission decisions.",
    )
    write_text(
        job_dir / "HUMAN_APPROVAL.md",
        "# Sophia Human Approval Gate\n\n"
        f"Job: `{job_id}`\n\n"
        "- [ ] Confirm the manuscript owner authorized this review.\n"
        "- [ ] Confirm the manuscript owner authorized the configured reasoned-review processing.\n"
        "- [ ] Verify every retained citation against the full source.\n"
        "- [ ] Resolve cited-but-missing and listed-but-uncited entries.\n"
        "- [ ] Review high-risk claims and their evidence standard.\n"
        "- [ ] Confirm reviewer commentary is diagnostic, not substituted authorship.\n"
        "- [ ] Approve the final pack for delivery.\n",
    )
    generated = sorted(path for path in job_dir.iterdir() if path.is_file())
    receipt = {
        "schema": "dio.sophia_review_receipt.v1",
        "job_id": job_id,
        "created_at": utc_now(),
        "status": "needs_human_review",
        "source": {
            "name": document_path.name,
            "sha256": sha256_file(document_path),
            "parser": parser,
            "word_count": len(text.split()),
            "full_text_copied_to_pack": False,
        },
        "metrics": {
            "literature_queries": len(queries),
            "candidate_sources": len(sources),
            "claims_reviewed": len(claim_maps),
            "reference_entries": len(reference_audit["reference_entries"]),
            "reference_findings": reference_audit["actionable_issue_count"],
            "reviewer_commentary_status": commentary["status"],
            "reviewer_provider": commentary.get("provider"),
            "reviewer_model": commentary.get("model"),
            "reviewer_grounding_passed": bool((commentary.get("validation") or {}).get("passed")),
        },
        "reasoned_processing": {
            "approved": bool(
                request.get(
                    "reasoned_review_approved",
                    request.get("gemini_review_approved", False),
                )
            ),
            "provider": commentary.get("provider"),
            "model": commentary.get("model"),
            "remote_processing": bool(commentary.get("remote_processing", False)),
            "characters_transmitted": commentary.get("characters_transmitted", 0),
        },
        "outputs": [{"name": path.name, "sha256": sha256_file(path)} for path in generated],
        "delivery_released": False,
    }
    write_json(job_dir / "SOPHIA_REVIEW_RECEIPT.json", receipt)
    archive_path = job_dir / f"{job_id}_SOPHIA_REVIEW_PACK.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(job_dir.iterdir()):
            if (
                path.is_file()
                and path != archive_path
                and path.name in generated_names
                and path.name != "R4_QUARANTINED_INFERENCE.json"
            ):
                archive.write(path, arcname=path.name)
    return job_dir
