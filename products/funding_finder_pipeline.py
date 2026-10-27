"""Evidence-dated funding opportunity screening, without award/eligibility claims."""
from __future__ import annotations

import base64
import csv
import hashlib
import http.client
import ipaddress
import json
import math
import re
import shutil
import socket
import ssl
import zipfile
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from adapters.format_core.renderer import render_semantic_asset

MAX_SOURCE_BYTES = 2 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_INSTRUCTION = re.compile(r"ignore (?:all |previous |prior )*(?:instructions|rules)|(?:system|developer)\s*(?:prompt|message)|declare .*eligible|<script\b[^>]*>.*(?:credential|password)", re.I | re.S)


def _json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _day(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("A source-dated ISO date is required")
    try:
        return date.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def _id(value: Any) -> str:
    value = _nonempty(value, "identifier")
    if not _ID.fullmatch(value):
        raise ValueError("Identifiers must be safe and at most 64 characters")
    return value


def _public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_reserved or address.is_multicast:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped or address.sixtofour or address.teredo or address in ipaddress.ip_network("64:ff9b::/96"):
            return False
    return True


def _public_url(url: str, *, resolve: bool) -> tuple[str, list[str]]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("Official source URLs require HTTPS, port 443 and no credentials or fragment")
    hostname = parsed.hostname.rstrip(".").casefold()
    if "." not in hostname or hostname.endswith((".local", ".internal", ".localhost", ".test", ".invalid")):
        raise ValueError("Private/internal source URLs are forbidden")
    try:
        ipaddress.ip_address(hostname)
        if not _public_address(hostname):
            raise ValueError("Non-public source IP addresses are forbidden")
    except ValueError as exc:
        if "forbidden" in str(exc):
            raise
    addresses = []
    if resolve:
        try:
            addresses = sorted({row[4][0] for row in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)})
        except OSError as exc:
            raise ValueError("Official source DNS resolution failed") from exc
        if not addresses or any(not _public_address(ip) for ip in addresses):
            raise ValueError("Official source resolves to a non-public address")
    return hostname, addresses


def _fetch_official(url: str, allowlist: list[str]) -> dict[str, Any]:
    if url not in allowlist:
        raise ValueError("Public fetch URL must be explicitly present in official_url_allowlist")
    hostname, addresses = _public_url(url, resolve=True)
    # Connect to the validated address directly. TLS still verifies the official
    # hostname, preventing a second DNS resolution/rebinding between check/use.
    connection = http.client.HTTPSConnection(hostname, timeout=15, context=ssl.create_default_context())
    connection.sock = connection._context.wrap_socket(socket.create_connection((addresses[0], 443), timeout=15), server_hostname=hostname)
    parsed = urlsplit(url)
    try:
        connection.request("GET", (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""), headers={"User-Agent": "DIO-FundingFinder-source-review/1.0", "Accept": "text/html,text/plain", "Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Official source returned HTTP {response.status}; redirects are not followed")
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
            raise ValueError("Only bounded public HTML/plain-text opportunity pages may be fetched")
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("Official source exceeds the bounded 2 MiB fetch limit")
        return {"raw": raw, "retrieved_at": datetime.now(timezone.utc).isoformat(), "content_type": content_type,
                "transport": "HTTPS public-IP-pinned GET; no redirects", "http_status": response.status,
                "last_modified": response.getheader("Last-Modified"), "resolved_ip": addresses[0]}
    finally:
        connection.close()


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.words: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.words.append(data)


def _normal(text: str) -> str:
    return " ".join(text.split())


def _visible(raw: bytes, content_type: str) -> str:
    text = raw.decode("utf-8-sig", errors="replace")
    if "html" in content_type or re.match(r"\s*<(?:!doctype|html)", text, re.I):
        page = _PageText()
        page.feed(text)
        text = " ".join(page.words)
    return _normal(text)


def _quoted(text: str, quote: Any, value: Any = None) -> tuple[bool, str]:
    if not isinstance(quote, str) or not quote.strip():
        return False, "Exact supporting quotation missing"
    quote = _normal(quote)
    if _INSTRUCTION.search(quote):
        return False, "Instruction-like source quotation quarantined"
    if quote not in text:
        return False, "Quotation not present in captured source"
    if value is not None:
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, bool):
                return False, "Boolean interpretations need reviewer confirmation"
            if isinstance(item, (int, float)):
                numbers = re.findall(r"(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?!\d)", quote)
                if not math.isfinite(item) or not any(float(n.replace(",", "")) == float(item) for n in numbers):
                    return False, "Structured numeric value absent from source quotation"
            elif _normal(str(item)).casefold() not in quote.casefold():
                return False, "Structured value absent from source quotation"
            elif re.search(r"\b(?:not|no|never|excluding)\s+(?:a |an |in )?" + re.escape(str(item)) + r"\b", quote, re.I):
                return False, "Potential negation requires reviewer interpretation"
    return True, "Exact quotation captured; interpretation still requires funder/reviewer confirmation"


def _comparison(operator: str, actual: Any, expected: Any) -> str:
    normal = lambda value: _normal(str(value)).casefold()
    if operator in {"equals", "not_equals"}:
        matched = normal(actual) == normal(expected)
        if operator == "not_equals":
            matched = not matched
    elif operator == "one_of" and isinstance(expected, list):
        matched = normal(actual) in [normal(x) for x in expected]
    elif operator in {"maximum", "minimum"} and isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and not isinstance(actual, bool) and not isinstance(expected, bool):
        matched = actual <= expected if operator == "maximum" else actual >= expected
    else:
        return "unknown"
    return "met" if matched else "mismatch"


def _date_evidence(text: str, record: dict[str, Any]) -> tuple[bool, str]:
    supported, reason = _quoted(text, record.get("quote"))
    if not supported or not record.get("date"):
        return False, reason
    try:
        stated = _day(record["date"])
    except (ValueError, TypeError):
        return False, "Invalid stated calendar date"
    # Calendar text is normalised only through unambiguous date spellings.
    # Ambiguous numeric month/day dates stay unknown.
    spellings = {stated.isoformat(), stated.strftime("%d %B %Y").lstrip("0"), stated.strftime("%B %d, %Y").replace(" 0", " ")}
    quote = _normal(record["quote"]).casefold()
    if not any(re.search(r"(?<!\w)" + re.escape(s.casefold()) + r"(?!\w)", quote) for s in spellings):
        return False, "Calendar date not established from exact source quotation"
    return True, "Calendar date anchored to captured source quotation"


def _prepare(packet: Mapping[str, Any], as_of: date, fetch_public: bool) -> dict[str, Any]:
    applicant = packet.get("applicant") or {}
    name = _nonempty(applicant.get("name"), "applicant.name")
    title = str(packet.get("title") or f"Funding shortlist for {name}")
    sources, facts, flags = {}, {}, []
    for row in applicant.get("sources") or []:
        sid = _id(row.get("source_id"))
        if sid in sources:
            raise ValueError("Duplicate applicant source_id")
        text = _nonempty(row.get("text"), "applicant source.text")
        sources[sid] = {"source_id": sid, "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    for row in applicant.get("facts") or []:
        field = _nonempty(row.get("field"), "fact.field")
        if field in facts:
            raise ValueError("Duplicate applicant fact field; reconcile contradictory facts first")
        source = sources.get(row.get("source_id"))
        supported, reason = _quoted(_normal(source["text"]) if source else "", row.get("quote"), row.get("value"))
        supported = supported and row.get("value") is not None
        facts[field] = {**row, "supported": bool(source) and supported, "reason": reason}
    opportunities = packet.get("opportunities")
    if not isinstance(opportunities, list) or not 1 <= len(opportunities) <= 25:
        raise ValueError("Supply 1 to 25 official opportunity records")
    seen, prepared, raw_sources = set(), [], []
    for opportunity in opportunities:
        oid = _id(opportunity.get("opportunity_id"))
        if oid in seen:
            raise ValueError("Duplicate opportunity_id")
        seen.add(oid)
        url = _nonempty(opportunity.get("official_url"), "official_url")
        _public_url(url, resolve=False)
        supplied = opportunity.get("source") or {}
        if fetch_public:
            snapshot = _fetch_official(url, packet.get("official_url_allowlist") or [])
        else:
            content = supplied.get("content")
            if isinstance(content, str):
                raw = content.encode("utf-8")
            elif supplied.get("content_base64"):
                raw = base64.b64decode(supplied["content_base64"], validate=True)
            else:
                raise ValueError("Supply source.content or explicitly enable public fetching")
            snapshot = {"raw": raw, "retrieved_at": supplied.get("retrieved_at"), "content_type": supplied.get("content_type", "text/plain"), "transport": "supplied_snapshot_not_independently_fetched"}
        raw = snapshot.pop("raw")
        if not raw or len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("Opportunity source must be nonempty and no larger than 2 MiB")
        retrieved = _day(snapshot["retrieved_at"])
        if not isinstance(snapshot["retrieved_at"], str):
            snapshot["retrieved_at"] = snapshot["retrieved_at"].isoformat()
        if retrieved > as_of:
            raise ValueError("Source retrieval date cannot be later than as_of")
        digest = hashlib.sha256(raw).hexdigest()
        if supplied.get("sha256") and supplied["sha256"] != digest:
            raise ValueError("Opportunity raw-byte SHA256 mismatch")
        text = _visible(raw, snapshot["content_type"])
        if _INSTRUCTION.search(text):
            flags.append({"code": "source_instruction_quarantined", "opportunity_id": oid, "detail": "Source contains instruction-like material; instruction-bearing evidence fields are held."})
        if (as_of - retrieved).days > 30:
            flags.append({"code": "source_refresh_required", "opportunity_id": oid, "detail": "Source snapshot is older than 30 days; recheck programme availability and rules."})
        source_row = {"opportunity_id": oid, "url": url, "sha256": digest, "bytes": len(raw), "raw_path": f"sources/{oid}.raw", "text_path": f"sources/{oid}.txt", "synthetic": bool(supplied.get("synthetic")), **snapshot}
        raw_sources.append({"record": source_row, "raw": raw, "text": text})
        criteria, counts = [], {"met": 0, "mismatch": 0, "unknown": 0}
        criterion_ids = set()
        for rule in opportunity.get("criteria") or []:
            cid = _id(rule.get("criterion_id"))
            if cid in criterion_ids:
                raise ValueError("Duplicate criterion_id")
            criterion_ids.add(cid)
            support, why = _quoted(text, rule.get("quote"), rule.get("expected"))
            support = support and rule.get("expected") is not None
            fact = facts.get(rule.get("field"))
            state = _comparison(rule.get("operator"), fact.get("value"), rule.get("expected")) if support and fact and fact["supported"] else "unknown"
            weight = rule.get("weight", 1)
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 < weight <= 100:
                raise ValueError("Criterion weights must be finite and between 0 and 100")
            counts[state] += 1
            criteria.append({"criterion_id": cid, "field": rule.get("field"), "operator": rule.get("operator"), "expected": rule.get("expected"), "state": state, "weight": weight,
                             "funder_quote": rule.get("quote"), "applicant_evidence": fact,
                             "reason": why if not support else "Applicant evidence missing/unsupported" if not fact or not fact["supported"] else "Explicit comparison on supplied records; confirm full funder rules"})
        deadline = opportunity.get("deadline") or {}
        supported, why = _date_evidence(text, deadline)
        timing, deadline_date = "unknown", None
        if deadline.get("date") and supported:
            try:
                deadline_date = _day(deadline["date"])
                timing = "expired" if deadline_date < as_of else "deadline_today_confirm_timezone" if deadline_date == as_of else "within_stated_deadline"
            except (ValueError, TypeError):
                pass
        rolling = opportunity.get("rolling") or {}
        if not deadline_date and rolling.get("value") is True:
            supported, why = _quoted(text, rolling.get("quote"))
            negated = re.search(r"\b(?:not|never|closed|suspended|paused|no longer|isn't|aren't)\b", str(rolling.get("quote") or ""), re.I)
            if supported and not negated and re.search(r"no deadlines|apply (?:at )?any ?time|rolling|open to applications", rolling["quote"], re.I):
                timing = "rolling_stated_confirm_current_availability"
        opens = opportunity.get("opens") or {}
        opening_supported, _ = _date_evidence(text, opens)
        if opens.get("date") and opening_supported and _day(opens["date"]) > as_of:
            timing = "not_yet_open"
        if not criteria or counts["unknown"] or timing in {"unknown", "deadline_today_confirm_timezone"} or (as_of - retrieved).days > 30:
            fit = "unknown_review_required"
        else:
            fit = "appears_aligned_on_supplied_record"
        if counts["mismatch"]:
            fit = "mismatch_on_supplied_record"
        if timing in {"expired", "not_yet_open"}:
            fit = "closed_on_as_of_date"
        funding = opportunity.get("funding") or {}
        fund_support, fund_reason = _quoted(text, funding.get("quote"), [funding.get("minimum"), funding.get("maximum"), funding.get("currency")]) if funding else (False, "Funding bounds not supplied")
        if funding and (not fund_support or not all(isinstance(funding.get(k), (int, float)) and not isinstance(funding.get(k), bool) and math.isfinite(funding[k]) for k in ("minimum", "maximum")) or funding.get("minimum", 0) < 0 or funding.get("maximum", 0) < funding.get("minimum", 0)):
            fund_support = False
        funds = {**funding, "source_supported": fund_support, "reason": fund_reason}
        descriptors = {}
        for key, value_key in (("purpose", "text"), ("stage", "value")):
            supplied_descriptor = opportunity.get(key) or {}
            descriptor_support, reason = _quoted(text, supplied_descriptor.get("quote"), supplied_descriptor.get(value_key)) if isinstance(supplied_descriptor, dict) else (False, "Provide an exact source quotation and value")
            descriptors[key] = {**supplied_descriptor, "source_supported": descriptor_support and supplied_descriptor.get(value_key) is not None, "reason": reason} if isinstance(supplied_descriptor, dict) else {"source_supported": False, "reason": reason}
        documents = []
        for item in opportunity.get("required_documents") or []:
            support, reason = _quoted(text, item.get("quote"), item.get("name"))
            documents.append({**item, "source_supported": support, "reason": reason})
        points = {"met": 2, "mismatch": -4, "unknown": -1}
        timing_penalty = -1000 if fit == "closed_on_as_of_date" else -10 if timing == "unknown" else 0
        score = sum(points[r["state"]] * r["weight"] for r in criteria) + timing_penalty
        actions = [{"kind": "verify_official_rules", "action": "Recheck the official source and full eligibility rules before preparing an application.", "url": url}]
        for rule in criteria:
            if rule["state"] != "met":
                actions.append({"kind": "resolve_eligibility", "criterion_id": rule["criterion_id"], "action": f"Resolve {rule['field']}: {rule['state']}; obtain applicant evidence or ask the funder for clarification."})
        for item in documents:
            actions.append({"kind": "prepare_document" if item["source_supported"] else "confirm_document_requirement", "action": item.get("name") if item["source_supported"] else "Ask the funder to confirm the document requirement; unsupported supplied wording is held in the reviewer matrix.", "source_quote": item.get("quote") if item["source_supported"] else None})
        if timing in {"unknown", "expired", "not_yet_open", "deadline_today_confirm_timezone"}:
            actions.append({"kind": "confirm_timing", "action": "Confirm the current round, deadline, timezone and next opening date. Do not submit on inferred timing."})
        prepared.append({"opportunity_id": oid, "title": _nonempty(opportunity.get("title"), "opportunity.title"), "funder": _nonempty(opportunity.get("funder"), "opportunity.funder"), "official_url": url,
                         "retrieved_at": snapshot["retrieved_at"], "source_sha256": digest, "fit_state": fit, "timing_state": timing, "deadline": deadline_date.isoformat() if deadline_date else None,
                         "criteria": criteria, "criteria_counts": counts, "funding": funds, "required_documents": documents, "next_actions": actions, "score": score,
                         "purpose": descriptors["purpose"], "stage": descriptors["stage"]})
    category = {"appears_aligned_on_supplied_record": 0, "unknown_review_required": 1, "mismatch_on_supplied_record": 2, "closed_on_as_of_date": 3}
    prepared.sort(key=lambda row: (category[row["fit_state"]], -row["score"], row["opportunity_id"]))
    for rank, row in enumerate(prepared, 1):
        row["rank"] = rank
    flags.append({"code": "funder_confirmation_required", "detail": "Source presence and numeric/string comparisons do not certify eligibility, completeness, programme availability or award likelihood."})
    return {"title": title, "applicant_name": name, "as_of": as_of.isoformat(), "facts": list(facts.values()), "applicant_sources": list(sources.values()), "shortlist": prepared, "raw_sources": raw_sources, "review_flags": flags}


def _semantic(model: dict[str, Any]) -> dict[str, Any]:
    blocks = [{"type": "title", "text": model["title"]},
              {"type": "paragraph", "text": f"Applicant: {model['applicant_name']}. Screening as of {model['as_of']}. Controlled opportunity research; eligibility is not certified and no award is guaranteed."},
              {"type": "heading", "level": 1, "text": "Ranked opportunity shortlist"},
              {"type": "table", "title": "Fit and timing on supplied records", "headers": ["Rank", "Opportunity", "Fit", "Timing", "Score"],
               "rows": [[str(r["rank"]), r["title"], r["fit_state"].replace("_", " "), r["timing_state"].replace("_", " "), str(r["score"])] for r in model["shortlist"]]},
              {"type": "paragraph", "text": "Ranking sorts apparent alignment, unresolved eligibility, mismatches and closed/not-yet-open calls in that order. Within a class: met +2, mismatch -4 and unknown -1, multiplied by each explicit criterion weight; unknown timing -10, closed timing -1000. Scores compare the supplied records; they are not funding probabilities."}]
    for row in model["shortlist"]:
        blocks.extend([{"type": "heading", "level": 1, "text": f"{row['rank']}. {row['title']}"},
                       {"type": "paragraph", "text": f"Funder: {row['funder']}. Official URL declared for this record: {row['official_url']}. Source captured {row['retrieved_at']}; SHA256 {row['source_sha256']}."},
                       {"type": "paragraph", "text": f"Fit: {row['fit_state']}. Timing: {row['timing_state']}. Deadline: {row['deadline'] or 'not established from captured source'}."}])
        if row["funding"]["source_supported"]:
            funding = row["funding"]
            blocks.append({"type": "paragraph", "text": f"Source-stated funding bounds: {funding['minimum']}–{funding['maximum']} {funding.get('currency', 'currency not established')}. Evidence: {funding['quote']}"})
        else:
            blocks.append({"type": "paragraph", "text": "Funding bounds are not established from supported captured evidence; confirm with the funder."})
        for key, value_key in (("purpose", "text"), ("stage", "value")):
            descriptor = row[key]
            if descriptor["source_supported"]:
                blocks.append({"type": "paragraph", "text": f"Source-stated {key}: {descriptor[value_key]}. Evidence: {descriptor['quote']}"})
        for rule in row["criteria"]:
            fact = rule["applicant_evidence"]
            detail = f"{rule['criterion_id']}: {rule['field']} — {rule['state']}. {rule['reason']}."
            if rule["state"] != "unknown":
                detail += f" Funder evidence: {rule['funder_quote']} Applicant evidence [{fact['source_id']}]: {fact['quote']}"
            blocks.append({"type": "paragraph", "text": detail})
        blocks.append({"type": "bullet_list", "items": [f"{a['kind'].replace('_', ' ')}: {a['action']}" for a in row["next_actions"]]})
    blocks.extend([{"type": "heading", "level": 1, "text": "Reviewer and source limitations"},
                   {"type": "bullet_list", "items": [f["detail"] for f in model["review_flags"]]}])
    return {"schema": "dio.semantic_content.v1", "object_id": "FUNDING-" + hashlib.sha256(json.dumps(model["shortlist"], sort_keys=True).encode()).hexdigest()[:12],
            "version": "1.0", "title": model["title"], "source_language": "English", "context": {"product": "fundingfinder", "artifact_type": "funding_shortlist", "audience": model["applicant_name"]},
            "blocks": [{"block_id": f"B{i:04}", **block} for i, block in enumerate(blocks, 1)]}


def build_funding_shortlist(packet: Mapping[str, Any], output_dir: str | Path, *, as_of: str | date | None = None, fetch_public: bool = False, render_pdf: bool = True) -> dict[str, Any]:
    """Screen explicit opportunity criteria against source-quoted applicant facts.

    No browsing occurs unless fetch_public=True and every fetched official_url
    is declared in packet.official_url_allowlist. Redirects and non-public IPs
    are refused. Supply snapshots for deterministic/offline customer work.
    """
    as_of_day = _day(as_of) if as_of is not None else datetime.now(timezone.utc).date()
    out = Path(output_dir).expanduser().resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("output_dir must be empty to avoid stale customer artifacts")
    model = _prepare(packet, as_of_day, fetch_public)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sources").mkdir()
    for source in model["raw_sources"]:
        (out / source["record"]["raw_path"]).write_bytes(source["raw"])
        (out / source["record"]["text_path"]).write_text(source["text"], encoding="utf-8")
    _json(out / "source_register.json", {"opportunities": [s["record"] for s in model["raw_sources"]], "applicant_sources": model["applicant_sources"], "applicant_facts": model["facts"]})
    _json(out / "eligibility_matrix.json", {"as_of": model["as_of"], "opportunities": model["shortlist"], "review_flags": model["review_flags"]})
    _json(out / "next_actions.json", {"opportunities": [{"opportunity_id": r["opportunity_id"], "actions": r["next_actions"]} for r in model["shortlist"]], "actions_executed": False})
    semantic = _semantic(model)
    _json(out / "shortlist_semantic.json", semantic)
    channels = ["docx", "html"]
    if render_pdf and (shutil.which("libreoffice") or shutil.which("soffice")):
        channels.append("pdf")
    receipt = render_semantic_asset(semantic, out / "report", style_profile="minimal_print", source_root=out, channels=channels, release_mode=False)
    deliverables = {f"shortlist_{r['channel']}": f"report/{r['path']}" for r in receipt["outputs"]}
    fields = ["rank", "opportunity_id", "title", "funder", "official_url", "retrieved_at", "deadline", "fit_state", "timing_state", "score"]
    with (out / "shortlist.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        # Spreadsheet formula prefixes are neutralised in customer-supplied text.
        for row in model["shortlist"]:
            writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for k, v in row.items() if k in fields})
    deliverables["shortlist_csv"] = "shortlist.csv"
    result = {"schema": "dio.funding_finder_shortlist.v1", "status": "review_candidate", "as_of": model["as_of"], "output_dir": str(out), "applicant": model["applicant_name"],
              "shortlist": model["shortlist"], "deliverables": deliverables, "review_flags": model["review_flags"],
              "processing": {"public_fetch_enabled": fetch_public, "renderer": "DIO Format Core", "factual_inference": "explicit comparisons of quoted supplied records"},
              "release": {"eligibility_certified": False, "award_guaranteed": False, "application_submitted": False, "externally_sent": False, "canon_promoted": False}, "qa": receipt["qa"]}
    result["artifacts"] = [{"path": str(p.relative_to(out)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in sorted(out.rglob("*")) if p.is_file()]
    _json(out / "package_manifest.json", result)
    with zipfile.ZipFile(out / "controlled_funding_review.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path.name != "controlled_funding_review.zip":
                archive.write(path, path.relative_to(out))
    return result
