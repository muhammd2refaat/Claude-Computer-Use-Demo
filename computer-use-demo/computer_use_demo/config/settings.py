"""Application Settings - Configuration Management."""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # API Configuration
    APP_NAME: str = "Computer Use API"
    DEBUG: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    API_VERSION: str = "1.0.0"

    # Anthropic API
    ANTHROPIC_API_KEY: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    ANTHROPIC_BASE_URL: str = field(default_factory=lambda: os.getenv("ANTHROPIC_BASE_URL", ""))
    ANTHROPIC_MODEL: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"))

    # Gemini API (alternative)
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    # Database
    DB_PATH: str = field(default_factory=lambda: os.getenv("DB_PATH", "/data/sessions.db"))
    DB_POOL_MIN_SIZE: int = field(default_factory=lambda: int(os.getenv("DB_POOL_MIN_SIZE", "2")))
    DB_POOL_MAX_SIZE: int = field(default_factory=lambda: int(os.getenv("DB_POOL_MAX_SIZE", "10")))
    DB_POOL_ACQUIRE_TIMEOUT: float = field(default_factory=lambda: float(os.getenv("DB_POOL_ACQUIRE_TIMEOUT", "30.0")))

    # Display Configuration
    WIDTH: int = field(default_factory=lambda: int(os.getenv("WIDTH", "1024")))
    HEIGHT: int = field(default_factory=lambda: int(os.getenv("HEIGHT", "768")))
    BASE_DISPLAY_NUM: int = 100
    BASE_VNC_PORT: int = 5810
    BASE_WS_PORT: int = 5910

    # Agent Configuration
    DEFAULT_MAX_TOKENS: int = 4096 * 4
    DEFAULT_TOOL_VERSION: str = "computer_use_20250124"

    # CORS
    ALLOWED_ORIGINS: List[str] = field(default_factory=lambda: ["*"])

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FORMAT: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "dual"))  # console, json, or dual
    LOG_DIR: str = field(default_factory=lambda: os.getenv("LOG_DIR", "/data/logs"))
    LOG_MAX_SIZE_MB: int = field(default_factory=lambda: int(os.getenv("LOG_MAX_SIZE_MB", "10")))
    LOG_BACKUP_COUNT: int = field(default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5")))

    # Logging Feature Flags
    ENABLE_PERFORMANCE_LOGGING: bool = field(
        default_factory=lambda: os.getenv("ENABLE_PERFORMANCE_LOGGING", "true").lower() == "true"
    )
    ENABLE_DATABASE_QUERY_LOGGING: bool = field(
        default_factory=lambda: os.getenv("ENABLE_DATABASE_QUERY_LOGGING", "true").lower() == "true"
    )
    ENABLE_API_REQUEST_LOGGING: bool = field(
        default_factory=lambda: os.getenv("ENABLE_API_REQUEST_LOGGING", "true").lower() == "true"
    )
    ENABLE_TOOL_EXECUTION_LOGGING: bool = field(
        default_factory=lambda: os.getenv("ENABLE_TOOL_EXECUTION_LOGGING", "true").lower() == "true"
    )

    def get_api_key(self) -> str:
        """Get the primary API key (Anthropic or Gemini)."""
        return self.ANTHROPIC_API_KEY or self.GEMINI_API_KEY

    def is_using_gemini(self) -> bool:
        """Check if using Gemini API."""
        api_key = self.get_api_key()
        return api_key.startswith("AIza") if api_key else False


# Global settings instance
settings = Settings()
