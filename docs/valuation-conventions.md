# Valuation conventions

One page for every price of a win and the discount rate used in this portfolio, where each is used, and why. Added 2026-11-14.

## The discount rate: one convention
- **The rule:** future dollars are discounted 10% a year, and the price of a win grows 3% a year. Net of growth that is about 7% a year (1.10 / 1.03 = 1.068).
- **Where it lives:** `DISCOUNT = 0.10` and `DPW_GROWTH = 0.03` in `baseball/roster/money.py`. The reliever pricing, the arbitration carry cost and the Torres price all import those two numbers.
- **So "10%" and "7%" in the reports are the same convention.** 10% is the rate on dollars. 7% is the rate on wins once their price grows.
- **Source:** FanGraphs' 2026 method. It is an assumption, and every memo's sensitivity section says so.

## The price of a win: four numbers, four jobs

| Price | Dollars | Used for | Why this one | Code |
|---|---|---|---|---|
| Tiered: $12.84M at 2+ WAR, $8.51M at 1-2, $6.74M below 1 | 2026 | The Skenes extension | FanGraphs' study (Ben Clemens, Feb. 24, 2026) reports what the market paid by projected-WAR band. Skenes projects above 2 WAR on his base path. | `DPW_TIERS_2026` in `baseball/roster/money.py` |
| Flat: $11.23M | 2026 | The cross-check on Skenes and on Torres ($11.57M once grown to 2027) | The same study's one-rate figure. A win is priced the same for every player. | `DPW_FLAT_2026` |
| Own fit: $11.66M | 2027 | The Torres evaluation | My fit to 46 comparable free-agent contracts. It sits within 1% of the flat rate grown to 2027. | `PRICE_OF_WIN_2027` in `baseball/evaluation/swing_decisions.py` |
| Reliever line: $0.93M plus $9.60M per projected win | 2027 | The bullpen memo | Relievers are paid on their own line. This one is fit to the 21 relief signings of 2025-26. It is a market-clearing price, not a club's value of a win. | `market_line()` in `baseball/roster/acquisition.py` |

## Do they agree?
- **Two agree.** The flat rate grown to 2027 ($11.57M) and my own fit ($11.66M) are within 1%.
- **The tiers are the outlier, on purpose.** They pay more per win for stars and less for role players. That is a claim about the market, and it matters:
  - **Skenes:** the walk-away is about $215M on the tiers and about $200M on the flat rate (the roster and CBA memo's Nov. 14 check).
  - **Torres:** two years are worth $29.6M at one rate and $22.2M on the tiers, because 1.50 WAR prices in the 1-2 band.
- **The reliever slope is lower ($9.60M)** and has a wide error (standard error $3.58M, 21 signings). It is not evidence that a reliever's win is worth less. It is what that market paid.
- **None of these is a club's own value of a win.** A club near a playoff spot should pay more than the market rate. No report here estimates that curve. Where a memo says "value," it means value at the market's price.

## What would make this one number
- A single price fit across all free agents with a term for projected WAR, tested for the star premium directly. Not done. It needs a contract table with projections at signing for every free agent of 2022-26, which this repo has only for the 21 relief signings and the 46 contracts behind the Torres rate.
