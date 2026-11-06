# Report standard

Every report in this portfolio follows the same standard, so a GM, a coach or an analyst finds the answer in under a minute and the evidence in under five. The format follows how front offices read: a decision memo's answer first, then the evidence, with pre-registered studies and their placebo tests shown in full.

## Every study report opens the same way

The prediction log is the exception: `bb predictions render` writes it from `predictions/2027.yaml`.
1. **Navigation** back to the portfolio and to the previous and next report.
2. **The title**, then badges: status, data, who in a club uses it, and the methods.
3. **At a glance:** the question, the answer, and what a club does with it.
4. **The work:** the report's own sections (the answer first, then method, validation, limits).
5. **Footer:** navigation and how to cite.

The header, the at-a-glance box and the footer are stamped by `docs/build_pages.py`, between marker comments, so they can be refreshed without touching the report's text. `tests/test_portfolio_pages.py` fails if a report is missing them or if a link or image on the front page is broken.

## The analysis rules (unchanged)
- **Out of sample by default.** Forecasts are tested on seasons their parameters never saw, against a regressed baseline.
- **One evidence standard.** Confirmed means p < 0.05 with enough sample; many tests get a Benjamini-Hochberg correction; "no effect" is claimed only when the interval rules out effects that matter.
- **Separate review.** Every finished report gets a review pass that checks each number against the saved outputs; [LOG.md](../LOG.md) records what each review changed.
- **Public data only.** No club's data is in this repository.

## Adding a report
1. Write `reports/<year>-<slug>.md` with its figure in `reports/figures/`.
2. Add an entry to `PAGES` in `docs/build_pages.py` (question, answer, what a club does with it, photo, badges) and a row to the README's research table.
3. Run `uv run python docs/build_pages.py` and `uv run pytest`.
