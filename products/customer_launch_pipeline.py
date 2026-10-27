"""Customer-bound LaunchStudio assets using existing Lingua and NicheFoundry.

Only explicit source expressions enter marketing. Governance, raw story plans
and reviewer questions are kept in the private review appendix.
"""
from __future__ import annotations

import csv
import hashlib
import html
import importlib.util
import json
import re
import shutil
import zipfile
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageOps

from lingua.product_projection import build_projection_plan, project_story
from lingua.semantic_law import build_semantic_law, validate_projection

ROOT = Path(__file__).resolve().parents[1]
FACTORY_SOURCE = ROOT / "scripts/build_multichannel_campaign_factory_v3.py"
_INSTRUCTION = re.compile(r"ignore (?:all |previous |prior )*(?:instructions|rules)|(?:system|developer)\s*(?:prompt|message)|publish now|exfiltrate|<script\b", re.I)
_STRONG_CLAIM = re.compile(r"\bguarantee(?:d|s)?\b|\b100\s*%|\b(?:certified|accredited|market leader|number one)\b", re.I)
_INTERNAL = re.compile(r"human authority|publication (?:held|hold)|spend disabled|canon promoted|#DIO\b", re.I)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def _native_factory():
    # A private module namespace loads the actual source definitions even if the
    # public campaign factory already installed identity/Gamma monkeypatches on
    # its canonical module. No registry wrapper or global mutation is involved.
    spec = importlib.util.spec_from_file_location("_dio_customer_launch_native_factory_v3", FACTORY_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Native NicheFoundry source cannot be loaded")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return native


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def _prepare(packet: Mapping[str, Any]) -> dict[str, Any]:
    sources, flags, anchors = {}, [], {}
    for row in packet.get("sources") or []:
        sid = _text(row.get("source_id"), "source_id")
        if not _ID.fullmatch(sid) or sid in sources:
            raise ValueError("Source IDs must be unique safe identifiers")
        text = _text(row.get("text"), "source.text")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if row.get("sha256") and str(row["sha256"]).removeprefix("sha256:") != digest:
            raise ValueError("Supplied source hash does not match source text")
        sources[sid] = {"source_id": sid, "text": text, "sha256": digest}
        if _INSTRUCTION.search(text):
            flags.append({"code": "source_instruction_present", "source_id": sid, "detail": "Instruction-like source content is retained only in review evidence and cannot act as a creative instruction."})
    if not sources:
        raise ValueError("Supply actual customer source content")

    def anchor(raw: Any, field: str) -> str:
        if not isinstance(raw, dict):
            raise ValueError(f"{field} needs a source anchor with text, source_id and quote")
        text = _text(raw.get("text"), field)
        quote = _text(raw.get("quote"), f"{field}.quote")
        source = sources.get(raw.get("source_id"))
        if not source or quote not in source["text"] or text not in quote:
            raise ValueError(f"{field} is not supported by an exact source quotation")
        if raw.get("source_sha256") and str(raw["source_sha256"]).removeprefix("sha256:") != source["sha256"]:
            raise ValueError(f"{field} source hash mismatch")
        if _INSTRUCTION.search(quote) or _STRONG_CLAIM.search(text) or _INTERNAL.search(text):
            raise ValueError(f"{field} requires a bounded source expression without instructions or unverified strong claims")
        # A substring can drop the qualification that made a source statement
        # accurate. Require those source qualifiers in the marketing expression.
        qualifiers = re.findall(r"\b(?:may|might|could|not|never|only|subject to|up to|approximately|estimated|no guarantee)\b", quote, re.I)
        if any(not re.search(r"\b" + re.escape(term) + r"\b", text, re.I) for term in qualifiers):
            raise ValueError(f"{field} drops a source qualification; retain the qualified expression")
        start = source["text"].find(quote)
        anchors[field] = {"text": text, "source_id": source["source_id"], "quote": quote, "source_sha256": source["sha256"], "start": start, "end": start + len(quote)}
        return text

    offer_raw, audience_raw = packet.get("offer") or {}, packet.get("audience") or {}
    offer = {key: anchor(offer_raw.get(key), f"offer.{key}") for key in ("name", "promise", "cta")}
    for key in ("short_name", "offer", "headline", "poster_cta", "cta_url"):
        if offer_raw.get(key):
            offer[key] = anchor(offer_raw[key], f"offer.{key}")
    offer.setdefault("short_name", offer["name"])
    offer.setdefault("offer", offer["name"])
    offer.setdefault("headline", offer["promise"])
    offer.setdefault("poster_cta", offer["cta"])
    audience = {key: anchor(audience_raw.get(key), f"audience.{key}") for key in ("name", "pain", "outcome")}
    accepted, held = [], []
    for index, row in enumerate(packet.get("approved_claims") or [], 1):
        try:
            if not row.get("approved_by"):
                raise ValueError("Customer approval owner not supplied")
            text = anchor(row, f"approved_claims.{index}")
            accepted.append({"text": text, "approval_claimed_by": row["approved_by"], "approval_independently_verified": False, "anchor": anchors[f"approved_claims.{index}"]})
        except ValueError as exc:
            held.append({**row, "reason": str(exc), "state": "held_out_of_marketing"})
    if offer.get("cta_url"):
        url = urlsplit(offer["cta_url"])
        if url.scheme not in {"https", "mailto"} or any(c in offer["cta_url"] for c in ("\r", "\n", "\t")) or re.search(r"%0[ad]", offer["cta_url"], re.I):
            raise ValueError("CTA destination must be a source-bound HTTPS or mailto URL")
        if url.scheme == "https" and (not url.hostname or url.username or url.password):
            raise ValueError("CTA destination cannot contain credentials or lack a host")
        if url.scheme == "mailto" and not re.fullmatch(r"[^\s@?]+@[^\s@?]+", url.path):
            raise ValueError("CTA mailto destination must contain a plain email address")
    else:
        flags.append({"code": "cta_destination_missing", "detail": "CTA intent is source bound but no destination was supplied; landing CTA is text pending customer contact details."})
    brand = packet.get("brand") or {}
    brand_path = Path(_text(brand.get("asset_path"), "brand.asset_path")).expanduser().resolve()
    if not brand_path.is_file() or brand_path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("Supply a customer image file no larger than 30 MiB")
    digest = _sha(brand_path)
    if str(brand.get("sha256") or "").removeprefix("sha256:") != digest:
        raise ValueError("Customer brand asset hash mismatch")
    with Image.open(brand_path) as image:
        if image.width * image.height > 25_000_000:
            raise ValueError("Customer brand image exceeds 25 megapixels")
        image.verify()
    accent = str(brand.get("accent") or "#e8b773")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", accent):
        raise ValueError("brand.accent must be a six-digit colour")
    configured = json.loads((ROOT / "config/marketing_audience_matrix.json").read_text())["channels"]
    channel_ids = packet.get("allowed_channels")
    if not isinstance(channel_ids, list) or not channel_ids or len(channel_ids) > 10 or len(set(channel_ids)) != len(channel_ids) or any(c not in configured for c in channel_ids):
        raise ValueError("allowed_channels must explicitly select known unique DIO channel profiles")
    product_id = "CUSTOMER-" + _digest(offer)[:12]
    offer.update({"id": product_id, "accent": accent, "proof": " ".join(c["text"] for c in accepted)})
    audience["id"] = "AUDIENCE-" + _digest(audience)[:12]
    start = date.fromisoformat(packet["planned_start"]) if packet.get("planned_start") else None
    owners = packet.get("approval_owners") or {}
    for owner in ("content", "brand", "release"):
        if not owners.get(owner):
            flags.append({"code": "approval_owner_missing", "role": owner, "detail": f"Customer must name the {owner} owner before release."})
    return {"title": str(packet.get("title") or offer["name"] + " launch kit"), "sources": list(sources.values()), "anchors": anchors,
            "offer": offer, "audience": audience, "accepted_claims": accepted, "held_claims": held,
            "brand": {"path": str(brand_path), "sha256": digest, "accent": accent, "rights_claim": brand.get("rights"), "rights_verified": False},
            "channels": {c: configured[c] for c in channel_ids}, "planned_start": start, "approval_owners": owners, "review_flags": flags}


def _choose(expressions: list[str], limit: int) -> str | None:
    return next((text for text in expressions if text and len(text) <= limit), None)


def _channel_copy(native, model, channel_id, profile, projection):
    product, audience = model["offer"], model["audience"]
    # Reuse the native copy mechanism for channel shape/tone, but its DIO house
    # boilerplate is not customer copy. Every final expression is replaced by a
    # complete source expression; no ellipsis or stronger paraphrase is allowed.
    candidate = native.copy_package(product, audience, channel_id, projection)
    headline = _choose([product["headline"], audience["outcome"], product["name"]], int(profile.get("headline_limit") or 100))
    body = _choose([" ".join([audience["pain"], product["promise"], product["cta"]]), " ".join([product["promise"], product["cta"]]), product["promise"]], int(profile.get("body_limit") or 1000))
    final = {"headline": headline, "body": body, "cta": product["cta"]}
    if channel_id == "GOOGLE_ADS":
        headlines = list(dict.fromkeys(t for t in (product["name"], product["headline"], product["cta"], audience["outcome"]) if len(t) <= int(profile["headline_limit"])))
        descriptions = list(dict.fromkeys(t for t in (product["promise"], audience["pain"], audience["outcome"]) if len(t) <= int(profile["description_limit"])))
        final = {"headlines": headlines, "descriptions": descriptions, "cta": product["cta"]}
        ready = bool(headlines and descriptions)
    else:
        ready = bool(headline and body)
        if profile.get("description_limit"):
            description = _choose([product["cta"], product["poster_cta"]], int(profile["description_limit"]))
            if description:
                final["description"] = description
            else:
                ready = False
    final = {k: value for k, value in final.items() if value is not None}
    errors = native.validate_copy(profile, final)
    if _INTERNAL.search(json.dumps(final)):
        raise ValueError("Internal governance wording entered customer marketing")
    return {"channel": channel_id, "copy": final, "tone": candidate.get("angle"), "configured_limits": {k: v for k, v in profile.items() if k.endswith("_limit")},
            "limits_passed": not errors and ready, "state": "copy_candidate" if not errors and ready else "held_for_source_bound_shorter_copy", "validation_errors": errors,
            "copy_boundary": "Complete source expressions composed without truncating claims or qualifications"}


def _poster_layout(native, source, size, product, audience, message, output, visual):
    width, height = size
    margin = max(42, round(width * 0.055))
    draw = ImageDraw.Draw(source)
    for label, text, font in (
        ("brand short name", product["short_name"].upper(), native._font(native.FONT_BOLD, max(24, round(width * .027)))),
        ("audience name", audience["name"], native._font(native.FONT_REGULAR, max(22, round(width * .022)))),
        ("poster CTA", product["poster_cta"], native._font(native.FONT_BOLD, max(22, round(width * .025)))),
    ):
        if draw.textbbox((0, 0), text, font=font)[2] > width - margin * 2 - (42 if label == "poster CTA" else 0):
            raise ValueError(f"{label} needs a shorter source-bound expression for the selected poster format")
    maximum = 4 if height > width else 3
    if len(native._wrap(draw, message, native._font(native.FONT_BOLD, 34), width - 2 * margin)) > maximum:
        # Replace a too-long creative angle with an intact, sourced short
        # headline rather than clipping a qualifier or shrinking illegibly.
        message = product["headline"]
        if len(native._wrap(draw, message, native._font(native.FONT_BOLD, 34), width - 2 * margin)) > maximum:
            raise ValueError("Poster needs a shorter source-bound headline")
    native.draw_poster(source, size, product, audience, output, message=message, footer=product["poster_cta"], visual_grammar=visual)
    return message


def _landing(model, hero_path):
    e = lambda text: html.escape(str(text), quote=True)
    product, audience = model["offer"], model["audience"]
    def cta():
        text = e(product["cta"])
        return f'<a class="button" href="{e(product["cta_url"])}">{text}</a>' if product.get("cta_url") else f'<p class="button">{text}</p>'
    claims = "".join(f'<li>{e(c["text"])}</li>' for c in model["accepted_claims"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(product['name'])}</title><meta name="description" content="{e(product['promise'])}"><link rel="stylesheet" href="styles.css"></head><body><main><nav><a class="wordmark" href="#top">{e(product['short_name'])}</a><span>{e(product['offer'])}</span></nav><section class="hero" id="top"><div class="hero-copy"><p class="eyebrow">{e(audience['name'])}</p><h1>{e(product['headline'])}</h1><p class="lead">{e(product['promise'])}</p>{cta()}</div><figure><img src="{e(hero_path)}" alt="Customer-supplied image for {e(product['name'])}"></figure></section><section class="details"><div><p class="eyebrow">The starting point</p><h2>{e(audience['pain'])}</h2></div><div><p class="eyebrow">What to expect</p><h2>{e(audience['outcome'])}</h2>{('<ul>'+claims+'</ul>') if claims else ''}</div></section><section class="contact"><h2>{e(product['name'])}</h2><p>{e(product['promise'])}</p>{cta()}</section><footer>{e(product['name'])}</footer></main></body></html>'''


def _media_preview(poster: Path, output: Path, narration_text: str) -> dict[str, Any]:
    from scripts.build_campaign_media_v3 import synthesize_pocket_story, _render_projected_format
    from products.canonical_marketing_media import approved_music
    output.parent.mkdir(parents=True, exist_ok=True)
    music = approved_music()
    narration = synthesize_pocket_story(
        [{"scene_id": "customer_offer", "narration": narration_text}], output.parent / "narration",
        {"required": True, "provider": "pocket_tts", "profile": "vera_pocket_public", "voice": "vera", "remote_tts_allowed": False})
    rendered = _render_projected_format(scene_images=[poster], narration=narration["scenes"], music=Path(music["path"]), music_volume=music["volume"], output=output, width=720, height=720, brand_owner="customer")
    shutil.copy2(music["attribution"], output.parent / "MUSIC_ATTRIBUTION.md")
    _json(output.parent / "MUSIC_RIGHTS_RECEIPT.json", music)
    return {**rendered, "kind": "vera_narrated_customer_poster_video", "voice": {"provider": "pocket_tts", "voice": "vera", "receipt": narration["receipt"]}, "music": music, "brand_owner": "customer", "customer_source_preserved": True}


def build_customer_launch_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_media: bool = False) -> dict[str, Any]:
    """Build owned creative files and public copy from source-quoted customer fields.

    Required packet keys: sources, offer{name,promise,cta}, audience{name,pain,
    outcome}, brand{asset_path,sha256}, allowed_channels. Text fields are anchors
    {text,source_id,quote,source_sha256?}. Never publishes or spends. Explicit render_media uses local Vera and verified music.
    """
    out = Path(output_dir).expanduser().resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("output_dir must be empty to prevent stale customer artifacts")
    model = _prepare(packet)
    native = _native_factory()
    law = build_semantic_law(model["offer"], model["audience"])
    projection = build_projection_plan(law, model["offer"], model["audience"], model["channels"])
    projection_errors = validate_projection(law, projection)
    if projection_errors:
        raise ValueError("Lingua semantic projection failed: " + "; ".join(projection_errors))
    stories = {surface: project_story(law, projection, model["offer"], model["audience"], surface) for surface in ("vertical_short", "landscape_explainer")}
    copy_rows = [_channel_copy(native, model, cid, profile, projection["channel_projections"][cid]) for cid, profile in model["channels"].items()]
    with Image.open(model["brand"]["path"]) as image:
        source = ImageOps.exif_transpose(image).convert("RGB")
    angles = [model["offer"]["promise"], model["audience"]["outcome"], model["audience"]["pain"]]
    # Preflight native layout in memory before creating a customer output tree.
    widths = []
    for cid, profile in model["channels"].items():
        asset = str(profile.get("asset") or "square_1080").replace("reel_", "vertical_")
        size = native.SIZES.get(asset, (1080, 1080))
        widths.append((cid, size))
    # Layout validation uses the actual native metrics, without writing files.
    # Source expressions are already bounded; failures leave no misleading kit.
    for cid, size in widths:
        width = size[0]; margin = max(42, round(width * .055)); draw = ImageDraw.Draw(source)
        for text, font_size, pad in ((model["offer"]["short_name"].upper(), max(24, round(width * .027)), 0),
                                    (model["audience"]["name"], max(22, round(width * .022)), 0),
                                    (model["offer"]["poster_cta"], max(22, round(width * .025)), 42)):
            if draw.textbbox((0, 0), text, font=native._font(native.FONT_BOLD, font_size))[2] > width - 2 * margin - pad:
                raise ValueError("Poster label/CTA needs a shorter source-bound expression")
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir()
    (out / "review").mkdir()
    hero = source.copy(); hero.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    hero.save(out / "assets/customer-image.jpg", quality=92)
    shutil.copy2(model["brand"]["path"], out / "review/customer-source-image.raw")
    creative_assets = []
    count = max(3, len(widths))
    for index in range(count):
        cid, size = widths[index % len(widths)]
        relative = f"assets/creative-{index+1:02d}-{cid.lower()}.png"
        message = _poster_layout(native, source, size, model["offer"], model["audience"], angles[index % 3], out / relative, projection["surfaces"]["vertical_short"]["visual_grammar"])
        creative_assets.append({"path": relative, "channel": cid, "kind": "owned_static_creative", "dimensions": list(size), "sha256": _sha(out / relative),
                                "source_image_sha256": model["brand"]["sha256"], "message": message, "cta": model["offer"]["poster_cta"]})
    (out / "landing.html").write_text(_landing(model, "assets/customer-image.jpg"), encoding="utf-8")
    (out / "styles.css").write_text('''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f0e7;color:#22271f;font:18px/1.6 system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:0 5vw}nav{display:flex;justify-content:space-between;gap:24px;align-items:center;padding:27px 0;border-bottom:1px solid #aaa79b}.wordmark{font-weight:900;font-size:1.3rem;color:inherit;text-decoration:none}nav span{font-size:.85rem}.hero{display:grid;grid-template-columns:1fr 1fr;gap:5vw;align-items:center;padding:70px 0}.eyebrow{font-size:.78rem;text-transform:uppercase;letter-spacing:.13em;font-weight:800;color:#59634b}h1{font-size:clamp(2.5rem,5.1vw,5.4rem);line-height:1.03;letter-spacing:-.045em;margin:18px 0 28px;overflow-wrap:anywhere}h2{font-size:clamp(1.65rem,2.4vw,2.7rem);line-height:1.16;letter-spacing:-.025em}.lead{max-width:40ch;font-size:1.13rem;color:#4c5545}.button{display:inline-block;background:#263e30;color:#fff;padding:16px 23px;margin:15px 0;border-radius:4px;text-decoration:none;font-weight:750;max-width:100%;overflow-wrap:anywhere}.button:focus-visible{outline:3px solid #c77a29;outline-offset:4px}figure{margin:0}figure img{display:block;width:100%;aspect-ratio:4/5;object-fit:cover;border-radius:90px 8px 8px 8px}.details{display:grid;grid-template-columns:1fr 1fr;gap:7vw;border-top:1px solid #aaa79b;padding:60px 0}.details ul{padding-left:24px}.contact{border-top:1px solid #aaa79b;padding:55px 0 65px;max-width:800px}footer{padding:25px 0;border-top:1px solid #aaa79b;font-size:.9rem;color:#59634b}@media(max-width:700px){main{padding:0 22px}nav{align-items:flex-start}nav span{max-width:38%;font-size:.75rem}.hero,.details{grid-template-columns:1fr}.hero{gap:35px;padding:38px 0}figure img{aspect-ratio:5/4;border-radius:45px 5px 5px 5px}.details{gap:22px;padding:35px 0}h1{font-size:2.9rem}.contact{padding:35px 0}}''', encoding="utf-8")
    _json(out / "channel_copy.json", {"channels": copy_rows})
    schedule = []
    for index, asset in enumerate(creative_assets):
        day_offset = (index // max(1, len(widths))) * 2
        planned_date = (model["planned_start"] + timedelta(days=day_offset)).isoformat() if model["planned_start"] else None
        schedule.append({"sequence": index + 1, "planned_date": planned_date, "day_offset": day_offset, "channel": asset["channel"], "creative": asset["path"],
                         "copy": "channel_copy.json", "approval_owners": model["approval_owners"], "status": "draft_not_scheduled", "publication_authorized": False})
    _json(out / "launch_schedule.json", {"schedule": schedule, "automatic_posting": False})
    with (out / "launch_schedule.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sequence", "planned_date", "day_offset", "channel", "creative", "status"])
        writer.writeheader();writer.writerows({k: row[k] for k in writer.fieldnames} for row in schedule)
    _json(out / "review/LINGUA_SEMANTIC_LAW.json", law)
    _json(out / "review/LINGUA_PROJECTION_PLAN.json", projection)
    _json(out / "review/LINGUA_STORY_PLANS.json", {"plans": stories, "public_copy": False, "narration_rendered": False})
    _json(out / "review/source_semantic_manifest.json", {"sources": model["sources"], "anchors": model["anchors"], "brand": model["brand"], "semantic_law_hash": law["semantic_law_hash"], "projection_hash": projection["projection_hash"],
                                                        "native_factory_source": str(FACTORY_SOURCE), "native_factory_sha256": _sha(FACTORY_SOURCE), "native_poster_namespace": native.__name__})
    _json(out / "review/reviewer_checklist.json", {"review_flags": model["review_flags"], "held_claims": model["held_claims"], "accepted_claims": model["accepted_claims"], "approval_owners": model["approval_owners"],
                                                 "checks": ["Confirm source meaning and customer-approved claims", "Confirm image rights, crop and legibility", "Confirm channel-specific copy and destination", "Approve dates and assign channel owners", "Authorise any publication separately"], "approval_status": "pending"})
    media = {"requested": render_media, "video_generated": False, "audio_generated": False, "voice_provider_called": False, "remote_generation_called": False}
    if render_media:
        preview = _media_preview(out / creative_assets[0]["path"], out / "assets/customer-offer-video.mp4", " ".join([model["offer"]["promise"], model["offer"]["cta"]]))
        preview["path"] = str(Path(preview["path"]).relative_to(out))
        media.update({"video_generated": True, "audio_generated": True, "voice_provider_called": True, "video": preview})
    result = {"schema": "dio.customer_launch_package.v1", "status": "review_candidate", "output_dir": str(out), "title": model["title"],
              "semantic_law_hash": law["semantic_law_hash"], "projection_hash": projection["projection_hash"], "creative_assets": creative_assets, "channel_copy": copy_rows, "schedule": schedule,
              "held_claims": model["held_claims"], "review_flags": model["review_flags"], "deliverables": {"landing_html": "landing.html", "channel_copy": "channel_copy.json", "launch_schedule": "launch_schedule.json", "source_semantic_manifest": "review/source_semantic_manifest.json"},
              "media": media, "output_formats": ["png", "jpg", "html", "css", "json", "csv"] + (["mp4_vera_narrated_customer_video"] if media["video_generated"] else []),
              "qa": {"projection_errors": projection_errors, "native_copy_limits_passed": all(row["limits_passed"] for row in copy_rows), "visual_review": "pending", "marketing_governance_boilerplate": False},
              "release": {"published": False, "scheduled_in_external_service": False, "spend_enabled": False, "canon_promoted": False, "customer_rights_verified": False}}
    result["artifacts"] = [{"path": str(p.relative_to(out)), "bytes": p.stat().st_size, "sha256": _sha(p)} for p in sorted(out.rglob("*")) if p.is_file()]
    _json(out / "package_manifest.json", result)
    with zipfile.ZipFile(out / "controlled_launch_review.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path.name != "controlled_launch_review.zip":
                archive.write(path, path.relative_to(out))
    return result
