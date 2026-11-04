"""Governed genre-to-composition planning for Sonoris.

Compiles genre grammar into an auditable behavior-first composition plan. It does
not emit notes or claim audio has passed genre validation; realization/rendering
and evidence-based audit are separate explicit stages.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'config/sonoris/genre_grammars_v1.json'


class GenreCompilerError(ValueError):
    pass


def _read_catalog(path: str | Path = CATALOG) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 'dio.sonoris.genre_grammar_catalog.v1':
        raise GenreCompilerError('unsupported Sonoris genre grammar catalog')
    if not isinstance(data.get('profiles'), dict) or not data['profiles']:
        raise GenreCompilerError('genre catalog has no profiles')
    return data


def genre_catalog_snapshot(path: str | Path = CATALOG) -> dict[str, Any]:
    data = _read_catalog(path)
    raw = Path(path).read_bytes()
    return {
        'schema': 'dio.sonoris.genre_compiler_capability.v1',
        'compiler_version': data['compiler_version'],
        'catalog_path': str(Path(path).resolve()),
        'catalog_sha256': hashlib.sha256(raw).hexdigest(),
        'genres': {key: {'id': row['id'], 'label': row['label'], 'family': row['family'],
                         'gestures': sorted(row['gestures']),
                         'form_sections': len(row['form']),
                         'song_types': [{'key': item['key'], 'label': item['label']} for item in row.get('song_types') or []],
                         'reference_artists': row.get('reference_artists') or []}
                   for key, row in sorted(data['profiles'].items())},
        'stages': ['SELECT_GRAMMAR', 'COMPILE_BEHAVIOR_PLAN', 'REALIZE_NOTES_AND_ARTICULATIONS',
                   'RENDER_INSTRUMENTS', 'AUDIT_GENRE_EVIDENCE', 'HUMAN_LISTENING_REVIEW'],
        'claim_boundary': 'A compiled plan expresses intended behavior. Genre conformance requires measured composition/audio evidence and human listening.'
    }


def _parse_meter(meter: str) -> tuple[int, int] | None:
    if meter == 'free':
        return None
    try:
        n, d = (int(part) for part in meter.split('/', 1))
    except (ValueError, TypeError):
        raise GenreCompilerError(f'invalid meter: {meter!r}')
    if not (1 <= n <= 16 and d in (2, 4, 8, 16)):
        raise GenreCompilerError(f'unsupported meter: {meter!r}')
    return n, d


def _scale_form(form: list[dict[str, Any]], target_bars: int) -> list[dict[str, Any]]:
    total = sum(int(section['bars']) for section in form)
    if target_bars < len(form):
        raise GenreCompilerError('requested bar count is too short to preserve this genre form')
    ratios = [int(section['bars']) * target_bars / total for section in form]
    bars = [max(1, int(value)) for value in ratios]
    # Distribute rounding drift by largest fractional remainder, preserving every section.
    delta = target_bars - sum(bars)
    order = sorted(range(len(form)), key=lambda i: ratios[i] - int(ratios[i]), reverse=(delta > 0))
    cursor = 0
    while delta:
        index = order[cursor % len(order)]
        if delta > 0:
            bars[index] += 1; delta -= 1
        elif bars[index] > 1:
            bars[index] -= 1; delta += 1
        cursor += 1
    return [dict(section, bars=bars[i]) for i, section in enumerate(form)]


def compile_composition_request(request: Mapping[str, Any], *, catalog_path: str | Path = CATALOG) -> dict[str, Any]:
    """Compile a behavior-first, genre-governed composition brief into a plan."""
    catalog = _read_catalog(catalog_path)
    primary_key = str(request.get('genre', '')).strip().lower().replace('-', '_').replace(' ', '_')
    profiles = catalog['profiles']
    if primary_key not in profiles:
        raise GenreCompilerError(f'unknown genre {primary_key!r}; available: {", ".join(sorted(profiles))}')
    primary = profiles[primary_key]
    variant_key = str(request.get('song_type') or '').strip().lower()
    variants = {row['key']: row for row in primary.get('song_types') or []}
    if variant_key and variant_key not in variants:
        raise GenreCompilerError(f'unknown song type {variant_key!r} for {primary["label"]}')
    variant = variants.get(variant_key)
    secondary_key = request.get('secondary_genre')
    secondary_weight = float(request.get('secondary_weight', 0.0))
    if not 0.0 <= secondary_weight <= float(catalog['blend_policy']['secondary_weight_max']):
        raise GenreCompilerError('secondary genre weight must be between 0 and 0.35')
    secondary = None
    if secondary_key:
        secondary_key = str(secondary_key).strip().lower().replace('-', '_').replace(' ', '_')
        if secondary_key not in profiles:
            raise GenreCompilerError(f'unknown secondary genre: {secondary_key}')
        if secondary_key == primary_key and secondary_weight:
            raise GenreCompilerError('primary and secondary genre must differ')
        secondary = profiles[secondary_key]
    elif secondary_weight:
        raise GenreCompilerError('secondary_weight requires secondary_genre')

    default_bpm = round(primary['preferred_bpm'] * float(variant.get('tempo_factor', 1))) if variant else primary['preferred_bpm']
    default_bpm = min(int(primary['tempo_bpm'][3]), max(int(primary['tempo_bpm'][0]), default_bpm))
    allowed_ranges = primary.get('tempo_ranges') or [[primary['tempo_bpm'][0], primary['tempo_bpm'][3]]]
    if not any(int(lo) <= default_bpm <= int(hi) for lo, hi in allowed_ranges):
        default_bpm = min((int(edge) for lo, hi in allowed_ranges for edge in (lo, hi)), key=lambda edge: abs(edge - default_bpm))
    bpm = int(request.get('tempo_bpm', default_bpm))
    ranges = primary.get('tempo_ranges') or [[primary['tempo_bpm'][0], primary['tempo_bpm'][3]]]
    if not any(int(lo) <= bpm <= int(hi) for lo, hi in ranges):
        spans = ', '.join(f'{lo}..{hi}' for lo, hi in ranges)
        raise GenreCompilerError(f'{bpm} BPM is outside {primary["label"]} allowed tempo bands {spans}')
    preferred_lo, preferred_hi = primary['tempo_bpm'][1:3]
    default_meter = primary['default_meter']
    if variant_key == 'fracture':
        default_meter = next((m for m in primary['meters'] if m in {'5/4', '7/8'}), default_meter)
    elif variant_key == 'space':
        default_meter = next((m for m in primary['meters'] if m in {'6/8', '3/4'}), default_meter)
    meter = str(request.get('meter', default_meter))
    if meter not in primary['meters']:
        raise GenreCompilerError(f'{meter} is not an allowed meter for {primary["label"]}')
    _parse_meter(meter)
    form = list(primary['form'])
    if variant_key == 'fracture' and len(form) > 3:
        form = form[:2] + list(reversed(form[2:-1])) + form[-1:]
    elif variant_key == 'space' and len(form) > 2:
        form = form[:2] + [{'section': 'Suspended return', 'gesture': form[1]['gesture'], 'bars': 4}] + form[2:]
    default_bars = round(sum(int(section['bars']) for section in form) * float(variant.get('bar_factor', 1))) if variant else sum(int(section['bars']) for section in form)
    bars = int(request.get('bars', default_bars))
    if not 1 <= bars <= 512:
        raise GenreCompilerError('bars must be between 1 and 512')
    sections = _scale_form(form, bars)
    cursor = 0
    for index, section in enumerate(sections, 1):
        section['index'] = index
        section['start_bar'] = cursor
        section['end_bar'] = cursor + section['bars']
        section['motif_id'] = f'M{min(index, 3)}'
        cursor += section['bars']

    roles = {key: list(value) for key, value in primary['roles'].items()}
    if secondary:
        secondary_roles = {key: list(value) for key, value in secondary['roles'].items()}
        roles['secondary_color_roles'] = sorted({instrument for values in secondary_roles.values() for instrument in values})
    constraints = dict(primary['structural_laws'])
    plan = {
        'schema': 'dio.sonoris.governed_composition_plan.v1',
        'compiler_version': catalog['compiler_version'],
        'request': {'title': str(request.get('title', 'Untitled Sonoris composition')),
                    'mood': str(request.get('mood', 'unspecified')), 'purpose': str(request.get('purpose', 'composition'))},
        'grammar': {'primary': {'key': primary_key, 'id': primary['id'], 'label': primary['label']},
                    'song_type': ({'key': variant_key, 'label': variant['label'], 'energy': variant['energy']} if variant else None),
                    'secondary': ({'key': secondary_key, 'id': secondary['id'], 'label': secondary['label'],
                                   'weight': secondary_weight} if secondary else None),
                    'blend_policy': catalog['blend_policy'], 'primary_owns_structure': True},
        'musical_frame': {'tempo_bpm': bpm, 'tempo_position': 'preferred' if preferred_lo <= bpm <= preferred_hi else 'allowed_band',
                          'tempo_ranges_bpm': ranges, 'meter': meter, 'bars': bars, 'tonal_center': request.get('tonal_center', primary['harmony']['center']),
                          'harmony_behaviors': list(primary['harmony']['behaviors'])},
        'structural_laws': constraints,
        'sections': sections,
        'gesture_dictionary': primary['gestures'],
        'instrument_roles': roles,
        'performance_grammar': primary['performance'],
        'production_grammar': primary['production'],
        'compiler_sequence': ['COMPILE_GESTURES', 'ASSIGN_MOTIF_IDENTITIES', 'ALLOCATE_INSTRUMENT_ROLES',
                              'REALIZE_HARMONY_AND_RHYTHM', 'SELECT_SUPPORTED_ARTICULATIONS',
                              'HUMANIZE_PERFORMANCE', 'RENDER_STEMS', 'MEASURE_AND_AUDIT'],
        'audit_gates': ['form_and_section_contrast', 'gesture_and_motif_distinction', 'genre_harmony_behaviors',
                        'instrument_interaction', 'articulation_support', 'production_laws',
                        'rights_and_source_receipts', 'human_listening_review'],
        'evidence_state': 'PLAN_COMPILED_AUDIO_NOT_YET_REALIZED',
        'release_authorized': False,
    }
    return plan


def audit_composition_evidence(plan: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Audit supplied measured evidence against governed constraints; missing evidence stays UNKNOWN."""
    if plan.get('schema') != 'dio.sonoris.governed_composition_plan.v1':
        raise GenreCompilerError('unsupported composition plan')
    profile = _read_catalog()['profiles'][plan['grammar']['primary']['key']]
    checks: list[dict[str, Any]] = []
    def check(name: str, passed: bool | None, detail: str):
        checks.append({'gate': name, 'state': 'PASS' if passed is True else 'FAIL' if passed is False else 'UNKNOWN', 'detail': detail})
    tempo = evidence.get('tempo_bpm')
    ranges = profile.get('tempo_ranges') or [[profile['tempo_bpm'][0], profile['tempo_bpm'][3]]]
    allowed = lambda value: any(float(lo) <= float(value) <= float(hi) for lo, hi in ranges)
    bands = ', '.join(f'{lo}..{hi}' for lo, hi in ranges)
    check('tempo_range', None if tempo is None else allowed(tempo),
          f'{tempo} BPM observed; allowed bands {bands}' if tempo is not None else 'audio or MIDI tempo evidence missing')
    meter = evidence.get('meter')
    check('meter', None if meter is None else meter == plan['musical_frame']['meter'],
          f'{meter} observed' if meter is not None else 'meter evidence missing')
    required_gestures = {section['gesture'] for section in plan['sections']}
    observed = evidence.get('gestures')
    check('gesture_coverage', None if observed is None else required_gestures.issubset(set(observed)),
          'required gestures: ' + ', '.join(sorted(required_gestures)))
    structural = evidence.get('structural_laws')
    if structural is None:
        for law, required in profile['structural_laws'].items():
            if required is True and law.endswith('_required'):
                check(law, None, 'structural evidence missing')
    else:
        for law, required in profile['structural_laws'].items():
            if required is True and law.endswith('_required'):
                check(law, bool(structural.get(law)) if law in structural else None,
                      'required by primary genre grammar')
    for requirement in profile.get('acceptance_requirements', ()):
        field = requirement['field']; op = requirement['op']; expected = requirement['value']
        observed_value = evidence.get(field)
        if observed_value is None:
            passed = None
        elif op == 'eq':
            passed = observed_value == expected
        elif op == 'contains':
            passed = expected in observed_value
        elif op == 'contains_any':
            passed = any(item in observed_value for item in expected)
        else:
            raise GenreCompilerError(f'unsupported acceptance operator: {op}')
        check('acceptance:' + field + ':' + str(expected), passed,
              requirement.get('reason', field) + ('; evidence missing' if observed_value is None else ''))
    statuses = {row['state'] for row in checks}
    state = 'REJECT' if 'FAIL' in statuses else 'NEEDS_EVIDENCE' if 'UNKNOWN' in statuses else 'PASS_REQUIRES_HUMAN_LISTENING'
    return {'schema': 'dio.sonoris.genre_evidence_audit.v1', 'genre': profile['id'], 'state': state,
            'checks': checks, 'human_listening_review_required': True, 'release_authorized': False}
