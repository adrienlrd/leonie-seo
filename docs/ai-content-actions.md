# AI Content Actions Simplification — Giulio Geo

> Référence canonique du workflow unique de génération de contenu IA. Fusionne meta titles, meta descriptions, descriptions produits, alt text, FAQ, Answer Blocks, guides courts et JSON-LD FAQPage en **un seul orchestrateur** alimenté par les faits confirmés, Shopify, GSC/GA4 et les hypothèses marchand validées.
>
> Statut : décisions produit/architecture figées au 2026-05-20 (tâche 134, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

État actuel — **7 générateurs et 5 workflows disjoints** :

| Contenu | Module | Prompt | Problème |
|---|---|---|---|
| Meta titles | `app/llm/batch.py:76` | `meta_title.yaml:3` | Contexte hardcodé "accessoires premium pour animaux" |
| Meta descriptions | `app/llm/batch.py:90` | `meta_description.yaml:3` | Idem |
| Descriptions produits | `config/prompts/product_description.yaml:3` | YAML | Idem |
| Alt text | `config/prompts/alt_text.yaml` | YAML | Générique mais non injecté |
| FAQ / Answer Blocks | `app/geo/faq_generator.py:283` | **Template, pas de LLM** | Aucun enrichissement hypothèse marketing |
| Blog briefs | `app/llm/briefs.py:68` | `blog_brief.yaml:3` | Hardcodé idem |
| Collection briefs | `app/llm/briefs.py:158` | `collection_brief.yaml:3` | Hardcodé idem |
| Multilingual meta | `app/llm/multilingual.py:72` | `meta_multilingual.yaml` | Texte regex-parsé (pas JSON) |

Problèmes majeurs :

- **`niche_hypothesis` jamais consommé** — l'investissement de la tâche 130 ne se traduit pas en sortie de contenu.
- **Faits inventables** — pas de garde-fou structurel `confirmed_facts only`.
- **Markdown brut** côté briefs au lieu de JSON structuré.
- **5 workflows UI** (`app.review`, `app.descriptions`, `app.geo-faq-content`, briefs API-only…) sans cohérence.

La tâche 134 fixe un **workflow unique** : un orchestrateur central appelé par chaque action prioritaire (tâche 133), un seul schéma de sortie JSON commun, des prompts uniformément alimentés par `niche_hypothesis` + `confirmed_facts` + GSC/GA4 + Shopify, une review humaine obligatoire, et un branchement direct sur Safe Apply (135).

C'est le **plus gros consommateur LLM** de la Phase 11.7 — donc le respect strict de `docs/llm-strategy.md` est non négociable.

---

## 2. Workflow unique « Content Action »

```
1. Trigger          ← bouton "Préparer cette action" depuis Priority Engine (133)
2. Bundle inputs    ← faits confirmés + Shopify + GSC + niche_hypothesis + previous content
3. Route LLM tier   ← low-cost / medium selon content_type (cf. §4)
4. Generate         ← appel LLMRouter (`app/llm/router.py:70`) avec prompt versionné
5. Validate schema  ← JSON structuré contractuel + faits utilisés tracés
6. Audit guardrails ← confirmed_facts_only, forbidden_promises, do_not_say, longueurs
7. Persist as draft ← table `content_actions` (à créer par tâche d'implémentation)
8. Human review     ← workflow Safe Apply (135) — diff, accept/edit/reject
9. Dry-run apply    ← preview Shopify-side
10. Real apply      ← `app/apply/shopify_writer.py:16` après confirmation marchand
11. Event tracking  ← Impact Tracker (136) capture snapshot avant/après
```

Un seul orchestrateur (`app/content_actions/runner.py`, à créer post-134), un seul endpoint d'entrée (`POST /api/shops/{shop}/content-actions/run`), un seul format de sortie.

---

## 3. Types de contenu pris en charge

| `content_type` | Description | Application Shopify | Statut V1 |
|---|---|---|---|
| `meta_title` | Title SEO produit ou collection | `productUpdate.seo.title` | ✅ Migré dans le workflow |
| `meta_description` | Description SEO produit ou collection | `productUpdate.seo.description` | ✅ Migré |
| `product_description` | Description HTML produit | `productUpdate.descriptionHtml` | ✅ Migré |
| `collection_description` | Description collection | `collectionUpdate.descriptionHtml` | ✅ Migré |
| `alt_text` | Alt text d'une image produit | `productImageUpdate.image.altText` | ✅ Migré |
| `faq_block` | FAQ produit ou collection (Q/A) | Metafield `faq.items` ou Theme block | ✅ Migré (avec LLM en plus du template) |
| `answer_block` | Bloc de réponse court (1-2 phrases) | Metafield `answer.block` | ✅ Migré |
| `buying_guide` | Guide d'achat court (3-5 sections) | Metafield `guide.sections` ou article blog | ✅ Migré |
| `jsonld_faqpage` | JSON-LD FAQPage | Theme App Extension (existant tâche 69) | ✅ Migré |
| `meta_multilingual` | Variantes EN/DE/NL/FR | Metafields locale-aware | ⚠ V1 = FR + EN, autres locales V2 |

Hors V1 (laissé en place mais hors orchestrateur unifié) :

- **Blog briefs** — `app/llm/briefs.py:68`, exclu du workflow Content Actions car ne touche pas une page produit/collection existante (cf. `docs/opportunity-finder.md` §2). Reste accessible en mode avancé.
- **Génération massive d'articles blog** — explicitement repoussée hors MVP public (cf. Phase 11.7 overview).

---

## 4. Mapping `content_type` → tier LLM

Cohérent avec `docs/llm-strategy.md` §3 (mapping consommateurs → tier).

| `content_type` | Tier | Modèle par défaut | Justification |
|---|---|---|---|
| `meta_title`, `meta_description`, `alt_text` | `low-cost` | Groq `llama3-70b-8192` | Extraction / reformulation courte, déterministe |
| `product_description`, `collection_description` | `medium` | OpenAI `gpt-4o-mini` | Synthèse plus longue, ton de marque à respecter |
| `faq_block`, `answer_block`, `buying_guide` | `medium` | OpenAI `gpt-4o-mini` | Q/R structurée, faits confirmés à mobiliser |
| `jsonld_faqpage` | déterministe Python | — | Construit depuis `faq_block` validé, **pas d'appel LLM** |
| `meta_multilingual` | `low-cost` × N locales | Groq par défaut | Variation de traduction, prompt court par locale |

Conséquences :

- **Plan Free** : pas d'`advanced`, mais low-cost + medium accessibles selon quotas (cf. `docs/llm-strategy.md` §5).
- **Mode `low-cost only`** : `product_description`, `faq_block`, `answer_block`, `buying_guide` sont dégradés vers low-cost.
- **`jsonld_faqpage` n'appelle jamais le LLM** — c'est une conversion déterministe Python depuis le `faq_block` accepté.

---

## 5. Bundle d'inputs LLM

Pour chaque content_type, l'orchestrateur assemble **un seul bundle** déterministe avant l'appel LLM :

```json
{
  "content_type": "string",
  "resource": {
    "type": "product|collection|article",
    "id": "string",
    "handle": "string",
    "title": "string",
    "current_seo": {"title": "string|null", "description": "string|null"},
    "current_description_html": "string|null",
    "primary_image_alt_text": "string|null"
  },
  "confirmed_facts": [
    {"key": "materials|dimensions|origins|certifications|...", "value": "string", "source": "shopify|merchant"}
  ],
  "missing_facts": [
    {"key": "string", "severity": "sensitive|standard"}
  ],
  "gsc_signals": {
    "top_queries": [{"query": "string", "impressions": int, "clicks": int, "position": float}],
    "intent_distribution": {"informational": float, "transactional": float, ...}
  },
  "ga4_signals": {
    "sessions_30d": int|null,
    "conversions_30d": int|null,
    "avg_order_value": float|null,
    "estimate_basis": "ga4|fallback"
  },
  "niche_context": {
    "primary_niche": "string",
    "brand_voice": {"tone": "string", "register": "string", "do_say": [], "do_not_say": []},
    "marketing_angles": ["string"],
    "customer_segments": [...],
    "forbidden_promises": ["string"],
    "conversational_intents": [{"intent": "string", "example_queries": []}]
  },
  "constraints": {
    "max_length": int|null,
    "min_length": int|null,
    "locale": "fr|en|de|nl",
    "tone_override": "string|null"
  },
  "previous_content": {
    "version": "string|null",
    "content": "string|null",
    "feedback": "string|null"
  }
}
```

### Règles sur le bundle

- **`confirmed_facts` est la seule source autorisée pour les affirmations factuelles.** Aucune autre source ne doit nourrir des claims (matière, origine, certifications, garanties, propriétés médicales).
- **`missing_facts` avec `severity: sensitive`** déclenche le statut `needs_review` automatique (cf. §7).
- **`niche_context` vient de `shop_config.niche_hypothesis`** (cf. `docs/niche-understanding.md` §6). Si `status != "validated_by_merchant"`, l'orchestrateur **refuse l'exécution** et renvoie une erreur explicite côté UI.
- **`previous_content`** permet une boucle de retravail itératif (cf. §11).

---

## 6. Schéma de sortie JSON unifié

Tous les `content_type` partagent un schéma d'enveloppe commun :

```json
{
  "action_id": "string",
  "content_type": "string",
  "resource_id": "string",
  "generated_at": "ISO date",

  "output": {
    "primary_text": "string",
    "structured": "object|null"
  },

  "facts_used": [
    {"key": "string", "value": "string", "source": "shopify|merchant"}
  ],
  "claims_unverified": [
    {"claim": "string", "category": "factual|opinion|hypothesis"}
  ],
  "queries_targeted": ["string"],
  "intents_targeted": ["informational|transactional|commercial|navigational"],

  "constraints_check": {
    "length_ok": true|false,
    "language_ok": true|false,
    "forbidden_promise_violations": ["string"],
    "do_not_say_violations": ["string"]
  },

  "quality": {
    "score": 0-100,
    "label": "excellent|bon|à_compléter|incomplet"
  },

  "status": "draft|needs_review|approved|rejected|exported|applied|reverted",

  "llm_meta": {
    "tier": "low-cost|medium|advanced",
    "provider": "openai|groq|cloudflare",
    "model": "string",
    "prompt_version": "string",
    "tokens_in": int,
    "tokens_out": int,
    "cost_usd": float,
    "cache_hit": true|false
  }
}
```

### Détails par `content_type`

| `content_type` | `output.primary_text` | `output.structured` |
|---|---|---|
| `meta_title` | string court (50-60 chars) | `null` |
| `meta_description` | string (140-160 chars) | `null` |
| `product_description` | HTML | `{ "headings": [], "paragraphs": [] }` |
| `collection_description` | HTML | idem |
| `alt_text` | string (8-12 mots) | `null` |
| `faq_block` | string (rendu lisible) | `{ "items": [{"question": "string", "answer": "string", "facts_used": [...]}] }` |
| `answer_block` | string (1-2 phrases) | `null` |
| `buying_guide` | string (rendu lisible) | `{ "title": "string", "sections": [{"heading": "string", "content": "string", "source": "string"}] }` |
| `jsonld_faqpage` | string (JSON-LD sérialisé) | `{ "@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [...] }` |
| `meta_multilingual` | string (résumé toutes locales) | `{ "fr": {...}, "en": {...}, ... }` |

### Règles sur la sortie

- **`facts_used` est obligatoire et non vide** pour tout contenu à charge factuelle (description produit, FAQ, guide, JSON-LD).
- **`claims_unverified`** liste explicitement ce qui n'est PAS appuyé par un `confirmed_facts`. Vide pour `meta_title` et `alt_text` (descriptifs courts). Pour les contenus longs, toute affirmation hors `confirmed_facts` doit y figurer.
- **`constraints_check.forbidden_promise_violations`** non vide ⇒ statut auto `needs_review`. L'orchestrateur n'auto-approuve **jamais** un contenu qui viole une promesse interdite.
- **`status = applied`** uniquement après confirmation marchand côté Safe Apply (135).
- **`llm_meta`** est obligatoire pour traçabilité coût et debug.

---

## 7. Statuts et transitions

Reprend et étend les statuts du FAQ generator (`app/geo/faq_generator.py:329`).

```
draft → needs_review → approved → exported → applied → reverted
                ↓
            rejected
```

| Statut | Déclencheurs auto |
|---|---|
| `draft` | Génération réussie sans alerte |
| `needs_review` | `forbidden_promise_violations` ou `do_not_say_violations` ≠ ∅, OR `missing_facts.sensitive` ≠ ∅, OR `quality.score < 45` |
| `approved` | Validation explicite marchand côté Safe Apply (135) |
| `rejected` | Rejet explicite marchand |
| `exported` | Téléchargé en CSV/Markdown sans publication Shopify |
| `applied` | Mutation Shopify réussie via `app/apply/shopify_writer.py` |
| `reverted` | Rollback explicite (`docs/...` Safe Apply) |

Aucune auto-application possible en V1, même pour `quality=excellent`. La règle « `human_review_required: true` par défaut » du Priority Engine (133) reste stricte.

---

## 8. Garde-fous d'audit (étape 6 du workflow §2)

Vérifications **systématiques après LLM, avant persistance**.

### 8.1 — `confirmed_facts_only`

Toute affirmation factuelle (regex domaine : `made of`, `fabriqué en`, `certifié`, `garanti N ans`, etc.) doit pouvoir se justifier par un `facts_used`. Sinon → ajout dans `claims_unverified` + `status = needs_review` si la claim est sensible.

### 8.2 — `forbidden_promises`

Match exact + match sémantique (similarité embeddings, `app/embeddings/store.py`) contre `niche_hypothesis.forbidden_promises`. Toute violation → `constraints_check.forbidden_promise_violations` peuplé + `status = needs_review`.

### 8.3 — `do_not_say`

Match exact insensible à la casse contre `niche_hypothesis.brand_voice.do_not_say`. Violations → `constraints_check.do_not_say_violations` + `status = needs_review` (sans suppression auto du contenu — c'est au marchand de trancher).

### 8.4 — Longueurs

| `content_type` | Min | Max |
|---|---|---|
| `meta_title` | 30 | 60 |
| `meta_description` | 120 | 160 |
| `alt_text` | 5 mots | 12 mots |
| `product_description` | 600 chars | 4 000 chars |
| `faq_block` (par Q/R) | 20 chars Q, 40 chars A | 200 chars Q, 600 chars A |
| `answer_block` | 100 chars | 300 chars |
| `buying_guide` | 3 sections | 6 sections |

Hors plage → `constraints_check.length_ok = false` + `status = needs_review`.

### 8.5 — Langue

Détection de langue (lib `langdetect` ou similaire) cohérente avec `constraints.locale`. Mauvaise langue → `language_ok = false` + `status = needs_review`.

### 8.6 — Qualité

`quality.score` calculé selon la même grille que `app/geo/faq_generator.py:320-325` :
- 40 % `confirmed_facts` utilisés / disponibles ;
- 30 % couverture des `queries_targeted` (mots-clés présents) ;
- 20 % contraintes respectées (longueurs, langue, pas de violation) ;
- 10 % cohérence avec `brand_voice` (heuristique simple : registre cohérent).

Score < 45 → `status = needs_review`.

---

## 9. Refactor des prompts existants

Le hardcode `"accessoires premium pour animaux"` est éliminé partout. Chaque prompt YAML reçoit `niche_context` en variable Jinja-like (déjà supporté par `app/llm/prompts.py:88`).

### Plan de migration des prompts

| Prompt | Fichier | Variables à injecter |
|---|---|---|
| `meta_title.yaml` | `config/prompts/meta_title.yaml` | `{{ primary_niche }}`, `{{ brand_voice.tone }}`, `{{ marketing_angles }}`, `{{ confirmed_facts }}` |
| `meta_description.yaml` | idem | + `{{ customer_segments[0].label }}` |
| `product_description.yaml` | idem | + `{{ buying_motivations }}`, `{{ do_not_say }}`, `{{ forbidden_promises }}` |
| `collection_brief.yaml` | idem | + `{{ conversational_intents }}` |
| `blog_brief.yaml` | idem | (conservé, hors workflow Content Actions V1) |
| `alt_text.yaml` | idem | + `{{ primary_niche }}` (très léger) |
| `meta_multilingual.yaml` | idem | + `{{ brand_voice.do_not_say }}` par locale |
| `faq_product.yaml` | **à créer** | Variables complètes — c'est le nouveau prompt LLM qui enrichit le template existant |
| `answer_block.yaml` | **à créer** | idem |
| `buying_guide.yaml` | **à créer** | idem |

### Versioning

Chaque prompt monte de `version: 1.x` à `version: 2.0` pour invalider le cache (`docs/llm-strategy.md` §4).

### Compatibilité ascendante

L'orchestrateur 134 fournit un `niche_context` par défaut (dérivé du snapshot + clusters niche brut) si `niche_hypothesis` n'est pas encore validée. Mais comme indiqué §5, **l'exécution refuse les `content_type` à charge factuelle** (`product_description`, `faq_block`, `buying_guide`) tant que le marchand n'a pas validé. Seuls `meta_title`, `meta_description` et `alt_text` peuvent tourner avec un contexte par défaut.

---

## 10. FAQ : LLM + template, pas LLM-only

Le `app/geo/faq_generator.py` actuel est **template-based** (regex matching + `_FACT_QA_FR`). Il fonctionne sans LLM, ce qui est précieux pour les marchands Free.

Décision V1 :

- Le template existant **reste le fallback** quand LLM indisponible / budget dépassé / plan Free.
- Le LLM enrichit le template : il rédige les `answer` à partir des `confirmed_facts` + `niche_context`, là où le template produit aujourd'hui du texte plus rigide.
- Le marchand voit toujours dans `facts_used` la source utilisée pour chaque Q/R.

Cela évite de jeter le template (qui marche et fonctionne sans coût LLM) tout en ajoutant la valeur LLM aux marchands Pro/Agency.

---

## 11. Boucle de retravail itératif

Le marchand peut demander une **re-génération avec feedback** depuis le workflow Safe Apply (135) :

- L'orchestrateur ré-appelle le LLM avec `previous_content` rempli et un champ `feedback` (texte libre marchand).
- Compte comme un nouvel appel LLM (logué + facturé + budget vérifié).
- Plafonné : **3 retravails max par action** pour éviter les boucles infinies coûteuses.
- Au-delà : le marchand doit éditer manuellement, pas re-générer.

---

## 12. Mapping fichiers

### Existant à réutiliser

| Fichier | Rôle |
|---|---|
| `app/llm/router.py:70` | Appel LLM unique pour tous les content_types |
| `app/llm/prompts.py:88` | Loader prompts YAML avec versioning + interpolation variables |
| `app/llm/batch.py:61` | Logique batch (parallélisation par produit) à généraliser |
| `app/llm/briefs.py:68` | Réutilisé pour `collection_description`, **pas** pour blog (hors V1) |
| `app/llm/multilingual.py:72` | Réutilisé pour `meta_multilingual` |
| `app/geo/faq_generator.py:283` | Template fallback + base de `_FACT_QA_FR` |
| `app/geo/facts.py:89` | Source des `confirmed_facts` |
| `app/shop_config_store.py:1` | Lecture `niche_hypothesis` |
| `app/apply/shopify_writer.py:16` | Mutation Shopify (déjà dry-run par défaut) |
| `app/apply/bulk_orchestrator.py:22` | Orchestrateur apply (déjà rollback + rate-limit) |
| `app/embeddings/store.py` | Détection sémantique `forbidden_promises` |
| `app/observability/metrics.py:12` | Log coût LLM |
| `app/observability/metrics.py:113` | `check_budget` avant LLM |

### À créer par la tâche d'implémentation (post-134)

| Fichier | Rôle |
|---|---|
| `app/content_actions/runner.py` | Orchestrateur unique (workflow §2) |
| `app/content_actions/audit.py` | Garde-fous §8 (confirmed_facts_only, forbidden_promises, longueurs, langue, qualité) |
| `app/content_actions/schema.py` | Schéma JSON commun §6, validation Pydantic |
| `app/api/content_actions.py` | Routes `POST /content-actions/run`, `GET /content-actions/{action_id}`, `POST /retry` |
| `config/prompts/faq_product.yaml` | LLM prompt FAQ produit |
| `config/prompts/answer_block.yaml` | LLM prompt Answer Block |
| `config/prompts/buying_guide.yaml` | LLM prompt guide d'achat court |
| `shopify-app/app/routes/app.content-actions.tsx` | UI unique du workflow |
| Migrations DB : table `content_actions` | Persistance des drafts/approved/applied par action_id |

### À mettre à jour (post-134)

| Fichier | Évolution |
|---|---|
| `config/prompts/meta_title.yaml:3` | Retirer "premium pour animaux", injecter `niche_context` |
| `config/prompts/meta_description.yaml:3` | idem |
| `config/prompts/product_description.yaml:3` | idem |
| `config/prompts/collection_brief.yaml:3` | idem |
| `config/prompts/alt_text.yaml:3` | idem (léger) |
| `config/prompts/meta_multilingual.yaml` | idem + JSON output (sortir du regex parsing) |
| `app/api/generate.py` | Routes existantes conservées en alias pour backward compat, mais marquées `deprecated` |
| `app/jobs/handlers.py:66` | Handler `meta_generation` redirigé vers l'orchestrateur unique |
| `shopify-app/app/routes/app.review.tsx`, `app.descriptions.tsx`, `app.geo-faq-content.tsx` | Migration vers la vue unique `app.content-actions.tsx` |

---

## 13. Endpoints — stratégie

| Endpoint actuel | Statut post-134 |
|---|---|
| `POST /generate/meta` | Conservé en alias deprecated, redirige vers `/content-actions/run?type=meta_title,meta_description` |
| `POST /generate/meta/from-snapshot` | Conservé en alias deprecated |
| `GET /generate/meta/results` | Conservé pour drill-down |
| `GET /generate/meta/diff` | Migré vers Safe Apply (135) |
| `POST /generate/meta/review` | Migré vers Safe Apply |
| `POST /generate/meta/auto-approve` | **Supprimé** — auto-approve incompatible avec `human_review_required: true` |
| `POST /generate/meta/apply` | Conservé tel quel, déjà aligné dry-run |
| `POST /generate/blog-briefs` | Conservé hors workflow V1 |
| `POST /generate/collection-briefs` | Conservé + intégré comme `content_type=collection_description` |
| **`POST /api/shops/{shop}/content-actions/run`** | **À créer** — canonique |
| **`GET /api/shops/{shop}/content-actions/{action_id}`** | **À créer** |
| **`POST /api/shops/{shop}/content-actions/{action_id}/retry`** | **À créer** (3 max) |
| **`POST /api/shops/{shop}/content-actions/{action_id}/export`** | **À créer** (Markdown / CSV / JSON sans apply Shopify) |

---

## 14. Cohérence avec `docs/llm-strategy.md`

| Règle LLM | Application 134 |
|---|---|
| Tiers low-cost / medium / advanced | ✅ Mapping clair §4 |
| Cache `(shop, task_name, prompt_version, content_hash)` | ✅ Clé inclut `resource_id` + `niche_hypothesis_version` |
| TTL par type | ✅ §4 — meta/alt 90 j, FAQ/desc 30 j, jsonld_faqpage déterministe |
| `check_budget` avant `router.complete` | ✅ Obligatoire dans l'orchestrateur |
| Mode low-cost only / Free | ✅ Dégradation transparente |
| Outputs JSON structurés | ✅ Schéma §6 contractuel, obligatoire |
| Prompts YAML versionnés | ✅ Bump v2.0 partout (§9) |
| Aucun appel HTTP direct hors LLMRouter | ✅ |
| Aucune analyse LLM massive sans déclenchement explicite | ✅ Chaque action est lancée depuis 133, jamais en cron massif |
| Checklist d'intégration §12 LLM strategy | ✅ Reprise dans §16 ci-dessous |

---

## 15. Cohérence avec les autres modules Phase 11.7

- **127 Product Scope** : `content-actions/run` refuse de s'exécuter sur produits non `ACTIVE Online Store` (sauf Pre-launch check explicite avec flag).
- **128 Crawl L3** : pas de dépendance directe — Crawl L3 alimente l'audit 131, pas le contenu.
- **129 LLM Strategy** : cf. §14.
- **130 Niche Understanding** : bloque l'exécution si `niche_hypothesis.status != "validated_by_merchant"` pour les content_types à charge factuelle. Injecté en `niche_context` partout.
- **131 Readiness Audit** : `recommended_actions` du score unifié alimente le choix de `content_type` à générer.
- **132 Opportunity Finder** : chaque opportunité indique le `recommended_actions[].category` qui détermine le `content_type`.
- **133 Priority Engine** : déclencheur unique du workflow. Le marchand clique sur une carte 133, ça lance un `content-actions/run`.
- **135 Safe Apply** : consomme la sortie de 134, gère la review, le dry-run et l'apply Shopify.
- **136 Impact Tracker** : capture le snapshot avant/après chaque `applied`.

---

## 16. Checklist d'intégration consommateur LLM (rappel `docs/llm-strategy.md` §12)

À cocher quand l'implémentation 134 démarre :

- [ ] Tier LLM déclaré explicitement par `content_type` (cf. §4).
- [ ] Prompt externalisé `config/prompts/*.yaml` avec `version: 2.x`.
- [ ] Schéma JSON documenté dans chaque prompt YAML (section `schema:`).
- [ ] Clé de cache `(shop, content_type, prompt_version, content_hash, niche_hypothesis_version)`.
- [ ] TTL par `content_type` documenté.
- [ ] `check_budget()` appelé avant chaque `router.complete()`.
- [ ] Comportement de dépassement budget testé.
- [ ] Mode `low-cost only` respecté.
- [ ] Aucun appel HTTP direct hors `LLMRouter`.
- [ ] Log de coût vérifié dans `llm_metrics`.
- [ ] Fallback testé sur au moins un échec provider simulé.

---

## 17. Critères d'acceptation de l'implémentation future

À cocher quand la tâche concrétise les Content Actions unifiées :

- [ ] Un seul endpoint `POST /content-actions/run` couvre tous les `content_type`.
- [ ] Un seul schéma JSON de sortie (§6).
- [ ] `confirmed_facts` est la **seule** source autorisée pour les affirmations factuelles.
- [ ] `niche_hypothesis.status == "validated_by_merchant"` requis pour les content_types à charge factuelle.
- [ ] `forbidden_promises` et `do_not_say` violations marquent automatiquement `needs_review`.
- [ ] `jsonld_faqpage` est généré déterministiquement depuis `faq_block` accepté (pas d'appel LLM).
- [ ] Plan Free et mode low-cost only dégradent vers low-cost.
- [ ] Aucune auto-approbation : `human_review_required: true` est strict.
- [ ] Retravail itératif plafonné à 3.
- [ ] Migration prompts hardcodés `"premium animaux"` complète (bump v2.0).
- [ ] UI unique `app.content-actions.tsx` remplace `app.review`, `app.descriptions`, `app.geo-faq-content` en entrée principale (drill-downs accessibles).
- [ ] Tests : génération avec `niche_hypothesis` validé OK, refus si non validé pour `product_description`, garde-fou `forbidden_promises` déclenche `needs_review`, retravail × 3 → erreur 4ᵉ tentative.
- [ ] Checklist `docs/llm-strategy.md` §12 cochée (cf. §16).

---

## 18. Limites V1 explicites

- **Pas de génération massive d'articles blog.** Reste hors workflow Content Actions. Blog briefs accessibles en mode avancé uniquement.
- **Pas de génération de pages CMS Shopify** en V1 (Pages → V1.1).
- **Pas de génération vidéo / podcast / image.** Texte structuré seulement.
- **Pas d'auto-traduction au-delà de FR + EN** en V1. DE/NL en V2 même si techniquement le prompt `meta_multilingual.yaml` existe.
- **Pas de modèle de fine-tuning par shop.** Tout passe par le prompt + `niche_context`.
- **Pas d'A/B testing automatique** des contenus générés (gardé pour 136 + futur).

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Workflow unique en 11 étapes | ✅ Spécifié | Section 2 |
| 10 `content_type` pris en charge | ✅ Listés | Section 3 |
| Mapping tier LLM par content_type | ✅ Décidé | Section 4 |
| Bundle d'inputs LLM unique | ✅ Spécifié | Section 5 |
| Schéma JSON unifié de sortie | ✅ Spécifié | Section 6 |
| Statuts et transitions | ✅ Documentés | Section 7 |
| Garde-fous audit (6 checks) | ✅ Documentés | Section 8 |
| Refactor prompts hardcodés v2.0 | ✅ Planifié | Section 9 |
| FAQ LLM + template fallback | ✅ Décidé | Section 10 |
| Boucle retravail (3 max) | ✅ Cadrée | Section 11 |
| Cohérence stratégie LLM | ✅ Vérifiée | Section 14 |
| Cohérence autres modules 11.7 | ✅ Vérifiée | Section 15 |
| Création `app/content_actions/runner.py` + `audit.py` + `schema.py` | ⏳ À porter | Section 12 |
| Création `app/api/content_actions.py` (routes canoniques) | ⏳ À porter | Section 12 |
| UI `app.content-actions.tsx` unique | ⏳ À créer | Section 12 |
| Migration prompts hardcodés `"premium animaux"` | ⏳ À porter | Section 9 |
| Migration 5 workflows UI vers le workflow unique | ⏳ À porter | Section 12 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 134. Ils seront pris en charge par la tâche d'implémentation Content Actions ultérieure et par 135 (Safe Apply qui consomme la sortie de 134) + 137 (Dashboard).
