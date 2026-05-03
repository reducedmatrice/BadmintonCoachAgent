# Structured Run Log Summary

- Total requests: 3
- Error rate: 33.33%
- Fallback rate: 0.00%

## Key Findings

- Slowest route by P95 latency: `badminton-coach` at 2855.00 ms.
- Most expensive route by avg total tokens: `badminton-coach` at 130.00.
- No fallback observed in the current sample.
- Token cost is currently dominated by `final generation` at 36.67 avg tokens.

## Overall

- avg latency: 1300.00 ms
- p50 latency: 800.00 ms
- p95 latency: 2780.00 ms
- avg total tokens: 106.67
- fallback rate: 0.00%
- avg router tokens: 0.00
- avg memory-context tokens: 0.00
- avg generation tokens: 36.67

## By Route

- badminton-coach: requests=2, avg_latency=1550.00 ms, p50=1550.00 ms, p95=2855.00 ms, avg_total_tokens=130.00, fallback_rate=0.00%, error_rate=50.00%
- recovery-coach: requests=1, avg_latency=800.00 ms, p50=800.00 ms, p95=800.00 ms, avg_total_tokens=60.00, fallback_rate=0.00%, error_rate=0.00%
