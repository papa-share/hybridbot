"""Validation des fichiers uploadés."""

import os

from chatbot.config import config
from chatbot.constants import MIME_IMAGE_PREFIX, MIME_PDF, MIME_TEXT_PREFIX
from chatbot.logger import logger

# Constante de conversion
BYTES_PER_MB = 1024 * 1024


class FileValidationError(Exception):
    """Exception levée lors d'erreurs de validation de fichiers."""

    pass


def validate_file_size(file_path: str, max_size_mb: int) -> tuple[bool, str]:
    """
    Valide la taille d'un fichier.

    Args:
        file_path: Chemin vers le fichier à valider
        max_size_mb: Taille maximale autorisée en MB

    Returns:
        Tuple (True, "") si valide, (False, message_erreur) sinon
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Fichier introuvable: {file_path}")
            return False, "Fichier introuvable"

        file_size = os.path.getsize(file_path)
        max_size_bytes = max_size_mb * BYTES_PER_MB
        size_mb = file_size / BYTES_PER_MB

        if file_size > max_size_bytes:
            logger.warning(f"Fichier trop volumineux: {size_mb:.2f}MB (max: {max_size_mb}MB)")
            return False, f"Fichier trop volumineux: {size_mb:.2f}MB (max: {max_size_mb}MB)"

        logger.debug(f"Taille du fichier validée: {file_size} bytes ({size_mb:.2f}MB)")
        return True, ""

    except OSError as e:
        logger.error(f"Erreur lors de la validation de taille: {e}")
        return False, "Erreur lors de la lecture du fichier"


def validate_file_type(file, allowed_types: list[str]) -> tuple[bool, str]:
    """Valide le type MIME d'un fichier."""
    mime = getattr(file, "mime", None)

    if not mime:
        logger.error(f"Type MIME manquant pour le fichier {getattr(file, 'name', 'inconnu')}")
        return False, "Type MIME manquant"

    # Support des préfixes (ex: "image/") ou types exacts (ex: "application/pdf")
    for allowed in allowed_types:
        is_match = mime.startswith(allowed) if allowed.endswith("/") else mime == allowed
        if is_match:
            logger.debug(f"Type MIME validé: {mime}")
            return True, ""

    logger.warning(f"Type de fichier non supporté: {mime}")
    return False, f"Type de fichier non supporté: {mime}"


def validate_uploaded_files(files) -> tuple[list, list, list[str]]:
    """Valide tous les fichiers uploadés et les sépare en images et documents."""
    images = []
    documents = []
    errors = []

    # Validation du nombre de fichiers
    if len(files) > config.MAX_FILES:
        error_msg = f"Trop de fichiers ({len(files)}). Maximum autorisé: {config.MAX_FILES}"
        logger.warning(error_msg)
        errors.append(error_msg)
        return [], [], errors

    logger.info(f"Validation de {len(files)} fichier(s)")

    for file in files:
        file_name = getattr(file, "name", "inconnu")
        file_path = getattr(file, "path", None)

        if not file_path:
            errors.append(f"{file_name}: Chemin de fichier manquant")
            continue

        is_image, _ = validate_file_type(file, [MIME_IMAGE_PREFIX])
        if is_image:
            # Validation de la taille pour les images
            valid, error = validate_file_size(file_path, config.MAX_IMAGE_SIZE_MB)
            if valid:
                images.append(file)
                logger.debug(f"Image validée: {file_name}")
            else:
                errors.append(f"{file_name}: {error}")
        else:
            is_document, _ = validate_file_type(file, [MIME_PDF, MIME_TEXT_PREFIX])
            if is_document:
                # Validation de la taille pour les documents
                valid, error = validate_file_size(file_path, config.MAX_DOCUMENT_SIZE_MB)
                if valid:
                    documents.append(file)
                    logger.debug(f"Document validé: {file_name}")
                else:
                    errors.append(f"{file_name}: {error}")
            else:
                # Type de fichier non supporté
                mime = getattr(file, "mime", "inconnu")
                error_msg = f"{file_name}: Type de fichier non supporté ({mime})"
                errors.append(error_msg)
                logger.warning(error_msg)

    logger.info(
        f"Validation terminée: {len(images)} image(s), "
        f"{len(documents)} document(s), {len(errors)} erreur(s)"
    )

    return images, documents, errors


def validate_image_path(image_path: str) -> bool:
    """
    Valide qu'un chemin d'image existe et pointe vers un fichier.

    Args:
        image_path: Chemin absolu vers l'image à valider

    Returns:
        True si le chemin est valide

    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        FileValidationError: Si le chemin n'est pas un fichier
    """
    if not os.path.exists(image_path):
        logger.error(f"Image introuvable: {image_path}")
        raise FileNotFoundError(f"Image introuvable: {image_path}")

    if not os.path.isfile(image_path):
        logger.error(f"Le chemin n'est pas un fichier: {image_path}")
        raise FileValidationError(f"Le chemin n'est pas un fichier: {image_path}")

    logger.debug(f"Chemin d'image validé: {image_path}")
    return True
