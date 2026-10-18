-- velocity_by_inning
-- Question: Does this starter's fastball hold its velocity deep into his starts, or does it fade?
-- Inputs:
--   $pitcher      MLBAM pitcher id (required)
--   $season       season, e.g. 2026 (required)
--   $pitch_type   pitch to track (default NULL = his most-thrown of FF, SI, FC in his starts)
-- Output: one row per inning he pitched in a start
--   inning               inning of the game
--   pitch_type           the pitch tracked
--   starts               starts in which he threw that pitch in that inning
--   pitches              pitches of that type in that inning
--   velo                 mean release speed (mph)
--   velo_vs_1st          velo minus his 1st-inning velo (mph; NULL if he never threw it in the 1st)
--   max_velo             fastest pitch of that type in that inning (mph)
--   avg_pitch_of_game    mean pitch count (all his pitch types) at the time of those pitches
-- Definitions:
--   start    he threw his team's first pitch of the game. The fielding team is the home team in the top
--            of the inning and the away team in the bottom.
--   Later innings only include starts in which he lasted that long, which leans toward his better days;
--   read a late-inning drop as a floor on the fade.
--   Regular season only; automatic_ball / automatic_strike dropped (no pitch was thrown).

WITH season_pitches AS (
    SELECT
        game_pk, inning, at_bat_number, pitch_number, pitcher, pitch_type, release_speed, description,
        CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END   AS fld_team
    FROM pitches
    WHERE game_type = 'R'
      AND game_year = $season
),

starts AS (
    -- the first pitch of each game for each fielding team: ROW_NUMBER() picks it, QUALIFY keeps it
    SELECT game_pk, pitcher
    FROM season_pitches
    QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, fld_team ORDER BY at_bat_number, pitch_number) = 1
),

his_starts AS (
    -- grain: one row per pitch he threw in his starts, numbered within the game
    SELECT
        s.game_pk, s.inning, s.pitch_type, s.release_speed,
        ROW_NUMBER() OVER (PARTITION BY s.game_pk ORDER BY s.at_bat_number, s.pitch_number) AS pitch_of_game
    FROM season_pitches AS s
    JOIN starts AS st ON st.game_pk = s.game_pk AND st.pitcher = s.pitcher
    WHERE s.pitcher = $pitcher
      AND s.description NOT IN ('automatic_ball', 'automatic_strike')
),

tracked_pitch AS (
    -- the pitch asked for, or his primary fastball
    SELECT COALESCE(
        $pitch_type::VARCHAR,
        (SELECT pitch_type
         FROM his_starts
         WHERE pitch_type IN ('FF', 'SI', 'FC')
         GROUP BY pitch_type
         ORDER BY COUNT(*) DESC, pitch_type
         LIMIT 1)
    ) AS pitch_type
),

by_inning AS (
    SELECT
        h.inning,
        h.pitch_type,
        COUNT(DISTINCT h.game_pk)      AS starts,
        COUNT(*)                       AS pitches,
        AVG(h.release_speed)           AS velo,
        MAX(h.release_speed)           AS max_velo,
        AVG(h.pitch_of_game)           AS avg_pitch_of_game
    FROM his_starts AS h
    JOIN tracked_pitch AS t ON t.pitch_type = h.pitch_type
    GROUP BY h.inning, h.pitch_type
)

SELECT
    inning,
    pitch_type,
    starts,
    pitches,
    ROUND(velo, 1)                                                     AS velo,
    ROUND(velo - (SELECT velo FROM by_inning WHERE inning = 1), 1) + 0.0 AS velo_vs_1st,
    ROUND(max_velo, 1)                                                 AS max_velo,
    ROUND(avg_pitch_of_game, 0)                                        AS avg_pitch_of_game
FROM by_inning
ORDER BY inning
