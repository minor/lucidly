from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # LLM provider configuration
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o"
    
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

    # Agent / Modal (for benchmark runs)
    agent_internal_secret: str = ""
    modal_app_name: str = "lucidly-agent"
    backend_public_url: str = "http://localhost:8000"  # URL Modal worker uses to call back

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
