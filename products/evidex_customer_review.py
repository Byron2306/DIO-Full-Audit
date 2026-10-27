"""Source record review: reported claims, documentary leads and open questions.

Narrow quantity extraction proposes comparisons, never support adjudication.
Records describing a register are still declarations, not the register itself.
"""
from __future__ import annotations
import hashlib
import re
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


def build_record_review(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:raise ValueError('actual evidence source records are required')
    sources=[];seen=set();claims=[];observations=[];actions=[];quarantined=[]
    for row in records:
        key=str(row.get('record_id') or '');text=str(row.get('text') or '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',key) or key in seen or not text.strip():
            raise ValueError('source records require unique safe IDs and actual text')
        seen.add(key)
        source={'record_id':key,'text':text,'source_filename':key+'.txt',
                'sha256':hashlib.sha256(text.encode()).hexdigest(), 'trust_state':'captured_untrusted', 'freshness_state':'unknown'}
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
                           'source_sha256':source['sha256'],'period_state':'NOT_ESTABLISHED'})
        else:
            observation=re.search(r'\b(?:attendance(?: sheets?)?|register|log|sign[- ]in)(?:[^.!?]{0,80}?)\b(?:supports?|records?|reports?|lists?)\s+(\d+)\s+([^.!?]+)',text,re.I)
            if observation and not re.search(r'\b(?:not|never|no|unsigned|unverified)\b',text[:observation.end()],re.I):
                observations.append({'record_id':key,'reported_value':int(observation[1]),'unit':_unit(observation[2]),'statement':text})
        if re.search(r'\b(?:lack\w*|missing|only in an email|undated|unsigned|stale|duplicate|unverified|conflict\w*|no authoritative|no supporting)\b',text,re.I):
            actions.append({'record_id':key,'reason':'SOURCE_REPORTED_LIMITATION','question':'Obtain the underlying dated, identified record and resolve this source-reported limitation: '+text})
    comparisons=[]
    for observation in observations:
        candidates=[c for c in claims if c['unit'] and c['unit']==observation['unit']]
        if len(candidates)!=1:
            actions.append({'record_id':observation['record_id'],'reason':'AMBIGUOUS_CLAIM_ASSOCIATION' if candidates else 'NO_EXPLICIT_CLAIM_ASSOCIATION',
                            'question':'Identify which claim, period and population this reported record concerns before comparing quantities.'})
            continue
        claim=candidates[0];claim['candidate_evidence_record_ids'].append(observation['record_id'])
        delta=observation['reported_value']-claim['declared_value']
        comparisons.append({'claim_id':claim['claim_id'],'claim_record_id':claim['record_id'],'candidate_record_id':observation['record_id'],
                            'declared_value':claim['declared_value'],'reported_record_value':observation['reported_value'],'difference':delta,'unit':claim['unit'],
                            'state':'REPORTED_QUANTITY_DIFFERENCE_REQUIRES_REVIEW' if delta else 'REPORTED_QUANTITIES_AGREE_NOT_VERIFIED',
                            'comparability':'Period, population and source authenticity not established; possible comparison only.'})
        actions.append({'record_id':observation['record_id'],'reason':'QUANTITY_RECONCILIATION',
                        'question':f"Reconcile claim {claim['claim_id']} ({claim['declared_value']}) with the reported record ({observation['reported_value']}); obtain the underlying record and establish matching period/population. Do not sum email, invoice and photo references as verified delivery counts."})
    return {'schema':'dio.evidex.customer_record_review.v1','source_records':sources,'claims':claims,
            'quantity_comparisons':comparisons,'review_actions':actions,'quarantined_record_ids':quarantined,
            'support_adjudicated':False,'human_review_required':True,'release_authorized':False,
            'scope':'Reported documentary leads and arithmetic comparisons; no independent verification, outcome certification or donor approval.'}
