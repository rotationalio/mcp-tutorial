CREATE TABLE IF NOT EXISTS olympic_games (
    edition_id INTEGER PRIMARY KEY,
    edition TEXT NOT NULL,
    edition_url TEXT,
    year INTEGER NOT NULL,
    city TEXT NOT NULL,
    country_flag_url TEXT,
    country_noc TEXT REFERENCES countries (noc),
    start_date TEXT,
    end_date TEXT,
    competition_date TEXT,
    is_held TEXT
);

CREATE INDEX IF NOT EXISTS idx_olympic_games_year ON olympic_games (year);
