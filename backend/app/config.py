from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACARE_", env_file=".env", extra="ignore")

    env: str = "development"               # development | production
    database_url: str = "sqlite:///./aracare.db"
    secret_key: str = DEV_SECRET
    token_ttl_hours: int = 12
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"   # comma separated
    enable_docs: bool = True               # /docs and /openapi.json
    log_level: str = "INFO"

    facility_name: str = "General Hospital Ikeja"
    state_code: str = "LAG"
    timezone: str = "Africa/Lagos"         # queue days and patient-number years roll over at local midnight
    # production has no demo accounts: the first admin is created from this, then it can be unset
    admin_password: str | None = None

    # security limits
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    password_min_length: int = 8
    max_photo_mb: int = 5
    max_audio_mb: int = 25

    # queue engine
    call_timeout_seconds: int = 180        # 3-minute "you've been called" window
    noshow_grace_seconds: int = 1800       # 30-minute grace before cancelling
    aging_p2_minutes: int = 45
    aging_p3_minutes: int = 90
    p1_burst_limit: int = 3
    p2_burst_limit: int = 5
    sweep_interval_seconds: int = 15
    # waiting-time estimates on the TV fall back to these until a department has served a few patients today
    est_triage_minutes: int = 5
    est_opd_minutes: int = 12

    # AraPulse (internal comms): unacknowledged emergency pages widen to every on-duty doctor, then all doctors
    page_escalate_seconds: int = 120
    critical_result_escalate_minutes: int = 10

    # AI scribe (all local)
    asr_engine: str = "auto"               # auto | faster-whisper | none
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute: str = "int8"
    whisper_beam_size: int = 1             # 1 = greedy: ~2-3x faster on CPU than beam search, near-identical text
    llm_engine: str = "auto"               # auto | ollama | rules
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: int = 120
    ollama_keep_alive: str = "24h"         # keep the model in RAM; reloading it costs ~20 s on a laptop CPU
    scribe_warmup: bool = True             # load Whisper + the LLM at startup so the first dictation isn't slow

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def check(self) -> None:
        """Refuse to boot a production server with settings that would be unsafe."""
        if self.env not in ("development", "production"):
            raise RuntimeError("ARACARE_ENV must be 'development' or 'production'")
        if not self.is_production:
            return
        problems = []
        if self.secret_key == DEV_SECRET or len(self.secret_key) < 32:
            problems.append("ARACARE_SECRET_KEY must be set to a random value of at least 32 characters "
                            "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")")
        if "*" in self.cors_origin_list:
            problems.append("ARACARE_CORS_ORIGINS must list the web client's origin(s), not '*'")
        if problems:
            raise RuntimeError("Unsafe production configuration:\n  - " + "\n  - ".join(problems))


settings = Settings()
