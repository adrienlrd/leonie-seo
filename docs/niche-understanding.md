# Merchant Niche Understanding Layer — Léonie SEO

> Référence canonique de la couche de compréhension de la boutique par LLM. Définit comment Léonie SEO transforme les signaux Shopify, GSC, GA4 et catalogue en hypothèses marketing validées par le marchand, qui alimentent ensuite les modules 131-134.
>
> Statut : décisions produit/architecture figées au 2026-05-19 (tâche 130, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

Aujourd'hui, les prompts existants (`config/prompts/product_description.yaml`, `collection_brief.yaml`, `blog_brief.yaml`) ont un contexte de niche **hardcodé** ("accessoires premium pour animaux"). Si l'app est installée sur une boutique cosmétique, déco, jardinage, sport, les sorties LLM seront génériques ou erronées.

L'infrastructure niche existante (`app/niche/engine.py`, `app/niche/signals/*`, `app/niche/intent.py`, `app/niche/ner.py`, `app/embeddings/store.py`) extrait des signaux solides mais ne produit **aucune synthèse marketing** : pas de personas, pas de motivations d'achat, pas d'angles, pas de promesses interdites, pas de niveau de confiance par hypothèse.

La tâche 130 cadre la **couche de synthèse LLM** qui transforme ces signaux en hypothèses marchand, et le **workflow de correction** par lequel le marchand valide ou ajuste avant que toute génération aval ne démarre.

C'est **le premier vrai consommateur de la stratégie LLM** (`docs/llm-strategy.md`) — tier `advanced`, mis en cache long TTL.

---

## 2. Position dans le workflow GEO Autopilot

```
Connecter → [Comprendre] → Proposer → Valider → Appliquer → Mesurer
              ↑↑↑
              tâche 130
```

- Le marchand connecte sa boutique (Shopify OAuth, GSC, optionnel GA4).
- Léonie SEO synthétise les signaux en hypothèses.
- Le marchand voit "Voici ce que l'IA a compris de votre boutique" et corrige.
- Les hypothèses validées sont persistées dans `shop_config`.
- **Aucun module aval (131 audit, 132 opportunités, 133 priorisation, 134 contenu)** ne tourne sans hypothèses marchand validées.

---

## 3. Inputs LLM (sources à fusionner)

| Source | Fichier | Contribution |
|---|---|---|
| Snapshot Shopify produits Active | `scripts/audit/crawl_shopify.py:24`, `app/api/snapshot_store.py:12` | Titres, descriptions, tags, types, prix, collections |
| Clusters produits | `app/niche/clustering.py`, `engine.py` | Regroupement TF-IDF déjà calculé |
| NER entités | `app/niche/ner.py` | Materials, certifications, origins, targets |
| Intent clusters GSC | `app/niche/intent.py` | Intentions conversationnelles déjà classifiées |
| Keyword gaps | `app/niche/gaps.py` | Requêtes manquantes vs catalogue |
| Signaux externes | `app/niche/signals/aggregator.py:14` | Google Suggest, pytrends, Reddit |
| GSC top queries | endpoint GSC existant | Volume réel d'intérêt |
| GA4 sessions / conversions (si dispo) | `app/api/ga4.py` | Produits qui convertissent vs ceux qui attirent |
| Embeddings produits/requêtes | `app/embeddings/store.py` | Similarité multilingue |

**Pré-traitement obligatoire avant LLM** : tous les signaux ci-dessus passent par les modules Python existants. Le LLM ne reçoit **jamais le snapshot brut** mais une synthèse pré-calculée (clusters + top entities + top intents + top queries + KPIs agrégés). Cela réduit la taille du prompt et le coût.

---

## 4. Tier LLM et règle d'appel

Réutilise la stratégie figée dans `docs/llm-strategy.md` :

- **Tier** : `advanced` (justifié par : volume contexte multi-signaux + valeur business haute + ambiguïté de synthèse multi-niveaux).
- **Fréquence** : **1 appel par shop**, mis en cache **30 jours**. Re-déclenchement automatique si :
  - le snapshot Shopify évolue de > 20 % (ajouts/suppressions de produits) ;
  - GSC reçoit > 10 nouvelles top queries d'intérêt depuis le dernier appel ;
  - le marchand demande explicitement "Re-analyser ma boutique".
- **Clé cache** : `(shop, "niche_understanding", prompt_version, content_hash)` où `content_hash` = SHA-256 du payload pré-traité.
- **Plan Free** : ne lance pas `advanced`, dégrade vers `medium`. Le marchand Free voit une version simplifiée des hypothèses, sans personas détaillés.

---

## 5. Schéma de sortie attendu (output JSON contractuel)

Le prompt YAML `config/prompts/niche_understanding.yaml` (à créer par la tâche d'implémentation) doit imposer ce schéma :

```json
{
  "shop_summary": {
    "what_you_sell": "string court (1 phrase)",
    "primary_niche": "string",
    "sub_niches": ["string"],
    "languages_detected": ["fr", "en"],
    "markets_detected": ["FR", "BE", "CH"]
  },
  "customer_segments": [
    {
      "id": "string",
      "label": "string",
      "description": "string",
      "size_estimate": "small|medium|large",
      "confidence": "low|medium|high"
    }
  ],
  "buying_motivations": [
    {
      "segment_id": "string",
      "motivation": "string",
      "evidence": ["from_product_title|from_gsc_query|from_review|inferred"],
      "confidence": "low|medium|high"
    }
  ],
  "objections": [
    {"objection": "string", "confidence": "low|medium|high"}
  ],
  "priority_products": [
    {"product_id": "string", "reason": "string", "confidence": "low|medium|high"}
  ],
  "marketing_angles": [
    {"angle": "string", "for_segment_id": "string", "confidence": "low|medium|high"}
  ],
  "conversational_intents": [
    {"intent": "string", "example_queries": ["string"], "confidence": "low|medium|high"}
  ],
  "probable_competitors": [
    {"name": "string", "domain": "string|null", "confidence": "low|medium|high"}
  ],
  "brand_voice": {
    "tone": "string court",
    "register": "casual|professional|technical|playful",
    "do_say": ["string"],
    "do_not_say": ["string"],
    "confidence": "low|medium|high"
  },
  "forbidden_promises": [
    {"promise": "string", "reason": "regulatory|unverifiable|brand_safety"}
  ],
  "global_confidence": "low|medium|high",
  "missing_inputs": ["string"]
}
```

### Règles sur le schéma

- **Chaque hypothèse porte sa propre confiance.** Pas de score global opaque.
- **`evidence`** est obligatoire pour `buying_motivations` : le marchand voit pourquoi l'IA propose cette hypothèse.
- **`forbidden_promises`** capture les promesses que le marchand doit éviter (claims santé, garanties non documentées, comparaisons). Une promesse interdite empêche tout module aval de la générer.
- **`missing_inputs`** liste explicitement ce qui manquait à l'IA (pas de GA4, peu de reviews, etc.). Sert à demander au marchand d'enrichir.

---

## 6. Workflow de correction marchand

### Écran "Voici ce que l'IA a compris de votre boutique"

Affiche le payload retourné, regroupé en sections claires :

- **Votre boutique** : `shop_summary`.
- **Vos clients types** : `customer_segments` + `buying_motivations`.
- **Vos arguments marketing** : `marketing_angles`, `brand_voice`.
- **À éviter** : `objections`, `forbidden_promises`.
- **Concurrents possibles** : `probable_competitors`.
- **Produits prioritaires** : `priority_products`.

Chaque section est **éditable** : champ texte libre, ajout/suppression d'élément, ajustement du niveau de confiance.

### Persistance

Le payload corrigé est stocké dans `shop_config` (table existante `app/shop_config_store.py:1`) sous la clé `niche_hypothesis`. Format :

```
shop_config (
  shop TEXT,
  key TEXT,        # "niche_hypothesis"
  value JSONB,     # schéma section 5, version + corrected_at
)
```

### Versioning

Chaque correction écrase la version précédente mais conserve l'historique dans une seconde clé `niche_hypothesis_history` (liste des N=5 dernières versions). Permet rollback et audit.

### Confirmation obligatoire avant aval

Tant que `shop_config.niche_hypothesis.status != "validated_by_merchant"`, **les modules 131-134 n'utilisent pas les hypothèses** : ils tombent sur leurs heuristiques actuelles (catalog + GSC bruts). Pas de génération aval avec hypothèses non validées.

---

## 7. Propagation vers les modules aval

| Module | Champs niche injectés dans le prompt / la logique |
|---|---|
| 131 Unified AI Search Readiness Audit | `forbidden_promises` (pénaliser), `brand_voice.do_not_say` (signaler), `conversational_intents` (couverture FAQ) |
| 132 Unified Opportunity Finder | `conversational_intents`, `customer_segments`, `priority_products` (filtre de relevance) |
| 133 Unified Priority Engine | `priority_products`, `customer_segments` (poids), `forbidden_promises` (exclure les recommandations à risque) |
| 134 AI Content Actions | `brand_voice`, `marketing_angles`, `customer_segments`, `buying_motivations`, `forbidden_promises`, `do_not_say` — **injection dans tous les prompts** |

### Mise à jour des prompts existants

Les prompts `product_description.yaml`, `collection_brief.yaml`, `blog_brief.yaml`, `meta_title.yaml`, `meta_description.yaml` doivent recevoir un contexte niche dynamique au lieu du contexte hardcodé "accessoires premium animaux". À porter par la tâche 134 (AI Content Actions Simplification), pas dans 130.

---

## 8. Garde-fous

- **L'IA ne pose que des hypothèses, jamais des faits.** Aucune affirmation sur matière, origine, certification, garantie, propriété médicale n'est produite ici. Ces faits restent du périmètre du Product Facts Layer (tâche 106).
- **Confidence obligatoire par hypothèse.** Une hypothèse `low` doit être affichée différemment d'une `high` dans l'UI marchand.
- **Pas de génération aval sans validation marchand.** Tant que `status != "validated_by_merchant"`, les modules 131-134 utilisent leurs heuristiques par défaut.
- **Re-déclenchement contrôlé.** Pas de re-synthèse automatique non plafonnée : seuil > 20 % changement catalogue, > 10 nouvelles top queries, ou demande explicite marchand.
- **Plan Free dégradé.** Pas de `advanced` sur Free. Synthèse simplifiée `medium` avec moins de personas et pas de `probable_competitors`.
- **Cache invalidation explicite.** Bumper la version du prompt YAML invalide le cache automatiquement (cf. `docs/llm-strategy.md` section 4).
- **Pas de fuite de signaux concurrents en dehors du shop.** Les hypothèses sont par shop ; on ne réutilise pas la synthèse d'un shop pour un autre.
- **Pas d'écriture Shopify dans cette couche.** Aucune modification de produit, collection ou metafield. La couche est purement analytique + persistée dans `shop_config`.

---

## 9. Mapping fichiers

### Existant à réutiliser

| Fichier | Rôle dans la tâche 130 |
|---|---|
| `app/niche/engine.py` | Source de clusters + intents + gaps (pré-traitement avant LLM) |
| `app/niche/signals/aggregator.py:14` | Signaux externes (Suggest, trends, Reddit) |
| `app/niche/ner.py` | Entités catalogue (alimente `evidence`) |
| `app/embeddings/store.py` | Embeddings produits/requêtes pour similarité multilingue |
| `app/shop_config_store.py:1` | Persistance des hypothèses validées (`niche_hypothesis`) |
| `app/llm/router.py:70` | Appel LLM tier `advanced` |
| `app/observability/metrics.py:12` | Log coût + budget check |

### À créer par la tâche d'implémentation (post-130)

| Fichier | Rôle |
|---|---|
| `app/niche/understanding.py` | Orchestrateur : assemble signaux, appelle LLM, valide schéma JSON, persiste |
| `config/prompts/niche_understanding.yaml` | Prompt versionné + schéma de sortie |
| `app/api/niche.py` (étendre) | `POST /api/shops/{shop}/niche/understand`, `GET/PATCH /api/shops/{shop}/niche/hypothesis` |
| `shopify-app/app/routes/app.niche-understanding.tsx` | UI "Voici ce que l'IA a compris" + formulaire de correction |
| Migration `shop_config` | Clés `niche_hypothesis` et `niche_hypothesis_history` documentées |

### À mettre à jour (post-130, par les tâches consommatrices)

| Fichier | Évolution |
|---|---|
| `config/prompts/product_description.yaml:5` | Remplacer le contexte hardcodé par injection dynamique de `brand_voice`, `marketing_angles`, `forbidden_promises` |
| `config/prompts/collection_brief.yaml` | Idem |
| `config/prompts/blog_brief.yaml` | Idem |
| `config/prompts/meta_title.yaml`, `meta_description.yaml` | Idem (à confirmer) |
| `shopify-app/app/routes/app.niche.tsx:1` | Lien vers `app.niche-understanding.tsx`, statut "hypothèses validées par le marchand" |

---

## 10. Critères d'acceptation de l'implémentation future

À cocher quand une tâche concrétise la couche niche :

- [ ] Le marchand voit "Voici ce que l'IA a compris de votre boutique" après la 1re connexion Shopify + import GSC.
- [ ] Le payload retourné suit le schéma JSON section 5.
- [ ] Chaque hypothèse porte un niveau de confiance.
- [ ] Le formulaire de correction est éditable section par section.
- [ ] Le payload corrigé est persisté dans `shop_config.niche_hypothesis`.
- [ ] L'historique des N=5 dernières versions est consultable.
- [ ] Tant que `status != "validated_by_merchant"`, aucun module aval (131-134) n'utilise les hypothèses.
- [ ] Le LLM est appelé en tier `advanced` (sauf plan Free → `medium`).
- [ ] Le résultat est mis en cache 30 jours, ré-invalidable sur les 3 critères (≥20 % catalogue, ≥10 nouvelles queries, demande marchand).
- [ ] `check_budget()` est appelé avant `router.complete()` (cf. `docs/llm-strategy.md` §6).
- [ ] `forbidden_promises` est propagé jusqu'aux prompts de génération aval.
- [ ] La checklist d'intégration consommateur (`docs/llm-strategy.md` §12) est cochée.

---

## 11. Limitations V1 explicites

- **Pas de scraping d'avis tiers.** Seuls les avis Shopify (metafield ou app reviews intégrée) sont utilisés. Pas de Trustpilot, Google Reviews, etc. dans V1.
- **Pas de détection de marque visuelle.** Pas d'analyse des images produit (logo, couleurs, style) en V1. Reposera sur les titres / descriptions / tags.
- **Pas de personas auto-générés au-delà de 4.** Trop de personas dilue les angles. Limite stricte 4 segments en V1.
- **Pas de localisation par marché < shop level.** Une seule hypothèse niche par shop, pas une hypothèse par marché Shopify Markets en V1.
- **Pas de détection automatique de concurrents par scraping.** `probable_competitors` est inféré du contenu + signaux externes (Suggest, Reddit), pas d'un crawl concurrent. Le marchand peut compléter manuellement.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Position dans le workflow GEO Autopilot | ✅ Documentée | Section 2 |
| Inputs LLM (fusion de signaux) | ✅ Documentée | Section 3 |
| Tier LLM + cache + ré-invalidation | ✅ Spécifié | Section 4 |
| Schéma JSON de sortie | ✅ Spécifié | Section 5 |
| Workflow de correction marchand | ✅ Spécifié | Section 6 |
| Propagation vers modules aval | ✅ Mappé | Section 7 |
| Garde-fous (confidence, validation obligatoire, pas de faits inventés) | ✅ Documentés | Section 8 |
| Mapping fichiers existants à réutiliser | ✅ Documenté | Section 9 |
| `app/niche/understanding.py` | ⏳ À créer | Section 9 |
| `config/prompts/niche_understanding.yaml` | ⏳ À créer | Section 9 |
| `app/api/niche.py` route `understand` / `hypothesis` | ⏳ À étendre | Section 9 |
| UI Remix `app.niche-understanding.tsx` | ⏳ À créer | Section 9 |
| Mise à jour des prompts existants pour consommer `brand_voice` etc. | ⏳ Par tâche 134 | Section 7 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 130. Ils seront pris en charge par la tâche d'implémentation Niche Understanding ultérieure et par la tâche 134 (Content Actions).
