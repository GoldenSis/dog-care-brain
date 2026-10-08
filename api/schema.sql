-- Dog-Care-Brain slice 1. Business-scoped care data; preferences belong to users.
CREATE TABLE IF NOT EXISTS business (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  created INTEGER NOT NULL,
  imported INTEGER NOT NULL DEFAULT 0, -- Import eligibility closed by import or care write.
  revision INTEGER NOT NULL DEFAULT 0 -- Optimistic concurrency counter for care snapshots.
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

-- Additive operational records; existing accounts start without invented activity.
CREATE TABLE IF NOT EXISTS business_daily (
  business_id INTEGER PRIMARY KEY REFERENCES business(id),
  snapshot TEXT NOT NULL
);

-- Never exposed through the public static tree; downloads require the owning account.
CREATE TABLE IF NOT EXISTS daily_document (
  business_id INTEGER NOT NULL REFERENCES business(id),
  id TEXT NOT NULL,
  mime TEXT NOT NULL,
  contents BLOB NOT NULL,
  PRIMARY KEY (business_id, id)
);

-- User-entered experience remains private and separate from sourced education.
CREATE TABLE IF NOT EXISTS business_knowledge (
  business_id INTEGER PRIMARY KEY REFERENCES business(id),
  snapshot TEXT NOT NULL
);

-- Private accounting originals are immutable and scoped to their business.
CREATE TABLE IF NOT EXISTS business_finance (
  business_id INTEGER PRIMARY KEY REFERENCES business(id),
  snapshot TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS finance_document (
  business_id INTEGER NOT NULL REFERENCES business(id),
  id TEXT NOT NULL,
  mime TEXT NOT NULL,
  contents BLOB NOT NULL,
  PRIMARY KEY (business_id, id)
);

-- Client membership is explicit; old accounts and care records stay internal.
CREATE TABLE IF NOT EXISTS client_access (
  user_id INTEGER PRIMARY KEY REFERENCES user(id),
  business_id INTEGER NOT NULL REFERENCES business(id),
  client_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS client_update (
  id TEXT PRIMARY KEY,
  business_id INTEGER NOT NULL REFERENCES business(id),
  dog_id TEXT NOT NULL,
  client_id TEXT,
  author_id INTEGER NOT NULL REFERENCES user(id),
  text TEXT NOT NULL,
  created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS booking_request (
  id TEXT PRIMARY KEY,
  business_id INTEGER NOT NULL REFERENCES business(id),
  user_id INTEGER NOT NULL REFERENCES user(id),
  dog_id TEXT NOT NULL,
  client_id TEXT,
  service TEXT NOT NULL,
  start TEXT NOT NULL,
  end TEXT NOT NULL,
  note TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'requested',
  created INTEGER NOT NULL
);
-- Explicitly client-facing files. Health and accounting originals stay separate.
CREATE TABLE IF NOT EXISTS client_document (
  id TEXT PRIMARY KEY,
  business_id INTEGER NOT NULL REFERENCES business(id),
  dog_id TEXT NOT NULL,
  client_id TEXT,
  label TEXT NOT NULL,
  name TEXT NOT NULL,
  mime TEXT NOT NULL,
  contents BLOB NOT NULL
);

-- Quote values never rewrite issued invoices or execute payments.
CREATE TABLE IF NOT EXISTS request_quote (
  business_id INTEGER NOT NULL REFERENCES business(id),
  id TEXT NOT NULL,
  unit_minor INTEGER,
  currency TEXT NOT NULL,
  PRIMARY KEY (business_id, id)
);
CREATE TABLE IF NOT EXISTS booking_extra (
  business_id INTEGER NOT NULL REFERENCES business(id),
  target_id TEXT NOT NULL,
  id TEXT NOT NULL,
  label TEXT NOT NULL,
  unit_minor INTEGER NOT NULL,
  currency TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  PRIMARY KEY (business_id, id)
);
CREATE TABLE IF NOT EXISTS extra_template (
  business_id INTEGER NOT NULL REFERENCES business(id),
  id TEXT NOT NULL,
  label TEXT NOT NULL,
  unit_minor INTEGER NOT NULL,
  currency TEXT NOT NULL,
  PRIMARY KEY (business_id, id),
  UNIQUE (business_id, label, currency)
);
CREATE TABLE IF NOT EXISTS login_attempt (
  key TEXT PRIMARY KEY,
  started INTEGER NOT NULL,
  count INTEGER NOT NULL
);

-- Immutable family audience for saved bookings, even if a dog is reassigned later.
CREATE TABLE IF NOT EXISTS booking_client (
  business_id INTEGER NOT NULL REFERENCES business(id),
  id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  PRIMARY KEY (business_id,id)
);

CREATE TABLE IF NOT EXISTS media_asset (
  id TEXT PRIMARY KEY,
  business_id INTEGER NOT NULL REFERENCES business(id),
  dog_id TEXT,
  client_id TEXT,
  purpose TEXT NOT NULL CHECK (purpose IN ('dog','branding')),
  mime TEXT NOT NULL,
  name TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  contents BLOB NOT NULL,
  created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS media_business ON media_asset(business_id);
CREATE TABLE IF NOT EXISTS dog_cover (
  business_id INTEGER NOT NULL REFERENCES business(id),
  dog_id TEXT NOT NULL,
  media_id TEXT NOT NULL REFERENCES media_asset(id),
  PRIMARY KEY (business_id,dog_id)
);
CREATE TABLE IF NOT EXISTS business_branding (
  business_id INTEGER PRIMARY KEY REFERENCES business(id),
  snapshot TEXT NOT NULL
);
