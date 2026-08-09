from __future__ import annotations

import html
import urllib.parse
from typing import Any


MAIN_SITE = "https://byron2306.github.io/DIO-Workflows/"

PRODUCTS: dict[str, dict[str, Any]] = {
    "evidex": {
        "name": "Evidex Evidence Packs",
        "url": MAIN_SITE + "sites/evidex/",
        "accent": "#245B78",
        "soft": "#EAF2F7",
        "tagline": "Messy evidence, mapped into a reviewable pack.",
        "bullets": ["Claim-to-source mapping", "Provenance trail", "Human review boundary"],
    },
    "homs": {
        "name": "HOMS Assessment Desk",
        "url": MAIN_SITE + "sites/homs/",
        "accent": "#176B5B",
        "soft": "#EAF5F1",
        "tagline": "Assessment and marking work prepared for educator approval.",
        "bullets": ["CAPS-aware planning", "Paper, memo and rubric support", "Educator authority retained"],
    },
    "homs_learning": {
        "name": "HOMS Learning Studio",
        "url": MAIN_SITE + "sites/homs/learning-studio/",
        "accent": "#176B5B",
        "soft": "#EAF5F1",
        "tagline": "Worksheets, activities and learning media from a governed curriculum spine.",
        "bullets": ["Term-aware material", "Classroom-ready drafts", "Teacher review retained"],
    },
    "sophia": {
        "name": "Sophia Academic Review",
        "url": MAIN_SITE + "sites/sophia/",
        "accent": "#8B3D63",
        "soft": "#F8ECF2",
        "tagline": "Academic claims, sources and reviewer commentary made inspectable.",
        "bullets": ["Reference checks", "Claim-to-source audit", "Reviewer commentary"],
    },
    "vamp": {
        "name": "VAMP Evidence Snapshot",
        "url": MAIN_SITE + "sites/vamp/",
        "accent": "#6A4B2E",
        "soft": "#F4EFE9",
        "tagline": "Performance evidence mapped before review day.",
        "bullets": ["Objective mapping", "Gap visibility", "Human acceptance retained"],
    },
    "document_studio": {
        "name": "DIO Document Studio",
        "url": MAIN_SITE + "sites/document-studio/",
        "accent": "#3F5F8F",
        "soft": "#EEF3FA",
        "tagline": "Technical editing, translation and format control for serious documents.",
        "bullets": ["Language-aware editing", "Terminology review", "DOCX, PDF and slide formatting"],
    },
    "dio": {
        "name": "DIO Workflows",
        "url": MAIN_SITE,
        "accent": "#202A33",
        "soft": "#F1F4F5",
        "tagline": "Professional evidence and document workflows with human authority retained.",
        "bullets": ["Bounded intake", "Reviewable output", "Controlled delivery"],
    },
}


def product_profile(product: str | None) -> dict[str, Any]:
    key = str(product or "dio").strip().lower().replace("-", "_")
    aliases = {
        "evidex_pack": "evidex",
        "homs_assess": "homs",
        "homs_learn": "homs_learning",
        "sophia_review": "sophia",
        "sophia_learn": "sophia",
        "vamp_academic": "vamp",
        "vamp_performance": "vamp",
        "translation": "document_studio",
        "formatting": "document_studio",
        "lingua": "document_studio",
    }
    return PRODUCTS.get(aliases.get(key, key), PRODUCTS["dio"])


def reply_link(subject: str, body: str, address: str = "dio_workflows@outlook.com") -> str:
    return f"mailto:{address}?" + urllib.parse.urlencode({"subject": subject, "body": body})


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def branded_email(
    *,
    product: str,
    eyebrow: str,
    headline: str,
    greeting: str,
    intro: str,
    body: list[str],
    reference: str | None = None,
    bullets: list[str] | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    secondary_label: str = "View DIO Workflows",
    secondary_url: str = MAIN_SITE,
    caution: str | None = None,
    footer: str | None = None,
) -> tuple[str, str]:
    profile = product_profile(product)
    product_name = profile["name"]
    bullet_values = bullets or list(profile.get("bullets") or [])
    plain = [
        f"{product_name} | {eyebrow}",
        "",
        greeting,
        "",
        intro,
        "",
        *body,
        "",
        f"Main site: {MAIN_SITE}",
        f"{product_name}: {profile['url']}",
    ]
    if cta_label and cta_url:
        plain.extend(["", f"{cta_label}: {cta_url}"])
    if reference:
        plain.extend(["", f"Reference: {reference}"])
    if caution:
        plain.extend(["", caution])
    if footer:
        plain.extend(["", footer])
    bullet_cells = "".join(
        '<td style="width:33.33%%;padding:12px 8px;border-right:%s;text-align:center;font-size:13px;line-height:18px;color:#25313b;font-weight:700">%s</td>'
        % ("0" if index == len(bullet_values[:3]) - 1 else "1px solid #d7dee3", _e(item))
        for index, item in enumerate(bullet_values[:3])
    )
    body_html = "".join(f'<p style="margin:0 0 14px">{_e(paragraph)}</p>' for paragraph in body)
    buttons: list[str] = []
    seen_urls: set[str] = set()

    def add_button(label: str | None, url: str | None, primary: bool = False) -> None:
        if not label or not url or url in seen_urls:
            return
        seen_urls.add(url)
        if primary:
            buttons.append(
                f'<a href="{_e(url)}" style="display:inline-block;padding:11px 16px;background:{profile["accent"]};'
                'color:#ffffff;text-decoration:none;font-weight:800;font-size:13px">'
                f'{_e(label)}</a>'
            )
        else:
            buttons.append(
                f'<a href="{_e(url)}" style="display:inline-block;padding:10px 15px;border:1px solid #aeb8bf;'
                'color:#33414c;text-decoration:none;font-weight:800;font-size:13px">'
                f'{_e(label)}</a>'
            )

    add_button(cta_label, cta_url, primary=True)
    add_button(f"View {product_name}", profile["url"])
    add_button(secondary_label, secondary_url)
    button_html = "".join(f'<td style="padding:0 8px 0 0">{button}</td>' for button in buttons)
    html_body = f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f3f5f6;color:#202a33;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f5f6"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:660px;background:#ffffff;border:1px solid #d7dee3;border-collapse:separate">
  <tr><td style="padding:12px 24px;background:#202a33;color:#ffffff;font-size:13px;font-weight:800">DIO WORKFLOWS <span style="color:#aebac3;font-weight:400">&nbsp; | &nbsp; governed professional workflow products</span></td></tr>
  <tr><td style="padding:28px 28px 22px;background:{profile['accent']};color:#ffffff">
    <div style="font-size:11px;line-height:16px;font-weight:800;text-transform:uppercase">{_e(eyebrow)}</div>
    <div style="font-size:25px;line-height:32px;font-weight:800;margin-top:8px">{_e(headline)}</div>
    <div style="font-size:14px;line-height:21px;margin-top:9px;color:#eef7f5">{_e(profile['tagline'])}</div>
  </td></tr>
  <tr><td style="padding:26px 28px 10px;font-size:15px;line-height:23px">
    <p style="margin:0 0 14px">{_e(greeting)}</p>
    <p style="margin:0 0 14px"><strong>{_e(intro)}</strong></p>
    {body_html}
  </td></tr>
  <tr><td style="padding:8px 28px 18px">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #d7dee3;background:{profile['soft']};border-collapse:collapse"><tr>{bullet_cells}</tr></table>
  </td></tr>
  <tr><td style="padding:0 28px 26px;font-size:14px;line-height:22px">
    <table role="presentation" cellspacing="0" cellpadding="0"><tr>
      {button_html}
    </tr></table>
    {f'<p style="margin:16px 0 0;color:#52616b"><strong>Reference:</strong> {_e(reference)}</p>' if reference else ''}
  </td></tr>
  <tr><td style="padding:18px 28px;background:#f7f8f8;border-top:1px solid #d7dee3;font-size:11px;line-height:17px;color:#5d6871">
    { _e(caution or "DIO prepares bounded, reviewable workflow outputs. Human authority remains with the client, educator, reviewer, organisation or operator as applicable.") }<br><br>
    { _e(footer or "Byron Bunt | DIO Workflows | dio_workflows@outlook.com") }
  </td></tr>
</table>
</td></tr></table>
</body></html>"""
    return "\n".join(line for line in plain if line is not None).strip() + "\n", html_body
