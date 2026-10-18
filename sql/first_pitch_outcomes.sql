-- first_pitch_outcomes
-- Question: How often does the first pitch go for a strike, and how do plate appearances end after an
--           0-1 count compared with a 1-0 count?
-- Inputs:
--   $season    season, e.g. 2026 (required)
--   $pitcher   MLBAM pitcher id (default NULL = the whole league)
-- Output: one row per first-pitch result
--   after_first_pitch        0-1 (strike, PA goes on), 1-0 (ball, PA goes on), in play on 0-0, or
--                            hit by pitch on 0-0
--   counts_as_strike         true when the first pitch was a strike (0-1 or in play)
--   pa                       plate appearances
--   share_pct                share of all plate appearances
--   first_pitch_strike_pct   strikes / first pitches over every row (the same value on each row)
--   woba                     wOBA of the PA
--   xwoba                    xwOBA of the PA
--   k_pct                    strikeouts / PA
--   bb_pct                   walks / PA
-- Definitions:
--   first pitch    the thrown pitch at 0-0. PAs whose 0-0 row is automatic_ball / automatic_strike (a
--                  pitch-clock call or an intentional walk, no pitch thrown) or intent_ball are left out.
--   ball           ball, blocked_ball, pitchout, hit_by_pitch (as in baseball/evaluation/delivery.py);
--                  every other thrown pitch is a strike.
--   PA result      the PA's last row with a plate-appearance event (baserunning events like
--                  caught_stealing and truncated_pa do not count). A PA that changes pitchers counts for
--                  the pitcher who threw the first pitch.
--   wOBA, xwOBA    over PAs with woba_denom = 1; xwOBA uses estimated_woba_using_speedangle on balls in
--                  play (woba_value when there is no estimate). walks = walk only. An intentional walk
--                  issued before any pitch (automatic_ball) never reaches this table, since it has no thrown
--                  first pitch; one issued mid-count after a thrown first pitch does, as intent_walk, but
--                  isn't counted in bb_pct.
--   Regular season only.

WITH season_pitches AS (
    SELECT game_pk, at_bat_number, pitch_number, pitcher, balls, strikes, description, type, events,
           woba_value, woba_denom, estimated_woba_using_speedangle
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
),

first_pitch AS (
    -- grain: one row per PA, its thrown 0-0 pitch
    SELECT
        game_pk,
        at_bat_number,
        CASE
            WHEN description IN ('hit_into_play', 'hit_into_play_no_out', 'hit_into_play_score')
                THEN 'in play on 0-0'
            WHEN description = 'hit_by_pitch'
                THEN 'hit by pitch on 0-0'
            WHEN description IN ('ball', 'blocked_ball', 'pitchout')
                THEN '1-0'
            ELSE '0-1'
        END AS after_first_pitch
    FROM season_pitches
    WHERE balls = 0 AND strikes = 0
      AND description NOT IN ('automatic_ball', 'automatic_strike', 'intent_ball')
      AND ($pitcher::BIGINT IS NULL OR pitcher = $pitcher::BIGINT)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, at_bat_number ORDER BY pitch_number) = 1
),

pa_result AS (
    -- grain: one row per PA, its last plate-appearance event
    SELECT
        game_pk,
        at_bat_number,
        events,
        woba_denom = 1                                                          AS in_woba,
        woba_value,
        CASE WHEN type = 'X'
             THEN COALESCE(estimated_woba_using_speedangle, woba_value)
             ELSE woba_value END                                                AS xwoba_value
    FROM season_pitches
    WHERE events IS NOT NULL
      AND NOT regexp_matches(events,
          '^(caught_stealing|pickoff|stolen_base|wild_pitch|passed_ball|other_advance|truncated_pa)')
    QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, at_bat_number ORDER BY pitch_number DESC) = 1
),

by_result AS (
    SELECT
        f.after_first_pitch,
        f.after_first_pitch IN ('0-1', 'in play on 0-0')                         AS counts_as_strike,
        COUNT(*)                                                                 AS pa,
        AVG(r.woba_value) FILTER (WHERE r.in_woba)                               AS woba,
        AVG(r.xwoba_value) FILTER (WHERE r.in_woba)                              AS xwoba,
        AVG((r.events IN ('strikeout', 'strikeout_double_play'))::INT)           AS k_rate,
        AVG((r.events = 'walk')::INT)                                            AS bb_rate
    FROM first_pitch AS f
    JOIN pa_result AS r USING (game_pk, at_bat_number)
    GROUP BY f.after_first_pitch
)

SELECT
    after_first_pitch,
    counts_as_strike,
    pa,
    ROUND(100.0 * pa / SUM(pa) OVER (), 1)                                          AS share_pct,
    ROUND(100.0 * SUM(pa) FILTER (WHERE counts_as_strike) OVER () / SUM(pa) OVER (), 1)
                                                                                    AS first_pitch_strike_pct,
    ROUND(woba, 3)                                                                  AS woba,
    ROUND(xwoba, 3)                                                                 AS xwoba,
    ROUND(100 * k_rate, 1)                                                          AS k_pct,
    ROUND(100 * bb_rate, 1)                                                         AS bb_pct
FROM by_result
ORDER BY CASE after_first_pitch WHEN '0-1' THEN 1 WHEN '1-0' THEN 2 WHEN 'in play on 0-0' THEN 3 ELSE 4 END
