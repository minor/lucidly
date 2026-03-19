CREATE TABLE IF NOT EXISTS user_integrations (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       TEXT        NOT NULL,
  provider      TEXT        NOT NULL CHECK (provider IN ('linear', 'github')),
  access_token  TEXT        NOT NULL,
  refresh_token TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, provider)
);
