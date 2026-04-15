CREATE TABLE IF NOT EXISTS athletes (
    athlete_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    sex TEXT,
    birth_country TEXT REFERENCES countries (noc)
);

CREATE INDEX IF NOT EXISTS idx_athletes_birth_country ON athletes (birth_country);
