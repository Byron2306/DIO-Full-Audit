#!/usr/bin/env python3
"""Parser for PurpleSharp emulation output.
This script reads PurpleSharp JSON output and converts it to ingestable indicators
for the central threat intel ingestion API.

Usage: python parse_purplesharp.py /path/to/purplesharp_output.json
"""
import os
import sys
import json
import requests

API_URL = os.environ.get('API_URL', 'http://localhost:8001').rstrip('/')
INGEST = f"{API_URL}/api/integrations/ingest/direct"
TOKEN = os.environ.get('INTEGRATION_API_KEY', '')


def parse_file(path):
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    indicators = []
    # PurpleSharp may include artifacts like commands, dlls, registry paths, users
    for item in data.get('results', []) if isinstance(data, dict) else (data if isinstance(data, list) else []):
        # Example heuristic extraction
        if isinstance(item, dict):
            for k, v in item.items():
                if isinstance(v, str) and ('\\' in v or '/' in v) and len(v) > 3:
                    indicators.append({'type': 'path', 'value': v, 'confidence': 60, 'description': f'PurpleSharp:{k}'})
                elif isinstance(v, str) and v.count('.') >= 1:
                    indicators.append({'type': 'domain', 'value': v, 'confidence': 50})
    return indicators


def post_indicators(indicators):
    headers = {'Content-Type': 'application/json'}
    if TOKEN:
        headers['X-Internal-Token'] = TOKEN
    payload = {'source': 'purplesharp', 'indicators': indicators}
    r = requests.post(INGEST, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    if len(sys.argv) < 2:
        print('Usage: parse_purplesharp.py <file>')
        sys.exit(1)
    path = sys.argv[1]
    inds = parse_file(path)
    if not inds:
        print('No indicators found')
        return
    res = post_indicators(inds)
    print('Posted', res)


if __name__ == '__main__':
    main()
