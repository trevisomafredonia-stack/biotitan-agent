from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Opzionale: serve solo all'agente Bandi (lettura capitolati).
    # Lo Scraper Aziende funziona anche senza.
    anthropic_api_key: Optional[str] = None
    match_autoconfirm_threshold: int = 50
    scan_interval_hours: int = 12
    crm_api_token: str = "biotitan-crm-token"

    class Config:
        env_file = ".env"


settings = Settings()
