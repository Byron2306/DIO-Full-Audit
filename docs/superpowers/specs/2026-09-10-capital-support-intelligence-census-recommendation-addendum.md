# DIO Capital & Support Intelligence Census — Recommendation Layer Addendum

**Date:** 2026-09-10  
**Status:** APPROVED with parent design  
**Parent spec:** `docs/superpowers/specs/2026-09-10-capital-support-intelligence-census-design.md`

## Purpose

The Capital & Support Intelligence Census must not stop at discovery, ranking, or draft generation. It must filter the large census into an operator-facing recommendation queue that answers practical questions such as:

- Should I approach this organisation now?
- Why is this target worth my attention?
- Who or what public route should I use?
- Which DIO product/proof wedge should lead?
- Which HiveNance hypothesis and LINGUA hook should be tested?
- Should I email, use an application route, request a partnership conversation, wait, or do more research?
- What draft would DIO recommend if I choose to proceed?

This mirrors the useful operator behaviour of the historical DIO lead/advertising intelligence lane, while preserving the stricter truth and authority boundaries of the capital system.

## Recommendation object

GoldenEye and Market Command must be able to emit a governed `CAPITAL_ACTION_RECOMMENDATION` for a ranked opportunity.

```text
recommendation_id
opportunity_id
organisation_id
person_id optional
capital_type
capital_archetype
recommendation = APPROACH_NOW | APPLY_NOW | PARTNERSHIP_INQUIRY | CULTIVATE | RESEARCH_FIRST | WATCH | HOLD | DO_NOT_CONTACT
recommendation_score
recommendation_reason[]
atlas_product_wedge[]
atlas_proof_bundle[]
leading_hypothesis
lingua_approach
recommended_route
route_state
route_evidence[]
timing_reason[]
missing_research[]
missing_proofs[]
risk_notes[]
draft_available
operator_question
truth_class = ACTION_RECOMMENDATION_MODEL_OUTPUT
authority_created = false
external_effects = false
```

`operator_question` should be phrased as a concrete decision prompt, for example:

- `Consider emailing this investor using the verified public route?`
- `Review and apply to this grant before 2026-10-31?`
- `Consider a partnership inquiry to this foundation?`
- `Hold this sponsor until the proof bundle is stronger?`
- `Research the programme officer and eligibility terms before drafting?`

The recommendation is advice, not permission and not an action.

## Recommendation rules

A high rank alone is insufficient for `APPROACH_NOW` or `APPLY_NOW`. Recommendation logic must consider the typed scoring model plus:

- verified public route or verified application route;
- source freshness;
- deadline/timing state;
- Atlas fit and proof readiness;
- HiveNance hypothesis quality;
- missing evidence;
- route policy state;
- `DO_NOT_CONTACT`;
- Legalis requirements;
- whether the target has already been contacted or engaged;
- operator-set suppression or priority rules.

If a target is attractive but lacks a safe route, the recommendation must be `RESEARCH_FIRST` or `WATCH`, never `APPROACH_NOW`.

If a grant is highly relevant but eligibility is unresolved, the recommendation must say to verify eligibility rather than imply that DIO qualifies.

If a donor/foundation has strong mission fit but no current programme or route, the recommendation may be `CULTIVATE` or `WATCH` rather than fabricating an application opportunity.

## Draft coupling

When a recommendation supports outreach and a lawful public route exists, Market Command may attach a draft-only communication package. The package must include:

- draft subject/opening/body;
- LINGUA-selected hook/style and alternates;
- Atlas product/proof wedge;
- HiveNance hypothesis being tested;
- safe claims;
- claims to avoid;
- target-specific rationale;
- required approvals;
- route evidence;
- `send_authority = false`.

The operator experience should resemble:

> **Recommendation:** Approach this organisation now.  
> **Why:** Strong Atlas fit, recent relevant funding activity, verified public route, and adequate proof bundle.  
> **Suggested approach:** thesis-first / proof-first / mission-first etc.  
> **Draft ready:** Yes.  
> **Action:** Review draft / approve governed send / hold / dismiss / ask Vesper why.

The system may generate the draft automatically, but must never send it automatically merely because the recommendation is positive.

## Needs You / operator queue

High-value recommendations should flow into an operator-facing Capital & Support recommendation queue rather than forcing the operator to inspect thousands of census records.

The queue should expose at least:

- top recommendations;
- recommendation type;
- target and capital type;
- why now;
- Atlas fit/product wedge;
- route state;
- LINGUA approach;
- draft availability;
- deadline where applicable;
- missing research/proof;
- operator action buttons or equivalent governed actions.

Suggested operator actions:

- `Review draft`
- `Ask Vesper why`
- `Research more`
- `Watch`
- `Hold`
- `Do not contact`
- `Approve governed outreach` only when the existing authority/Legalis path permits it.

The queue should be available through the Control Deck and queryable conversationally through Vesper.

## Vesper examples

Vesper should be able to answer:

- `Who are the five capital targets you think I should approach this week?`
- `Why are you recommending this foundation?`
- `Should I email this investor or wait?`
- `Show me grants you recommend applying for this month.`
- `Draft the email you would use for rank 2, but do not send it.`
- `What proof is missing before you would recommend approaching this sponsor?`
- `Which recommendations changed since yesterday and why?`

Vesper must distinguish recommendation from authority and from evidence of external intent.

## Learning loop

Recommendation outcomes feed the existing learning loop:

```text
recommendation → operator decision → governed outreach/application if approved
→ response / silence / rejection / conversion / award / settlement
→ HiveNance hypothesis update + LINGUA expression learning + GoldenEye movement
→ next recommendation
```

Operator rejection of a recommendation is also useful evidence. The system should preserve whether the operator chose `hold`, `research`, `do_not_contact`, or `proceed`, without treating that decision as market evidence.

## Acceptance additions

The implementation is incomplete unless:

1. the census can produce a small operator recommendation queue from a much larger registry;
2. recommendations explain `why this target` and `why now`;
3. a recommendation may attach a target-specific LINGUA draft;
4. unsafe or unverified routes cannot yield `APPROACH_NOW`;
5. `DO_NOT_CONTACT` always wins;
6. the Control Deck and Vesper can surface the recommendations;
7. no recommendation creates send, application, financial, contractual, or acceptance authority.