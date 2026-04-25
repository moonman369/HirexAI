from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HirexAI Backend"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 60 * 24

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "hirexai"

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_linkedin_client_id: str = ""
    oauth_linkedin_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
