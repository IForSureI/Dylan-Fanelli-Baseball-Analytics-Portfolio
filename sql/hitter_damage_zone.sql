-- hitter_damage_zone
-- Question: In which zones does this hitter do damage when he makes contact, and in which zones is
--           he weak, overall or in one count state?
-- Inputs:
--   $batter        MLBAM batter id (required)
--   $season        season, e.g. 2026 (required)
--   $count_state   0-0, even/ahead, behind or 2 strikes (default NULL = every count; anything else is an
--                  error)
--   $min_bip       fewest balls in play for a zone to get a damage rank (default 5)
-- Output: one row per Statcast zone (1-9, 11-14) he put a ball in play in, every rate next to its count
--   zone                Statcast zone
--   pitches             pitches seen in the zone
--   swings              swings at them
--   bip                 balls in play
--   tracked_bip         balls in play with a tracked exit velocity
--   xwoba_con           mean expected wOBA on those balls in play
--   xwoba_con_vs_avg    xwoba_con minus his own xwoba_con over every zone (same count filter)
--   hard_hit_pct        balls in play at 95+ mph / tracked balls in play (Savant's denominator)
--   barrel_pct          barrels / tracked balls in play
--   damage_rank         1 = highest xwoba_con among zones with at least min_bip balls in play
-- Definitions:
--   ball in play  type = 'X'. xwoba_con averages estimated_woba_using_speedangle over balls in play that
--                 have one (Statcast's xwOBA on contact; same as xwoba_con in baseball/evaluation/arsenal.py).
--   barrel        launch_speed_angle = 6 (Statcast's barrel class).
--   count state   pitcher's count buckets as in arsenal_by_count: 0-0; 2 strikes; behind (more balls than
--                 strikes, the hitter is ahead); even/ahead (the rest).
--   swing         swinging_strike, swinging_strike_blocked, foul, foul_tip, foul_bunt, missed_bunt,
--                 hit_into_play (and the older hit_into_play_no_out / hit_into_play_score labels)
--   Zone samples are small: a zone with 6 balls in play tells you little. Regular season only;
--   automatic_ball / automatic_strike dropped.

WITH guard AS (
    -- a misspelled count state would silently match nothing; stop with an error instead
    SELECT CASE WHEN $count_state::VARCHAR IS NOT NULL
                 AND $count_state::VARCHAR NOT IN ('0-0', 'even/ahead', 'behind', '2 strikes')
                THEN error('count_state must be one of: 0-0, even/ahead, behind, 2 strikes') END AS bad
),

seen AS (
    -- grain: one row per pitch to this hitter with a tracked zone, in the count state asked for
    SELECT
        zone,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip', 'foul_bunt',
                        'missed_bunt', 'hit_into_play', 'hit_into_play_no_out',
                        'hit_into_play_score')                       AS is_swing,
        type = 'X'                                                   AS is_bip,
        CASE WHEN type = 'X' THEN estimated_woba_using_speedangle END AS xwoba_bip,
        type = 'X' AND launch_speed IS NOT NULL                      AS is_tracked,
        type = 'X' AND launch_speed >= 95                            AS is_hard,
        type = 'X' AND launch_speed_angle = 6                        AS is_barrel
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND batter = $batter
      AND zone IS NOT NULL
      AND description NOT IN ('automatic_ball', 'automatic_strike')
      AND (SELECT bad FROM guard) IS NULL
      AND ($count_state::VARCHAR IS NULL
           OR $count_state::VARCHAR = CASE
                WHEN balls = 0 AND strikes = 0 THEN '0-0'
                WHEN strikes = 2               THEN '2 strikes'
                WHEN balls > strikes           THEN 'behind'
                ELSE 'even/ahead' END)
),

by_zone AS (
    SELECT
        zone,
        COUNT(*)                                AS pitches,
        COUNT(*) FILTER (WHERE is_swing)        AS swings,
        COUNT(*) FILTER (WHERE is_bip)          AS bip,
        AVG(xwoba_bip)                          AS xwoba_con,
        COUNT(*) FILTER (WHERE is_tracked)      AS tracked_bip,
        COUNT(*) FILTER (WHERE is_hard)         AS hard,
        COUNT(*) FILTER (WHERE is_barrel)       AS barrels,
        SUM(xwoba_bip)                          AS xwoba_sum,
        COUNT(xwoba_bip)                        AS xwoba_n
    FROM seen
    GROUP BY zone
)

SELECT
    zone,
    pitches,
    swings,
    bip,
    tracked_bip,
    ROUND(xwoba_con, 3)                                                             AS xwoba_con,
    -- his overall xwOBA on contact = summed numerators over summed denominators, as a window
    ROUND(xwoba_con - SUM(xwoba_sum) OVER () / SUM(xwoba_n) OVER (), 3) + 0.0       AS xwoba_con_vs_avg,
    ROUND(100.0 * hard / NULLIF(tracked_bip, 0), 1)                                 AS hard_hit_pct,
    ROUND(100.0 * barrels / NULLIF(tracked_bip, 0), 1)                              AS barrel_pct,
    CASE WHEN bip >= $min_bip
         THEN RANK() OVER (ORDER BY CASE WHEN bip >= $min_bip THEN xwoba_con END DESC NULLS LAST) END
                                                                                    AS damage_rank
FROM by_zone
WHERE bip > 0
ORDER BY zone
