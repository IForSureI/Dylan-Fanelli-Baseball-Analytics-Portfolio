# Shape exposure: 2026 confirmation results

*Fit 2026-10-18, once, with the frozen specification in [the plan](2026-shape-exposure-plan.md), after [the development results](2026-shape-exposure-dev-results.md) were committed. Recorded here before any interpretation.*

| Test | Outcome | Term | Coef | SE | 95% interval | p | Rows | Batters |
|---|---|---|---|---|---|---|---|---|
| H1 | whiff | s_S30_h1.0 | -0.737 | 0.115 | -0.962 to -0.512 | 0.0000 | 241,285 | 585 |
| H1 | whiff | logN30 | +0.045 | 0.320 | -0.583 to +0.672 | 0.8893 | 241,285 | 585 |
| H2_narrow | whiff | s_S30_h0.5 | -0.261 | 0.089 | -0.436 to -0.086 | 0.0034 | 241,285 | 585 |
| H2_narrow | whiff | logN30 | +0.029 | 0.321 | -0.600 to +0.658 | 0.9276 | 241,285 | 585 |
| H2_wide | whiff | s_S30_h2.0 | -1.239 | 0.139 | -1.511 to -0.967 | 0.0000 | 241,285 | 585 |
| H2_wide | whiff | logN30 | +0.061 | 0.320 | -0.565 to +0.688 | 0.8477 | 241,285 | 585 |
| H3 | whiff | s_S30_h1.0 | -0.635 | 0.122 | -0.874 to -0.396 | 0.0000 | 236,749 | 571 |
| H3 | whiff | s_Slead30_h1.0 | -0.363 | 0.113 | -0.585 to -0.141 | 0.0013 | 236,749 | 571 |
| H3 | whiff | logN30 | +0.066 | 0.325 | -0.572 to +0.703 | 0.8403 | 236,749 | 571 |
| H3 | whiff | logNlead30 | -0.031 | 0.183 | -0.390 to +0.328 | 0.8645 | 236,749 | 571 |
| H4 | whiff | s_S7_h1.0 | -0.336 | 0.113 | -0.556 to -0.115 | 0.0029 | 201,162 | 517 |
| H4 | whiff | s_S8_30_h1.0 | -0.303 | 0.139 | -0.576 to -0.030 | 0.0296 | 201,162 | 517 |
| H4 | whiff | s_S31_90_h1.0 | -0.507 | 0.138 | -0.777 to -0.237 | 0.0002 | 201,162 | 517 |
| H4 | whiff | logN7 | -0.504 | 0.170 | -0.838 to -0.170 | 0.0031 | 201,162 | 517 |
| H4 | whiff | logN8_30 | +0.045 | 0.243 | -0.431 to +0.522 | 0.8522 | 201,162 | 517 |
| H4 | whiff | logN31_90 | +0.280 | 0.218 | -0.146 to +0.706 | 0.1982 | 201,162 | 517 |
| H5 | rv | s_S30_h1.0 | -0.115 | 0.045 | -0.203 to -0.026 | 0.0112 | 512,512 | 587 |
| H5 | rv | logN30 | +0.102 | 0.114 | -0.122 to +0.327 | 0.3715 | 512,512 | 587 |

**Against the plan's rules:**
- **H1:** passes. The 2026 coefficient is negative and its interval excludes zero.
- **H3 (lead placebo):** fails. Exposure from the *next* 30 days has a coefficient of its own whose interval excludes zero. Under the plan, H1 is therefore reported as confounded: the association is real, but it isn't evidence that hitters adapt to shapes they've seen.
- **H2:** the wide kernel's coefficient is larger than the narrow one's, the opposite of what an exact-shape effect predicts (reported, not a pass/fail test).
- **H5:** negative, interval excludes zero; it carries the same confound as H1.
