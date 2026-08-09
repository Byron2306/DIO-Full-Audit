#!/usr/bin/env python3
"""PurpleSharp runner via WinRM.

Usage:
  python run_purplesharp.py --host <host> --username <user> --password <pass> --outfile /tmp/out.json

This script uses pywinrm to connect to a Windows host and execute a PurpleSharp PowerShell command.
It captures JSON output and writes to outfile. Requires `pywinrm` installed and WinRM enabled on target.
"""
import argparse
import os
import sys
import json
from datetime import datetime

try:
    import winrm
except Exception:
    print('pywinrm is required to run this script. Install with pip install pywinrm')
    sys.exit(2)

DEFAULT_PS_CMD = r"try { Import-Module C:\\Tools\\PurpleSharp\\PurpleSharp.psm1 -ErrorAction Stop; $r = Invoke-PurpleSharp -OutputJson; $r | ConvertTo-Json -Depth 5 } catch { Write-Output (ConvertTo-Json @{error=$_.Exception.Message}) }"


def run_winrm_command(host, username, password, ps_cmd, use_ssl=False):
    protocol = 'https' if use_ssl else 'http'
    transport = 'ntlm' if '\\' in username else 'basic'
    session = winrm.Session(host, auth=(username, password), transport=transport)
    res = session.run_ps(ps_cmd)
    out = res.std_out.decode('utf-8', errors='ignore') if res.std_out else ''
    err = res.std_err.decode('utf-8', errors='ignore') if res.std_err else ''
    return res.status_code, out, err


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host', required=True)
    p.add_argument('--username', required=True)
    p.add_argument('--password', required=True)
    p.add_argument('--ps-cmd', default=None)
    p.add_argument('--outfile', default=None)
    p.add_argument('--use-ssl', action='store_true')
    args = p.parse_args()

    ps_cmd = args.ps_cmd or DEFAULT_PS_CMD

    status, out, err = run_winrm_command(args.host, args.username, args.password, ps_cmd, use_ssl=args.use_ssl)
    if status != 0:
        print('WinRM command failed', file=sys.stderr)
        print(err, file=sys.stderr)
        sys.exit(3)

    # try to parse JSON from output
    parsed = None
    try:
        parsed = json.loads(out)
    except Exception:
        # attempt to recover by searching for first JSON object
        import re
        m = re.search(r"\{.*\}", out, flags=re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = {'raw': out}
        else:
            parsed = {'raw': out}

    if args.outfile:
        with open(args.outfile, 'w', encoding='utf-8') as fh:
            json.dump({'timestamp': datetime.utcnow().isoformat(), 'host': args.host, 'result': parsed}, fh)
        print(args.outfile)
    else:
        print(json.dumps({'timestamp': datetime.utcnow().isoformat(), 'host': args.host, 'result': parsed}))


if __name__ == '__main__':
    main()
