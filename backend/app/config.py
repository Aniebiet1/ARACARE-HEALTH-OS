from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACARE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./aracare.db"
    secret_key: str = "dev-secret-change-me"
    token_ttl_hours: int = 12
    data_dir: str = "./data"

    facility_name: str = "General Hospital Ikeja"
    state_code: str = "LAG"

    # queue engine
    call_timeout_seconds: int = 180        # 3-minute "you've been called" window
    noshow_grace_seconds: int = 1800       # 30-minute grace before cancelling
    aging_p2_minutes: int = 45
    aging_p3_minutes: int = 90
    p1_burst_limit: int = 3
    p2_burst_limit: int = 5

    # AI scribe (all local)
    asr_engine: str = "auto"               # auto | faster-whisper | none
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute: str = "int8"
    llm_engine: str = "auto"               # auto | ollama | rules
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: int = 120


settings = Settings()
