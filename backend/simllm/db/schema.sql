-- SimLLM per-save SQLite schema.
-- One file per save. WAL mode is enabled by connection.py on every open.

CREATE TABLE IF NOT EXISTS meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  save_name TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sim_clock (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  current_tick INTEGER NOT NULL DEFAULT 0,
  sim_datetime TEXT NOT NULL,
  is_paused INTEGER NOT NULL DEFAULT 1,
  generation INTEGER NOT NULL DEFAULT 1,
  last_saved_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  emoji TEXT NOT NULL,
  traits TEXT NOT NULL,
  backstory TEXT,
  age_ticks INTEGER NOT NULL DEFAULT 0,
  lifespan_ticks INTEGER NOT NULL,
  age_stage TEXT NOT NULL DEFAULT 'adult',
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  home_building_id INTEGER REFERENCES buildings(id),
  currency REAL NOT NULL DEFAULT 0,
  health REAL NOT NULL DEFAULT 100,
  mood REAL NOT NULL DEFAULT 0,
  mood_band INTEGER NOT NULL DEFAULT 0,
  zero_health_ticks INTEGER NOT NULL DEFAULT 0,
  is_alive INTEGER NOT NULL DEFAULT 1,
  death_tick INTEGER,
  death_cause TEXT,
  generation INTEGER NOT NULL,
  created_at_tick INTEGER NOT NULL,
  current_action TEXT,
  next_decision_tick INTEGER NOT NULL DEFAULT 0,
  current_goal TEXT,
  life_summary TEXT,
  life_summary_updated_tick INTEGER
);

CREATE TABLE IF NOT EXISTS agent_needs (
  agent_id INTEGER PRIMARY KEY REFERENCES agents(id),
  hunger REAL NOT NULL DEFAULT 100,
  energy REAL NOT NULL DEFAULT 100,
  social REAL NOT NULL DEFAULT 100,
  shelter REAL NOT NULL DEFAULT 100,
  hygiene REAL NOT NULL DEFAULT 100,
  fun REAL NOT NULL DEFAULT 100,
  purpose REAL NOT NULL DEFAULT 100,
  updated_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL REFERENCES agents(id),
  tick INTEGER NOT NULL,
  sim_datetime TEXT NOT NULL,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  related_agent_id INTEGER REFERENCES agents(id)
);
CREATE INDEX IF NOT EXISTS idx_memories_agent_tick ON memories(agent_id, tick DESC);

CREATE TABLE IF NOT EXISTS relationships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_a_id INTEGER NOT NULL REFERENCES agents(id),
  agent_b_id INTEGER NOT NULL REFERENCES agents(id),
  affinity REAL NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  updated_tick INTEGER NOT NULL,
  UNIQUE(agent_a_id, agent_b_id)
);

CREATE TABLE IF NOT EXISTS world_tiles (
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  tile_type TEXT NOT NULL,
  building_id INTEGER REFERENCES buildings(id),
  PRIMARY KEY (x, y)
);

CREATE TABLE IF NOT EXISTS buildings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  owner_agent_id INTEGER REFERENCES agents(id),
  status TEXT NOT NULL,
  construction_progress INTEGER NOT NULL DEFAULT 0,
  construction_total_ticks INTEGER NOT NULL,
  built_by_agent_id INTEGER REFERENCES agents(id),
  capacity INTEGER,
  created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workplace_building_id INTEGER NOT NULL REFERENCES buildings(id),
  title TEXT NOT NULL,
  wage_per_shift REAL NOT NULL,
  slots INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS job_assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  agent_id INTEGER NOT NULL REFERENCES agents(id),
  started_tick INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_job_assignments_agent ON job_assignments(agent_id, active);

CREATE TABLE IF NOT EXISTS currency_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL REFERENCES agents(id),
  tick INTEGER NOT NULL,
  amount REAL NOT NULL,
  reason TEXT NOT NULL,
  balance_after REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tick INTEGER NOT NULL,
  sim_datetime TEXT NOT NULL,
  category TEXT NOT NULL,
  agent_id INTEGER REFERENCES agents(id),
  payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_log_tick ON events_log(tick);
