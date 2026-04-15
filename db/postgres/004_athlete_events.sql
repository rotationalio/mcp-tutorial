CREATE TABLE IF NOT EXISTS athlete_events (
    result_id BIGINT PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES olympic_games (edition_id),
    country_represented TEXT REFERENCES countries (noc),
    athlete_id INTEGER REFERENCES athletes (athlete_id),
    sport TEXT NOT NULL,
    event TEXT NOT NULL,
    pos TEXT,
    medal TEXT,
    is_team_sport BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_athlete_events_edition_id ON athlete_events (edition_id);
CREATE INDEX IF NOT EXISTS idx_athlete_events_athlete_id ON athlete_events (athlete_id);
CREATE INDEX IF NOT EXISTS idx_athlete_events_sport_event ON athlete_events (sport, event);
