#!/usr/bin/env python3
import sys, json, os
try:
    import requests
except Exception:
    requests = None

# BloodHound JSON typically contains 'nodes' and 'relationships' arrays.
# We'll extract common node properties for Computer and User types.

def parse(filepath):
    indicators = []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        nodes = data.get('nodes') or data.get('data') or []
        if isinstance(nodes, dict) and 'nodes' in nodes:
            nodes = nodes['nodes']
        for node in nodes:
            try:
                label = node.get('label') or node.get('type') or ''
                props = node.get('properties') or node.get('data') or {}
                if isinstance(label, list):
                    label = label[0]
                label = label.lower()
                # Computer host
                if 'computer' in label:
                    name = props.get('name') or props.get('samAccountName') or props.get('hostname')
                    if name:
                        indicators.append({'type':'domain','value':name})
                    ip = props.get('ip') or props.get('lastLogonIp')
                    if ip:
                        indicators.append({'type':'ip','value':ip})
                # User principal
                if 'user' in label:
                    upn = props.get('name') or props.get('userPrincipalName') or props.get('samAccountName')
                    if upn:
                        indicators.append({'type':'email','value':upn})
            except Exception:
                continue

    # Deduplicate
    seen=set(); out=[]
    for it in indicators:
        t=it.get('type','domain'); v=it.get('value','').strip()
        if not v: continue
        key=f"{t}:{v.lower()}"
        if key in seen: continue
        seen.add(key); out.append({'type':t,'value':v})
    return out

if __name__=='__main__':
    if len(sys.argv)<2:
        print('Usage: parse_bloodhound.py <bloodhound_export.json>')
        sys.exit(1)
    file=sys.argv[1]
    inds=parse(file)
    out=os.path.splitext(file)[0]+'.indicators.json'
    with open(out,'w',encoding='utf-8') as fh:
        json.dump({'indicators':inds},fh,indent=2)
    print('Wrote',out)

    api=os.environ.get('THREAT_INTEL_API')
    if api and requests:
        try:
            r=requests.post(api,json={'source':'bloodhound','indicators':inds},timeout=15)
            print('Ingested to',api,'status',r.status_code)
        except Exception as e:
            print('Ingest failed:',e)
    elif api and not requests:
        print('Requests not installed; cannot POST to API')
