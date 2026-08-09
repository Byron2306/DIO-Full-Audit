import os,time
from presence_core.signing import sign_body,verify_body,SignatureError

def test_hmac_roundtrip():
    secret='x'*40; body=b'{"hello":"world"}'; ts=str(int(time.time())); sig=sign_body(secret,ts,'nonce',body); verify_body(secret,ts,'nonce',body,sig,300)

def test_hmac_tamper_rejected():
    secret='x'*40; body=b'abc'; ts=str(int(time.time())); sig=sign_body(secret,ts,'n',body)
    try: verify_body(secret,ts,'n',b'abd',sig,300); assert False
    except SignatureError: pass
