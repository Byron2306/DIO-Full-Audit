// Sonoris dark ambient bed, built from the DIO Darksynth v3 native-PCM oscillator
// approach. Original notes and arrangement; no samples or catalog music.
const fs = require('fs');
const output = process.argv[2];
const rate = 48000, seconds = 45, n = rate * seconds, tau = Math.PI * 2;
const bpm = 85, beat = 60 / bpm, bar = beat * 4, chordBars = 4, chordSpan = bar * chordBars;
const hz = m => 440 * Math.pow(2, (m - 69) / 12);
const chords = [
  { root: 41, notes: [41, 48, 53, 56, 60, 67] }, // Fm(add9)
  { root: 37, notes: [37, 44, 49, 53, 56, 61] }, // Dbmaj7
  { root: 39, notes: [39, 46, 51, 55, 58, 65] }, // Eb
  { root: 36, notes: [36, 43, 48, 51, 55, 60] }  // Cm
];
const left = new Float32Array(n), right = new Float32Array(n);
const tri = (f, t) => 2 / Math.PI * Math.asin(Math.sin(tau * f * t));
const sat = x => Math.tanh(x * 1.5) / Math.tanh(1.5);
// Slow detuned pad chords. A restrained low-pass-like blend keeps the field dark.
for (let i = 0; i < n; i++) {
  const t = i / rate, ci = Math.min(3, Math.floor(t / chordSpan));
  const local = t - ci * chordSpan, span = Math.min(chordSpan, seconds - ci * chordSpan);
  const swell = Math.min(1, local / 2.2) * Math.min(1, (span - local) / 2.8);
  let pL = 0, pR = 0;
  for (let j = 0; j < chords[ci].notes.length; j++) {
    const f = hz(chords[ci].notes[j]);
    const mod = 0.16 * Math.sin(tau * (0.055 + j * 0.009) * t + j * 0.8);
    pL += 0.018 * (Math.sin(tau * f * (1 - 0.0017) * t + mod) + 0.24 * tri(f * 2, t));
    pR += 0.018 * (Math.sin(tau * f * (1 + 0.0019) * t - mod) + 0.22 * tri(f * 2.003, t));
  }
  left[i] += pL * swell; right[i] += pR * swell;
}
// A clear, slow arpeggio gives the bed an audible identity without turning it into a beat track.
const arpPattern = [0, 2, 4, 3, 5, 2, 1, 4, 0, 3, 5, 4, 2, 1, 3, 5];
const step = beat / 2;
for (let start = 2.7; start < seconds - 2.2; start += step) {
  const ci = Math.min(3, Math.floor(start / chordSpan));
  const chord = chords[ci].notes;
  const k = Math.floor((start % chordSpan) / step);
  if (k % 8 === 7) continue;
  const note = chord[arpPattern[k % arpPattern.length]] + 12;
  const freq = hz(note), dur = 0.28, count = Math.floor(dur * rate), pan = (k % 4 < 2) ? 0.78 : 0.22;
  for (let j = 0; j < count && Math.floor(start * rate) + j < n; j++) {
    const age = j / rate, env = Math.min(1, age / 0.012) * Math.exp(-age * 5.3);
    const tone = (Math.sin(tau * freq * age) + 0.33 * Math.sin(tau * freq * 2 * age) + 0.11 * Math.sin(tau * freq * 3 * age)) * env * 0.14;
    const ix = Math.floor(start * rate) + j;
    left[ix] += tone * Math.sqrt(1 - pan); right[ix] += tone * Math.sqrt(pan);
  }
}
// Slow sub pulses anchor each bar. They support the pad without kick/snare transients.
for (let start = 0; start < seconds; start += bar) {
  const ci = Math.min(3, Math.floor(start / chordSpan)), freq = hz(chords[ci].root - 12), count = Math.floor(1.1 * rate);
  for (let j = 0; j < count && Math.floor(start * rate) + j < n; j++) {
    const age = j / rate, env = Math.min(1, age / 0.05) * Math.exp(-age * 1.7);
    const v = (Math.sin(tau * freq * age) + 0.16 * Math.sin(tau * freq * 2 * age)) * env * 0.105;
    const ix = Math.floor(start * rate) + j; left[ix] += v; right[ix] += v;
  }
}
// Cross-channel delay adds a soft halo around the synth motif.
const delayA = Math.floor(rate * 0.31), delayB = Math.floor(rate * 0.47);
for (let i = delayA; i < n; i++) left[i] += right[i - delayA] * 0.19;
for (let i = delayB; i < n; i++) right[i] += left[i - delayB] * 0.16;
let peak = 0;
for (let i = 0; i < n; i++) {
  const t = i / rate, fade = Math.min(1, t / 1.5) * Math.min(1, (seconds - t) / 2.8);
  left[i] = sat(left[i] * fade * 2.2); right[i] = sat(right[i] * fade * 2.2);
  peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
}
const pcm = Buffer.alloc(44 + n * 4);
pcm.write('RIFF',0); pcm.writeUInt32LE(36+n*4,4); pcm.write('WAVE',8); pcm.write('fmt ',12);
pcm.writeUInt32LE(16,16); pcm.writeUInt16LE(1,20); pcm.writeUInt16LE(2,22);
pcm.writeUInt32LE(rate,24); pcm.writeUInt32LE(rate*4,28); pcm.writeUInt16LE(4,32); pcm.writeUInt16LE(16,34);
pcm.write('data',36); pcm.writeUInt32LE(n*4,40);
const gain = Math.min(1.25, 0.86 / Math.max(peak, 0.001));
for (let i = 0; i < n; i++) {
  pcm.writeInt16LE(Math.max(-32768,Math.min(32767,Math.round(left[i]*gain*32767))),44+i*4);
  pcm.writeInt16LE(Math.max(-32768,Math.min(32767,Math.round(right[i]*gain*32767))),46+i*4);
}
fs.writeFileSync(output, pcm);
