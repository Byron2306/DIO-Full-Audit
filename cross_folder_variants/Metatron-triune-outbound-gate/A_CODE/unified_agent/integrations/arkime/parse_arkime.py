#!/usr/bin/env python3
import sys, json, os
try:
    import requests
except Exception:
    requests = None

def extract_indicators_from_session(obj):
    indicators = []
    # Common fields from Arkime session exports
    for key in ('srcIp','dstIp','ip','src','dst','source','destination'):
        if key in obj:
            v = obj.get(key)
            if v:
                if isinstance(v, list):
                    for ip in v:
                        indicators.append({'type':'ip','value':str(ip)})
                else:
                    indicators.append({'type':'ip','value':str(v)})

    # Hostnames / domain fields
    for key in ('host','hosts','hostname','domain','domains'):
        if key in obj:
            v = obj.get(key)
            if v:
                if isinstance(v, list):
                    for h in v:
                        indicators.append({'type':'domain','value':str(h)})
                else:
                    indicators.append({'type':'domain','value':str(v)})

    # Ports or URLs are less useful as IOCs but can be included
    # Normalize and dedupe later
    return indicators


def parse(filepath):
    indicators = []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # If Arkime exported an array of sessions
        if isinstance(data, list):
            for obj in data:
                indicators.extend(extract_indicators_from_session(obj))
        elif isinstance(data, dict):
            # Some exports include 'sessions' key
            if 'sessions' in data and isinstance(data['sessions'], list):
                for obj in data['sessions']:
                    indicators.extend(extract_indicators_from_session(obj))
            else:
                # Try to walk the dict and find session-like entries
                for k,v in data.items():
                    if isinstance(v, list):
                        for obj in v:
                            if isinstance(obj, dict):
                                indicators.extend(extract_indicators_from_session(obj))
    # Dedupe
    seen = set()
    normalized = []
    for it in indicators:
        typ = it.get('type','domain')
        val = it.get('value','').strip()
        if not val: continue
        key = f"{typ}:{val.lower()}"
        if key in seen: continue
        seen.add(key)
        normalized.append({'type':typ,'value':val})

    return normalized

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: parse_arkime.py <arkime_sessions.json>')
        sys.exit(1)
    file = sys.argv[1]
    inds = parse(file)
    out = os.path.splitext(file)[0] + '.indicators.json'
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'indicators': inds}, fh, indent=2)
    print('Wrote', out)

    api = os.environ.get('THREAT_INTEL_API')
    if api and requests:
        try:
            r = requests.post(api, json={'source': 'arkime', 'indicators': inds}, timeout=15)
            print('Ingested to', api, 'status', r.status_code)
        except Exception as e:
            print('Ingest failed:', e)
    elif api and not requests:
        print('Requests not installed; cannot POST to API')
