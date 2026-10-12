"""The edge engine: league-wide detectors for things box scores and leaderboards don't show.

- tells.py    : release tells. Can you tell a pitch from the fastball using release alone?
- shifts.py   : hidden in-season changes. When did one pitch change shape, and did results follow?
- stuff.py    : stuff vs results. Expected whiffs from physics alone; where results disagree.
- baselines.py: league-wide season-over-season shifts (is it the pitcher or the cameras?).

Every detector reports its sample sizes and an uncertainty, and every finding states what
would make it wrong.
"""
