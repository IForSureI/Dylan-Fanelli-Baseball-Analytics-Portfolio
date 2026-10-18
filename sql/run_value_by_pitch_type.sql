-- run_value_by_pitch_type
-- Question: Which pitches save the most runs per 100 thrown, and where does each rank among pitches
--           of the same type?
-- Inputs:
--   $season        season, e.g. 2026 (required)
--   $min_pitches   fewest pitches of a type for a pitcher-pitch row to be listed (default 250)
--   $pitcher       MLBAM pitcher id (default NULL = every pitcher)
-- Output: one row per pitcher x pitch type with enough pitches, best run value first
--   pitcher         MLBAM id
--   name            from the people register (NULL if missing)
--   pitch_type      Statcast pitch label
--   n               pitches
--   usage_pct       share of his pitches (computed before the floor)
--   velo            mean release speed (mph)
--   runs_saved      runs saved by the pitch over the season (pitcher's view)
--   rv_per100       runs saved per 100 pitches
--   rank_in_type    1 = best rv_per100 among qualifying pitches of the same type
--   type_avg_rv100  mean rv_per100 of qualifying pitches of that type (pitch-weighted)
-- Definitions:
--   run value     Statcast's delta_run_exp: the change in the inning's run expectancy from the pitch,
--                 from the offense's side. runs_saved = -SUM(delta_run_exp), so positive is good for the
--                 pitcher. rv_per100 = 100 x runs_saved / pitches, as in baseball/evaluation/arsenal.py
--                 outcomes().
--   Run value per pitch is noisy; read rv_per100 next to n.
--   Regular season only; automatic_ball / automatic_strike dropped (no pitch was thrown).

WITH thrown AS (
    -- grain: one row per pitch
    SELECT pitcher, pitch_type, release_speed, delta_run_exp
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND pitch_type IS NOT NULL
      AND description NOT IN ('automatic_ball', 'automatic_strike')
      AND ($pitcher::BIGINT IS NULL OR pitcher = $pitcher::BIGINT)
),

cells AS (
    -- grain: pitcher x pitch type; usage is taken here, over every pitch, before any floor
    SELECT
        pitcher,
        pitch_type,
        COUNT(*)                                                        AS n,
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY pitcher)    AS usage_pct,
        AVG(release_speed)                                              AS velo,
        -SUM(delta_run_exp)                                             AS runs_saved
    FROM thrown
    GROUP BY pitcher, pitch_type
),

qualified AS (
    -- the floor comes before the ranking, so ranks are among qualifiers only
    SELECT *, 100.0 * runs_saved / n AS rv_per100
    FROM cells
    WHERE n >= $min_pitches
)

SELECT
    q.pitcher,
    pe.name,
    q.pitch_type,
    q.n,
    ROUND(q.usage_pct, 1)                                                           AS usage_pct,
    ROUND(q.velo, 1)                                                                AS velo,
    ROUND(q.runs_saved, 1)                                                          AS runs_saved,
    ROUND(q.rv_per100, 2)                                                           AS rv_per100,
    RANK() OVER (PARTITION BY q.pitch_type ORDER BY q.rv_per100 DESC)               AS rank_in_type,
    ROUND(100.0 * SUM(q.runs_saved) OVER (PARTITION BY q.pitch_type)
                / SUM(q.n) OVER (PARTITION BY q.pitch_type), 2)                     AS type_avg_rv100
FROM qualified AS q
LEFT JOIN people AS pe ON pe.key_mlbam = q.pitcher
ORDER BY q.rv_per100 DESC, q.pitcher, q.pitch_type
