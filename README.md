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
| **Avec historique** | `AUTH_MODE=password` + `DATABASE_URL` | Login, fils sauvegardés en PostgreSQL |

### Activer l'historique

```bash
make db-up      # lance PostgreSQL (Docker)
make db-init    # crée le schéma Chainlit
```

Puis dans `.env` :

```env
AUTH_MODE=password
AUTH_PASSWORD=change-moi
CHAINLIT_AUTH_SECRET=...   # générer : uv run python -m chainlit create-secret
DATABASE_URL=postgresql+asyncpg://chainlit:chainlit@localhost:5432/chainlit
```

- **Nouveau fil** : icône crayon (en haut à gauche)
- **Anciens fils** : barre latérale

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

## Licence

MIT — voir [LICENSE](LICENSE).
