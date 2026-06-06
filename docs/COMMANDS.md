# COMMANDS.md — Giulio Geo

Ce fichier liste les commandes détectées dans le dépôt. Ne pas inventer de commande : si une commande n'existe pas dans `pyproject.toml`, `package.json`, le README ou la documentation projet, elle doit rester recommandée mais non obligatoire.

## Python / backend / CLI

| Usage | Command | What it does | When to use | Required before commit |
|---|---|---|---|---|
| Install package | `pip install -e .` | Installe le package Python local et la commande `leonie-seo`. | Setup local ou environnement de dev. | No |
| Install dev dependencies | `pip install -e .[dev]` | Installe le package avec `pytest`, `pytest-mock` et `ruff`. | Avant de lancer tests/lint localement. | No |
| CLI help | `leonie-seo --help` | Affiche les commandes CLI disponibles. | Vérifier l'installation ou explorer le CLI. | No |
| Backend dev server | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | Lance le backend FastAPI. | Développement backend local. | No |
| Lint Python | `ruff check .` | Vérifie le lint/imports Python selon `pyproject.toml`. | Après changement Python. | Yes, si Python modifié |
| Tests Python | `pytest` | Lance la suite de tests Python. | Après changement backend, CLI ou logique SEO. | Yes, si logique Python modifiée |
| Targeted Python tests | `pytest path/to/test_file.py` | Lance un sous-ensemble de tests. | Pendant développement ou triage. | No, sauf si pertinent |

## Shopify app / frontend

Gestionnaire détecté : `npm`, via `shopify-app/package-lock.json`.

| Usage | Command | What it does | When to use | Required before commit |
|---|---|---|---|---|
| Install Node dependencies | `cd shopify-app && npm install` | Installe les dépendances Remix/Shopify. | Setup local. | No |
| Shopify dev | `cd shopify-app && npm run dev` | Lance `shopify app dev`. | Développement embedded Shopify. | No |
| Remix dev | `cd shopify-app && npm run web` | Lance `remix vite:dev`. | Développement UI hors tunnel Shopify si utile. | No |
| Typecheck | `cd shopify-app && npm run typecheck` | Lance TypeScript `tsc`. | Après changement TypeScript/Remix. | Yes, si `shopify-app/` modifié |
| Build | `cd shopify-app && npm run build` | Build Remix/Vite. | Avant merge d'un changement UI/app. | Yes, si `shopify-app/` modifié |
| Start built app | `cd shopify-app && npm run start` | Sert le build Remix. | Vérification post-build. | No |

## Docker

| Usage | Command | What it does | When to use | Required before commit |
|---|---|---|---|---|
| Build image | `docker build -t leonie-seo .` | Construit l'image backend Python + CLI. | Vérification Docker ou déploiement. | No |
| Run backend container | `docker run -p 8000:8000 -v $(pwd)/data:/app/data -v $(pwd)/reports:/app/reports --env-file .env --entrypoint uvicorn leonie-seo app.main:app --host 0.0.0.0 --port 8000` | Lance FastAPI en container. | Test local Docker. | No |
| Run CLI container | `docker run --rm --env-file .env leonie-seo audit crawl` | Lance une commande CLI dans l'image. | Test CLI en container. | No |

## Pilot / smoke checks

| Usage | Command | What it does | When to use | Required before commit |
|---|---|---|---|---|
| Public pilot smoke | `leonie-seo pilot smoke-public` | Vérifie les endpoints publics du pilote. | Après déploiement pilote ou changement infra. | No |

## Formatting

Aucune commande de format dédiée n'est détectée dans `pyproject.toml` ou `shopify-app/package.json`.

Recommended if needed later:

- Python format: add an explicit `ruff format .` workflow only if the project decides to enforce it.
- Frontend format: add Prettier only if the repo adopts it explicitly.

## Type checking

- Python typecheck: not configured yet. `mypy` or `pyright` are not listed in `pyproject.toml`.
- Shopify/TypeScript typecheck: configured via `cd shopify-app && npm run typecheck`.

## Tests

- Python tests: configured with `pytest`.
- Frontend tests: not configured yet in `shopify-app/package.json`.

## Migrations

No explicit migration command was detected from the files reviewed. If database migrations are added, document the exact command here before using it in tasks.

## Deployment

Deployment is documented through Docker and Render-related project docs, but no single deploy command is defined as mandatory here. Production deployment/config changes require explicit user request and a short plan.

## Recommended missing commands

| Missing command | Why it would help | Suggested next step |
|---|---|---|
| Python typecheck | Improves reliability for FastAPI/CLI code. | Add `mypy` or `pyright` only after choosing one standard. |
| Frontend lint | `shopify-app/package.json` has no `lint` script. | Add ESLint only if the Shopify app adopts it consistently. |
| Frontend tests | No `test` script detected in `shopify-app/package.json`. | Add a test framework only when UI logic needs automated coverage. |
| Shared validation script | Claude hooks should call a repo-owned safe script, not local absolute paths. | Add `scripts/validate-command.sh` only if it remains non-destructive. |
