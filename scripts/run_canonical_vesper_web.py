#!/usr/bin/env python3
"""Run DIO's existing web reconciliation lane with its existing local signing identity."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def core_public_secret(pid: int, *, proc_root: Path=Path('/proc')) -> str:
    if pid<=0:
        raise ValueError('canonical_presence_core_not_running')
    proc=proc_root/str(pid)
    args=(proc/'cmdline').read_bytes().decode().split('\0')
    scripts=[Path(a) for a in args if a.endswith('/serve_presence_bridge.py')]
    if len(scripts)!=1 or scripts[0].resolve()!=ROOT/'scripts/serve_presence_bridge.py':
        raise ValueError('core_source_owner_mismatch')
    # Read only this identity into the child environment. Never print or persist it.
    key=b'DIO_PRESENCE_PUBLIC_SHARED_SECRET='
    for item in (proc/'environ').read_bytes().split(b'\0'):
        if item.startswith(key):
            value=item[len(key):].decode()
            if value.strip():return value
    raise ValueError('public_signing_secret_missing_from_canonical_core')


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Process existing web custody using the existing authority checks.')
    parser.add_argument('--watch',action='store_true',help='Continue polling web custody; requires --run.')
    args=parser.parse_args()
    if args.watch and not args.run:parser.error('--watch requires --run')
    config_path=ROOT/'config/dio_presence_edge.staging.json'
    config=json.loads(config_path.read_text())
    if config.get('core_url') not in ('http://127.0.0.1:8787','http://localhost:8787'):
        raise ValueError('nonlocal_presence_core_refused')
    url=urlsplit(str(config.get('base_url','')))
    if url.scheme!='https' or url.netloc!='dio-presence-gateway-staging.dio-workflows.workers.dev' or url.path not in ('','/'):
        raise ValueError('unreviewed_web_transport_target')
    status=subprocess.run(['systemctl','--user','show','dio-presence-local.service','-p','MainPID','--value'],
                          check=True,capture_output=True,text=True)
    secret=core_public_secret(int(status.stdout.strip() or '0'))
    token=Path(config['edge_token_path']).expanduser()
    if not token.is_file() or not token.read_text().strip():
        raise ValueError('existing_edge_pull_token_missing')
    print(json.dumps({'schema':'dio.canonical_web_reconciler.preflight.v1','ready':True,
        'source_owner':'DIO-Full-Audit','transport':config['base_url'],
        'public_signing_identity':'existing_canonical_core','web_only':True,
        'telegram_processed':False,'secrets_printed':False,'custom_domain_changed':False}),flush=True)
    if not args.run:return 0
    env=dict(os.environ);env['DIO_PRESENCE_PUBLIC_SHARED_SECRET']=secret
    command=[sys.executable,str(ROOT/'scripts/sync_vesper_presence_edge.py'),
             '--config',str(config_path),'--web-only']
    if args.watch:command.append('--watch')
    os.execve(sys.executable,command,env)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        # No raw process environment or configuration value is included in errors.
        print('Vesper web reconciliation held: '+str(exc),file=sys.stderr)
        raise SystemExit(2)
