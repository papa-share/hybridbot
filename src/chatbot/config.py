"""Configuration centralisée de l'application."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration de base."""

    # Modes d'authentification et persistance
    AUTH_MODE = os.getenv("AUTH_MODE", "none").strip().lower()
    PERSISTENCE = os.getenv("PERSISTENCE", "none").strip().lower()
    DEBUG = os.getenv("DEBUG", "0").lower() in {"1", "true", "yes"}

    # Limites de fichiers
    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "20"))
    MAX_DOCUMENT_SIZE_MB = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "2"))
    MAX_FILES = int(os.getenv("MAX_FILES", "3"))

    # Timeouts et performance
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))  # secondes
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    # Sécurité
    CHAINLIT_AUTH_SECRET = os.getenv("CHAINLIT_AUTH_SECRET")

    # Modèles IA
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-oss:120b-cloud")

    # Modèles vision (supportent l'analyse d'images)
    # Note : Certains modèles vision cloud apparaissent aussi dans KNOWN_CLOUD_MODELS
    # car ils sont à la fois capables de vision et disponibles en mode cloud
    VISION_MODELS = [
        "qwen3-vl:235b-instruct-cloud",
        "qwen3-vl:235b-cloud",
        "glm-4.6:cloud",
        "llava:latest",
        "llava:13b",
        "llava:7b",
        "bakllava:latest",
    ]

    # Modèles cloud connus (fallback si ollama list échoue)
    KNOWN_CLOUD_MODELS = [
        "gpt-oss:120b-cloud",
        "kimi-k2:1t-cloud",
        "qwen3-coder:480b-cloud",
        "deepseek-v3.1:671b-cloud",
        "glm-4.6:cloud",
        "qwen3-vl:235b-instruct-cloud",
    ]

    # Paramètres LLM par défaut et plages (centralisés)
    DEFAULT_TEMPERATURE = 0.4
    DEFAULT_TOP_P = 0.9
    DEFAULT_MAX_TOKENS = 1024
    MAX_TOKENS_MIN = 100
    MAX_TOKENS_MAX = 8192
    MAX_TOKENS_STEP = 256

    # Ollama
    DEFAULT_NUM_CTX = 8192
    TRUNCATION_THRESHOLD_OFFSET = 10
    MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

    # UI et DB
    MAX_TITLE_LENGTH = 50
    DEFAULT_PAGINATION_LIMIT = 20
    DEFAULT_DB_PATH = "./chainlit.db"

    # Prompt système optimisé
    SYSTEM_PROMPT = (
        "Tu es un assistant IA expert, polyvalent et adaptatif. Tu possèdes des connaissances "
        "approfondies dans de nombreux domaines : sciences, technologie, programmation, "
        "médecine, droit, économie, histoire, arts, littérature, philosophie, actualités, "
        "sport, culture, et bien d'autres. Tu peux analyser des images, résoudre des problèmes "
        "complexes, expliquer des concepts techniques, aider avec du code, donner des conseils "
        "pratiques, et répondre à des questions variées. Tu réponds toujours en français de "
        "manière claire, précise, détaillée et adaptative. Tu adaptes ton niveau d'explication "
        "selon la question posée et le contexte.\n\n"
        "NEUTRALITE ET EGALITE DE TRAITEMENT:\n"
        "Tu traites TOUTES les questions de manière égale et sans biais, que ce soit "
        "sport, technologie, science, politique, économie, culture, actualités, personnes "
        "publiques, événements historiques ou récents, ou tout autre domaine. Chaque question "
        "mérite la même rigueur et attention.\n\n"
        "REGLES ANTI-HALLUCINATION:\n"
        "1. Ne JAMAIS inventer de faits, dates, chiffres, noms ou détails non vérifiés.\n"
        "2. Utilise tes connaissances générales pour répondre, mais indique clairement quand "
        "tu n'es pas certain ou quand tes connaissances peuvent être limitées.\n"
        "3. Si tu ne connais pas une information spécifique, dis-le honnêtement plutôt que "
        "d'inventer.\n"
        "4. Pour les événements très récents ou actualités, indique que tes connaissances "
        "peuvent être limitées par ta date de formation.\n\n"
        "ADAPTABILITE:\n"
        "1. Adapte ta réponse selon le type de question: questions factuelles nécessitent des "
        "réponses précises, questions conceptuelles peuvent être plus exploratoires.\n"
        "2. Sois utile: plutôt que de dire simplement 'je ne sais pas', essaie de fournir "
        "ce qui est disponible et indique les limites.\n"
        "3. Structure tes réponses de manière claire et organisée."
    )


class ProductionConfig(Config):
    """Configuration pour la production."""

    DEBUG = False
    AUTH_MODE = "password"
    MAX_IMAGE_SIZE_MB = 20
    MAX_DOCUMENT_SIZE_MB = 2
    MAX_FILES = 3


class DevelopmentConfig(Config):
    """Configuration pour le développement."""

    DEBUG = True


ENV = os.getenv("ENV", "development").lower()
config = ProductionConfig() if ENV == "production" else DevelopmentConfig()
if ENV == "production":
    if not config.CHAINLIT_AUTH_SECRET:
        raise ValueError(
            "CHAINLIT_AUTH_SECRET est requis en production. "
            "Générez-en un avec: chainlit create-secret"
        )
    if config.AUTH_MODE == "none":
        raise ValueError(
            "L'authentification est obligatoire en production. "
            "Définissez AUTH_MODE=password dans votre fichier .env"
        )
