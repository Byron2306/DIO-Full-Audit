import requests
import time

def test_connection(url):
    try:
        resp = requests.get(f"{url.rstrip('/')}/v1/accounts/hivenance-system", timeout=3)
        print(f"URL: {url} | Status: {resp.status_code}")
        return True
    except Exception as e:
        print(f"URL: {url} | Error: {e}")
        return False

urls = [
    "http://localhost:9009",
    "http://127.0.0.1:9009",
    "http://host.docker.internal:9009"
]
for u in urls:
    test_connection(u)
