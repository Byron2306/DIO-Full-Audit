# Provider Diagnostic: xai

- Task: `tsk_d5e97e053369`
- Category: `auth_or_credentials`
- Confidence: `0.82`
- Cloud escalation needed: `False`

## Checks

- `provider_policy`: **warning** - No provider policy found for xai
- `credentials`: **passed** - Required environment credential is present
- `runtime_circuit`: **passed** - Runtime circuit is closed
- `recent_attempts`: **warning** - No recent attempts found
- `log_scan`: **warning** - No provider-specific failures found in local log tails

## Recommendations

- Set or verify one of: XAI_API_KEY.
- Avoid retrying provider calls until credential state changes.
- Run the diagnostic again after updating the environment.
