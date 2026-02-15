-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Table for storing challenge sessions (scores + metadata)
create table if not exists challenge_sessions (
  id uuid primary key default uuid_generate_v4(),
  challenge_id text not null,
  title text not null,
  category text not null,
  difficulty text not null,
  model text not null,
  username text not null,
  
  -- Stats
  accuracy float not null,
  time_seconds float not null,
  total_tokens int not null,
  total_turns int not null,
  total_cost float not null,
  
  -- Scores (normalized 0-1000)
  composite_score int not null,
  accuracy_score int not null,
  speed_score int not null,
  token_score int not null,
  turn_score int not null,
  
  created_at timestamptz default now(),
  completed_at timestamptz default now()
);

-- Table for conversation logs (linked to session)
create table if not exists conversation_logs (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid references challenge_sessions(id) on delete cascade,
  role text not null, -- 'user' or 'assistant'
  content text not null,
  turn_number int not null,
  timestamp timestamptz default now()
);

-- Index for leaderboard queries
create index if not exists idx_sessions_composite on challenge_sessions(composite_score desc);
create index if not exists idx_sessions_challenge on challenge_sessions(challenge_id);

-- Additional indices for filtering/sorting by specific metrics within a challenge
create index if not exists idx_sessions_accuracy on challenge_sessions(challenge_id, accuracy desc);
create index if not exists idx_sessions_time on challenge_sessions(challenge_id, time_seconds asc);
create index if not exists idx_sessions_tokens on challenge_sessions(challenge_id, total_tokens asc);
create index if not exists idx_sessions_turns on challenge_sessions(challenge_id, total_turns asc);
create index if not exists idx_sessions_cost on challenge_sessions(challenge_id, total_cost asc);
create index if not exists idx_sessions_recent on challenge_sessions(challenge_id, created_at desc);
