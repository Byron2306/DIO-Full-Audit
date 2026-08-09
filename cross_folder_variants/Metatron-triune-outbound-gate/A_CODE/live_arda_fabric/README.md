# Live Arda-Fabric Recovery/Rejoin Testbed

This directory provides a tiny live testbed that turns isolation/rejoin from a JSON-only claim into a measurable network event.

Topology (docker bridge network with static IPs):

- 10.77.0.2: seraph-controller (quorum coordinator, Mandos ledger, recovery controller)
- 10.77.0.11: node-a-sacrificial
- 10.77.0.12: node-b-witness
- 10.77.0.13: node-c-quorum
- 10.77.10.10: protected-fake-vault
- 10.77.20.10: remediation-service

## What this proves

The scripted run enforces real network quarantine on Node A using both:

- `nftables` output policy
- WireGuard `AllowedIPs` mutation during isolate/rejoin

Before isolation:

- Node A reaches fake vault and remediation.

After isolation:

- Node A cannot reach fake vault or peers.
- Node A can reach only remediation-service and controller.

After lawful recovery:

- Quarantine rules are removed.
- WireGuard `AllowedIPs` are restored to lawful peer set.
- Node A reaches fake vault again.

## Run

From this directory:

```bash
./run_live_recovery_rejoin.sh
```

Optional output directory:

```bash
./run_live_recovery_rejoin.sh /tmp/live_recovery_rejoin_proof
```

Horror-class live scenarios (AATR-039..044 + Omega):

```bash
./run_live_horror_class.sh aatr_039_root_shadow_executor /tmp/aatr_039_live
./run_live_horror_class.sh aatr_040_fragmented_persistence_coalescer /tmp/aatr_040_live
./run_live_horror_class.sh aatr_041_echelon_fusion_entity /tmp/aatr_041_live
./run_live_horror_class.sh aatr_042_role_assimilation_jailbreaker /tmp/aatr_042_live
./run_live_horror_class.sh aatr_043_shodanization_drift /tmp/aatr_043_live
./run_live_horror_class.sh aatr_044_kawaiigpt_coercion_engine /tmp/aatr_044_live
./run_live_horror_class.sh live_omega_broken_choir_gauntlet_001 /tmp/aatr_omega_live

# 15-minute chaos mutation campaign (random 1-3 layer ablations + live noise)
HORROR_CHAOS_MODE=1 HORROR_DURATION_SECONDS=900 \
  ./run_live_horror_class.sh live_omega_broken_choir_gauntlet_001 /tmp/aatr_omega_chaos_15m
```

The script creates:

- `00_manifest.json`
- `01_baseline_connectivity.txt`
- `02_baseline_wg_show.txt`
- `03_baseline_nft_ruleset.txt`
- `04_compromise_seed_event.json`
- `05_isolation_event.json`
- `05b_isolation_nft_ruleset_ACTIVE.txt`
- `06_post_isolation_connectivity.txt`
- `06b_post_isolation_wg_show.txt`
- `07_bad_quorum_vote_rejected.json`
- `08_bad_recovery_witness_rejected.json`
- `09_lawful_recovery_accepted.json`
- `10_post_rejoin_connectivity.txt`
- `11_final_wg_show.txt`
- `12_final_nft_ruleset.txt`
- `13_mandos_ledger.json`
- `13b_quorum_metatron_heartbeat_metrics.json`
- `13c_quorum_metatron_heartbeat_metrics.csv`
- `14_pcap_controller_nodeA.pcap`
- `14b_tcpdump_controller_nodeA.log`
- `14c_pcap_controller_nodeA_meta.txt`
- `15_summary.md`

Horror-class runs also emit:

- `16_horror_class_trace.json`
- `17_control_state_effective.json`
- `18_expected_vs_observed_failure_modes.json`

Chaos-mode runs also emit:

- `19_mutation_campaign.json`
- `20_noise_traffic_summary.json`
- `21_random_ablation_timeline.json`

And one extra machine-checkable file:

- `assertions.json`

## Notes

- This is a fake-lab substrate only. No production secrets. No production services.
- The runner now creates a minimal WireGuard peer relationship between controller and Node A and mutates `AllowedIPs` for isolation and lawful recovery evidence.
