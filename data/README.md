# Data

**Seeded in Docker:** CSVs are normally downloaded inside the `seed` container from Hugging Face (see repository [README](../README.md)).

**Local copies (optional):** You can place the same CSVs here for design discussion or ad-hoc inspection. `*.csv` under `data/` is gitignored so large files are not committed.

Files used by the stack (excluding `Olympic_Medal_Tally_History.csv`):

- `Olympic_Country_Profiles.csv` → Postgres `countries`
- `Olympic_Games_Summary.csv` → Postgres `olympic_games`
- `Olympic_Athlete_Biography.csv` → Postgres `athletes` (slim columns) and Mongo `olympic_athlete_biography` (full document)
- `Olympic_Athlete_Event_Details.csv` → Postgres `athlete_events`
- `Olympic_Event_Results.csv` → Mongo `olympic_event_results`
