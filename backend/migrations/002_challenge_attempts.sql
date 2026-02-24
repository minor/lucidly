-- =========================================================================
-- Lightweight table to track when a user *starts* a challenge attempt
-- (first turn sent), separate from challenge_sessions which are written
-- on submission.
--
-- Run this in the Supabase SQL Editor.
-- =========================================================================

CREATE TABLE IF NOT EXISTS challenge_attempts (
  id         UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  username   TEXT        NOT NULL,
  challenge_id TEXT      NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ca_user_challenge_date
  ON challenge_attempts (username, challenge_id, created_at);
