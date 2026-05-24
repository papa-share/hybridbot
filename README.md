# OllamaHybridBot

![PBN ARCHITECT](public/logo_pbn.png)

OllamaHybridBot est l'interface de chat développée par **PBN ARCHITECT**, branchée sur **Ollama**. L'application route les conversations vers des modèles locaux ou cloud, enrichit les réponses avec une recherche web sourcée (Exa), traite des documents et des images, et gère le travail en équipe avec historique PostgreSQL.

## Interface

Connexion, page d'accueil avec starters, réglages, recherche web (Tasks + citations), partage de fil et choix du thème.

| | |
| --- | --- |
| **Connexion** | **Accueil** |
| ![Connexion](public/screenshots/login.png) | ![Accueil](public/screenshots/accueil.png) |
| **Réglages** | **Thème clair / sombre** |
| ![Réglages](public/screenshots/parametre.png) | ![Thème](public/screenshots/selecteur_theme.png) |
| **Recherche web** | **Partage d'un fil** |
| ![Recherche web](public/screenshots/web.png) | ![Partage](public/screenshots/share.png) |

## Contenu

- [Interface](#interface)
- [Ce que fait l'application](#ce-que-fait-lapplication)
- [Pipeline](#pipeline)
- [Stack](#stack)
- [Structure du projet](#structure-du-projet)
- [Prérequis](#prérequis)
- [Installation et lancement](#installation-et-lancement)
- [Modes de déploiement](#modes-de-déploiement)
- [PostgreSQL et comptes](#postgresql-et-comptes)
- [Configuration](#configuration)
- [Administration des comptes](#administration-des-comptes)
- [Développement](#développement)
- [Notes techniques](#notes-techniques)
- [Guide utilisateur in-app](#guide-utilisateur-in-app)
- [Licence](#licence)

## Ce que fait l'application

**Chat Ollama.** Les messages partent vers le modèle choisi dans les réglages (température, top P, tokens max). La liste des modèles distingue local, cloud et vision via les préfixes `[local]`, `[cloud]`, `[vision local]`, `[vision cloud]`. Les modèles non conversationnels (embeddings, OCR, rerankers) sont filtrés.

**Recherche web.** Avant l'envoi, l'utilisateur peut activer la recherche Exa. L'application récupère des pages, les injecte au modèle et renvoie une synthèse avec citations numérotées `[1]`, `[2]`, etc. Un modèle cloud compatible outils est privilégié dans ce mode.

**Documents.** PDF (extraction texte via opendataloader-pdf, Java 11+ requis), Markdown et texte. Jusqu'à 5 fichiers, 50 Mo chacun. Le contenu extrait est passé au modèle pour synthèse ou questionnement.

**Vision.** Les images jointes sont analysées par un modèle vision. Si le modèle sélectionné ne le supporte pas, bascule automatique vers un modèle vision disponible (cloud en priorité).

**Combinaisons.** Document et recherche web peuvent être demandés dans le même message. Les deux pipelines s'enchaînent ; la progression s'affiche dans le panneau Tasks Chainlit.

**Persistance (PostgreSQL).** Historique des fils par utilisateur, messages favoris, partage de fil en lecture seule (`/share/{id}`), préférences de chat (modèle, paramètres) sauvegardées par compte.

**Authentification.** Login par identifiant et mot de passe. Comptes gérés en CLI, rôles `user` et `admin`. Mode dev possible avec un mot de passe partagé sans base de données.

## Pipeline

Traitement d'un message (`app.py` → `llm.process_llm_request`).

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 55, "rankSpacing": 65, "padding": 22}, "themeVariables": {"fontSize": "20px"}}}%%
flowchart LR
    subgraph b1 ["B1 · Entree (1-3)"]
        direction TB
        e1["1 · Message"]
        e2["2 · Validation uploads"]
        e3["3 · Flow handler"]
        e1 --> e2 --> e3
    end

    subgraph b2 ["B2 · Enrichissement (4-6)"]
        direction TB
        e4["4 · Extraction PDF / texte"]
        e5["5 · Exa + contexte"]
        e6["6 · Prompt enrichi"]
        e4 --> e5 --> e6
    end

    subgraph b3 ["B3 · Inference (7-8)"]
        direction TB
        e7["7 · Modele + contexte + images"]
        e8["8 · Stream Ollama"]
        e7 --> e8
        e8 -->|echec retryable| e8
    end

    subgraph b4 ["B4 · Sortie (9-10)"]
        direction TB
        e9["9 · Post-traitement"]
        e10["10 · Reponse finale"]
        e9 --> e10
    end

    e3 --> e4
    e6 --> e7
    e8 --> e9
```

### B1 · Entree (1-3)

1. Message utilisateur et pièces jointes.
2. Validation des fichiers (`validate_uploaded_files`). Arrêt si erreur bloquante.
3. Création du flow handler (Tasks document et/ou web).

### B2 · Enrichissement (4-6)

4. Extraction des documents si présents (PDF, Markdown, texte). Sinon, passage direct à 5.
5. Recherche Exa si le web est activé. Sinon, passage direct à 6. Si 4 et 5 sont actifs, l'ordre reste 4 puis 5.
6. Prompt utilisateur enrichi ajouté à l'historique de la conversation.

### B3 · Inference (7-8)

7. Choix du modèle, troncature du contexte, encodage des images jointes.

| Situation | Comportement |
| --- | --- |
| Image jointe, modèle actif sans vision | Modèles vision ; intersection vision + web si les deux sont actifs |
| Web actif, pas de bascule vision | Modèles cloud compatibles outils |
| Sinon | Modèle des réglages |

8. Appel Ollama en stream (affichage progressif dans Chainlit). Nouvel essai sur le modèle suivant en cas d'échec retryable.

### B4 · Sortie (9-10)

9. Nettoyage de la réponse et citations cliquables si recherche web.
10. Réponse finalisée et enregistrée dans l'historique.

Tasks (`flow.py`) : B2 étape 4 → panneau Document. B2 étape 5 et B3 étape 8 → panneau Web s'il existe ; sinon les événements LLM de l'étape 8 vont au panneau Document.

Hors de ce pipeline : auth, PostgreSQL, favoris, prefs utilisateur, partage de fils.

## Stack

| Composant | Rôle |
| --- | --- |
| [Chainlit](https://chainlit.io/) 2.x | Interface web, historique, auth |
| [Ollama](https://ollama.com/) | Inférence LLM local et cloud |
| [Exa](https://exa.ai/) | Recherche web |
| opendataloader-pdf | Extraction PDF |
| PostgreSQL 16 | Historique, comptes, favoris |
| [uv](https://docs.astral.sh/uv/) | Gestion des dépendances Python |

## Structure du projet

```
src/chatbot/
  app.py              Entrée Chainlit, handlers, starters
  llm.py              Catalogue modèles, requêtes Ollama, routing vision
  web.py              Recherche Exa, formatage des citations
  flow.py             Routage des événements (document / web)
  document_flow.py    Pipeline extraction document
  web_flow.py         Pipeline recherche web
  flow_ui.py          Affichage Tasks Chainlit
  flow_events.py      Événements partagés des flows
  pdf_loader.py       Extraction PDF
  persistence.py      PostgreSQL, prefs, PostgresDataLayer
  auth.py             Authentification
  config.py           Variables .env
  validators.py       Validation des pièces jointes

public/               logo_pbn.png, favicon.png, web.css, screenshots/, starters SVG
.chainlit/            config.toml, traductions
scripts/              init_db.py, manage_user.py, schema.sql
tests/                pytest (67 tests)
chainlit.md           Guide affiché dans l'app (« Lisez-moi »)
```

## Prérequis

- **Python** ≥ 3.10
- **[uv](https://docs.astral.sh/uv/)**
- **[Ollama](https://ollama.com/)** en service (`ollama serve`, port 11434)
- **Java 11+** pour l'extraction PDF (`java -version`)
- **Docker** si vous activez PostgreSQL via `make db-up`
- **Clé Exa** pour la recherche web ([dashboard.exa.ai/api-keys](https://dashboard.exa.ai/api-keys))

## Installation et lancement

```bash
copy .env.example .env    # Linux/macOS : cp .env.example .env
make install-dev
make run
```

Ouvrir http://localhost:8000

Rechargement automatique du code Python :

```bash
make run-watch
```

## Modes de déploiement

| Mode | `.env` | Résultat |
| --- | --- | --- |
| Local simple | `AUTH_MODE=none`, pas de `DATABASE_URL` | Chat immédiat, pas de login, pas d'historique |
| Équipe | `AUTH_MODE=password` + `DATABASE_URL` | Login par compte, fils et favoris en PostgreSQL |
| Dev sans DB | `AUTH_MODE=password` + `AUTH_PASSWORD` | Login avec un mot de passe unique partagé |

## PostgreSQL et comptes

```bash
make db-up          # PostgreSQL 16 via docker compose
make db-init        # Schéma Chainlit
make user-create USER=admin PASS=change-moi ROLE=admin
```

Dans `.env` :

```env
AUTH_MODE=password
CHAINLIT_AUTH_SECRET=...   # uv run python -m chainlit create-secret
DATABASE_URL=postgresql+asyncpg://chainlit:chainlit@localhost:5432/chainlit
```

Identifiants par défaut du conteneur : user `chainlit`, password `chainlit`, base `chainlit` (voir `docker-compose.yml`).

## Configuration

Fichiers de référence : [.env.example](.env.example), `.env.production`.

| Variable | Rôle |
| --- | --- |
| `OLLAMA_URL` | URL Ollama (défaut `http://localhost:11434`) |
| `DEFAULT_MODEL` | Modèle au lancement |
| `DEFAULT_WEB_MODEL` | Modèle prioritaire en recherche web |
| `EXA_API_KEY` | Clé API Exa |
| `WEB_SEARCH_MAX_RESULTS` | Nombre de sources Exa (défaut 5) |
| `DATABASE_URL` | PostgreSQL (`postgresql+asyncpg://...`) |
| `AUTH_MODE` | `none` ou `password` |
| `CHAINLIT_AUTH_SECRET` | Secret sessions (obligatoire si login en prod) |
| `AUTH_PASSWORD` | Dev : mot de passe partagé sans PostgreSQL |
| `MAX_FILES` / `MAX_*_SIZE_MB` | Limites upload (aligner avec `.chainlit/config.toml`) |

Variables optionnelles commentées dans `.env.example` : température, contexte, modèles vision/web prioritaires, prompt système.

## Administration des comptes

```bash
make user-create USER=alice PASS=secret          # nouveau compte
make user-list                                   # lister
make user-disable USER=alice                     # bloquer
make user-enable USER=alice                      # réactiver
make user-reset-pass USER=alice PASS=nouveau     # mot de passe
make user-set-role USER=alice ROLE=admin         # rôle
```

Le dernier admin actif ne peut pas être désactivé ni rétrogradé.

`make help` liste toutes les cibles disponibles.

## Développement

```bash
make test           # pytest
make check          # ruff + black + tests
make lint           # ruff seul
make format         # black
make typecheck      # pyright
make deadcode       # vulture
make db-down        # arrêter PostgreSQL
```

CI GitHub Actions (`.github/workflows/ci.yml`) exécute `make check` sur Python 3.10.

Dépendances dev installées par `make install-dev` : ruff, black, pytest, pyright, vulture.

## Notes techniques

### PostgresDataLayer et favoris

Avec `DATABASE_URL`, l'application enregistre `PostgresDataLayer` (`src/chatbot/persistence.py`) à la place du `SQLAlchemyDataLayer` Chainlit.

Chainlit filtre les favoris avec `metadata LIKE '%"favorite": true%'`. Sur PostgreSQL, `metadata` est en jsonb : cela provoque `operator does not exist: jsonb ~~ unknown`. L'override utilise `metadata @> '{"favorite": true}'::jsonb`. Ne pas supprimer cette classe si l'historique et les favoris sont activés.

## Guide utilisateur in-app

[chainlit.md](chainlit.md) reprend l'usage quotidien (modèles, pièces jointes, favoris, partage) et s'affiche dans l'application via le panneau « Lisez-moi ».

## Licence

MIT. Voir [LICENSE](LICENSE).
