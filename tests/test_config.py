"""
Tests pour le module de configuration.
"""


class TestConfig:
    """Tests pour la configuration de l'application."""

    def test_config_import(self):
        """Vérifie que le module config peut être importé."""
        from chatbot.config import config

        assert config is not None

    def test_config_has_required_attributes(self):
        """Vérifie que la config a tous les attributs requis."""
        from chatbot.config import config

        required_attrs = [
            "AUTH_MODE",
            "PERSISTENCE",
            "DEBUG",
            "MAX_IMAGE_SIZE_MB",
            "MAX_DOCUMENT_SIZE_MB",
            "MAX_FILES",
            "OLLAMA_TIMEOUT",
            "OLLAMA_URL",
            "DEFAULT_MODEL",
            "VISION_MODELS",
            "KNOWN_CLOUD_MODELS",
            "SYSTEM_PROMPT",
        ]

        for attr in required_attrs:
            assert hasattr(config, attr), f"Attribut manquant: {attr}"

    def test_config_default_values(self):
        """Vérifie les valeurs par défaut de la configuration."""
        from chatbot.config import Config

        # Créer une instance fraîche sans variables d'environnement
        assert Config.OLLAMA_URL == "http://localhost:11434"
        assert Config.OLLAMA_TIMEOUT == 120
        assert Config.MAX_FILES == 3
        assert Config.MAX_IMAGE_SIZE_MB == 20
        assert Config.MAX_CONTEXT_MESSAGES == 20

    def test_config_vision_models_not_empty(self):
        """Vérifie que la liste des modèles vision n'est pas vide."""
        from chatbot.config import config

        assert len(config.VISION_MODELS) > 0

    def test_config_known_cloud_models_not_empty(self):
        """Vérifie que la liste des modèles cloud connus n'est pas vide."""
        from chatbot.config import config

        assert len(config.KNOWN_CLOUD_MODELS) > 0

    def test_config_system_prompt_exists(self):
        """Vérifie que le prompt système est défini et non vide."""
        from chatbot.config import config

        assert config.SYSTEM_PROMPT
        assert len(config.SYSTEM_PROMPT) > 100  # Prompt significatif

    def test_development_config(self):
        """Vérifie la configuration de développement."""
        from chatbot.config import DevelopmentConfig

        assert DevelopmentConfig.DEBUG is True

    def test_production_config(self):
        """Vérifie la configuration de production."""
        from chatbot.config import ProductionConfig

        assert ProductionConfig.DEBUG is False
        assert ProductionConfig.AUTH_MODE == "password"
        assert ProductionConfig.MAX_FILES == 3  # Plus restrictif


class TestEnvironmentConfig:
    """Tests pour la configuration basée sur les variables d'environnement."""

    def test_auth_mode_default(self):
        """Vérifie que AUTH_MODE a une valeur par défaut."""
        from chatbot.config import Config

        assert Config.AUTH_MODE in ["none", "password"]

    def test_persistence_default(self):
        """Vérifie que PERSISTENCE a une valeur par défaut."""
        from chatbot.config import Config

        assert Config.PERSISTENCE in ["none", "local"]
