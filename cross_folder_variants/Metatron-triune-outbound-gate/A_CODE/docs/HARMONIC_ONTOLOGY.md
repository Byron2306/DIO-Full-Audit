# Harmonic Ontology

## Purpose

This document formalizes the meaning of the harmonic-governance fields used by the runtime on `August 1, 2026`.

The goal is to make the harmonic layer:

- exact enough for policy use
- inspectable enough for audit
- bounded enough to avoid mystical overreach

These fields are descriptive control signals, not identity proofs and not stand-alone verdicts.

---

## Field Semantics

### `resonance_score`

- Formula: sigmoid over inverse jitter, inverse drift, inverse burstiness, and entropy fit, then modulated by resonance spectrum
- Domain: `0.0` to `1.0`
- Required sample size: at least `4` intervals for meaningful inference
- High means: timing remains close to lawful baseline and harmonic structure is stable
- Low means: timing materially diverges from baseline or choral resonance has degraded
- Confidence penalties:
  - fallback baseline
  - degraded environment
  - low sample window
  - micro-resonance collapse
- Misuse boundary:
  - must not directly grant trust or authority

### `discord_score`

- Formula: sigmoid over drift, jitter, burstiness, entropy delta, and perfect-tempo penalty, then spectrum-boosted
- Domain: `0.0` to `1.0`
- Required sample size: at least `4` intervals for meaningful inference
- High means: timing is strained, adversarial, or materially off-baseline
- Low means: timing remains within lawful variation
- Confidence penalties:
  - low sample count
  - fallback baseline
- Misuse boundary:
  - must not be treated as maliciousness in isolation

### `confidence`

- Formula: `0.65 * sample_factor + 0.35 * baseline_quality - degradation_penalty`
- Domain: `0.0` to `1.0`
- Required sample size: minimum `1`, but low counts sharply reduce usable meaning
- High means: enough cadence evidence and credible baseline quality exist for bounded policy use
- Low means: the system may increase caution, but may not privilege the subject
- Confidence penalties:
  - low sample counts
  - degraded environment
  - fallback baseline quality
- Misuse boundary:
  - low confidence must never greenlight sensitive action

### `drift_norm`

- Formula: absolute median interval deviation from baseline, normalized by baseline median
- Domain: clamped to `0.0` to `1.0`
- Required sample size: at least `2` intervals
- High means: cadence pulse has drifted materially from baseline
- Low means: cadence remains near expected tempo
- Misuse boundary:
  - must be interpreted with baseline quality, not alone

### `jitter_norm`

- Formula: population standard deviation of intervals, normalized by baseline jitter
- Domain: clamped to `0.0` to `1.0`
- Required sample size: at least `2` intervals
- High means: variance is materially less stable than baseline
- Low means: timing variation remains controlled
- Misuse boundary:
  - must not be a sole determinant of discord

### `burstiness`

- Formula: short-interval ratio above baseline expected burstiness
- Domain: clamped to `0.0` to `1.0`
- Required sample size: at least `2` intervals
- High means: short clustered execution exceeds lawful expectation
- Low means: cluster pressure stays near baseline
- Misuse boundary:
  - must be interpreted against role-aware automation baselines

### `entropy_signature`

- Formula: normalized Shannon entropy across interval buckets
- Domain: `0.0` to `1.0`
- Required sample size: at least `4` intervals
- High means: interval distribution spans multiple timing buckets
- Low means: execution is overly concentrated or overly regular
- Misuse boundary:
  - must not be treated as a stand-alone risk verdict

### `sequence_class`

- Formula: categorical classification from median interval and coefficient of variation
- Domain:
  - `cold_start`
  - `rapid_regular`
  - `regular`
  - `chaotic`
  - `adaptive`
- Required sample size: at least `2` intervals
- Meaning:
  - `cold_start`: not enough evidence yet
  - `rapid_regular`: fast and low-variance
  - `regular`: stable and expected
  - `chaotic`: high-variance and irregular
  - `adaptive`: mixed tempo with meaningful variation
- Misuse boundary:
  - descriptive only unless combined with the rest of harmonic state

---

## Policy Use Rules

- `confidence` constrains every downstream consequence.
- `resonance_score` and `discord_score` may shape caution, delay, or review, but not identity truth by themselves.
- `drift_norm`, `jitter_norm`, `burstiness`, `entropy_signature`, and `sequence_class` are supporting explanatory features.
- No harmonic field may silently override missing baseline quality.

---

## Alignment Note

The canonical machine-readable source for this ontology is [backend/services/harmonic_ontology.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/harmonic_ontology.py).
