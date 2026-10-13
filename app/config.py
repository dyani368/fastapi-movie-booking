from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    secure_cookies: bool = False

    database_url: str
    plivo_auth_id: str | None = None
    plivo_auth_token: SecretStr | None = None
    plivo_source_number: str | None = None
    plivo_status_callback_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
settings = Settings()
