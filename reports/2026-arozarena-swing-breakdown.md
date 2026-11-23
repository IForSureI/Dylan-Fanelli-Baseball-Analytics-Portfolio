<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Catcher framing](2026-catcher-framing.md) &nbsp;|&nbsp; [Draft analytics →](2026-mlb-draft-analytics.md)</sub>
<!-- /portfolio:header -->

# Randy Arozarena, frame by frame: is the 2026 power real?

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-reviewed-1d5c3f" alt="status: reviewed"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-Pro%20personnel%20and%20hitting-6b6b6b" alt="for: Pro personnel and hitting"> <img src="https://img.shields.io/badge/method-video,%20frame%20by%20frame-b4532a" alt="method: video, frame by frame"> <img src="https://img.shields.io/badge/method-pose%20estimation-b4532a" alt="method: pose estimation"> <img src="https://img.shields.io/badge/method-bat%20tracking-b4532a" alt="method: bat tracking"></p>

**At a glance**

- **The question:** Is Randy Arozarena's 2026 power real, and did his swing change?
- **The answer:** Not from the swing: measured frame by frame on MLB's clips of his home runs, his 2026 swing has the same timing and sequence as 2024. His swings got slower, shorter and flatter and his home runs softer while his ISO rose. Bat tracking adds nothing to ISO and hard-hit exit velocity as a forecast, and that model says a .181 ISO in 2027.
- **For a club:** Video used the way a front office should: to rule a mechanical change in or out, with the camera's limits stated.
<!-- /portfolio:glance -->

Dylan Fanelli. Data: MLB's highlight clips of all 73 of his 2024-26 home runs (MLB Stats API content feed, 1280x720 at 59.94 frames a second), Statcast pitch and bat-tracking data 2024-26; all pulled Nov. 23, 2026.

**The question:** Arozarena posted a 151 wRC+ in 2026 and is one of this winter's top free agents. My [prediction log](2027-prediction-log.md) says his 2027 wRC+ will be 130 or lower (call 6, 0.70), and my [market board](2027-market-board.md) has him at $33.0M a year against MLB Trade Rumors' $25.0M. Did something in his swing change to earn the 2026 numbers?

**The answer: no, not in the swing that hit the home runs.**
- **The video:** frame by frame from the center-field camera, his 2026 home-run swing matches his 2024 swing. Foot down 200 ms before contact both years, the same hips-before-shoulders order, and the same posture once park cameras are matched.
- **Statcast:** what changed is the rest of his swings. His competitive swings got slower (72.3 to 70.9 mph), shorter (7.4 to 7.2 ft) and flatter (8.7° to 7.9°), while his ISO rose (.188 to .203).
- **His home runs were hit softer and higher:** median exit velocity 102.7 mph in 2026 against 104.9 in 2024, and median launch angle 30° against 26.5°.
- **Projection:** across the league, last season's ISO plus hard-hit exit velocity is the best forecast of next season's power. Bat tracking adds nothing to it, and that forecast puts his 2027 ISO at **.181**.

So 2026 looks like an approach that traded some damage for contact, plus home runs that landed. It doesn't look like a new swing. That supports call 6. A club paying for his 2026 is paying for something the swing doesn't show, which is a reason to bid below my board's market forecast, not at it.

![His home-run swings measured frame by frame, 2024-25 against 2026](figures/2026-arozarena-swing.png)

## The league question first: does bat tracking predict power?

Before reading one hitter's bat speed, I checked what bat speed is worth for anyone. I took every hitter with 300+ PA and 150+ competitive swings in one season and 300+ PA the next. I fit on 2024 to 2025 (199 hitters) and scored on 2025 to 2026 (194 hitters), pairs the fit never saw.

| Model for next season's ISO | Out-of-sample R² | Error (RMSE) |
|---|---|---|
| ISO alone | 0.33 | .0389 |
| ISO + barrel rate | 0.35 | .0382 |
| **ISO + 90th-percentile exit velocity** | **0.37** | **.0375** |
| Bat speed alone | 0.29 | .0401 |
| Blast rate alone | 0.27 | .0406 |

Adding any bat-tracking measure to the best model (bat speed, swing length, attack angle, squared-up rate, blast rate) changes its out-of-sample error by less than 0.001 ISO, and every 95% bootstrap range includes zero.

- **Bat speed is still the most stable number in the set.** It correlates 0.94 with itself year to year, against 0.61 for ISO and 0.91 for 90th-percentile exit velocity. But the hard-hit exit velocities already carry what it knows.
- **A drop in bat speed doesn't add a warning of its own.** On the 151 hitters with three straight qualifying seasons, a change in bat speed from 2024 to 2025 predicted no extra 2026 ISO beyond 2025's ISO and exit velocity: -0.002 ISO per mph, 95% range -0.008 to +0.004.

**For Arozarena:** his 2026 ISO (.203) went up while every input that predicts ISO went down:

| | 2024 | 2025 | 2026 |
|---|---|---|---|
| ISO | .169 | .188 | .203 |
| Barrel rate (per batted ball) | 8.4% | 11.5% | 8.1% |
| 90th-percentile exit velocity | 105.1 | 106.7 | 104.4 |
| Bat speed, competitive swings | 72.7 | 72.3 | 70.9 |
| Swing length (ft) | 7.38 | 7.45 | 7.21 |
| Attack angle | 9.4° | 8.7° | 7.9° |

The model that held up out of sample puts his 2027 ISO at **.181**. The chance he matches .203 is about 28%, on the model's residual spread (.038).

## What the video shows

**How I measured it:**
1. **The clips:** for each home run, I took MLB's own highlight clip, matched to the play by its Statcast play id.
2. **Finding the pitch view:** I cut each clip into camera shots and kept the center-field shot. That's the shot with grass across the lower half and the pitcher low and centered.
3. **Tracking:** I tracked Arozarena through every frame with a pose model (YOLO pose). Every length is measured in torso lengths, so a near camera and a far one compare.
4. **Contact by eye:** the camera can't see the bat meet the ball, so I timed every swing from the moment his shoulders square to the camera.
   - I read contact by eye on seven swings, at the frame where the barrel is out in front of the plate on the ball's line.
   - It came 5 to 7 frames after the shoulders squared (median 6, about 100 ms). My frame reads are saved with the outputs.
5. **The figures:** drawn from the measured joints. No MLB frame is reproduced; each swing links to MLB.com.

**What I could measure:** 23 of the 73 clips.
- **2024:** 11 swings. **2025:** 2. **2026:** 10.
- **Why 50 drop out:** the camera can't see well enough. Some parks use a wide center-field shot where he's under 110 pixels tall, his home park in Seattle among them, which is why 2025 is nearly empty. Other clips open after the swing has started.
- **2024 leans on one park:** 7 of its 11 swings are at Tropicana Field. 2026 is spread over seven parks.

| His home-run swing, center-field view | 2024 (11) | 2026 (10) | Difference, 2026 minus 2024-25 (permutation p) |
|---|---|---|---|
| Foot down to contact | 200 ms | 200 ms | 0 ms (p = 1.0) |
| Leg lift to contact (clips that open before the lift: 8 and 9) | 742 ms | 717 ms | -42 ms vs 2024-25's 759, 2.5 frames (p = 0.07) |
| Hips square ahead of shoulders | 17 ms (one frame) | 17 ms | 0 (p = 1.0) |
| Head drop from stance to contact (torso lengths) | 0.55 | 0.41 | -0.15 (p = 0.007), camera-confounded (below) |
| Shoulder tilt at contact (rear shoulder lower) | 22.5° | 19.7° | -2.8° (p = 0.37) |

**The head drop is the only significant difference, and it's mostly the camera:**
- **Same park, Fenway Park:** 0.45 in 2024 against 0.42 and 0.48 in 2026.
- **Outside Tropicana:** the 2024-25 median is 0.50 against 2026's 0.41, a smaller gap on six swings.
- **Why the camera matters:** a camera mounted higher or lower changes how a vertical drop projects. With the park mix this lopsided, I don't read a posture change into it.

**The timing is the robust part, and it didn't move:**
- Timing doesn't depend on where the camera sits.
- Foot down to contact is 200 ms both years, and the hips square one frame before the shoulders both years.
- He loads and fires the same way he did in 2024.

**Statcast on all 73 home runs** (not only the measured 23), medians:

| | 2024 | 2025 | 2026 |
|---|---|---|---|
| Bat speed on the home-run swing | 75.9 | 75.4 | 74.2 |
| Attack angle | 11.4° | 10.2° | 13.0° |
| Exit velocity | 104.9 | 106.5 | 102.7 |
| Launch angle | 26.5° | 28.0° | 30.0° |

- **His home-run swing kept most of its speed:** 74-76 mph.
- **The drop shows on his other swings:** the season-wide competitive average fell 1.4 mph, more than the home-run swings did (1.2 mph from 2025). So he swung easier more often.
- **The 2026 home runs were softer and higher:** about 2 mph less exit velocity at a 30° median launch angle. That's a profile with less margin, and it's the kind of power that regresses first.

## What a club should do with this

1. **Price the 2024-25 hitter, not the 2026 line.** The video says the home-run swing is the same one; the inputs say the power came with less damage. My log's call 6 (130 wRC+ or lower in 2027, 0.70) stands.
2. **On the market board:** my model's $33.0M a year is a forecast of what the market will pay, and nothing here changes how the call is scored. For a club bidding, the walk-away should sit below that. My log's call 4 threshold was $21.7M a year at two or more years.
3. **Video as a check, not a source:** a broadcast camera times a swing to within a frame. It can't measure stride length (it points down the stride), and its posture numbers move with the park. Use it to rule changes in or out, and say which park a number came from.

## Limits

- **Sample:** 23 measured swings, two seasons with real samples, and a park mix that leans on one park in 2024.
- **Pose estimates:** 2-D, from a camera behind the pitcher. Wrists blur during the swing, so nothing here uses them; every event comes from the shoulders, hips, knees, ankles and head.
- **Contact:** timed by a fixed offset read by eye on seven swings (spread of about one frame).
- **Home runs only:** they are his best swings. The rest of his 2026 swings are only in the Statcast tables, not the video.

## Sources

- MLB highlight clips, via the MLB Stats API game content feed (/api/v1/game/{game_pk}/content), matched to plays by Statcast play id; each measured swing's MLB.com page is listed in `reports/outputs/arozarena_swings.json`. Pulled Nov. 23, 2026.
- Statcast pitch-level and bat-tracking data, 2024-26 regular seasons, via Baseball Savant; pulled Nov. 23, 2026.
- Pose model: Ultralytics YOLO11 pose (medium for tracking, small for finding the pitch view).

Code: `baseball/video/` (`clips.py`, `pose.py`, `measure.py`, `breakdown.py`) and `baseball/evaluation/bat_power.py`. Outputs: `reports/outputs/arozarena_swings.json`, `arozarena_swing_summary.json`, `arozarena_contact_by_eye.json`, `bat_power_summary.json`. Tests: `tests/test_video_measure.py`, `tests/test_bat_power.py`.

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Catcher framing](2026-catcher-framing.md) &nbsp;|&nbsp; [Draft analytics →](2026-mlb-draft-analytics.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *Randy Arozarena, frame by frame: is the 2026 power real?*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-arozarena-swing-breakdown.md</sub>
<!-- /portfolio:footer -->
