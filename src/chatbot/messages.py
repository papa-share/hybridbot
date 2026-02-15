"""Messages utilisateur centralisés."""

# Accueil
WELCOME = (
    "Assistant IA avec support multimodal (texte, images, documents). "
    "Modèles cloud et locaux disponibles via Ollama. "
    "Utilisez les paramètres pour sélectionner le modèle."
)

# Commandes
HELP = """Commandes disponibles :

- /model <nom> : Changer de modèle
- /help : Afficher cette aide
- /clear : Réinitialiser la conversation
- /history : Accéder à l'historique des conversations

Paramètres : Cliquez sur l'icône de paramètres pour ajuster le modèle IA,
la température, Top P et les tokens max."""

HISTORY = """Historique des Conversations

Pour accéder à vos conversations passées :
1. Cliquez sur l'icône en haut à gauche
2. Sélectionnez une conversation dans la liste
3. La conversation sera automatiquement restaurée

Fonctionnalités :
- Sauvegarde automatique : Toutes vos conversations sont sauvegardées localement
- Reprise : Continuez là où vous vous êtes arrêté
- Recherche : Retrouvez vos échanges facilement
- Suppression : Gérez vos conversations

Vos données restent locales et privées."""

# Messages système
CONVERSATION_RESET = "Conversation réinitialisée"
CONVERSATION_RESUMED = "Conversation reprise ({count} messages restaurés)"
RESUME_NOT_AVAILABLE = "Reprise non disponible sans persistance locale"
MODEL_CURRENT = "Modèle actuel : {model}\n\nUsage : /model <nom>"
MODEL_SET = "Modèle défini : {model}"
VISION_MODEL_USED = "Analyse d'image avec le modèle vision : {model}"

# Erreurs Ollama
ERROR_400 = "Erreur de requête (400). Le format des données n'est pas valide. Veuillez réessayer avec une image différente."
ERROR_404 = "Le modèle '{model}' n'est pas disponible. Veuillez sélectionner un autre modèle dans les paramètres."
ERROR_CONNECTION = "Impossible de se connecter à Ollama. Vérifiez que le service Ollama est démarré (ollama serve)."
ERROR_TIMEOUT = "Délai d'attente dépassé. Réessayez ou simplifiez la demande."
ERROR_500 = (
    "Le serveur Ollama a renvoyé une erreur (500). "
    "Pour un modèle cloud, vérifiez la disponibilité du modèle ou essayez un autre modèle."
)
ERROR_GENERIC = "Erreur lors de la communication avec le modèle: {error}"
TRUNCATION_WARNING = (
    "\n\n---\n*Cette réponse a été tronquée. Tapez 'continue' ou 'poursuit' pour voir la suite.*"
)
NO_RESPONSE = "Désolé, je n'ai pas pu générer de réponse."
ERROR_PROCESSING = "Une erreur interne est survenue pendant le traitement."
ERROR_GENERAL = "Une erreur est survenue. Veuillez reformuler ou réessayer."
ERROR_INTERNAL = "Une erreur interne est survenue: {error_type}. Veuillez réessayer."
