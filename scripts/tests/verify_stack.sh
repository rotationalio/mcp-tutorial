#!/usr/bin/env bash
# Reset volumes, start Postgres + Mongo, seed from Hugging Face, run sample queries.
# Usage: bash scripts/tests/verify_stack.sh   (from repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop (or the Docker daemon) and run this script again." >&2
  exit 1
fi

echo "=== docker compose: fresh volumes, DBs, seed ==="
docker compose down -v
docker compose up --build -d postgres mongo

echo "=== waiting for health ==="
for _ in $(seq 1 60); do
  if docker compose exec -T postgres pg_isready -U olympics -d olympics -q 2>/dev/null \
    && docker compose exec -T mongo mongosh --quiet --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q 1; then
    break
  fi
  sleep 2
done

docker compose run --build --rm seed

echo ""
echo "=== Postgres: row counts ==="
docker compose exec -T postgres psql -U olympics -d olympics -c "
SELECT 'countries' AS tbl, COUNT(*)::bigint AS n FROM countries
UNION ALL SELECT 'olympic_games', COUNT(*) FROM olympic_games
UNION ALL SELECT 'athletes', COUNT(*) FROM athletes
UNION ALL SELECT 'athlete_events', COUNT(*) FROM athlete_events;
"

echo ""
echo "=== Postgres: sample join (2000 Sydney, medals) ==="
docker compose exec -T postgres psql -U olympics -d olympics -c "
SELECT g.year, ae.event, a.name, ae.medal, ae.country_represented
FROM athlete_events ae
JOIN athletes a ON a.athlete_id = ae.athlete_id
JOIN olympic_games g ON g.edition_id = ae.edition_id
WHERE g.year = 2000 AND ae.medal IS NOT NULL AND TRIM(ae.medal) <> ''
ORDER BY ae.event, ae.medal
LIMIT 10;
"

echo ""
echo "=== Postgres: FK sanity (orphan check) ==="
docker compose exec -T postgres psql -U olympics -d olympics -c "
SELECT COUNT(*) AS athlete_events_missing_game
FROM athlete_events ae
LEFT JOIN olympic_games g ON g.edition_id = ae.edition_id
WHERE g.edition_id IS NULL;
"

echo ""
echo "=== MongoDB: collection counts ==="
docker compose exec -T mongo mongosh olympics --quiet --eval '
const b = db.olympic_athlete_biography.countDocuments({});
const e = db.olympic_event_results.countDocuments({});
print("olympic_athlete_biography: " + b);
print("olympic_event_results: " + e);
const one = db.olympic_athlete_biography.findOne({}, { athlete_id: 1, name: 1, country_noc: 1 });
print("sample biography doc: " + JSON.stringify(one));
'

echo ""
echo "=== done (postgres + mongo still running; docker compose down -v to reset) ==="
