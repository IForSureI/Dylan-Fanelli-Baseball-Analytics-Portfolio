# Shape exposure: follow-up designs, specified after the placebo failed and before they were fit

*Written 2026-10-18, after [the 2026 confirmation](2026-shape-exposure-2026-results.md) failed its lead placebo, and before either design below was fit. These are exploratory: they were not in the original plan, and the report will say so.*

## Why a follow-up
- **What the failure means:** in 2026, the shapes a hitter is *about to* see predict his whiffs almost as well as the shapes he *has* seen. Something stable is linked to both.
- **The likeliest cause is selection on who plays against what:**
  - A hitter who handles a shape keeps getting at-bats against it.
  - A hitter who doesn't gets platooned away from it.
  - Past and future exposure then both stand in for a skill the fixed effects don't capture, because that skill is shape-specific within a pitch family.
- **What the follow-up needs:** variation in exposure that a manager's lineup choices can't produce.

## Design A: the schedule (reduced form)
- **The exposure:** a hitter's team plays series in an order fixed before the season.
  - The staff it faced in the *previous* series exposed him to that staff's shapes.
  - The staff of the *next* series hasn't yet.
  - Today's lineup is chosen against today's starter, not against last week's opponent.
- **The variable:** for each target pitch, the share of the previous-series opponent's season pitches (same family, pitcher hand and batter side) that look like it.
  - It uses the same kernel at 1 SD.
  - It's computed whether or not the hitter played in that series, so it's intent-to-treat.
  - The same share for the *next*-series opponent is the placebo.
  - Each is standardized within family.
- **The model:** the H1 fixed effects, with both shares in one regression, 2024–2026 pooled; each season is also reported alone.
- **Pre-specified test:** the previous-series coefficient minus the next-series coefficient is negative, with a 95% interval (batter-clustered, from the joint fit) that excludes zero.
  - If the difference's interval includes zero, the report says adaptation isn't detected by the schedule and gives the bound.

## Design B: timing within a hitter's season
- **The added control:** the hitter's season-long share for that shape, from all of his same-season games except today's, before and after.
  - With it in the model, S30 measures whether *recent* exposure matters beyond his season-long diet, which is where selection lives.
- **The model:** H3's model (S30 and the lead share, with their log counts) plus the season-long share and its log count; 2024–2026 pooled, and each season alone.
- **Pre-specified test:** S30's interval excludes zero (negative) and the lead share's interval includes zero.

## Reporting
- Both designs are reported whatever they show, labeled exploratory, next to the original plan's results.
- If either design passes, the decision translation from the original plan is redone on that design's coefficient. If neither passes, there is no translation, and the report says the public data can't separate adaptation from selection with these designs.
