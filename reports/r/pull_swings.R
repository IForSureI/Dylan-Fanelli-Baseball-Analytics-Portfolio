# pull_swings.R -- build the small DuckDB warehouse this study needs.
#
# One table, `swings`: every regular-season swing of one season, one row per pitch,
# straight from Baseball Savant's public Statcast search (CSV), one day per request.
#
# Usage (from the repo root):
#   Rscript reports/r/pull_swings.R 2026 data/r/swings_2026.duckdb
#
# Savant rate-limits, so the script waits between requests, retries a failed day,
# and skips days already in the table (safe to stop and re-run).

suppressPackageStartupMessages({
  library(DBI)
  library(duckdb)
  library(readr)
  library(dplyr)
})

args   <- commandArgs(trailingOnly = TRUE)
season <- if (length(args) >= 1) as.integer(args[1]) else 2026L
db     <- if (length(args) >= 2) args[2] else sprintf("data/r/swings_%d.duckdb", season)
first  <- if (length(args) >= 3) as.Date(args[3]) else as.Date(sprintf("%d-03-20", season))
last   <- if (length(args) >= 4) as.Date(args[4]) else as.Date(sprintf("%d-10-05", season))

# Every pitch result Savant files as a swing. We pull this superset and keep the repo's
# exact swing list (baseball/evaluation/arsenal.py SWINGS) in whiff_regress.R.
SWING_RESULTS <- c("foul", "foul_tip", "hit_into_play", "swinging_strike",
                   "swinging_strike_blocked", "missed_bunt", "foul_bunt", "bunt_foul_tip")

KEEP <- c("game_pk", "game_date", "player_name", "game_year", "game_type", "at_bat_number", "pitch_number",
          "batter", "pitcher", "stand", "p_throws", "pitch_type", "description", "zone")

savant_url <- function(day) {
  paste0(
    "https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&player_type=batter",
    "&hfGT=R%7C",                                   # regular season only
    "&hfSea=", season, "%7C",
    "&game_date_gt=", day, "&game_date_lt=", day,   # one day per request (Savant caps rows per request)
    "&hfPR=", paste0(SWING_RESULTS, collapse = "%7C"), "%7C"
  )
}

pull_day <- function(day, tries = 4) {
  for (i in seq_len(tries)) {
    out <- tryCatch({
      tmp <- tempfile(fileext = ".csv")
      download.file(savant_url(day), tmp, quiet = TRUE,
                    headers = c("User-Agent" = "Mozilla/5.0 (research; one request per day of games)"))
      d <- read_csv(tmp, col_types = cols(.default = col_character()), progress = FALSE)
      unlink(tmp)
      d
    }, error = function(e) NULL)
    if (!is.null(out)) break
    Sys.sleep(5 * i)                                # back off, then retry
  }
  if (is.null(out)) stop("Savant failed 4 times for ", day)
  if (nrow(out) == 0) return(NULL)
  if (nrow(out) >= 25000) warning(day, ": 25,000 rows, the request cap; split this day")
  out |>
    select(any_of(KEEP)) |>
    filter(game_type == "R") |>
    mutate(across(c(game_pk, game_year, at_bat_number, pitch_number, batter, pitcher, zone), as.integer),
           game_date = as.Date(game_date))
}

dir.create(dirname(db), showWarnings = FALSE, recursive = TRUE)
con <- dbConnect(duckdb(), db)
on.exit(dbDisconnect(con, shutdown = TRUE), add = TRUE)

done <- if (dbExistsTable(con, "swings")) {
  as.Date(dbGetQuery(con, "SELECT DISTINCT game_date FROM swings")$game_date)
} else as.Date(character())
if (!dbExistsTable(con, "pulled_days")) dbExecute(con, "CREATE TABLE pulled_days (day DATE, rows INTEGER, pulled_at TIMESTAMP)")
done <- c(done, as.Date(dbGetQuery(con, "SELECT day FROM pulled_days")$day))

for (day in as.character(seq(first, last, by = "day"))) {
  if (as.Date(day) %in% done) next
  d <- pull_day(day)
  n <- if (is.null(d)) 0L else nrow(d)
  if (n > 0) {
    if (!dbExistsTable(con, "swings")) dbCreateTable(con, "swings", d)
    dbAppendTable(con, "swings", d)
  }
  dbExecute(con, "INSERT INTO pulled_days VALUES (?, ?, now())", params = list(as.Date(day), n))
  message(day, ": ", n, " swings")
  Sys.sleep(1.5)                                    # be polite to Savant
}

# One row per pitch: drop any duplicate (game_pk, at_bat_number, pitch_number)
dbExecute(con, "CREATE OR REPLACE TABLE swings AS
                SELECT DISTINCT ON (game_pk, at_bat_number, pitch_number) * FROM swings")
print(dbGetQuery(con, "SELECT COUNT(*) AS swings, COUNT(DISTINCT game_pk) AS games,
                              COUNT(DISTINCT batter) AS batters, MIN(game_date) AS first_day,
                              MAX(game_date) AS last_day FROM swings"))
