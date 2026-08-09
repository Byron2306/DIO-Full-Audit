import os
import time
import requests

BASE = os.environ.get("SHIELD_BASE", "http://127.0.0.1:8080")

def hit(path, headers=None):
  r = requests.get(BASE + path, headers=headers or {})
  print(path, r.status_code, {k: v for k, v in r.headers.items() if k.lower().startswith("x-pebble")})
  return r

print("TEST 1: PASS_THROUGH expected (demo upstream response)")
hit("/cas/login")

print("TEST 2: FRICTION expected (missing UA), delay then forward")
hit("/cas/login", headers={"User-Agent": ""})

print("TEST 3: TRAP_SINK expected (/.env)")
t0 = time.time()
hit("/.env")
print("trap latency seconds", round(time.time()-t0, 2))

print("TEST 4: Repeat TRAP_SINK to trigger stonewall escalation")
for i in range(1, 25):
  hit("/wp-admin")
  time.sleep(0.05)

print("STATUS")
print(requests.get(BASE + "/__shield/status").json())
