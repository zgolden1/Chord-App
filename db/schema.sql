-- ChordFlow catalog schema. Portable: runs on PostgreSQL (production) and SQLite (local development).
-- JSON is stored as TEXT; timestamps are ISO-8601 strings in UTC.

CREATE TABLE IF NOT EXISTS recordings (
  mbid          TEXT PRIMARY KEY,          -- MusicBrainz recording id: identifies one specific recording
  title         TEXT NOT NULL,
  artist        TEXT NOT NULL,
  album         TEXT,
  year          INTEGER,
  length_s      REAL,
  kind          TEXT,                      -- studio / live / remix / acoustic ... (from MusicBrainz disambiguation)
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS recordings_title ON recordings (title);

-- One row per version of a recording's transcription. Exactly one row per recording is 'official'.
-- 'candidate' rows are other pipelines' results kept for A/B comparison and the accuracy benchmark.
CREATE TABLE IF NOT EXISTS analyses (
  id            INTEGER PRIMARY KEY,       -- SERIAL / IDENTITY on PostgreSQL (see README)
  mbid          TEXT NOT NULL REFERENCES recordings(mbid),
  version       INTEGER NOT NULL,
  status        TEXT NOT NULL,             -- official | superseded | candidate
  source        TEXT NOT NULL,             -- pipeline:<name> | suggestion:<id> | revert:<version>
  data          TEXT NOT NULL,             -- JSON: key, bpm, beats, chords[], confidence summary
  created_at    TEXT NOT NULL,
  created_by    TEXT,
  UNIQUE (mbid, version)
);
CREATE INDEX IF NOT EXISTS analyses_mbid ON analyses (mbid, status);

-- User suggestions. Never applied directly: they wait here until validated and approved.
CREATE TABLE IF NOT EXISTS suggestions (
  id            INTEGER PRIMARY KEY,
  mbid          TEXT NOT NULL REFERENCES recordings(mbid),
  base_version  INTEGER NOT NULL,          -- the official version the user was looking at
  kind          TEXT NOT NULL,             -- chord | key | bpm | voicing | shape | sync
  payload       TEXT NOT NULL,             -- JSON, shape depends on kind
  note          TEXT,
  by_user       TEXT NOT NULL,
  status        TEXT NOT NULL,             -- pending | approved | rejected
  agree_count   INTEGER NOT NULL DEFAULT 1,-- how many independent users sent the same fix
  created_at    TEXT NOT NULL,
  reviewed_by   TEXT,
  reviewed_at   TEXT,
  reason        TEXT,
  result_version INTEGER                   -- the analyses.version this created, if approved
);
CREATE INDEX IF NOT EXISTS suggestions_q ON suggestions (status, mbid);

-- Background processing queue. A worker claims one job at a time.
CREATE TABLE IF NOT EXISTS jobs (
  id            INTEGER PRIMARY KEY,
  mbid          TEXT NOT NULL REFERENCES recordings(mbid),
  status        TEXT NOT NULL,             -- queued | running | done | failed
  pipeline      TEXT NOT NULL,
  upload_path   TEXT,                      -- deleted as soon as the job finishes
  by_user       TEXT,
  error         TEXT,
  created_at    TEXT NOT NULL,
  started_at    TEXT,
  finished_at   TEXT
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs (status, created_at);

-- Accuracy benchmark runs (written by eval/evaluate.py --save).
CREATE TABLE IF NOT EXISTS eval_runs (
  id            INTEGER PRIMARY KEY,
  pipeline      TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  n_songs       INTEGER NOT NULL,
  metrics       TEXT NOT NULL              -- JSON
);

-- One vote per user per suggestion, so "N people agree" counts independent people.
CREATE TABLE IF NOT EXISTS suggestion_votes (
  suggestion_id INTEGER NOT NULL REFERENCES suggestions(id),
  user_id       TEXT NOT NULL,
  PRIMARY KEY (suggestion_id, user_id)
);
