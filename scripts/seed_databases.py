"""
Download the Hugging Face dataset CSVs (no authentication) and load:
  - PostgreSQL: countries, olympic_games, athletes, athlete_events
    (CSV has many rows per result_id; athlete_events.athlete_event_id is the row PK.)
  - MongoDB: olympic_athlete_biography, olympic_event_results

Olympic_Medal_Tally_History.csv is not downloaded or loaded.
"""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import execute_batch
from pymongo import MongoClient


def _hf_base_url() -> str:
    repo = os.environ.get("HF_DATASET_REPO", "SVeldman/126-years-olympic-results").strip()
    rev = os.environ.get("HF_DATASET_REVISION", "main").strip() or "main"
    return f"https://huggingface.co/datasets/{repo}/resolve/{rev}"


def _hf_file_url(filename: str) -> str:
    return f"{_hf_base_url()}/{filename}"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "mcp-tutorial-seed/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Download failed for {url}: {exc.reason}") from exc


def _parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.upper() == "NA":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _parse_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in ("true", "t", "1", "yes")


def _postgres_seeded(conn: psycopg2.extensions.connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM countries")
        (n,) = cur.fetchone()
    return int(n or 0) > 0


def _load_countries(conn: psycopg2.extensions.connection, path: Path) -> None:
    rows: list[tuple[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            noc = (row.get("noc") or "").strip()
            country = (row.get("country") or "").strip()
            if noc:
                rows.append((noc, country or noc))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO countries (noc, country)
            VALUES (%s, %s)
            ON CONFLICT (noc) DO NOTHING
            """,
            rows,
            page_size=500,
        )


def _collect_country_nocs_from_games_details_bio(
    games_path: Path, details_path: Path, bio_path: Path
) -> set[str]:
    nocs: set[str] = set()
    for path in (games_path, details_path, bio_path):
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                n = (row.get("country_noc") or "").strip()
                if n:
                    nocs.add(n)
    return nocs


def _ensure_country_placeholders(conn: psycopg2.extensions.connection, nocs: set[str]) -> None:
    """Insert (noc, noc) for NOCs referenced by other tables but missing from profiles."""
    rows = [(n, n) for n in sorted(nocs)]
    if not rows:
        return
    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO countries (noc, country)
            VALUES (%s, %s)
            ON CONFLICT (noc) DO NOTHING
            """,
            rows,
            page_size=500,
        )


def _load_games_summary(conn: psycopg2.extensions.connection, path: Path) -> None:
    rows: list[tuple[Any, ...]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = _parse_int(row.get("edition_id"))
            if eid is None:
                continue
            year = _parse_int(row.get("year"))
            if year is None:
                continue
            rows.append(
                (
                    eid,
                    (row.get("edition") or "").strip(),
                    (row.get("edition_url") or "").strip() or None,
                    year,
                    (row.get("city") or "").strip(),
                    (row.get("country_flag_url") or "").strip() or None,
                    (row.get("country_noc") or "").strip() or None,
                    (row.get("start_date") or "").strip() or None,
                    (row.get("end_date") or "").strip() or None,
                    (row.get("competition_date") or "").strip() or None,
                    (row.get("isHeld") or "").strip() or None,
                )
            )
    if not rows:
        return
    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO olympic_games (
                edition_id, edition, edition_url, year, city, country_flag_url,
                country_noc, start_date, end_date, competition_date, is_held
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (edition_id) DO NOTHING
            """,
            rows,
            page_size=100,
        )


def _flush_athletes_biography_batch(
    conn: psycopg2.extensions.connection, batch: list[tuple[Any, ...]]
) -> None:
    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO athletes (athlete_id, name, sex, birth_country)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (athlete_id) DO UPDATE SET
                name = EXCLUDED.name,
                sex = EXCLUDED.sex,
                birth_country = EXCLUDED.birth_country
            """,
            batch,
            page_size=len(batch),
        )


def _load_athletes_from_biography(conn: psycopg2.extensions.connection, path: Path) -> set[int]:
    """Load slim athlete rows from biography CSV; returns athlete_ids present in the file."""
    batch: list[tuple[Any, ...]] = []
    batch_size = 2000
    seen: set[int] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = _parse_int(row.get("athlete_id"))
            if aid is None:
                continue
            name = (row.get("name") or "").strip() or f"Athlete {aid}"
            sex = (row.get("sex") or "").strip() or None
            noc = (row.get("country_noc") or "").strip() or None
            birth_country = noc if noc else None
            batch.append((aid, name, sex, birth_country))
            seen.add(aid)
            if len(batch) >= batch_size:
                _flush_athletes_biography_batch(conn, batch)
                batch.clear()
        if batch:
            _flush_athletes_biography_batch(conn, batch)
    return seen


def _scan_event_athlete_ids_and_names(path: Path) -> tuple[set[int], dict[int, str]]:
    ids: set[int] = set()
    names: dict[int, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = _parse_int(row.get("athlete_id"))
            if aid is None:
                continue
            ids.add(aid)
            an = (row.get("athlete") or "").strip()
            if an:
                names[aid] = an
    return ids, names


def _insert_athlete_stubs(
    conn: psycopg2.extensions.connection, missing: set[int], names: dict[int, str]
) -> None:
    if not missing:
        return
    rows = [
        (aid, names.get(aid) or f"Athlete {aid}", None, None) for aid in sorted(missing)
    ]
    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO athletes (athlete_id, name, sex, birth_country)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (athlete_id) DO NOTHING
            """,
            rows,
            page_size=2000,
        )


def _load_athlete_events(conn: psycopg2.extensions.connection, path: Path) -> None:
    batch: list[tuple[Any, ...]] = []
    batch_size = 4000
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = _parse_int(row.get("result_id"))
            if rid is None:
                continue
            eid = _parse_int(row.get("edition_id"))
            if eid is None:
                continue
            aid = _parse_int(row.get("athlete_id"))
            country = (row.get("country_noc") or "").strip() or None
            batch.append(
                (
                    int(rid),
                    eid,
                    country,
                    aid,
                    (row.get("sport") or "").strip(),
                    (row.get("event") or "").strip(),
                    (row.get("pos") or "").strip() or None,
                    (row.get("medal") or "").strip() or None,
                    _parse_bool(row.get("isTeamSport")),
                )
            )
            if len(batch) >= batch_size:
                _flush_athlete_events_batch(conn, batch)
                batch.clear()
        if batch:
            _flush_athlete_events_batch(conn, batch)


def _flush_athlete_events_batch(
    conn: psycopg2.extensions.connection, batch: list[tuple[Any, ...]]
) -> None:
    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO athlete_events (
                result_id, edition_id, country_represented, athlete_id,
                sport, event, pos, medal, is_team_sport
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            batch,
            page_size=len(batch),
        )


def _mongo_row_document(row: dict[str, str | None]) -> dict[str, Any]:
    doc: dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        doc[k] = v.strip() if isinstance(v, str) else v
    return doc


def _load_mongo_csv(db, collection_name: str, path: Path) -> None:
    coll = db[collection_name]
    batch: list[dict[str, Any]] = []
    batch_size = 2000
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append(_mongo_row_document(row))
            if len(batch) >= batch_size:
                coll.insert_many(batch, ordered=False)
                batch.clear()
    if batch:
        coll.insert_many(batch, ordered=False)


def main() -> None:
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = int(os.environ.get("POSTGRES_PORT", "5432"))
    pg_user = os.environ.get("POSTGRES_USER", "olympics")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "olympics")
    pg_db = os.environ.get("POSTGRES_DB", "olympics")
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    mongo_db_name = os.environ.get("MONGO_DB", "olympics")

    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        user=pg_user,
        password=pg_password,
        dbname=pg_db,
    )
    mongo = MongoClient(mongo_uri)
    workdir: Path | None = None

    try:
        if _postgres_seeded(conn):
            print("Database already seeded; skipping.")
            return

        workdir = Path(tempfile.mkdtemp(prefix="hf_olympic_"))
        base = _hf_base_url()
        print(f"Using dataset base: {base}")

        country = workdir / "Olympic_Country_Profiles.csv"
        games = workdir / "Olympic_Games_Summary.csv"
        details = workdir / "Olympic_Athlete_Event_Details.csv"
        bio = workdir / "Olympic_Athlete_Biography.csv"
        events = workdir / "Olympic_Event_Results.csv"

        for path, name in (
            (country, "Olympic_Country_Profiles.csv"),
            (games, "Olympic_Games_Summary.csv"),
            (details, "Olympic_Athlete_Event_Details.csv"),
            (bio, "Olympic_Athlete_Biography.csv"),
            (events, "Olympic_Event_Results.csv"),
        ):
            url = _hf_file_url(name)
            print(f"Fetching {name} …")
            _download(url, path)

        print("Loading PostgreSQL …")
        try:
            _load_countries(conn, country)
            extra_nocs = _collect_country_nocs_from_games_details_bio(games, details, bio)
            _ensure_country_placeholders(conn, extra_nocs)
            _load_games_summary(conn, games)
            bio_ids = _load_athletes_from_biography(conn, bio)
            event_ids, event_names = _scan_event_athlete_ids_and_names(details)
            stubs = event_ids - bio_ids
            _insert_athlete_stubs(conn, stubs, event_names)
            _load_athlete_events(conn, details)
            print("Loading MongoDB …")
            mongo_db = mongo[mongo_db_name]
            _load_mongo_csv(mongo_db, "olympic_athlete_biography", bio)
            _load_mongo_csv(mongo_db, "olympic_event_results", events)
        except Exception:
            conn.rollback()
            raise

        conn.commit()
        print("Seed completed.")
    finally:
        conn.close()
        mongo.close()
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
