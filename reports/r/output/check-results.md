# R vs Python check: hitter whiff per swing, 2026 regular season

Run 2026-10-28. Data: 340,712 swings, 661 batters, 2429 games (Baseball Savant, pulled with reports/r/pull_swings.R).

**Result: 79 of 79 checks pass.**

- Python (repo code, seed 2026, 200 splits): M = 54.7 swings (95%: 48.0-62.4), tau = 0.0620
- R (independent splits, seed 2026, 200 splits): M = 54.5 swings (95%: 48.6-61.2), tau = 0.0621
- Atlas (2024-26 pooled, shipped): M = 55.4 (49.0-62.7). This season alone is inside that interval.

Tolerances: A, B and C are exact (rounding only). D compares two independent sets of random splits:
M within 1.5% (its interval ends within 5%), tau within 1%, r(n) within 0.0075, regressed estimates within 0.1 point, interval ends within 0.2 points.
These bars are about 1.5x how far Python moves from itself when only the random seed changes.

| Check | Quantity | Python | R | R - Python | Tolerance | Pass |
|---|---|---|---|---|---|---|
| A same splits | r(1) | 0.009891 | 0.009891 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(2) | 0.038143 | 0.038143 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(3) | 0.059911 | 0.059911 | 5.55e-16 | 1.0e-10 | yes |
| A same splits | r(4) | 0.074994 | 0.074994 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(6) | 0.108292 | 0.108292 | 6.97e-15 | 1.0e-10 | yes |
| A same splits | r(8) | 0.137688 | 0.137688 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(11) | 0.175313 | 0.175313 | 6.11e-16 | 1.0e-10 | yes |
| A same splits | r(16) | 0.239080 | 0.239080 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(23) | 0.304419 | 0.304419 | -4.77e-15 | 1.0e-10 | yes |
| A same splits | r(32) | 0.374668 | 0.374668 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(45) | 0.455538 | 0.455538 | 6.83e-15 | 1.0e-10 | yes |
| A same splits | r(64) | 0.533854 | 0.533854 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(90) | 0.609163 | 0.609163 | 6.66e-15 | 1.0e-10 | yes |
| A same splits | r(128) | 0.691481 | 0.691481 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(181) | 0.760867 | 0.760867 | 1.22e-15 | 1.0e-10 | yes |
| A same splits | r(256) | 0.825463 | 0.825463 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | r(362) | 0.867437 | 0.867437 | -4.22e-15 | 1.0e-10 | yes |
| A same splits | r(512) | 0.888997 | 0.888997 | 0.00e+00 | 1.0e-10 | yes |
| A same splits | hitter-halves counted (all n) | 9033.8 | 9033.8 | 0.00e+00 | 1.0e-09 | yes |
| B same points | M | 54.732 | 54.732 | 4.83e-07 | 5.5e-05 | yes |
| C same constants | estimate, 40% in 50 | 0.321683 | 0.321683 | -2.78e-16 | 1.0e-09 | yes |
| C same constants | estimate, 15% in 50 | 0.203088 | 0.203088 | 4.16e-16 | 1.0e-09 | yes |
| C same constants | estimate, 30% in 100 | 0.282531 | 0.282531 | 5.55e-17 | 1.0e-09 | yes |
| C same constants | estimate, 35% in 200 | 0.328525 | 0.328525 | -3.33e-16 | 1.0e-09 | yes |
| C same constants | estimate, 20% in 400 | 0.206204 | 0.206204 | 5.55e-17 | 1.0e-09 | yes |
| C same constants | estimate, 25% in 10 | 0.250847 | 0.250847 | 3.89e-16 | 1.0e-09 | yes |
| C same constants | lo, 40% in 50 | 0.233876 | 0.233876 | -5.00e-16 | 1.0e-09 | yes |
| C same constants | lo, 15% in 50 | 0.115280 | 0.115280 | 2.08e-16 | 1.0e-09 | yes |
| C same constants | lo, 30% in 100 | 0.210217 | 0.210217 | 4.16e-16 | 1.0e-09 | yes |
| C same constants | lo, 35% in 200 | 0.272117 | 0.272117 | 2.22e-16 | 1.0e-09 | yes |
| C same constants | lo, 20% in 400 | 0.163961 | 0.163961 | 1.94e-16 | 1.0e-09 | yes |
| C same constants | lo, 25% in 10 | 0.139376 | 0.139376 | -1.67e-16 | 1.0e-09 | yes |
| C same constants | hi, 40% in 50 | 0.409490 | 0.409490 | -5.55e-17 | 1.0e-09 | yes |
| C same constants | hi, 15% in 50 | 0.290895 | 0.290895 | -3.89e-16 | 1.0e-09 | yes |
| C same constants | hi, 30% in 100 | 0.354846 | 0.354846 | -2.78e-16 | 1.0e-09 | yes |
| C same constants | hi, 35% in 200 | 0.384933 | 0.384933 | 1.11e-16 | 1.0e-09 | yes |
| C same constants | hi, 20% in 400 | 0.248447 | 0.248447 | -8.33e-17 | 1.0e-09 | yes |
| C same constants | hi, 25% in 10 | 0.362318 | 0.362318 | -5.55e-17 | 1.0e-09 | yes |
| C same constants | sd, 40% in 50 | 0.044800 | 0.044800 | -3.47e-17 | 1.0e-09 | yes |
| C same constants | sd, 15% in 50 | 0.044800 | 0.044800 | -3.47e-17 | 1.0e-09 | yes |
| C same constants | sd, 30% in 100 | 0.036896 | 0.036896 | 6.94e-18 | 1.0e-09 | yes |
| C same constants | sd, 35% in 200 | 0.028780 | 0.028780 | -4.51e-17 | 1.0e-09 | yes |
| C same constants | sd, 20% in 400 | 0.021553 | 0.021553 | 1.73e-17 | 1.0e-09 | yes |
| C same constants | sd, 25% in 10 | 0.056874 | 0.056874 | 6.94e-18 | 1.0e-09 | yes |
| C same constants | weight, 40% in 50 | 0.474381 | 0.474381 | 3.89e-16 | 1.0e-09 | yes |
| C same constants | weight, 15% in 50 | 0.474381 | 0.474381 | 3.89e-16 | 1.0e-09 | yes |
| C same constants | weight, 30% in 100 | 0.643499 | 0.643499 | -3.33e-16 | 1.0e-09 | yes |
| C same constants | weight, 35% in 200 | 0.783084 | 0.783084 | -2.22e-16 | 1.0e-09 | yes |
| C same constants | weight, 20% in 400 | 0.878348 | 0.878348 | 2.22e-16 | 1.0e-09 | yes |
| C same constants | weight, 25% in 10 | 0.152904 | 0.152904 | 8.33e-17 | 1.0e-09 | yes |
| D independent | swings in the data | 340712.0 | 340712.0 | 0.00e+00 | 0.0e+00 | yes |
| D independent | league whiff rate | 0.250696 | 0.250696 | -1.11e-16 | 1.0e-12 | yes |
| D independent | M (swings) | 54.732 | 54.519 | -2.14e-01 | 8.2e-01 | yes |
| D independent | M, 95% low | 48.018 | 48.577 | 5.58e-01 | 2.4e+00 | yes |
| D independent | M, 95% high | 62.385 | 61.188 | -1.20e+00 | 3.1e+00 | yes |
| D independent | tau (talent SD) | 0.061960 | 0.062076 | 1.16e-04 | 6.2e-04 | yes |
| D independent | r(16) | 0.239420 | 0.236200 | -3.22e-03 | 7.5e-03 | yes |
| D independent | r(32) | 0.370132 | 0.371171 | 1.04e-03 | 7.5e-03 | yes |
| D independent | r(64) | 0.528353 | 0.531778 | 3.42e-03 | 7.5e-03 | yes |
| D independent | r(128) | 0.694529 | 0.696877 | 2.35e-03 | 7.5e-03 | yes |
| D independent | r(256) | 0.826503 | 0.826465 | -3.83e-05 | 7.5e-03 | yes |
| D independent | estimate, 40% in 50 | 0.321975 | 0.322120 | 1.46e-04 | 1.0e-03 | yes |
| D independent | estimate, 15% in 50 | 0.202623 | 0.202524 | -9.84e-05 | 1.0e-03 | yes |
| D independent | estimate, 30% in 100 | 0.282560 | 0.282604 | 4.41e-05 | 1.0e-03 | yes |
| D independent | estimate, 35% in 200 | 0.328663 | 0.328729 | 6.55e-05 | 1.0e-03 | yes |
| D independent | estimate, 20% in 400 | 0.206102 | 0.206081 | -2.10e-05 | 1.0e-03 | yes |
| D independent | estimate, 25% in 10 | 0.250588 | 0.250588 | -3.56e-07 | 1.0e-03 | yes |
| D independent | lo, 40% in 50 | 0.234186 | 0.234249 | 6.32e-05 | 2.0e-03 | yes |
| D independent | lo, 15% in 50 | 0.114834 | 0.114653 | -1.81e-04 | 2.0e-03 | yes |
| D independent | lo, 30% in 100 | 0.210335 | 0.210335 | -7.02e-09 | 2.0e-03 | yes |
| D independent | lo, 35% in 200 | 0.272372 | 0.272419 | 4.64e-05 | 2.0e-03 | yes |
| D independent | lo, 20% in 400 | 0.163971 | 0.163943 | -2.75e-05 | 2.0e-03 | yes |
| D independent | lo, 25% in 10 | 0.138923 | 0.138746 | -1.76e-04 | 2.0e-03 | yes |
| D independent | hi, 40% in 50 | 0.409763 | 0.409992 | 2.28e-04 | 2.0e-03 | yes |
| D independent | hi, 15% in 50 | 0.290412 | 0.290396 | -1.57e-05 | 2.0e-03 | yes |
| D independent | hi, 30% in 100 | 0.354785 | 0.354873 | 8.82e-05 | 2.0e-03 | yes |
| D independent | hi, 35% in 200 | 0.384954 | 0.385039 | 8.46e-05 | 2.0e-03 | yes |
| D independent | hi, 20% in 400 | 0.248233 | 0.248218 | -1.45e-05 | 2.0e-03 | yes |
| D independent | hi, 25% in 10 | 0.362254 | 0.362429 | 1.75e-04 | 2.0e-03 | yes |
