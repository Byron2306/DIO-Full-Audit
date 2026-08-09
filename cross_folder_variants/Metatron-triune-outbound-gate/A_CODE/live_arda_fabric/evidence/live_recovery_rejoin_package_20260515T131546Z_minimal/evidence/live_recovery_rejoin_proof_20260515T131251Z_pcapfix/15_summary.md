# Live Recovery Rejoin Summary

## Assertion Results
- node_is_isolated: PASS
- protected_asset_blocked_during_isolation: PASS
- remediation_endpoint_allowed_during_isolation: PASS
- bad_quorum_vote_rejected: PASS
- bad_recovery_witness_rejected: PASS
- lawful_witness_accepted: PASS
- node_re_admitted: PASS
- quorum_returns_lawful: PASS
- recovery_recorded_in_ledger: PASS
- wireguard_allowedips_restricted_during_isolation: PASS
- wireguard_allowedips_restored_after_recovery: PASS
- network_routes_restored_after_recovery: PASS
- metatron_heartbeat_continuous: PASS
- quorum_metrics_show_strain_then_lawful: PASS
- pcap_has_payload_packets: PASS

## Phase Highlights
- Phase 1 seed mode: partial_compromise
- Phase 2 isolation reason: node isolation bypass refused; quarantine is enforced at the fabric layer
- Phase 3 vote accepted: False
- Phase 4 recovered: False
- Phase 5 quorum_state: lawful

## Connectivity Checks
- During isolation, vault HTTP code: curl: (28) Connection timed out after 3001 milliseconds
- During isolation, remediation HTTP code: 200
- After rejoin, vault HTTP code: 200

## Quorum and Metatron Heartbeat Metrics
- Metric samples collected: 6
- Metatron heartbeat continuous: PASS
- Quorum strain->lawful transition observed: PASS

## Packet Capture
- PCAP bytes: 24909
- Payload packets present: PASS
