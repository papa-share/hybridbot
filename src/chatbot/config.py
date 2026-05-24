import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

TEMPERATURE_STEP = 0.1
TOP_P_STEP = 0.05

TEXT_EXTENSIONS = (".md", ".txt")
MIME_IMAGE_PREFIX = "image/"
MIME_PDF = "application/pdf"
MIME_TEXT_PREFIX = "text/"


def file_is_pdf_bytes(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False


def is_pdf_source(*, path: str = "", mime: str = "", name: str = "") -> bool:
    if mime == MIME_PDF:
        return True
    for value in (path, name):
        if value.lower().endswith(".pdf"):
            return True
    return file_is_pdf_bytes(path)


def is_text_document_source(*, path: str = "", mime: str = "", name: str = "") -> bool:
    if mime.startswith(MIME_TEXT_PREFIX):
        return True
    for value in (path, name):
        if value.lower().endswith(TEXT_EXTENSIONS):
            return True
    return False


def is_document_source(*, path: str = "", mime: str = "", name: str = "") -> bool:
    return is_pdf_source(path=path, mime=mime, name=name) or is_text_document_source(
        path=path, mime=mime, name=name
    )


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
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    DEBUG = _env_bool("DEBUG", default=ENV != "production")

    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "50"))
    MAX_DOCUMENT_SIZE_MB = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "50"))
    MAX_FILES = int(os.getenv("MAX_FILES", "5"))

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

    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Réponds en français, court et factuel.")


config = Config()


def validate_config() -> None:
    if config.AUTH_MODE not in {"none", "password"}:
        raise ValueError("AUTH_MODE doit être 'none' ou 'password'")

    if config.ENV == "production":
        if not config.DATABASE_URL:
            raise ValueError("DATABASE_URL requis en production")
        if not config.CHAINLIT_AUTH_SECRET:
            raise ValueError(
                "CHAINLIT_AUTH_SECRET requis en production (uv run python -m chainlit create-secret)"
            )
        if config.AUTH_MODE != "password":
            raise ValueError("AUTH_MODE=password obligatoire en production")


validate_config()

logger = logging.getLogger("chatbot")
if not logger.handlers:
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(_handler)
