# The GM tree: who trained today's heads of baseball operations, and what the path to the chair looks like

**League study from public data, built as a graph in Neo4j.** Every club decision-maker since 2009 has a sourced career history in this repo, and Baseball-Reference's team pages add each club's GM, scouting director and farm director from 1998. Put together, they show who worked under whom. This study asks three questions:
- **Which bosses** produced future heads of baseball operations?
- **Which clubs** did future heads work for first?
- **What path** did today's heads take to the chair?

*Written 2026-10-20; Dylan Fanelli; Data: the front-office graph `bb front-office` exports (391 executives, 1,315 dated jobs, 181 decision-maker stints); Code: `baseball/roster/gm_tree.py` (`bb gm-tree`), Neo4j loader `baseball/roster/gm_tree.cypher`, tests in `tests/test_gm_tree.py`*

![Where future heads worked first, and the lines from John Hart to today's heads](figures/2026-gm-tree.png)

## Summary
- **Cleveland trained more future heads than any other club.**
  - **The count:** 16 people worked in Cleveland's front office before their first head job, and 9 of them run a club today.
  - **Next:** Washington (formerly Montreal) and Colorado with 11 each, then Boston, Tampa Bay and the A's with 10.
  - **Today's heads:** 38 people run the 27 clubs that have a permanent head. Interim heads and people who have left are excluded.
- **John Hart's tree is the largest by every measure.**
  - **Direct:** 14 future heads learned under him in Cleveland (GM 1991-2001) or Texas (2002-05): Shapiro, Antonetti, O'Dowd, DePodesta, Byrnes, Huntington, Cherington, Hazen, Atkins, Daniels, Preller, Minasian, Arnold and Schmidt.
  - **Across generations:** 43 heads descend from him through the people they trained. That includes 21 of today's 38, more than half.
  - **PageRank:** he ranks first. A boss scores high when the people he trained went on to train heads too. Sandy Alderson ranks second because his tree runs through Billy Beane.
- **Several schools, one dominant one.**
  - **Epstein's Boston:** 11 direct, 21 across generations.
  - **O'Dowd's Colorado:** 9 direct.
  - **Friedman's Tampa Bay:** 8 direct, and Matt Silverman, who learned under Friedman, 6 more.
  - **Jocketty's St. Louis and Cincinnati:** 8 direct.
  - **The overlap:** these trees cross. Cherington learned under Hart, Port and Epstein, so one head can sit in several trees.
- **The path to the chair, for the 64 heads since 2009 with a recorded job before it:**
  - **Time:** a median of 14 years from the first recorded front-office job (the middle half took 11-18). Former major-league players are the fast lane: Sam Fuld took 3 years, Brandon Gomes and Craig Breslow 5.
  - **Titles held on the way:** 75% held an assistant GM title first. 52% held a scouting role, 38% a player-development role and 33% a scouting-director job.
  - **Clubs:** a median of two before the first head job. Nearly half (30 of 64) got the job at the only club they had worked for.
  - **Internal promotion:** 56% were promoted from inside the club they then ran.
  - **Entry level:** 44% have an internship or entry-level job on record. Sources often skip a person's first job, so that is a floor.

## How it's built
- **Bosses.** A club's bosses in a season are its decision-makers from the researched decision-maker list: the president of baseball operations and the general manager, without interim or acting heads.
  - **Before 2009:** that list doesn't cover every club, so the club's GM title fills in.
- **A head.** Someone becomes a head in the first season he runs a club or holds a general manager title. Assistant, special-assistant, interim, acting and co-GM titles don't count.
- **Learned under.** A person who worked for a club, below its boss, in a season that boss ran it. Co-heads (a president and GM running a club together) aren't each other's juniors. The edge keeps the club and the first and last shared seasons.
- **Produced.** A boss produced a head when someone who learned under him later became a head, after their first shared season.
- **Trees and PageRank.** A boss's tree is every head below him, generation by generation.
  - **The PageRank:** it runs on the produced edges, junior to boss, with damping 0.85.
  - **Two implementations:** `gm_tree.pagerank` in Python and Neo4j Graph Data Science's `gds.pageRank` on the same graph. They give the same top-12 order. GDS reports unnormalized scores; the Python version sums to 1.
- **Tests:** eight, on a fictional front office with the arithmetic in comments. They cover:
  - which titles count, and the before-2009 fill;
  - first head years;
  - who learned under whom, and descendants;
  - PageRank on a three-person chain, solved by hand;
  - internal promotion;
  - today's heads.

## Results

**The bosses who produced the most heads**

| Boss | Heads produced directly | Heads in the tree | PageRank | Who |
|---|---|---|---|---|
| John Hart | 14 | 43 | 0.061 | A.J. Preller, Ben Cherington, Bill Schmidt, Chris Antonetti, Dan O'Dowd, Jon Daniels, Josh Byrnes, Mark Shapiro, Matt Arnold, Mike Hazen, Neal Huntington, Paul DePodesta, Perry Minasian, Ross Atkins |
| Theo Epstein | 11 | 21 | 0.020 | Ben Cherington, Brian O'Halloran, Craig Breslow, Jared Porter, Jed Hoyer, Jeff Greenberg, Jerry Dipoto, Josh Byrnes, Mike Hazen, Scott Harris, Zack Scott |
| Dan O'Dowd | 9 | 20 | 0.024 | Bill Schmidt, Billy Eppler, Jeff Bridich, Jerry Dipoto, Jon Daniels, Josh Byrnes, Matt Klentak, Michael Hill, Thad Levine |
| Dave Dombrowski | 9 | 11 | 0.013 | Al Avila, Anirudh Kilambi, Brian O'Halloran, Dan Duquette, Jared Porter, Jim Hendry, Paul Toboni, Preston Mattingly, Zack Scott |
| Mark Shapiro | 8 | 20 | 0.018 | Carter Hawkins, Chris Antonetti, Derek Falvey, Mike Chernoff, Mike Hazen, Neal Huntington, Ross Atkins, Tony LaCava |
| Andrew Friedman | 8 | 13 | 0.023 | Brandon Gomes, Chaim Bloom, Erik Neander, James Click, Jeremy Zoll, Matt Arnold, Matt Silverman, Peter Bendix |
| Walt Jocketty | 8 | 12 | 0.023 | Brad Meador, Dick Williams, Jeff Luhnow, Jeremy Zoll, John Mozeliak, Mike Elias, Mike Girsch, Nick Krall |
| Billy Beane | 6 | 18 | 0.019 | David Forst, Farhan Zaidi, J.P. Ricciardi, Nick Krall, Paul DePodesta, Paul Toboni |
| Matt Silverman | 6 | 10 | 0.012 | Anirudh Kilambi, Chaim Bloom, Erik Neander, James Click, Matt Arnold, Peter Bendix |
| Andy MacPhail | 6 | 8 | 0.019 | Bill Smith, Jim Hendry, Matt Klentak, Rob Antony, Sam Fuld, Terry Ryan |

Sandy Alderson (4 direct, 29 in the tree) and Chuck LaMar (5 direct, 16) rank second and third on PageRank. They trained few heads directly, but those heads (Beane; Friedman) built large trees of their own.

**Where future heads worked first** (before their first head job, below the boss)

| Club | Future heads | Running a club today | Who |
|---|---|---|---|
| CLE | 16 | 9 | Ben Cherington, Bill Schmidt, Carter Hawkins, Chris Antonetti, Dan O'Dowd, David Stearns, Derek Falvey, John Hart, Josh Byrnes, Mark Shapiro, Mike Chernoff, Mike Hazen, Neal Huntington, Paul DePodesta, Ross Atkins, Tony LaCava |
| WSN | 11 | 3 | Alex Anthopoulos, Bill Stoneman, Chris Antonetti, Dana Brown, Dan Duquette, Dave Dombrowski, Larry Beinfest, Mike DeBartolo, Mike Rizzo, Neal Huntington, Tony LaCava |
| COL | 11 | 2 | Bill Schmidt, Billy Eppler, Jeff Bridich, Jerry Dipoto, John Mozeliak, Jon Daniels, Josh Byrnes, Matt Klentak, Michael Hill, Thad Levine, Walt Jocketty |
| BOS | 10 | 6 | Ben Cherington, Brian O'Halloran, Jared Porter, Jed Hoyer, Jerry Dipoto, Josh Byrnes, Mike Hazen, Paul Toboni, Theo Epstein, Zack Scott |
| TBR | 10 | 6 | Andrew Friedman, Anirudh Kilambi, Chaim Bloom, Dan Jennings, Erik Neander, James Click, Matt Arnold, Matt Silverman, Michael Hill, Peter Bendix |
| ATH | 10 | 3 | Billy Beane, Dave Stewart, David Forst, Farhan Zaidi, J.P. Ricciardi, Nick Krall, Paul DePodesta, Paul Toboni, Sandy Alderson, Walt Jocketty |
| NYY | 9 | 1 | Bill Schmidt, Billy Eppler, Brian Cashman, Brian Sabean, Doug Melvin, John Coppolella, Kim Ng, Pat Gillick, Tal Smith |
| CIN | 8 | 4 | Bill Schmidt, Brad Meador, Dan Jennings, Dick Williams, Jeremy Zoll, Matt Arnold, Nick Krall, Tal Smith |

**The path to the chair** (64 heads whose first head job came in 2009 or later, with a job on record before it)

| Measure | Value |
|---|---|
| Years from first recorded front-office job to first head job | median 14 (middle half 11-18; fastest 3, longest 39) |
| Clubs worked for before | median 2 (1: 30 heads; 2: 17; 3: 9; 4 or more: 8) |
| Held an assistant GM title first | 48 of 64 (75%) |
| Held a scouting role (area scout to scouting VP) | 33 of 64 (52%) |
| Held a player-development role | 24 of 64 (38%) |
| Was a scouting director | 21 of 64 (33%) |
| Internship or entry-level job on record | 28 of 64 (44%, a floor) |
| Promoted from inside the club he then ran | 36 of 64 (56%) |

Five of the 16 without an assistant GM title came up through Tampa Bay: Bloom, Neander, Click, Silverman and Bendix.

## What it means for someone starting out
- **Where you start matters, and the evidence points to a few rooms.** 18 of today's 38 heads worked in Cleveland, Boston or Tampa Bay before their first head job.
- **The time is long and steady.** The median was 14 years for heads first hired in 2009-17 and 14 again for 2018-26. Former major-league players are the exception: Fuld, Gomes and Breslow took 3 to 5 years.
- **The assistant GM title is the usual step before the chair** (75%), and more than half of heads (56%) were promoted from inside the club they then ran.

## Limits
- **Learned under means worked below the boss in the same season.** It doesn't mean the boss mentored the person, and a big front office puts more people under one boss. The counts reward large departments and long tenures as well as teaching.
- **The sample is people who reached a head job or a director job Baseball-Reference lists.** People who never got that far are mostly missing, so this study can say where heads came from. It can't say what share of a club's interns became heads.
- **Coverage before 1998 rests on the decision-makers' own career histories.** Bosses from the 1970s and 1980s are thin. Hart's own boss in Cleveland, for example, isn't in the data, so the oldest trees are undercounted at the root.
- **Entry-level jobs are undercounted.** Published biographies often start at a person's first title of note.
- **Trees overlap and aren't additive.** The 21 of today's heads in Hart's tree also appear in other trees.

## Neo4j
The study runs from the CSV tables in Python. The same graph loads into Neo4j next to the trade graph:
- **Load:** `bb gm-tree` writes `data/graph/learned_under.csv` and `heads.csv`. Then run `baseball/roster/gm_tree.cypher` with the import folder pointed at `data/graph`.
- **What it adds:** 929 `LEARNED_UNDER` relationships, 263 of them `produced_head: true`, plus a `first_head` year on 135 executives.

Example queries (also in the `.cypher` file):

```cypher
// Three generations of Hart's tree
MATCH p = (j:Executive)-[:LEARNED_UNDER*1..3 {produced_head: true}]->(:Executive {name: 'John Hart'}) RETURN p

// PageRank with Graph Data Science
MATCH (j:Executive)-[:LEARNED_UNDER {produced_head: true}]->(b:Executive)
WITH DISTINCT j, b WITH gds.graph.project('gmTree', j, b) AS g RETURN g.graphName;
CALL gds.pageRank.stream('gmTree') YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score ORDER BY score DESC LIMIT 15;
```

## Reproduce
```bash
uv run bb front-office --no-pull   # the graph tables, if data/graph/ isn't built yet
uv run bb gm-tree                  # tables, figure, and the Neo4j CSVs
```
