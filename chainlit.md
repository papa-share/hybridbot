# OllamaHybridBot

![PBN ARCHITECT](public/logo_pbn.png?v=14)

Guide d'utilisation dans l'application.

OllamaHybridBot est l'interface de chat de **PBN ARCHITECT**. Les réponses passent par Ollama (local ou cloud). La recherche web passe par Exa lorsqu'elle est activée avant l'envoi.

## Utilisation

Un message part vers le modèle choisi dans les réglages : température, top P, limite de tokens. Les préfixes `[local]`, `[cloud]`, `[vision local]` et `[vision cloud]` indiquent où tourne le modèle.

La recherche web interroge Exa, puis produit une synthèse avec des renvois numérotés vers les sources (`[1]`, `[2]`, etc.).

Pièces jointes : PDF, Markdown, texte (5 fichiers max, 50 Mo ; Java 11+ pour les PDF), images PNG/JPG. Le texte extrait ou l'image est transmis au modèle. Si le modèle actif ne gère pas la vision, l'application bascule vers un modèle vision disponible.

Document et recherche web peuvent être combinés dans le même message. La progression s'affiche dans le panneau Tasks.

## Historique, favoris, partage

Sans PostgreSQL, les fils ne sont pas conservés entre les sessions.

Avec login et `DATABASE_URL` : historique dans la barre latérale, messages favoris réutilisables depuis le composer, partage d'un fil en lecture seule (`/share/{id}`) via le menu ⋯. Nouveau fil : icône crayon en haut à gauche.

## Interface

Logo **PBN ARCHITECT** : connexion et en-tête. Couleur d'accent `#070318`.

Starters disponibles : veille IA, résumé de document, explication de code, analyse d'image.

## Administration

Gestion des comptes en CLI (`make user-create`, `make user-list`, etc.). Détail complet dans le README.
