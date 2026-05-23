# OllamaHybridBot

Assistant de chat local : Chainlit + Ollama, avec recherche web (Exa), vision et fichiers.

## Démarrage rapide

**Prérequis** : [uv](https://docs.astral.sh/uv/), Ollama en marche (`ollama serve`, port 11434).

```bash
copy .env.example .env    # Linux/macOS : cp .env.example .env
make install-dev
make run
```

Ouvrir http://localhost:8000

## Deux modes

| Mode | `.env` | Comportement |
| --- | --- | --- |
| **Local simple** | `AUTH_MODE=none`, pas de `DATABASE_URL` | Chat sans login, sans historique |
| **Avec historique** | `AUTH_MODE=password` + `DATABASE_URL` | Login par compte, fils en PostgreSQL |
| **Dev sans DB** | `AUTH_MODE=password` + `AUTH_PASSWORD` | Mot de passe partagé (un seul secret) |

### Activer l'historique

```bash
make db-up      # lance PostgreSQL (Docker)
make db-init    # crée le schéma Chainlit + table accounts
make user-create USER=admin PASS=change-moi ROLE=admin
```

Puis dans `.env` :

```env
AUTH_MODE=password
CHAINLIT_AUTH_SECRET=...   # générer : uv run python -m chainlit create-secret
DATABASE_URL=postgresql+asyncpg://chainlit:chainlit@localhost:5432/chainlit
```

Chaque membre de l'équipe se connecte avec son identifiant et mot de passe (`make user-create USER=... PASS=...`). Rôle `admin` ou `user` (défaut). En dev local sans PostgreSQL, `AUTH_PASSWORD` reste supporté comme mot de passe unique partagé.

**Administration des comptes** (PostgreSQL requis) :

```bash
make user-list                          # lister
make user-disable USER=alice            # désactiver
make user-enable USER=alice             # réactiver
make user-reset-pass USER=alice PASS=…  # nouveau mot de passe
make user-set-role USER=alice ROLE=admin
```

Impossible de désactiver ou rétrograder le **dernier admin actif**.

- **Nouveau fil** : icône crayon (en haut à gauche)
- **Anciens fils** : barre latérale
- **Partager un fil** : menu ⋯ du fil → « Partager » → lien copié (lecture seule, sans login pour le visiteur)

## Interface

Tout se pilote depuis l'UI, sans commandes texte :

| Élément | Rôle |
| --- | --- |
| **Starters** | Actualités IA, PDF, code, image (icônes + raccourcis) |
| **Engrenage** | Modèle, température, top P, tokens max |
| **Globe** | Recherche web Exa (clé `EXA_API_KEY`) |
| **Trombone** | Pièces jointes (images, PDF, texte) |
| **Barre latérale** | Historique des conversations (si PostgreSQL actif) |
| **Étoile** | Favoris : sauvegarder un message et le réutiliser (login + PostgreSQL) |
| **Partager** | Menu ⋯ d'un fil → lien lecture seule (login + PostgreSQL) |

Guide utilisateur détaillé : [chainlit.md](chainlit.md) (lien « Lisez-moi » dans l'app).

## Configuration

- Variables : [.env.example](.env.example)
- Production : `.env.production`
- Limites fichiers : `.env` (`MAX_*`) et `.chainlit/config.toml` — garder les mêmes valeurs (ex. 5 fichiers max)

Clé Exa : [dashboard.exa.ai/api-keys](https://dashboard.exa.ai/api-keys)

## Développement

```bash
make test       # tests
make check      # lint + format + tests
make db-down    # arrêter PostgreSQL
```

Comptes PostgreSQL : `make user-list`, `make user-create`, `make user-disable`, etc. (voir section historique).

## Licence

MIT — voir [LICENSE](LICENSE).
