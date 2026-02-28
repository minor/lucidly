-- =========================================================================
-- Migration 002: Backfill display usernames in challenge_sessions
--
-- Problem: challenge_sessions.username was previously stored as the raw
-- Auth0 user ID (e.g. "auth0|abc123") instead of the chosen display name.
-- This migration replaces those IDs with the display name from the
-- usernames table, wherever a mapping exists.
--
-- Safe to run multiple times (the WHERE clause is idempotent).
-- Run this once in the Supabase SQL Editor.
-- =========================================================================

UPDATE challenge_sessions cs
SET username = u.username
FROM usernames u
WHERE cs.username = u.auth0_id     -- row still holds the raw Auth0 ID
  AND cs.username <> u.username;   -- skip rows already correct (no-op guard)
