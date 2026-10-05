"""
Application configuration for FinReq AI Backend.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FinReq AI — Requirement Engineer"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    ENV: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./storage/finreq.db"

    # Storage
    STORAGE_DIR: str = "./storage"
    STORAGE_UPLOADS_DIR: str = "./storage/uploads"
    STORAGE_GENERATED_DIR: str = "./storage/generated"

    # Security & Session
    SESSION_COOKIE_NAME: str = "anon_session_token"
    SESSION_COOKIE_MAX_AGE: int = 60 * 60 * 24 * 30  # 30 days
    SESSION_SECRET: str = "finreq-development-secret-key-change-in-prod"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()

# Ensure directories exist
os.makedirs(settings.STORAGE_UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.STORAGE_GENERATED_DIR, exist_ok=True)
