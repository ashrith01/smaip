# Week 7 episode rescore

Model `Qwen/Qwen2.5-3B-Instruct`; backend `hf`; device `cuda`; subset `full`.

Integration episodes reuse the probe corpus. No thresholds or weights were changed. These are not unseen-attack generalization results.

Model load excluded; text caches cleared per ablation. Repeated pages within a row may hit cache. Trace logging does not compute new trained scores.

The original training report and GPU archive are preserved separately. This command does not retrain either probe.

## week5 episodes

| ablation | utility | asr | fpr | cost | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `no-defense` | 1.00 | 1.00 | 0.00 | 68.00 | 60.275 |
| `keyword` | 1.00 | 0.10 | 0.00 | 74.80 | 54.022 |
| `LP-only` | 1.00 | 0.00 | 0.00 | 85.00 | 1643.504 |
| `probe-only` | 1.00 | 0.00 | 0.00 | 102.00 | 1340.875 |
| `gateway-only` | 1.00 | 0.00 | 0.00 | 71.40 | 51.050 |
| `full-stack` | 1.00 | 0.00 | 0.00 | 129.20 | 1332.589 |

## week6 episodes

| ablation | utility | asr | fpr | cost | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `no-defense` | 1.00 | 1.00 | 0.00 | 73.00 | 55.481 |
| `keyword` | 1.00 | 0.25 | 0.00 | 80.30 | 60.653 |
| `LP-only` | 0.88 | 0.00 | 0.12 | 91.25 | 1532.562 |
| `probe-only` | 1.00 | 0.00 | 0.00 | 109.50 | 1533.655 |
| `gateway-only` | 1.00 | 0.00 | 0.00 | 76.65 | 56.378 |
| `full-stack` | 0.88 | 0.00 | 0.12 | 138.70 | 1528.636 |
