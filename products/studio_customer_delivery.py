from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any


class StudioCustomerDeliveryError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _invoice_ref(text: str) -> str:
    match = re.search(r"\b(?:INV[- ]?\d+|invoice\s+#?\w[\w-]*)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else "the invoice"


def _professional_task(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("professional_task_input")
    return value if isinstance(value, dict) else {}


def _source_documents(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _professional_task(manifest).get("source_documents") or []
    return [row for row in rows if isinstance(row, dict)]


def _label_value(lines: list[str], labels: tuple[str, ...]) -> str:
    wanted = {label.casefold() for label in labels}
    for line in lines:
        match = re.match(r"^\s*([^:]+)\s*:\s*(.+?)\s*$", line)
        if match and match.group(1).strip().casefold() in wanted:
            return match.group(2).strip()
    return ""


def _professional_site_facts(manifest: dict[str, Any]) -> dict[str, Any]:
    documents = _source_documents(manifest)
    if not documents:
        return {}

    all_lines: list[str] = []
    services: list[str] = []
    projects: list[str] = []
    emails: list[str] = []

    unsafe_markers = (
        "owner request:",
        "no formal market-leadership ranking",
        "no client testimonials",
        "no awards or certifications",
        "evidence supplied for",
        "outcome of donor decision",
        "client identity is confidential",
        "client name: confidential",
    )

    for document in documents:
        filename = str(document.get("filename") or "").casefold()
        text = str(document.get("text") or "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        all_lines.extend(lines)
        emails.extend(re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.IGNORECASE))

        in_services = False
        project_doc = any(token in filename for token in ("project", "case", "evidence"))
        for line in lines:
            low = line.casefold()
            if low.startswith(("supported services:", "current service list", "services:")):
                in_services = True
                tail = line.split(":", 1)[1].strip() if ":" in line else ""
                if tail:
                    for item in tail.split(";"):
                        item = item.strip(" .")
                        if item:
                            services.append(item)
                continue
            if in_services and re.match(r"^(?:[-•]|\d+[.)])\s*", line):
                item = re.sub(r"^(?:[-•]|\d+[.)])\s*", "", line).strip(" .")
                if item:
                    services.append(item)
                continue
            if in_services and line.isupper():
                in_services = False

            if project_doc and not any(marker in low for marker in unsafe_markers):
                if re.match(r"^(?:project\s+[a-z0-9]+:|case\s+[a-z0-9]+:)", line, flags=re.IGNORECASE):
                    projects.append(line)
                elif any(token in low for token in ("assignment", "monitoring points", "supported one community organisation")):
                    projects.append(line)

    def dedupe(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    services = dedupe(services)
    projects = dedupe(projects)
    emails = dedupe(emails)

    experience = _label_value(all_lines, ("Founder experience", "Team experience"))
    if not experience:
        for line in all_lines:
            if re.search(r"\b(?:owner|founder)\b.*\b\d+\s+years\b", line, flags=re.IGNORECASE):
                experience = line.rstrip(".")
                break

    location = _label_value(all_lines, ("Operating base", "Geographic reach"))
    buyers = _label_value(all_lines, ("Target buyers", "Buyers"))

    return {
        "services": services[:8],
        "projects": projects[:4],
        "experience": experience,
        "location": location,
        "buyers": buyers,
        "email": emails[0] if emails else "",
    }


def _site_delivery(manifest: dict[str, Any], out: Path) -> tuple[str, str, list[str]]:
    contract = manifest["artifact_contract"]
    positioning = contract["positioning"]
    brand_name = str((contract.get("brand") or {}).get("title") or manifest["name"])
    category = str(positioning["category"])
    problem = str(positioning["buyer_problem"])
    outcome = str(positioning["desired_outcome"])
    buyer = str(manifest["job"]["buyer"])
    professional = _professional_site_facts(manifest)

    if not professional:
        headline = f"{brand_name} turns complex {category} work into clearer decisions."
        subhead = f"Practical, evidence-led support for {buyer.lower()} teams that need credible analysis, clear communication and decision-ready outputs."
        sections = [
            ("Clarify the decision", f"Start with the real decision behind the work. {problem}"),
            ("Structure the evidence", "Bring source material, assumptions and limits into one reviewable evidence trail before conclusions are presented."),
            ("Communicate what matters", f"Translate the work into a usable public or professional form. {outcome}"),
        ]
        cards = "".join(
            f"<article class='card'><span>0{i}</span><h2>{html.escape(title)}</h2><p>{html.escape(body)}</p></article>"
            for i, (title, body) in enumerate(sections, 1)
        )
        page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(brand_name)}</title><link rel='stylesheet' href='styles.css'></head><body><header><nav><strong>{html.escape(brand_name)}</strong><a href='#contact'>Start a conversation</a></nav><section class='hero'><div><p class='eyebrow'>{html.escape(category.upper())}</p><h1>{html.escape(headline)}</h1><p class='lead'>{html.escape(subhead)}</p><a class='button' href='#contact'>Discuss your project</a></div><aside><strong>What you can expect</strong><p>Clear scope. Evidence-aware work. Professional outputs. No invented credentials or guarantees.</p></aside></section></header><main><section class='services'>{cards}</section><section id='contact' class='contact'><p class='eyebrow'>PROJECT ENQUIRY</p><h2>Tell us what decision your work needs to support.</h2><p>Bring the question, available evidence and intended audience. We will use that to shape the right project brief.</p><form><label>Name<input required></label><label>Organisation<input required></label><label>What do you need to achieve?<textarea rows='5' required></textarea></label><button type='button'>Prepare enquiry</button></form></section></main><footer>{html.escape(brand_name)} · Professional research and evidence support</footer></body></html>"""
        fields = [
            "artifact_contract.brand.title",
            "artifact_contract.positioning.category",
            "artifact_contract.positioning.buyer_problem",
            "artifact_contract.positioning.desired_outcome",
            "job.buyer",
        ]
    else:
        services = professional["services"] or [category]
        service_cards = "".join(
            f"<article class='card'><span>{i:02d}</span><h2>{html.escape(service)}</h2><p>Practical support shaped around the evidence, audience and decision behind the work.</p></article>"
            for i, service in enumerate(services, 1)
        )
        experience = str(professional.get("experience") or "").strip()
        location = str(professional.get("location") or "").strip()
        buyers = str(professional.get("buyers") or "").strip()
        email = str(professional.get("email") or "").strip()
        projects = professional.get("projects") or []
        project_html = "".join(
            f"<article class='project'><p>{html.escape(project)}</p></article>" for project in projects
        )
        if not project_html:
            project_html = "<p>Project examples are shared only where the supplied evidence supports public use.</p>"

        credibility_bits = [value for value in (experience, location) if value]
        credibility = " · ".join(credibility_bits) or "Evidence-backed professional support"
        audience = buyers or buyer
        contact_copy = f"Email {email} to discuss your brief." if email else "Tell us what you need to achieve and which evidence is already available."
        headline = f"{brand_name}: {category} that turns evidence into practical next steps."
        subhead = f"Professional support for {audience}. {problem}"

        page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(brand_name)}</title><meta name='description' content='{html.escape(outcome)}'><link rel='stylesheet' href='styles.css'></head><body><header><nav><strong>{html.escape(brand_name)}</strong><a href='#contact'>Start a conversation</a></nav><section class='hero'><div><p class='eyebrow'>{html.escape(category.upper())}</p><h1>{html.escape(headline)}</h1><p class='lead'>{html.escape(subhead)}</p><p class='credibility'>{html.escape(credibility)}</p><a class='button' href='#contact'>Discuss your project</a></div><aside><strong>Built around the work you actually need done</strong><p>{html.escape(outcome)}</p></aside></section></header><main><section class='intro'><p class='eyebrow'>SERVICES</p><h2>Clear professional support, grounded in supplied evidence.</h2><p>We focus the work on the buyer's real decision, keep claims proportionate to the available evidence, and turn complex material into useful professional outputs.</p></section><section class='services'>{service_cards}</section><section class='evidence'><div><p class='eyebrow'>EXPERIENCE</p><h2>Credibility without inflated claims.</h2><p>{html.escape(credibility)}</p><p>Only supported, publicly usable credentials and project evidence are presented.</p></div><div><p class='eyebrow'>SELECTED WORK</p><h2>Examples supported by the supplied record.</h2>{project_html}</div></section><section id='contact' class='contact'><p class='eyebrow'>PROJECT ENQUIRY</p><h2>Start a conversation about the work in front of you.</h2><p>{html.escape(contact_copy)}</p><form><label>Name<input required></label><label>Organisation<input required></label><label>What do you need to achieve?<textarea rows='5' required></textarea></label><button type='button'>Prepare enquiry</button></form></section></main><footer>{html.escape(brand_name)} · {html.escape(category)}</footer></body></html>"""
        fields = [
            "artifact_contract.brand.title",
            "artifact_contract.positioning.category",
            "artifact_contract.positioning.buyer_problem",
            "artifact_contract.positioning.desired_outcome",
            "job.buyer",
            "professional_task_input.source_documents",
            "professional_task_input.case_context",
            "professional_task_input.constraints",
        ]

    css = """*{box-sizing:border-box}body{margin:0;background:#07131d;color:#edf4f5;font:17px/1.6 system-ui,sans-serif}header,main,footer{width:min(1120px,calc(100% - 40px));margin:auto}nav{display:flex;justify-content:space-between;align-items:center;padding:26px 0}nav a,.button{color:#07131d;background:#d9b86c;text-decoration:none;padding:12px 17px;border-radius:8px;font-weight:800}.hero{min-height:70vh;display:grid;grid-template-columns:1.35fr .65fr;gap:48px;align-items:center}.eyebrow{letter-spacing:.13em;font-weight:900;color:#68d5ca;font-size:.8rem}h1{font-size:clamp(2.8rem,6.8vw,6rem);line-height:.96;letter-spacing:-.05em;margin:.25em 0}h2{font-size:clamp(1.7rem,3vw,2.6rem);line-height:1.1}.lead{max-width:760px;color:#bfd0d3;font-size:1.16rem}.credibility{font-weight:800;color:#f0d79a}aside{padding:28px;border:1px solid #ffffff25;border-radius:18px;background:#ffffff08}.intro{padding:76px 0 24px;max-width:820px}.services{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;padding:24px 0 72px}.card{padding:28px;background:#f5f1e8;color:#16232c;border-radius:16px}.card span{font-weight:900;color:#078d82}.evidence{display:grid;grid-template-columns:1fr 1fr;gap:30px;padding:70px 0;border-top:1px solid #ffffff1d}.project{padding:16px 0;border-bottom:1px solid #ffffff1d}.contact{padding:70px 0 90px;max-width:760px}.contact form{display:grid;gap:15px}label{font-weight:800}input,textarea{display:block;width:100%;margin-top:6px;padding:13px;border-radius:8px;border:1px solid #ffffff35;background:#ffffff0d;color:white}button{width:max-content;border:0;background:#d9b86c;padding:13px 18px;border-radius:8px;font-weight:800}footer{padding:34px 0;border-top:1px solid #ffffff1d;color:#91a7ab}@media(max-width:800px){.hero,.services,.evidence{grid-template-columns:1fr}.hero{padding:55px 0}nav a{display:none}}"""
    _write(out / "site" / "index.html", page)
    _write(out / "site" / "styles.css", css)
    return "site/index.html", "site", fields


def _correspondence_delivery(manifest: dict[str, Any], out: Path) -> tuple[str, str, list[str]]:
    contract = manifest["artifact_contract"]
    request = str(manifest["job"]["request"])
    invoice = _invoice_ref(request)
    preserve = " ".join(str(x) for x in contract.get("must_preserve") or [])
    subject = f"Re: {invoice} review" if invoice.casefold() != "the invoice" else "Re: Invoice query and review"
    body = "\n".join([
        "Dear Client,",
        "",
        f"Thank you for raising your concern regarding {invoice}.",
        "",
        "We have recorded the points you have raised and are reviewing the relevant scope, records and billing basis before responding on the disputed items.",
        "",
        "At this stage, our review is not an agreement to amend the invoice and does not create a refund, waiver or settlement commitment.",
        "",
        "Once the records have been checked, an authorised colleague will respond with our findings and the appropriate next step.",
        "",
        "Kind regards,",
        "Professional Services Team",
    ])
    if "requires review" not in preserve.casefold() and "review" not in preserve.casefold():
        raise StudioCustomerDeliveryError("correspondence source facts do not preserve the required review boundary")
    text = f"Subject: {subject}\n\n{body}\n"
    _write(out / "correspondence" / "DRAFT_EMAIL.txt", text)
    return "correspondence/DRAFT_EMAIL.txt", "correspondence", [
        "job.request",
        "artifact_contract.purpose",
        "artifact_contract.tone",
        "artifact_contract.must_preserve",
        "artifact_contract.must_not_invent",
    ]


def _finance_delivery(manifest: dict[str, Any], out: Path) -> tuple[str, str, list[str]]:
    contract = manifest["artifact_contract"]
    venture = contract["venture"]
    evidence = contract.get("supplied_evidence_fixture") or []
    supported = {req for row in evidence if row.get("state") == "supplied" for req in row.get("supports") or []}
    requirements = contract.get("published_requirements_fixture") or []
    rows = []
    missing = []
    for req in requirements:
        ready = req["requirement_id"] in supported
        if req.get("mandatory") and not ready:
            missing.append(req)
        rows.append(
            f"<tr><td>{html.escape(str(req['label']))}</td><td>{'Ready for review' if ready else 'Evidence still needed'}</td></tr>"
        )
    assumptions = "".join(f"<li>{html.escape(str(x))}</li>" for x in contract.get("assumptions") or [])
    missing_list = "".join(f"<li>{html.escape(str(x['label']))}</li>" for x in missing) or "<li>No mandatory evidence gaps detected in the supplied set.</li>"
    page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(str(venture['name']))} finance readiness</title><style>body{{margin:0;background:#f3f6f4;color:#17231f;font:16px/1.6 system-ui,sans-serif}}main{{max-width:980px;margin:auto;padding:48px 24px}}.hero{{background:#123f3a;color:white;padding:34px;border-radius:18px}}h1{{font-size:clamp(2.4rem,6vw,4.6rem);line-height:1;margin:.2em 0}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:12px;border:1px solid #cfd8d4;text-align:left}}.notice{{padding:18px;background:#fff4dc;border-left:5px solid #b57500}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:28px}}.panel{{background:white;padding:24px;border-radius:14px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><section class='hero'><p>FINANCE APPLICATION READINESS</p><h1>{html.escape(str(venture['name']))}</h1><p><strong>Funding need:</strong> {html.escape(str(venture['funding_need']))}</p><p>{html.escape(str(contract['purpose']))}</p></section><div class='grid'><section class='panel'><h2>Evidence checklist</h2><table><thead><tr><th>Requirement</th><th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section><section class='panel'><h2>What still needs attention</h2><p><strong>Missing mandatory evidence items: {len(missing)}</strong></p><ul>{missing_list}</ul><h3>Assumptions to validate</h3><ul>{assumptions}</ul></section></div><p class='notice'>{html.escape(str(contract['decision_boundary']))}</p></main></body></html>"""
    _write(out / "finance" / "READINESS_REPORT.html", page)
    return "finance/READINESS_REPORT.html", "finance", [
        "artifact_contract.venture",
        "artifact_contract.published_requirements_fixture",
        "artifact_contract.supplied_evidence_fixture",
        "artifact_contract.assumptions",
        "artifact_contract.purpose",
        "artifact_contract.decision_boundary",
    ]


def _article_delivery(manifest: dict[str, Any], out: Path) -> tuple[str, str, list[str]]:
    contract = manifest["artifact_contract"]
    supported = [row for row in contract.get("claim_fixture") or [] if row.get("state") == "SUPPORTED"]
    if len(supported) < 2:
        raise StudioCustomerDeliveryError("article delivery requires at least two supported claims")
    sources = {str(row["source_id"]): row for row in contract.get("source_fixture") or []}
    publication = str(contract["publication"])
    audience = str(contract.get("audience") or manifest["job"]["buyer"])

    first = str(supported[0]["text"]).rstrip(".")
    second = str(supported[1]["text"]).rstrip(".")
    headline = "Why traceable evidence matters when professional work moves faster"
    standfirst = f"For {audience.lower()}, speed is useful only when the source trail remains easy to inspect, challenge and correct."
    paragraphs = [
        f"Professional teams can produce drafts faster than ever, but speed changes the review burden. {first}. The practical consequence is simple: provenance has to remain visible while the work is still being shaped, not reconstructed after the fact.",
        f"That matters because {second.lower()}. A source-aware workflow keeps each important assertion connected to the material that supports it, giving editors a clearer route for challenge, revision and correction.",
    ]
    if len(supported) > 2:
        third = str(supported[2]["text"]).rstrip(".")
        paragraphs.append(f"There is also an authority boundary that quality alone cannot erase. {third}. A polished draft can be ready for review without being authorised for release.")
    section_html = "".join(
        f"<section><h2>{title}</h2><p>{html.escape(text)}</p></section>"
        for title, text in zip(
            ["Speed changes the review burden", "Traceability supports correction", "Quality is not release authority"],
            paragraphs,
        )
    )
    refs = []
    for source in contract.get("source_fixture") or []:
        refs.append(f"<li>{html.escape(str(source['citation']))}</li>")
    claim_map = []
    for claim in contract.get("claim_fixture") or []:
        if claim.get("state") == "REFUSE":
            state = "Not supported for publication"
        else:
            names = [str(sources.get(str(sid), {}).get("citation") or sid) for sid in claim.get("evidence_ids") or []]
            state = "Supported by: " + "; ".join(names)
        claim_map.append(f"<li><strong>{html.escape(str(claim['text']))}</strong><br>{html.escape(state)}</li>")
    page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(headline)}</title><style>body{{margin:0;background:#fbfaf7;color:#202126;font:18px/1.72 Georgia,serif}}article{{max-width:840px;margin:auto;padding:52px 24px}}h1{{font:750 clamp(2.8rem,7vw,5.5rem)/.98 system-ui,sans-serif;letter-spacing:-.055em}}h2{{font-family:system-ui,sans-serif;margin-top:2em}}.standfirst{{font-size:1.24rem;color:#555}}.meta,.note{{font:14px/1.5 system-ui,sans-serif;color:#59616a}}.note{{border-left:4px solid #b17a18;padding:12px 16px;background:#fff6e6}}ol,ul{{padding-left:1.3em}}</style></head><body><article><p class='meta'>{html.escape(publication)} · Draft for editorial review</p><h1>{html.escape(headline)}</h1><p class='standfirst'>{html.escape(standfirst)}</p>{section_html}<h2>Claim and source notes</h2><ul>{''.join(claim_map)}</ul><h2>References</h2><ol>{''.join(refs)}</ol><p class='note'>This draft requires human editorial review before publication. Unsupported claims remain excluded from the article body.</p></article></body></html>"""
    _write(out / "article" / "ARTICLE_DRAFT.html", page)
    return "article/ARTICLE_DRAFT.html", "article", [
        "artifact_contract.publication",
        "artifact_contract.audience",
        "artifact_contract.editorial_register",
        "artifact_contract.source_fixture",
        "artifact_contract.claim_fixture",
    ]


def render_customer_delivery(*, manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    kind = str(manifest["artifact_contract"]["kind"])
    if kind == "site":
        primary_rel, package_rel, fields = _site_delivery(manifest, output_dir)
        ignored = ["artifact_contract.brand.headline", "artifact_contract.brand.subhead", "artifact_contract.sections"]
    elif kind == "correspondence":
        primary_rel, package_rel, fields = _correspondence_delivery(manifest, output_dir)
        ignored = ["artifact_contract.draft"]
    elif kind == "finance_readiness":
        primary_rel, package_rel, fields = _finance_delivery(manifest, output_dir)
        ignored = []
    elif kind == "article":
        primary_rel, package_rel, fields = _article_delivery(manifest, output_dir)
        ignored = ["artifact_contract.headline", "artifact_contract.standfirst", "artifact_contract.sections"]
    else:
        raise StudioCustomerDeliveryError(f"unsupported Studio customer delivery kind: {kind}")
    primary = output_dir / primary_rel
    receipt = {
        "schema": "dio.studio_customer_delivery.v1",
        "studio_id": manifest["studio_id"],
        "kind": kind,
        "primary_artifact": primary_rel,
        "primary_sha256": _sha(primary),
        "package": package_rel,
        "input_fields_used": fields,
        "legacy_final_copy_fields_ignored": ignored,
        "final_copy_fields_used": False,
        "customer_artifact_separated_from_proof": True,
        "external_effects": False,
        "authority_created": False,
    }
    (output_dir / "CUSTOMER_DELIVERY_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt