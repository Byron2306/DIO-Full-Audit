"""Source-bound report, pitch and article production through DIO Format Core.

This is a local drafting service. Source attribution proves where words came
from, not their truth. It never grants expert approval or publication authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import textwrap
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

from adapters.document_studio.conversion import execute_conversion
from adapters.format_core.renderer import render_semantic_asset


_INSTRUCTION = re.compile(
    r"ignore (?:all |previous |prior )*(?:instructions|rules)|(?:system|developer)\s*(?:prompt|message)"
    r"|declare .*approved|(?:send|upload|exfiltrate) .*credentials|<script\b", re.I)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def _chunks(text: str, maximum: int = 620) -> list[str]:
    # Render long evidence across slides without silently dropping its qualifiers.
    return textwrap.wrap(text, width=maximum, break_long_words=True, break_on_hyphens=False) or [text]


def _metric_context_supported(row: Mapping[str, Any], quote: str) -> bool:
    # Do not borrow a label, unit or reporting period from another measurement
    # across a sentence or semicolon. Ambiguous compound measures need review.
    return any(_single_metric_context_supported(row, clause)
               for clause in re.split(r'(?<=[.!?;])\s+|\n+', quote)
               if not re.search(r"\b(?:not|never|no|unmeasured|unknown|didn't|wasn't)\b", clause, re.I))


def _single_metric_context_supported(row: Mapping[str, Any], quote: str) -> bool:
    """Require the metric's label, adjacent unit and period in its own quote.

    Finding the same number somewhere in prose cannot bind a financial label to
    an appointment count or move a measurement to another reporting period.
    """
    metric, unit, period = (_text(row.get(k), k) for k in ('metric', 'unit', 'period'))
    normalize = lambda value: ' '.join(value.casefold().split())
    if normalize(period) not in normalize(quote):
        return False
    without_period = re.sub(r'(?<!\w)' + re.escape(normalize(period)) + r'(?!\w)', ' ', normalize(quote))
    measurements = re.findall(r'(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?![\d.])', without_period)
    if len(measurements) != 1 or float(measurements[0].replace(',', '')) != float(row['value']):
        return False
    if re.search(r'\b(?:and|but|whereas|while)\b', quote, re.I):
        return False
    label_pattern = r'\b' + r'\s+'.join(re.escape(part) for part in metric.split()) + r'\b'
    labels = list(re.finditer(label_pattern, quote, re.I))
    for number in re.finditer(r'(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?![\d.])', quote):
        if float(number[0].replace(',', '')) != float(row['value']):
            continue
        related = False
        for label in labels:
            between = quote[label.end():number.start()] if label.end() <= number.start() else quote[number.end():label.start()] if number.end() <= label.start() else ''
            if len(between) <= 80 and not re.search(r'\d', between):
                related = True
                break
        prefix, suffix = quote[max(0, number.start()-12):number.start()], quote[number.end():number.end()+40]
        unit_ok = bool(re.match(r'\s*' + re.escape(unit) + r'\b', suffix, re.I))
        if unit.casefold() == 'zar':
            unit_ok = unit_ok or bool(re.search(r'\b(?:ZAR|R)\s*$', prefix, re.I))
        if unit.casefold() in {'percent', '%'}:
            unit_ok = bool(re.match(r'\s*(?:%|percent\b)', suffix, re.I))
        if related and unit_ok:
            return True
    return False


def _prepare(packet: Mapping[str, Any]) -> dict[str, Any]:
    title = _text(packet.get("title"), "title")
    audience = _text(packet.get("audience"), "audience")
    objective = _text(packet.get("objective"), "objective")
    raw_sources = packet.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("sources must contain supplied customer content")
    sources, claims, metrics, flags, held, quarantine = [], [], [], [], [], []
    seen: set[str] = set()
    for raw in raw_sources:
        sid = _text(raw.get("source_id"), "source_id")
        if not _IDENTIFIER.fullmatch(sid) or sid in seen:
            raise ValueError("source_id must be a unique safe identifier")
        seen.add(sid)
        content = _text(raw.get("text"), f"{sid}.text")
        visibility = raw.get("visibility", "review_only")
        if visibility not in {"public", "review_only", "restricted"}:
            raise ValueError(f"{sid}.visibility must be public, review_only or restricted")
        source = {"source_id": sid, "title": str(raw.get("title") or sid),
                  "citation": str(raw.get("citation") or "Customer-supplied source; bibliographic details not supplied"),
                  "text": content, "sha256": hashlib.sha256(content.encode()).hexdigest(), "visibility": visibility}
        sources.append(source)
        if visibility == "restricted":
            flags.append({"code": "restricted_source", "source_id": sid, "detail": "Excluded from the article; report and pitch remain controlled internal drafts."})
        if not raw.get("citation"):
            flags.append({"code": "citation_incomplete", "source_id": sid, "detail": "Confirm authorship, date and usage rights."})
        for ordinal, match in enumerate(re.finditer(r"[^\r\n]+", content), 1):
            quote = match.group().strip()
            if not quote:
                continue
            cid = f"{sid}-P{ordinal}"
            if _INSTRUCTION.search(quote):
                quarantine.append({"source_id": sid, "claim_id": cid, "text": quote, "reason": "Source contains instruction-like content; not followed or included in narrative."})
                flags.append({"code": "source_instruction_quarantined", "source_id": sid, "detail": cid})
                continue
            offset = content.find(quote, match.start(), match.end())
            claims.append({"claim_id": cid, "text": quote, "source_id": sid, "quote": quote,
                           "start": offset, "end": offset + len(quote), "state": "source_attributed_unverified",
                           "visibility": visibility, "source_sha256": source["sha256"]})
        for row in raw.get("metrics") or []:
            quote = _text(row.get("quote"), f"{sid}.metric.quote")
            value = row.get("value")
            numbers = re.findall(r"(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?![\d.])", quote)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"{sid}: metric value must be finite numeric data")
            if quote not in content or not any(float(n.replace(",", "")) == float(value) for n in numbers) or _INSTRUCTION.search(quote):
                raise ValueError(f"{sid}: metric value and exact quote must be anchored in source text")
            if not _metric_context_supported(row, quote):
                raise ValueError(f"{sid}: metric label, unit and period must be supported beside the value in its source quote")
            metrics.append({"source_id": sid, "metric": _text(row.get("metric"), "metric"), "value": value,
                            "unit": _text(row.get("unit"), "unit"), "period": _text(row.get("period"), "period"), "quote": quote})
    if not claims:
        raise ValueError("No usable source observations remain after quarantine")
    source_map = {s["source_id"]: s for s in sources}
    for row in packet.get("claims") or []:
        # Proposed paraphrases need editorial judgment. Only exact attributed
        # wording is machine accepted; unsupported text stays in the reviewer map.
        source = source_map.get(row.get("source_id"))
        quote, statement = str(row.get("quote") or ""), str(row.get("text") or "")
        if not source or not quote or quote not in source["text"] or statement != quote or _INSTRUCTION.search(quote):
            held.append({**row, "state": "held_for_editorial_review", "reason": "Missing exact source support or proposed paraphrase requires human verification"})
    if held:
        flags.append({"code": "unsupported_claims_held", "detail": f"{len(held)} proposed claims excluded from customer narrative."})
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in metrics:
        grouped[(row["metric"].casefold(), row["unit"].casefold(), row["period"].casefold())].append(row)
    for key, rows in grouped.items():
        if len({r["value"] for r in rows}) > 1:
            flags.append({"code": "metric_conflict", "detail": f"{rows[0]['metric']} ({rows[0]['period']}): " + "; ".join(f"{r['value']} {r['unit']} [{r['source_id']}]" for r in rows), "resolution": "Unresolved; values are displayed separately and never averaged."})
    claim_ids = {c["claim_id"] for c in claims}
    recommendations = []
    for row in packet.get("recommendations") or []:
        statement = _text(row.get("text"), "recommendation.text")
        refs = row.get("claim_ids") or []
        if not isinstance(refs, list) or not refs or any(cid not in claim_ids for cid in refs):
            raise ValueError("Every recommendation requires existing source claim_ids")
        if _INSTRUCTION.search(statement):
            raise ValueError("Instruction-like recommendation requires separate review")
        recommendations.append({"text": statement, "claim_ids": refs, "state": "customer_proposed_option_not_validated"})
    calculations = []
    for row in packet.get("calculations") or []:
        if row.get("kind") != "ratio":
            raise ValueError("Only explicit source-anchored ratio calculations are supported")
        operands = []
        for key in ("numerator", "denominator"):
            ref = row.get(key) or {}
            matches = [m for m in metrics if m["source_id"] == ref.get("source_id") and m["metric"] == ref.get("metric")]
            if len(matches) != 1:
                raise ValueError("Calculation operand must identify exactly one supplied metric")
            operands.append(matches[0])
        num, den = operands
        if not den["value"] or num["period"] != den["period"]:
            flags.append({"code": "calculation_held", "detail": f"{row.get('calculation_id')}: denominator is zero or periods differ; no result asserted."})
            continue
        value = num["value"] / den["value"]
        if not math.isfinite(value):
            raise ValueError("Calculation result is not finite")
        calculations.append({"calculation_id": _text(row.get("calculation_id"), "calculation_id"),
                             "title": _text(row.get("title"), "calculation.title"), "kind": "ratio", "value": round(value, 6),
                             "unit": f"{num['unit']}/{den['unit']}", "period": num["period"],
                             "formula": f"{num['value']} / {den['value']}", "operands": operands,
                             "state": "arithmetic_from_supplied_values_not_independently_verified"})
    domain = str(packet.get("domain") or "general").casefold()
    requirements = {
        "healthcare": "Clinical reviewer must assess safety, causality and patient confidentiality; this is not medical guidance.",
        "medical": "Clinical reviewer must assess safety, causality and patient confidentiality; this is not medical guidance.",
        "legal": "Qualified legal reviewer must check jurisdiction, current law and privilege.",
        "financial": "Qualified financial reviewer must check assumptions, forecasts and suitability.",
        "education": "Educator must check curriculum, age suitability and assessment validity.",
        "research": "Research editor must check methods, limitations, citations and publication ethics.",
    }
    if domain in requirements:
        flags.append({"code": f"{domain}_domain_review", "detail": requirements[domain]})
    flags.extend([{"code": "source_truth_unverified", "detail": "Attribution establishes source lineage; source assertions have not been independently verified."},
                  {"code": "editorial_and_rights_review", "detail": "Confirm interpretation, rights and confidentiality before external release."}])
    return {"title": title, "audience": audience, "objective": objective, "domain": domain,
            "sources": sources, "claims": claims, "metrics": metrics, "review_flags": flags,
            "held_claims": held, "quarantined_content": quarantine, "recommendations": recommendations, "calculations": calculations}


def _semantic(model: dict[str, Any], kind: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    title = model["title"] + (" — article draft" if kind == "article" else "")
    return {"schema": "dio.semantic_content.v1", "object_id": f"DIO-{kind.upper()}-{_digest(model)[:10]}",
            "version": "1.0", "title": title,
            "source_language": "English", "context": {"product": "report_pitch_studio" if kind != "article" else "article_publication_studio",
            "artifact_type": kind, "audience": model["audience"], "subject": "Controlled review candidate"},
            "blocks": [{"block_id": f"B{i:04d}", **block} for i, block in enumerate([{"type": "title", "text": title}] + blocks, 1)]}


def _coverage_figure(model: dict[str, Any], path: Path) -> None:
    counts = [(s["source_id"], sum(c["source_id"] == s["source_id"] for c in model["claims"])) for s in model["sources"]]
    height = max(580, 170 + 70 * len(counts))
    image = Image.new("RGB", (1200, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 23)
    draw.text((35, 20), "Evidence coverage by supplied source", fill="#146A6F", font=font)
    draw.text((35, 58), "Count of retained source paragraphs; not a measure of evidence quality", fill="#5F6B76", font=font)
    maximum = max(n for _, n in counts) or 1
    for i, (sid, count) in enumerate(counts):
        y = 115 + i * 70
        draw.text((35, y), sid[:15], fill="#17212B", font=font)
        width = int(700 * count / maximum)
        if width:
            draw.rectangle((280, y, 280 + width, y + 30), fill="#146A6F")
        draw.text((1000, y), str(count), fill="#17212B", font=font)
    image.save(path)


def _projections(model: dict[str, Any], figure_name: str) -> dict[str, dict[str, Any]]:
    def p(text, title=None):
        return {"type": "paragraph", "text": text, **({"title": title} if title else {})}
    def h(text):
        return {"type": "heading", "text": text, "level": 1}
    citation = lambda c: f"[{c['claim_id']}; {c['source_id']}]"
    summary = "\n".join(f"{c['text']} {citation(c)}" for c in model["claims"][:4])
    report = [h("Decision and scope"), p(model["objective"]), p(f"Prepared for {model['audience']}. Supplied-source analysis; editorial, expert and release approval remain pending."),
              h("Executive evidence brief"), p(summary)]
    pitch = [p(model["objective"], "Decision to resolve")]
    for source in model["sources"]:
        report.append(h(source["title"]))
        for claim in [c for c in model["claims"] if c["source_id"] == source["source_id"]]:
            report.append(p(f"{claim['text']} {citation(claim)}"))
        source_brief = "\n".join(f"{c['text']} {citation(c)}" for c in model["claims"] if c["source_id"] == source["source_id"])
        for index, part in enumerate(_chunks(source_brief)):
            pitch.append(p(part, source["title"] + (f" ({index + 1})" if index else "")))
        report.append(p(f"Source: {source['citation']} [{source['source_id']}]. Visibility: {source['visibility']}."))
    if model["metrics"]:
        rows = [[r["metric"], str(r["value"]), r["unit"], r["period"], f"[{r['source_id']}]" ] for r in model["metrics"]]
        report.extend([h("Reported measurements"), {"type": "table", "title": "Source-reported values", "headers": ["Measure", "Value", "Unit", "Period", "Source"], "rows": rows}])
        for start in range(0, len(rows), 5):
            pitch.append({"type": "table", "title": "Source-reported measurements", "headers": ["Measure", "Value", "Unit", "Period", "Source"], "rows": rows[start:start+5]})
    if model["calculations"]:
        report.append(h("Analysis from the supplied figures"))
        for calc in model["calculations"]:
            refs = ", ".join(f"[{r['source_id']}]" for r in calc["operands"])
            narrative = f"{calc['title']}: {calc['value']:g} {calc['unit']} ({calc['period']}). Calculation: {calc['formula']}; inputs: {refs}. This arithmetic uses the supplied period totals; it does not establish causality, benefit, marginal cost or forecast performance."
            report.extend([h(calc["title"]), p(narrative)])
            pitch.append(p(narrative, calc["title"]))
    figure = {"type": "figure", "title": "Coverage of the supplied evidence", "media_path": figure_name,
              "alt_text": "; ".join(f"{s['source_id']}: {sum(c['source_id'] == s['source_id'] for c in model['claims'])} retained source paragraphs" for s in model["sources"]),
              "caption": "Evidence coverage counts retained paragraphs in the supplied packet. Counts do not establish reliability or independent corroboration."}
    report.extend([h("Evidence coverage"), figure])
    pitch.append(figure)
    report.append(h("Decision options and rationale"))
    if model["recommendations"]:
        for rec in model["recommendations"]:
            refs = ", ".join(rec["claim_ids"])
            statement = f"Proposed option: {rec['text']} Rationale references: [{refs}]. This is a customer-proposed option requiring reviewer judgment."
            report.append(p(statement))
            for part in _chunks(statement):
                pitch.append(p(part, "Proposed decision option"))
    else:
        statement = f"No decision option was supplied for: {model['objective']} The packet supports an attributed evidence brief; a recommendation needs an accountable decision owner."
        report.append(p(statement))
        pitch.append(p(statement, "Decision still required"))
    report.append(h("Limitations and reviewer questions"))
    for flag in model["review_flags"]:
        report.append(p(flag["detail"] + (" " + flag.get("resolution", ""))))
    for index, part in enumerate(_chunks("\n".join(f["detail"] for f in model["review_flags"]))):
        pitch.append(p(part, f"Review before release ({index + 1})"))
    report.append(h("References and provenance"))
    for source in model["sources"]:
        report.append(p(f"[{source['source_id']}] {source['citation']}; {source['title']}. Source SHA-256: {source['sha256']}."))
    for start in range(0, len(model["sources"]), 4):
        pitch.append({"type": "bullet_list", "title": "Source references", "items": [f"[{s['source_id']}] {s['citation']}" for s in model["sources"][start:start+4]]})
    eligible = [s for s in model["sources"] if s["visibility"] != "restricted"]
    article = [p(f"{model['objective']} This article draft examines the supplied record for {model['audience']}; source assertions remain attributed and unverified.")]
    for source in eligible:
        article.append(h(source["title"]))
        for claim in model["claims"]:
            if claim["source_id"] == source["source_id"]:
                article.append(p(f"{claim['text']} {citation(claim)}"))
    article.extend([h("What the record leaves open"), p(f"The decision under consideration is: {model['objective']} These sources alone do not establish independent corroboration, causal attribution or professional approval.")])
    # Restricted text and source identifiers never enter the article projection.
    article.append(h("References"))
    for source in eligible:
        article.append(p(f"[{source['source_id']}] {source['citation']} — {source['title']}"))
    if not eligible:
        article.append(p("No source material is cleared for this article draft. An editor must supply eligible evidence before publication."))
    return {"report": _semantic(model, "report", report), "pitch": _semantic(model, "pitch", pitch), "article": _semantic(model, "article", article)}


def build_report_pitch_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Build a review package from supplied text, retaining exact source lineage.

    Required: title, audience, objective, sources[{source_id,text,title?,citation?,
    visibility?,metrics?}]. Metrics need metric/value/unit/period/exact quote.
    Optional recommendations[{text,claim_ids}] are explicit proposed options.
    Source paragraph IDs are SOURCE-P1 etc. Proposed claims are never inferred
    true from lexical similarity; unsupported/paraphrased claims are held.
    Output must be empty, preventing stale files from leaking across customers.
    """
    model = _prepare(packet)
    out = Path(output_dir).expanduser().resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("output_dir must be empty to prevent stale customer content")
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "customer_packet.json", dict(packet))
    _write_json(out / "claim_map.json", {k: model[k] for k in ("claims", "held_claims", "quarantined_content", "metrics", "calculations")})
    _write_json(out / "source_register.json", {"sources": model["sources"], "source_validation": "Customer supplied; not independently verified"})
    figure = out / "evidence_coverage.png"
    _coverage_figure(model, figure)
    projections = _projections(model, figure.name)
    receipts, deliverables = {}, {}
    pdf_available = bool(shutil.which("libreoffice") or shutil.which("soffice"))
    for kind, semantic in projections.items():
        _write_json(out / f"{kind}_semantic.json", semantic)
        channels = ["pptx"] if kind == "pitch" else ["docx", "html"]
        if render_pdf and pdf_available and kind != "pitch":
            channels.append("pdf")
        # Minimal Print avoids Format Core's unpopulated Word TOC field and
        # unnecessary cover pages for compact customer reports and articles.
        receipt = render_semantic_asset(semantic, out / kind, channels=channels, source_root=out, release_mode=False,
                                        style_profile="dio_professional" if kind == "pitch" else "minimal_print")
        receipts[kind] = receipt
        for output in receipt["outputs"]:
            deliverables[f"{kind}_{output['channel']}"] = f"{kind}/{output['path']}"
        if kind == "pitch" and render_pdf and pdf_available:
            deck_pdf = out / "pitch" / "pitch_review.pdf"
            execute_conversion(out / deliverables["pitch_pptx"], deck_pdf)
            deliverables["pitch_pdf"] = "pitch/pitch_review.pdf"
    review = {"status": "pending", "checks": ["Verify every substantive claim against its source locator", "Resolve conflicting values and any held assertions", "Review proposed decision options and preserve limitations", "Confirm usage rights, confidentiality and audience suitability", "Inspect document and slide layout", "Obtain accountable expert/editor approval and separate release authority"],
              "domain_flags": model["review_flags"], "approval": {"reviewer": None, "decision": None},
              "authority": {"publish": False, "send": False, "spend": False, "canon_or_maturity_promotion": False}}
    _write_json(out / "reviewer_checklist.json", review)
    (out / "README.md").write_text(
        f"# {model['title']}\n\nControlled customer review package. The report and deck may contain restricted source material. The article omits sources explicitly marked restricted. All files require editorial and rights review before release.\n\n"
        "Start with report/ and pitch/. Use article/ for the editorial draft. claim_map.json contains exact source offsets and source hashes; source_register.json preserves supplied content. Held assertions and quarantined instruction-like source text stay in the reviewer evidence only.\n\n"
        "Source-attributed means the text can be traced to a supplied source. It does not mean factual, independent, expert approved or publication authorised. Recommendations are customer-proposed options, not validated professional advice.\n", encoding="utf-8")
    result = {"schema": "dio.report_pitch_package.v1", "status": "review_candidate", "output_dir": str(out),
              "input_sha256": _digest(dict(packet)), "deliverables": deliverables, "claim_count": len(model["claims"]),
              "held_claim_count": len(model["held_claims"]), "review_flags": model["review_flags"],
              "processing": {"composition": "deterministic source-bound editorial assembly", "renderer": "adapters.format_core.renderer.render_semantic_asset", "external_calls": 0},
              "pdf": {"requested": render_pdf, "available": pdf_available, "rendered": any(k.endswith("_pdf") for k in deliverables)},
              "release": {"externally_released": False, "expert_approved": False, "publication_authorized": False, "canon_promoted": False},
              "qa": {"format_core_passed": all(r["qa"]["passed"] for r in receipts.values()), "visual_review": "pending"}}
    result["artifacts"] = [{"path": str(p.relative_to(out)), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in sorted(out.rglob("*")) if p.is_file()]
    _write_json(out / "package_manifest.json", result)
    with zipfile.ZipFile(out / "controlled_review_package.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path.name != "controlled_review_package.zip":
                archive.write(path, path.relative_to(out))
    return result
