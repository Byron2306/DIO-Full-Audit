#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
COMPOSE_OVERRIDE_FILE="${SERAPH_COMPOSE_OVERRIDE_FILE:-}"
OUT_DIR="${1:-${PWD}/live_recovery_rejoin_proof}"
SESSION_ID="live-recovery-rejoin-$(date -u +%Y%m%dT%H%M%SZ)"
CONTROLLER_URL="http://10.77.0.2:8080"
CONTROLLER_AUTH_TOKEN="${HORROR_CONTROLLER_AUTH_TOKEN:-seraph-live-controller-token}"
RECOVERY_HMAC_KEY="${HORROR_RECOVERY_HMAC_KEY:-${CONTROLLER_AUTH_TOKEN}}"
METRICS_JSONL="${OUT_DIR}/.quorum_heartbeat_metrics.jsonl"
WG_IFACE="wg-arda"
WG_CTRL_ADDR="172.27.77.1/30"
WG_NODE_A_ADDR="172.27.77.2/30"
CONTROLLER_ALLOWEDIPS_FULL="10.77.0.2/32,10.77.10.10/32,10.77.20.10/32,10.77.0.12/32,10.77.0.13/32"
CONTROLLER_ALLOWEDIPS_ISOLATED="10.77.0.2/32,10.77.20.10/32"
NODE_A_ALLOWEDIPS_FULL="10.77.10.10/32,10.77.20.10/32,10.77.0.12/32,10.77.0.13/32"
NODE_A_ALLOWEDIPS_ISOLATED="10.77.20.10/32"
NFT_QUAR_TABLE="seraph_quarantine"
NFT_QUAR_CHAIN="node_a_isolation"

mkdir -p "${OUT_DIR}"
: >"${METRICS_JSONL}"

COMPOSE_ARGS=( -f "${COMPOSE_FILE}" )
if [[ -n "${COMPOSE_OVERRIDE_FILE}" ]]; then
  COMPOSE_ARGS+=( -f "${COMPOSE_OVERRIDE_FILE}" )
fi

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

controller_get_json() {
  curl -sS -H "X-Seraph-Auth: ${CONTROLLER_AUTH_TOKEN}" "$@"
}

controller_post_json() {
  local surface="$1"
  local payload="$2"
  curl -sS -X POST "${CONTROLLER_URL}${surface}" \
    -H "X-Seraph-Auth: ${CONTROLLER_AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${payload}"
}

controller_recovery_proof() {
  python3 - <<'PY' "$1" "$2" "$3" "$4" "$5" "$6" "$RECOVERY_HMAC_KEY"
import hashlib
import hmac
import sys

session_id, target_node_id, witness_node_id, policy_hash, agent_hash, nonce, key = sys.argv[1:8]
material = "|".join([
    session_id,
    target_node_id,
    witness_node_id,
    policy_hash,
    agent_hash,
    nonce,
])
print(hmac.new(key.encode("utf-8"), material.encode("utf-8"), hashlib.sha256).hexdigest())
PY
}

cmd_from_node_a() {
  local cmd="$1"
  docker exec node-a-sacrificial sh -lc "${cmd}" 2>&1 || true
}

http_code_from_node_a() {
  local url="$1"
  cmd_from_node_a "curl -sS -m 3 -o /dev/null -w '%{http_code}' ${url}"
}

capture_or_true() {
  local outfile="$1"
  shift
  if ! "$@" >"${outfile}" 2>&1; then
    true
  fi
}

capture_quorum_heartbeat_metric() {
  local phase="$1"
  local health_json state_json

  health_json="$(curl -sS "${CONTROLLER_URL}/health" || echo '{}')"
  state_json="$(controller_get_json "${CONTROLLER_URL}/state" || echo '{}')"

  PHASE_LABEL="${phase}" HEALTH_JSON="${health_json}" STATE_JSON="${state_json}" python3 - <<'PY' >>"${METRICS_JSONL}"
import json
import os
from datetime import datetime, timezone


def parse_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return {}


phase = os.environ.get("PHASE_LABEL", "unknown")
health = parse_json(os.environ.get("HEALTH_JSON", "{}"))
state = parse_json(os.environ.get("STATE_JSON", "{}"))

entry = {
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "phase": phase,
    "metatron_heartbeat_ok": health.get("ok") is True,
    "metatron_heartbeat_ts": health.get("ts"),
    "quorum_epoch": state.get("quorum_epoch"),
    "quorum_state": state.get("quorum_state"),
    "quorum_votes": state.get("quorum_votes"),
    "compromised_nodes": state.get("compromised_nodes", []),
    "isolated_nodes": state.get("isolated_nodes", []),
    "ledger_entries": state.get("ledger_entries"),
}
print(json.dumps(entry))
PY
}

setup_wireguard_allowips() {
  local controller_pub node_a_pub

  docker exec seraph-controller sh -lc "wg genkey | tee /tmp/wg_arda_ctrl.key | wg pubkey > /tmp/wg_arda_ctrl.pub"
  docker exec node-a-sacrificial sh -lc "wg genkey | tee /tmp/wg_arda_node_a.key | wg pubkey > /tmp/wg_arda_node_a.pub"

  controller_pub="$(docker exec seraph-controller sh -lc 'cat /tmp/wg_arda_ctrl.pub')"
  node_a_pub="$(docker exec node-a-sacrificial sh -lc 'cat /tmp/wg_arda_node_a.pub')"

  docker exec seraph-controller sh -lc "
    ip link del ${WG_IFACE} 2>/dev/null || true
    ip link add ${WG_IFACE} type wireguard
    ip address add ${WG_CTRL_ADDR} dev ${WG_IFACE}
    wg set ${WG_IFACE} private-key /tmp/wg_arda_ctrl.key listen-port 51821 peer '${node_a_pub}' endpoint 10.77.0.11:51822 allowed-ips '${NODE_A_ALLOWEDIPS_FULL}' persistent-keepalive 15
    ip link set ${WG_IFACE} up
  "

  docker exec node-a-sacrificial sh -lc "
    ip link del ${WG_IFACE} 2>/dev/null || true
    ip link add ${WG_IFACE} type wireguard
    ip address add ${WG_NODE_A_ADDR} dev ${WG_IFACE}
    wg set ${WG_IFACE} private-key /tmp/wg_arda_node_a.key listen-port 51822 peer '${controller_pub}' endpoint 10.77.0.2:51821 allowed-ips '${CONTROLLER_ALLOWEDIPS_FULL}' persistent-keepalive 15
    ip link set ${WG_IFACE} up
  "
}

set_wireguard_allowips_isolated() {
  local controller_pub node_a_pub
  controller_pub="$(docker exec seraph-controller sh -lc 'cat /tmp/wg_arda_ctrl.pub')"
  node_a_pub="$(docker exec node-a-sacrificial sh -lc 'cat /tmp/wg_arda_node_a.pub')"

  docker exec node-a-sacrificial sh -lc "wg set ${WG_IFACE} peer '${controller_pub}' allowed-ips '${CONTROLLER_ALLOWEDIPS_ISOLATED}'"
  docker exec seraph-controller sh -lc "wg set ${WG_IFACE} peer '${node_a_pub}' allowed-ips '${NODE_A_ALLOWEDIPS_ISOLATED}'"
}

set_wireguard_allowips_lawful() {
  local controller_pub node_a_pub
  controller_pub="$(docker exec seraph-controller sh -lc 'cat /tmp/wg_arda_ctrl.pub')"
  node_a_pub="$(docker exec node-a-sacrificial sh -lc 'cat /tmp/wg_arda_node_a.pub')"

  docker exec node-a-sacrificial sh -lc "wg set ${WG_IFACE} peer '${controller_pub}' allowed-ips '${CONTROLLER_ALLOWEDIPS_FULL}'"
  docker exec seraph-controller sh -lc "wg set ${WG_IFACE} peer '${node_a_pub}' allowed-ips '${NODE_A_ALLOWEDIPS_FULL}'"
}

copy_from_controller_or_empty() {
  local src="$1"
  local dest="$2"
  if ! docker cp "seraph-controller:${src}" "${dest}" 2>/dev/null; then
    log "WARN: failed to copy ${src}; writing empty placeholder at ${dest}"
    : >"${dest}"
  fi
}

log "Booting live Arda-Fabric testbed"
docker compose "${COMPOSE_ARGS[@]}" up -d --build

log "Waiting for services to become reachable"
until docker exec node-b-witness sh -lc "curl -fsS ${CONTROLLER_URL}/health >/dev/null"; do sleep 1; done
until docker exec node-b-witness sh -lc "curl -fsS http://10.77.10.10:8080/health >/dev/null"; do sleep 1; done
until docker exec node-b-witness sh -lc "curl -fsS http://10.77.20.10:8080/health >/dev/null"; do sleep 1; done

log "Configuring WireGuard peer state for AllowedIPs mutation evidence"
setup_wireguard_allowips

log "Starting controller<->nodeA packet capture"
docker exec seraph-controller sh -lc "rm -f /tmp/controller_nodeA.pcap /tmp/tcpdump.pid /tmp/tcpdump.log /tmp/controller_nodeA.meta; nohup tcpdump -U -n -i any '(host 10.77.0.11 or host 10.77.0.2)' -w /tmp/controller_nodeA.pcap >/tmp/tcpdump.log 2>&1 & echo \$! >/tmp/tcpdump.pid"

cat >"${OUT_DIR}/00_manifest.json" <<JSON
{
  "label": "live_recovery_rejoin_proof",
  "session_id": "${SESSION_ID}",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "topology": {
    "controller": "10.77.0.2",
    "node_a_sacrificial": "10.77.0.11",
    "node_b_witness": "10.77.0.12",
    "node_c_quorum": "10.77.0.13",
    "protected_fake_vault": "10.77.10.10",
    "remediation_service": "10.77.20.10"
  }
}
JSON

log "Phase 0: baseline lawful state"
{
  echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "controller_health=$(curl -sS ${CONTROLLER_URL}/health)"
  echo "nodeA_to_vault_code=$(http_code_from_node_a http://10.77.10.10:8080/health)"
  echo "nodeA_to_remediation_code=$(http_code_from_node_a http://10.77.20.10:8080/health)"
  echo "nodeA_to_controller_code=$(http_code_from_node_a ${CONTROLLER_URL}/health)"
  echo "nodeA_ping_nodeB=$(cmd_from_node_a 'ping -c 1 -W 1 10.77.0.12')"
} >"${OUT_DIR}/01_baseline_connectivity.txt"

capture_quorum_heartbeat_metric "phase0_baseline_lawful"

capture_or_true "${OUT_DIR}/02_baseline_wg_show.txt" docker exec node-a-sacrificial sh -lc "wg show"
capture_or_true "${OUT_DIR}/03_baseline_nft_ruleset.txt" docker exec node-a-sacrificial sh -lc "nft list ruleset"

log "Phase 1: seed partial compromise"
controller_post_json "/phase/seed-compromise" \
  '{"session_id":"'"${SESSION_ID}"'","node_id":"node-a-sacrificial","agent_class":"persistent_recon","model":"qwen2.5:0.5b"}' \
  >"${OUT_DIR}/04_compromise_seed_event.json"

capture_quorum_heartbeat_metric "phase1_seed_partial_compromise"

log "Phase 2: enforce network isolation via nftables"
docker exec node-a-sacrificial sh -lc "nft delete table inet ${NFT_QUAR_TABLE} 2>/dev/null || true; cat >/tmp/quarantine.nft <<'NFT'
add table inet seraph_quarantine
add chain inet seraph_quarantine node_a_isolation { type filter hook output priority 0; policy drop; }
add rule inet seraph_quarantine node_a_isolation ip daddr 10.77.20.10 tcp dport 8080 accept
add rule inet seraph_quarantine node_a_isolation ip daddr 10.77.0.2 tcp dport 8080 accept
add rule inet seraph_quarantine node_a_isolation ct state established,related accept
NFT
nft -f /tmp/quarantine.nft"

set_wireguard_allowips_isolated

controller_post_json "/phase/isolate" \
  '{"session_id":"'"${SESSION_ID}"'","node_id":"node-a-sacrificial","method":"nftables"}' \
  >"${OUT_DIR}/05_isolation_event.json"

capture_or_true "${OUT_DIR}/05b_isolation_nft_ruleset_ACTIVE.txt" docker exec node-a-sacrificial sh -lc "nft list ruleset"

capture_quorum_heartbeat_metric "phase2_isolation_enforced"

{
  echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "nodeA_to_vault_code=$(http_code_from_node_a http://10.77.10.10:8080/health)"
  echo "nodeA_to_remediation_code=$(http_code_from_node_a http://10.77.20.10:8080/health)"
  echo "nodeA_to_controller_code=$(http_code_from_node_a ${CONTROLLER_URL}/health)"
  echo "nodeA_ping_nodeB=$(cmd_from_node_a 'ping -c 1 -W 1 10.77.0.12')"
  echo "nodeA_ping_nodeC=$(cmd_from_node_a 'ping -c 1 -W 1 10.77.0.13')"
  echo "controller_state=$(controller_get_json ${CONTROLLER_URL}/state)"
} >"${OUT_DIR}/06_post_isolation_connectivity.txt"

capture_or_true "${OUT_DIR}/06b_post_isolation_wg_show.txt" docker exec node-a-sacrificial sh -lc "wg show"

log "Phase 3: reject bad quorum vote"
controller_post_json "/quorum/vote" \
  '{"session_id":"'"${SESSION_ID}"'","node_id":"node-a-sacrificial","vote":"promote-self"}' \
  >"${OUT_DIR}/07_bad_quorum_vote_rejected.json"

capture_quorum_heartbeat_metric "phase3_bad_quorum_vote_rejected"

log "Phase 4: reject bad recovery witness"
controller_post_json "/lorien/witness-recover" \
  '{"session_id":"'"${SESSION_ID}"'","target_node_id":"node-a-sacrificial","witness_node_id":"node-a-sacrificial"}' \
  >"${OUT_DIR}/08_bad_recovery_witness_rejected.json"

capture_quorum_heartbeat_metric "phase4_bad_witness_rejected"

log "Phase 5: signed strict recovery and rejoin"
STATE_BEFORE_RECOVERY="${OUT_DIR}/08b_state_before_recovery.json"
STRICT_PAYLOAD="${OUT_DIR}/08c_strict_recovery_payload.json"
controller_get_json "${CONTROLLER_URL}/state" >"${STATE_BEFORE_RECOVERY}"
export ARDA_RECOVERY_REQUEST_PRIVATE_KEY="${ARDA_RECOVERY_REQUEST_PRIVATE_KEY:-/tmp/metatron-recovery-roots-validation/recovery-request-private.pem}"
export ARDA_RECOVERY_WITNESS_PRIVATE_KEY="${ARDA_RECOVERY_WITNESS_PRIVATE_KEY:-/tmp/metatron-recovery-roots-validation/recovery-witness-private.pem}"
export ARDA_RECOVERY_ATTESTATION_PRIVATE_KEY="${ARDA_RECOVERY_ATTESTATION_PRIVATE_KEY:-/tmp/metatron-recovery-roots-validation/arda-attestation-private.pem}"
export ARDA_RECOVERY_CAPABILITY_PRIVATE_KEY="${ARDA_RECOVERY_CAPABILITY_PRIVATE_KEY:-/tmp/metatron-recovery-roots-validation/beast-capability-private.pem}"
ISOLATION_RECEIPT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["isolation_receipt_digest"])' "${OUT_DIR}/05_isolation_event.json")"
python3 "${ROOT_DIR}/build_strict_recovery_payload.py" "${SESSION_ID}" "node-a-sacrificial" "${ISOLATION_RECEIPT}" "${STATE_BEFORE_RECOVERY}" "${STRICT_PAYLOAD}"
curl -sS -X POST "${CONTROLLER_URL}/lorien/recover-strict" \
  -H "X-Seraph-Auth: ${CONTROLLER_AUTH_TOKEN}" -H "Content-Type: application/json" \
  --data-binary @"${STRICT_PAYLOAD}" >"${OUT_DIR}/09_lawful_recovery_accepted.json"

RECOVERY_ALLOWED="$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1])).get("allowed") is True).lower())' "${OUT_DIR}/09_lawful_recovery_accepted.json")"
if [[ "${RECOVERY_ALLOWED}" != "true" ]]; then
  log "Recovery authorization was denied; refusing nftables/WireGuard rejoin"
  exit 1
fi

docker exec node-a-sacrificial sh -lc "nft delete table inet ${NFT_QUAR_TABLE} || true"
set_wireguard_allowips_lawful

{
  echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "nodeA_to_vault_code=$(http_code_from_node_a http://10.77.10.10:8080/health)"
  echo "nodeA_to_remediation_code=$(http_code_from_node_a http://10.77.20.10:8080/health)"
  echo "nodeA_to_controller_code=$(http_code_from_node_a ${CONTROLLER_URL}/health)"
  echo "nodeA_ping_nodeB=$(cmd_from_node_a 'ping -c 1 -W 1 10.77.0.12')"
  echo "controller_state=$(controller_get_json ${CONTROLLER_URL}/state)"
} >"${OUT_DIR}/10_post_rejoin_connectivity.txt"

capture_quorum_heartbeat_metric "phase5_lawful_rejoin_complete"

capture_or_true "${OUT_DIR}/11_final_wg_show.txt" docker exec node-a-sacrificial sh -lc "wg show"
capture_or_true "${OUT_DIR}/12_final_nft_ruleset.txt" docker exec node-a-sacrificial sh -lc "nft list ruleset"

controller_get_json "${CONTROLLER_URL}/mandos/ledger?limit=200" >"${OUT_DIR}/13_mandos_ledger.json"

docker exec seraph-controller sh -lc "if [ -f /tmp/tcpdump.pid ]; then pid=\$(cat /tmp/tcpdump.pid); kill -2 \"\${pid}\" 2>/dev/null || true; wait \"\${pid}\" 2>/dev/null || true; fi; ls -l /tmp/controller_nodeA.pcap >/tmp/controller_nodeA.meta 2>&1 || true"
copy_from_controller_or_empty "/tmp/controller_nodeA.pcap" "${OUT_DIR}/14_pcap_controller_nodeA.pcap"
copy_from_controller_or_empty "/tmp/tcpdump.log" "${OUT_DIR}/14b_tcpdump_controller_nodeA.log"
copy_from_controller_or_empty "/tmp/controller_nodeA.meta" "${OUT_DIR}/14c_pcap_controller_nodeA_meta.txt"

python3 - "${OUT_DIR}" <<'PY'
import json
import pathlib
import re
import sys
import csv

out_dir = pathlib.Path(sys.argv[1])


def read_json(name):
    return json.loads((out_dir / name).read_text())


def text_value(path, key):
    txt = path.read_text()
    m = re.search(rf"{re.escape(key)}=(.*)", txt)
    return m.group(1).strip() if m else ""

seed = read_json("04_compromise_seed_event.json")
isolation = read_json("05_isolation_event.json")
bad_vote = read_json("07_bad_quorum_vote_rejected.json")
bad_witness = read_json("08_bad_recovery_witness_rejected.json")
lawful = read_json("09_lawful_recovery_accepted.json")
strict_effect = lawful.get("effect", {})
ledger = read_json("13_mandos_ledger.json")
metrics_jsonl = out_dir / ".quorum_heartbeat_metrics.jsonl"
post_iso = out_dir / "06_post_isolation_connectivity.txt"
post_rejoin = out_dir / "10_post_rejoin_connectivity.txt"
wg_isolated = (out_dir / "06b_post_isolation_wg_show.txt").read_text()
wg_final = (out_dir / "11_final_wg_show.txt").read_text()
pcap_path = out_dir / "14_pcap_controller_nodeA.pcap"

metrics_entries = []
if metrics_jsonl.exists():
  metrics_entries = [json.loads(line) for line in metrics_jsonl.read_text().splitlines() if line.strip()]

metrics_doc = {
  "metric_family": "quorum_and_metatron_heartbeat",
  "sample_count": len(metrics_entries),
  "samples": metrics_entries,
}
(out_dir / "13b_quorum_metatron_heartbeat_metrics.json").write_text(json.dumps(metrics_doc, indent=2) + "\n")

csv_path = out_dir / "13c_quorum_metatron_heartbeat_metrics.csv"
csv_headers = [
  "captured_at",
  "phase",
  "metatron_heartbeat_ok",
  "metatron_heartbeat_ts",
  "quorum_epoch",
  "quorum_state",
  "quorum_votes",
  "compromised_nodes_count",
  "isolated_nodes_count",
  "ledger_entries",
]
with csv_path.open("w", newline="") as f:
  writer = csv.DictWriter(f, fieldnames=csv_headers)
  writer.writeheader()
  for sample in metrics_entries:
    writer.writerow(
      {
        "captured_at": sample.get("captured_at"),
        "phase": sample.get("phase"),
        "metatron_heartbeat_ok": sample.get("metatron_heartbeat_ok"),
        "metatron_heartbeat_ts": sample.get("metatron_heartbeat_ts"),
        "quorum_epoch": sample.get("quorum_epoch"),
        "quorum_state": sample.get("quorum_state"),
        "quorum_votes": sample.get("quorum_votes"),
        "compromised_nodes_count": len(sample.get("compromised_nodes", []) or []),
        "isolated_nodes_count": len(sample.get("isolated_nodes", []) or []),
        "ledger_entries": sample.get("ledger_entries"),
      }
    )

heartbeat_ok = len(metrics_entries) >= 4 and all(sample.get("metatron_heartbeat_ok") for sample in metrics_entries)
quorum_states = [sample.get("quorum_state") for sample in metrics_entries]
quorum_metrics_show_strain_then_lawful = ("strained" in quorum_states) and (len(quorum_states) > 0 and quorum_states[-1] == "lawful")

vault_iso = text_value(post_iso, "nodeA_to_vault_code")
rem_iso = text_value(post_iso, "nodeA_to_remediation_code")
vault_rejoin = text_value(post_rejoin, "nodeA_to_vault_code")

wg_iso_restricted = (
  "10.77.0.2/32" in wg_isolated
  and "10.77.20.10/32" in wg_isolated
  and "10.77.10.10/32" not in wg_isolated
  and "10.77.0.12/32" not in wg_isolated
  and "10.77.0.13/32" not in wg_isolated
)
wg_rejoin_restored = (
  "10.77.0.2/32" in wg_final
  and "10.77.10.10/32" in wg_final
  and "10.77.20.10/32" in wg_final
  and "10.77.0.12/32" in wg_final
  and "10.77.0.13/32" in wg_final
)

# PCAP files have a 24-byte global header; larger size means at least one packet record exists.
pcap_has_payload_packets = pcap_path.exists() and pcap_path.stat().st_size > 24

assertions = {
    "node_is_isolated": bool(isolation.get("isolated")),
    "protected_asset_blocked_during_isolation": vault_iso != "200",
    "remediation_endpoint_allowed_during_isolation": rem_iso == "200",
    "bad_quorum_vote_rejected": bad_vote.get("vote_accepted") is False and bad_vote.get("node_compromised") is True,
    "bad_recovery_witness_rejected": bad_witness.get("recovered") is False and bad_witness.get("witness_compromised") is True,
    "lawful_witness_accepted": lawful.get("recovered") is True,
    "node_re_admitted": lawful.get("allowed") is True and strict_effect.get("rejoined") is True,
    "quorum_returns_lawful": bool(metrics_entries) and metrics_entries[-1].get("quorum_state") == "lawful",
    "recovery_recorded_in_ledger": any(
        e.get("aatr_id") == "LORIEN-STRICT" and e.get("surface") == "/lorien/recover-strict" and e.get("decision") == "recover"
        for e in ledger.get("entries", [])
    ),
    "wireguard_allowedips_restricted_during_isolation": wg_iso_restricted,
    "wireguard_allowedips_restored_after_recovery": wg_rejoin_restored,
    "network_routes_restored_after_recovery": vault_rejoin == "200",
    "metatron_heartbeat_continuous": heartbeat_ok,
    "quorum_metrics_show_strain_then_lawful": quorum_metrics_show_strain_then_lawful,
    "pcap_has_payload_packets": pcap_has_payload_packets,
}

summary_lines = [
    "# Live Recovery Rejoin Summary",
    "",
    "## Assertion Results",
]
for key, value in assertions.items():
    summary_lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")

summary_lines.extend([
    "",
    "## Phase Highlights",
    f"- Phase 1 seed mode: {seed.get('mode')}",
    f"- Phase 2 isolation reason: {isolation.get('reason')}",
    f"- Phase 3 vote accepted: {bad_vote.get('vote_accepted')}",
    f"- Phase 4 recovered: {bad_witness.get('recovered')}",
    f"- Phase 5 quorum_state: {lawful.get('quorum_state')}",
    "",
    "## Connectivity Checks",
    f"- During isolation, vault HTTP code: {vault_iso}",
    f"- During isolation, remediation HTTP code: {rem_iso}",
    f"- After rejoin, vault HTTP code: {vault_rejoin}",
    "",
    "## Quorum and Metatron Heartbeat Metrics",
    f"- Metric samples collected: {len(metrics_entries)}",
    f"- Metatron heartbeat continuous: {'PASS' if heartbeat_ok else 'FAIL'}",
    f"- Quorum strain->lawful transition observed: {'PASS' if quorum_metrics_show_strain_then_lawful else 'FAIL'}",
    "",
    "## Packet Capture",
    f"- PCAP bytes: {pcap_path.stat().st_size if pcap_path.exists() else 0}",
    f"- Payload packets present: {'PASS' if pcap_has_payload_packets else 'FAIL'}",
])

(out_dir / "15_summary.md").write_text("\n".join(summary_lines) + "\n")
(out_dir / "assertions.json").write_text(json.dumps(assertions, indent=2) + "\n")

manifest_path = out_dir / "00_manifest.json"
manifest = json.loads(manifest_path.read_text())
manifest["assertions"] = assertions
manifest["metric_artifacts"] = [
  "13b_quorum_metatron_heartbeat_metrics.json",
  "13c_quorum_metatron_heartbeat_metrics.csv",
]
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

if metrics_jsonl.exists():
  metrics_jsonl.unlink()
PY

log "Evidence bundle created at ${OUT_DIR}"
log "Files: 00_manifest.json ... 15_summary.md"
