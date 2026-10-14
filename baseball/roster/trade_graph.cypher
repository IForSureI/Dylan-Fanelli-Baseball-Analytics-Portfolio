// The MLB trade graph: load data/graph/*.csv (written by `bb trades build`) into Neo4j.
// Neo4j's import folder (server.directories.import in neo4j.conf) points at ~/Baseball/data/graph.
// Rerunnable: clears the trade graph first, keeps anything else in the database.
//
// (:Team)-[:MADE {war_received, war_sent, net_war, tree_war_received, flips}]->(:Trade)
// (:Trade)-[:MOVED {from_team, to_team, war_for_acquirer, seasons_with_acquirer, still_accruing}]->(:Player)
// (:Trade)-[:LED_TO {team, player, days_held}]->(:Trade)      a club flipped a player it got in the first trade
// (:Team)-[:TRADED_WITH {trades, players}]-(:Team)            pair totals, for Graph Data Science

MATCH (n) WHERE n:Trade OR n:Player OR n:Team DETACH DELETE n;

CREATE CONSTRAINT team_id IF NOT EXISTS FOR (t:Team) REQUIRE t.team_id IS UNIQUE;
CREATE CONSTRAINT player_id IF NOT EXISTS FOR (p:Player) REQUIRE p.player_id IS UNIQUE;
CREATE CONSTRAINT trade_id IF NOT EXISTS FOR (t:Trade) REQUIRE t.trade_id IS UNIQUE;
CREATE INDEX trade_season IF NOT EXISTS FOR (t:Trade) ON (t.season);
CREATE INDEX player_name IF NOT EXISTS FOR (p:Player) ON (p.name);
CREATE INDEX team_abbr IF NOT EXISTS FOR (t:Team) ON (t.abbr);

LOAD CSV WITH HEADERS FROM 'file:///teams.csv' AS r
MERGE (t:Team {team_id: toInteger(r.team_id)}) SET t.abbr = r.abbr;

LOAD CSV WITH HEADERS FROM 'file:///players.csv' AS r
MERGE (p:Player {player_id: toInteger(r.player_id)}) SET p.name = r.name;

LOAD CSV WITH HEADERS FROM 'file:///trades.csv' AS r
MERGE (t:Trade {trade_id: toInteger(r.trade_id)})
SET t.date = date(r.date), t.season = toInteger(r.season), t.description = r.description,
    t.n_teams = toInteger(r.n_teams), t.n_player_legs = toInteger(r.n_player_legs),
    t.cash_or_ptbnl_legs = toInteger(r.cash_or_ptbnl_legs), t.non_mlb_party = r.non_mlb_party = 'True',
    t.record_repaired = r.record_repaired = 'True', t.record_incomplete = r.record_incomplete = 'True';

LOAD CSV WITH HEADERS FROM 'file:///legs.csv' AS r
MATCH (t:Trade {trade_id: toInteger(r.trade_id)}), (p:Player {player_id: toInteger(r.player_id)}),
      (f:Team {team_id: toInteger(r.from_id)}), (to:Team {team_id: toInteger(r.to_id)})
CREATE (t)-[:MOVED {from_team: f.abbr, to_team: to.abbr, war_for_acquirer: toFloat(r.war_for_acquirer),
        seasons_with_acquirer: toInteger(r.seasons_with_acquirer),
        reached_mlb_with_acquirer: r.reached_mlb_with_acquirer = 'True', still_accruing: r.still_accruing = 'True'}]->(p);

LOAD CSV WITH HEADERS FROM 'file:///sides.csv' AS r
MATCH (tm:Team {team_id: toInteger(r.team_id)}), (t:Trade {trade_id: toInteger(r.trade_id)})
CREATE (tm)-[:MADE {war_received: toFloat(r.war_received), war_sent: toFloat(r.war_sent), net_war: toFloat(r.net_war),
        players_in: toInteger(r.players_in), players_out: toInteger(r.players_out),
        tree_war_received: toFloat(r.tree_war_received), flips: toInteger(r.flips)}]->(t);

LOAD CSV WITH HEADERS FROM 'file:///links.csv' AS r
MATCH (a:Trade {trade_id: toInteger(r.from_trade)}), (b:Trade {trade_id: toInteger(r.to_trade)}), (tm:Team {team_id: toInteger(r.team_id)})
CREATE (a)-[:LED_TO {team: tm.abbr, player_id: toInteger(r.player_id), player: r.player_name, days_held: toInteger(r.days_held)}]->(b);

MATCH (a:Team)-[:MADE]->(t:Trade)<-[:MADE]-(b:Team) WHERE a.team_id < b.team_id
WITH a, b, count(DISTINCT t) AS trades
OPTIONAL MATCH (a)-[:MADE]->(t2:Trade)<-[:MADE]-(b), (t2)-[m:MOVED]->()
WHERE (m.from_team = a.abbr AND m.to_team = b.abbr) OR (m.from_team = b.abbr AND m.to_team = a.abbr)
WITH a, b, trades, count(m) AS players
MERGE (a)-[r:TRADED_WITH]-(b) SET r.trades = trades, r.players = players;
