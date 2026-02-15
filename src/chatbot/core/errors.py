"""Gestion centralisée des erreurs Ollama."""

from chatbot.messages import (
    ERROR_400,
    ERROR_404,
    ERROR_CONNECTION,
    ERROR_GENERIC,
    ERROR_TIMEOUT,
)


def get_ollama_error_message(error: Exception, model_name: str = "") -> str:
    """
    Convertit les erreurs Ollama en messages utilisateur clairs.

    Analyse le message d'erreur technique et retourne un message
    compréhensible avec des suggestions de résolution.

    Args:
        error: Exception levée par Ollama
        model_name: Nom du modèle (utilisé dans le message 404)

    Returns:
        Message d'erreur localisé et actionnable pour l'utilisateur
    """
    error_msg = str(error).lower()
    error_str = str(error)

    if "400" in error_str or "bad request" in error_msg:
        return ERROR_400
    elif "404" in error_str or "not found" in error_msg:
        return ERROR_404.format(model=model_name)
    elif "connection" in error_msg or "refused" in error_msg:
        return ERROR_CONNECTION
    elif "timeout" in error_msg:
        return ERROR_TIMEOUT
    elif "500" in error_str or "internal server error" in error_msg:
        return ERROR_500
    else:
        return ERROR_GENERIC.format(error=error_str)
