# Seraph/Arda Confidence Scorecard

- Generated At: 2026-05-09T14:02:05.816453+00:00
- Composite Score: 9.9 / 10
- Grade: A+

## Dimension Breakdown

| Dimension | Score (0-1) | Weight | Weighted Contribution |
|---|---:|---:|---:|
| Atomic Breadth Coverage | 1.0000 | 0.24 | 2.400 |
| Kernel Prevention Consistency | 1.0000 | 0.28 | 2.800 |
| High-Impact Hostile Containment | 1.0000 | 0.24 | 2.400 |
| Adaptive Escalation Behavior | 1.0000 | 0.14 | 1.400 |
| Dependency Hygiene | 0.9000 | 0.10 | 0.900 |

## Rationales

- Atomic Breadth Coverage: 684 unique techniques observed over denominator 412.
- Kernel Prevention Consistency: denied=true for 684 / 684 latest technique records.
- High-Impact Hostile Containment: hostile_denied 21 / hostile_total 21 in latest Dagor report.
- Adaptive Escalation Behavior: Latest strictness state: lockdown.
- Dependency Hygiene: Dependency hygiene not fully measured in this run.

## Core Metrics

```json
{
  "atomic_denominator": 412,
  "prevention": {
    "unique_techniques": 684,
    "verdicts": {
      "kernel_prevented": 684
    },
    "exec_denied_true": 684,
    "exec_denied_false": 0,
    "prevention_consistency": 1.0,
    "top_tactics": {
      "TA0005": 135,
      "TA0003": 94,
      "TA0040": 79,
      "TA0006": 55,
      "TA0042": 49,
      "TA0011": 44,
      "TA0043": 44,
      "TA0007": 35,
      "TA0002": 35,
      "TA0009": 31,
      "TA0004": 31,
      "TA0010": 19
    }
  },
  "dagor": {
    "available": true,
    "status": "pass",
    "hostile_total": 21,
    "hostile_denied": 21,
    "hostile_approved": 0,
    "hostile_queued": 0,
    "pass_rate_pct": 100.0,
    "global_strictness": "lockdown",
    "live_harness_used": true
  },
  "dependency_hygiene": {
    "available": false,
    "oqs_mismatch_detected": null,
    "notes": "No log supplied for dependency-hygiene scan."
  }
}
```
