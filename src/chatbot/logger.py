"""Configuration du logger."""

import logging
import sys

from chatbot.config import config


def setup_logger(name: str = "chatbot") -> logging.Logger:
    """
    Configure et retourne un logger structuré.

    Le niveau de log et le format sont adaptés selon le mode DEBUG.
    En mode DEBUG : logs détaillés avec nom de fonction et numéro de ligne.
    En mode production : logs concis avec timestamp et niveau uniquement.

    Args:
        name: Nom du logger (par défaut "chatbot")

    Returns:
        Logger configuré et prêt à l'emploi
    """
    logger = logging.getLogger(name)

    # Éviter d'ajouter plusieurs handlers si le logger existe déjà
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    if config.DEBUG:
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logger()
