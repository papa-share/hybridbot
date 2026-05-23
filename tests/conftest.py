import os
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_file(temp_dir):
    file_path = os.path.join(temp_dir, "sample.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Contenu de test pour les validations.")
    return file_path


@pytest.fixture
def sample_large_file(temp_dir):
    file_path = os.path.join(temp_dir, "large_file.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("x" * (3 * 1024 * 1024))
    return file_path


@pytest.fixture
def mock_file():
    class MockFile:
        def __init__(self, name: str, path: str, mime: str):
            self.name = name
            self.path = path
            self.mime = mime

    return MockFile
