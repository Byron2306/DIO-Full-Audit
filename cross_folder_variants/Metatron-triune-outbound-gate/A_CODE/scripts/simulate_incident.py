import requests, os, json
BACKEND = os.environ.get('BACKEND_URL','http://localhost:8001')
LOGIN = BACKEND + '/api/auth/login'
LOKI = BACKEND + '/api/loki/ingest'
CAMPAIGN = BACKEND + '/api/metatron/campaign'

email = os.environ.get('ADMIN_EMAIL','buntbyron@gmail.com')
password = os.environ.get('ADMIN_PASSWORD','Sephiroth23!')

print('Logging in...')
resp = requests.post(LOGIN, json={'email': email, 'password': password}, timeout=10)
if resp.status_code != 200:
    print('Login failed', resp.status_code, resp.text); raise SystemExit(1)

token = resp.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

payloads = [
    {"kind":"detection","id":"host-1","entity_type":"host","attributes":{"sig":"suspicious_process","risk_score":0.92,"os":"linux","last_seen":"2026-03-14T10:00:00Z"}},
    {"kind":"detection","id":"db-1","entity_type":"host","attributes":{"sig":"suspicious_db_access","risk_score":0.65,"service":"postgres"}},
    {"kind":"detection","id":"user-1","entity_type":"user","attributes":{"sig":"phish_click","risk_score":0.82}},
    {"kind":"detection","id":"file-1","entity_type":"file","attributes":{"sig":"sensitive_exfil","risk_score":0.88}},
    {"kind":"edge","source":"host-1","target":"db-1","relation":"accessed"},
    {"kind":"edge","source":"user-1","target":"host-1","relation":"logged_into"}
]

print('Posting world-model payloads...')

def post_with_retries(url, j, headers, tries=3, timeout=30):
    for attempt in range(1, tries+1):
        try:
            r = requests.post(url, json=j, headers=headers, timeout=timeout)
            return r
        except Exception as e:
            print(f"attempt {attempt} failed: {e}")
    raise SystemExit('All attempts failed')

for p in payloads:
    r = post_with_retries(LOKI, p, headers)
    try:
        print(p.get('id') or p.get('kind'), '->', r.status_code, r.json())
    except Exception:
        print(p.get('id') or p.get('kind'), '->', r.status_code, r.text)

camp = {
    "name": "Exfiltration Campaign Alpha",
    "objective": "exfiltrate-data",
    "stage": "active",
    "confidence": 0.91,
    "entities": ["host-1","db-1","user-1"],
    "attributes": {"origin_host":"host-1","predicted_next":["exfiltrate:file-1"],"evidence":["suspicious_process","sensitive_exfil"]}
}
rc = requests.post(CAMPAIGN, json=camp, headers=headers, timeout=10)
print('campaign ->', rc.status_code, rc.json() if rc.status_code==200 else rc.text)

print('Done. You can now run Michael analysis to rank actions.')
