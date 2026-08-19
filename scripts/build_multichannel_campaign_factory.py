#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edge_tts_runtime import configure_edge_tts_environment

# Production Studio runs as a user systemd service, whose PATH may omit
# ~/.local/bin even when an interactive shell can resolve edge-tts. Hydrate the
# explicit executable binding before the v3 factory imports its media executor.
configure_edge_tts_environment()

from scripts import build_multichannel_campaign_factory_v3 as _v3
from scripts.lingua_music_projection import select_projection_music
from scripts.nichefoundry_visual_spine import install_visual_spine

# LINGUA projection owns music fitness. Merely having a rights-cleared track is
# not enough: zero-semantic-match reuse would recreate the old one-track clone.
_v3._select_music = select_projection_music

# LINGUA decides lawful representational meaning; Document Studio compiles the
# visual language; BEAST contributes only human-approved representational memory;
# NicheFoundry/Gamma execute; the media renderer must execute real motion.
install_visual_spine(_v3)

from scripts.build_multichannel_campaign_factory_v3 import *  # noqa: E402,F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
