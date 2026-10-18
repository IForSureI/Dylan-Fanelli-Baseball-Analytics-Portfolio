-- hitter_zone_discipline
-- Question: Where does this hitter swing, where does he miss, and how much does he chase, zone by
--           zone (Statcast zones 1-9 in the strike zone, 11-14 outside it)?
-- Inputs:
--   $batter    MLBAM batter id (required)
--   $season    season, e.g. 2026 (required)
-- Output: one row per zone, plus one total row each for "in zone" and "out of zone" (zone NULL)
--   region       in zone (1-9) or out of zone (11-14)
--   zone         Statcast zone; NULL on the region total
--   pitches      pitches seen
--   swings       swings
--   swing_pct    swings / pitches
--   whiffs       whiffs
--   whiff_pct    whiffs / swings
--   chase_pct    swing rate outside the zone (= swing_pct on out-of-zone rows, NULL in the zone)
-- Definitions:
--   swing        swinging_strike, swinging_strike_blocked, foul, foul_tip, foul_bunt, missed_bunt,
--                hit_into_play (and the older hit_into_play_no_out / hit_into_play_score labels)
--   whiff        swinging_strike, swinging_strike_blocked, foul_tip, missed_bunt
--   Zones 1-9 are a 3x3 grid from the catcher's view (1 = up and to the catcher's left). Zones 11-14
--   are the four out-of-zone quadrants (11 up-left, 12 up-right, 13 down-left, 14 down-right).
--   Pitches with no zone are left out. Regular season only; automatic_ball / automatic_strike dropped.

WITH seen AS (
    -- grain: one row per pitch to this hitter with a tracked zone
    SELECT
        zone,
        CASE WHEN zone BETWEEN 1 AND 9 THEN 'in zone' ELSE 'out of zone' END   AS region,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip', 'foul_bunt',
                        'missed_bunt', 'hit_into_play', 'hit_into_play_no_out',
                        'hit_into_play_score')                                 AS is_swing,
        description IN ('swinging_strike', 'swinging_strike_blocked', 'foul_tip',
                        'missed_bunt')                                         AS is_whiff
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
      AND batter = $batter
      AND zone IS NOT NULL
      AND description NOT IN ('automatic_ball', 'automatic_strike')
),

by_zone AS (
    -- (region, zone) gives the zone rows; (region) alone gives the two region totals
    SELECT
        region,
        zone,
        COUNT(*)                            AS pitches,
        COUNT(*) FILTER (WHERE is_swing)    AS swings,
        COUNT(*) FILTER (WHERE is_whiff)    AS whiffs
    FROM seen
    GROUP BY GROUPING SETS ((region, zone), (region))
)

SELECT
    region,
    zone,
    pitches,
    swings,
    ROUND(100.0 * swings / pitches, 1)                  AS swing_pct,
    whiffs,
    ROUND(100.0 * whiffs / NULLIF(swings, 0), 1)        AS whiff_pct,
    CASE WHEN region = 'out of zone'
         THEN ROUND(100.0 * swings / pitches, 1) END    AS chase_pct
FROM by_zone
ORDER BY region, zone NULLS FIRST
