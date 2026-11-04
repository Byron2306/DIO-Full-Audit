"""Sonoris native, score-driven short-form atmospheric engine.

Does not consume, remix or sample the reference WAV. It produces five stereo
stems from authored musical events and deterministic synthesis/percussion.
V4 dark-industrial native synthesis. Does not modify the established Sonoris song engine.
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




def _dark_voice_v4(x, a, b, t, p1, p2, f, velocity, kind, timbre):
    """Native industrial synthesizer voices with evolving harmonics.

    The instrument is not a post-effect on the V3 recording. It generates
    oscillator partials directly from score events, then filters and shapes
    each note independently. No recorded input is opened.
    """
    drive = float(timbre.get('drive', 3.4))
    cutoff = float(timbre.get('filter_cutoff_hz', 720))
    sweep = float(timbre.get('filter_envelope', 1.1))
    darkness = float(timbre.get('darkness', .78))
    grit = float(timbre.get('harmonic_grit', .7))
    swell = float(timbre.get('dread_motion', .65))
    if kind == 'bass':
        # Detuned pulse/saw with a sinusoidal sub below the fundamental.
        # Saturate BEFORE filtering: gritty harmonics without harsh fizz.
        sub = np.sin(p1*.5)
        osc_l = (.60*signal.sawtooth(p1, .43) +
                 .30*signal.square(p1, .48) + .27*sub +
                 .17*np.sin(3*p2+.2))
        osc_r = (.58*signal.sawtooth(p2, .46) +
                 .31*signal.square(p2, .51) + .27*sub +
                 .16*np.sin(3*p1+.4))
        pair = np.column_stack((osc_l, osc_r))
        pair = np.tanh(pair * (2.2 + 1.1*drive))
        dark = _filter(pair, 'lowpass', max(90, cutoff*(.33-.10*darkness)))
        open_ = _filter(pair, 'lowpass', max(170, cutoff*.90))
        moving = np.clip(.18 + .33*sweep*(.5+.5*np.sin(2*np.pi*.083*t+.9)),.12,.7)
        pair = dark*(1-moving[:,None]) + open_*moving[:,None]
        env = _envelope(len(t), .28, 1.1)
        gain = float(timbre.get('bass_level', .16))*1.25
    elif kind == 'pad':
        # Distant machine choir: detuned partials, slow formant-like sweep,
        # and faint tritone beating in the upper partials.
        l = sum(np.sin(h*p1 + .13*h) * (1/h**1.18) for h in range(1,9))
        r = sum(np.sin(h*p2 + .24*h) * (1/h**1.18) for h in range(1,9))
        dis_l = .14*grit*np.sin(1.4142*p1+.35)
        dis_r = .14*grit*np.sin(1.4142*p2+.63)
        pair = np.column_stack((l+dis_l,r+dis_r))
        pair = np.tanh(pair * drive*.8)
        low = _filter(pair,'lowpass',max(160,cutoff*(.54-.20*darkness)))
        high = _filter(pair,'lowpass',max(370,cutoff*1.45))
        opening = np.clip(.12 + .38*swell*(.5+.5*np.sin(2*np.pi*.034*t+.8)),0,.68)
        pair = low*(1-opening[:,None])+high*opening[:,None]
        env = _envelope(len(t), 2.7, 2.1)
        gain = float(timbre.get('pad_level', .075))*1.10
    else:
        # The motif should sound like a threatening analogue synth, not a
        # rounded electric piano. Slow attack, PWM grit and detuned harmonics.
        saw_l = signal.sawtooth(p1, .46)
        saw_r = signal.sawtooth(p2, .54)
        pulse_l = signal.square(p1, duty=.46+.075*np.sin(2*np.pi*.19*t))
        pulse_r = signal.square(p2, duty=.54+.075*np.sin(2*np.pi*.17*t+1.4))
        l = .51*saw_l + .28*pulse_l + .18*np.sin(p1) + .10*np.sin(4*p2)
        r = .51*saw_r + .28*pulse_r + .18*np.sin(p2) + .10*np.sin(4*p1)
        pair = np.tanh(np.column_stack((l,r)) * (1.2 + drive*.68))
        low = _filter(pair,'lowpass',max(340,cutoff*(.69-.16*darkness)))
        high = _filter(pair,'lowpass',max(850,cutoff*2.7))
        opening = np.clip(.14 + .31*sweep*np.exp(-t/.65),.12,.64)
        pair = low*(1-opening[:,None])+high*opening[:,None]
        env = _envelope(len(t), .095, .37) * np.exp(-t/max(1.5,len(t)/SR*2.0))
        gain = float(timbre.get('motif_level', .19))*.87
    x[a:b] += (pair * env[:,None] * gain * velocity).astype(np.float32)

def _note(x, start: float, duration: float, pitch: float, velocity: float,
          *, kind: str, rng: np.random.Generator, timbre=None):
    """Deterministic evolving voices. Parameters are specified in the score."""
    a = max(0, int(start * SR)); b = min(x.shape[0], int((start + duration) * SR))
    if b <= a: return
    t = np.arange(b - a, dtype=np.float64) / SR
    f = _hz(pitch)
    timbre = timbre or {}
    detune = float(timbre.get('oscillator_detune_cents', 12.0))
    drift_amount = float(timbre.get('stereo_drift', .003))
    rate = .09 + rng.uniform(.0, .035)
    # Integrate frequency drift so instantaneous pitch is smooth.
    freq_a = f * (1 + drift_amount * np.sin(2*np.pi*rate*t + .35))
    freq_b = f * 2**(detune/1200) * (1 + drift_amount * np.sin(2*np.pi*(rate*.79)*t + 1.75))
    p1 = 2*np.pi*np.cumsum(freq_a)/SR
    p2 = 2*np.pi*np.cumsum(freq_b)/SR + .27
    filt = float(timbre.get('filter_cutoff_hz', 900))
    sweep = float(timbre.get('filter_envelope', .7))
    drive = float(timbre.get('drive', 2.25))
    if kind in ('bass', 'pad', 'motif'):
        _dark_voice_v4(x, a, b, t, p1, p2, f, velocity, kind, timbre)
        return
    if kind == 'bass':
        sub = np.sin(p1/2 + .08)
        body_l = .65*np.sin(p1)+.37*np.sin(2*p1)+.21*np.sin(3*p2)
        body_r = .64*np.sin(p2)+.37*np.sin(2*p2)+.19*np.sin(3*p1)
        rough = np.column_stack((body_l+.42*sub, body_r+.42*sub))
        pair = np.tanh(rough * drive * 1.7)
        dark = _filter(pair, 'lowpass', max(100, filt*.48))
        bright = _filter(pair, 'lowpass', max(240, filt*.94))
        movement = np.clip(.20 + sweep*.30*(1+np.sin(2*np.pi*.073*t+.2))/2, 0, 1)
        pair = dark*(1-movement[:,None])+bright*movement[:,None]
        e = _envelope(len(t), .14, .65)
        x[a:b] += pair.astype(np.float32)*e[:,None]*(float(timbre.get('bass_level',.16))*velocity)
    elif kind == 'pad':
        # Sustained, detuned, stereo-moving harmonic cloud.
        left = sum(np.sin(h*p1+.08*h)/(h**1.25) for h in range(1,12))
        right = sum(np.sin(h*p2+.19*h)/(h**1.27) for h in range(1,12))
        pair = np.column_stack((left,right))
        dark = _filter(pair, 'lowpass', max(170, filt*.70))
        bright = _filter(pair, 'lowpass', max(400, filt*2.2))
        movement = np.clip(.16+sweep*.57*(1+np.sin(2*np.pi*.045*t+f*.002))/2,0,1)
        pair = dark*(1-movement[:,None])+bright*movement[:,None]
        pair = np.tanh(pair*drive*.58)
        e = _envelope(len(t), 2.25, 2.0)
        x[a:b] += pair.astype(np.float32)*e[:,None]*(float(timbre.get('pad_level',.075))*velocity)
    elif kind == 'motif':
        # Controlled edge: not a clean piano, and not a piercing saw preset.
        l = .62*np.sin(p1)+.34*np.sin(2*p1+.17)+.24*np.sin(3*p2)+.11*np.sin(5*p1)
        r = .58*np.sin(p2)+.36*np.sin(2*p2+.27)+.20*np.sin(3*p1)+.12*np.sin(5*p2)
        pair = np.column_stack((l,r))
        dark = _filter(pair, 'lowpass', max(300, filt*1.15))
        bright = _filter(pair, 'lowpass', max(950, filt*3.6))
        movement = np.clip(.22+sweep*.35*np.exp(-t/.7)+.07*np.sin(2*np.pi*.22*t),0,1)
        pair = dark*(1-movement[:,None])+bright*movement[:,None]
        pair = np.tanh(pair * drive*.85)
        env = np.exp(-t/max(.6,duration*1.35))*np.minimum(1,t/.038)
        x[a:b] += pair.astype(np.float32)*env[:,None]*(float(timbre.get('motif_level',.19))*velocity)
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


    timbre = score.get('timbre', {})
    limits = {
        'oscillator_detune_cents': (0, 40),
        'filter_cutoff_hz': (180, 4500),
        'filter_envelope': (0, 1.5),
        'drive': (1, 5),
        'stereo_drift': (0, .015),
        'noise_texture': (0, .015),
        'section_intensity': (.3, 2),
        'darkness': (0, 1),
        'harmonic_grit': (0, 1),
        'dread_motion': (0, 1),
    }
    for key, (lo, hi) in limits.items():
        value = float(timbre.get(key, {'oscillator_detune_cents':12,'filter_cutoff_hz':900,'filter_envelope':.7,'drive':2.25,'stereo_drift':.003,'noise_texture':.0025,'section_intensity':1,'darkness':.78,'harmonic_grit':.7,'dread_motion':.65}[key]))
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'INVALID_TIMBRE_{key.upper()}')

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
    stems['atmosphere'] = atmosphere * (float(timbre.get('noise_texture', .0025))*breathing[:,None])
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
    # Musical dynamics are separate from output loudness. This increases
    # final-section orchestration while preserving voice-first space.
    intensity = float(timbre.get('section_intensity', 1.0))
    finale_shape = _curve(t, [(0,1),(max(0,voice-.1),1),
                               (min(duration,voice+2.2), intensity),
                               (max(0,duration-2), intensity),(duration,1)])
    for role in ('bass','pads','pulse'):
        stems[role] *= finale_shape[:,None]
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
    # Preserve sonic dynamics without making V3 simply louder than V2.
    # Default ~-20.4 dBFS stereo RMS, conservatively close to the V2 audition.
    target_rms = float(score.get('master_target_rms', .095))
    measured_rms = float(np.sqrt(np.mean(mix.astype(np.float64)**2)))
    if measured_rms > target_rms:
        mix *= target_rms / measured_rms
    master = out/'SONORIS_NOCTURNE_NATIVE_AUDITION.wav'
    sf.write(master, mix, SR, subtype='PCM_24')
    rec={'schema':'dio.sonoris.native_shortform.v4','state':'AWAITING_HUMAN_LISTENING_REVIEW',
         'engine':'sonoris_nocturne_engine_v4','audio_generation':'native_score_synthesis_with_PWM_saw_pulse_dissonance_saturation_and_evolving_filters',
         'reference_wav_used_in_render':False,'motif_provenance':score.get('motif_provenance','authored_candidate'),
         'duration_seconds':duration,'voice_ends_at':voice,'seed':seed,'sample_rate':SR,
         'score_sha256':hashlib.sha256(json.dumps(score,sort_keys=True).encode()).hexdigest(),
         'stems':stem_metadata,'master':master.name,'master_sha256':_sha(master),
         'rights_review_required':True,'release_authorized':False,'timbre':timbre,'master_target_rms':target_rms}
    (out/'SONORIS_NATIVE_RECEIPT.json').write_text(json.dumps(rec,indent=2))
    return rec
