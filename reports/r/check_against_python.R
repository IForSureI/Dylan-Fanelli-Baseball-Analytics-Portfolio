# check_against_python.R -- does the R rebuild agree with the repo's Python atlas code?
#
# Run after both sides have written their results (repo root):
#   uv run python reports/r/python_reference.py 2026 data/r/swings_2026.duckdb
#   Rscript reports/r/whiff_regress.R 2026 data/r/swings_2026.duckdb
#   Rscript reports/r/check_against_python.R 2026 data/r/swings_2026.duckdb
#
# Four checks, from strictest to loosest:
#   A. Same splits, same data      -> r(n) must agree to 1e-10 (pure arithmetic).
#   B. Same curve points, two fits -> M must agree to 1e-6 relative (R's optimize vs Python's golden section).
#   C. Same constants, regress()   -> estimates and intervals must agree to 1e-9.
#   D. Independent random splits   -> M, tau, r(n) and regressed estimates agree within Monte Carlo
#      tolerance (each side draws its own 200 splits with its own random number generator).
# Writes reports/r/output/check-results.md and stops with an error if any check fails.

suppressPackageStartupMessages({ library(testthat); library(jsonlite) })
source("reports/r/whiff_regress.R")

args <- commandArgs(trailingOnly = TRUE)
season <- if (length(args) >= 1) as.integer(args[1]) else 2026L
db <- if (length(args) >= 2) args[2] else sprintf("data/r/swings_%d.duckdb", season)

py <- read_json("reports/r/output/python_whiff.json", simplifyVector = TRUE)
rr <- read_json("reports/r/output/r_whiff.json", simplifyVector = TRUE)

# Tolerances for check D (independent splits), set from how much Python disagrees WITH ITSELF when only
# the random seed changes (2026 data, 200 splits; seeds 1-10 and 2026): M ranged 54.16-54.79 (1.2%),
# r(64) ranged 0.528-0.533, tau moved 0.2%. Each bar below is about 1.5x that Python-vs-Python range.
# The M interval ends also depend on which 100 bootstrap samples of hitters were drawn, so they get 5%.
TOL <- list(M_rel = 0.015, M_ci_rel = 0.05, tau_rel = 0.01, r_abs = 0.0075, est_abs = 0.001, ci_abs = 0.002)

rows <- list()
log_row <- function(check, quantity, python, r, tolerance) {
  diff <- r - python
  rows[[length(rows) + 1]] <<- tibble(check, quantity, python, r, diff, tolerance, pass = abs(diff) <= tolerance)
}

# ---- A. the same 20 splits, scored in R
swings <- load_swings(db, season)
shared <- readr::read_csv(sprintf("data/r/shared_splits_%d.csv", season), show_col_types = FALSE)
grid <- py$shared_splits$grid
ones <- matrix(1, 1, n_distinct(swings$batter), dimnames = list(NULL, sort(unique(swings$batter))))
sums_A <- shared |>
  group_split(split) |>
  map(\(d) split_sums(half_rates(swings, select(d, batter, game_pk, half, pos), grid), ones)) |>
  bind_rows() |>
  group_by(draw, n) |>
  summarise(across(c(N, Sa, Sq, Sab), sum), .groups = "drop") |>
  reliability_from_sums(py$shared_splits$k)
A <- inner_join(py$shared_splits$curve, sums_A, by = "n", suffix = c("_py", "_r"))
for (i in seq_len(nrow(A))) log_row("A same splits", sprintf("r(%d)", A$n[i]), A$r_py[i], A$r_r[i], 1e-10)
log_row("A same splits", "hitter-halves counted (all n)", sum(A$players_py), sum(A$players_r), 1e-9)

# ---- B. R's fit on Python's curve points
pc <- py$curve |> filter(in_fit)
M_B <- fit_M(pc$n, pc$r, pc$entities)
log_row("B same points", "M", py$M, M_B, 1e-6 * py$M)

# ---- C. regress() with the same constants (the shipped atlas constants)
for (k in c("estimate", "lo", "hi", "sd", "weight")) {
  for (i in seq_along(py$regress_shipped[[k]])) {
    log_row("C same constants", sprintf("%s, %.0f%% in %d", k, 100 * py$examples$observed[i], py$examples$n[i]),
            py$regress_shipped[[k]][i], rr$regress_shipped[[k]][i], 1e-9)
  }
}

# ---- D. independent splits
log_row("D independent", "swings in the data", py$swings, rr$swings, 0)
log_row("D independent", "league whiff rate", py$league_mean, rr$league_mean, 1e-12)
log_row("D independent", "M (swings)", py$M, rr$M, TOL$M_rel * py$M)
log_row("D independent", "M, 95% low", py$M_lo, rr$M_lo, TOL$M_ci_rel * py$M_lo)
log_row("D independent", "M, 95% high", py$M_hi, rr$M_hi, TOL$M_ci_rel * py$M_hi)
log_row("D independent", "tau (talent SD)", py$tau, rr$tau, TOL$tau_rel * py$tau)
D <- inner_join(py$curve, rr$curve, by = "n", suffix = c("_py", "_r")) |> filter(n %in% c(16, 32, 64, 128, 256))
for (i in seq_len(nrow(D))) log_row("D independent", sprintf("r(%d)", D$n[i]), D$r_py[i], D$r_r[i], TOL$r_abs)
for (k in c("estimate", "lo", "hi")) {
  for (i in seq_along(py$regress_fitted[[k]])) {
    log_row("D independent", sprintf("%s, %.0f%% in %d", k, 100 * py$examples$observed[i], py$examples$n[i]),
            py$regress_fitted[[k]][i], rr$regress_fitted[[k]][i], if (k == "estimate") TOL$est_abs else TOL$ci_abs)
  }
}

res <- bind_rows(rows)

# ---- the report
fmt <- \(x) ifelse(abs(x) >= 100, sprintf("%.1f", x), ifelse(abs(x) >= 1, sprintf("%.3f", x), sprintf("%.6f", x)))
lines <- c(
  sprintf("# R vs Python check: hitter whiff per swing, %d regular season", season), "",
  sprintf("Run %s. Data: %s swings, %d batters, %d games (Baseball Savant, pulled with reports/r/pull_swings.R).",
          format(Sys.Date()), format(py$swings, big.mark = ","), py$batters, py$games), "",
  sprintf("**Result: %d of %d checks pass.**", sum(res$pass), nrow(res)), "",
  sprintf("- Python (repo code, seed %d, %d splits): M = %.1f swings (95%%: %.1f-%.1f), tau = %.4f", py$seed, py$reps, py$M, py$M_lo, py$M_hi, py$tau),
  sprintf("- R (independent splits, seed %d, %d splits): M = %.1f swings (95%%: %.1f-%.1f), tau = %.4f", rr$seed, rr$reps, rr$M, rr$M_lo, rr$M_hi, rr$tau),
  sprintf("- Atlas (2024-26 pooled, shipped): M = 55.4 (49.0-62.7). This season alone is %s that interval.",
          ifelse(rr$M >= 48.982859 & rr$M <= 62.658945, "inside", "outside")), "",
  "Tolerances: A, B and C are exact (rounding only). D compares two independent sets of random splits:",
  sprintf("M within %.1f%% (its interval ends within %.0f%%), tau within %.0f%%, r(n) within %.4f, regressed estimates within %.1f point, interval ends within %.1f points.",
          100 * TOL$M_rel, 100 * TOL$M_ci_rel, 100 * TOL$tau_rel, TOL$r_abs, 100 * TOL$est_abs, 100 * TOL$ci_abs),
  "These bars are about 1.5x how far Python moves from itself when only the random seed changes.", "",
  "| Check | Quantity | Python | R | R - Python | Tolerance | Pass |", "|---|---|---|---|---|---|---|",
  sprintf("| %s | %s | %s | %s | %.2e | %.1e | %s |", res$check, res$quantity, fmt(res$python), fmt(res$r),
          res$diff, res$tolerance, ifelse(res$pass, "yes", "**NO**"))
)
writeLines(lines, "reports/r/output/check-results.md")
cat(lines[1:14], sep = "\n")

test_that("R agrees with the Python atlas code", {
  failed <- filter(res, !pass)
  expect_equal(nrow(failed), 0, info = paste(failed$check, failed$quantity, collapse = "; "))
})
