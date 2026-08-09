{
  "service": {
    "name": "cas-shield-sidecar",
    "listen_host": "0.0.0.0",
    "listen_port": 8080,
    "log_dir": "./logs",
    "audit_file": "./logs/audit.jsonl",
    "telemetry_file": "./logs/telemetry.jsonl",
    "echo_mode": true
  },
  "upstream": {
    "cas_base_url_env": "CAS_BASE_URL",
    "cas_base_url": "http://demo-cas:9090",
    "health_path": "/health",
    "connect_timeout_sec": 3,
    "read_timeout_sec": 15,
    "check_interval_sec": 5,
    "circuit_breaker_ms": 15000
  },
  "routing": {
    "trap_paths_prefix": [
      "/.env",
      "/wp-admin",
      "/phpmyadmin",
      "/admin",
      "/actuator",
      "/swagger",
      "/graphql"
    ]
  },
  "rate_limit": {
    "per_ip_rps": 3,
    "per_ip_burst": 10,
    "per_ip_path_rps": 2,
    "per_ip_path_burst": 6
  },
  "friction": {
    "enabled": true,
    "base_delay_ms": 350,
    "max_delay_ms": 3000,
    "challenge_on_score_at_least": 60
  },
  "trap_sink": {
    "enabled": true,
    "min_score": 85,
    "tarpit_delay_ms": 2000
  },
  "pebbles": {
    "enabled": true,
    "echo_header": "X-Pebble-Trace",
    "echo_on_routes": [
      "FRICTION",
      "TRAP_SINK"
    ],
    "fingerprint_fields": [
      "user-agent",
      "accept",
      "accept-language",
      "accept-encoding"
    ],
    "campaign_window_minutes": 120,
    "campaign_salt_env": "PEBBLES_SALT",
    "stonewall": {
      "enable_auto_ban": true,
      "ban_seconds_first": 1800,
      "ban_seconds_repeat": 21600,
      "repeat_threshold": 20,
      "trap_hits_to_blocklist": 50
    },
    "canary_endpoints": {
      "enabled": true,
      "paths": [
        "/pebble.gif",
        "/.well-known/pebble"
      ]
    }
  },
  "mystique": {
    "enabled": true,
    "max_friction_multiplier": 2.5,
    "max_tarpit_multiplier": 2.0,
    "min_sink_score_floor": 60,
    "adapt_every_n_events": 25,
    "campaign_promote_threshold": 30
  },
  "scoring": {
    "weights": {
      "bad_user_agent": 15,
      "missing_headers": 10,
      "rate_pressure": 25,
      "suspicious_path": 40,
      "known_bad_ip": 50
    },
    "allowlist_ips": [],
    "blocklist_ips": []
  }
}