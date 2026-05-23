import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DEFAULT_USER_ID = "local_user"
DEFAULT_USER_NAME = "Utilisateur"
DEFAULT_THREAD_NAME = "Nouvelle conversation"
TEMPERATURE_STEP = 0.1
TOP_P_STEP = 0.05

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff")
DOCUMENT_EXTENSIONS = (".pdf", ".md", ".txt")
MIME_IMAGE_PREFIX = "image/"
MIME_PDF = "application/pdf"
MIME_TEXT_PREFIX = "text/"


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes"}


def _parse_list(key: str, default: list[str]) -> list[str]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    ENV = os.getenv("ENV", "development").strip().lower()

    AUTH_MODE = os.getenv("AUTH_MODE", "none").strip().lower()
    AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")
    PERSISTENCE = os.getenv("PERSISTENCE", "none").strip().lower()
    DEBUG = _env_bool("DEBUG", default=ENV != "production")

    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "20"))
    MAX_DOCUMENT_SIZE_MB = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "2"))
    MAX_FILES = int(os.getenv("MAX_FILES", "3"))

    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    EXA_API_KEY = os.getenv("EXA_API_KEY", "")

    CHAINLIT_AUTH_SECRET = os.getenv("CHAINLIT_AUTH_SECRET")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-oss:120b-cloud")
    DEFAULT_WEB_MODEL = os.getenv("DEFAULT_WEB_MODEL", "gpt-oss:120b-cloud")

    VISION_MODELS = _parse_list("VISION_MODELS", [])
    WEB_SEARCH_MODELS = _parse_list("WEB_SEARCH_MODELS", [])

    WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
    WEB_SEARCH_NUM_CTX = int(os.getenv("WEB_SEARCH_NUM_CTX", "32768"))

    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.4"))
    DEFAULT_TOP_P = float(os.getenv("DEFAULT_TOP_P", "0.9"))
    DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1024"))
    MAX_TOKENS_MIN = 100
    MAX_TOKENS_MAX = 8192
    MAX_TOKENS_STEP = 256

    DEFAULT_NUM_CTX = int(os.getenv("DEFAULT_NUM_CTX", "8192"))
    MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

    MAX_TITLE_LENGTH = 50
    DB_PATH = os.getenv("DB_PATH", "./chainlit.db")

    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Réponds en français, court et factuel.")


config = Config()


def validate_config() -> None:
    auth_mode = os.getenv("AUTH_MODE", "none").strip().lower()
    persistence = os.getenv("PERSISTENCE", "none").strip().lower()
    env = os.getenv("ENV", "development").strip().lower()

    if auth_mode not in {"none", "password"}:
        raise ValueError("AUTH_MODE doit être 'none' ou 'password'")
    if persistence not in {"none", "local"}:
        raise ValueError("PERSISTENCE doit être 'none' ou 'local'")

    if env == "production":
        if not os.getenv("CHAINLIT_AUTH_SECRET"):
            raise ValueError("CHAINLIT_AUTH_SECRET requis en production (chainlit create-secret)")
        if auth_mode != "password":
            raise ValueError("AUTH_MODE=password obligatoire en production")
        if not os.getenv("AUTH_PASSWORD"):
            raise ValueError("AUTH_PASSWORD requis en production")


validate_config()

logger = logging.getLogger("chatbot")
if not logger.handlers:
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(_handler)
