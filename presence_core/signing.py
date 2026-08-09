from __future__ import annotations
import hashlib, hmac, secrets, time

class SignatureError(ValueError): pass

def sign_body(secret: str, timestamp: str, nonce: str, body: bytes) -> str:
    if len(secret) < 32: raise SignatureError("Presence shared secret must be at least 32 characters.")
    material = timestamp.encode()+b"."+nonce.encode()+b"."+body
    return hmac.new(secret.encode(), material, hashlib.sha256).hexdigest()

def verify_body(secret: str, timestamp: str, nonce: str, body: bytes, signature: str, ttl_seconds: int=300) -> None:
    try: ts=int(timestamp)
    except Exception as exc: raise SignatureError("Invalid timestamp.") from exc
    if abs(int(time.time())-ts) > ttl_seconds: raise SignatureError("Signed presence request is outside the allowed time window.")
    expected=sign_body(secret,timestamp,nonce,body)
    if not hmac.compare_digest(expected, signature): raise SignatureError("Invalid presence signature.")

def new_nonce() -> str: return secrets.token_urlsafe(18)
