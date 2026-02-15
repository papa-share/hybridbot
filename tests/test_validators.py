"""
Tests pour le module de validation des fichiers.
"""

import os

import pytest


class TestValidateFileSize:
    """Tests pour la fonction validate_file_size."""

    def test_valid_file_size(self, sample_text_file):
        """Vérifie qu'un fichier de taille valide passe la validation."""
        from chatbot.utils.validators import validate_file_size

        is_valid, error = validate_file_size(sample_text_file, max_size_mb=1)
        assert is_valid is True
        assert error == ""

    def test_file_too_large(self, sample_large_file):
        """Vérifie qu'un fichier trop volumineux est rejeté."""
        from chatbot.utils.validators import validate_file_size

        is_valid, error = validate_file_size(sample_large_file, max_size_mb=1)
        assert is_valid is False
        assert "trop volumineux" in error.lower()

    def test_file_not_found(self, temp_dir):
        """Vérifie qu'un fichier inexistant retourne une erreur."""
        from chatbot.utils.validators import validate_file_size

        fake_path = os.path.join(temp_dir, "inexistant.txt")
        is_valid, error = validate_file_size(fake_path, max_size_mb=1)
        assert is_valid is False
        assert "introuvable" in error.lower()


class TestValidateFileType:
    """Tests pour la fonction validate_file_type."""

    def test_valid_image_type(self, mock_file):
        """Vérifie qu'un type image valide passe la validation."""
        from chatbot.utils.validators import validate_file_type

        file = mock_file("test.png", "/tmp/test.png", "image/png")
        is_valid, error = validate_file_type(file, ["image/"])
        assert is_valid is True
        assert error == ""

    def test_valid_pdf_type(self, mock_file):
        """Vérifie qu'un PDF valide passe la validation."""
        from chatbot.utils.validators import validate_file_type

        file = mock_file("doc.pdf", "/tmp/doc.pdf", "application/pdf")
        is_valid, error = validate_file_type(file, ["application/pdf"])
        assert is_valid is True

    def test_invalid_file_type(self, mock_file):
        """Vérifie qu'un type non autorisé est rejeté."""
        from chatbot.utils.validators import validate_file_type

        file = mock_file("script.exe", "/tmp/script.exe", "application/x-msdownload")
        is_valid, error = validate_file_type(file, ["image/", "application/pdf"])
        assert is_valid is False
        assert "non supporté" in error.lower()

    def test_missing_mime_type(self, mock_file):
        """Vérifie qu'un fichier sans type MIME est rejeté."""
        from chatbot.utils.validators import validate_file_type

        file = mock_file("test.txt", "/tmp/test.txt", None)
        is_valid, error = validate_file_type(file, ["text/"])
        assert is_valid is False
        assert "mime" in error.lower()


class TestValidateUploadedFiles:
    """Tests pour la fonction validate_uploaded_files."""

    def test_empty_files_list(self):
        """Vérifie qu'une liste vide retourne des listes vides."""
        from chatbot.utils.validators import validate_uploaded_files

        images, documents, errors = validate_uploaded_files([])
        assert images == []
        assert documents == []
        assert errors == []

    def test_too_many_files(self, mock_file):
        """Vérifie que trop de fichiers génère une erreur."""
        from chatbot.utils.validators import validate_uploaded_files

        # Créer plus de fichiers que la limite
        files = [mock_file(f"file{i}.png", f"/tmp/file{i}.png", "image/png") for i in range(10)]
        images, documents, errors = validate_uploaded_files(files)
        assert len(errors) > 0
        assert "trop de fichiers" in errors[0].lower()

    def test_valid_image_classification(self, mock_file, sample_text_file):
        """Vérifie qu'une image valide est classée comme image."""
        from chatbot.utils.validators import validate_uploaded_files

        # Utiliser un vrai fichier pour passer la validation de taille
        file = mock_file("test.png", sample_text_file, "image/png")
        images, documents, errors = validate_uploaded_files([file])
        assert len(images) == 1
        assert len(documents) == 0

    def test_valid_document_classification(self, mock_file, sample_text_file):
        """Vérifie qu'un document valide est classé comme document."""
        from chatbot.utils.validators import validate_uploaded_files

        file = mock_file("doc.pdf", sample_text_file, "application/pdf")
        images, documents, errors = validate_uploaded_files([file])
        assert len(images) == 0
        assert len(documents) == 1


class TestValidateImagePath:
    """Tests pour la fonction validate_image_path."""

    def test_valid_image_path(self, sample_text_file):
        """Vérifie qu'un chemin valide passe la validation."""
        from chatbot.utils.validators import validate_image_path

        result = validate_image_path(sample_text_file)
        assert result is True

    def test_nonexistent_path(self, temp_dir):
        """Vérifie qu'un chemin inexistant lève FileNotFoundError."""
        from chatbot.utils.validators import validate_image_path

        fake_path = os.path.join(temp_dir, "inexistant.png")
        with pytest.raises(FileNotFoundError):
            validate_image_path(fake_path)

    def test_directory_path(self, temp_dir):
        """Vérifie qu'un répertoire lève FileValidationError."""
        from chatbot.utils.validators import FileValidationError, validate_image_path

        with pytest.raises(FileValidationError):
            validate_image_path(temp_dir)


class TestFileValidationError:
    """Tests pour l'exception FileValidationError."""

    def test_exception_inheritance(self):
        """Vérifie que FileValidationError hérite de Exception."""
        from chatbot.utils.validators import FileValidationError

        assert issubclass(FileValidationError, Exception)

    def test_exception_message(self):
        """Vérifie que l'exception peut contenir un message."""
        from chatbot.utils.validators import FileValidationError

        error = FileValidationError("Test error message")
        assert str(error) == "Test error message"
