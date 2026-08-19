#!/usr/bin/env python3
"""Compatibility entrypoint for the governed narrated NicheFoundry media pipeline.

The former implementation called the legacy caption-led, music-only reel engine.
All callers now resolve to v2, which requires Gamma-bound visuals, local Piper
narration, rights-recorded music, and both vertical and landscape MP4 outputs.
"""

from scripts.run_nichefoundry_media_pipeline_v2 import *  # noqa: F401,F403
from scripts.run_nichefoundry_media_pipeline_v2 import main


if __name__ == "__main__":
    raise SystemExit(main())
