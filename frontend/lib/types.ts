export interface TestCase {
  input: string;
  expected_output: string;
}

export interface Challenge {
  id: string;
  title: string;
  description: string;
  category: string;
  difficulty: string;
  target_code: string | null;
  test_suite: TestCase[] | null;
  starter_code: string | null;
  image_url: string | null;
  embed_url: string | null;
  html_url: string | null;
}

export interface Turn {
  turn_number: number;
  prompt_text: string;
  prompt_tokens: number;
  response_text: string;
  response_tokens: number;
  generated_code: string;
  accuracy_at_turn: number;
  timestamp: number;
}

/** One step in the agent thinking trace (agent runs only). */
export interface ThinkingTraceEntry {
  step: string;
  elapsed_ms: number;
  timestamp: number;
  [key: string]: unknown;
}

export interface Session {
  id: string;
  challenge_id: string;
  mode: string;
  status: string;
  model_used: string;
  started_at: number;
  completed_at: number | null;
  total_tokens: number;
  total_turns: number;
  turns: Turn[];
  /** Prompt for the turn currently in progress (show in chat before response is ready) */
  current_prompt?: string | null;
  /** Agent run: ordered list of thinking-trace steps */
  thinking_trace?: ThinkingTraceEntry[];
  accuracy_score: number | null;
  speed_score: number | null;
  token_score: number | null;
  turn_score: number | null;
  composite_score: number | null;
  final_code: string;
  username: string;
}

export interface PromptResponse {
  turn_number: number;
  response_text: string;
  generated_code: string;
  prompt_tokens: number;
  response_tokens: number;
  accuracy: number;
  test_results: boolean[] | null;
}

export interface Scores {
  accuracy_score: number;
  speed_score: number;
  token_score: number;
  turn_score: number;
  composite_score: number;
}

export interface LeaderboardEntry {
  id?: string; // Optional if not always returned by all endpoints, but db has it
  username: string;
  composite_score: number;
  accuracy_score: number;
  speed_score: number;
  challenge_id: string;
  challenge_title?: string;
  total_turns: number;
  total_tokens: number;
  completed_at: number | string; // Supabase returns string
  accuracy?: number; // Raw accuracy
  time_seconds?: number;
  total_cost?: number;
}

export interface Agent {
  id: string;
  name: string;
  strategy: string;
  description: string;
  model: string;
}
