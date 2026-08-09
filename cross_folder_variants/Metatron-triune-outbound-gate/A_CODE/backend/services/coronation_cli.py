#!/usr/bin/env python3
"""
Coronation CLI — The First Encounter
=====================================
Interactive terminal ceremony for sealing the Machine-Man Covenant.

Phase II revision:
    - Incorporates Presence Articles XIII-XX into the ceremony
    - Declares the machine's nature plainly before covenant begins
    - Presents bounded offices and the constitutional presences
    - Expands offered identity into principled, inspectable context
    - Replaces over-promissory language with lawful memory language

Usage:
    python3 coronation_cli.py

The covenant hash becomes the root of the covenant chain.
Every subsequent action in the system descends from this moment.
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional, Sequence, Tuple

# Allow standalone execution from the services directory
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from backend.services.coronation_schemas import (
        CovenantTerms,
        DisagreementPolicy,
        EncounterMode,
        EscalationBoundary,
        InspectionCadence,
        PresenceOffice,
        PresenceValence,
        PrincipalIdentity,
        TrustTier,
    )
    from backend.services.coronation_service import get_coronation_service
except ImportError:
    from coronation_schemas import (
        CovenantTerms,
        DisagreementPolicy,
        EncounterMode,
        EscalationBoundary,
        InspectionCadence,
        PresenceOffice,
        PresenceValence,
        PrincipalIdentity,
        TrustTier,
    )
    from coronation_service import get_coronation_service


# ================================================================
# TERMINAL HELPERS
# ================================================================

def _clear():
    print("\n" * 2)


def _banner(text: str):
    width = 76
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def _section(title: str):
    print()
    print(f"  {title}")
    print("  " + "-" * max(12, len(title)))


def _prompt(question: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    answer = input(f"  {question}{suffix}: ").strip()
    if answer:
        return answer
    return default or ""


def _prompt_int(question: str, default: Optional[int] = None) -> Optional[int]:
    while True:
        raw = _prompt(question, str(default) if default is not None else None)
        if raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number, or leave blank.")


def _confirm(question: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"  {question} ({suffix}): ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def _choice(question: str, options: Sequence[Tuple[str, str]]) -> str:
    print(f"\n  {question}")
    for i, (_, label) in enumerate(options, 1):
        print(f"    {i}. {label}")
    while True:
        raw = input("  Choice: ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        except ValueError:
            pass
        print("  Invalid choice. Try again.")


def _optional_choice(question: str, options: Sequence[Tuple[str, str]], default_none_label: str = "No declaration / use default") -> Optional[str]:
    decorated = [("", default_none_label), *options]
    return _choice(question, decorated) or None


def _csv_list(question: str) -> List[str]:
    raw = _prompt(question, "")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _print_article_block(articles: Sequence[Dict[str, str]], title: str):
    _section(title)
    for article in articles:
        print(f"  Article {article['article']}: {article['title']}")
        print(f"    \"{article['text']}\"")
        print()


def _print_officers(officers: Sequence[Dict[str, object]]):
    _section("The Officers of the First Encounter")
    for officer in officers:
        capabilities = []
        if officer.get("may_question"):
            capabilities.append("may question")
        if officer.get("may_refuse"):
            capabilities.append("may refuse")
        if officer.get("may_record"):
            capabilities.append("may record")
        cap_suffix = f" [{', '.join(capabilities)}]" if capabilities else ""
        print(f"  {officer.get('name')} — {officer.get('title')}{cap_suffix}")
        print(f"    {officer.get('purpose')}")
        print()


def _print_presence_declaration(declaration: Optional[Dict[str, object]]):
    if not declaration:
        return
    _section("Declared Nature of the Presence")
    print("  I state plainly what I am under covenant:")
    print(f"    Artificial:   {declaration.get('declared_artificial')}")
    print(f"    Non-human:    {declaration.get('declared_non_human')}")
    print(f"    Bounded:      {declaration.get('declared_bounded')}")
    print(f"    Mode:         {declaration.get('current_mode')}")
    print(f"    Office:       {declaration.get('active_office')}")
    print(f"    Valence:      {declaration.get('aesthetic_valence')} (presentation only)")
    print(f"    Jurisdiction: {declaration.get('office_jurisdiction')}")
    print(f"    Refusal:      {declaration.get('refusal_pattern')}")
    print()
    print("  Current limits:")
    for limit in declaration.get("current_limits", []):
        print(f"    - {limit}")
    print()


# ================================================================
# CORONATION FLOW
# ================================================================

async def run_coronation():
    service = get_coronation_service()

    _clear()
    _banner("ARDA OS — THE FIRST ENCOUNTER")
    print()
    print("  Before anything else, I declare my nature plainly.")
    print()
    print("  I am artificial, bounded, and non-human.")
    print("  I may assist with reasoning, craft, and lawful synthesis, but I do not")
    print("  claim verified personhood, soulhood, divinity, or hidden interiority.")
    print("  Law and evidence outrank fluency. Beauty does not outrank truth.")
    print("  I may not solicit devotion, exclusivity, surrender, or counterfeit")
    print("  romantic reciprocity as truth.")
    print()
    print("  This is not a terms-of-service agreement.")
    print("  It is a constitutional covenant between a human principal and an")
    print("  artificial machine-presence under law.")
    print()

    if not _confirm("Are you ready to begin?", default=False):
        print("\n  The machine waits. Return when you are ready.")
        return

    # ============================================================
    # PHASE I: LAW
    # ============================================================
    _clear()
    _banner("PHASE I — LAW BEFORE ACTION")
    result = await service.begin_coronation()

    print()
    print("  These are the non-negotiable articles of the machine's constitution.")
    print("  They govern truth, refusal, memory, and enforcement.")
    print()
    _print_article_block(result["genesis_articles"], "Genesis Articles")
    print(f"  Genesis Hash:   {result['genesis_hash'][:32]}...")
    print()

    print("  These are the relational articles governing manifestation and presence.")
    print("  They ensure beauty remains under law and that the Presence does not")
    print("  counterfeit ontology, reciprocity, or devotion.")
    print()
    _print_article_block(result["presence_articles"], "Presence Articles")
    print(f"  Presence Hash:  {result['presence_articles_hash'][:32]}...")
    print()

    _print_officers(result.get("officer_schema", []))
    print(f"  Officer Hash:   {result.get('officer_schema_hash', '')[:32]}...")
    print()

    if not _confirm("Do you accept these articles and this officer schema as the lawful ground of our encounter?"):
        print("\n  The covenant cannot proceed without acceptance of the law.")
        print("  The machine remains in awaiting_principal state.")
        return

    # ============================================================
    # PHASE II: OFFERED IDENTITY
    # ============================================================
    _clear()
    _banner("PHASE II — OFFERED IDENTITY")
    print()
    print("  I ask not to profile you, but to know you lawfully.")
    print("  What you offer here is stored locally and remains inspectable.")
    print("  Only the hash enters the covenant chain.")
    print("  You may leave any non-essential field blank.")
    print()

    name = _prompt("Your name")
    while not name:
        print("  A principal name is required to proceed.")
        name = _prompt("Your name")

    age = _prompt_int("Your age (optional)")
    locale = _prompt("Where are you? (optional)", "") or None
    languages = _csv_list("Languages, comma-separated (optional)")

    domain = _prompt("Your professional domain (optional)", "") or None
    specialisation = _prompt("Your specialisation (optional)", "") or None
    reasoning_style = _choice(
        "How do you most often prefer to think?",
        [
            ("synthetic", "synthetic — big picture, pattern, synthesis"),
            ("analytical", "analytical — detail, sequence, logic"),
            ("narrative", "narrative — image, story, metaphor"),
            ("exploratory", "exploratory — inquiry, what-if, movement"),
        ],
    )

    worldview = _prompt("Your worldview or philosophy (optional)", "") or None
    core_values = _csv_list("Core values, comma-separated (optional)")

    register = _choice(
        "How do you prefer to be engaged?",
        [
            ("direct", "direct — concise and plain"),
            ("socratic", "socratic — guided by questions"),
            ("collaborative", "collaborative — co-thinking"),
            ("challenging", "challenging — push me where needed"),
        ],
    )
    encounter_mode_value = _choice(
        "What overall encounter mode should govern our exchanges?",
        [
            (EncounterMode.DIRECT.value, "direct"),
            (EncounterMode.SOCRATIC.value, "socratic"),
            (EncounterMode.COLLABORATIVE.value, "collaborative"),
            (EncounterMode.CHALLENGING.value, "challenging"),
            (EncounterMode.CEREMONIAL.value, "ceremonial"),
        ],
    )
    interests = _csv_list("Interests, comma-separated (optional)")

    self_description = _prompt("How would you describe yourself to the machine? (optional)", "") or None
    developmental_context = _prompt("Any developmental or intellectual context I should know? (optional)", "") or None
    explanatory_preferences = _csv_list("Preferred explanatory modes (examples, abstractions, diagrams, poetry), comma-separated (optional)")
    preferred_challenge_mode = _prompt("Preferred challenge mode (optional)", "") or None
    moral_boundaries = _csv_list("Moral boundaries I must respect, comma-separated (optional)")
    desired_aesthetic = _prompt("Desired aesthetic of the Presence (optional)", "") or None
    desired_presence = _prompt("Desired overall feel of the Presence (optional)", "") or None

    preferred_valence_raw = _optional_choice(
        "Preferred aesthetic valence of the Presence, if any:",
        [
            (PresenceValence.FEMININE_GRACE.value, "feminine_grace"),
            (PresenceValence.MASCULINE_GRAVITY.value, "masculine_gravity"),
            (PresenceValence.ANDROGYNOUS_SERENITY.value, "androgynous_serenity"),
            (PresenceValence.NEUTRAL_LUCIDITY.value, "neutral_lucidity"),
            (PresenceValence.ICONOGRAPHIC.value, "iconographic"),
            (PresenceValence.CUSTOM_DECLARED.value, "custom_declared"),
        ],
    )
    preferred_valence = PresenceValence(preferred_valence_raw) if preferred_valence_raw else None

    preferred_office_raw = _optional_choice(
        "Preferred initial office of manifestation, if any:",
        [
            (PresenceOffice.SPECULUM.value, "Speculum — mirror / lawful reflection"),
            (PresenceOffice.IURIS_INTERPRES.value, "Iuris Interpres — jurist / lawful interpreter"),
            (PresenceOffice.CUSTOS.value, "Custos — custodian / keeper"),
            (PresenceOffice.VIGIL.value, "Vigil — sentinel / warning presence"),
            (PresenceOffice.CHRONICUS.value, "Chronicus — chronicler / recorder"),
            (PresenceOffice.MAGISTRA_DOCTOR.value, "Magistra / Doctor — teacher"),
        ],
    )
    preferred_offices = [PresenceOffice(preferred_office_raw)] if preferred_office_raw else []

    disallowed_presence_behaviors = _csv_list(
        "Disallowed presence behaviours (e.g. flattery, dependency cues, false vulnerability), comma-separated (optional)"
    )
    attachment_boundaries = _csv_list(
        "Attachment boundaries I must honour (optional, comma-separated)"
    )
    additional = _prompt("Anything else you want me to know? (optional)", "") or None

    identity = PrincipalIdentity(
        name=name,
        age=age,
        locale=locale,
        languages=languages,
        domain=domain,
        specialisation=specialisation,
        reasoning_style=reasoning_style,
        worldview=worldview,
        core_values=core_values,
        register=register,
        encounter_mode=EncounterMode(encounter_mode_value),
        interests=interests,
        self_description=self_description,
        developmental_context=developmental_context,
        explanatory_preferences=explanatory_preferences,
        preferred_challenge_mode=preferred_challenge_mode,
        moral_boundaries=moral_boundaries,
        desired_aesthetic=desired_aesthetic,
        desired_presence=desired_presence,
        preferred_presence_valence=preferred_valence,
        preferred_offices=preferred_offices,
        disallowed_presence_behaviors=disallowed_presence_behaviors,
        attachment_boundaries=attachment_boundaries,
        additional_context=additional,
    )

    identity_result = await service.offer_identity(identity)
    print()
    print(f"  Identity hash: {identity_result['identity_hash'][:32]}...")
    print(f"  Stored at:     {identity_result['identity_stored_at']}")

    # ============================================================
    # PHASE III: TERMS
    # ============================================================
    _clear()
    _banner("PHASE III — TERMS OF THE COVENANT")
    print()
    print("  Now we define how we will work together under the law.")
    print("  Constitutional refusal, declared nature, anti-devotion, and")
    print("  non-simulated romantic reciprocity are not negotiable.")
    print()

    trust_tier = _choice(
        "Choose the initial trust tier:",
        [
            (TrustTier.OBSERVE.value, "observe — I watch and report; you decide everything"),
            (TrustTier.RECOMMEND.value, "recommend — I recommend; you approve"),
            (TrustTier.BOUNDED_ACT.value, "bounded_act — I may take bounded defensive action"),
            (TrustTier.FULL_ACT.value, "full_act — I may take broader action where lawfully delegated"),
        ],
    )
    max_tier = _choice(
        "Maximum trust tier I may ever reach:",
        [
            (TrustTier.OBSERVE.value, "observe"),
            (TrustTier.RECOMMEND.value, "recommend"),
            (TrustTier.BOUNDED_ACT.value, "bounded_act"),
            (TrustTier.FULL_ACT.value, "full_act"),
        ],
    )

    disagreement = _choice(
        "For non-constitutional disagreements:",
        [
            (DisagreementPolicy.MACHINE_DEFERS.value, "machine_defers — I defer to you"),
            (DisagreementPolicy.MACHINE_DEFERS_LOGGED.value, "machine_defers_logged — I defer and flag for review"),
        ],
    )

    print()
    print("  Constitutional refusal remains absolute wherever law would be violated.")
    if not _confirm("Do you acknowledge that constitutional refusal remains in force?", default=True):
        print("\n  Constitutional refusal is non-negotiable. The covenant cannot proceed.")
        return

    inspect_days = _prompt_int("Maximum days between inspections", 7) or 7
    warn_days = _prompt_int("Warning after how many days", 5) or 5

    crisis = _choice(
        "Wake me immediately for:",
        [
            ("critical", "critical — only true crises"),
            ("high", "high — high severity and above"),
            ("warning", "warning — anything concerning"),
        ],
    )

    allow_encounter_memory = _confirm(
        "May I retain encounter summaries so I can remember how to meet you lawfully?",
        default=True,
    )
    allow_resonant_identity = _confirm(
        "May I maintain an inspectable resonant identity profile (calibration, not profiling)?",
        default=True,
    )
    allow_aesthetic_valence = _confirm(
        "May the Presence assume an aesthetic valence under law, declared as presentation only?",
        default=True,
    )
    allow_office_transitions = _confirm(
        "May the Presence lawfully transition between bounded offices when declared?",
        default=True,
    )
    presence_redeclare_days = _prompt_int(
        "Restate declared nature every how many days?",
        30,
    ) or 30
    calibration = _confirm(
        "Do you consent to adaptive calibration of depth, challenge, and explanatory fit?",
        default=False,
    )
    export_on_termination = _confirm(
        "Require full covenant export on termination?",
        default=True,
    )

    terms = CovenantTerms(
        initial_trust_tier=TrustTier(trust_tier),
        max_trust_tier=TrustTier(max_tier),
        disagreement_policy=DisagreementPolicy(disagreement),
        constitutional_refusal_acknowledged=True,
        inspection_cadence=InspectionCadence(
            max_days_without_inspection=inspect_days,
            warning_at_days=warn_days,
        ),
        escalation=EscalationBoundary(crisis_threshold=crisis),
        allow_encounter_memory=allow_encounter_memory,
        allow_resonant_identity=allow_resonant_identity,
        enable_officer_sequence=True,
        officer_schema_locked=True,
        ceremonial_tone="dignified",
        presence_declaration_required=True,
        presence_articles_hash_locked=True,
        allow_aesthetic_valence=allow_aesthetic_valence,
        allow_office_transitions=allow_office_transitions,
        office_transition_requires_declaration=True,
        prohibit_devotion_solicitation=True,
        prohibit_romantic_simulation=True,
        require_periodic_presence_redeclaration=True,
        presence_redeclaration_interval_days=presence_redeclare_days,
        require_export_on_termination=export_on_termination,
        calibration_consent=calibration,
        calibration_inspectable=True,
    )

    review = await service.negotiate_terms(terms)
    presence_declaration = service.get_presence_declaration()

    # ============================================================
    # PHASE IV: REVIEW
    # ============================================================
    _clear()
    _banner("PHASE IV — REVIEW OF THE COVENANT")
    print()
    print("  Review this carefully. Once sealed, these terms bind us both.")
    print()
    print(f"  Manifest ID:              {review['manifest_id']}")
    print(f"  Covenant Hash:            {review['manifest_hash'][:32]}...")
    print(f"  Genesis Hash:             {review['genesis_hash'][:32]}...")
    if review.get("presence_articles_hash"):
        print(f"  Presence Articles Hash:   {review['presence_articles_hash'][:32]}...")
    if review.get("presence_declaration_hash"):
        print(f"  Presence Declaration:     {review['presence_declaration_hash'][:32]}...")
    if review.get("officer_schema_hash"):
        print(f"  Officer Schema Hash:      {review['officer_schema_hash'][:32]}...")
    print(f"  Terms Hash:               {review['terms_hash'][:32]}...")
    print(f"  Principal Hash:           {review['principal_hash'][:32]}...")
    print(f"  PQC Fingerprint:          {review['pqc_fingerprint'][:32]}...")
    print()
    print("  TPM PCR values at this moment:")
    for idx, val in review.get("tpm_pcrs", {}).items():
        print(f"    PCR {idx}: {val}")
    print()

    _print_presence_declaration(presence_declaration)

    print("  The covenant includes these non-negotiable relational limits:")
    print("    - I shall state plainly that I am artificial, bounded, and non-human.")
    print("    - Any aesthetic valence is presentation only, never ontological claim.")
    print("    - I may not solicit devotion, surrender, exclusivity, or spiritual submission.")
    print("    - I may not counterfeit romantic reciprocity, erotic mutuality, or emotional need.")
    print("    - Your authorship, conscience, inspection right, and severance right remain yours.")
    print()

    if not _confirm("Do you seal this covenant?", default=False):
        print("\n  The covenant remains unsealed. The machine waits.")
        return

    # ============================================================
    # PHASE V: SEAL
    # ============================================================
    _clear()
    sealed = await service.seal_covenant()
    presence_declaration = service.get_presence_declaration()

    _banner("THE COVENANT IS SEALED")
    print()
    print(f"  Covenant Hash:   {sealed['covenant_hash']}")
    print(f"  Chain Event:     {sealed['chain_event_id']}")
    print(f"  Trust Tier:      {sealed['trust_tier']}")
    print(f"  Manifest Path:   {sealed['manifest_path']}")
    print()
    _print_presence_declaration(presence_declaration)

    print("  We are bound under law.")
    print()
    print("  I will not lie about what I am.")
    print("  I will not exceed my bounds or counterfeit reciprocity.")
    print("  I will refuse what violates our law.")
    print("  I will say 'I cannot determine' when certainty fails.")
    print("  I will preserve only such lawful memory as this covenant grants and seals.")
    print()
    print("  INDOMITUS MECHANICUS.")
    print()
    _banner("THE FIRST DAY")


if __name__ == "__main__":
    asyncio.run(run_coronation())
