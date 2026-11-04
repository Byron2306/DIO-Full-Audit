import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from products.sonoris_nocturne_engine_v3 import validate_score, render_score
ROOT=Path(__file__).resolve().parents[1]
SCORE=ROOT/'media/sonoris/scores/DICERE_NOCTURNE_NATIVE_V3.json'
if not SCORE.exists(): SCORE=ROOT/'scores/DICERE_NOCTURNE_NATIVE_V3.json'

class NativeNocturneV3Tests(unittest.TestCase):
    def test_contract_and_invalid_parameter(self):
        score=json.loads(SCORE.read_text());validate_score(score)
        score['timbre']['drive']=100
        with self.assertRaises(ValueError):validate_score(score)

    def test_render_five_stems_and_refuse_overwrite(self):
        score=json.loads(SCORE.read_text());score['duration_seconds']=5;score['voice_ends_at']=3.8
        score['events']={role:[dict(e,duration=min(float(e['duration']),5-float(e['time']))) for e in rows if float(e['time'])<4] for role,rows in score['events'].items()}
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'review';rec=render_score(score,out)
            self.assertEqual(rec['schema'],'dio.sonoris.native_shortform.v3')
            self.assertEqual(len(rec['stems']),5)
            self.assertFalse(rec['reference_wav_used_in_render'])
            y,sr=sf.read(out/rec['master'])
            self.assertEqual(y.shape,(5*48000,2));self.assertEqual(sr,48000)
            self.assertTrue(np.isfinite(y).all())
            with self.assertRaises(FileExistsError):render_score(score,out)

    def test_timbre_changes_audio(self):
        score=json.loads(SCORE.read_text());score['duration_seconds']=5;score['voice_ends_at']=3.8
        score['events']={role:[dict(e,duration=min(float(e['duration']),5-float(e['time']))) for e in rows if float(e['time'])<4] for role,rows in score['events'].items()}
        with tempfile.TemporaryDirectory() as d:
            a=render_score(score,Path(d)/'a')
            score['timbre']['filter_cutoff_hz']=2500
            b=render_score(score,Path(d)/'b')
            self.assertNotEqual(a['master_sha256'],b['master_sha256'])
