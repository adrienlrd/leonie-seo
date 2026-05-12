# AGENTS.md — Léonie SEO

## 1. CONTEXTE BUSINESS & VISION PRODUIT

### Projet actuel — leoniedelacroix.com
- Site Shopify **accessoires premium pour chiens et chats**, fabriqués en France
- URL : https://www.leoniedelacroix.com · Domaine : 287c4a-bb.myshopify.com
- **Catalogue** : vêtements chien/chat (pardessus, pull, harnais), fontaines eau, griffoirs, bols design
- **Objectif SEO** : 5 000–10 000 visites organiques/mois, 40–100 conversions/mois
- Concurrents : Miacara, Zara Pets, Ferplast

### Vision produit finale — Shopify App publique
**One-liner** : *"L'IA SEO qui identifie ta niche rentable, écrit ton contenu, et l'applique proprement sur ton Shopify. En 1 install."*

- App native Shopify App Store : install 1 clic, embedded dans l'Admin, Polaris UI
- Génération IA de contenu SEO (GPT-4o mini + Cloudflare Workers AI fallback)
- **Niche Intelligence** : détection clusters produits réels, saturation SERP, keyword gaps vs concurrents
- Application directe via Admin API avec validation marchande à chaque étape (review par batch, auto-approve opt-in)
- Mesure d'impact via GSC + GA4 sur URLs modifiées
- Distribution FR + EN, freemium Shopify (Free/Pro/Agency)
- Budget infra cible : ≤ 12 €/mois jusqu'à 100 stores

**Différenciateur vs concurrents** (Smart SEO, AVADA, TinyIMG, Booster SEO) :
- Le marché est saturé sur : meta tags automatiques, alt texts, compression images, schema basique
- Notre angle : **niche-first** — "quel contenu longue traîne mon catalogue peut réellement dominer ?" vs templates génériques
- Pas un générateur de metas. Un copilote qui priorise, contextualise, applique proprement, et mesure l'impact.

### Architecture retenue — Option B : scaffold Remix + moteur Python
- **Couche app** : nouveau dossier `shopify-app/` scaffoldé via Shopify CLI (Remix) — App Bridge v4, Polaris, OAuth, sessions multi-tenant, Billing API, GDPR webhooks
- **Moteur SEO/IA** : `scripts/`, `app/llm/`, `app/niche/`, `app/jobs/` conservés intégralement en Python
- `shopify-app/` appelle le backend Python via HTTP interne
- `frontend/` React existant décommissionné après tâche 57
- Décision documentée dans `DECISIONS.md`

---

## 2. DÉBUT DE SESSION — OBLIGATOIRE

**À chaque session, dans cet ordre avant toute action :**
1. Lire `PROGRESS.md` — état actuel, tâches faites, blocages
2. Lire `ROADMAP.md` — identifier la prochaine tâche ⏳ non faite
3. Proposer explicitement cette tâche à l'utilisateur avant de coder

**Ne jamais sauter de tâches.** Suivre l'ordre de ROADMAP.md sauf demande explicite.
**Ne jamais coder sans que le plan soit validé par l'utilisateur.**

---

## 3. ÉTAT DES PHASES

| Phase | Tâches | Objectif | Statut |
|---|---|---|---|
| 1 — Audit & Fondations | 1–15 | Rapport SEO fonctionnel | ✅ Complète |
| 2 — Application supervisée | 16–29 | Corrections automatisées | ✅ Complète |
| 3 — Contenu SEO & Niche | 30–39 | Contenu IA niche accessoires animaux | ✅ Complète |
| 4 — Productisation CLI | 40–44 | Outil vendable, multi-tenant | ✅ Complète |
| 5 — App Shopify v1 | 45–50 | OAuth + API + Dashboard | ✅ Complète (49 supersédée par 75) |
| 6 — Conformité & Infra async | 51–57 | GDPR + Billing + Queue + App Bridge | ✅ Complète |
| 7 — Moteur IA & Niche | 58–68 | Génération LLM + Niche Intelligence concrète | ✅ Complète |
| **8 — Scale & App Store final** | **69–75** | **Theme Extension + Common Crawl + soumission** | **🔄 6/7 — tâche 75 restante** |

**Prochaine tâche ordonnée :** `75` — Soumission App Store finale, après vérification des prérequis GDPR, Billing, App Bridge, documentation, secrets, tunnels/URLs et checklists Shopify Partner.

---

## 4. RÈGLES NON NÉGOCIABLES

1. **Plan avant code** — toute tâche >15 lignes → plan validé d'abord
2. **Dry-run par défaut** — scripts `apply/` : `--dry-run` par défaut, `--apply` explicite
3. **Confirmation humaine** avant chaque écriture Shopify
4. **Jamais de secrets en dur** — `.env` uniquement, `.env.example` tenu à jour
5. **Pas de modification de handles** — risque 404 massif, interdit définitivement
6. **Commits atomiques** — format `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
7. **Tests minimaux** — un test unitaire mocké par fonction qui touche une API
8. **Pas d'hallucination** — si une donnée manque, lever une exception explicite
9. **ROADMAP.md** — mettre à jour statut + date après chaque tâche terminée
10. **Revue Shopify safety** — avant tout `--apply`, faire une revue sécurité Shopify ; utiliser le subagent Codex `shopify-safety` seulement si la délégation est disponible/autorisée, sinon faire la revue localement avec les mêmes critères
11. **GDPR obligatoire** — tout stockage de données marchand implique les 3 webhooks GDPR
12. **Shopify Billing API** — toute monétisation passe par `appSubscriptionCreate`, jamais un système maison en production App Store
13. **Pas de theme.liquid modifié** — injection contenu uniquement via Theme App Extensions ou metafields
14. **Niche Intelligence = concret** — les recommandations doivent identifier des clusters, gaps, et saturation SERP réels ; jamais de généralités type "le marché est en croissance"
15. **Async queue dès Phase 6** — tout job long (audit, LLM batch, webhook) passe par la queue tâche 55 ; pas de blocking requests en production
16. **Common Crawl en dernier** — valider les sources légères (Google Suggest, pytrends, Reddit, tâche 63) avant d'investir dans le Web Graph (tâche 74)

---

## 5. WORKFLOW OBLIGATOIRE

1. **Explore** → lire PROGRESS.md + ROADMAP.md + fichiers concernés
2. **Plan** → bullet points soumis à l'utilisateur, pas de code avant validation
3. **Implement** → coder le plan approuvé uniquement
4. **Verify** → tests verts + ruff clean + prouver que ça marche
5. **Update** → ROADMAP.md (statut + date) + PROGRESS.md + commit atomique

---

## 6. STACK TECHNIQUE

### Back-end (existant)
- Python 3.11+ · FastAPI + uvicorn · Click + Rich
- Shopify Admin API GraphQL (version 2025-01 minimum)
- SQLite stdlib (→ migrer vers Neon Postgres en Phase 6, tâche 54)
- Chiffrement Fernet (`cryptography`) · JWT PyJWT
- Dépendances autorisées : `requests`, `pandas`, `python-dotenv`, `pydantic`, `click`, `rich`, `google-auth`, `google-api-python-client`, `pyyaml`, `fastapi`, `uvicorn`, `httpx`, `cryptography`, `pyjwt`

### Infrastructure async (implémentée — tâche 55)
- **Async job queue** : Postgres-backed (pattern pg-boss simplifié en Python) — pas de Redis pour rester ≤ 12 €/mois
- Gère : audits background, batch LLM, retry exponentiels, rate-limit Shopify, synchro GSC

### Couche app Shopify (implémentée — tâche 56)
- **Scaffold** : Shopify CLI → `shopify app create` → Remix (TypeScript)
- **Inclus d'emblée** : App Bridge v4, Polaris, OAuth Shopify, sessions multi-tenant, routing
- **Dossier** : `shopify-app/` (nouveau, indépendant du Python)
- `frontend/` React existant → décommissionné après tâche 57

### IA & NLP (implémentée — Phase 7)
- LLM principal : OpenAI GPT-4o mini (`openai` SDK) — prompts déterministes, templates versionnés
- Fallback gratuit : Cloudflare Workers AI (`httpx`) + Groq (`groq` SDK)
- Embeddings : `sentence-transformers` local (`multilingual-e5-base`) — 0 €, ~400 Mo
- NLP : `spacy` + `fr_core_news_lg` pour entity extraction (matières, certifications, origines)
- **Pas de LangChain** — sur-engineering pour des prompts déterministes

### Niche Intelligence (implémentée — tâches 62-63)
- Étape 1 — sources légères (tâche 63) : Google Suggest + pytrends + Reddit scraping
- Étape 2 — moteur (tâche 62) : clustering produits, analyse saturation SERP, keyword gaps vs concurrents
- Étape 3 — avancé (tâche 74) : Common Crawl / Web Graph backlinks

### Base de données (implémentée — Phases 6 & 8)
- Neon Postgres serverless (scale-to-zero, free tier 0,5 Go) pour le multi-tenant
- SQLite conservé comme fallback/local historique selon modules
- Extension `pgvector` activée pour embeddings (tâche 70)

### APIs externes
- Shopify Admin API GraphQL
- Google Search Console API
- PageSpeed Insights API
- GA4 Data API
- Ahrefs Webmaster Tools API si disponible côté tenant/config
- Screaming Frog Free via exports CSV manuels

### Modules implémentés à maintenir
- `app/llm/` — provider abstraction + prompts
- `app/niche/` — Niche Intelligence engine
- `app/jobs/` — async queue Postgres-backed
- `app/billing/` — Shopify Billing API wrapper
- `app/observability/` — logs structurés + métriques tenant + coût LLM
- `shopify-app/extensions/` — Shopify Theme App Extension JSON-LD

**Demander confirmation avant toute autre dépendance.**

---

## 7. GESTION DU CONTEXTE AVEC CODEX

- Codex Desktop compacte automatiquement le contexte quand nécessaire ; ne pas utiliser les anciennes commandes Claude Code `/compact` ou `/clear`.
- Ne pas utiliser les anciennes commandes Claude Code `/review`, `/plan` ou `!<cmd>` comme workflow ; demander simplement une review ou un plan en langage naturel, et laisser Codex utiliser ses outils.
- Pour les tâches longues, préserver l'état durable dans `PROGRESS.md` avant de continuer : objectif, fichiers touchés, commandes lancées, tests, blocages, prochaine étape.
- Après une compaction ou reprise de session, relire `PROGRESS.md`, `ROADMAP.md`, puis les fichiers concernés avant de modifier.
- Si le fil devient ambigu, s'appuyer sur les fichiers du repo plutôt que sur la mémoire de conversation.
- Utiliser `update_plan` pour suivre les tâches complexes pendant la session, et mettre à jour `PROGRESS.md` pour tout suivi qui doit survivre à la session.

---

## 8. SUBAGENTS CODEX (`.codex/agents/`)

- `shopify-safety` — critères de review sécurité avant tout `--apply`
- `python-quality` — critères de review qualité avant chaque commit

Dans Codex, la délégation à un subagent n'est utilisée que si elle est explicitement disponible et appropriée. Sinon, appliquer localement les mêmes critères de review.

---

## 9. ARBORESCENCE

```
shopify-app/            ← [Phase 6] Scaffold Remix (Shopify CLI) — couche app
  app/                  ← routes Remix (UI Polaris, App Bridge v4, OAuth sessions)
  extensions/           ← [Phase 8] Theme App Extension (JSON-LD)
  package.json          ← dépendances Node (@shopify/polaris, app-bridge, remix)

app/                    ← Backend Python (moteur SEO/IA — conservé intégralement)
  api/                  ← endpoints REST appelés par shopify-app/ via HTTP
  jobs/                 ← [Phase 6] async queue Postgres-backed
  llm/                  ← [Phase 7] provider abstraction + prompts Jinja2
  niche/                ← [Phase 7] Niche Intelligence engine
  observability/        ← [Phase 7] logs structurés, métriques, coût LLM
  db.py                 ← schéma SQLite (→ Postgres Phase 6)
  main.py               ← entry point FastAPI (port 8000)

scripts/                ← pipeline CLI (moteur SEO — réutilisable)
  audit/                ← lecture seule (crawl, GSC, PageSpeed, detection)
  apply/                ← écriture Shopify (dry-run par défaut)
  report/               ← génération rapports Markdown

frontend/               ← Dashboard React LEGACY (décommissionné après tâche 57)

config/
  tenants/              ← YAML par boutique (leoniedelacroix.yaml)
  niches/               ← YAML par secteur (pet_accessories_fr, etc.)
  prompts/              ← [Phase 7] templates Jinja2 par type de contenu

data/
  history.db            ← SQLite (→ Neon Postgres Phase 6)
  raw/                  ← exports bruts (gitignored)

reports/YYYY-MM-DD/     ← rapports horodatés
.github/workflows/      ← CI/CD hebdomadaire
```

---

## 10. COMMANDES FRÉQUENTES

```bash
# Audit SEO
leonie-seo audit crawl          # snapshot catalogue Shopify
leonie-seo audit gsc            # données GSC 90 jours
leonie-seo audit pagespeed      # Core Web Vitals
leonie-seo audit detect         # détection problèmes

# Rapports
leonie-seo report weekly        # rapport Markdown hebdomadaire
leonie-seo report delta         # comparaison avant/après

# Application (dry-run par défaut)
leonie-seo apply meta --dry-run
leonie-seo apply meta --apply
leonie-seo apply alt --dry-run
leonie-seo apply rollback --last 5

# Licences
leonie-seo license issue --tenant <id> --plan pro --days 365
leonie-seo license check

# API web
uvicorn app.main:app --reload   # port 8000
cd shopify-app && npm run dev    # app Remix Shopify
```

---

## 11. FICHIERS DE RÉFÉRENCE

| Fichier | Rôle |
|---|---|
| `ROADMAP.md` | Statuts ✅/🔄/⏳ des 75 tâches — **mettre à jour après chaque tâche** |
| `PROGRESS.md` | État session par session, blocages, métriques |
| `DECISIONS.md` | Journal des choix techniques + décisions ouvertes |
| `RAPPORT_AUDIT.md` | Archive de l'audit gap initial — historique, pas état courant |
| `AUDIT_CLAUDE_CODE.md` | Archive du brief d'audit Claude Code — historique, pas consigne active Codex |
| `CONTEXT.md` | Fiche marché, concurrents, mots-clés stratégiques |
| `docs/guide-utilisateur.fr.md` | Guide marchand FR |
| `docs/user-guide.en.md` | Merchant guide EN |
| `skills/seo-technique.md` | Seuils et règles de scoring SEO |
| `skills/shopify-graphql.md` | Patterns GraphQL sûrs et rate limiting |
