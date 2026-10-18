-- arsenal_by_count
-- Question: What does this pitcher throw in each count state, how hard, and how often do hitters
--           swing and miss at it or chase it?
-- Inputs:
--   $pitcher   MLBAM pitcher id (required)
--   $season    season, e.g. 2026 (required)
--   $min_n     smallest pitch-type cell shown in a count state (default 1)
-- Output: one row per count state x pitch type, plus an "all" count state for the whole season
--   count_state   0-0, even/ahead, behind, 2 strikes, or all
--   pitch_type    Statcast pitch label
--   n             pitches
--   usage_pct     share of his pitches in that count state
--   velo          mean release speed (mph)
--   swings        swings
--   whiffs        whiffs
--   whiff_pct     whiffs / swings
--   out_zone      pitches outside the strike zone (zones 11-14)
--   chase_pct     swings at pitches outside the zone / pitches outside the zone
-- Definitions:
--   count state   0-0; 2 strikes (any 2-strike count); behind (more balls than strikes); even/ahead (the
--                 rest). Same buckets as baseball/evaluation/delivery.py count_state().
--   swing         swinging_strike, swinging_strike_blocked, foul, foul_tip, foul_bunt, missed_bunt,
--                 hit_into_play (and the older hit_into_play_no_out / hit_into_play_score labels)
--   whiff         swinging_strike, swinging_strike_blocked, foul_tip, missed_bunt
--   in zone       Statcast zone 1-9; outside = zone 11-14 (a pitch with no zone is neither)
--   usage_pct is computed over every pitch type before the min_n floor, so a floor never inflates usage.
--   Regular season only (game_type 'R'). Rows with no pitch thrown (automatic_ball, automatic_strike)
--   are dropped.

WITH thrown AS (
    -- grain: one row per pitch he threw this season
    SELECT pitch_type, release_speed, balls, strikes, zone, description
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND pitcher = $pitcher
      AND pitch_type IS NOT NULL
      AND description NOT IN ('automatic_ball', 'automatic_strike')
),

flagged AS (
    -- flags once, here; every rate below is built from these
    SELECT
        pitch_type,
        release_speed,
        CASE
            WHEN balls = 0 AND strikes = 0 THEN '0-0'
            WHEN strikes = 2               THEN '2 strikes'
            WHEN balls > strikes           THEN 'behind'
            ELSE 'even/ahead'
        END                                                                  AS count_state,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip', 'foul_bunt',
                        'missed_bunt', 'hit_into_play', 'hit_into_play_no_out',
                        'hit_into_play_score')                               AS is_swing,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul_tip',
                        'missed_bunt')                                       AS is_whiff,
        zone IN (11, 12, 13, 14)                                             AS is_out_zone
    FROM thrown
),

cells AS (
    -- GROUPING SETS builds the count-state rows and the season ("all") rows in one pass
    SELECT
        CASE WHEN GROUPING(count_state) = 1 THEN 'all' ELSE count_state END AS count_state,
        pitch_type,
        COUNT(*)                                                    AS n,
        AVG(release_speed)                                          AS velo,
        COUNT(*) FILTER (WHERE is_swing)                            AS swings,
        COUNT(*) FILTER (WHERE is_whiff)                            AS whiffs,
        COUNT(*) FILTER (WHERE is_out_zone)                         AS out_zone,
        COUNT(*) FILTER (WHERE is_out_zone AND is_swing)            AS chases
    FROM flagged
    GROUP BY GROUPING SETS ((count_state, pitch_type), (pitch_type))
)

SELECT
    count_state,
    pitch_type,
    n,
    ROUND(100.0 * n / SUM(n) OVER (PARTITION BY count_state), 1)   AS usage_pct,
    ROUND(velo, 1)                                                  AS velo,
    swings,
    whiffs,
    ROUND(100.0 * whiffs / NULLIF(swings, 0), 1)                    AS whiff_pct,
    out_zone,
    ROUND(100.0 * chases / NULLIF(out_zone, 0), 1)                  AS chase_pct
FROM cells
QUALIFY n >= $min_n          -- QUALIFY runs after the window, so usage_pct already counts every pitch
ORDER BY
    CASE count_state WHEN 'all' THEN 0 WHEN '0-0' THEN 1 WHEN 'even/ahead' THEN 2
                     WHEN 'behind' THEN 3 ELSE 4 END,
    n DESC,
    pitch_type
