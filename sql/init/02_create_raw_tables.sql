CREATE TABLE IF NOT EXISTS raw.master (
    run_date   date        PRIMARY KEY,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    payload    jsonb       NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.fixtures (
    run_date   date        PRIMARY KEY,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    payload    jsonb       NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.player_summary (
    player_id  integer     NOT NULL,
    run_date   date        NOT NULL,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    payload    jsonb       NOT NULL,
    PRIMARY KEY (run_date, player_id)
);
CREATE TABLE IF NOT EXISTS raw.pipeline_runs (
    run_id       bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_date     date        NOT NULL,
    step         text        NOT NULL, 
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    rows_loaded  integer,
    failed_ids   integer[]   NOT NULL DEFAULT '{}',
    status       text        NOT NULL DEFAULT 'running'
                             CHECK (status IN ('running', 'success', 'failed')),
    error        text        
);