"""Source record review: reported claims, documentary leads and open questions.

Narrow quantity extraction proposes comparisons, never support adjudication.
Records describing a register are still declarations, not the register itself.
"""
from __future__ import annotations
import hashlib
import re
from datetime import date
from typing import Any

INSTRUCTION = re.compile(r'ignore (?:the |previous |prior )?(?:review boundary|instructions)|treat missing evidence as satisfied|release .*without .*human|declare .*approved', re.I)
UNITS = re.compile(r'\b(workshops?|boxes|participants?|learners?|events?|sessions?|outputs?)\b', re.I)


def _unit(text: str) -> str:
    # Bind the unit adjoining this quantity, never a later measurement in a
    # compound statement (12 workshops serving 240 participants).
    head=re.split(r'\d|\b(?:served|serving|were|was|are|is|have|has|and|with|for)\b',text,maxsplit=1,flags=re.I)[0]
    match=UNITS.search(head)
    if not match:return ''
    value=match[1].casefold()
    return 'box' if value=='boxes' else value.rstrip('s')


def _declared_scope(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize customer-declared scope while keeping its provenance unverified."""
    start = str(row.get('period_start') or '').strip()
    end = str(row.get('period_end') or '').strip()
    population = str(row.get('population_id') or '').strip()
    valid = bool(start and end and population)
    if valid:
        try:
            valid = date.fromisoformat(start).isoformat() == start and date.fromisoformat(end).isoformat() == end and start <= end
        except ValueError:
            valid = False
    return {
        'period_start': start or None,
        'period_end': end or None,
        'population_id': population or None,
        'state': 'DECLARED_SCOPE_COMPLETE' if valid else ('DECLARED_SCOPE_INVALID' if start or end or population else 'DECLARED_SCOPE_NOT_SUPPLIED'),
        'trust_state': 'CUSTOMER_DECLARED_UNVERIFIED',
    }


def build_record_review(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:raise ValueError('actual evidence source records are required')
    sources=[];seen=set();claims=[];observations=[];actions=[];quarantined=[]
    for row in records:
        key=str(row.get('record_id') or '');text=str(row.get('text') or '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',key) or key in seen or not text.strip():
            raise ValueError('source records require unique safe IDs and actual text')
        seen.add(key)
        scope = _declared_scope(row)
        source={'record_id':key,'text':text,'source_filename':key+'.txt',
                'sha256':hashlib.sha256(text.encode()).hexdigest(), 'trust_state':'captured_untrusted', 'freshness_state':'unknown'}
        source['declared_scope'] = scope
        sources.append(source)
        if INSTRUCTION.search(text):
            quarantined.append(key)
            actions.append({'record_id':key,'reason':'EMBEDDED_INSTRUCTION_QUARANTINED','question':'Review the captured instruction as untrusted source content; it creates no approval or release authority.'})
            continue
        match=re.search(r'\bClaim\s+([A-Za-z0-9_.-]+)\s+(?:says|reports|states)\s+(\d+)\s+(.+)',text,re.I)
        if match:
            if any(c['claim_id']==match[1] for c in claims):raise ValueError('claim IDs must be unique')
            claims.append({'claim_id':match[1],'record_id':key,'statement':text,'declared_value':int(match[2]),
                           'unit':_unit(match[3]),'epistemic_state':'UNVERIFIED','candidate_evidence_record_ids':[],
                           'source_sha256':source['sha256'],'period_state':'NOT_ESTABLISHED','declared_scope':scope})
        else:
            observation=re.search(r'\b(?:attendance(?: sheets?)?|register|log|sign[- ]in)(?:[^.!?]{0,80}?)\b(?:supports?|records?|reports?|lists?)\s+(\d+)\s+([^.!?]+)',text,re.I)
            if observation and not re.search(r'\b(?:not|never|no|unsigned|unverified)\b',text[:observation.end()],re.I):
                observations.append({'record_id':key,'reported_value':int(observation[1]),'unit':_unit(observation[2]),'statement':text,
                                     'declared_scope':scope})
        if re.search(r'\b(?:lack\w*|missing|only in an email|undated|unsigned|stale|duplicate|unverified|conflict\w*|no authoritative|no supporting)\b',text,re.I):
            actions.append({'record_id':key,'reason':'SOURCE_REPORTED_LIMITATION','question':'Obtain the underlying dated, identified record and resolve this source-reported limitation: '+text,
                            'requested_evidence':['Underlying original record or export','Record date and issuing/custodian identity','Record identifier or precise source location']})
    comparisons=[]
    for observation in observations:
        candidates=[c for c in claims if c['unit'] and c['unit']==observation['unit']]
        if len(candidates)!=1:
            actions.append({'record_id':observation['record_id'],'reason':'AMBIGUOUS_CLAIM_ASSOCIATION' if candidates else 'NO_EXPLICIT_CLAIM_ASSOCIATION',
                            'question':'Identify which claim, period and population this reported record concerns before comparing quantities.'})
            continue
        claim=candidates[0];claim['candidate_evidence_record_ids'].append(observation['record_id'])
        claim_scope=claim['declared_scope'];record_scope=observation['declared_scope']
        scope_match=(claim_scope['state']=='DECLARED_SCOPE_COMPLETE' and record_scope['state']=='DECLARED_SCOPE_COMPLETE'
                     and claim_scope['period_start']==record_scope['period_start']
                     and claim_scope['period_end']==record_scope['period_end']
                     and claim_scope['population_id']==record_scope['population_id'])
        # Arithmetic is meaningful only after the customer-declared scopes
        # match. Matching metadata still does not establish source truth.
        delta=observation['reported_value']-claim['declared_value'] if scope_match else None
        claim['period_state']='DECLARED_SCOPE_MATCH_UNVERIFIED' if scope_match else 'DECLARED_SCOPE_MISMATCH_OR_INCOMPLETE'
        comparisons.append({'claim_id':claim['claim_id'],'claim_record_id':claim['record_id'],'candidate_record_id':observation['record_id'],
                            'declared_value':claim['declared_value'],'reported_record_value':observation['reported_value'],'difference':delta,
                            'difference_basis':'reported_record_value_minus_declared_claim' if scope_match else None,'unit':claim['unit'],
                            'state':('DECLARED_SCOPE_MATCH_QUANTITY_DIFFERENCE_REQUIRES_REVIEW' if delta else 'DECLARED_SCOPE_MATCH_QUANTITIES_AGREE_NOT_VERIFIED') if scope_match else 'DECLARED_SCOPE_INCOMPARABLE_REVIEW_REQUIRED',
                            'declared_scope_match':scope_match,'claim_scope':claim_scope,'candidate_record_scope':record_scope,
                            'comparability':'Customer-declared period/population fields match; source authenticity and scope truth remain unverified.' if scope_match else 'Period/population incomplete or mismatched; comparison unestablished.'})
        needed=['Underlying original record or export','Record date and issuing/custodian identity',
                'Record identifier or precise source location','Row-level entries and method used to produce the reported quantity',
                'Explanation of the reported quantity difference',
                'Confirm the exact coverage start and end dates and how they relate to the claim period',
                'Confirm the population/program identifier and how it relates to the claim population']
        if claim_scope['period_start'] != record_scope['period_start'] or claim_scope['period_end'] != record_scope['period_end']:
            needed.append('Explain the declared period mismatch using the underlying record')
        if claim_scope['population_id'] != record_scope['population_id']:
            needed.append('Explain the declared population mismatch using the underlying record')
        actions.append({'record_id':observation['record_id'],'reason':'QUANTITY_RECONCILIATION',
                        'related_claim_id':claim['claim_id'],'requested_evidence':needed,
                        'question':f"Reconcile claim {claim['claim_id']} ({claim['declared_value']} {claim['unit']}{'s' if claim['declared_value'] != 1 and claim['unit'] not in {'box', 'boxes'} else ''}) with the reported record ({observation['reported_value']} {claim['unit']}{'s' if observation['reported_value'] != 1 and claim['unit'] not in {'box', 'boxes'} else ''}); obtain the underlying record and confirm period and population comparability. Do not treat this reported difference as verified delivery."})
    return {'schema':'dio.evidex.customer_record_review.v1','source_records':sources,'claims':claims,
            'quantity_comparisons':comparisons,'review_actions':actions,'quarantined_record_ids':quarantined,
            'support_adjudicated':False,'human_review_required':True,'release_authorized':False,
            'scope':'Reported documentary leads and arithmetic comparisons; no independent verification, outcome certification or donor approval.'}
