import requests
import os
import uuid
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')


@pytest.fixture(scope='module')
def auth_token():
    email = f"honeypot_test_{uuid.uuid4().hex[:8]}@example.com"
    resp = requests.post(f"{BASE_URL}/api/auth/register", json={
        'email': email, 'password': 'testpass123', 'name': 'HP Test'
    })
    if resp.status_code != 200:
        pytest.skip('Could not register test user')
    return resp.json()['access_token']


def test_post_honeypot_alert(auth_token):
    url = f"{BASE_URL}/api/honeypots/alert"
    payload = {
        'source': 'canary-host-1',
        'payload': {'file': '/tmp/secret.txt', 'actor': 'unknown'},
        'severity': 'high'
    }
    resp = requests.post(url, json=payload, headers={'Authorization': f'Bearer {auth_token}'})
    assert resp.status_code == 200, f"Honeypot alert failed: {resp.text}"
    data = resp.json()
    assert 'honeypot_id' in data and 'alert_id' in data


def test_get_honeypot_alerts(auth_token):
    url = f"{BASE_URL}/api/honeypots/alerts"
    resp = requests.get(url, headers={'Authorization': f'Bearer {auth_token}'})
    assert resp.status_code == 200, f"List honeypots failed: {resp.text}"
    data = resp.json()
    assert isinstance(data, list)
