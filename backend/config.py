from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # LLM provider configuration
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-5.2"
    """Model used for vision-based UI replication (screenshot → code). Should be vision-capable (e.g. gpt-4o, claude-3-5-sonnet)."""
    vision_model: str = "gpt-4o"
    max_tokens: int = 16384
    
    # Anthropic/Claude configuration
    anthropic_api_key: str = ""

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Scoring defaults (medians for normalization)
    median_time_sec: float = 120.0
    median_tokens: int = 500
    median_turns: int = 4

    # Difficulty-based baselines
    SCORING_BASELINES: dict = {
        "easy": {"time": 30.0, "tokens": 200, "turns": 2},
        "medium": {"time": 120.0, "tokens": 500, "turns": 4},
        "hard": {"time": 300.0, "tokens": 1000, "turns": 8},
    }

    # Browserbase / Stagehand (optional: for agent view_reference_page tool)
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    # Supabase (Leaderboard & Logs)
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Agent / Modal (for benchmark runs)
    agent_internal_secret: str = ""
    modal_app_name: str = "lucidly-agent"
    max_completion_tokens_agent: int = 16384  # per-turn limit; 16k allows full HTML landing pages without truncation
    backend_public_url: str = "http://localhost:8000"  # URL Modal worker uses to call back
    use_inprocess_agent: bool = True  # If True, run agent in backend (no Modal). Set False and deploy Modal for cloud.

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()


# Pricing (per 1M tokens)
MODEL_PRICING = {
    # Anthropic
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    # OpenAI
    "gpt-5.2": {"input": 1.75, "output": 14.0},
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
}
