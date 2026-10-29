from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    secure_cookies: bool = False

    database_url: str
    tmdb_api_key: SecretStr | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:5173/oauth/callback"
    frontend_url: str = "http://localhost:5173"
    booking_hold_minutes: int = Field(default=10, ge=1, le=30)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
settings = Settings()
