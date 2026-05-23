import os

import pytest

from chatbot.validators import (
    validate_file_size,
    validate_file_type,
    validate_image_path,
    validate_uploaded_files,
)


def test_valid_file_size(sample_text_file):
    ok, err = validate_file_size(sample_text_file, max_size_mb=1)
    assert ok and err == ""


def test_file_too_large(sample_large_file):
    ok, err = validate_file_size(sample_large_file, max_size_mb=1)
    assert not ok
    assert "trop volumineux" in err.lower()


def test_file_not_found(temp_dir):
    fake = os.path.join(temp_dir, "nope.txt")
    ok, err = validate_file_size(fake, max_size_mb=1)
    assert not ok
    assert "introuvable" in err.lower()


def test_valid_image_type(mock_file):
    f = mock_file("test.png", "/tmp/test.png", "image/png")
    assert validate_file_type(f, ["image/"])[0]


def test_invalid_file_type(mock_file):
    f = mock_file("script.exe", "/tmp/script.exe", "application/x-msdownload")
    ok, err = validate_file_type(f, ["image/", "application/pdf"])
    assert not ok
    assert "non supporté" in err.lower()


def test_too_many_files(mock_file):
    files = [mock_file(f"f{i}.png", f"/tmp/f{i}.png", "image/png") for i in range(10)]
    _, _, errors = validate_uploaded_files(files)
    assert errors and "trop de fichiers" in errors[0].lower()


def test_image_classification(mock_file, sample_text_file):
    f = mock_file("test.png", sample_text_file, "image/png")
    images, documents, _ = validate_uploaded_files([f])
    assert len(images) == 1
    assert not documents


def test_validate_image_path(sample_text_file):
    assert validate_image_path(sample_text_file)


def test_validate_image_path_missing(temp_dir):
    with pytest.raises(FileNotFoundError):
        validate_image_path(os.path.join(temp_dir, "nope.png"))


def test_validate_image_path_is_dir(temp_dir):
    with pytest.raises(ValueError):
        validate_image_path(temp_dir)
