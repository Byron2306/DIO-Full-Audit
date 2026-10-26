#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edge_tts_runtime import configure_edge_tts_environment

# Production Studio runs as a user systemd service, whose PATH may omit
# ~/.local/bin even when an interactive shell can resolve edge-tts. Hydrate the
# explicit executable binding before the v3 factory imports its media executor.
configure_edge_tts_environment()

from scripts import build_multichannel_campaign_factory_v3 as _v3
from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law, validate_projection
from lingua.storyline_planner import project_story as project_story_semantic_anti_clone
from scripts.gamma_primary_visual_bridge import install_gamma_primary_visual_bridge
from scripts.lingua_music_projection import select_projection_music
from scripts.local_compositor_identity_bridge import install_local_compositor_identity_bridge
from scripts.nichefoundry_visual_spine import install_visual_spine

# Production Studio namespaces a reusable marketing profile with the exact
# portfolio incarnation before LINGUA appends the audience id. The local visual
# compositor resolves visual/source profile from the first segment and audience
# from the final segment while preserving the middle exact-incarnation lineage.
install_local_compositor_identity_bridge()

# LINGUA owns semantic allocation across story beats. Semantic invariants are
# preserved by the story contract, not mechanically repeated as narration after
# every scene. Refuse substantive duplicate narration before media execution.
_v3.project_story = project_story_semantic_anti_clone

# LINGUA projection owns music fitness. Merely having a rights-cleared track is
# not enough: zero-semantic-match reuse would recreate the old one-track clone.
_v3._select_music = select_projection_music

# LINGUA decides lawful representational meaning; Document Studio compiles the
# visual language; BEAST contributes only human-approved representational memory;
# Document Studio local composition remains a governed fallback; NicheFoundry
# executes voice, music and real motion; Gamma may provide art-directed scene
# visuals when the operator explicitly enables DIO_GAMMA_VISUAL_CANDIDATE.
install_visual_spine(_v3)
install_gamma_primary_visual_bridge(_v3)

from scripts.build_multichannel_campaign_factory_v3 import *  # noqa: E402,F401,F403


# Production Studio v3 added an explicit channel_projection argument to
# copy_package. Older native Studio executors legitimately call the public
# factory wrapper with the original three-argument contract. Preserve that
# contract by deriving the missing projection through the current LINGUA law,
# rather than fabricating a tone or bypassing semantic governance.
_copy_package_v3 = _v3.copy_package


def copy_package(
    product: dict[str, Any],
    audience: dict[str, Any],
    channel_id: str,
    channel_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if channel_projection is None:
        law = build_semantic_law(product, audience)
        projection = build_projection_plan(
            law,
            product,
            audience,
            {channel_id: {"format": "studio_native_activation"}},
        )
        errors = validate_projection(law, projection)
        if errors:
            raise ValueError("LINGUA channel projection invalid: " + "; ".join(errors))
        channel_projection = dict(projection["channel_projections"][channel_id])
    return _copy_package_v3(product, audience, channel_id, channel_projection)


if __name__ == "__main__":
    raise SystemExit(main())
