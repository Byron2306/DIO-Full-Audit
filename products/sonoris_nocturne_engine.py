"""Sonoris native, score-driven short-form atmospheric engine.

Does not consume, remix or sample the reference WAV. It produces five stereo
stems from authored musical events and deterministic synthesis/percussion.
Experimental standalone extension; does not modify the established song engine.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000
ROLES = ('motif', 'bass', 'pads', 'pulse', 'atmosphere')


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _hz(note: float) -> float:
    return 440.0 * 2 ** ((float(note) - 69) / 12)


def _filter(x, kind: str, cutoff, order=2):
    sos = signal.butter(order, cutoff, fs=SR, btype=kind, output='sos')
    return signal.sosfilt(sos, x, axis=0).astype(np.float32)


def _envelope(length: int, attack: float, release: float):
    t = np.arange(length) / SR
    d = length / SR
    e = np.minimum(1, t / max(.002, attack))
    e *= np.minimum(1, np.maximum(0, d - t) / max(.002, release))
    return e.astype(np.float32)


def _tanh(x: np.ndarray, drive: float):
    return (np.tanh(x * drive) / np.tanh(drive)).astype(np.float32)


def _note(x, start: float, duration: float, pitch: float, velocity: float,
          *, kind: str, rng: np.random.Generator):
    a = max(0, int(start * SR)); b = min(x.shape[0], int((start + duration) * SR))
    if b <= a: return
    t = np.arange(b - a, dtype=np.float64) / SR
    f = _hz(pitch)
    # Small, deterministic instabilities to avoid phase-locked keyboard presets.
    detune = rng.uniform(3.2, 8.0)
    drift = 1 + .0013 * np.sin(2 * np.pi * (.11 + rng.uniform(0, .04)) * t)
    p1 = 2 * np.pi * f * np.cumsum(drift) / SR
    p2 = p1 * 2 ** (detune / 1200) + .34
    if kind == 'bass':
        y = (.75 * np.sin(p1) + .23 * np.sin(2 * p1) + .10 * np.sin(3 * p2))
        y = _tanh(y, 1.7) * _envelope(len(t), .28, .65)
        y = _filter(y, 'lowpass', 340)
    elif kind == 'pad':
        # Different harmonics, slow filter movement and stereo detune.
        y = sum(np.sin(h * p1) / (h ** 1.35) for h in range(1, 8))
        z = sum(np.sin(h * p2 + .1) / (h ** 1.45) for h in range(1, 8))
        pair = np.column_stack((y, z)).astype(np.float32)
        pair = _filter(pair, 'lowpass', 1200)
        e = _envelope(len(t), 1.7, 2.0)[:, None]
        x[a:b] += pair * e * (.065 * velocity)
        return
    elif kind == 'motif':
        # A rounded, harmonically rich voice with a soft physical-feeling attack.
        y = (.68 * np.sin(p1) + .22 * np.sin(2 * p1 + .15) +
             .14 * np.sin(3 * p2) + .065 * np.sin(5 * p1))
        y = _filter(y, 'lowpass', 2400)
        y *= np.exp(-t / max(.32, duration * .85)) * np.minimum(1, t / .016)
    else:
        raise ValueError(f'UNKNOWN_NOTE_KIND={kind}')
    y = np.asarray(y, dtype=np.float32) * velocity
    if kind == 'bass':
        x[a:b, 0] += y * .15
        x[a:b, 1] += y * .15
    else:
        x[a:b, 0] += y * .17
        x[a:b, 1] += y * .155


def _echo(x, delay_s, wet=.16, feedback=.33):
    delay = int(delay_s * SR)
    out = x.copy()
    for j in (1, 2, 3):
        shift = delay * j
        if shift < len(x):
            out[shift:] += x[:-shift] * wet * (feedback ** (j - 1))
    return out


def _space(x, wet=.18):
    # Smooth multi-tap diffusion: keeps the stereo bed broad but leaves a clear center.
    out = x.copy()
    for d, gain, swap in ((.071, .15, True), (.139, .12, False),
                          (.307, .085, True), (.617, .05, False)):
        shift = int(d * SR)
        if swap:
            out[shift:, 0] += x[:-shift, 1] * wet * gain
            out[shift:, 1] += x[:-shift, 0] * wet * gain
        else:
            out[shift:] += x[:-shift] * wet * gain
    return out


def _curve(t: np.ndarray, points):
    return np.interp(t, [v[0] for v in points], [v[1] for v in points]).astype(np.float32)


def _pulse(x, sec, strength, rng):
    a = int(sec * SR)
    length = min(int(.25 * SR), len(x) - a)
    if length <= 0: return
    t = np.arange(length) / SR
    noise = rng.standard_normal(length).astype(np.float32)
    click = _filter(noise, 'bandpass', (100, 1900))
    kick = np.sin(2 * np.pi * (60 * t - 21 * t * t))
    env = np.exp(-22 * t).astype(np.float32)
    hit = (click * .22 + kick * .7) * env * strength
    x[a:a+length, 0] += hit * .12
    x[a:a+length, 1] += hit * .105


def validate_score(score: Mapping[str, Any]):
    duration = float(score['duration_seconds'])
    if not 5 <= duration <= 180:
        raise ValueError('INVALID_SHORTFORM_DURATION')
    if float(score['voice_ends_at']) > duration:
        raise ValueError('INVALID_VOICE_END')
    if int(score['sample_rate']) != SR:
        raise ValueError('REQUIRES_48000_HZ')
    for role in ('motif', 'bass', 'pads'):
        if not score['events'].get(role):
            raise ValueError(f'EMPTY_{role.upper()}_EVENTS')
        for e in score['events'][role]:
            if not (0 <= float(e['time']) < duration and
                    0 < float(e['duration']) <= duration and
                    20 <= float(e['pitch']) <= 108 and
                    0 < float(e['velocity']) <= 1):
                raise ValueError(f'INVALID_EVENT={role}')


def render_score(score: Mapping[str, Any], out: Path) -> dict[str, Any]:
    """Render original score-derived Sonoris stems and a restrained audition master.

    Refuses to overwrite nonempty output folders; no reference recording is read.
    """
    validate_score(score)
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f'REFUSE_NONEMPTY_OUTPUT={out}')
    out.mkdir(parents=True, exist_ok=True)
    seed = int(score['seed']); rng = np.random.default_rng(seed)
    duration = float(score['duration_seconds'])
    n = int(round(duration * SR)); t = np.arange(n, dtype=np.float32) / SR
    stems = {role: np.zeros((n, 2), dtype=np.float32) for role in ROLES}
    for role, kind in (('motif', 'motif'), ('bass', 'bass'), ('pads', 'pad')):
        for event in score['events'][role]:
            _note(stems[role], float(event['time']), float(event['duration']),
                  float(event['pitch']), float(event['velocity']), kind=kind, rng=rng)
    # Distinct processing and editorial curve per role.
    stems['motif'] = _echo(stems['motif'], .375, wet=.21)
    stems['motif'] = _space(stems['motif'], wet=.4)
    stems['pads'] = _space(_echo(stems['pads'], .53, wet=.28), wet=1.0)
    stems['bass'] = _filter(_tanh(stems['bass'], 1.8), 'lowpass', 240)
    for event in score['events'].get('pulse', []):
        _pulse(stems['pulse'], float(event['time']), float(event['velocity']), rng)
    stems['pulse'] = _space(stems['pulse'], wet=.5)
    atmosphere = rng.standard_normal((n, 2)).astype(np.float32)
    atmosphere = _filter(atmosphere, 'bandpass', (180, 4100), order=2)
    stems['atmosphere'] = atmosphere * .0013
    voice = float(score['voice_ends_at'])
    curves = {
        'motif': [(0,.42),(9,.42),(22,.35),(voice,.32),(voice+1,.62),(42,.68),(45,0)],
        'bass': [(0,.24),(10,.36),(24,.4),(voice,.44),(voice+2,.82),(42,.78),(45,0)],
        'pads': [(0,.15),(12,.23),(27,.32),(voice,.38),(voice+2,.88),(42,.77),(45,0)],
        'pulse': [(0,0),(9,0),(16,.35),(voice,.45),(voice+2,.9),(42,.75),(45,0)],
        'atmosphere': [(0,.24),(16,.4),(voice,.45),(voice+1,.9),(43,1),(45,0)],
    }
    # Time-scale curves adapt to any supported duration.
    scale = duration / 45
    vratio = voice / 33.8 if voice else 1
    for role in ROLES:
        points = [(min(duration, (v * vratio if v <= 33.8 else voice + (v-33.8) * ((duration-voice)/11.2))), gain)
                  for v,gain in curves[role]]
        points.sort(key=lambda pair: pair[0])
        stems[role] *= _curve(t, points)[:, None]
        stems[role] = np.nan_to_num(stems[role])
    stem_metadata=[]
    gains={'motif':.95,'bass':.9,'pads':.8,'pulse':.75,'atmosphere':1}
    for role, x in stems.items():
        peak=float(np.max(np.abs(x)))
        if peak > .98: x *= .98 / peak
        path=out/f'{role}.wav'; sf.write(path, x, SR, subtype='PCM_24')
        stem_metadata.append({'role':role, 'file':path.name,'sha256':_sha(path),
                              'peak':round(float(np.max(np.abs(x))),6),'mix_gain':gains[role]})
    mix=sum(stems[r] * gains[r] for r in ROLES)
    peak=float(np.max(np.abs(mix)))
    if peak > .78: mix *= .78 / peak
    master = out/'SONORIS_NOCTURNE_NATIVE_AUDITION.wav'
    sf.write(master, mix, SR, subtype='PCM_24')
    rec={'schema':'dio.sonoris.native_shortform.v1','state':'AWAITING_HUMAN_LISTENING_REVIEW',
         'engine':'sonoris_nocturne_engine','audio_generation':'native_score_synthesis',
         'reference_wav_used_in_render':False,'motif_provenance':score.get('motif_provenance','authored_candidate'),
         'duration_seconds':duration,'voice_ends_at':voice,'seed':seed,'sample_rate':SR,
         'score_sha256':hashlib.sha256(json.dumps(score,sort_keys=True).encode()).hexdigest(),
         'stems':stem_metadata,'master':master.name,'master_sha256':_sha(master),
         'rights_review_required':True,'release_authorized':False}
    (out/'SONORIS_NATIVE_RECEIPT.json').write_text(json.dumps(rec,indent=2))
    return rec
