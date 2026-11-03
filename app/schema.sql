-- Provenance-first schema.
-- Facilities and regions hold identity only. Every number lives in `facts`,
-- and every fact must point at a source. A metric with no fact row is "unknown".

CREATE TABLE sources (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    publisher   TEXT NOT NULL,
    url         TEXT,
    published   TEXT,            -- date or year as published
    accessed    TEXT,            -- date the data was pulled / read
    kind        TEXT NOT NULL CHECK (kind IN (
                    'utility_filing', 'permit', 'sustainability_report',
                    'government_data', 'academic', 'directory',
                    'operator_site', 'industry_survey', 'model_assumption')),
    verified    INTEGER NOT NULL DEFAULT 0,  -- 1 once a human has checked the value against the document
    notes       TEXT
);

CREATE TABLE regions (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    state               TEXT NOT NULL,
    utilities           TEXT,
    balancing_authority TEXT,
    egrid_subregion     TEXT,
    lat                 REAL NOT NULL,
    lon                 REAL NOT NULL,
    notes               TEXT
);

CREATE TABLE facilities (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    operator           TEXT NOT NULL,
    region_id          TEXT NOT NULL REFERENCES regions(id),
    city               TEXT,
    state              TEXT NOT NULL,
    lat                REAL NOT NULL,
    lon                REAL NOT NULL,
    location_precision TEXT NOT NULL CHECK (location_precision IN ('site', 'city', 'county')),
    status             TEXT NOT NULL CHECK (status IN ('operating', 'under_construction', 'proposed', 'unknown')),
    source_id          TEXT NOT NULL REFERENCES sources(id),
    notes              TEXT
);

CREATE TABLE facts (
    id                  INTEGER PRIMARY KEY,
    entity_type         TEXT NOT NULL CHECK (entity_type IN ('facility', 'region', 'model')),
    entity_id           TEXT NOT NULL,
    metric              TEXT NOT NULL,
    value_low           REAL,
    value               REAL,
    value_high          REAL,
    value_text          TEXT,    -- for categorical metrics such as cooling_method
    unit                TEXT,
    kind                TEXT NOT NULL CHECK (kind IN ('measured', 'reported', 'estimate', 'assumption')),
    period              TEXT,    -- e.g. '2023' or '2024-06'
    source_id           TEXT NOT NULL REFERENCES sources(id),
    related_source_ids  TEXT,    -- comma-separated, for values informed by more than one document
    method              TEXT,    -- how the number was derived, required for estimates
    notes               TEXT,
    CHECK (value IS NOT NULL OR value_text IS NOT NULL),
    CHECK (kind NOT IN ('estimate', 'assumption') OR method IS NOT NULL)
);

CREATE INDEX facts_entity ON facts (entity_type, entity_id, metric);
