from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from portfolio_runtime import ROOT
from products.professional_evidence_projection import evidence_rows, sha256, slug, write_json


COMPAT_SCHEMA = "dio.professional_evidence.customer_surface_compat.v1"
VAMP_DOMAIN_PRIORITY = ("RESEARCH", "TEACHING", "ENGAGEMENT", "LEADERSHIP", "DEVELOPMENT")
VAMP_DOMAIN_TERMS = {
    "RESEARCH": {"research", "publication", "article", "manuscript", "scholarship", "grant", "journal", "output"},
    "TEACHING": {"teaching", "module", "curriculum", "assessment", "student", "learner", "timetable", "supervision"},
    "ENGAGEMENT": {"community", "engagement", "service", "outreach", "industry", "professional service"},
    "LEADERSHIP": {"leadership", "committee", "coordination", "coordinator", "appointment", "governance", "management"},
    "DEVELOPMENT": {"training", "cpd", "registration", "ethics", "compliance", "certificate", "development"},
}
CAMPAIGN_ROLE_VISUAL_KINDS = {
    "question": ("research_workbench", "decision_landscape"),
    "hook": ("research_workbench", "decision_landscape"),
    "problem": ("decision_landscape", "research_workbench"),
    "workflow_demo": ("method_map", "communication_outputs"),
    "proof": ("provenance_stack", "evidence_network"),
    "boundary": ("human_review_scene", "provenance_stack"),
    "cta": ("bounded_action", "research_workbench"),
}
CAMPAIGN_FILE_MATERIAL_KINDS = {"curated_photo", "curated_illustration", "generated_editorial", "artifact_render"}


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _tokens(value: Any) -> set[str]:
    return {part for part in re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split() if part}


def _merge_reference_text(embedded: str, supplied: str) -> str:
    rows = [str(value or "").strip() for value in (embedded, supplied) if str(value or "").strip()]
    return "\n\n".join(rows)


def _sophia_reference_wrapper(original: Callable[..., Path]) -> Callable[..., Path]:
    """Bind a sibling customer references.txt into Sophia's local reference audit only.

    The manuscript bytes sent to the review lane are not modified. The extra reference
    evidence expands only the closed-world citation allow-set used by the deterministic
    local audit and grounded commentary validator.
    """

    def run_review(request: dict[str, Any], request_path: Path, out_root: Path, base_url: str, sophia_root: Path) -> Path:
        from adapters.sophia import review_pipeline

        raw_document = Path(str(request.get("document_path") or "")).expanduser()
        document = raw_document if raw_document.is_absolute() else (Path(request_path).parent / raw_document)
        document = document.resolve()
        references = document.parent / "references.txt"
        if not references.is_file():
            return original(request, request_path, out_root, base_url, sophia_root)

        supplied = references.read_text(encoding="utf-8", errors="replace").strip()
        if not supplied:
            return original(request, request_path, out_root, base_url, sophia_root)
        manuscript_text = review_pipeline.extract_document_text(document)[0]
        original_split = review_pipeline.split_reference_section

        def split_with_customer_references(text: str) -> tuple[str, str]:
            body, embedded = original_split(text)
            if text == manuscript_text:
                return body, _merge_reference_text(embedded, supplied)
            return body, embedded

        binding = {
            "schema": "dio.sophia.customer_reference_binding.v1",
            "manuscript": str(document),
            "manuscript_sha256": "sha256:" + sha256(document),
            "reference_evidence": str(references),
            "reference_evidence_sha256": "sha256:" + sha256(references),
            "reference_evidence_role": "closed_world_local_reference_audit_only",
            "manuscript_bytes_modified": False,
            "citation_validator_weakened": False,
            "authority_created": False,
            "external_effects": False,
        }
        binding["binding_fingerprint"] = _fingerprint(binding)
        write_json(Path(request_path).resolve().parent / "SOPHIA_REFERENCE_BINDING.json", binding)

        review_pipeline.split_reference_section = split_with_customer_references
        try:
            return original(request, request_path, out_root, base_url, sophia_root)
        finally:
            review_pipeline.split_reference_section = original_split

    return run_review


def _vamp_domain(record: str) -> str:
    tokens = _tokens(record)
    lowered = " ".join(str(record or "").casefold().split())
    scores: dict[str, int] = {}
    for domain in VAMP_DOMAIN_PRIORITY:
        score = 0
        for term in VAMP_DOMAIN_TERMS[domain]:
            if " " in term:
                if term in lowered:
                    score += 3
            elif term in tokens:
                score += 2
        scores[domain] = score
    best = max(scores.values(), default=0)
    if best <= 0:
        return "DEVELOPMENT"
    return next(domain for domain in VAMP_DOMAIN_PRIORITY if scores[domain] == best)


def _build_vamp_database_v2(packet: dict[str, Any], target: Path) -> Path:
    """Project customer records into the actual domain vocabulary VAMP accepts."""

    rows = evidence_rows(packet)
    evidence_dir = target.parent / "vamp_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    con = sqlite3.connect(target)
    con.executescript(
        """
        CREATE TABLE tasks(task_id TEXT PRIMARY KEY,kpa_code TEXT NOT NULL,title TEXT NOT NULL,window_start TEXT NOT NULL,window_end TEXT NOT NULL,cadence TEXT NOT NULL,min_required INTEGER NOT NULL,stretch_target INTEGER NOT NULL,lead_lag TEXT NOT NULL,hints_json TEXT NOT NULL);
        CREATE TABLE evidence(evidence_id TEXT PRIMARY KEY,sha1 TEXT,staff_id TEXT NOT NULL,year INTEGER NOT NULL,month_bucket TEXT NOT NULL,kpa_code TEXT,rating TEXT,tier TEXT,file_path TEXT NOT NULL,meta_json TEXT NOT NULL);
        CREATE TABLE evidence_task(evidence_id TEXT NOT NULL,task_id TEXT NOT NULL,mapped_by TEXT NOT NULL,confidence REAL NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(evidence_id,task_id));
        CREATE TABLE task_no_evidence(staff_id TEXT NOT NULL,year INTEGER NOT NULL,task_id TEXT NOT NULL,month TEXT NOT NULL,reason TEXT,declared_at TEXT NOT NULL,PRIMARY KEY(staff_id,year,task_id,month));
        """
    )
    projection: list[dict[str, Any]] = []
    from products.professional_evidence_execution import utc_now

    for index, row in enumerate(rows, 1):
        record = str(row.get("customer_supplied_record") or "").strip()
        task = f"PRO-TASK-{index:02d}"
        evidence = f"PRO-E-{index:02d}"
        domain = _vamp_domain(record)
        path = evidence_dir / f"record_{index:02d}.txt"
        path.write_text(record + "\n", encoding="utf-8")
        meta = {
            "target_task_id": task,
            "customer_packet_fingerprint": packet["packet_fingerprint"],
            "profile_domain_projection": domain,
            "rating_authority_created": False,
        }
        con.execute(
            "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)",
            (task, domain, record[:120], "2026-01-01", "2026-08-31", "review_period", 1, 1, "lag", "{}"),
        )
        con.execute(
            "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
            (evidence, sha256(path)[:40], "PROFESSIONAL-001", 2026, "2026-08", domain, "", "", str(path), json.dumps(meta, sort_keys=True)),
        )
        con.execute("INSERT INTO evidence_task VALUES(?,?,?,?,?)", (evidence, task, "customer_packet_domain_projection", 1.0, utc_now()))
        projection.append({"record_id": row.get("record_id"), "task_id": task, "evidence_id": evidence, "domain": domain, "record": record})
    con.commit()
    con.close()
    write_json(
        target.parent / "VAMP_DOMAIN_PROJECTION.json",
        {
            "schema": "dio.professional_evidence.vamp_domain_projection.v1",
            "packet_fingerprint": packet["packet_fingerprint"],
            "profile_id": "university_generic_v1",
            "allowed_domains": list(VAMP_DOMAIN_PRIORITY),
            "rows": projection,
            "rating_authority_created": False,
            "human_review_required": True,
        },
    )
    return target


def _markdown_blocks(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append({"type": "paragraph", "text": " ".join(paragraph).strip()})
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            blocks.append({"type": "bullet_list", "items": list(bullets)})
            bullets.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_bullets()
            continue
        heading = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            flush_bullets()
            blocks.append({"type": "heading", "level": min(4, len(heading.group(1))), "text": heading.group(2).strip()})
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if bullet:
            flush_paragraph()
            bullets.append(bullet.group(1).strip())
            continue
        flush_bullets()
        paragraph.append(re.sub(r"\*\*(.*?)\*\*", r"\1", line).strip())
    flush_paragraph()
    flush_bullets()
    return blocks


def _semantic_from_markdown(path: Path, *, object_id: str, title: str, artifact_type: str) -> dict[str, Any]:
    source_blocks = _markdown_blocks(path.read_text(encoding="utf-8", errors="replace"))
    blocks: list[dict[str, Any]] = []
    for index, block in enumerate(source_blocks, 1):
        row = {**block, "block_id": f"B{index:03d}"}
        blocks.append(row)
    if not blocks:
        raise RuntimeError(f"HOMS customer document is empty: {path}")
    return {
        "schema": "dio.semantic_content.v1",
        "object_id": object_id,
        "version": "1.0.0",
        "title": title,
        "source_language": "en",
        "context": {
            "product": "HOMS Exam",
            "artifact_type": artifact_type,
            "audience": "assessment coordinator and educator",
            "subject": "History",
            "grade": "11",
        },
        "blocks": blocks,
        "translations": {},
    }


def _homs_exam_surface_wrapper(original: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def run_homs_exam(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
        from adapters.format_core.renderer import render_semantic_asset

        result = original(packet, output_dir, now=now)
        render_root = output_dir / "CUSTOMER_FORMAT_CORE"
        specs = [
            (output_dir / "HOMS_EXAM_PAPER.md", "homs-exam-paper", "Grade 11 History Mid-Year Examination", "exam_paper"),
            (output_dir / "HOMS_EXAM_MEMORANDUM.md", "homs-exam-memorandum", "Grade 11 History Mid-Year Examination Memorandum", "memorandum"),
        ]
        rendered: list[dict[str, Any]] = []
        for source, object_id, title, artifact_type in specs:
            if not source.is_file():
                raise RuntimeError(f"HOMS Exam finishing source missing: {source.name}")
            semantic = _semantic_from_markdown(source, object_id=object_id, title=title, artifact_type=artifact_type)
            destination = render_root / object_id
            receipt = render_semantic_asset(
                semantic,
                destination,
                style_profile="dio_professional",
                delivery_profile="editable_review",
                language="en",
                channels=["docx", "html"],
                release_mode=False,
                source_root=ROOT,
            )
            rendered.append({"source": source.name, "object_id": object_id, "format_core_receipt": receipt})
        receipt = dict((result or {}).get("receipt") or {})
        receipt["customer_format_core"] = {
            "schema": "dio.homs_exam.customer_format_composition.v1",
            "rendered": rendered,
            "channels": ["docx", "html"],
            "format_core_authority": "DIO_FORMAT_CORE",
            "human_release": "NEEDS_YOU",
            "automatic_publication": "REFUSE",
        }
        receipt["customer_presentation_ready_for_review"] = True
        write_json(output_dir / "HOMS_EXAM_RECEIPT.json", receipt)
        return {**result, "receipt": receipt}

    return run_homs_exam


def _evidex_contextual_intake(original: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def build_intake(job: dict[str, Any]) -> dict[str, Any]:
        intake = original(job)
        context = dict(job.get("customer_context") or {})
        if not context:
            return intake
        organisation = str(context.get("organisation") or "").strip()
        if organisation:
            intake.setdefault("client", {})["organization"] = organisation
        reporting = dict(context.get("reporting_period") or {})
        start = str(reporting.get("start") or "").strip() or "Not supplied by customer"
        end = str(reporting.get("end") or "").strip() or "Not supplied by customer"
        intake.setdefault("pack", {}).setdefault("reporting_period", {})["start"] = start
        intake["pack"]["reporting_period"]["end"] = end
        gaps = list((intake.get("constraints") or {}).get("known_gaps") or [])
        gaps = [row for row in gaps if "Client organization" not in str(row)]
        if start == "Not supplied by customer" or end == "Not supplied by customer":
            gaps.append("Reporting period was not supplied by the customer and remains a human intake requirement before dated donor submission.")
        intake.setdefault("constraints", {})["known_gaps"] = gaps
        return intake

    return build_intake


def _evidex_executor(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.run_evidex_jobs import EVIDEX_PYTHON, run_evidex
    from products.professional_evidence_execution import utc_now

    if not EVIDEX_PYTHON.is_file():
        raise FileNotFoundError(f"Evidex runtime missing: {EVIDEX_PYTHON}")
    rows = evidence_rows(packet)
    body = "\n".join(str(row.get("customer_supplied_record") or "") for row in rows)
    customer = dict((packet.get("intake") or {}).get("customer") or {})
    organisation = str(customer.get("organisation") or "").strip() or "Customer organisation not supplied"
    buyer_role = str(customer.get("buyer_role") or "").strip() or "Professional customer"
    job = {
        "job_id": "PRO-EVIDEX-EVIDENCEOPS-001",
        "created_at": utc_now(),
        "route": {"product": "evidex", "confidence": 1.0, "reason": "Explicit Professional Evidence Portfolio route"},
        "risk": "moderate",
        "customer_context": {
            "organisation": organisation,
            "buyer_role": buyer_role,
            "reporting_period": {},
            "truth_boundary": "Missing reporting dates remain missing; no date is fabricated for customer-surface completeness.",
        },
        "inputs": [{
            "sender": f"{buyer_role} <customer-contact-not-supplied>",
            "subject": packet["intake"]["request"],
            "attachment_names": "customer evidence register",
            "intent": "evidence_pack",
            "urgency": "normal",
            "next_step": "prepare governed evidence pack",
        }],
        "evidence": [{"text_extract": body}],
    }
    write_json(execution_dir.parent / "PROJECTION" / "EVIDEX_JOB.json", job)
    receipt = run_evidex(job, execution_dir)
    if int(receipt.get("returncode", 1)) != 0:
        raise RuntimeError(f"Evidex engine failed: {str(receipt.get('stderr') or '')[-500:]}")
    output_dir = Path(str(receipt.get("output_dir") or ""))
    if not output_dir.is_dir() or not any(output_dir.rglob("*")):
        raise RuntimeError("Evidex returned success without a professional output pack")
    return {
        "executor": "scripts.run_evidex_jobs.run_evidex + customer-context projection",
        "product_id": "evidex",
        "terminal_artifact_kind": "evidence_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": {**receipt, "customer_context_bound": True, "authority_created": False, "external_effects": False},
    }


def _campaign_material_candidates() -> list[dict[str, Any]]:
    from adapters.format_core.visual_material_registry import load_visual_material_registry, validate_visual_material

    try:
        registry = load_visual_material_registry(root=ROOT)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for raw in registry.get("materials") or []:
        material = dict(raw)
        validation = validate_visual_material(material, root=ROOT)
        if not validation.get("selectable") or material.get("material_kind") not in CAMPAIGN_FILE_MATERIAL_KINDS:
            continue
        payload = dict(material.get("payload") or {})
        path = (ROOT / str(payload.get("path") or "")).resolve()
        if not path.is_file():
            continue
        composition = dict(material.get("composition") or {})
        if composition.get("crop_safe") is not True:
            continue
        rows.append({**material, "_path": path})
    return rows


def _campaign_material_for_role(role: str, candidates: list[dict[str, Any]], used: set[str]) -> dict[str, Any] | None:
    desired = set(CAMPAIGN_ROLE_VISUAL_KINDS.get(role, ()))
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for material in candidates:
        material_id = str(material.get("material_id") or "")
        if material_id in used:
            continue
        kinds = set(material.get("semantic_visual_kinds") or [])
        score = len(desired & kinds) * 100
        if material.get("material_kind") == "curated_photo":
            score += 20
        if material.get("material_kind") == "artifact_render" and role in {"proof", "workflow_demo"}:
            score += 35
        ranked.append((score, material_id, material))
    if not ranked:
        return None
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked[0][2]


def _campaign_frames_with_material_pool(
    original: Callable[..., dict[str, Any]],
    *,
    story: dict[str, Any],
    art_direction: dict[str, Any],
    directory: Path,
    selection_log: list[dict[str, Any]],
) -> dict[str, Any]:
    from PIL import Image
    from adapters.document_studio import local_media_compositor as compositor

    if not str(story.get("family_id") or "").startswith("PROFESSIONAL_CAMPAIGN_LAB--"):
        return original(story=story, art_direction=art_direction, directory=directory)
    candidates = _campaign_material_candidates()
    if len(candidates) < 2:
        receipt = original(story=story, art_direction=art_direction, directory=directory)
        selection_log.append({
            "surface": story.get("surface"),
            "state": "FALLBACK_SINGLE_SOURCE",
            "material_ids": [],
            "distinct_material_count": 0,
            "human_visual_release": "NEEDS_YOU",
        })
        return receipt

    product, audience = compositor.resolve_product_audience(str(story.get("family_id") or ""))
    surface = str(story.get("surface") or "campaign_story")
    size = (1080, 1920) if surface == "vertical_short" else (1280, 720)
    art_scenes = list(art_direction.get("scenes") or [])
    story_scenes = list(story.get("scenes") or [])
    if len(art_scenes) != len(story_scenes) or not art_scenes:
        raise RuntimeError("Campaign material composition requires art direction for every scene")

    assets = directory / "assets"
    frames: list[dict[str, Any]] = []
    used: set[str] = set()
    scene_materials: list[dict[str, Any]] = []
    for index, (story_scene, art_scene) in enumerate(zip(story_scenes, art_scenes, strict=True), 1):
        role = str(story_scene.get("role") or f"scene_{index:02d}")
        material = _campaign_material_for_role(role, candidates, used)
        if material is None:
            used.clear()
            material = _campaign_material_for_role(role, candidates, used)
        if material is None:
            raise RuntimeError("Approved campaign visual material pool became empty")
        material_id = str(material.get("material_id") or "")
        used.add(material_id)
        role_slug = "-".join(part for part in re.sub(r"[^a-z0-9]+", "-", role.casefold()).split("-") if part)
        output = assets / f"{surface}_{index:02d}_{role_slug}.jpg"
        frame_scene = {**story_scene, **art_scene, "role": role}
        source = Image.open(Path(material["_path"]))
        rendered = compositor.render_art_directed_scene(
            source=source,
            size=size,
            product=product,
            audience=audience,
            scene=frame_scene,
            art_language=dict(art_direction.get("art_language") or {}),
            output=output,
            scene_index=index,
            art_direction_hash=str(art_direction.get("art_direction_hash") or ""),
        )
        rendered["visual_material_id"] = material_id
        rendered["visual_material_kind"] = material.get("material_kind")
        frames.append(rendered)
        scene_materials.append({
            "scene_id": story_scene.get("scene_id"),
            "role": role,
            "material_id": material_id,
            "material_kind": material.get("material_kind"),
            "semantic_visual_kinds": material.get("semantic_visual_kinds") or [],
            "registry_surface_suitability": material.get("surface_suitability") or [],
            "campaign_use_state": "CANDIDATE_NEEDS_YOU",
        })

    distinct = len({row["material_id"] for row in scene_materials})
    receipt = {
        "schema": "dio.document_studio.local_story_composition.v2",
        "state": "ready",
        "family_id": story.get("family_id"),
        "surface": surface,
        "art_direction_hash": art_direction.get("art_direction_hash"),
        "frame_count": len(frames),
        "frames": frames,
        "visual_material_selection": {
            "state": "PASS" if distinct >= 2 else "REFUSE",
            "distinct_material_count": distinct,
            "scene_materials": scene_materials,
            "selection_basis": "Format Core approved licensed crop-safe material registry; semantic visual kind fit preferred; campaign suitability remains human-reviewed",
            "human_visual_release": "NEEDS_YOU",
        },
        "governance": {
            "semantic_authority_created": False,
            "release_authority_created": False,
            "human_visual_release": "NEEDS_YOU",
            "gamma_required": False,
        },
    }
    receipt_path = directory / f"DOCUMENT_STUDIO_LOCAL_COMPOSITION_{surface.upper()}.json"
    write_json(receipt_path, receipt)
    receipt["receipt"] = str(receipt_path.resolve())
    selection_log.append({
        "surface": surface,
        "state": receipt["visual_material_selection"]["state"],
        "material_ids": [row["material_id"] for row in scene_materials],
        "distinct_material_count": distinct,
        "human_visual_release": "NEEDS_YOU",
    })
    return receipt


def _campaign_surface_wrapper(original_campaign: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def run_campaign(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
        from adapters.document_studio import local_media_compositor
        from scripts import nichefoundry_visual_spine

        local_original = local_media_compositor.render_story_frames
        spine_original = nichefoundry_visual_spine.render_story_frames
        selection_log: list[dict[str, Any]] = []

        def render_frames(*, story: dict[str, Any], art_direction: dict[str, Any], directory: Path) -> dict[str, Any]:
            return _campaign_frames_with_material_pool(
                local_original,
                story=story,
                art_direction=art_direction,
                directory=directory,
                selection_log=selection_log,
            )

        local_media_compositor.render_story_frames = render_frames
        nichefoundry_visual_spine.render_story_frames = render_frames
        try:
            result = original_campaign(packet, execution_dir)
        finally:
            local_media_compositor.render_story_frames = local_original
            nichefoundry_visual_spine.render_story_frames = spine_original

        distinct = len({material_id for row in selection_log for material_id in row.get("material_ids") or []})
        diversity_pass = bool(selection_log) and all(row.get("state") == "PASS" for row in selection_log) and distinct >= 2
        receipt = dict((result or {}).get("receipt") or {})
        receipt["customer_visual_material_composition"] = {
            "schema": "dio.campaign_lab.customer_visual_material_composition.v1",
            "surfaces": selection_log,
            "distinct_visual_material_count": distinct,
            "visual_material_diversity_pass": diversity_pass,
            "human_visual_release": "NEEDS_YOU",
            "automatic_publication": "REFUSE",
            "authority_created": False,
        }
        receipt["visual_material_diversity_pass"] = diversity_pass
        receipt["distinct_visual_material_count"] = distinct
        write_json(execution_dir / "PROFESSIONAL_CAMPAIGN_LAB_RECEIPT.json", receipt)
        return {**result, "receipt": receipt}

    return run_campaign


def install_customer_surface_compat() -> None:
    """Install Alpha customer-surface repairs without replacing domain organs."""

    from adapters.sophia import review_pipeline
    from products import professional_evidence_execution as execution
    from products import professional_evidence_executor as executor
    from scripts import run_evidex_jobs

    if getattr(executor, "_dio_customer_surface_compat_installed", False):
        return

    # Sophia keeps its strict closed-world validator. Only customer-supplied
    # reference evidence is added to the local reference audit allow-set.
    if not getattr(review_pipeline, "_dio_customer_reference_binding_installed", False):
        review_pipeline.run_review = _sophia_reference_wrapper(review_pipeline.run_review)
        review_pipeline._dio_customer_reference_binding_installed = True

    # VAMP receives its own profile vocabulary rather than the unsupported
    # synthetic PROFESSIONAL KPA code used by the earlier test projection.
    execution._build_vamp_database = _build_vamp_database_v2

    # HOMS remains the semantic exam constructor; Format Core owns the customer
    # document finish in DOCX + responsive/printable HTML review candidates.
    executor.run_homs_exam = _homs_exam_surface_wrapper(executor.run_homs_exam)

    # Evidex receives literal customer identity from the packet. Missing reporting
    # dates stay explicitly missing rather than remaining template placeholders.
    run_evidex_jobs.build_intake = _evidex_contextual_intake(run_evidex_jobs.build_intake)
    executor._run_evidex = _evidex_executor

    # Preserve the existing LINGUA anti-clone + Document Studio + NicheFoundry
    # campaign route, but give its local compositor a governed material pool.
    executor._run_campaign_lab = _campaign_surface_wrapper(executor._run_campaign_lab)

    executor._dio_customer_surface_compat_installed = True


__all__ = [
    "CAMPAIGN_ROLE_VISUAL_KINDS",
    "COMPAT_SCHEMA",
    "VAMP_DOMAIN_PRIORITY",
    "_build_vamp_database_v2",
    "_campaign_material_for_role",
    "_evidex_contextual_intake",
    "_markdown_blocks",
    "_merge_reference_text",
    "_semantic_from_markdown",
    "_vamp_domain",
    "install_customer_surface_compat",
]
