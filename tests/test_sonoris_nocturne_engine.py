import copy
import json
import tempfile
import unittest
from pathlib import Path
from products.sonoris_nocturne_engine import validate_score, render_score

ROOT=Path(__file__).resolve().parents[1]
SCORE=ROOT/'media/sonoris/scores/DICERE_NOCTURNE_NATIVE_V1.json'
if not SCORE.is_file():
    SCORE=ROOT/'scores/DICERE_NOCTURNE_NATIVE_V1.json'

class NativeShortformTests(unittest.TestCase):
    def test_score_schema(self):
        validate_score(json.loads(SCORE.read_text()))
    def test_no_overwrite_and_actual_stems(self):
        score=json.loads(SCORE.read_text())
        score['duration_seconds']=5
        score['voice_ends_at']=3.8
        score['events']={key:[dict(e, duration=min(e['duration'], 5-e['time'])) if 'duration' in e else e for e in rows if e['time']<4] for key,rows in score['events'].items()}
        for role in ('motif','bass','pads'):
            self.assertTrue(score['events'][role])
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'render'
            receipt=render_score(score,out)
            self.assertFalse(receipt['reference_wav_used_in_render'])
            self.assertEqual(len(receipt['stems']),5)
            self.assertTrue((out/receipt['master']).exists())
            with self.assertRaises(FileExistsError): render_score(score,out)
