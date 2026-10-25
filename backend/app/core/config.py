import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Root project paths
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# Guarantee project root is in sys.path so imports never fail regardless of working directory
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

class Settings(BaseSettings):
    APP_NAME: str = "Banking Transaction Monitoring System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_PORT: int = 8000

    # Database Configuration
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "banking_fraud_monitoring"
    DB_URL: str | None = None  # Optional override

    # Scoring Bounds
    MAX_RISK_SCORE: int = 100
    LOW_RISK_MAX: int = 29
    MEDIUM_RISK_MAX: int = 59
    HIGH_RISK_MAX: int = 79
    CRITICAL_RISK_MIN: int = 80

    # CORS
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500"

    model_config = {
        "env_file": os.path.join(BACKEND_DIR, ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    def get_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def get_database_url(self) -> str:
        if self.DB_URL:
            # If a relative SQLite path is configured, make it absolute relative to PROJECT_DIR
            # so the application works seamlessly regardless of the working directory
            if self.DB_URL.startswith("sqlite:///./") or self.DB_URL.startswith("sqlite:////."):
                rel_path = self.DB_URL.split("sqlite:///", 1)[-1].lstrip("./")
                abs_path = (PROJECT_DIR / rel_path).resolve().as_posix()
                return f"sqlite:///{abs_path}"
            return self.DB_URL
        # PyMySQL connection string
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

settings = Settings()
