-- velocity_drop_between_starts
-- Question: For each starter, what was the biggest one-start drop in fastball velocity this season,
--           and did it come back the next time out?
-- Inputs:
--   $season       season, e.g. 2026 (required)
--   $min_starts   fewest starts for a pitcher to be listed (default 10)
--   $min_fb       fewest primary fastballs in a start for that start to count (default 10)
-- Output: one row per starter, biggest drop first
--   pitcher          MLBAM id
--   name             from the people register (NULL if missing)
--   fb_type          his primary fastball (most-thrown of FF, SI, FC in his starts)
--   starts           starts that count (enough fastballs)
--   starts_skipped   starts with fewer than $min_fb primary fastballs (kept in the sequence, never compared)
--   season_velo      mean of his start-level fastball velocities (mph)
--   game_date        date of the start with the biggest drop
--   prev_game_date   date of the start before it
--   prev_velo        fastball velocity in the start before (mph)
--   velo             fastball velocity in the drop start (mph)
--   drop_mph         prev_velo - velo (positive = slower)
--   next_velo        fastball velocity in the start after (NULL if it was his last, or it had too few
--                    fastballs to count)
-- Definitions:
--   start         he threw his team's first pitch of the game.
--   start velo    mean release speed of his primary fastball in that start.
--   The window function LAG() reads the previous start's velo onto each start, LEAD() the next one,
--   and ROW_NUMBER() ranks each pitcher's drops so QUALIFY can keep the largest.
--   LAG and LEAD run over every start, short ones included, and the $min_fb floor is applied afterwards.
--   A drop is measured only between two adjacent starts that both count, so a short start (often the
--   injury-shortened one you most want to see) never makes two non-adjacent starts look adjacent.
--   A one-start drop of 1 mph is within normal start-to-start noise for many pitchers; 2+ mph is the
--   usual threshold to look at video and health notes.
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

starts AS (
    SELECT game_pk, pitcher
    FROM season_pitches
    QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, fld_team ORDER BY at_bat_number, pitch_number) = 1
),

start_pitches AS (
    -- grain: one row per pitch a starter threw in his starts
    SELECT s.*
    FROM season_pitches AS s
    JOIN starts AS st ON st.game_pk = s.game_pk AND st.pitcher = s.pitcher
    WHERE s.description NOT IN ('automatic_ball', 'automatic_strike')
),

primary_fb AS (
    SELECT pitcher, pitch_type
    FROM start_pitches
    WHERE pitch_type IN ('FF', 'SI', 'FC')
    GROUP BY pitcher, pitch_type
    QUALIFY ROW_NUMBER() OVER (PARTITION BY pitcher ORDER BY COUNT(*) DESC, pitch_type) = 1
),

start_velo AS (
    -- grain: one row per start, short ones included (fb_n = 0 when he threw no primary fastballs)
    SELECT
        st.pitcher,
        p.pitch_type                                                    AS fb_type,
        st.game_pk,
        MIN(sp.game_date)                                               AS game_date,
        COUNT(*) FILTER (WHERE sp.pitch_type = p.pitch_type)            AS fb_n,
        AVG(sp.release_speed) FILTER (WHERE sp.pitch_type = p.pitch_type) AS velo
    FROM starts AS st
    JOIN primary_fb AS p ON p.pitcher = st.pitcher
    JOIN start_pitches AS sp ON sp.game_pk = st.game_pk AND sp.pitcher = st.pitcher
    GROUP BY st.pitcher, p.pitch_type, st.game_pk
),

sequenced AS (
    -- each start next to the one before and the one after, over every start
    SELECT
        *,
        fb_n >= $min_fb                         AS counts,
        LAG(velo)       OVER w                  AS prev_velo,
        LAG(fb_n)       OVER w                  AS prev_fb_n,
        LAG(game_date)  OVER w                  AS prev_game_date,
        LEAD(velo)      OVER w                  AS lead_velo,
        LEAD(fb_n)      OVER w                  AS next_fb_n,
        COUNT(*) FILTER (WHERE fb_n >= $min_fb) OVER (PARTITION BY pitcher) AS starts,
        COUNT(*) FILTER (WHERE fb_n <  $min_fb) OVER (PARTITION BY pitcher) AS starts_skipped,
        AVG(velo) FILTER (WHERE fb_n >= $min_fb) OVER (PARTITION BY pitcher) AS season_velo
    FROM start_velo
    WINDOW w AS (PARTITION BY pitcher ORDER BY game_date, game_pk)
),

biggest AS (
    SELECT
        *,
        prev_velo - velo                                                AS drop_mph,
        CASE WHEN next_fb_n >= $min_fb THEN lead_velo END               AS next_velo
    FROM sequenced
    WHERE counts
      AND prev_fb_n >= $min_fb
      AND velo IS NOT NULL AND prev_velo IS NOT NULL
      AND starts >= $min_starts
    QUALIFY ROW_NUMBER() OVER (PARTITION BY pitcher ORDER BY prev_velo - velo DESC, game_date) = 1
)

SELECT
    b.pitcher,
    pe.name,
    b.fb_type,
    b.starts,
    b.starts_skipped,
    ROUND(b.season_velo, 1)     AS season_velo,
    b.game_date,
    b.prev_game_date,
    ROUND(b.prev_velo, 1)       AS prev_velo,
    ROUND(b.velo, 1)            AS velo,
    ROUND(b.drop_mph, 1) + 0.0  AS drop_mph,
    ROUND(b.next_velo, 1)       AS next_velo
FROM biggest AS b
LEFT JOIN people AS pe ON pe.key_mlbam = b.pitcher
ORDER BY b.drop_mph DESC, b.pitcher
