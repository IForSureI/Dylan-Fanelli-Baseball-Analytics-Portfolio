# whiff_regress.R -- the Reliability Atlas regress step for hitter whiff per swing, in R.
#
# The question: after n swings, how much of a hitter's whiff rate is him, and how far should we
# regress it toward the league before anyone acts on it?
#
# The method is the atlas's (reports/2026-reliability-atlas.md, baseball/evaluation/reliability.py):
#   1. Split each hitter's season by GAME: shuffle his games, deal them alternately into two halves.
#   2. Fill each half, in shuffled game order, until it holds exactly n swings.
#   3. Correlate the two halves across hitters (double-entry / intraclass correlation) = r(n).
#      Repeat over many random splits, pooling the sums before taking the ratio.
#   4. Fit r(n) = n / (n + M) by weighted least squares. M = swings at which r = 0.5.
#   5. Noise per swing sigma2 from the halves; talent spread tau = sqrt(sigma2 / M).
#   6. Regress: estimate = league + w (observed - league), w = n / (n + M);
#      95% interval for his true level = estimate +/- 1.96 tau sqrt(1 - w).
#   Intervals for M come from a bootstrap of hitters (multinomial weights, fixed before the splits).
#
# Usage (repo root):
#   Rscript reports/r/whiff_regress.R 2026 data/r/swings_2026.duckdb
# Or source() it and call the functions one at a time (see reports/r/whiff-regress-r.Rmd).

suppressPackageStartupMessages({
  library(DBI)
  library(duckdb)
  library(dplyr)
  library(tidyr)
  library(purrr)
  library(tibble)
})

# The repo's swing and whiff flags (baseball/evaluation/arsenal.py: SWINGS, WHIFFS)
SWINGS <- c("swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "foul_bunt", "missed_bunt",
            "hit_into_play", "hit_into_play_no_out", "hit_into_play_score")
WHIFFS <- c("swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt")

# The atlas's sample-size grid (reliability.GRID) and its floor of 50 hitters per point
GRID <- c(1, 2, 3, 4, 6, 8, 11, 16, 23, 32, 45, 64, 90, 128, 181, 256, 362, 512, 724, 1024, 1448, 2048, 2896)
MIN_PLAYERS <- 50
Z95 <- qnorm(0.975)

# ------------------------------------------------------------------ 1. data (DuckDB via DBI)

#' One row per swing, in game order, with a 0/1 whiff flag. The flags are made in SQL.
load_swings <- function(db, season) {
  con <- dbConnect(duckdb(), db, read_only = TRUE)
  on.exit(dbDisconnect(con, shutdown = TRUE))
  sql <- sprintf("
    SELECT batter, player_name, game_pk, game_date, at_bat_number, pitch_number, pitch_type,
           CAST(description IN (%s) AS INTEGER) AS whiff
    FROM swings
    WHERE game_year = %d AND game_type = 'R' AND description IN (%s)
    ORDER BY batter, game_date, game_pk, at_bat_number, pitch_number",
    paste0("'", WHIFFS, "'", collapse = ", "), as.integer(season), paste0("'", SWINGS, "'", collapse = ", "))
  as_tibble(dbGetQuery(con, sql))
}

#' The sample sizes this season can support: n where 50+ hitters have at least 2n swings.
usable_grid <- function(swings) {
  tot <- count(swings, batter)$n
  GRID[map_lgl(GRID, \(n) sum(tot >= 2 * n) >= MIN_PLAYERS)]
}

#' Median swings per hitter-game: halves smaller than one game are left out of the fit.
swings_per_game <- function(swings) median(count(swings, batter, game_pk)$n)

# ------------------------------------------------------------------ 2. one random split by game

#' Shuffle each hitter's games and deal them alternately into halves 0 and 1 (a coin flip decides
#' which half gets the first). Returns one row per hitter-game: half and its place in the deal.
deal_games <- function(games) {
  games |>
    mutate(key = runif(n())) |>
    arrange(batter, key) |>
    group_by(batter) |>
    mutate(half = (row_number() - 1 + sample(0:1, 1)) %% 2) |>
    ungroup() |>
    transmute(batter, game_pk, half, pos = row_number())
}

#' Each half's whiff rate on exactly n swings, for every n in grid. Games are added in dealt order,
#' swings within a game in pitch order, so the last game contributes only its first k swings.
#' Returns hitter x n with the two halves a and b (only where both halves reach n).
half_rates <- function(swings, deal, grid) {
  swings |>
    inner_join(deal, by = c("batter", "game_pk")) |>
    arrange(batter, half, pos, at_bat_number, pitch_number) |>
    group_by(batter, half) |>
    mutate(k = row_number(), whiffs = cumsum(whiff)) |>
    ungroup() |>
    filter(k %in% grid) |>
    transmute(batter, n = k, half = paste0("h", half), rate = whiffs / k) |>
    pivot_wider(names_from = half, values_from = rate) |>
    filter(!is.na(h0), !is.na(h1)) |>
    rename(a = h0, b = h1)
}

# ------------------------------------------------------------------ 3. the split-half correlation

#' Sufficient sums for the double-entry correlation at each n, under each set of hitter weights.
#' weights: matrix, one row per weight set (row 1 all ones = the estimate; the rest bootstrap draws),
#' one column per hitter (colnames = batter ids). Returns a long tibble: draw, n, N, Sa, Sq, Sab.
split_sums <- function(halves, weights) {
  halves |>
    group_by(n) |>
    group_modify(\(h, key) {
      W <- weights[, as.character(h$batter), drop = FALSE]
      X <- cbind(N = 1, Sa = h$a + h$b, Sq = h$a^2 + h$b^2, Sab = h$a * h$b)
      as_tibble(W %*% X) |> mutate(draw = seq_len(nrow(W)) - 1L, .before = 1)
    }) |>
    ungroup()
}

#' From pooled sums to r(n): C = covariance of the halves, V = double-entry variance (both times N).
#' r = C / V. Pool the SUMS over splits first, then take the ratio (as the atlas does).
reliability_from_sums <- function(sums, reps) {
  sums |>
    mutate(C = Sab - Sa^2 / (4 * N), V = Sq / 2 - Sa^2 / (4 * N),
           r = C / V, players = N / reps, sigma2_n = (V - C) / N * n)
}

#' One function for steps 2-3: `reps` random game splits, scored under every bootstrap weight set.
run_splits <- function(swings, grid, reps = 200, boot = 100, seed = 2026) {
  set.seed(seed)
  games <- distinct(swings, batter, game_pk)
  players <- sort(unique(swings$batter))
  draws <- rmultinom(boot, length(players), rep(1 / length(players), length(players)))   # players x boot
  weights <- rbind(1, t(draws)); colnames(weights) <- players
  per_split <- map(seq_len(reps), \(r) split_sums(half_rates(swings, deal_games(games), grid), weights))
  bind_rows(per_split) |>
    group_by(draw, n) |>
    summarise(across(c(N, Sa, Sq, Sab), sum), .groups = "drop") |>   # pool the sums over splits
    reliability_from_sums(reps)
}

# ------------------------------------------------------------------ 4-5. the curve, M, sigma2, tau

#' Weighted least squares for M in r(n) = n / (n + M), searched on log M (stats.fit_reliability_constant).
fit_M <- function(n, r, w) {
  ok <- is.finite(n) & is.finite(r) & is.finite(w) & w > 0
  n <- n[ok]; r <- r[ok]; w <- w[ok]
  loss <- \(logM) sum(w * (r - n / (n + exp(logM)))^2)
  exp(optimize(loss, lower = log(1e-3), upper = log(1e7), tol = 1e-10)$minimum)
}

#' Everything the regress step needs from the pooled curve: M with a 95% bootstrap interval,
#' sigma2 (noise per swing) and tau (spread of true talent), plus the curve itself.
fit_curve <- function(rel, per_game) {
  est <- filter(rel, draw == 0)
  keep_n <- est$n[est$players >= MIN_PLAYERS]
  fit_n <- keep_n[keep_n >= max(per_game, 1)]
  if (length(fit_n) < 3) fit_n <- keep_n
  pts <- filter(est, n %in% fit_n)
  M <- fit_M(pts$n, pts$r, pts$players)
  M_boot <- rel |>
    filter(draw > 0, n %in% fit_n) |>
    left_join(select(pts, n, w = players), by = "n") |>
    group_by(draw) |>
    summarise(M = fit_M(n, r, w), .groups = "drop")
  se_logM <- sd(log(M_boot$M))
  sigma2 <- weighted.mean(pts$sigma2_n, pts$players)
  r_se <- rel |> filter(draw > 0) |> group_by(n) |> summarise(se = sd(r), .groups = "drop")
  curve <- est |>
    filter(n %in% keep_n) |>
    left_join(r_se, by = "n") |>
    transmute(n, r, r_lo = r - Z95 * se, r_hi = r + Z95 * se, players,
              r_model = n / (n + M), in_fit = n %in% fit_n)
  list(M = M, M_lo = M * exp(-Z95 * se_logM), M_hi = M * exp(Z95 * se_logM),
       sigma2 = sigma2, tau = sqrt(sigma2 / M), n_fit_min = min(fit_n), per_game = per_game, curve = curve)
}

# ------------------------------------------------------------------ 6. regress (reliability.regress)

#' Shrink an observed rate toward the league mean, with a 95% interval for the player's true level.
#' horizon "season": w = n / (n + M), sd = tau sqrt(1 - w).
#' "next_season": weight rho w, sd = tau sqrt(1 - rho^2 w). "rest_of_season": sd adds drift_sd.
regress <- function(observed, n, league_mean, M, tau, horizon = "season", rho = NA, drift_sd = NA,
                    level = 0.95, rate = TRUE) {
  w <- n / (n + M)
  z <- qnorm(0.5 + level / 2)
  out <- switch(horizon,
    season         = tibble(weight = w, sd = tau * sqrt(1 - w)),
    rest_of_season = tibble(weight = w, sd = sqrt(tau^2 * (1 - w) + drift_sd^2)),
    next_season    = tibble(weight = rho * w, sd = tau * sqrt(1 - rho^2 * w)),
    stop("horizon must be 'season', 'rest_of_season' or 'next_season'"))
  out |>
    mutate(observed = observed, n = n,
           estimate = ifelse(n > 0, league_mean + weight * (observed - league_mean), league_mean),
           lo = estimate - z * sd, hi = estimate + z * sd,
           lo = if (rate) pmax(lo, 0) else lo, hi = if (rate) pmin(hi, 1) else hi,
           .before = 1)
}

#' Real hitters: this season's whiff rate, regressed with this season's constants.
regress_hitters <- function(swings, fit, league_mean, min_swings = 1) {
  swings |>
    group_by(batter, player_name) |>
    summarise(swings = n(), whiffs = sum(whiff), .groups = "drop") |>
    filter(swings >= min_swings) |>
    mutate(observed = whiffs / swings,
           regress(observed, swings, league_mean, fit$M, fit$tau)[c("estimate", "lo", "hi", "weight")])
}

# ------------------------------------------------------------------ main

main <- function(args = commandArgs(trailingOnly = TRUE)) {
  season <- if (length(args) >= 1) as.integer(args[1]) else 2026L
  db <- if (length(args) >= 2) args[2] else sprintf("data/r/swings_%d.duckdb", season)
  reps <- if (length(args) >= 3) as.integer(args[3]) else 200L
  swings <- load_swings(db, season)
  league_mean <- mean(swings$whiff)
  grid <- usable_grid(swings)
  t0 <- Sys.time()
  rel <- run_splits(swings, grid, reps = reps, boot = 100, seed = 2026)
  fit <- fit_curve(rel, swings_per_game(swings))
  message(sprintf("R: %d splits in %.0f s", reps, as.numeric(Sys.time() - t0, units = "secs")))

  examples <- tibble(observed = c(0.400, 0.150, 0.300, 0.350, 0.200, 0.250), n = c(50, 50, 100, 200, 400, 10))
  shipped <- list(M = 55.40049, tau = 0.061794)                    # baseball/evaluation/reliability_params.json
  out <- list(
    season = season, reps = reps, boot = 100, seed = 2026,
    swings = nrow(swings), batters = n_distinct(swings$batter), games = n_distinct(swings$game_pk),
    league_mean = league_mean, per_game = fit$per_game,
    M = fit$M, M_lo = fit$M_lo, M_hi = fit$M_hi, tau = fit$tau, sigma2 = fit$sigma2, n_fit_min = fit$n_fit_min,
    curve = fit$curve,
    regress_shipped = c(list(M = shipped$M, tau = shipped$tau, league_mean = 0.251),
                        as.list(regress(examples$observed, examples$n, 0.251, shipped$M, shipped$tau))),
    regress_fitted = c(list(league_mean = league_mean),
                       as.list(regress(examples$observed, examples$n, league_mean, fit$M, fit$tau)))
  )
  dir.create("reports/r/output", showWarnings = FALSE, recursive = TRUE)
  jsonlite::write_json(out, "reports/r/output/r_whiff.json", auto_unbox = TRUE, digits = NA, pretty = TRUE)
  cat(sprintf("R: M = %.2f (%.2f-%.2f), tau = %.4f, league %.4f, %s swings, %d batters\n",
              fit$M, fit$M_lo, fit$M_hi, fit$tau, league_mean, format(nrow(swings), big.mark = ","),
              n_distinct(swings$batter)))
  invisible(out)
}

if (sys.nframe() == 0L) main()
