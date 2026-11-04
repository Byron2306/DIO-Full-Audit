from __future__ import annotations

import hashlib
import http.client
import json
import re
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = False
        self.hidden = 0
        self.title_parts: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.title = True
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.title = False
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        if self.title:
            self.title_parts.append(value)
        if not self.hidden:
            self.parts.append(value)


def _fetch(url: str) -> tuple[bytes, str, str | None, int, str, str]:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError(f"Market Radar source must be an HTTPS public host: {url}")
    hostname = parsed.hostname.rstrip(".").casefold()
    if "." not in hostname or hostname.endswith((".local", ".internal", ".localhost", ".test", ".invalid")):
        raise ValueError("Market Radar source must use a public DNS host")
    try:
        literal = ip_address(hostname)
        addresses = [str(literal)]
    except ValueError:
        try:
            addresses = sorted({row[4][0] for row in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)})
        except OSError as exc:
            raise ValueError("Market Radar source DNS resolution failed") from exc
    if not addresses:
        raise ValueError("Market Radar source resolved to no addresses")
    for value in addresses:
        ip = ip_address(value)
        if not ip.is_global or ip.is_reserved or ip.is_multicast or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
            raise ValueError("Market Radar source resolves to a non-public IP address")

    # Connect directly to the checked address so a second DNS lookup cannot
    # rebind the source to a private host. TLS still validates the requested
    # hostname. Do not follow redirects or fetch unreviewed hosts.
    raw_socket = socket.create_connection((addresses[0], 443), timeout=20)
    tls_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=hostname)
    connection = http.client.HTTPSConnection(hostname, timeout=20, context=ssl.create_default_context())
    connection.sock = tls_socket
    request_path = parsed.path or "/"
    if parsed.query:
        request_path += "?" + parsed.query
    try:
        connection.request("GET", request_path, headers={
            "User-Agent": "DIO-Market-Radar/1.0 (public-source research)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Market Radar source returned HTTP {response.status}; redirects are not followed")
        content_type = str(response.getheader("content-type") or "")
        if "html" not in content_type.casefold():
            raise ValueError(f"Market Radar source returned unsupported content type: {content_type}")
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Market Radar source exceeded the 2 MB capture limit")
        return data, url, response.getheader("last-modified"), int(response.status), content_type, addresses[0]
    finally:
        connection.close()


def _pricing_signals(text: str) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for match in re.finditer(r"\bR\s*([\d,]+(?:\.\d{1,2})?)\s*/\s*(?:mo(?:nth)?|month)\b", text, re.I):
        before = text[max(0, match.start() - 95):match.start()]
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9&-]*", before)
        label = (" ".join(tokens[-2:]) if tokens and tokens[-1].casefold() == "firm" else tokens[-1]) if tokens else "Published plan"
        amount = float(match.group(1).replace(",", ""))
        signals.append({"signal_type": "published_list_price", "plan_label_context": label, "amount_zar_per_month": amount, "interpretation": "Vendor-published price at capture time; verify tax, promotional terms, user limits and inclusions directly."})
    return signals


def _market_facts(source: dict[str, Any], text: str) -> list[dict[str, Any]]:
    lower = text.casefold()
    facts: list[dict[str, Any]] = []
    prices = _pricing_signals(text)
    for price in prices:
        facts.append(price)
    if "astricomply" in source["url"].casefold():
        for phrase, signal in [
            ("evidence vault", "Vendor describes an evidence-vault feature."),
            ("processing register", "Vendor describes a processing-register feature."),
            ("service-provider register", "Vendor describes a service-provider register feature."),
            ("review reminders", "Vendor describes recurring review reminders."),
        ]:
            if phrase in lower:
                facts.append({"signal_type": "vendor_feature_claim", "statement": signal, "feature_term": phrase})
    elif "filesafe" in source["url"].casefold():
        for phrase, signal in [
            ("case management", "Vendor describes case-management functionality."),
            ("documents management", "Vendor describes document-management functionality."),
            ("case workflow automation", "Vendor describes case-workflow automation."),
        ]:
            if phrase in lower:
                facts.append({"signal_type": "vendor_feature_claim", "statement": signal, "feature_term": phrase})
    else:
        respondents = re.search(r"\b(\d{2,4})\s+(?:business\s+)?respondents\b", lower)
        wc = re.search(r"\b(\d{2,4})\s+(?:w\.?\s?cape|western cape)\s+respondents\b", lower)
        pct = re.search(r"\b(almost\s+\d{1,2}%|\d{1,2}%)\s+of\s+the\s+(\d{1,3})\s+largest employers", lower)
        if respondents:
            facts.append({"signal_type": "survey_scope", "respondent_count": int(respondents.group(1)), "interpretation": "Survey sample size reported by the publisher; not a representative estimate for the target segment."})
        if wc:
            facts.append({"signal_type": "survey_geographic_scope", "western_cape_respondent_count": int(wc.group(1)), "interpretation": "Publisher reports a predominantly Western Cape sample; avoid treating the finding as nationally representative."})
        if pct:
            facts.append({"signal_type": "survey_finding", "reported_share": pct.group(1), "employer_subgroup_count": int(pct.group(2)), "interpretation": "Publisher-reported labour-regulation constraint among the largest-employer subgroup; not evidence about 20–200 person professional firms."})
    return facts


def build_targeted_market_brief(packet: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    scope_path = packet["packet_dir"] / "SOURCES" / "market_radar_scope.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    records = []
    failures = []
    source_dir = output_dir / "market_research_sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    for candidate in scope.get("source_candidates") or []:
        try:
            raw, final_url, last_modified, http_status, content_type, resolved_ip = _fetch(str(candidate["url"]))
            raw_path = source_dir / (str(candidate["source_id"]).lower() + ".html")
            raw_path.write_bytes(raw)
            parser = _VisibleText()
            parser.feed(raw.decode("utf-8", errors="replace"))
            text = " ".join(" ".join(parser.parts).split())
            facts = _market_facts(candidate, text)
            records.append({
                **candidate,
                "final_url": final_url,
                "page_title": " ".join(parser.title_parts).strip()[:250],
                "captured_at": captured_at,
                "last_modified_header": last_modified,
                "http_status": http_status,
                "transport": "HTTPS public-IP-pinned GET; TLS hostname verified; redirects refused",
                "resolved_ip": resolved_ip,
                "content_type": content_type,
                "raw_bytes": len(raw),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "raw_path": str(raw_path.resolve()),
                "facts": facts,
                "fact_count": len(facts),
                "source_text_retained": False,
                "source_text_policy": "Only structured, short factual observations are retained; original page remains available at source URL.",
            })
        except Exception as exc:
            failures.append({"source_id": candidate.get("source_id"), "url": candidate.get("url"), "error": f"{type(exc).__name__}: {exc}"})
    if not records:
        raise RuntimeError("Market Radar could not capture any source candidates: " + json.dumps(failures[:3]))
    result = {
        "schema": "dio.market_radar.targeted_source_brief.v1",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
        "scope_source_sha256": hashlib.sha256(scope_path.read_bytes()).hexdigest(),
        "scope": {key: scope.get(key) for key in ("geography", "buyer", "question")},
        "captured_at": captured_at,
        "source_count": len(records),
        "source_failures": failures,
        "sources": records,
        "interpretation": [
            "Vendor features and published prices are vendor claims captured from their own pages, not verified product performance or a complete market census.",
            "Survey evidence is contextual only; sample mix and geography limit transfer to the specified buyer segment.",
            "These observations do not establish market size, demand, willingness to pay, competitive rank or product-market fit.",
        ],
        "market_demand_claimed": False,
        "customer_outreach_performed": False,
        "spend_authorized": False,
        "authority_created": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "MARKET_RADAR_TARGET_BRIEF.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Market Radar — source-bound signal brief", "", f"**Scope:** {result['scope']['geography']} · {result['scope']['buyer']}", f"**Captured:** {captured_at}", "", "This is a small public-signal sample. It does not prove demand, market size, willingness to pay, competitive rank or product-market fit."]
    for source in records:
        lines.extend(["", f"## {source['source_id']} — {source['page_title'] or source['market_relation']}", "", f"- Publisher/source: {source['final_url']}", f"- Category: {source['source_class']} · {source['market_relation']}", f"- Capture: {source['captured_at']} · {source['raw_bytes']} bytes · SHA-256 `{source['raw_sha256']}`"])
        if source["facts"]:
            for fact in source["facts"]:
                if fact.get("signal_type") == "published_list_price":
                    lines.append(f"- Published price signal: {fact.get('plan_label_context')} — R{fact['amount_zar_per_month']:,.0f}/month. {fact['interpretation']}")
                elif fact.get("signal_type") == "vendor_feature_claim":
                    lines.append(f"- Vendor feature claim: {fact['statement']}")
                else:
                    lines.append(f"- Context signal: {fact.get('interpretation')}")
        else:
            lines.append("- No structured signal extracted; source requires manual review.")
        lines.append(f"- Scope limit: {source['relevance_limit']}")
    lines.extend(["", "## Decision use", "", "Use these observations to frame buyer interviews and compare testable workflows. Confirm prices and features directly with vendors before making commercial decisions. The synthetic customer case contains no buyer interviews, purchase data or willingness-to-pay evidence."])
    md_path = output_dir / "MARKET_RADAR_TARGET_BRIEF.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"brief": result, "json_path": str(json_path), "markdown_path": str(md_path)}
