# OllamaHybridBot

Chat Chainlit + Ollama.

## Lancer

Prérequis : [uv](https://docs.astral.sh/uv/). Copier `.env.example` vers `.env`, puis :

```bash
make install-dev
make run
```

Ollama : `ollama serve` (port 11434). Interface : http://localhost:8000

Web (Exa) : globe dans la barre de saisie. Clé sur [dashboard.exa.ai/api-keys](https://dashboard.exa.ai/api-keys), variable `EXA_API_KEY` dans `.env`.

## Config

Voir `.env.example`. En prod : `.env.production`.

Limites fichiers : `.env` et `.chainlit/config.toml` (mêmes valeurs).

## Dev

```bash
make test
make lint
make format
make check
```

## Licence

MIT. Voir [LICENSE](LICENSE).
