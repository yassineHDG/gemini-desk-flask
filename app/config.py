import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://gemini:gemini_dev_password@127.0.0.1:3306/gemini_chat?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    LOG_FOLDER = BASE_DIR / "logs"
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
