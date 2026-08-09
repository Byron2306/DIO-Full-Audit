#!/usr/bin/env python3
import sys, json, os
try:
    import requests
except Exception:
    requests = None

def parse(filepath):
    hosts = set()
    with open(filepath, 'r') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                j=json.loads(line)
            except Exception:
                continue
            name = j.get('name') or j.get('host')
            if name:
                hosts.add(name)
    return list(hosts)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: parse_amass.py <amass_json_lines_file>')
        sys.exit(1)
    file = sys.argv[1]
    hosts = parse(file)
    out = os.path.splitext(file)[0] + '.hosts.json'
    with open(out, 'w') as fh:
        json.dump({'hosts': hosts}, fh, indent=2)
    print('Wrote', out)

    api = os.environ.get('THREAT_INTEL_API')
    if api and requests:
        try:
            r = requests.post(api, json={
                'source': 'amass',
                'file': os.path.basename(file),
                'hosts': hosts
            }, timeout=10)
            print('Ingested to', api, 'status', r.status_code)
        except Exception as e:
            print('Ingest failed:', e)
    elif api and not requests:
        print('Requests library not installed; cannot POST to API. Install with: pip install requests')
