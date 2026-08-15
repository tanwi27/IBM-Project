import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Resume Screener"
    API_V1_STR: str = "/api/v1"
    
    # LLM Settings
    # Supports "gemini", "anthropic", "openai"
    PRIMARY_LLM_PROVIDER: str = "openai"  
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    VOYAGE_API_KEY: Optional[str] = None
    
    # Default Models
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20240620"
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # Embedding Model (Voyage or local fallback)
    EMBEDDING_PROVIDER: str = "local"  # "local" | "openai" | "gemini" | "voyage"
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
