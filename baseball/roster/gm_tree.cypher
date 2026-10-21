// The GM tree: load data/graph/learned_under.csv and heads.csv (written by `bb gm-tree`) into Neo4j.
// Needs the front-office graph (Executive, Team, WORKED_FOR, RAN) already loaded. Rerunnable.
//
// (:Executive)-[:LEARNED_UNDER {club, first, last, seasons, produced_head}]->(:Executive)
//     the junior worked for the club, below its boss, in the seasons first..last (shared employment);
//     produced_head = the junior later held a club's top baseball-operations job
// (:Executive {first_head})   the first season the person held a club's top baseball-operations job

MATCH ()-[e:LEARNED_UNDER]->() DELETE e;
MATCH (x:Executive) REMOVE x.first_head;

LOAD CSV WITH HEADERS FROM 'file:///learned_under.csv' AS r
MATCH (j:Executive {key: r.junior}), (b:Executive {key: r.boss})
MERGE (j)-[e:LEARNED_UNDER {club: r.club}]->(b)
SET e.first = toInteger(r.first), e.last = toInteger(r.last), e.seasons = toInteger(r.seasons),
    e.produced_head = r.produced_head = 'True';

LOAD CSV WITH HEADERS FROM 'file:///heads.csv' AS r
MATCH (x:Executive {key: r.key})
SET x.first_head = toInteger(r.first_head);

// Examples
// Cleveland's tree, three generations down from John Hart:
//   MATCH p = (j:Executive)-[:LEARNED_UNDER*1..3 {produced_head: true}]->(:Executive {name: 'John Hart'}) RETURN p
// Bosses with the most future heads working under them:
//   MATCH (j:Executive)-[e:LEARNED_UNDER {produced_head: true}]->(b)
//   RETURN b.name, count(DISTINCT j) AS heads ORDER BY heads DESC
// Influence (Graph Data Science):
//   MATCH (j:Executive)-[e:LEARNED_UNDER {produced_head: true}]->(b:Executive)
//   WITH DISTINCT j, b WITH gds.graph.project('gmTree', j, b) AS g RETURN g.graphName;
//   CALL gds.pageRank.stream('gmTree') YIELD nodeId, score
//   RETURN gds.util.asNode(nodeId).name AS name, score ORDER BY score DESC LIMIT 15;
//   CALL gds.graph.drop('gmTree');
