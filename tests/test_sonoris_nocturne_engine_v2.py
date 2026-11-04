import json
import tempfile
import unittest
from pathlib import Path
from products.sonoris_nocturne_engine_v2 import validate_score, render_score

ROOT = Path(__file__).resolve().parents[1]
SCORE = ROOT / 'media/sonoris/scores/DICERE_NOCTURNE_NATIVE_V2.json'
if not SCORE.exists():
    SCORE = ROOT / 'scores/DICERE_NOCTURNE_NATIVE_V2.json'

class NativeNocturneV2Tests(unittest.TestCase):
    def test_contract(self):
        score=json.loads(SCORE.read_text())
        validate_score(score)
        self.assertEqual(score['duration_seconds'],45)
        self.assertEqual(score['voice_ends_at'],33.8)

    def test_actual_render_and_no_overwrite(self):
        score=json.loads(SCORE.read_text())
        score['duration_seconds']=5
        score['voice_ends_at']=3.8
        score['events']={role:[dict(e,duration=min(float(e['duration']),5-float(e['time']))) if 'duration' in e else e for e in rows if float(e['time'])<4] for role,rows in score['events'].items()}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'render'
            rec=render_score(score,path)
            self.assertEqual(rec['schema'],'dio.sonoris.native_shortform.v2')
            self.assertFalse(rec['reference_wav_used_in_render'])
            self.assertEqual(len(rec['stems']),5)
            self.assertTrue((path/rec['master']).is_file())
            with self.assertRaises(FileExistsError): render_score(score,path)
