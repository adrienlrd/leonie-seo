# LLM Strategy & Provider Routing — Giulio Geo

> Référence canonique de l'usage LLM dans Giulio Geo. Tout module consommateur LLM (existant ou futur, en particulier les tâches 130-134 de la Phase 11.7) doit respecter les règles documentées ici.
>
> Statut : décisions produit/architecture figées au 2026-05-19 (tâche 129). Les seuils chiffrés sont des valeurs de départ ajustables, pas des contrats immuables.

---

## 1. Objectif et principes

- L'IA est **une brique centrale de valeur** : compréhension boutique, niche, segments clients, motivations d'achat, génération de contenu, synthèse multi-signaux.
- L'IA n'est **pas un simple générateur de texte**.
- Le coût LLM est maîtrisé dès la conception pour préserver la marge SaaS sur les plans Free / Pro / Agency.
- L'infrastructure existante (tâche 58 : `app/llm/provider.py`, `app/llm/router.py`, providers OpenAI / Groq / Cloudflare ; tâche 68 : `app/observability/metrics.py`, `app/observability/costs.py`) est **réutilisée et étendue**, jamais réécrite.
- Cette stratégie s'applique aux **modules existants** (`app/llm/batch.py`, `app/llm/briefs.py`, `app/llm/multilingual.py`) et aux **modules à venir** (tâches 130-134).

---

## 2. Tiers LLM et règles de routing

Trois tiers explicites, choisis par le module consommateur **avant** l'appel — jamais déduits du fallback.

| Tier | Provider primaire | Modèle | Fallback ordre | Usage |
|---|---|---|---|---|
| `low-cost` | Groq | `llama3-70b-8192` (gratuit) | Cloudflare `@cf/meta/llama-3-8b-instruct` → OpenAI `gpt-4o-mini` | Extraction structurée, classification, meta titles, alt text, normalisation |
| `medium` | OpenAI | `gpt-4o-mini` | Groq `llama3-70b-8192` → Cloudflare `llama-3-8b-instruct` | FAQ, descriptions produits, Answer Blocks, guides courts, opportunity finder, audit synthèse |
| `advanced` | OpenAI | `gpt-4o-mini` (élevé temperature + max_tokens) ou `gpt-4o` si activé | OpenAI `gpt-4o-mini` standard → Groq `llama3-70b-8192` | Compréhension niche (130), priority engine (133), arbitrage multi-signaux, synthèse stratégique |

> Note : `gpt-4o` n'est pas activé par défaut. Il reste un opt-in opérateur. Le tier `advanced` peut tourner en `gpt-4o-mini` avec un prompt enrichi tant que le volume n'exige pas l'escalade.

### Critères d'escalade vers un tier supérieur

Une tâche ne monte d'un tier que si **au moins deux** critères sont remplis :

1. **Volume de contexte** : prompt > 4 000 tokens en entrée.
2. **Valeur business** : la sortie influence directement une décision de priorisation, de stratégie ou un livrable marchand visible.
3. **Ambiguïté** : la tâche exige un raisonnement multi-signaux (croisement Shopify + GSC + GA4 + niche + concurrence).
4. **Variabilité acceptable faible** : la sortie sera comparée dans le temps ou affichée comme verdict.

Sans deux critères remplis, on **reste au tier inférieur**.

### Critères de descente vers `low-cost`

- Mode `low-cost only` activé (cf. section 7).
- Budget shop atteint à 80 % (cf. section 6).
- Plan Free du marchand (cf. section 5).

---

## 3. Mapping tâches consommatrices → tier

### Modules existants (à aligner)

| Module | Fichier | Tier cible |
|---|---|---|
| `meta_title` | `app/llm/batch.py` | `low-cost` |
| `meta_description` | `app/llm/batch.py` | `low-cost` |
| `alt_text` | (prompt `config/prompts/alt_text.yaml`) | `low-cost` |
| `product_description` | `config/prompts/product_description.yaml` | `medium` |
| `blog_brief` | `app/llm/briefs.py` | `medium` |
| `collection_brief` | `app/llm/briefs.py` | `medium` |
| `meta_multilingual` | `app/llm/multilingual.py` | `low-cost` (1 appel/locale, déterministe) |

### Modules à venir Phase 11.7

| Tâche | Module | Tier(s) |
|---|---|---|
| 130 | Merchant Niche Understanding Layer | `advanced` (1 appel par shop, mis en cache long TTL) |
| 131 | Unified AI Search Readiness Audit | `low-cost` (extraction faits) + `medium` (synthèse score & raisons lisibles) |
| 132 | Unified Opportunity Finder | `medium` (regroupement intentions + recommandation par page) |
| 133 | Unified Priority Engine | `advanced` (arbitrage multi-signaux pour les 3 actions prioritaires uniquement) |
| 134 | AI Content Actions Simplification | `low-cost` (meta, alt) + `medium` (FAQ, descriptions, guides courts, Answer Blocks) |

> Règle : la tâche 133 n'utilise `advanced` que pour produire la sélection finale des 3 actions. Le scoring brut reste déterministe (Python pur, signaux Shopify/GSC/GA4).

---

## 4. Cache LLM

### Clé de cache

```
(shop, task_name, prompt_version, content_hash)
```

- `shop` : identifie le tenant.
- `task_name` : `meta_title`, `niche_understanding`, `faq_product`, etc. — correspond au nom du prompt YAML.
- `prompt_version` : champ `version` de `config/prompts/<task>.yaml`. **Bumper la version invalide le cache** automatiquement.
- `content_hash` : SHA-256 du contenu d'entrée normalisé (faits produits, requêtes GSC pertinentes, hypothèses marchand validées). Le hash ignore le timestamp et l'ordre instable.

### TTL recommandés

| Type de tâche | TTL |
|---|---|
| Niche understanding (130) | 30 jours (re-générer si le catalogue change significativement) |
| Audit readiness (131) | 7 jours |
| Opportunity finder (132) | 7 jours |
| Priority engine (133) | 24 heures |
| Content actions meta/alt (134) | 90 jours (jusqu'à modification du produit) |
| FAQ / descriptions (134) | 30 jours |

### Stockage suggéré

Table Postgres `llm_cache` (à créer par la première tâche consommatrice qui en a besoin, pas dans cette tâche 129) :

```
llm_cache (
  shop TEXT,
  task_name TEXT,
  prompt_version TEXT,
  content_hash TEXT,
  response_json JSONB,
  tokens_in INT,
  tokens_out INT,
  created_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  PRIMARY KEY (shop, task_name, prompt_version, content_hash)
)
```

### Règle obligatoire

- **Aucun module consommateur ne fait un `router.complete()` sans vérifier le cache au préalable.**
- Le cache miss déclenche l'appel ; le résultat est inséré avec `expires_at = now + TTL`.

---

## 5. Quotas par plan

Valeurs de départ, à ajuster après pilotes :

| Plan | Tiers autorisés | Appels LLM / mois | Budget USD / mois | Comportement de dépassement |
|---|---|---|---|---|
| Free | `low-cost` uniquement | 200 | 0.50 | Blocage doux : message UI + désactivation génération |
| Pro | `low-cost`, `medium`, `advanced` (sur 130 et 133 seulement) | 5 000 | 15.00 | Dégradation low-cost only à 80 %, blocage doux à 100 % |
| Agency | Tous tiers, sans restriction de tâche | 25 000 | 75.00 | Alerte opérateur à 80 %, blocage doux à 100 % |

### Règles

- Le plan est lu depuis la table `subscriptions` (cf. `app/db.py:65`).
- Le compteur d'usage est dérivé de `get_shop_metrics(shop, days=30)` (`app/observability/metrics.py:47`).
- Le quota et le budget sont **deux limites indépendantes** ; la première atteinte déclenche le comportement de coupure.

---

## 6. Budget par shop

### Réutilisation existante

- Fonction : `check_budget(shop, budget_usd, days=30)` dans `app/observability/metrics.py:113`.
- Retourne `over_budget: bool` + alerte texte.

### Règle d'enforcement à implémenter

Tout module consommateur, **avant** chaque `router.complete()`, doit :

1. Lire le plan du shop.
2. Appeler `check_budget(shop, budget_usd=PLAN_LIMITS[plan]['budget'])`.
3. Si `over_budget == True` :
   - dégrader au tier `low-cost` si on était au-dessus ;
   - bloquer doux (lever `LLMQuotaExceeded`) si on était déjà au tier `low-cost`.
4. Sinon, procéder.

### Alertes

- 80 % du budget : entrée `llm_budget_warning` dans observability.
- 100 % : entrée `llm_budget_exceeded` + désactivation génération côté UI.

---

## 7. Mode `low-cost only`

### Toggle global (opérateur)

- Variable d'environnement : `LEONIE_LLM_LOW_COST_ONLY=true`.
- Effet : force tous les modules consommateurs à utiliser le tier `low-cost`, quel que soit leur tier déclaré.

### Toggle par shop (override)

- Colonne `subscriptions.llm_low_cost_only BOOLEAN DEFAULT FALSE` (à ajouter par la première tâche d'infra LLM, pas dans 129).
- Effet : même comportement que le toggle global, mais limité à un shop.

### Override opérateur ponctuel

- Un job opérateur peut forcer un appel `advanced` même en mode low-cost only, mais l'appel est logué avec un flag `override=true` pour audit.

---

## 8. Logs de coût

### Source de vérité existante

- `record_llm_call(shop, provider, model, tokens_in, tokens_out, latency_ms, error)` dans `app/observability/metrics.py:12`.
- Persiste dans la table `llm_metrics` (`app/db.py:89`).
- Coût calculé via `app/observability/costs.py:11` (pricing par modèle).
- Appelé automatiquement par `LLMRouter.complete()` (cf. `app/llm/router.py`).

### Règle

- **Aucun appel HTTP direct à un provider en dehors de `LLMRouter`.**
- Cela garantit que `record_llm_call` est toujours appelé et que le coût est tracé.

---

## 9. Fallback provider

### Logique existante

`LLMRouter.complete()` (`app/llm/router.py:70`) essaie chaque provider en séquence. Sur `LLMRateLimitError` ou `LLMUnavailableError`, passe au suivant. Sur `LLMError` non-retryable, lève immédiatement.

### Règle ajoutée

- Le fallback **n'escalade jamais vers un tier supérieur**.
- Un échec `advanced` retombe vers un autre provider du même tier, puis vers `medium`, puis vers `low-cost`.
- Un échec `low-cost` retombe uniquement vers un autre provider `low-cost`. Aucun fallback vers `medium`/`advanced` car cela violerait les quotas Free.

### Timeout

- 30 secondes par tentative provider, max 3 tentatives = 90 secondes total.
- Au-delà, lever `LLMUnavailableError` et laisser l'appelant gérer (job retry, dégradation UX, etc.).

---

## 10. Prompts

### Externalisation

- Tous les prompts sont dans `config/prompts/*.yaml`.
- Chaque prompt YAML a un champ obligatoire `version: <semver>` (cf. `app/llm/prompts.py:88`).

### Règles

- **Aucun prompt en dur dans le code applicatif.**
- **Bumper `version`** dans le YAML invalide automatiquement le cache (clé inclut `prompt_version` — section 4).
- Les prompts doivent être **courts, déterministes, et demander des sorties structurées JSON** quand le modèle le supporte (cf. section 11).
- Tout nouveau prompt (tâches 130-134) doit être ajouté dans `config/prompts/` avec `version: 0.1.0` au minimum.

---

## 11. Outputs JSON structurés

- **Recommandation forte** : chaque tier supporte un schéma de réponse JSON. À utiliser dès que la sortie est consommée par du code, pas par un humain directement.
- OpenAI : `response_format={"type": "json_object"}` quand disponible.
- Groq / Cloudflare : prompter avec exemples de schéma + parsing tolérant côté code (recoupement regex + json.loads avec fallback).
- Pour chaque tâche consommatrice, **documenter le schéma de réponse attendu dans le prompt YAML** (section `schema:`).

---

## 12. Checklist d'intégration consommateur

À cocher par chaque tâche consommatrice **avant** de mettre son module en production. Bloquant.

- [ ] Tier LLM déclaré explicitement (`low-cost`, `medium`, `advanced`).
- [ ] Prompt externalisé dans `config/prompts/<task>.yaml` avec `version` défini.
- [ ] Schéma de réponse JSON documenté dans le prompt YAML.
- [ ] Clé de cache `(shop, task_name, prompt_version, content_hash)` définie et appliquée.
- [ ] TTL de cache documenté (cf. section 4).
- [ ] `check_budget()` appelé avant `router.complete()`.
- [ ] Comportement de dépassement budget testé (dégradation puis blocage).
- [ ] Mode `low-cost only` respecté (test manuel ou unitaire).
- [ ] Aucun appel HTTP direct à un provider hors `LLMRouter`.
- [ ] Log de coût vérifié dans `llm_metrics` après appel test.
- [ ] Fallback testé sur au moins un échec provider simulé.

---

## 13. Garde-fous

- **Aucune analyse LLM massive sans action explicite ou job planifié.** Pas de polling automatique qui déclenche `advanced` sur tout le catalogue.
- **Aucun module consommateur ne bypass routing / cache / log de coût / budget.** Un PR qui ajoute un appel LLM hors `LLMRouter` doit être rejeté.
- **Cette stratégie ne réécrit pas la couche LLM existante.** Elle pose des règles que les tâches d'infra futures implémenteront incrémentalement.
- **Pas de fournisseur unique hardcodé.** OpenAI, Groq, Cloudflare et tout futur provider doivent rester interchangeables via `LLMRouter`.
- **La visibilité IA (ChatGPT, Perplexity, Gemini) n'est jamais présentée comme garantie.** L'usage LLM interne n'est pas non plus un argument marketing à survendre.

---

## Annexe — État d'avancement de la stratégie

| Décision | État | Référence |
|---|---|---|
| Tiers `low-cost` / `medium` / `advanced` | ✅ Documenté ici | Section 2 |
| Mapping consommateurs → tier | ✅ Documenté ici | Section 3 |
| Clé de cache + TTL | ✅ Documenté ici | Section 4 |
| Table `llm_cache` Postgres | ⏳ À implémenter (tâche consommatrice ou infra dédiée) | Section 4 |
| Quotas par plan | ✅ Documenté, valeurs ajustables | Section 5 |
| Enforcement quotas dans le code | ⏳ À implémenter | Sections 5-6 |
| Toggle `low-cost only` global | ⏳ Env var à ajouter | Section 7 |
| Toggle `low-cost only` par shop | ⏳ Colonne DB à ajouter | Section 7 |
| Logs de coût | ✅ Déjà en place | Section 8 (`app/observability/metrics.py:12`) |
| Fallback provider | ✅ Déjà en place + règle ajoutée | Section 9 (`app/llm/router.py:70`) |
| Prompts YAML + versioning | ✅ Déjà en place | Section 10 (`config/prompts/`, `app/llm/prompts.py`) |
| Outputs JSON structurés | ⏳ À ajouter prompt par prompt | Section 11 |
| Checklist intégration | ✅ Documentée ici | Section 12 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 129. Ils seront pris en charge par les tâches consommatrices 130-134 ou par une tâche d'infra dédiée ultérieure.
