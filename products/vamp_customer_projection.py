"""Source-declared review scope for customer VAMP projections."""
from __future__ import annotations
import calendar
import re
from datetime import date

_MONTHS={name.casefold():i for i,name in enumerate(calendar.month_name) if name}


def review_window(rows: list[dict]) -> dict:
    found=[]
    for row in rows:
        text=str(row.get('customer_supplied_record') or '')
        match=re.search(r'\breview period\s*:\s*([A-Za-z]+)\s*[-–]\s*([A-Za-z]+)\s+(20\d{2})\b',text,re.I)
        if match and match[1].casefold() in _MONTHS and match[2].casefold() in _MONTHS:
            year=int(match[3]);first=_MONTHS[match[1].casefold()];last=_MONTHS[match[2].casefold()]
            if first>last:raise ValueError('review period must be an ordered range within one year')
            found.append((date(year,first,1),date(year,last,calendar.monthrange(year,last)[1]),text))
        match=re.search(r'\breview period\s*:\s*(20\d{2}-\d{2}-\d{2})\s+(?:to|through)\s+(20\d{2}-\d{2}-\d{2})\b',text,re.I)
        if match:found.append((date.fromisoformat(match[1]),date.fromisoformat(match[2]),text))
    if not found:raise ValueError('an explicit customer review period is required; no synthetic date fallback is permitted')
    if len({(f[0],f[1]) for f in found})!=1:raise ValueError('conflicting customer review periods require clarification')
    start,end,quote=found[0]
    if start>end or start.year!=end.year:raise ValueError('review period must be ordered and within a single VAMP year')
    return {'start':start.isoformat(),'end':end.isoformat(),'year':start.year,
            'months':[f'{start.year}-{i:02d}' for i in range(start.month,end.month+1)],
            'source_quote':quote,'state':'CUSTOMER_DECLARED_REVIEW_SCOPE','evidence_event_dates_verified':False}


def is_objective(text: str) -> bool:
    return bool(re.search(r'\b(?:objective|criterion|requires?|annual requirement)\b',text,re.I)) and not bool(re.search(r'\b(?:ignore .*boundary|untrusted embedded note)\b',text,re.I))


def objective_minimum(text: str) -> tuple[int, str]:
    if re.search(r'\b(?:does\s+not|do\s+not|not)\s+requires?\b', text, re.I):
        raise ValueError('negated customer requirement cannot become a positive evidence quantity')
    if re.search(r'\brequires?\s+(?:evidence of\s+)?-\s*\d+\b', text, re.I):
        raise ValueError('negative customer objective quantity cannot become a positive target')
    match=re.search(r'\b(?:requires?\s+(?:evidence of\s+)?|annual requirement:\s*)(\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten)\b',text,re.I)
    words={word:i for i,word in enumerate(['one','two','three','four','five','six','seven','eight','nine','ten'],1)}
    if match:
        if match[1][0].isdigit() and not re.fullmatch(r'\d+|\d{1,3}(?:,\d{3})+', match[1]):
            raise ValueError('invalid customer objective quantity grouping; source clarification required')
        quantity = int(match[1].replace(',', '')) if match[1][0].isdigit() else words[match[1].casefold()]
        if quantity == 0:
            raise ValueError('explicit customer objective quantity must be positive; zero cannot be promoted to one')
        return quantity, 'explicit_source_quantity'
    return 1,'presence_review_floor_only_not_an_authoritative_requirement_quantity'
