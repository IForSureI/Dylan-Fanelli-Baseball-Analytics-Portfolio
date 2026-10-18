-- reliever_rest
-- Question: How often is each reliever used on zero, one or two days' rest, and does his fastball lose
--           velocity when he is?
-- Inputs:
--   $season          season, e.g. 2026 (required)
--   $min_relief_apps fewest relief appearances for a pitcher to be listed (default 30)
-- Output: one row per reliever, most zero-rest outings first
--   pitcher           MLBAM id
--   name              from the people register (NULL if missing)
--   relief_apps       relief appearances
--   apps_0d           relief appearances on zero days' rest (he pitched the day before)
--   apps_1d           relief appearances on one day's rest
--   apps_2d           relief appearances on two days' rest
--   apps_3plus        relief appearances on three or more days' rest
--   fb_type           his primary fastball (most-thrown of FF, SI, FC in relief)
--   velo_3plus        mean fastball velocity in outings on 3+ days' rest (the rested baseline, mph)
--   velo_chg_0d       zero-rest outings minus the rested baseline (mph)
--   velo_chg_1d       one-day-rest outings minus the rested baseline (mph)
--   velo_chg_2d       two-day-rest outings minus the rested baseline (mph)
-- Definitions:
--   appearance      a game he threw at least one pitch in. Relief = he did not throw his team's first
--                   pitch of the game.
--   days' rest      calendar days between this appearance and his previous one (starts included) minus
--                   one, so back-to-back days = 0. Two games on the same day also count as 0. His first
--                   appearance of the season has no rest value and sits in no bucket.
--   outing velo     mean speed of his primary fastball in that outing; bucket velo is the mean of outing
--                   means, so every outing counts once (as in baseball/evaluation/reliever.py workload()).
--   Velocity changes on a handful of zero-rest outings are noisy; read them next to apps_0d.
--   Regular season only; automatic_ball / automatic_strike dropped (no pitch was thrown).

WITH season_pitches AS (
    SELECT
        game_pk, CAST(game_date AS DATE) AS game_date, at_bat_number, pitch_number, pitcher, pitch_type,
        release_speed, description,
        CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END   AS fld_team
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
),

first_pitchers AS (
    -- each team's first pitcher of each game: the starter
    SELECT game_pk, pitcher
    FROM season_pitches
    QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, fld_team ORDER BY at_bat_number, pitch_number) = 1
),

appearances AS (
    -- grain: pitcher x game
    SELECT
        s.pitcher,
        s.game_pk,
        MIN(s.game_date)                    AS game_date,
        BOOL_AND(f.pitcher IS NULL)         AS is_relief
    FROM season_pitches AS s
    LEFT JOIN first_pitchers AS f ON f.game_pk = s.game_pk AND f.pitcher = s.pitcher
    WHERE s.description NOT IN ('automatic_ball', 'automatic_strike')
    GROUP BY s.pitcher, s.game_pk
),

with_lag AS (
    -- LAG looks one appearance back in his own season (NULL on his first appearance)
    SELECT
        *,
        LAG(game_date) OVER (PARTITION BY pitcher ORDER BY game_date, game_pk)   AS prev_date
    FROM appearances
),

with_rest AS (
    -- the CASE keeps the debut NULL (DuckDB's GREATEST skips NULLs); GREATEST keeps doubleheaders at 0
    SELECT
        *,
        CASE WHEN prev_date IS NOT NULL
             THEN GREATEST(DATE_DIFF('day', prev_date, game_date) - 1, 0) END    AS days_rest
    FROM with_lag
),

primary_fb AS (
    -- his most-thrown fastball type in relief
    SELECT s.pitcher, s.pitch_type
    FROM season_pitches AS s
    JOIN with_rest AS w ON w.pitcher = s.pitcher AND w.game_pk = s.game_pk AND w.is_relief
    WHERE s.pitch_type IN ('FF', 'SI', 'FC')
    GROUP BY s.pitcher, s.pitch_type
    QUALIFY ROW_NUMBER() OVER (PARTITION BY s.pitcher ORDER BY COUNT(*) DESC, s.pitch_type) = 1
),

outing_velo AS (
    -- grain: one row per relief outing with his primary fastball
    SELECT
        w.pitcher,
        w.game_pk,
        w.days_rest,
        AVG(s.release_speed) AS fb_velo
    FROM with_rest AS w
    JOIN primary_fb AS p ON p.pitcher = w.pitcher
    JOIN season_pitches AS s
      ON s.pitcher = w.pitcher AND s.game_pk = w.game_pk AND s.pitch_type = p.pitch_type
    WHERE w.is_relief
    GROUP BY w.pitcher, w.game_pk, w.days_rest
),

usage AS (
    SELECT
        pitcher,
        COUNT(*)                                        AS relief_apps,
        COUNT(*) FILTER (WHERE days_rest = 0)           AS apps_0d,
        COUNT(*) FILTER (WHERE days_rest = 1)           AS apps_1d,
        COUNT(*) FILTER (WHERE days_rest = 2)           AS apps_2d,
        COUNT(*) FILTER (WHERE days_rest >= 3)          AS apps_3plus
    FROM with_rest
    WHERE is_relief
    GROUP BY pitcher
    HAVING COUNT(*) >= $min_relief_apps
),

velo AS (
    SELECT
        pitcher,
        AVG(fb_velo) FILTER (WHERE days_rest >= 3)      AS v3,
        AVG(fb_velo) FILTER (WHERE days_rest = 0)       AS v0,
        AVG(fb_velo) FILTER (WHERE days_rest = 1)       AS v1,
        AVG(fb_velo) FILTER (WHERE days_rest = 2)       AS v2
    FROM outing_velo
    GROUP BY pitcher
)

SELECT
    u.pitcher,
    pe.name,
    u.relief_apps,
    u.apps_0d,
    u.apps_1d,
    u.apps_2d,
    u.apps_3plus,
    p.pitch_type                    AS fb_type,
    ROUND(v.v3, 1)                  AS velo_3plus,
    ROUND(v.v0 - v.v3, 1) + 0.0     AS velo_chg_0d,     -- + 0.0 turns a rounded -0.0 into 0.0
    ROUND(v.v1 - v.v3, 1) + 0.0     AS velo_chg_1d,
    ROUND(v.v2 - v.v3, 1) + 0.0     AS velo_chg_2d
FROM usage AS u
LEFT JOIN primary_fb AS p ON p.pitcher = u.pitcher
LEFT JOIN velo AS v ON v.pitcher = u.pitcher
LEFT JOIN people AS pe ON pe.key_mlbam = u.pitcher
ORDER BY u.apps_0d DESC, u.relief_apps DESC, u.pitcher
