# Assistant IA Hybride

Assistant conversationnel avec support local et cloud. Interface en français, analyse de fichiers, et paramètres configurables.

## Fonctionnalités

- **Chat** : Streaming des réponses en temps réel
- **Analyse de fichiers** : Images (50MB max), PDF et Markdown (2MB max)
- **Paramètres** : Température, top_p, tokens max
- **Hybride** : Modèles cloud (gratuits) et locaux (confidentiels)
- **Persistance** : Sauvegarde automatique dans SQLite

## Démarrage

1. Tapez votre message dans la zone de texte
2. Uploadez des fichiers via l'icône de pièce jointe (images, PDF, Markdown)
3. Ajustez les paramètres via l'icône de paramètres (haut à droite)
4. Consultez les réponses générées en temps réel

## Panneau de Paramètres

Cliquez sur l'icône de paramètres pour personnaliser votre expérience :

| Paramètre | Description | Valeurs |
|-----------|-------------|---------|
| **Modèle IA** | Choix du modèle (local ou cloud) | Liste dynamique |
| **Température** | Créativité des réponses | 0 (précis) → 1 (créatif) |
| **Top P** | Diversité du vocabulaire | 0 → 1 |
| **Tokens max** | Longueur des réponses | 100 → 8192 |

## Commandes

Tapez ces commandes directement dans le chat :

| Commande | Action |
|----------|--------|
| `/model <nom>` | Changer de modèle manuellement |
| `/help` | Afficher l'aide complète |
| `/clear` | Réinitialiser la conversation |
| `/history` | Aide sur l'historique |

## Sauvegarde

Vos conversations sont automatiquement sauvegardées dans une base SQLite locale. Vos données restent privées et sur votre machine.

Note : La sidebar d'historique native nécessitait Literal AI (cloud), qui a été discontinué en octobre 2025. La persistance locale fonctionne via Custom Data Layer SQLite, mais l'accès à l'historique nécessite `PERSISTENCE=local` ET `AUTH_MODE=password`.

## Architecture

### Modèles cloud
- API Ollama (suffixes `:cloud`)
- Pas de recherche web intégrée
- Usage : prototypage, données non sensibles

### Modèles locaux
- Exécution sur machine locale
- Données privées
- Usage : données sensibles, conformité RGPD

Changer de modèle via le panneau Settings.
