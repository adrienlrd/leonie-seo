# ARCHIVE — AUDIT CODE HISTORIQUE

> Rapport d'audit conservé pour traçabilité. Les règles actives Codex sont dans `AGENTS.md`.

# AUDIT CODE — Lot 2 du grand audit (2026-05-12)

> Audit code Python `app/` (12 654 lignes, 40 modules) — 4 sous-arbres scannés en parallèle par 4 agents `general-purpose` indépendants.
> **Lecture seule, aucune modification appliquée**. Le but de ce document est de fournir l'inventaire factuel pour le Lot 4 (corrections).

---

## TL;DR (à lire en priorité)

**Verdict global** : le code est **techniquement riche** (960 tests, ruff clean, architecture modulaire propre) mais souffre de **17 bugs bloquants pour la soumission App Store**, principalement liés à 3 thèmes :

1. **Fuites cross-tenant systémiques** : 4 modules globent des fichiers sans filtre par shop, 2 tables critiques (`seo_changes`, `snapshots`) n'ont pas de colonne `shop`, 1 endpoint (`GET /api/shops`) expose tous les tenants sans auth.

2. **Sécurité Billing & Jobs cassée** : `/billing/confirm` accepte n'importe quel `?shop=` sans HMAC ni vérification Shopify → bypass de paiement. `POST /api/jobs` et `GET /jobs/{id}` sans auth → enumeration cross-tenant.

3. **Brand-lock hardcodé** : 4 fichiers contiennent `"Léonie Delacroix"`, `"leoniedelacroix"`, des stopwords FR, ou des subreddits petfood → le moteur IA ne fonctionne en pratique **que pour Léonie**.

**S'y ajoute** un **anti-hallucination quasi-inexistant** sur les outputs LLM (le différenciateur produit), du **code mort** (`app/api/plans.py` jamais monté, modules niche jamais câblés dans `engine.py`), et **16 violations de la règle `AGENTS.md` "jamais `except Exception` nu"**.

---

## Inventaire complet par module

### 1. Layer API (`app/api/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `apply.py` | 96 | ✅ Core | ⚠️ L45 `raise exc` perd stacktrace | — | ✅ |
| `audit.py` | 83 | ✅ Core | — | — | ✅ |
| `deps.py` | 142 | ✅ Core | ⚠️ L33 `LEONIE_REQUIRE_SESSION_TOKEN` fail-open en défaut | 🟡 fallback env mono-tenant L102-111 | 🟡 |
| `embeddings.py` | 104 | ✅ Core | ⚠️ L57 `asyncio.get_event_loop()` deprecated, charge modèle 400 Mo à 1er call sans pré-warming | — | ✅ |
| **`ga4.py`** | 86 | ✅ Core | **🔴 L19-26 `GA4_PROPERTY_ID` env globale → mono-tenant strict** | 🗑️ env globale à migrer | ❌ |
| `generate.py` | 303 | ✅ Core | ⚠️ L76 accès privé `base_router._providers`, L264/297 `get_event_loop()` deprecated | — | ✅ |
| **`help.py`** | 210 | 🟡 | **🔴 L137-144 affirme "outil auto-hébergé, vos données ne quittent jamais"** — mensonge pour SaaS App Store. L168 mention édition manuelle `theme.liquid` (viole règle 13) | 🟡 contenu CLI-centric | ✅ |
| `impact.py` | 58 | ✅ Core | — | — | ✅ |
| `jsonld.py` | 94 | ✅ Core | ⚠️ L55/77 `product_id: int` mais Shopify utilise GID string | — | ✅ |
| `multilingual.py` | 107 | ✅ Core | ⚠️ L76 accès privé `_providers`, L77 `get_event_loop()` deprecated | — | ✅ |
| **`niche.py`** | 208 | ✅ Core | **🔴 L26-67 `_load_snapshot`/`_load_gsc` ignorent `shop`, globent tous les fichiers → fuite cross-tenant. 🔴 L65 `except (json.JSONDecodeError, OSError, (KeyError, IndexError))` tuple imbriqué INVALIDE → TypeError runtime, code mort silencieux.** L17 router sans prefix `/api` (incohérence) | 🟡 logique pré-OAuth | ❌ |
| `observability.py` | 50 | ✅ Core | — | — | ✅ |
| **`plans.py`** | 77 | 🟡 | **🗑️ JAMAIS MONTÉ dans `main.py` → code mort actif.** L53-71 mélange HMAC license et Billing API (deux vérités) | 🗑️ à supprimer ou monter | 🟡 |
| **`privacy.py`** | 189 | ✅ Core | **🔴 L19-127 page privacy hardcodée "outil auto-hébergé, aucune donnée à des serveurs tiers" — faux en mode App Store, risque rejet App Review.** L175 commentaire monkey-patch (odeur code testable) | 🟡 wording à réécrire | 🟡 |
| `session_token.py` | 73 | ✅ Core | ⚠️ L67 `payload["_shop"] = ...` mute payload (convention surchargée) | — | ✅ |
| **`shops.py`** | 46 | ✅ Core | **🔴 L15-18 `GET /api/shops` AUCUNE AUTH → liste tous les shops installés publiquement** | — | ❌ |
| `suggestions.py` | 42 | 🟡 | ⚠️ L17-23 fallback legacy flat → fuite si dossier par-shop absent | 🗑️ fallback à supprimer | 🟡 |
| `web_graph.py` | 118 | ✅ Core | ⚠️ L49/80/115 accès privé `client._cached_crawl`. Pas de plan/feature gating | — | ✅ |

---

### 2. Layer OAuth (`app/oauth/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `crypto.py` | 60 | ✅ Core | — Fernet propre | — | ✅ |
| `gdpr.py` | 96 | ✅ Core | ⚠️ L34-42 stocke body webhook brut en DB (PII client en clair >30j) | — | ✅ |
| `hmac_validator.py` | 42 | ✅ Core | — Constant-time correct | — | ✅ |
| `router.py` | 101 | ✅ Core | ⚠️ L86 `AsyncClient` sans timeout explicite. L96 `data["access_token"]` non validé | — | ✅ |
| `state_store.py` | 60 | ✅ Core | — Atomicité OK | — | ✅ |
| `token_store.py` | 68 | ✅ Core | ⚠️ L60-64 court-circuit SQLite-only à retirer post-Postgres | 🟡 | ✅ |
| `webhooks.py` | 66 | ✅ Core | ⚠️ L55-56 `raise HTTPException` sans `from exc`. Pas de vérif que `subscription_gid` correspond à un shop | — | ✅ |

**Verdict** : module **solide**, prêt App Store sur la mécanique. Seul point d'attention : `gdpr.py` stocke des PII en clair.

---

### 3. Layer LLM (`app/llm/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| **`__init__.py`** | 60 | ✅ Core | **🔴 L20 `lru_cache(maxsize=1)` sur `get_router()` SANS clé tenant → fuite cross-tenant + `shop=None` partout sauf workaround `multilingual.py:76`** | — | ❌ |
| **`router.py`** | 107 | ✅ Core | **🔴 L40 `except Exception:` nu (viole règle `AGENTS.md`). L104 n'attrape pas les exceptions inattendues du provider → chaîne fallback peut être interrompue.** Pas d'anti-hallucination niveau router | — | 🟡 |
| `provider.py` | 60 | ✅ Core | ⚠️ `CompletionResult` ne stocke pas `cost_usd`/`latency_ms`/`request_id` | — | ✅ |
| `providers/openai.py` | 67 | ✅ Core | ⚠️ Validation `response.choices` non vide absente (IndexError silencieux). Pas de `seed` ni `response_format=json` | — | ✅ |
| `providers/cloudflare.py` | 75 | ✅ | **⚠️ L71 ne renseigne JAMAIS `tokens_in`/`tokens_out` → coût Cloudflare INVISIBLE dans les métriques** | — | ✅ |
| `providers/groq.py` | 67 | ✅ | ⚠️ Quasi-clone de `openai.py` (duplication) | 🟡 refactor possible | ✅ |
| `prompts.py` | 105 | ✅ Core | ⚠️ Pas de validation `system`/`user` non vides | — | 🟡 |
| **`batch.py`** | 131 | ✅ Core | **🔴 L14 `_BRAND_WORDS` regex hardcodée à Léonie Delacroix → casse pour toute autre boutique.** L121 `except Exception:` nu | 🔴 brand-locked | ❌ |
| **`multilingual.py`** | 174 | ✅ Core | **🔴 L22 même brand-lock que `batch.py`. L94 `brand = "Léonie Delacroix"` codé en dur.** L20-21 parsing `TITLE:/DESCRIPTION:` fragile sans retry | 🔴 brand-locked | ❌ |
| `briefs.py` | 241 | ✅ Core | ⚠️ L11 import `_classify_intent` privé (encapsulation cassée). L99 `competitor_titles=[]` hardcodé. L142/230 `except Exception:` nus | — | 🟡 |
| `meta_store.py` | 136 | 🟡 | ⚠️ SQLite direct (à migrer Postgres). Pas de `cost_usd` par suggestion | — | ✅ |
| `review.py` | 94 | ✅ | **⚠️ Seul contrôle : longueurs. Aucune vérif keyword cible, brand, langue, ni claims inventés → anti-hallucination minimal** | — | ✅ |

---

### 4. Layer Niche (`app/niche/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `models.py` | 71 | ✅ Core | — Dataclasses pures | — | ✅ |
| **`engine.py`** | 40 | ✅ Core | **🟡 Ne consomme PAS `signals/`, `intent.py`, `ner.py`, `brand_signals.py` → pipeline INCOMPLET vs promesse "niche-first concret"** | 🟡 sous-câblé | ✅ |
| `clustering.py` | 206 | ✅ Core | ⚠️ Stopwords FR-only hardcodés L13-82. ⚠️ TF-IDF maison au lieu d'embeddings `multilingual-e5-base` annoncés en Phase 7 → clustering purement lexical | 🟡 | 🟡 |
| `gaps.py` | 168 | ✅ Core | ⚠️ L35 `_saturation` label trompeur (position ≤10 = "low saturation" alors que top 10 SERP = forte concurrence battue). ⚠️ Pas de vraie analyse SERP (juste position GSC du shop) | 🟡 promesse partielle | ✅ |
| **`intent.py`** | 360 | ✅ Core | **🔴 L141 signaux NAVIGATIONAL contiennent "leonie", "leoniedelacroix" → brand-lock.** Non importé par `engine.py` (zombie) | 🟡 brand-locked + non câblé | ❌ |
| **`ner.py`** | 225 | ✅ Core | **🔴 Vocab L51-123 petfood-only et FR-only.** spaCy annoncé mais juste regex rule-based | 🟡 vocab à externaliser | ❌ |
| `brand_signals.py` | 69 | 🟡 Phase 8 | ⚠️ Wrapper mince sans normalisation par autorité | 🟡 Phase 8 | ✅ |
| `web_graph.py` | 205 | 🟡 Phase 8 | ⚠️ L42 `_cached_crawl` cache d'instance partageable. L199 `except Exception:` nu | 🟡 | 🟡 |
| `signals/aggregator.py` | 85 | ✅ Core | **🔴 L49/60/73 trois `except Exception:` nus**. Aucune persistance/cache | — | ❌ pas de quota |
| `signals/google_suggest.py` | 103 | ✅ Core | **🔴 L50 `except Exception:` nu**. UA générique → 429 en prod | — | 🟡 |
| `signals/trends.py` | 100 | ✅ Core | **🔴 L52 `except Exception:` nu**. `keywords[:5]` tronque silencieusement | — | 🟡 |
| **`signals/reddit.py`** | 103 | ✅ Core | **🔴 L74 `except Exception:` nu. 🔴 L21 subreddits `_DEFAULT_SUBREDDITS = ["chiens", "chat_fr", ...]` petfood-only** | 🟡 niche-locked | ❌ |

---

### 5. Layer Billing (`app/billing/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `client.py` | 141 | ✅ Core | ⚠️ Pas de `test: true` (sandbox dev impossible). Pas de `trialDays`/`replacementBehavior` (upgrade Pro→Agency créera 2 subs concurrentes). L63-75 `_graphql` n'attrape pas `httpx.HTTPStatusError` | — | ✅ |
| **`router.py`** | 135 | ✅ Core | **🔴 L123-135 `/billing/confirm` AUCUNE vérif HMAC, AUCUN `charge_id`, AUCUN re-query Shopify → bypass de paiement total.** 🔴 L130-132 race condition (deux subs `pending` parallèles). L100-115 `cancel` ignore les status `frozen`/`cancelled`/`expired` | — | ✅ |
| `subscription_store.py` | 86 | ✅ Core | ⚠️ L11-12 `_ACTIVE_STATUSES = {"active"}` ignore `accepted` et `frozen`. ⚠️ `ON CONFLICT(shop)` écrase l'historique → pas d'audit trail | — | ✅ |

**Verdict** : Le flow `appSubscriptionCreate` existe mais le callback est **vulnérable à un bypass de paiement** — **bloquant App Store review**.

---

### 6. Layer Jobs (`app/jobs/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| **`store.py`** | 199 | ✅ Core | **🔴 L107-148 `claim_next` non atomique Postgres multi-worker (manque `FOR UPDATE SKIP LOCKED`).** ⚠️ Aucune notion de "stuck job" (job `running` orphelin reste running ad vitam) | — | 🟡 |
| `worker.py` | 129 | ✅ Core | ⚠️ L19-21 backoff sans jitter. L91-94 `asyncio.wait_for` ne tue pas les threads `run_in_executor` → fuite ressources. L61 `except Exception:` nu | — | ✅ |
| `handlers.py` | 108 | ✅ Core | ⚠️ L40-47 `handle_seo_audit` est un stub qui retourne `"queued"` immédiatement. L74 `get_router()` sans `shop=` → tous les jobs background attribués à `shop=None`. ⚠️ `payload.get("dry_run", True)` ne distingue pas "absent" vs `False` explicite | — | ✅ |
| **`router.py`** | 61 | ✅ Core | **🔴 L25-38 `POST /api/jobs` AUCUNE auth ni ownership check → enqueue cross-tenant possible.** 🔴 L41-49 `GET /jobs/{job_id}` ne filtre pas par shop → enumeration possible | — | ❌ |

---

### 7. Layer Apply (`app/apply/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| **`bulk_orchestrator.py`** | 164 | ✅ Core | **🔴 L59-63 `_log_applied` insère `old_value=NULL` → rollback IMPOSSIBLE pour bulk_apply.** ⚠️ L119 pas de feature gating plan (Free peut déclencher apply) | — | 🟡 |
| `shopify_writer.py` | 193 | ✅ Core | ⚠️ Retry 429 vs 5xx pas distingués. ⚠️ Ignore le header `X-Shopify-Shop-Api-Call-Limit` (leaky bucket). ⚠️ L113 401 token révoqué → continue à hammerer Shopify. ⚠️ L155/192 `time.sleep` bloquant event loop | — | ✅ |

---

### 8. Layer Embeddings (`app/embeddings/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| **`encoder.py`** | 53 | ✅ Core | **🔴 L40 `encode_texts` applique le préfixe E5 `query:` aux PASSAGES (devraient être `passage:`) → DÉGRADATION SILENCIEUSE de la qualité du recall.** ⚠️ L13-24 `_get_encoder()` lazy-init non thread-safe | — | n/a |
| `store.py` | 296 | ✅ Core | ⚠️ L77-92 recalcule normes alors que vecteurs déjà L2-normalisés (2× plus lent SQLite). ⚠️ Interpolation SQL d'identifiants sans whitelist | — | ✅ |

---

### 9. Layer Impact (`app/impact/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `calculator.py` | 169 | ✅ Core | ⚠️ Courbe CTR figée Sistrix desktop FR sans variation mobile. ⚠️ L97 sémantique `position_before` ambigu vs latence GSC (2-3j) | — | n/a |
| **`report.py`** | 182 | ✅ Core | **🔴 L25 `sqlite3.connect()` direct → incompatible Postgres.** **🔴 L67 fallback `data/raw/gsc_performance.csv` GLOBAL → fuite cross-tenant.** **🔴 `_load_seo_changes` ne filtre pas par `shop` (la table n'a pas la colonne) → fuite cross-tenant garantie.** ⚠️ L113 `read_text()` sans encoding | — | ❌ |

---

### 10. Layer GA4 (`app/ga4/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `client.py` | 132 | ✅ Core | ⚠️ L46-50 re-auth complet à chaque `run_report` (pas de cache token). ⚠️ L93 `httpx.post` SYNCHRONE bloque event loop FastAPI async | — | 🟡 mapping `shop → property_id` absent |
| `funnel.py` | 109 | ✅ Core | ⚠️ L11-13 `except Exception:` nu. L88-90 `avg_position` non pondérée par impressions → trompeur | — | n/a |
| `queries.py` | 66 | ✅ Core | ⚠️ Pas de pagination > 1000 pagePaths | — | n/a |

---

### 11. Layer JSON-LD (`app/jsonld/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| `builders.py` | 174 | ✅ Core | ⚠️ L11-12 `_strip_html` regex naïve (ne décode pas entités). ⚠️ L41-46 `inventory_management=None` → faux positifs OutOfStock. **⚠️ L72 breadcrumb "Accueil" hardcodé FR → contredit vision FR+EN.** ⚠️ L34-36 prend `variants[0]` au lieu de `AggregateOffer` (multi-variantes biaisé) | — | n/a |

---

### 12. Layer Observability (`app/observability/`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| **`logging.py`** | 86 | ✅ Utile | **⚠️ L13-53 JSON formatter copie TOUS les `extra=` sans whitelist → risque de leak de tokens si appelant fait `logger.info("...", extra={"access_token": "..."})`** | — | 🟡 |
| `metrics.py` | 151 | ✅ Core | ⚠️ L77-87 `error=""` traité comme succès (incohérent). **⚠️ L113-151 `check_budget` jamais appelé avant un LLM call → budget purement informatif, ne protège rien** | — | ✅ |
| `costs.py` | 43 | ✅ Utile | ⚠️ Pricing hardcodé 2025-05 sans versioning. ⚠️ Modèle inconnu → coût 0.0 SANS warning (sous-estimation silencieuse) | — | ✅ |

---

### 13. Layer Foundation (`app/main.py`, `app/db.py`, `app/db_adapter.py`)

| Fichier | LOC | Alignement | Bugs | Legacy | Multi-tenant |
|---|---|---|---|---|---|
| **`main.py`** | 126 | ✅ Core | **⚠️ L42 `init_db()` exécuté à l'import (bloque tests sans Postgres si `DATABASE_URL` mal configuré).** ⚠️ L45-49 `_REQUIRED_ENV` vérifié seulement via `/health` (pas de fail-fast réel au boot). ⚠️ **🗑️ `app/api/plans.py` jamais importé/monté → code mort** | 🗑️ plans.py | — |
| **`db.py`** | 272 | ✅ Core | **🔴 `seo_changes` (L31-40, L191-200) et `snapshots` (L41-47, L201-207) n'ont AUCUNE colonne `shop` → multi-tenant impossible au niveau schéma.** ⚠️ L153-164 PG `called_at TEXT` au lieu de `TIMESTAMP` (incohérent). ⚠️ Aucun système de migration versionnée. ⚠️ L243 `import psycopg2` sans dep dans pyproject | — | 🔴 |
| `db_adapter.py` | 101 | ✅ Core | **⚠️ L24-26 `re.sub(r"\?", "%s", sql)` matche AUSSI les `?` dans les chaînes littérales SQL → risque réel.** ⚠️ Pas de pool psycopg2 (incompatible scale Neon). ⚠️ Sélection backend par "DB_PATH égal au défaut" est fragile | — | ✅ |

---

## Problèmes transverses (rolled-up)

### 🔴 Violations multi-tenant critiques (blocking App Store)

| Source | Type | Sévérité |
|---|---|---|
| `db.py` : `seo_changes` sans `shop` | Schéma | 🔴 |
| `db.py` : `snapshots` sans `shop` | Schéma | 🔴 |
| `api/niche.py` L26-67 : glob de tous les snapshots/GSC | Route | 🔴 |
| `api/shops.py` L15-18 : GET /api/shops sans auth | Route | 🔴 |
| `api/ga4.py` L19-26 : `GA4_PROPERTY_ID` env globale | Config | 🔴 |
| `jobs/router.py` L25-49 : enqueue/get jobs sans auth | Route | 🔴 |
| `impact/report.py` L67 : fallback CSV global | Fichier | 🔴 |
| `llm/__init__.py` L20 : router cached sans clé tenant | Cache | 🔴 |
| `llm/batch.py` L14 : brand Léonie hardcodée | Code | 🔴 |
| `llm/multilingual.py` L22, L94 : brand Léonie hardcodée | Code | 🔴 |
| `niche/intent.py` L141 : "leoniedelacroix" hardcodé | Code | 🔴 |
| `niche/ner.py` L51-123 : vocab petfood-FR hardcodé | Code | 🔴 |
| `niche/signals/reddit.py` L21 : subreddits petfood | Code | 🔴 |

### 🔴 Sécurité (App Store rejection ou exploitation)

| Source | Type | Sévérité |
|---|---|---|
| `billing/router.py` L123-135 : `/billing/confirm` sans HMAC ni `charge_id` | Bypass paiement | 🔴 |
| `api/help.py` + `api/privacy.py` : "outil auto-hébergé" mensonge App Store | Privacy policy fausse | 🔴 |
| `oauth/gdpr.py` L34-42 : body webhook PII en clair >30j | RGPD | ⚠️ |
| `observability/logging.py` L13-53 : `extra=` sans whitelist → leak tokens | Logs | ⚠️ |

### ⚠️ Violations `AGENTS.md` (règle Python : jamais `except Exception` nu)

Total **16 occurrences** détectées :
- `db_adapter.py` L85, L97 (acceptable car branche backend, à confirmer)
- `niche/web_graph.py` L199
- `ga4/funnel.py` L11
- `jobs/worker.py` L61
- `llm/router.py:_record` L40
- `llm/briefs.py` L142, L230
- `llm/batch.py` L121
- `niche/signals/aggregator.py` L49, L60, L73
- `niche/signals/google_suggest.py` L50
- `niche/signals/trends.py` L52
- `niche/signals/reddit.py` L74

### ⚠️ API deprecation (`asyncio.get_event_loop()` en Python 3.11+)

- `api/embeddings.py` L57
- `api/generate.py` L264, L297
- `api/multilingual.py` L77

→ utiliser `asyncio.get_running_loop()` ou `asyncio.to_thread()`.

### ⚠️ Encapsulation cassée (accès attributs privés)

- `api/generate.py` L76, `api/multilingual.py` L76 : `base_router._providers`
- `api/web_graph.py` L49/80/115 : `client._cached_crawl`
- `llm/briefs.py` L11 : import `_classify_intent` privé

### 🗑️ Code mort / Legacy

| Source | Statut | Action recommandée |
|---|---|---|
| `app/api/plans.py` (77 LOC) | Jamais monté dans `main.py` | Supprimer ou monter |
| `scripts/license.py` (HMAC system) | Référencé par 6 fichiers, **viole règle 12** | Décommissionner après bascule App Store ou isoler en mode self-hosted strict |
| `frontend/` complet | Décommissionné (DECISIONS.md) | Supprimer le dossier après tâche 75 |
| `niche/intent.py` (360 LOC) | Non câblé dans `engine.py` (seul `briefs.py` l'importe en privé) | Câbler dans `engine.run_niche_analysis` ou retirer |
| `niche/ner.py` (225 LOC) | Idem zombie | Câbler ou retirer |
| `niche/signals/*` | Présents mais non câblés dans `engine.py` | Câbler |
| `_load_snapshot` dupliqué dans 5 fichiers API | Duplication | Centraliser dans `deps.py` ou `app/api/snapshots.py` |

### 🔴 Anti-hallucination LLM minimal

`app/llm/review.py` ne valide **que la longueur des chaînes**. Manque :
- Présence du keyword cible dans la sortie
- Présence de la brand
- Vérification de la langue (`multilingual.py` peut générer EN au lieu de DE silencieusement)
- Absence de claims inventés
- Retry avec reformulation si format `TITLE:/DESCRIPTION:` invalide

### ⚠️ Cost tracking LLM cassé

- `providers/cloudflare.py` L71 : `tokens_in`/`tokens_out` jamais renseignés → Cloudflare invisible dans les métriques
- `jobs/handlers.py` L74 : `get_router()` sans `shop=` → tous les jobs attribués à `shop=None`
- `llm/meta_store.py` : pas de `cost_usd` par suggestion
- `observability/costs.py` : modèle inconnu → coût 0 sans warning

---

## Synthèse — priorisation pour le Lot 4 (corrections TDD)

### Vague 1 — Bloquants App Store (à corriger avant tâche 75)

1. **Schéma DB multi-tenant** : ajouter `shop` à `seo_changes` et `snapshots` + migration ; passer `impact/report.py` par `db_adapter.get_conn`.
2. **Auth manquantes** : `GET /api/shops`, `POST/GET /api/jobs/*` — ajouter `Depends(get_shop_context)` ou auth admin interne.
3. **Bypass billing** : `/billing/confirm` doit vérifier HMAC + `charge_id` + re-query `currentAppInstallation.activeSubscriptions`.
4. **Privacy policy mensongère** : réécrire `api/privacy.py` + `api/help.py` pour App Store vs self-hosted (deux variantes via env `LEONIE_MODE`).
5. **Cache LLM cross-tenant** : retirer `lru_cache(maxsize=1)` de `get_router()`, exposer `LLMRouter.for_shop(shop)` factory publique.
6. **Brand-lock** : externaliser `_BRAND_WORDS`, brand string, vocab NER, subreddits vers `config/tenants/<shop>.yaml` + `config/niches/<sector>.yaml`.

### Vague 2 — Bugs comportementaux (impactent qualité produit)

7. **E5 prefix bug** : `encode_texts` doit prendre un argument `mode: "query" | "passage"` ou exposer deux fonctions séparées.
8. **Anti-hallucination** : étendre `review.py` (keyword target, brand presence, language detection, retry sur format invalide).
9. **Cost tracking Cloudflare** : implémenter le calcul de tokens (via tiktoken ou estimation char-based).
10. **Jobs `shop` attribution** : tous les handlers doivent passer `shop=` au router LLM.
11. **`niche/engine.py`** : câbler `intent.py`, `ner.py`, `signals/aggregator.py`, `brand_signals.py` ou retirer.
12. **`bulk_orchestrator.py` `old_value=NULL`** : remplir avec la valeur Shopify avant écriture.
13. **`api/niche.py` `except` invalide** : corriger le tuple `(KeyError, IndexError)` imbriqué.

### Vague 3 — Hygiène code (règle `AGENTS.md` + deprecations)

14. **16 violations `except Exception`** : remplacer par exceptions précises (`json.JSONDecodeError`, `httpx.RequestError`, etc.).
15. **`asyncio.get_event_loop()` deprecated** : utiliser `asyncio.to_thread`.
16. **Accès attributs privés** : refactoriser via API publique (`LLMRouter.providers`, `CCIndexClient.crawl_id`).
17. **Logs whitelist** : restreindre les `extra=` au formatter JSON pour éviter les leaks.

### Vague 4 — Cleanup

18. **Code mort** : supprimer `app/api/plans.py` (jamais monté) ou le monter. Câbler les modules niche orphelins.
19. **Snapshots dupliqués** : centraliser le `_load_snapshot` dans `ShopContext`.
20. **`frontend/`** : suppression (après tâche 75 ou maintenant si plus rien ne l'importe).

---

## Recommandation pour le Lot 4

Le **volume de corrections** est conséquent (~30 fix items, certains demandant plusieurs commits). Je recommande de **prioriser la Vague 1** (6 items, bloquants App Store) et de découper en 6 commits TDD atomiques :

1. `feat(db): add shop column to seo_changes and snapshots tables (+ migration)`
2. `fix(api): require shop context on /api/shops, /api/jobs (auth & isolation)`
3. `fix(billing): verify HMAC + charge_id on /billing/confirm callback`
4. `feat(config): dual-mode privacy/help docs (app_store vs self_hosted)`
5. `refactor(llm): remove global router cache, expose for_shop factory`
6. `refactor(niche): externalize brand and sector vocabulary to YAML config`

Chaque commit accompagné de tests qui couvrent le bug original (TDD : test rouge → fix → test vert).

Les vagues 2-4 peuvent suivre dans des cycles ultérieurs sans bloquer la soumission.

---

*Lot 2 terminé. 4 agents parallèles, 12 654 lignes auditées, 17 bugs critiques + 30+ items secondaires identifiés. Aucune modification appliquée. Audit utilisable comme blueprint pour le Lot 4.*
