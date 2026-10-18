# Shape exposure: development results (2024–2025)

*Fit 2026-10-18 on the development seasons only, with the specification in [the plan](2026-shape-exposure-plan.md). Committed before the 2026 confirmation fit, as the plan requires. Code: `baseball/edge/shape_exposure.py`.*

Two technical notes, neither a change to the plan:
- Fixed-effect groups with a single row (batter × season × family, or pitcher × pitch type × season) are dropped before fitting. They carry no within-group information, so the estimates don't change; the row counts below are after the drop.
- H3 has fewer rows than H1 because the lead window is empty for the last days of each season, where the lead share is undefined.

| Test | Outcome | Term | Coef | SE | 95% interval | p | Rows | Batters |
|---|---|---|---|---|---|---|---|---|
| H1 | whiff | s_S30_h1.0 | -0.695 | 0.090 | -0.871 to -0.519 | 0.0000 | 479,498 | 698 |
| H1 | whiff | logN30 | -0.323 | 0.220 | -0.754 to +0.108 | 0.1424 | 479,498 | 698 |
| H2_narrow | whiff | s_S30_h0.5 | -0.226 | 0.069 | -0.361 to -0.090 | 0.0011 | 479,498 | 698 |
| H2_narrow | whiff | logN30 | -0.333 | 0.220 | -0.764 to +0.098 | 0.1304 | 479,498 | 698 |
| H2_wide | whiff | s_S30_h2.0 | -1.203 | 0.106 | -1.411 to -0.995 | 0.0000 | 479,498 | 698 |
| H2_wide | whiff | logN30 | -0.305 | 0.220 | -0.736 to +0.125 | 0.1643 | 479,498 | 698 |
| H3 | whiff | s_S30_h1.0 | -0.598 | 0.096 | -0.786 to -0.410 | 0.0000 | 470,718 | 689 |
| H3 | whiff | s_Slead30_h1.0 | -0.152 | 0.084 | -0.316 to +0.012 | 0.0687 | 470,718 | 689 |
| H3 | whiff | logN30 | -0.330 | 0.221 | -0.763 to +0.103 | 0.1350 | 470,718 | 689 |
| H3 | whiff | logNlead30 | +0.122 | 0.132 | -0.137 to +0.381 | 0.3558 | 470,718 | 689 |
| H4 | whiff | s_S7_h1.0 | -0.300 | 0.078 | -0.454 to -0.147 | 0.0001 | 400,287 | 634 |
| H4 | whiff | s_S8_30_h1.0 | -0.313 | 0.103 | -0.514 to -0.112 | 0.0023 | 400,287 | 634 |
| H4 | whiff | s_S31_90_h1.0 | -0.256 | 0.106 | -0.464 to -0.049 | 0.0153 | 400,287 | 634 |
| H4 | whiff | logN7 | -0.587 | 0.129 | -0.839 to -0.335 | 0.0000 | 400,287 | 634 |
| H4 | whiff | logN8_30 | +0.138 | 0.185 | -0.224 to +0.501 | 0.4546 | 400,287 | 634 |
| H4 | whiff | logN31_90 | +0.077 | 0.144 | -0.204 to +0.359 | 0.5907 | 400,287 | 634 |
| H5 | rv | s_S30_h1.0 | -0.082 | 0.032 | -0.145 to -0.020 | 0.0099 | 1,013,197 | 703 |
| H5 | rv | logN30 | +0.157 | 0.078 | +0.004 to +0.310 | 0.0445 | 1,013,197 | 703 |

Units: whiff points per swing (whiff) or runs per 100 pitches from the pitcher's side (rv), per 1 SD of the share; log-count terms per unit of log count.
