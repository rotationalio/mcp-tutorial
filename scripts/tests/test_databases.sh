#!/usr/bin/env bash
# Sample read queries against Postgres and Mongo (compose stack must be up and seeded).
# Usage: bash scripts/tests/test_databases.sh   (from repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PG_USER="${POSTGRES_USER:-olympics}"
PG_DB="${POSTGRES_DB:-olympics}"
MONGO_DB="${MONGO_DB:-olympics}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running." >&2
  exit 1
fi

if ! docker compose exec -T postgres pg_isready -U "$PG_USER" -d "$PG_DB" -q 2>/dev/null; then
  echo "Postgres is not reachable. Run: docker compose up --build" >&2
  exit 1
fi
if ! docker compose exec -T mongo mongosh --quiet --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q 1; then
  echo "MongoDB is not reachable. Run: docker compose up --build" >&2
  exit 1
fi

echo "=== Postgres: seeded? (countries row count) ==="
n="$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -tAc "SELECT COUNT(*)::text FROM countries" | tr -d '[:space:]')"
if [[ "${n:-0}" == "0" ]]; then
  echo "No rows in countries. Seed has not run; use docker compose up --build (or verify_stack)." >&2
  exit 1
fi
echo "countries: $n"

echo ""
echo "=== Postgres: table counts ==="
docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -c "
SELECT 'countries' AS tbl, COUNT(*)::bigint AS n FROM countries
UNION ALL SELECT 'olympic_games', COUNT(*) FROM olympic_games
UNION ALL SELECT 'athletes', COUNT(*) FROM athletes
UNION ALL SELECT 'athlete_events', COUNT(*) FROM athlete_events;
"

echo ""
echo "=== Postgres: sample join (medals, latest years) ==="
docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -c "
SELECT g.year, ae.event, a.name, ae.medal
FROM athlete_events ae
JOIN athletes a ON a.athlete_id = ae.athlete_id
JOIN olympic_games g ON g.edition_id = ae.edition_id
WHERE ae.athlete_id IS NOT NULL
  AND ae.medal IS NOT NULL AND TRIM(ae.medal) <> ''
ORDER BY g.year DESC, ae.event
LIMIT 5;
"

echo ""
echo "=== Postgres: athlete_events surrogate key ==="
docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -c "
SELECT athlete_event_id, result_id, edition_id, sport
FROM athlete_events
ORDER BY athlete_event_id
LIMIT 3;
"

echo ""
echo "=== MongoDB: collection counts ==="
docker compose exec -T mongo mongosh "$MONGO_DB" --quiet --eval '
const b = db.olympic_athlete_biography.countDocuments({});
const e = db.olympic_event_results.countDocuments({});
print("olympic_athlete_biography: " + b);
print("olympic_event_results: " + e);
if (b === 0) {
  print("ERROR: biography collection is empty (seed may not have run).");
  quit(1);
}
'

echo ""
echo "=== MongoDB: sample biography projection ==="
docker compose exec -T mongo mongosh "$MONGO_DB" --quiet --eval '
const d = db.olympic_athlete_biography.findOne(
  {},
  { athlete_id: 1, name: 1, country_noc: 1, sex: 1, _id: 0 }
);
printjson(d);
'

echo ""
echo "=== MongoDB: sample event_results ==="
docker compose exec -T mongo mongosh "$MONGO_DB" --quiet --eval '
const d = db.olympic_event_results.findOne({}, { _id: 0 });
printjson(d);
'

echo ""
echo "=== All checks finished OK ==="
