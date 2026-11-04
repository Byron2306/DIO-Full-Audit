from products.sonoris_music_direction import direction_for_video, score_track
from scripts.lingua_music_projection import select_projection_music


def test_narrated_warm_ad_prefers_supportive_music():
    surface = {"pacing": "brisk", "voice": {"required": True},
               "music": {"family": "warm_upbeat", "keywords": ["warm"], "volume": 0.1}}
    choice = select_projection_music(surface, {"name": "Assessment Desk"},
                                     {"name": "Teachers"}, "assessment-teachers")
    assert choice["title"] == "Warm Sunset by MusicLFiles"
    assert choice["sonoris_direction"]["role"] == "support_narration_and_scene_transitions"
    assert choice["sonoris_selection"]["components"]["narration_space"] == 3


def test_dense_trailer_loses_narration_fit_even_with_matching_mood():
    direction = direction_for_video({"pacing": "deliberate", "voice": {"required": True},
                                     "music": {"family": "restrained_investigative"}})
    quiet = score_track(direction, {"music_traits": {"moods": ["serious"], "arcs": ["tense"],
                                                   "energy": 1, "voice_space": "high"}})
    trailer = score_track(direction, {"music_traits": {"moods": ["serious"], "arcs": ["tense"],
                                                     "energy": 3, "voice_space": "low"}})
    assert quiet["score"] > trailer["score"]
