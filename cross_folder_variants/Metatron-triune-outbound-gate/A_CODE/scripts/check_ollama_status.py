import requests, os
BACKEND = os.environ.get('BACKEND_URL','http://localhost:8001')
LOGIN = BACKEND + '/api/auth/login'
STATUS = BACKEND + '/api/advanced/ai/ollama/status'
resp = requests.post(LOGIN, json={'email': os.environ.get('ADMIN_EMAIL','buntbyron@gmail.com'), 'password': os.environ.get('ADMIN_PASSWORD','Sephiroth23!')}, timeout=10)
if resp.status_code!=200:
    print('login failed', resp.status_code, resp.text); raise SystemExit(1)
token = resp.json().get('access_token')
headers={'Authorization':f'Bearer {token}'}
r = requests.get(STATUS, headers=headers, timeout=10)
print('Status', r.status_code)
print(r.text)
