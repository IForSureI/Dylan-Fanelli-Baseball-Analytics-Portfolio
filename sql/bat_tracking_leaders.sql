-- bat_tracking_leaders
-- Question: Who swings the bat hardest, and who has the shortest and longest swings, on competitive
--           swings?
-- Inputs:
--   $season        season, e.g. 2026 (required)
--   $min_swings    fewest competitive swings for a hitter to be listed (default 200)
-- Output: one row per qualifying hitter, fastest average bat speed first
--   batter               MLBAM id
--   name                 from the people register (NULL if missing)
--   tracked_swings       swings with a bat speed reading
--   competitive_swings   tracked swings that pass the competitive rule
--   bat_speed            mean bat speed on competitive swings (mph)
--   swing_length         mean swing length on competitive swings (ft)
--   fast_swing_pct       competitive swings at 75+ mph / competitive swings
--   bat_speed_rank       1 = fastest among qualifiers
--   swing_length_rank    1 = shortest among qualifiers
-- Definitions:
--   competitive swing   the fastest 90% of a hitter's tracked swings in the season (bat speed at or above
--                       his own 10th percentile), plus any swing of 60+ mph with a 90+ mph exit velocity.
--                       Bunts (foul_bunt, missed_bunt) never count. Same rule as competitive_swings() in
--                       baseball/evaluation/reliability.py; the percentile is linear-interpolated
--                       (QUANTILE_CONT), as pandas' quantile() is.
--   swing               swinging_strike, swinging_strike_blocked, foul, foul_tip, foul_bunt, missed_bunt,
--                       hit_into_play (and the older hit_into_play_no_out / hit_into_play_score labels)
--   Regular season only.

WITH tracked AS (
    -- grain: one row per tracked, non-bunt swing
    SELECT batter, bat_speed, swing_length, launch_speed
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND bat_speed IS NOT NULL
      AND description IN ('swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip',
                          'hit_into_play', 'hit_into_play_no_out', 'hit_into_play_score')
),

with_cut AS (
    -- a window aggregate: each swing carries its hitter's own 10th-percentile bat speed
    SELECT
        *,
        QUANTILE_CONT(bat_speed, 0.10) OVER (PARTITION BY batter)   AS slow_cut,
        COUNT(*) OVER (PARTITION BY batter)                          AS tracked_swings
    FROM tracked
),

competitive AS (
    -- the 1e-9 slack absorbs floating-point error in the interpolated percentile: a swing recorded at
    -- exactly 63.9 mph must pass a cut computed as 63.900000000000006
    SELECT *
    FROM with_cut
    WHERE bat_speed >= slow_cut - 1e-9
       OR (bat_speed >= 60 AND launch_speed >= 90)
),

by_hitter AS (
    SELECT
        batter,
        ANY_VALUE(tracked_swings)                   AS tracked_swings,
        COUNT(*)                                    AS competitive_swings,
        AVG(bat_speed)                              AS bat_speed,
        AVG(swing_length)                           AS swing_length,
        AVG((bat_speed >= 75)::INT)                 AS fast_share
    FROM competitive
    GROUP BY batter
    HAVING COUNT(*) >= $min_swings
)

SELECT
    b.batter,
    pe.name,
    b.tracked_swings,
    b.competitive_swings,
    ROUND(b.bat_speed, 1)                                   AS bat_speed,
    ROUND(b.swing_length, 2)                                AS swing_length,
    ROUND(100 * b.fast_share, 1)                            AS fast_swing_pct,
    RANK() OVER (ORDER BY b.bat_speed DESC)                 AS bat_speed_rank,
    RANK() OVER (ORDER BY b.swing_length ASC)               AS swing_length_rank
FROM by_hitter AS b
LEFT JOIN people AS pe ON pe.key_mlbam = b.batter
ORDER BY bat_speed_rank, b.batter
