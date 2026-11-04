"""Sonoris native, score-driven short-form atmospheric engine.

Does not consume, remix or sample the reference WAV. It produces five stereo
stems from authored musical events and deterministic synthesis/percussion.
V2 isolated native synthesis. Does not modify the established Sonoris song engine.
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
          *, kind: str, rng: np.random.Generator, timbre=None):
    a = max(0, int(start * SR)); b = min(x.shape[0], int((start + duration) * SR))
    if b <= a: return
    t = np.arange(b - a, dtype=np.float64) / SR
    f = _hz(pitch)
    # Small, deterministic instabilities to avoid phase-locked keyboard presets.
    detune = rng.uniform(3.2, 8.0)
    drift = 1 + .0013 * np.sin(2 * np.pi * (.11 + rng.uniform(0, .04)) * t)
    p1 = 2 * np.pi * f * np.cumsum(drift) / SR
    p2 = p1 * 2 ** (detune / 1200) + .34
    timbre = timbre or {}
    if kind == 'bass':
        # Three slightly unstable oscillators; distortion generates harmonics
        # without the instantly recognizable General MIDI bass timbre.
        sub = np.sin(p1 / 2 + .09)
        body = .56*np.sin(p1) + .26*np.sin(2*p1) + .19*np.sin(3*p2)
        swell = 0.75 + 0.25*np.sin(2*np.pi*.078*t + .3)
        y = np.tanh((body + .37*sub)*float(timbre.get('bass_drive', 2.85)))
        y *= _envelope(len(t), .18, .85) * swell
        y = _filter(y, 'lowpass', 680)
        pair = np.column_stack((y, y*.98)).astype(np.float32)
        x[a:b] += pair * (float(timbre.get('bass_level', .16)) * velocity)
        return
    elif kind == 'pad':
        # Unison oscillators with independent phase drifts and harmonic content.
        # Slow multi-band motions, not short plucks.
        phase_l = p1
        phase_r = p2 + .13*np.sin(2*np.pi*.17*t)
        l = sum(np.sin(h*phase_l + .08*h)/(h**1.22) for h in range(1,10))
        r = sum(np.sin(h*phase_r + .16*h)/(h**1.27) for h in range(1,10))
        pair = np.column_stack((l,r)).astype(np.float32)
        # Slow filter travel built from smoothly crossfaded dark/bright versions.
        dark = _filter(pair, 'lowpass', 610)
        bright = _filter(pair, 'lowpass', 1700)
        movement = (.30+.34*(1+np.sin(2*np.pi*.047*t + f*.001))/2).astype(np.float32)
        pair = dark*(1-movement[:,None])+bright*movement[:,None]
        e = _envelope(len(t), 2.35, 2.15)[:,None]
        x[a:b] += np.tanh(pair*1.15) * e * (float(timbre.get('pad_level',.075))*velocity)
        return
    elif kind == 'motif':
        # Velvet-soft dual oscillator lead with controlled harmonic bite.
        raw = (.56*np.sin(p1) + .23*np.sin(2*p1+.21)
               +.21*np.sin(3*p2+.09) + .11*np.sin(5*p1))
        raw2 = (.48*np.sin(p2) + .28*np.sin(2*p2+.27)
                + .13*np.sin(4*p1))
        dark = _filter(raw, 'lowpass', 1500)
        bright = _filter(raw, 'lowpass', 3600)
        opening = .32 + .28 * np.exp(-t/.48)
        tone = dark*(1-opening)+bright*opening
        env = np.exp(-t/max(.43,duration*.95)) * np.minimum(1,t/.032)
        width = .92 + .08*np.sin(2*np.pi*.32*t)
        pair = np.column_stack((tone, .79*tone+.22*raw2*width)).astype(np.float32)
        pair = np.tanh(pair*float(timbre.get('motif_drive',1.65)))
        x[a:b] += pair * env[:,None] * (float(timbre.get('motif_level',.19))*velocity)
        return
    else:
        raise ValueError(f'UNKNOWN_NOTE_KIND={kind}')


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
    timbre = score.get('timbre', {})
    duration = float(score['duration_seconds'])
    n = int(round(duration * SR)); t = np.arange(n, dtype=np.float32) / SR
    stems = {role: np.zeros((n, 2), dtype=np.float32) for role in ROLES}
    for role, kind in (('motif', 'motif'), ('bass', 'bass'), ('pads', 'pad')):
        for event in score['events'][role]:
            _note(stems[role], float(event['time']), float(event['duration']),
                  float(event['pitch']), float(event['velocity']), kind=kind, rng=rng, timbre=timbre)
    # Distinct processing and editorial curve per role.
    stems['motif'] = _echo(stems['motif'], .375, wet=.27)
    stems['motif'] = _space(stems['motif'], wet=.4)
    stems['pads'] = _space(_echo(stems['pads'], .53, wet=.38), wet=1.6)
    stems['bass'] = _filter(_tanh(stems['bass'], 2.15), 'lowpass', 540)
    for event in score['events'].get('pulse', []):
        _pulse(stems['pulse'], float(event['time']), float(event['velocity']), rng)
    stems['pulse'] = _space(stems['pulse'], wet=.72)
    atmosphere = rng.standard_normal((n, 2)).astype(np.float32)
    atmosphere = _filter(atmosphere, 'bandpass', (180, 4100), order=2)
    # Slow evolving analogue-like air rather than fixed white noise.
    breathing = (.57 + .43*np.sin(2*np.pi*.029*t + .4)**2).astype(np.float32)
    stems['atmosphere'] = atmosphere * (.0017*breathing[:,None])
    # Post-voice finale includes extra independent harmonic undertone.
    finale_at = float(score['voice_ends_at'])
    finale_start = int((finale_at + .5)*SR)
    if finale_start < n:
        tail_t = np.arange(n-finale_start,dtype=np.float32)/SR
        entering = np.minimum(1,tail_t/2.4)
        leaving = np.minimum(1,np.maximum(0,duration-finale_at-.5-tail_t)/2.0)
        f = _hz(float(score.get('finale_root_pitch',38)))
        phase = 2*np.pi*f*tail_t
        layer = np.tanh((np.sin(phase)+.28*np.sin(2.004*phase)) * 1.9)
        layer *= entering*leaving*.065
        stems['bass'][finale_start:,0] += layer
        stems['bass'][finale_start:,1] += layer*.94
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
    rec={'schema':'dio.sonoris.native_shortform.v2','state':'AWAITING_HUMAN_LISTENING_REVIEW',
         'engine':'sonoris_nocturne_engine_v2','audio_generation':'native_score_synthesis_with_modulated_timbres',
         'reference_wav_used_in_render':False,'motif_provenance':score.get('motif_provenance','authored_candidate'),
         'duration_seconds':duration,'voice_ends_at':voice,'seed':seed,'sample_rate':SR,
         'score_sha256':hashlib.sha256(json.dumps(score,sort_keys=True).encode()).hexdigest(),
         'stems':stem_metadata,'master':master.name,'master_sha256':_sha(master),
         'rights_review_required':True,'release_authorized':False,'timbre':timbre}
    (out/'SONORIS_NATIVE_RECEIPT.json').write_text(json.dumps(rec,indent=2))
    return rec
