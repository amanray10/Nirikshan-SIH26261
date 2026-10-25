"""Central configuration. Every value can be overridden with an environment variable or backend/.env."""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
# tzlocal (used by pyhanko) rejects the legacy name Asia/Calcutta that some Linux images set.
if os.environ.get("TZ") in ("Asia/Calcutta", "IST"):
    os.environ["TZ"] = "Asia/Kolkata"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    app_name: str = "Nirikshan"
    # SQLite works out of the box; for MySQL use e.g.
    # mysql+pymysql://nirikshan:password@localhost:3306/nirikshan
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'nirikshan.db').as_posix()}"

    secret_key: str = "change-me-in-production-please-32+chars"
    token_minutes: int = 480
    # Salt for hashing faculty identifiers (PAN/Aadhaar). Raw IDs are never stored.
    id_hash_salt: str = "nirikshan-demo-salt"

    data_dir: Path = BACKEND_DIR / "data"
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_mb: int = 25

    # "auto" picks the best available engine; see services/ocr.py, retrieval.py, llm.py
    ocr_backend: str = "auto"          # auto | paddle | tesseract | none
    embedding_backend: str = "auto"    # auto | bge-m3 | tfidf
    llm_backend: str = "auto"          # auto | ollama | none
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    tesseract_cmd: str = ""            # e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe

    aph_edition: str = "APH 2024-27"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
