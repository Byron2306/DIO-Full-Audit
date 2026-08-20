from __future__ import annotations

import json
from pathlib import Path

from adapters.document_studio.art_direction import ANTI_PATTERNS
from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law
from products.studio_full_grade_convergence import _fixture_manuscript, _site_visual_qa


ROOT = Path(__file__).resolve().parents[1]


def _site_law_projection():
    product = {
        "id": "site_studio",
        "name": "Karoo Research Advisory",
        "offer": "research advisory",
        "promise": "A credible evidence-led public presence.",
        "proof": "Proof objects remain inspectable.",
        "cta": "Discuss the work",
    }
    audience = {
        "id": "research-buyer",
        "name": "South African research consultancy",
        "pain": "Research is trapped in unclear reports.",
        "outcome": "Make expertise and evidence boundaries understandable.",
    }
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, {"WEBSITE": {"format": "responsive_site"}})
    return law, projection


def test_site_full_grade_qa_requires_design_law_and_rejects_saas_grid():
    law, projection = _site_law_projection()
    art = {
        "art_direction_hash": "sha256:test",
        "anti_patterns": list(ANTI_PATTERNS),
        "scenes": [
            {"layout_family": "full_bleed_hook"},
            {"layout_family": "context_observation"},
            {"layout_family": "process_reveal"},
            {"layout_family": "proof_closeup"},
            {"layout_family": "human_handoff"},
        ],
    }
    html = '<html><head><meta name="viewport" content="width=device-width"></head><body><main>Proof & provenance <a href="proof/SITE_PROOF_MANIFEST.json">proof</a></main></body></html>'
    good = _site_visual_qa(law=law, projection=projection, art=art, html_text=html, css_text="@media(max-width:800px){.x{display:block}}")
    assert good["passed"] is True

    bad = _site_visual_qa(
        law=law,
        projection=projection,
        art=art,
        html_text=html,
        css_text=".grid{grid-template-columns:repeat(3,1fr)} @media(max-width:800px){.grid{display:block}}",
    )
    assert bad["passed"] is False
    assert bad["checks"]["saas_repeat_grid_not_hardcoded"] is False


def test_article_controlled_fixture_is_manuscript_shaped_and_reference_bound():
    manifest = json.loads((ROOT / "config/studio_harvest/article_publication_studio.json").read_text(encoding="utf-8"))
    manuscript = _fixture_manuscript(manifest)
    assert len(manuscript.split()) >= 40
    assert "## References" in manuscript
    assert "Mokoena" in manuscript
    assert "Naidoo" in manuscript
    assert "Traceable source lineage" in manuscript
    assert "Publication authority remains a separate decision" in manuscript
