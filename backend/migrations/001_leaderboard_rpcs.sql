-- =========================================================================
-- Leaderboard RPC functions + indexes
--
-- Run this once in the Supabase SQL Editor (or via a migration tool).
-- =========================================================================

-- Indexes for efficient deduplication and aggregation
CREATE INDEX IF NOT EXISTS idx_cs_challenge_user_score
  ON challenge_sessions (challenge_id, username, composite_score DESC);

CREATE INDEX IF NOT EXISTS idx_cs_user_challenge_score
  ON challenge_sessions (username, challenge_id, composite_score DESC);


-- -------------------------------------------------------------------------
-- Per-question leaderboard
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_challenge_leaderboard(
  p_challenge_id TEXT,
  p_limit        INT  DEFAULT 10,
  p_offset       INT  DEFAULT 0,
  p_sort_by      TEXT DEFAULT 'composite_score',
  p_username     TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_result JSONB;
BEGIN
  WITH best_per_user AS (
    -- Keep only the highest-score session per user for this challenge
    SELECT DISTINCT ON (username)
      id, username, composite_score, accuracy, time_seconds,
      total_turns, total_tokens, total_cost,
      accuracy_score, speed_score,
      challenge_id, title, completed_at
    FROM challenge_sessions
    WHERE challenge_id = p_challenge_id
      AND username IS NOT NULL
      AND username <> ''
    ORDER BY username, composite_score DESC
  ),
  ranked AS (
    SELECT *,
      ROW_NUMBER() OVER (
        ORDER BY
          -- Primary sort key
          CASE p_sort_by
            WHEN 'composite_score' THEN -COALESCE(composite_score, 0)::float8
            WHEN 'accuracy'        THEN -COALESCE(accuracy, 0)::float8
            ELSE                        -COALESCE(accuracy, 0)::float8
          END,
          -- Secondary sort key (only matters for time/turns/tokens/cost)
          CASE p_sort_by
            WHEN 'time_seconds'  THEN COALESCE(time_seconds, 999999)::float8
            WHEN 'total_turns'   THEN COALESCE(total_turns, 999999)::float8
            WHEN 'total_tokens'  THEN COALESCE(total_tokens, 999999)::float8
            WHEN 'total_cost'    THEN COALESCE(total_cost, 999999)::float8
            ELSE 0::float8
          END
      ) AS rank
    FROM best_per_user
  ),
  capped AS (
    SELECT * FROM ranked WHERE rank <= 100
  ),
  page AS (
    SELECT * FROM capped ORDER BY rank LIMIT p_limit OFFSET p_offset
  ),
  total AS (
    SELECT COUNT(*)::int AS cnt FROM capped
  ),
  user_rank AS (
    SELECT rank, username, composite_score, accuracy,
           time_seconds, total_turns, total_tokens, total_cost
    FROM ranked
    WHERE p_username IS NOT NULL AND username = p_username
    LIMIT 1
  )
  SELECT
    jsonb_build_object(
      'entries', COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id',              p.id,
            'rank',            p.rank,
            'username',        p.username,
            'composite_score', COALESCE(p.composite_score, 0),
            'accuracy_score',  COALESCE(p.accuracy_score, 0),
            'speed_score',     COALESCE(p.speed_score, 0),
            'accuracy',        p.accuracy,
            'time_seconds',    p.time_seconds,
            'total_turns',     p.total_turns,
            'total_tokens',    p.total_tokens,
            'total_cost',      p.total_cost,
            'challenge_id',    p.challenge_id,
            'challenge_title', p.title,
            'completed_at',    p.completed_at
          ) ORDER BY p.rank
        ) FROM page p
      ), '[]'::jsonb),
      'total_count', (SELECT cnt FROM total)
    )
    || CASE
         WHEN EXISTS (SELECT 1 FROM user_rank)
         THEN jsonb_build_object('user_entry', (
           SELECT jsonb_build_object(
             'rank',            ur.rank,
             'username',        ur.username,
             'composite_score', COALESCE(ur.composite_score, 0),
             'accuracy',        ur.accuracy,
             'time_seconds',    ur.time_seconds,
             'total_turns',     ur.total_turns,
             'total_tokens',    ur.total_tokens,
             'total_cost',      ur.total_cost
           ) FROM user_rank ur
         ))
         ELSE '{}'::jsonb
       END
  INTO v_result;

  RETURN v_result;
END;
$$;


-- -------------------------------------------------------------------------
-- Overall leaderboard (sum of top scores across challenges)
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_overall_leaderboard(
  p_limit    INT  DEFAULT 10,
  p_offset   INT  DEFAULT 0,
  p_username TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_result JSONB;
BEGIN
  WITH best_per_challenge AS (
    SELECT username,
           challenge_id,
           MAX(COALESCE(composite_score, 0)) AS best_score
    FROM challenge_sessions
    WHERE username IS NOT NULL AND username <> ''
    GROUP BY username, challenge_id
  ),
  user_totals AS (
    SELECT username,
           SUM(best_score)::int  AS total_score,
           COUNT(*)::int         AS challenges_completed
    FROM best_per_challenge
    GROUP BY username
  ),
  ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY total_score DESC) AS rank
    FROM user_totals
  ),
  capped AS (
    SELECT * FROM ranked WHERE rank <= 100
  ),
  page AS (
    SELECT * FROM capped ORDER BY rank LIMIT p_limit OFFSET p_offset
  ),
  total AS (
    SELECT COUNT(*)::int AS cnt FROM capped
  ),
  user_rank AS (
    SELECT rank, username, total_score, challenges_completed
    FROM ranked
    WHERE p_username IS NOT NULL AND username = p_username
    LIMIT 1
  )
  SELECT
    jsonb_build_object(
      'entries', COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'rank',                 p.rank,
            'username',             p.username,
            'total_score',          p.total_score,
            'challenges_completed', p.challenges_completed
          ) ORDER BY p.rank
        ) FROM page p
      ), '[]'::jsonb),
      'total_count', (SELECT cnt FROM total)
    )
    || CASE
         WHEN EXISTS (SELECT 1 FROM user_rank)
         THEN jsonb_build_object('user_entry', (
           SELECT jsonb_build_object(
             'rank',                 ur.rank,
             'username',             ur.username,
             'total_score',          ur.total_score,
             'challenges_completed', ur.challenges_completed
           ) FROM user_rank ur
         ))
         ELSE '{}'::jsonb
       END
  INTO v_result;

  RETURN v_result;
END;
$$;
