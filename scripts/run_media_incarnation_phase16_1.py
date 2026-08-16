from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from products.media_incarnation import ACCEPTANCE_TOKEN
from products.media_incarnation_gauntlet import run_gauntlet

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path("state/media_incarnation/phase16_1"))
    result=run_gauntlet(output_dir=parser.parse_args().output)
    keys=("native_nichefoundry_execution","ad_asset_rendering","carousel_rendering","thumbnail_rendering",
      "youtube_script_completeness","narration_rendering","caption_alignment","video_rendering","sophia_media_review",
      "evidex_asset_provenance","deterministic_generation","canonical_output_integrity","tamper_detection","network_used",
      "external_publication","media_spend","external_send","human_gate","video_duration_seconds")
    print(json.dumps({key:result[key] for key in keys},indent=2,sort_keys=True));print(ACCEPTANCE_TOKEN);return 0
if __name__=="__main__":raise SystemExit(main())

