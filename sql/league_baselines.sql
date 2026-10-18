-- league_baselines
-- Question: What is league average for each pitch type and season, so a pitcher's whiff, CSW, chase
--           and zone rates can be read against it?
-- Inputs:
--   $season_from   first season, e.g. 2024 (required)
--   $season_to     last season, e.g. 2026 (required)
--   $min_pitches   fewest pitches for a pitch type to get its own row in a season (default 1000)
-- Output: one row per season x pitch type, plus an ALL row per season
--   season         game_year
--   pitch_type     Statcast pitch label, or ALL for every pitch that season
--   pitches        pitches
--   velo           mean release speed (mph)
--   zone_pct       pitches in zones 1-9 / pitches
--   swing_pct      swings / pitches
--   whiff_pct      whiffs / swings
--   csw_pct        (called strikes + whiffs) / pitches
--   chase_pct      swings at pitches outside the zone / pitches outside the zone
--   rv_per100      runs saved per 100 pitches (pitcher's view, -100 x mean delta_run_exp)
-- Definitions:
--   swing          swinging_strike, swinging_strike_blocked, foul, foul_tip, foul_bunt, missed_bunt,
--                  hit_into_play (and the older hit_into_play_no_out / hit_into_play_score labels)
--   whiff          swinging_strike, swinging_strike_blocked, foul_tip, missed_bunt
--   called strike  description = 'called_strike'
--   zone           Statcast zone 1-9 in, 11-14 out. zone_pct divides by every pitch (as in
--                  baseball/evaluation/arsenal.py outcomes()); chase_pct divides by pitches with a zone
--                  outside 1-9.
--   The ALL row always counts every pitch, including pitch types too rare for their own row.
--   Regular season only; automatic_ball / automatic_strike dropped (no pitch was thrown).

WITH flagged AS (
    -- grain: one row per pitch; flags once
    SELECT
        game_year                                                            AS season,
        pitch_type,
        release_speed,
        delta_run_exp,
        zone BETWEEN 1 AND 9                                                 AS is_in_zone,
        zone IN (11, 12, 13, 14)                                             AS is_out_zone,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip', 'foul_bunt',
                        'missed_bunt', 'hit_into_play', 'hit_into_play_no_out',
                        'hit_into_play_score')                               AS is_swing,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul_tip',
                        'missed_bunt')                                       AS is_whiff,
        description = 'called_strike'                                        AS is_called
    FROM pitches
    WHERE game_type = 'R'
      AND game_year BETWEEN $season_from AND $season_to
      AND pitch_type IS NOT NULL
      AND description NOT IN ('automatic_ball', 'automatic_strike')
),

cells AS (
    -- (season, pitch_type) rows and a (season) total in one scan; GROUPING() marks the total
    SELECT
        season,
        CASE WHEN GROUPING(pitch_type) = 1 THEN 'ALL' ELSE pitch_type END   AS pitch_type,
        COUNT(*)                                                             AS pitches,
        AVG(release_speed)                                                   AS velo,
        COUNT(*) FILTER (WHERE is_in_zone)                                   AS in_zone,
        COUNT(*) FILTER (WHERE is_out_zone)                                  AS out_zone,
        COUNT(*) FILTER (WHERE is_swing)                                     AS swings,
        COUNT(*) FILTER (WHERE is_whiff)                                     AS whiffs,
        COUNT(*) FILTER (WHERE is_called)                                    AS called,
        COUNT(*) FILTER (WHERE is_out_zone AND is_swing)                     AS chases,
        SUM(delta_run_exp)                                                   AS rv
    FROM flagged
    GROUP BY GROUPING SETS ((season, pitch_type), (season))
)

SELECT
    season,
    pitch_type,
    pitches,
    ROUND(velo, 1)                                          AS velo,
    ROUND(100.0 * in_zone / pitches, 1)                     AS zone_pct,
    ROUND(100.0 * swings / pitches, 1)                      AS swing_pct,
    ROUND(100.0 * whiffs / NULLIF(swings, 0), 1)            AS whiff_pct,
    ROUND(100.0 * (called + whiffs) / pitches, 1)           AS csw_pct,
    ROUND(100.0 * chases / NULLIF(out_zone, 0), 1)          AS chase_pct,
    ROUND(-100.0 * rv / pitches, 2)                         AS rv_per100
FROM cells
WHERE pitch_type = 'ALL' OR pitches >= $min_pitches
ORDER BY season, pitch_type = 'ALL' DESC, pitches DESC
