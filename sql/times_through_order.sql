-- times_through_order
-- Question: How much worse does each pitcher get the second and third time hitters see him in a game?
-- Inputs:
--   $season       season, e.g. 2026 (required)
--   $min_pa_3rd   fewest third-time-or-later PAs for a pitcher to be listed (default 100)
-- Output: one row per pitcher with enough third-time PAs, biggest third-time penalty first
--   pitcher       MLBAM id
--   name          from the people register (NULL if missing)
--   pa_1st        wOBA PAs the first time through
--   woba_1st      wOBA allowed the first time through
--   pa_2nd        wOBA PAs the second time through
--   woba_2nd      wOBA allowed the second time through
--   pa_3rd        wOBA PAs the third time through or later
--   woba_3rd      wOBA allowed the third time through or later
--   penalty_2nd   woba_2nd - woba_1st
--   penalty_3rd   woba_3rd - woba_1st
-- Definitions:
--   times through  Statcast's n_thruorder_pitcher on the PA's last pitch; 4th-time PAs (rare) fold into 3rd.
--   wOBA           SUM(woba_value) / SUM(woba_denom) over PA-ending rows with woba_denom = 1 (Statcast's
--                  wOBA PAs: intentional walks and sacrifice bunts are not in the denominator).
--   Regular season only. PA-ending rows are kept even when no pitch was thrown (an automatic strike
--   three still ends the PA), so this query does not drop automatic_ball / automatic_strike rows.
--   The raw penalty mixes skill with who is left in games late; regress it before calling it a trait.

WITH pa AS (
    -- grain: one row per plate appearance that counts in wOBA
    SELECT
        pitcher,
        LEAST(n_thruorder_pitcher, 3)   AS time_through,
        woba_value
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND woba_denom = 1
),

by_pitcher AS (
    -- one pass, three columns per time through: conditional aggregation pivots the rows into columns
    SELECT
        pitcher,
        COUNT(*) FILTER (WHERE time_through = 1)              AS pa_1st,
        AVG(woba_value) FILTER (WHERE time_through = 1)       AS woba_1st,
        COUNT(*) FILTER (WHERE time_through = 2)              AS pa_2nd,
        AVG(woba_value) FILTER (WHERE time_through = 2)       AS woba_2nd,
        COUNT(*) FILTER (WHERE time_through = 3)              AS pa_3rd,
        AVG(woba_value) FILTER (WHERE time_through = 3)       AS woba_3rd
    FROM pa
    GROUP BY pitcher
    HAVING COUNT(*) FILTER (WHERE time_through = 3) >= $min_pa_3rd
)

SELECT
    b.pitcher,
    pe.name,
    b.pa_1st,
    ROUND(b.woba_1st, 3)                    AS woba_1st,
    b.pa_2nd,
    ROUND(b.woba_2nd, 3)                    AS woba_2nd,
    b.pa_3rd,
    ROUND(b.woba_3rd, 3)                    AS woba_3rd,
    ROUND(b.woba_2nd - b.woba_1st, 3)       AS penalty_2nd,
    ROUND(b.woba_3rd - b.woba_1st, 3)       AS penalty_3rd
FROM by_pitcher AS b
LEFT JOIN people AS pe ON pe.key_mlbam = b.pitcher
ORDER BY penalty_3rd DESC, b.pitcher
