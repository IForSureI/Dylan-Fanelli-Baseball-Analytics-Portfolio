# Tarik Skubal (DET, LHP): 2025 arsenal read

*Written 2026-10-12 · Dylan Fanelli · Data: Statcast via Baseball Savant (pybaseball), pulled 2026-10-12*

![Skubal 2025 pitch movement](figures/2025-skubal-movement.png)

## The read

- **The changeup is the best pitch in the arsenal and the one everything else is built around.** It's his most-used pitch (31.4%), his finisher with two strikes (39.4% of two-strike pitches), and the best of his four main pitches on every measure in the table.
- **His velocity carries both fastballs.** The four-seamer (97.6 mph) and sinker (97.3) get above-average whiffs for their types and set up the changeup. When hitters do connect with the four-seamer, though, they do the most damage on it of any pitch he throws.
- **He changes his pitch mix by batter handedness.** Against left-handed hitters he leads with the sinker (42.3%); against right-handers he leads with the changeup and four-seamer (65.4% combined).
- **The slider is the soft spot.** Its whiff and chase rates are below the usual range for sliders.

## Arsenal (2025 regular season, 2,849 pitches, 31 starts)

| Pitch | Usage | Velo | IVB (in) | Arm-side HB (in) | Whiff% | CSW% | Chase% | xwOBA on contact | Runs saved /100 |
|---|---|---|---|---|---|---|---|---|---|
| Changeup | 31.4% | 88.0 | 6.5 | 15.0 | **46.8** | **38.8** | **48.5** | **.312** | **2.83** |
| 4-Seam | 29.3% | 97.6 | 17.0 | 3.5 | 28.7 | 28.0 | 30.4 | .393 | 1.47 |
| Sinker | 23.9% | 97.3 | 13.6 | 13.1 | 18.3 | 32.3 | 21.4 | .382 | 1.27 |
| Slider | 12.5% | 90.0 | 4.8 | −3.2 | 25.5 | 33.4 | 20.3 | .342 | 1.59 |
| Curveball | 2.8% | 81.2 | −5.4 | −4.9 | 35.7 | 35.4 | 36.0 | n = 6 BIP | −0.52 |

Whole arsenal: 33.3% CSW, 35.2% chase, 33.0% hard-hit on balls in play.

## Evidence, pitch by pitch

**Changeup**
- Typical changeup whiff rate is about 31% per swing. His is 46.8% (252 of 538 swings; 95% interval 42.7–51.1%), so even the low end of the interval is well above average.
- The shape fits what a changeup is supposed to do against his fastball:
  - 9.6 mph slower than the four-seamer (the usual target is 8–12)
  - 10.5 inches less rise (the target is at least about 6)
  - 11.5 inches more arm-side run
- Hitters chase it 48.5% of the time even though only 43.8% of changeups land in the zone. It gets swings without having to be a strike.

**Four-seamer**
- 28.7% whiff rate against about 21% for four-seamers overall. The 17.0 inches of rise and 97.6 mph average (102.6 max) drive it.
- It gives up the most damage of anything he throws: .393 xwOBA on contact and 12.1% barrels. That's the price of a pitch he lives in the zone with (57.5% zone rate).

**Sinker**
- His strike pitch: 66.4% zone rate and a 23.2% called-strike rate, with the highest usage on the first pitch of an at-bat (36.1% of 0-0 pitches).
- Whiff rate is 18.3% against about 13% for sinkers overall. Its job is getting strikes, mainly against left-handers.

**Slider**
- Whiff rate is 25.5% against about 34% for sliders overall, and chase rate is 20.3%. Of the pitch types he throws regularly, it gets the fewest misses and the fewest chases.
- It still saves runs (1.59 per 100). Hitters take it for strikes (21.9% called-strike rate), and contact against it is softer than against his fastballs (.342 xwOBA on contact). Its role is a strike-getter more than a putaway pitch.

## Postseason (3 starts, 303 pitches)
- His four-seamer averaged 98.7 mph, 1.2 mph above his regular-season average.
- The changeup got whiffs on 31 of 44 swings (70.5%; 95% interval 55.8–81.8%). The interval sits entirely above the regular-season rate, so the jump is probably more than noise. Still, three starts is too few to call it a new level.

## What would change this read
- A second season with a lower changeup whiff rate would mean 2025 was the high point of a great pitch, not its true level. Next step: pull 2024 for comparison.
- Pitch labels come from Statcast. Three pitches on 2025-04-27 were labeled splitters, and their speed and movement match his changeup, so they're most likely mislabeled changeups. They fall under the 20-pitch floor and are left out of the table.

## Method
- Regular season only (`game_type = 'R'`). The raw pull also contains 252 spring training pitches, 84 of them with no pitch type recorded, and they're excluded.
- Rates are computed from totals summed by pitch type. Pitch types with fewer than 20 pitches are left out.
- Chase% uses Statcast zones 11–14 as "outside the zone." League reference values are approximate.
- Reproduce with:
  ```bash
  uv run bb pull skubal tarik 2025
  uv run bb arsenal skubal tarik 2025
  uv run bb arsenal skubal tarik 2025 --phase postseason
  ```
