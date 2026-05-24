import os

from chatbot.config import (
    MIME_IMAGE_PREFIX,
    config,
    is_document_source,
    logger,
)

BYTES_PER_MB = 1024 * 1024


def _upload_path(file) -> str:
    raw = getattr(file, "path", None)
    return str(raw) if raw else ""


def _upload_mime(file) -> str:
    return getattr(file, "mime", None) or ""


def _upload_name(file) -> str:
    return getattr(file, "name", None) or ""


def validate_file_size(file_path: str, max_size_mb: int) -> tuple[bool, str]:
    try:
        if not os.path.exists(file_path):
            return False, "Fichier introuvable"

        size_mb = os.path.getsize(file_path) / BYTES_PER_MB
        if size_mb > max_size_mb:
            return False, f"Fichier trop volumineux: {size_mb:.2f}MB (max: {max_size_mb}MB)"
        return True, ""
    except OSError:
        return False, "Erreur lors de la lecture du fichier"


def validate_file_type(file, allowed_types: list[str]) -> tuple[bool, str]:
    mime = getattr(file, "mime", None)
    if not mime:
        return False, "Type MIME manquant"

    for allowed in allowed_types:
        if allowed.endswith("/"):
            if mime.startswith(allowed):
                return True, ""
        elif mime == allowed:
            return True, ""
    return False, f"Type de fichier non supporté: {mime}"


def validate_uploaded_files(files) -> tuple[list, list, list[str]]:
    if len(files) > config.MAX_FILES:
        msg = f"Trop de fichiers ({len(files)}). Max: {config.MAX_FILES}"
        return [], [], [msg]

    images: list = []
    documents: list = []
    errors: list[str] = []

    for file in files:
        name = _upload_name(file) or "inconnu"
        path = _upload_path(file)
        mime = _upload_mime(file)
        if not path:
            errors.append(f"{name}: chemin manquant")
            continue

        if validate_file_type(file, [MIME_IMAGE_PREFIX])[0]:
            ok, err = validate_file_size(path, config.MAX_IMAGE_SIZE_MB)
            if ok:
                images.append(file)
            else:
                errors.append(f"{name}: {err}")
            continue

        if is_document_source(path=path, mime=mime, name=name):
            ok, err = validate_file_size(path, config.MAX_DOCUMENT_SIZE_MB)
            if ok:
                documents.append(file)
            else:
                errors.append(f"{name}: {err}")
            continue

        errors.append(f"{name}: type non supporté ({mime or 'inconnu'})")
        logger.warning(f"Type refusé: {name} ({mime})")

    return images, documents, errors


def validate_image_path(image_path: str) -> bool:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image introuvable: {image_path}")
    if not os.path.isfile(image_path):
        raise ValueError(f"Pas un fichier: {image_path}")
    return True
