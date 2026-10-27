-- MicroVerse local scientific database (SQLite). Schema version 1.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS sources (
    key TEXT PRIMARY KEY,
    citation TEXT NOT NULL,
    doi TEXT, url TEXT, licence TEXT, note TEXT,
    accessed TEXT
);

CREATE TABLE IF NOT EXISTS organisms (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    ncbi_taxonomy_id INTEGER,
    grp TEXT NOT NULL,                    -- bacteria, alga, rotifer, ...
    morphology_json TEXT,
    biosafety_note TEXT,
    source_key TEXT REFERENCES sources(key)
);

CREATE TABLE IF NOT EXISTS parameters (
    id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    conditions TEXT,
    evidence TEXT NOT NULL CHECK (evidence IN
        ('measured','literature_estimate','fitted','derived','assumed','control')),
    verified_against_source INTEGER NOT NULL DEFAULT 0,
    source_key TEXT REFERENCES sources(key),
    model_version_id INTEGER REFERENCES model_versions(id),
    note TEXT,
    UNIQUE (model_id, symbol, model_version_id)
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY,
    model_id TEXT NOT NULL,
    code_version TEXT NOT NULL,
    label TEXT NOT NULL,
    parent_id INTEGER REFERENCES model_versions(id),
    created TEXT NOT NULL,
    calibration_data TEXT,                -- description of data used for fitting
    validation_score_json TEXT            -- scores on SEPARATE validation data
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    created TEXT NOT NULL,
    notes TEXT
);

-- Predictions are append-only: triggers forbid UPDATE and DELETE.
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER REFERENCES experiments(id),
    config_hash TEXT NOT NULL,
    created TEXT NOT NULL,
    hypothesis TEXT,
    summary_json TEXT NOT NULL,           -- regime, key numbers, explanation
    record_hash TEXT NOT NULL             -- sha256 of (config_hash, created, summary_json)
);
CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions
BEGIN SELECT RAISE(ABORT, 'predictions are immutable; create a new prediction instead'); END;
CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions
BEGIN SELECT RAISE(ABORT, 'predictions are immutable'); END;

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    imported TEXT NOT NULL,
    variable TEXT NOT NULL,
    time_d REAL NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    method TEXT,
    source_file TEXT
);

-- Prediction-vs-reality comparisons (v0.5). Append-only like predictions: a comparison is a record of
-- what was compared, with which file (SHA-256) and what came out.
CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    created TEXT NOT NULL,
    observations_sha256 TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    report_path TEXT
);
CREATE TRIGGER IF NOT EXISTS comparisons_no_update BEFORE UPDATE ON comparisons
BEGIN SELECT RAISE(ABORT, 'comparisons are immutable'); END;
CREATE TRIGGER IF NOT EXISTS comparisons_no_delete BEFORE DELETE ON comparisons
BEGIN SELECT RAISE(ABORT, 'comparisons are immutable'); END;

-- ---- Organism reference database (schema version 2) -------------------------------
-- One row per organism with the full record (description + simulation traits) as JSON,
-- plus the most-used fields as columns so the table can be queried and opened in any SQLite browser.
CREATE TABLE IF NOT EXISTS organism_db (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    common TEXT, common_ar TEXT,
    grp TEXT NOT NULL, grp_ar TEXT,
    ncbi_taxid INTEGER,
    lineage TEXT,
    size_um REAL,
    feeding TEXT, oxygen TEXT,
    substrates TEXT, products TEXT,
    mu_max_per_h REAL, ks_mg_l REAL, yield REAL,
    t_min REAL, t_opt REAL, t_max REAL,
    ph_min REAL, ph_opt REAL, ph_max REAL,
    role TEXT, role_ar TEXT,
    metabolism TEXT, metabolism_ar TEXT,
    habitat TEXT, habitat_ar TEXT,
    applications TEXT, applications_ar TEXT,
    biosafety TEXT,
    trait_evidence TEXT,
    record_json TEXT NOT NULL,
    db_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS functions (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL, name_ar TEXT NOT NULL,
    meaning TEXT, meaning_ar TEXT,
    in_model TEXT, in_model_ar TEXT
);

CREATE TABLE IF NOT EXISTS organism_functions (
    organism_key TEXT NOT NULL REFERENCES organism_db(key),
    function_key TEXT NOT NULL REFERENCES functions(key),
    derived_from_traits INTEGER NOT NULL,      -- 1 = read from simulation traits, 0 = assigned by hand
    PRIMARY KEY (organism_key, function_key)
);
