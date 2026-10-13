from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    secure_cookies: bool = False

    database_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
settings = Settings()
