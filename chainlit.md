# OllamaHybridBot

Assistant de conversation branché sur **Ollama**. Tu écris ici, il répond via les modèles installés localement ou dans le cloud Ollama.

## C'est quoi

Un chat unique qui regroupe ce qu'on attend d'un assistant perso :

- répondre en français, de façon directe
- lire du code, un PDF, un fichier texte
- analyser une image (même si tu as sélectionné un modèle texte)
- chercher sur le web quand tu actives le globe

Pas de compte tiers pour le LLM : tout passe par ton instance Ollama. Le web, lui, utilise Exa (clé dans `.env`).

## Comment ça se passe

**Sans globe** : ton message part tel quel vers Ollama. Le modèle choisi dans les réglages répond.

**Avec globe** (avant d'envoyer) :

1. Exa cherche des pages en lien avec ta question
2. les extraits sont injectés au modèle
3. tu reçois une synthèse avec des renvois `[1]`, `[2]` cliquables vers les sources
4. le panneau Tasks montre la progression pendant la recherche

**Avec une image** : si le modèle actif ne fait pas de vision, le bot bascule seul sur un modèle vision disponible (cloud en priorité).

**Avec un fichier** : le contenu est lu et joint au message (PDF, `.md`, `.txt`).

## Modèles

La liste distingue quatre familles :

| Préfixe | Où ça tourne |
| --- | --- |
| `[local]` | Ta machine |
| `[cloud]` | Cloud Ollama |
| `[vision local]` | Vision locale |
| `[vision cloud]` | Vision cloud |

Embeddings, OCR, whisper et rerankers sont filtrés : seuls les modèles de chat utiles apparaissent.

Avec le web actif, le bot privilégie un modèle cloud compatible `tools`.

## Commandes

| Commande | Effet |
| --- | --- |
| `/model <nom>` | Affiche ou change le modèle |
| `/clear` | Efface la conversation en cours |
| `/history` | Où retrouver les anciens fils |

Historique des fils : `PERSISTENCE=local` et `AUTH_MODE=password` dans `.env`.

## Interface

**Pièces jointes** : PNG, JPG, PDF, Markdown, texte.

**Globe** : recherche Exa. Active-le avant d'envoyer.

**Réglages** : modèle, température, top P, tokens max.

## Limites

5 fichiers max, images 50 Mo, PDF/texte 2 Mo.

## Variables `.env`

| Variable | Rôle |
| --- | --- |
| `OLLAMA_URL` | Ollama (défaut `http://localhost:11434`) |
| `DEFAULT_MODEL` | Modèle au lancement |
| `DEFAULT_WEB_MODEL` | Modèle prioritaire pour le web |
| `EXA_API_KEY` | Recherche web |
| `WEB_SEARCH_MAX_RESULTS` | Nombre de sources Exa (défaut 5) |
| `PERSISTENCE` | `none` ou `local` (SQLite) |
| `AUTH_MODE` | `none` ou `password` |

Prod : `.env.production`. Détail : `.env.example`.
