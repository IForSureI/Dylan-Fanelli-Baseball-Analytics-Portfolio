"""Dylan Fanelli's baseball operations library.

Organized around the jobs of a front office:

- ingest/       getting data in: Statcast pulls, sample data, (later) TrackMan and Rapsodo files
- warehouse.py  the one DuckDB database every pull lands in
- evaluation/   what a player is: arsenals, splits, hitter profiles, scouting grades
- development/  what a player could become: development plans, progress tracking
- roster/       building the club: service time, arbitration, contracts, pref lists
- business/     the revenue side: partnerships, attendance, pricing
"""

from baseball import house as _house  # noqa: E402

_house.apply()  # every chart in the package uses the house style (baseball/house.py)
