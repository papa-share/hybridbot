"""
Configuration des fixtures pytest pour les tests.
"""

import os
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    """Crée un répertoire temporaire pour les tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_file(temp_dir):
    """Crée un fichier texte temporaire pour les tests."""
    file_path = os.path.join(temp_dir, "sample.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Contenu de test pour les validations.")
    return file_path


@pytest.fixture
def sample_large_file(temp_dir):
    """Crée un fichier volumineux pour tester les limites de taille."""
    file_path = os.path.join(temp_dir, "large_file.txt")
    # Crée un fichier de ~3MB
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("x" * (3 * 1024 * 1024))
    return file_path


@pytest.fixture
def mock_file():
    """Crée un mock d'objet fichier Chainlit."""

    class MockFile:
        def __init__(self, name: str, path: str, mime: str):
            self.name = name
            self.path = path
            self.mime = mime

    return MockFile
