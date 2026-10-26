# Vesper Persona Lab

Vesper Persona Lab is DIO's governed experiment layer for discovering which **presentation** of Vesper works best for different public interaction contexts without allowing presentation to mutate identity, meaning or authority.

## Constitutional split

```text
Vesper identity                 fixed
LINGUA semantic meaning        fixed by source lineage
Persona package                stable for a conversation
Live interaction regulation    may reduce pressure / humour / jargon / cadence
Avatar renderer                presentation only
Voice renderer                 presentation only
DIO authority                  owns external action
```

Vesper always remains an AI system and must not claim to be human.

## Research basis

The initial hypotheses deliberately compare meaningfully different embodiments rather than cosmetic variants.

- Ma et al. (2025), *Frontiers in Computer Science*, found that anthropomorphic avatar design can influence user experience indirectly through perceived empathy and trust rather than through a simple direct "more human is better" effect. DOI: `10.3389/fcomp.2025.1531976`.
- A 2025 *Frontiers in Psychology* systematic review of the uncanny-valley literature for embodied conversational agents found that human-likeness, expression and trust have context-dependent trade-offs, including cases where over-expressive or overly human-like agents are perceived as insincere or uncanny. DOI: `10.3389/fpsyg.2025.1625984`.
- Longitudinal work in *Computers in Human Behavior: Artificial Humans* shows that repeated personalization can change perceived trust, relevance, privacy risk, self-disclosure and recommendation adherence. DOI: `10.1016/j.chbah.2023.100030`.
- OpenVoice V2 provides MIT-licensed tone-colour cloning and style control for rhythm, pauses, intonation and accents. VAMP's inherited OpenVoice2 implementation is the local architectural precedent for Vesper's voice-identity layer.

Research sources are hypotheses for controlled testing, not authority to assume that one gender, age, accent, face style or personality universally converts better.

## Initial visual hypotheses

### Human Professional

A moderately anthropomorphic South African professional woman, roughly late-30s to early-40s presentation, contemporary consulting aesthetic, warm but composed, credible rather than glamorous. The design must not resemble a specific real person.

### Digital Vesper

A clearly synthetic female-presenting digital professional with stylised realism, expressive but restrained eyes, clean ivory/graphite/teal visual grammar and obvious AI identity.

### Vesper Sigil

A premium non-human visual presence combining an abstract face silhouette, speech waveform and DIO evidence-lattice geometry. This is a first-class candidate, not a fallback.

## Initial persona hypotheses

- `warm_professional`
- `executive_concierge`
- `evidence_specialist`

## Voice hypotheses

- OpenVoice2 South African warm/measured candidate, only after reviewed consented reference evidence exists.
- OpenVoice2 South African executive candidate, same consent/provenance rule.
- Piper neutral English control.

Piper provides free local base speech. OpenVoice2 may apply a reviewed Vesper tone identity after text has already been approved by the semantic communication path.

OpenVoice2 does not translate, choose copy or create send authority.

## Nine-cell starter design

The starter matrix is a balanced 3 × 3 Latin-style allocation across persona, avatar and voice candidates so the first controlled pilot does not require 27 fully crossed cells.

Assignment is deterministic by conversation ID and is stable for that conversation.

Operator Vesper is excluded from public Persona Lab experimentation.

## Real-time regulation

LINGUA may respond to **observable interaction cues** such as explicit complaints, repeated profanity, confusion, skepticism, urgency or pricing objections.

It may regulate:

- brevity;
- proof priority;
- question count;
- humour;
- sales pressure;
- jargon;
- voice cadence.

It may not infer or claim:

- emotion;
- personality;
- vulnerability;
- sensitive attributes;
- psychiatric or psychological state.

The avatar, voice identity and persona identity do not morph mid-conversation.

## Outcome evidence

Persona Lab can record:

- task completion;
- issue resolution;
- qualified intake;
- pilot request;
- paid conversion;
- repeat interaction;
- explicit satisfaction;
- human escalation;
- abandonment;
- complaint;
- mistaken-human belief.

A variant cannot be automatically promoted. The default configuration requires at least 30 distinct sessions per cell over at least seven distinct days before a cell can even become a human-review candidate.

High mistaken-human belief or complaint rates veto promotion regardless of conversion score.

## Build NicheFoundry briefs

```bash
python3 scripts/build_vesper_persona_lab.py
```

This creates held avatar-production requests, the experiment matrix and the governed voice-reference script under `state/vesper_persona_lab/`.

## Enable controlled public assignment

Persona experiments are off unless explicitly enabled:

```bash
export DIO_VESPER_PERSONA_LAB=1
```

That switch allows presentation assignment only. It creates no publication, spend, payment, fulfilment, professional or send authority.

## Record evidence

```bash
python3 scripts/manage_vesper_persona_lab.py outcome \
  --conversation CONV-... \
  --source reviewed_analytics \
  --qualified-intake \
  --task-completed
```

Evaluate without promotion:

```bash
python3 scripts/manage_vesper_persona_lab.py evaluate
```

The evaluator can propose a candidate for human review. It cannot change the public default.
