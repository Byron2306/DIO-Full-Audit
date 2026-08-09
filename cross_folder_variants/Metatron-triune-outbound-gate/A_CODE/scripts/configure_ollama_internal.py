import requests
import os

BACKEND = os.environ.get('BACKEND_URL','http://localhost:8001')
LOGIN_URL = BACKEND + '/api/auth/login'
CONFIG_URL = BACKEND + '/api/advanced/ai/ollama/configure'

email = os.environ.get('ADMIN_EMAIL','buntbyron@gmail.com')
password = os.environ.get('ADMIN_PASSWORD','Sephiroth23!')

print('Logging in...')
resp = requests.post(LOGIN_URL, json={'email': email, 'password': password}, timeout=10)
if resp.status_code != 200:
    print('Login failed:', resp.status_code, resp.text)
    raise SystemExit(1)

token = resp.json().get('access_token')
print('Got token:', token[:40]+'...')

headers = {'Authorization': f'Bearer {token}'}
body = {'base_url': 'http://ollama:11434', 'model': 'mistral'}
print('Configuring Ollama at', body['base_url'])
resp = requests.post(CONFIG_URL, json=body, headers=headers, timeout=10)
print('Status', resp.status_code)
print(resp.text)
