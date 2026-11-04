import json
import tempfile
import unittest
from pathlib import Path
from products.sonoris_nocturne_engine_v4 import validate_score,render_score

SCORE=Path(__file__).resolve().parents[1]/'media/sonoris/scores/DICERE_NOCTURNE_NATIVE_V4.json'
class NativeNocturneV4Tests(unittest.TestCase):
    def test_score_is_valid(self):
        validate_score(json.loads(SCORE.read_text()))
    def test_invalid_darkness_refuses(self):
        s=json.loads(SCORE.read_text());s['timbre']['darkness']=1.5
        with self.assertRaises(ValueError):validate_score(s)
