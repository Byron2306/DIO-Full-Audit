import requests
import sys
import time

def test_nginx_root():
    print("[+] Testing Nginx Root (localhost:3000)...")
    try:
        r = requests.get("http://localhost:3000", timeout=5)
        print(f"    - Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"    - FAILED: {e}")
        return False

def test_arda_dashboard():
    print("[+] Testing Arda Dashboard (localhost:3001)...")
    try:
        r = requests.get("http://localhost:3001", timeout=5)
        print(f"    - Status: {r.status_code}")
        print(f"    - URL: {r.url}")
        return r.status_code == 200 and "/valinor" in r.url
    except Exception as e:
        print(f"    - FAILED: {e}")
        return False

def test_backend_health():
    print("[+] Testing Backend Health (localhost:8001/health)...")
    try:
        r = requests.get("http://localhost:8001/health", timeout=5)
        print(f"    - Status: {r.status_code}")
        print(f"    - Data: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"    - FAILED: {e}")
        return False

if __name__ == "__main__":
    print("--- SOVEREIGN SUBSTRATE VERIFICATION ---")
    results = [
        test_nginx_root(),
        test_arda_dashboard(),
        test_backend_health()
    ]
    
    if all(results):
        print("\n[SUCCESS] Substrate verified from the ground up.")
        sys.exit(0)
    else:
        print("\n[FAILURE] Potential dissonance detected in substrate.")
        sys.exit(1)
