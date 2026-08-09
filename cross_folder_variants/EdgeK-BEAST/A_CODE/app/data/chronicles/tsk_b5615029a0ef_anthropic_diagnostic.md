# Provider Diagnostic: anthropic

- Task: `tsk_b5615029a0ef`
- Category: `auth_or_credentials`
- Confidence: `0.82`
- Cloud escalation needed: `False`

## Checks

- `provider_policy`: **passed** - Provider policy is enabled
- `credentials`: **failed** - No expected credential environment variable is set
- `runtime_circuit`: **passed** - Runtime circuit is closed
- `recent_attempts`: **passed** - 8 recent attempts, 0 non-successful
- `log_scan`: **warning** - No provider-specific failures found in local log tails

## Recommendations

- Set or verify one of: ANTHROPIC_API_KEY.
- Avoid retrying provider calls until credential state changes.
- Run the diagnostic again after updating the environment.
