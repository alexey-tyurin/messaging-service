"""
Application configuration management using Pydantic Settings.
Supports environment variables and .env files for configuration.
"""

from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn, validator
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application Settings
    app_name: str = "Messaging Service"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # API Settings
    api_prefix: str = "/api/v1"
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=4, env="WORKERS")
    
    # Security
    secret_key: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database Settings
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_user: str = Field(default="messaging_user", env="POSTGRES_USER")
    postgres_password: str = Field(default="messaging_password", env="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="messaging_service", env="POSTGRES_DB")
    database_url: Optional[PostgresDsn] = None
    
    # Database Pool Settings
    db_pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=40, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    
    # Redis Settings
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_url: Optional[RedisDsn] = None
    
    # Redis Pool Settings
    redis_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    redis_pool_timeout: int = Field(default=30, env="REDIS_POOL_TIMEOUT")
    
    # Message Queue Settings
    queue_max_retries: int = Field(default=3, env="QUEUE_MAX_RETRIES")
    queue_retry_delay: int = Field(default=60, env="QUEUE_RETRY_DELAY")
    queue_batch_size: int = Field(default=100, env="QUEUE_BATCH_SIZE")
    
    # Provider Settings
    sms_provider_timeout: int = Field(default=30, env="SMS_PROVIDER_TIMEOUT")
    email_provider_timeout: int = Field(default=30, env="EMAIL_PROVIDER_TIMEOUT")
    provider_max_retries: int = Field(default=3, env="PROVIDER_MAX_RETRIES")
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")
    
    # Observability
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    # CORS Settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(default=["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: list[str] = Field(default=["*"], env="CORS_ALLOW_HEADERS")
    
    # Webhook Settings
    webhook_secret: str = Field(default="webhook-secret", env="WEBHOOK_SECRET")
    webhook_timeout: int = Field(default=10, env="WEBHOOK_TIMEOUT")
    
    # Feature Flags
    enable_attachment_scanning: bool = Field(default=True, env="ENABLE_ATTACHMENT_SCANNING")
    
    # Processing Mode
    sync_message_processing: bool = Field(default=True, env="SYNC_MESSAGE_PROCESSING")  # Process messages immediately instead of queuing
    
    @validator("database_url", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.get("postgres_user"),
            password=values.get("postgres_password"),
            host=values.get("postgres_host"),
            port=int(values.get("postgres_port", 5432)),
            path=f"{values.get('postgres_db') or ''}",
        )
    
    @validator("redis_url", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        password = values.get("redis_password")
        if password:
            return RedisDsn.build(
                scheme="redis",
                username="",
                password=password,
                host=values.get("redis_host"),
                port=int(values.get("redis_port", 6379)),
                path=f"{values.get('redis_db') or 0}",
            )
        return RedisDsn.build(
            scheme="redis",
            host=values.get("redis_host"),
            port=int(values.get("redis_port", 6379)),
            path=f"{values.get('redis_db') or 0}",
        )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance
settings = get_settings()
