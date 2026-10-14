// Front offices: load data/graph/executives.csv, worked_for.csv and ran.csv (written by `bb front-office`)
// on top of the trade graph (baseball/roster/trade_graph.cypher). Rerunnable.
//
// (:Executive {key, name})-[:WORKED_FOR {role, start, end, uncertain, source}]->(:Team)
// (:Executive)-[:RAN {role, start, end, hired, left}]->(:Team)        president / GM-level decision roles

MATCH (e:Executive) DETACH DELETE e;
CREATE CONSTRAINT executive_key IF NOT EXISTS FOR (e:Executive) REQUIRE e.key IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///executives.csv' AS r
MERGE (e:Executive {key: r.key}) SET e.name = r.name;

LOAD CSV WITH HEADERS FROM 'file:///worked_for.csv' AS r
MATCH (e:Executive {key: r.key}), (t:Team {abbr: r.club})
CREATE (e)-[:WORKED_FOR {role: r.role, start: toInteger(r.start), end: toInteger(r.end),
        uncertain: r.uncertain = 'True', source: r.source}]->(t);

LOAD CSV WITH HEADERS FROM 'file:///ran.csv' AS r
MATCH (e:Executive {key: r.key}), (t:Team {abbr: r.club})
CREATE (e)-[:RAN {role: r.role, start: toInteger(r.start), end: toInteger(r.end), hired: r.hired, left: r.left}]->(t);
