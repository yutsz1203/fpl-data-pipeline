CREATE TABLE IF NOT EXISTS raw.bzzoiro_events (
    event_id   integer     PRIMARY KEY,
    run_date   date        NOT NULL,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    payload    jsonb       NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.bzzoiro_lineups (
    event_id   integer     PRIMARY KEY,
    run_date   date        NOT NULL,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    payload    jsonb       NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.bzzoiro_squads (
    team_id    integer     NOT NULL,
    run_date   date        NOT NULL,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    payload    jsonb       NOT NULL,
    PRIMARY KEY (run_date, team_id)
);
CREATE EXTENSION IF NOT EXISTS unaccent;
