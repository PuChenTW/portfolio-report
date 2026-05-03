from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # File paths
    portfolio_csv_path: str = "./portfolio.csv"
    watchlist_csv_path: str = "./watchlist.csv"
    price_alerts_path: str = "./price-alerts.yml"
    researcher_memory_path: str = "./memory"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # API keys
    tavily_api_key: str = ""
    google_api_key: str = ""

    # Models
    chat_model: str = "google-gla:gemini-3-flash-preview"
    research_model: str = "google-gla:gemini-3-pro-preview"


settings = Settings()
