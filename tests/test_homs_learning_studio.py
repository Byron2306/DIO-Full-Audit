from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_homs_learning_pack as learning  # noqa: E402
from scripts import finalize_homs_learning_video as video  # noqa: E402


PACK = ROOT / "deliverables" / "homs_learning_studio" / "grade_10_physical_sciences_term_3_motion"


class LearningPackContractTests(unittest.TestCase):
    def test_marks_match_the_declared_products(self) -> None:
        self.assertEqual(40, sum(item[2] for item in learning.WORKSHEET))
        self.assertEqual(30, sum(item[2] for item in learning.ASSESSMENT))

    def test_caps_evidence_is_available(self) -> None:
        evidence = learning.caps_evidence()
        self.assertEqual(4, len(evidence["evidence"]))
        self.assertTrue(Path(evidence["source"]).is_file())

    def test_golden_pack_and_video_are_validated_but_human_gated(self) -> None:
        validation = json.loads((PACK / "HOMS_LEARNING_PACK_VALIDATION.json").read_text(encoding="utf-8"))
        manifest = json.loads((PACK / "LEARNING_PACK_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertTrue(validation["passed"])
        self.assertTrue(validation["checks"]["video_lesson_present"])
        self.assertEqual("educator_review_required", manifest["status"])
        self.assertEqual("blocked_pending_educator_approval", manifest["video_lesson"]["publication"])
        self.assertTrue((PACK / manifest["video_lesson"]["path"]).is_file())

    def test_caption_time_format(self) -> None:
        self.assertEqual("01:01:01,125", video.srt_time(3661.125))


class LearningStudioSiteTests(unittest.TestCase):
    def test_homs_site_exposes_the_structured_learning_offer(self) -> None:
        site = (ROOT / "sites" / "homs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('value="learning_companion"', site)
        self.assertIn('data-offer="learning_companion"', site)
        self.assertIn("HOMS_G10_T3_MOTION_VIDEO_LESSON.mp4", site)
        self.assertIn("window.DIOPublicIntake.submit", site)
        self.assertIn("topic_or_assignment", site)

    def test_learning_campaign_route_preserves_attribution_and_selects_the_offer(self) -> None:
        route = (ROOT / "sites" / "homs" / "learning-studio" / "index.html").read_text(encoding="utf-8")
        site = (ROOT / "sites" / "homs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("new URLSearchParams(window.location.search)", route)
        self.assertIn('incoming.set("offer", "learning_companion")', route)
        self.assertIn('requestedOffer === "learning_companion"', site)
        self.assertIn('selectProofTab(document.querySelector("#learning-tab"))', site)


if __name__ == "__main__":
    unittest.main()
