-- Dog-Care-Brain slice 1. One SQLite file, one business_id on every care row.
CREATE TABLE IF NOT EXISTS business (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  created INTEGER NOT NULL,
  imported INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL DEFAULT 'owner',
  business_id INTEGER NOT NULL REFERENCES business(id),
  created INTEGER NOT NULL,
  last_seen INTEGER
);

CREATE TABLE IF NOT EXISTS dog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  business_id INTEGER NOT NULL REFERENCES business(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  profile_json TEXT NOT NULL DEFAULT '{}',
  created INTEGER NOT NULL,
  UNIQUE(business_id, slug)
);

CREATE TABLE IF NOT EXISTS observation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  business_id INTEGER NOT NULL REFERENCES business(id),
  dog_id INTEGER NOT NULL REFERENCES dog(id),
  author_id INTEGER REFERENCES user(id),
  client_id INTEGER,
  text TEXT NOT NULL,
  title TEXT,
  tags TEXT NOT NULL DEFAULT '[]',
  time TEXT,
  date TEXT,
  voice_blob_ref TEXT,
  audio_json TEXT,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS invite (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  business_id INTEGER NOT NULL REFERENCES business(id),
  token TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  name TEXT,
  role TEXT,
  areas TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending',
  created INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS magic (
  th TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  created INTEGER NOT NULL,
  expires INTEGER NOT NULL,
  used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session (
  sh TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES user(id),
  created INTEGER NOT NULL,
  expires INTEGER NOT NULL
);

-- Slice 2 will flip this. Empty in slice 1; no prices live here.
CREATE TABLE IF NOT EXISTS entitlement (
  business_id INTEGER PRIMARY KEY REFERENCES business(id),
  tier TEXT,
  status TEXT,
  period_end INTEGER,
  source TEXT
);

CREATE TABLE IF NOT EXISTS pref (
  user_id INTEGER PRIMARY KEY REFERENCES user(id),
  language TEXT NOT NULL DEFAULT 'en'
);
