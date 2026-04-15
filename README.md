# mcp-tutorial

Code and material for Benjamin’s AMLC tutorial on MCP servers.

## Stack

- **PostgreSQL** — tables sourced from the public Hugging Face dataset [`SVeldman/126-years-olympic-results`](https://huggingface.co/datasets/SVeldman/126-years-olympic-results): `countries`, `olympic_games`, `athletes`, `athlete_events`.
- **MongoDB** — collections `olympic_athlete_biography` and `olympic_event_results` (from `Olympic_Athlete_Biography.csv` and `Olympic_Event_Results.csv`).
- **`Olympic_Medal_Tally_History.csv`** is not downloaded or loaded.

## Run (after you are ready)

```bash
docker compose up --build
```

This starts Postgres and Mongo, waits for health checks, runs the **`seed`** service once (downloads CSVs from Hugging Face into a temp directory inside the container, loads both databases, deletes temp files), then leaves the databases running.

- Postgres: `localhost:5432` (defaults: user / password / database `olympics`).
- MongoDB: `localhost:27017`, database `olympics`.

Re-run skips work if `countries` already has rows. To re-seed from scratch:

```bash
docker compose down -v
docker compose up --build
```

Optional: copy [.env.example](.env.example) to `.env` to override ports or `HF_DATASET_REPO` / `HF_DATASET_REVISION`.

Schema and init scripts live under `db/postgres/` and `db/mongo/`; loading logic is in `scripts/seed_databases.py`.
