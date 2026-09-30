from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./nagari.db"

    notify_email: str = "nagarischoolsystem@gmail.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Preferred in production: an HTTPS email API. Many hosts (including Render free)
    # block SMTP ports, but HTTPS always works. If set, this is used instead of SMTP.
    resend_api_key: str = ""
    resend_from: str = "Nagari Website <onboarding@resend.dev>"

    cors_origins: str = "http://localhost:3000"
    admin_api_key: str = ""
    rate_limit_per_hour: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
