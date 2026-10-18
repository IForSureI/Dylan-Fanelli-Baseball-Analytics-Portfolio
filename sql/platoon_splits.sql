-- platoon_splits
-- Question: How does every pitcher do against left-handed and right-handed hitters, and how big is
--           his platoon gap?
-- Inputs:
--   $season    season, e.g. 2026 (required)
--   $min_pa    fewest PAs against EACH side for a pitcher to be listed (default 100)
-- Output: one row per pitcher with enough PAs against both sides, biggest platoon gap first
--   pitcher        MLBAM id
--   name           from the people register (NULL if missing)
--   p_throws       R or L
--   pa_vs_l        PAs against left-handed hitters
--   woba_vs_l      wOBA allowed to left-handed hitters
--   xwoba_vs_l     xwOBA allowed to left-handed hitters
--   k_pct_vs_l     strikeouts / PAs against left-handed hitters
--   pa_vs_r        PAs against right-handed hitters
--   woba_vs_r      wOBA allowed to right-handed hitters
--   xwoba_vs_r     xwOBA allowed to right-handed hitters
--   k_pct_vs_r     strikeouts / PAs against right-handed hitters
--   platoon_gap    xwOBA against opposite-hand hitters minus xwOBA against same-hand hitters
-- Definitions:
--   PA        a row with an event that ends a plate appearance: events is set and is not a baserunning
--             event (caught_stealing*, pickoff*, stolen_base*, wild_pitch, passed_ball, other_advance,
--             truncated_pa). Same rule as baseball/evaluation/reliever.py.
--   wOBA      SUM(woba_value) / SUM(woba_denom) over PAs with woba_denom = 1.
--   xwOBA     same denominator; the numerator uses estimated_woba_using_speedangle on balls in play
--             (the actual woba_value when Statcast has no estimate) and woba_value otherwise.
--   strikeout events strikeout or strikeout_double_play.
--   Hand is the hitter's side for that PA (stand), so switch hitters count on the side they hit from.
--   platoon_gap uses xwOBA because it settles faster than wOBA; a positive gap is the usual platoon split.
--   Regular season only. PA-ending rows are kept even when no pitch was thrown.

WITH pa AS (
    -- grain: one row per plate appearance
    SELECT
        pitcher,
        p_throws,
        stand,
        events IN ('strikeout', 'strikeout_double_play')                       AS is_k,
        woba_denom = 1                                                          AS in_woba,
        woba_value,
        CASE WHEN type = 'X'
             THEN COALESCE(estimated_woba_using_speedangle, woba_value)
             ELSE woba_value END                                                AS xwoba_value
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND events IS NOT NULL
      AND NOT regexp_matches(events,
          '^(caught_stealing|pickoff|stolen_base|wild_pitch|passed_ball|other_advance|truncated_pa)')
),

by_pitcher AS (
    SELECT
        pitcher,
        MODE(p_throws)                                                          AS p_throws,
        COUNT(*) FILTER (WHERE stand = 'L')                                     AS pa_vs_l,
        AVG(woba_value) FILTER (WHERE stand = 'L' AND in_woba)                  AS woba_vs_l,
        AVG(xwoba_value) FILTER (WHERE stand = 'L' AND in_woba)                 AS xwoba_vs_l,
        AVG(is_k::INT) FILTER (WHERE stand = 'L')                               AS k_vs_l,
        COUNT(*) FILTER (WHERE stand = 'R')                                     AS pa_vs_r,
        AVG(woba_value) FILTER (WHERE stand = 'R' AND in_woba)                  AS woba_vs_r,
        AVG(xwoba_value) FILTER (WHERE stand = 'R' AND in_woba)                 AS xwoba_vs_r,
        AVG(is_k::INT) FILTER (WHERE stand = 'R')                               AS k_vs_r
    FROM pa
    GROUP BY pitcher
    HAVING COUNT(*) FILTER (WHERE stand = 'L') >= $min_pa
       AND COUNT(*) FILTER (WHERE stand = 'R') >= $min_pa
)

SELECT
    b.pitcher,
    pe.name,
    b.p_throws,
    b.pa_vs_l,
    ROUND(b.woba_vs_l, 3)                       AS woba_vs_l,
    ROUND(b.xwoba_vs_l, 3)                      AS xwoba_vs_l,
    ROUND(100 * b.k_vs_l, 1)                    AS k_pct_vs_l,
    b.pa_vs_r,
    ROUND(b.woba_vs_r, 3)                       AS woba_vs_r,
    ROUND(b.xwoba_vs_r, 3)                      AS xwoba_vs_r,
    ROUND(100 * b.k_vs_r, 1)                    AS k_pct_vs_r,
    ROUND(CASE WHEN b.p_throws = 'R' THEN b.xwoba_vs_l - b.xwoba_vs_r
               ELSE b.xwoba_vs_r - b.xwoba_vs_l END, 3)   AS platoon_gap
FROM by_pitcher AS b
LEFT JOIN people AS pe ON pe.key_mlbam = b.pitcher
ORDER BY platoon_gap DESC, b.pitcher
