# Glossary

The terms used across the reports, in plain words first and the formal version second. Where a report defines a term more narrowly, the report's definition wins.

## Pitches and swings

| Term | Plain words | Formal |
|---|---|---|
| **Whiff rate** | How often a swing misses | Swinging strikes ÷ swings |
| **Chase rate** | How often a hitter swings at a pitch outside the zone | Swings at pitches outside the zone ÷ pitches outside the zone |
| **CSW** | Called strikes plus whiffs, a quick read of how often a pitch wins | (Called strikes + swinging strikes) ÷ pitches |
| **IVB** (induced vertical break) | How much a pitch "rides" or drops compared with a spinless ball | Statcast `pfx_z` × 12, in inches |
| **VAA** (vertical approach angle) | How steeply a pitch comes into the zone | The angle of the pitch's path at the front of home plate |
| **Run value** | How much a pitch changed the expected runs in the inning | Statcast `delta_run_exp` (from the offense's side; a pitcher's runs saved is its negative) |
| **xwOBA** | The quality of contact, from exit velocity and launch angle, on the wOBA scale | Statcast expected wOBA |
| **wOBA** | One number for a hitter's offense, each outcome weighted by its run value | Weighted on-base average |
| **Bat speed, attack angle, swing path tilt** | How fast the bat moves and how it comes through the zone | Statcast bat tracking: bat speed and swing length from 2024; attack angle and swing path from 2025 |
| **Stuff** | How good a pitch is from its physics alone (velocity, movement, release) | A model of whiff or run value from pitch characteristics |

## Reliability and evidence

| Term | Plain words | Formal |
|---|---|---|
| **Split-half reliability** | Does a player's number in one half of his sample predict the other half? | Correlation between random halves, by player |
| **M (regression constant)** | The sample at which signal and noise are equal, so you regress halfway | estimate $`= (n \cdot \text{observed} + M \cdot \text{league}) / (n + M)`$ |
| **ρ year to year** | How much a true skill carries from one season to the next | Between-season correlation ÷ within-season reliability |
| **Out of sample** | Tested on seasons the model never saw | Training and test seasons are named in each report |
| **Placebo test** | A check that should find nothing; if it finds something, the main result is suspect | For example a "lead" placebo using pitches a hitter has not seen yet |
| **Pre-registered** | The test was written down before the data that decides it was looked at | Plans are in the repo with their dates |
| **Benjamini-Hochberg** | A correction for running many tests at once | False discovery rate control |
| **Clustered standard errors** | Honest uncertainty when the same pitcher appears many times | Cluster-robust covariance by pitcher |
| **Brier score** | How far probability calls are from what happened; lower is better, 0.25 is a coin flip | $`\frac{1}{N}\sum_i (p_i - y_i)^2`$ |

## Scouting and roster

| Term | Plain words | Formal |
|---|---|---|
| **20-80 scale** | The scouting grade scale; 50 is major-league average | Grades in steps of 5 |
| **OFP** (overall future potential) | A scout's one-number summary of what a player becomes | 20-80 |
| **WAR** | Wins above a replacement-level player | Baseball-Reference WAR unless a report says otherwise |
| **Service time** | Days on the major-league roster, which set arbitration and free agency | 172 days = one year |
| **Super Two** | Players with 2 to 3 years of service, at least 86 days in the previous season, and in the top 22% of that group by service; they get a fourth arbitration year | CBA Article VI |
| **Arbitration filing** | Each side files a salary; a panel picks one or the other | The club's walk point is where a hearing beats settling |
| **CBT** (luxury tax) | The tax on payrolls above the threshold | Competitive Balance Tax, CBA Article XXIII |
| **Present value** | Future dollars counted in today's terms | Discounted at the rate each memo states |
| **PageRank** | How central a person is in a network, counting who is connected to whom | Neo4j Graph Data Science |
