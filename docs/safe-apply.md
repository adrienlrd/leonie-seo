# Human Review & Safe Apply Workflow — Giulio Geo

> Référence canonique du workflow de revue humaine et d'application Shopify. Étend le workflow meta existant à **tous les `content_type`** de la tâche 134 et verrouille les garde-fous d'écriture pour la V1 publique.
>
> Statut : décisions produit/architecture figées au 2026-05-20 (tâche 135, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

L'infrastructure de review/apply existe et est solide, mais elle est **partielle** :

| Brique | Fichier | Couvre |
|---|---|---|
| Review diff meta | `app/api/generate.py:167`, `app.review.tsx` | Meta titles + descriptions uniquement |
| Apply Shopify safe | `app/apply/shopify_writer.py:16`, `app/apply/bulk_orchestrator.py:84` | Meta + alt text + description HTML + redirects |
| Pilot-safe gate | `app/safety.py:14` (`is_pilot_safe_mode`) | ✅ global |
| Rollback per-item | `app/api/rollback.py:59`, table `seo_changes` (`app/db.py:39`) | Meta uniquement |
| Event tracking | `app/geo/ledger.py:48` (table `geo_impact_events` `app/db.py:144`) | ✅ structure prête, peu utilisée |
| UI review | `app.review.tsx`, `app.descriptions.tsx` | 2 pages séparées |

Problèmes pour la V1 publique :

- **Aucun workflow review pour** FAQ, Answer Blocks, buying guides, JSON-LD FAQPage, collection descriptions, multilingual.
- **Rollback ne couvre pas** ces nouveaux content types.
- **Diff format hétérogène** entre meta et descriptions.
- **Event tracking n'est pas branché** systématiquement sur les apply.
- **2 pages UI séparées** → marchand confus.

La tâche 135 fixe le workflow unifié qui consomme la sortie de la tâche 134 (schéma JSON unique §6 de `docs/ai-content-actions.md`), gère review + dry-run + apply + rollback + event tracking pour **tous les `content_type`**, sans réécrire les briques de sécurité existantes.

---

## 2. Workflow en 7 étapes

```
1. Receive draft       ← sortie de 134 (action_id + content_type + output + facts_used + claims_unverified)
2. Generate diff       ← preview avec ancien/nouveau, faits utilisés, alertes
3. Human decision      ← accept / edit / reject / retry (cf. 134 retravail × 3)
4. Dry-run             ← simulation Shopify SANS écriture, contrôles serveur-side
5. Live apply          ← écriture Shopify avec confirm_live_write=true, rate-limit, capture rollback
6. Event tracking      ← snapshot avant/après dans geo_impact_events
7. Post-apply          ← statut applied, lien vers Impact Tracker (136), rollback disponible
```

Chaque étape est **bloquante** : on ne passe à la suivante qu'avec une confirmation explicite (utilisateur ou validation auto). Aucune étape ne peut être contournée par un appel API direct — les gates `app/safety.py:19` s'appliquent partout.

---

## 3. Étape 2 — Diff & preview unifié

Pour chaque `content_type` (cf. `docs/ai-content-actions.md` §3), le workflow produit un objet `Diff` au schéma commun :

```json
{
  "action_id": "string",
  "content_type": "meta_title|meta_description|product_description|...",
  "resource": {
    "type": "product|collection|article",
    "id": "string",
    "handle": "string",
    "title": "string"
  },

  "before": {
    "primary_text": "string|null",
    "structured": "object|null",
    "captured_at": "ISO date"
  },
  "after": {
    "primary_text": "string",
    "structured": "object|null"
  },

  "facts_used": [
    {"key": "string", "value": "string", "source": "shopify|merchant", "highlighted": true|false}
  ],
  "claims_unverified": [
    {"claim": "string", "category": "factual|opinion|hypothesis", "severity": "info|warning"}
  ],

  "constraints_check": {
    "length_ok": true|false,
    "language_ok": true|false,
    "forbidden_promise_violations": ["string"],
    "do_not_say_violations": ["string"]
  },
  "quality": {"score": 0-100, "label": "string"},

  "merchant_view": {
    "summary_fr": "string court non-technique",
    "summary_en": "string",
    "why_this_change": "string",
    "expected_impact": "string"
  },

  "decision_state": {
    "status": "draft|needs_review|approved|rejected|exported|applied|reverted",
    "blocked_reasons": ["string"],
    "next_actions": ["accept|edit|reject|retry"]
  }
}
```

### Règles sur le diff

- **`before`** est obligatoire pour les content_types qui remplacent un existant (`meta_title`, `meta_description`, `product_description`, `alt_text`). Pour les `faq_block`, `buying_guide`, `jsonld_faqpage`, `before` peut être `null` (création).
- **`facts_used` avec `highlighted: true`** indique au marchand quels faits ont directement nourri ce contenu — UI peut surligner.
- **`claims_unverified.severity = warning`** sur une affirmation factuelle non sourcée → impossible à `approved` sans édition marchand.
- **`merchant_view.summary_fr`** est obligatoire : *« Cette page reçoit déjà des impressions Google mais la description ne mentionne pas la matière principale. Ce changement ajoute la matière confirmée. »* Pas de jargon SEO.
- **`decision_state.blocked_reasons`** liste explicitement pourquoi `accept` est bloqué (ex : `forbidden_promise_violation`, `length_too_short`).
- **`next_actions`** dynamique : si `claims_unverified.warning ≠ ∅`, `accept` est retiré tant que le marchand n'a pas édité.

---

## 4. Étape 3 — Décision humaine

Quatre actions possibles, exposées en boutons clairs côté UI :

| Action | Effet API | Garde-fou |
|---|---|---|
| **Accept** | `decision_state.status = approved` | Bloqué si `decision_state.blocked_reasons ≠ ∅` |
| **Edit** | Ouvre éditeur in-line, recalcule `constraints_check` à chaque keystroke (debounce 500 ms), passe `decision_state.status = approved` au save | Édition tracée, source = `merchant_edit` dans event log |
| **Reject** | `status = rejected`, raison libre stockée | Aucun |
| **Retry** | Renvoie au workflow 134 avec `feedback` (compteur ≤ 3, cf. `docs/ai-content-actions.md` §11) | Bloqué au 4ᵉ retry → "Veuillez éditer manuellement" |

### Granularité

- **Par item** : décision unitaire par `action_id`.
- **Par batch** : Accept all / Reject all sur une sélection — uniquement si tous les items sélectionnés ont `decision_state.blocked_reasons = ∅`.
- **Auto-approve supprimé** (cf. `docs/ai-content-actions.md` §13). La règle `human_review_required: true` est stricte.

### Traçabilité

Chaque décision est loguée :

```
content_action_decisions (
  shop, action_id, content_type, decision, decided_by, decided_at,
  before_hash, after_hash, edit_diff (si edit), rejected_reason (si reject),
  retry_index (si retry)
)
```

Table à créer par l'implémentation 135 — pas dans cette tâche de cadrage.

---

## 5. Étape 4 — Dry-run obligatoire avant live

Tout `approved` passe **systématiquement** par un dry-run avant l'option live.

### Comportement dry-run

- Appelle le writer Shopify (`app/apply/shopify_writer.py:16`) avec `dry_run=True` (déjà en place).
- Capture la requête GraphQL qui serait envoyée + le contenu attendu après application.
- Lit l'état actuel Shopify (re-fetch) pour comparer avec `before` capturé en étape 2 → détecte les changements latents (ex : un autre admin a modifié le produit entre temps).
- Bloque si `before_drift_detected = true` → propose au marchand de re-générer le diff ou de forcer l'écrasement.

### Réponse dry-run

```json
{
  "action_id": "string",
  "content_type": "string",
  "dry_run": true,
  "would_succeed": true|false,
  "would_change_fields": ["seo.title", "seo.description", "..."],
  "before_drift_detected": true|false,
  "shopify_request_preview": {...},
  "errors": []
}
```

Dry-run échoué → blocage live impossible.

---

## 6. Étape 5 — Live apply

### Gates de sécurité (déjà en place, à respecter strictement)

1. **`is_pilot_safe_mode()`** (`app/safety.py:14`) — Si `LEONIE_PILOT_SAFE_MODE=true`, bloque toute écriture live, autorise dry-run uniquement. **Inchangé**.
2. **`require_shopify_write_allowed(action, dry_run, confirmed)`** (`app/safety.py:19`) — Bloque si `dry_run=False` et `confirmed=False`. **Réutilisé tel quel pour tous content_types**.
3. **`confirm_live_write=true`** doit venir d'une **action UI explicite** (bouton "Confirmer l'écriture"), jamais d'un défaut côté code.
4. **Plan check** : certaines actions sont réservées Pro/Agency (cf. `app/api/plans.py:10` `can_apply`). Free voit l'option dry-run + export uniquement.
5. **Budget LLM check** ne s'applique PAS au live apply (pas d'appel LLM ici).

### Rate-limit

Réutilise `app/apply/bulk_orchestrator.py:84` :

- `max_per_run=50` par défaut, max 100 (paramétrable Agency).
- `delay=0.5s` entre mutations.
- Retry automatique sur `THROTTLED` Shopify avec backoff exponentiel.
- Aucun parallélisme par shop (`max_concurrent_per_shop=1`).

### Capture rollback

Pour **chaque content_type**, le writer doit lire la valeur actuelle Shopify **avant** la mutation et insérer dans `seo_changes` :

```
seo_changes (
  shop, applied_at, job_id, resource_type, resource_id,
  field,            # "seo.title", "alt_text", "faq_metafield", ...
  old_value, new_value,
  status            # applied|reverted
)
```

Cette table existe déjà (`app/db.py:39`) — à étendre pour couvrir les nouveaux content_types (FAQ metafields, JSON-LD theme blocks, descriptions HTML longues).

---

## 7. Étape 6 — Event tracking

Réutilise `app/geo/ledger.py:48` (`create_geo_event`) — déjà en place. Chaque apply réussi insère un événement `geo_impact_events` avec :

| Champ | Source |
|---|---|
| `score_before` | Score `AI Search Readiness` (131) lu avant apply |
| `score_after` | Recalculé après apply (job async, ≤ 5 min) |
| `before_snapshot` | Shopify snapshot pertinent au moment de l'apply |
| `after_snapshot` | Re-fetch après mutation |
| `metrics_before` | GSC + GA4 récents (28 derniers jours) |
| `metrics_after` | Capturé à J+7, J+30, J+60, J+90 par Impact Tracker (136) |
| `status_history` | Liste `[{status, changed_at, note}]` |
| `job_id` | ID du job `bulk_apply` qui a exécuté |
| `action_id` | ID du content action (lien avec 134) |
| `content_type` | meta_title / faq_block / ... |
| `decision_meta` | Décision humaine : accepted / edited (+ diff édit) |

**Couplage strict avec 136** : sans event, pas de mesure. Sans mesure, on ne propose pas la même action ailleurs.

---

## 8. Étape 7 — Post-apply

Une fois la mutation Shopify réussie :

1. Statut `applied` côté `content_action_decisions`.
2. Statut `applied` côté `content_actions` (sortie 134).
3. Événement créé dans `geo_impact_events` (cf. §7).
4. Notification UI marchand : *« Modification appliquée. Premier signal de mesure attendu sous 7 jours. »*
5. Action visible dans `app.impact-report` (déjà existant, à étendre).
6. Bouton **Revert** disponible 90 jours après apply (TTL aligné sur fenêtre de mesure).

### Rollback

Endpoint déjà en place : `POST /shops/{shop}/rollback/{change_id}/revert` (`app/api/rollback.py:59`).

À étendre pour les nouveaux content_types :

- `meta_title`, `meta_description` : ✅ déjà couvert.
- `product_description` : ⏳ à ajouter (mutation `productUpdate.descriptionHtml`).
- `alt_text` : ⏳ à ajouter (mutation `productImageUpdate`).
- `faq_block`, `answer_block`, `buying_guide` : ⏳ via metafields ou Theme App Extension.
- `jsonld_faqpage` : ⏳ via Theme App Extension.
- `collection_description` : ⏳ via `collectionUpdate`.
- `meta_multilingual` : ⏳ via metafields locale-aware.

Le rollback est **per-item** par défaut. Rollback batch possible mais demande confirmation forte (`confirm_live_write=true` + bouton "Confirmer la révocation de N changements").

### Soft-delete vs hard-delete

- `revert` ne supprime jamais le `seo_changes`, il marque `status=reverted` et applique une nouvelle mutation Shopify avec l'ancienne valeur.
- Garde un historique complet apply/revert/re-apply.

---

## 9. Comportement UI cible

### Page principale `app.safe-apply.tsx` (à créer, remplace `app.review` et `app.descriptions`)

Vue unique avec :

- **Tabs Polaris** par `content_type` (Meta, Descriptions, FAQ, Guides, JSON-LD, Alt text, Multilingue).
- Pour chaque tab : liste des `action_id` en `draft` / `needs_review` / `approved`.
- Détail (drawer ou page) : diff complet §3 + 4 boutons (Accept / Edit / Reject / Retry).
- Bouton global "Dry-run la sélection" / "Appliquer la sélection" (live) — toujours dans cet ordre.

### Drill-downs conservés

- `app.rollback-history.tsx` (à créer ou unifier) : historique complet avec filtres par content_type + bouton revert per-item.
- `app.impact-report.tsx` (existant) : suivi post-apply, événements geo.

### Pages dépréciées

- `app.review.tsx` : migré vers `app.safe-apply.tsx`, alias pendant 1 release.
- `app.descriptions.tsx` : idem.
- `app.geo-faq-content.tsx` : conservé en drill-down lecture seule pour les contenus déjà appliqués, plus en entrée principale.

---

## 10. Plan-based behavior

| Plan | Accept | Edit | Retry × 3 | Dry-run | Live apply | Rollback |
|---|---|---|---|---|---|---|
| Free | ✅ | ✅ | ⚠ retry 1 max | ✅ | ❌ (export only) | ✅ sur changes existants |
| Pro | ✅ | ✅ | ✅ × 3 | ✅ | ✅ (max 50/run) | ✅ |
| Agency | ✅ | ✅ | ✅ × 3 | ✅ | ✅ (max 100/run) | ✅ |

Cohérent avec `app/api/plans.py:10` `can_apply` (Pro/Agency). Free voit le bouton "Exporter" à la place de "Live apply".

---

## 11. Garde-fous transversaux

- **`human_review_required: true` est strict.** Aucun by-pass possible côté code (les anciennes routes auto-approve sont supprimées).
- **`is_pilot_safe_mode()` bloque tout live.** Inchangé.
- **Dry-run obligatoire avant live**, jamais "live direct".
- **`before_drift_detected`** force re-génération si l'état Shopify a changé entre étape 2 et étape 4.
- **Rate-limit per shop** : max 1 job `bulk_apply` actif à la fois.
- **Logs structurés** : `job_id + shop + content_type + action_id` (déjà supporté par `app/jobs/worker.py:97`).
- **Plan-based gates** : Free ne peut pas live-apply, mais peut exporter le contenu (CSV/Markdown) pour copier-coller manuel.
- **Idempotence** : appliquer 2 fois la même action sur le même resource avec le même `content_hash` est un no-op silencieux côté writer.
- **Budget LLM non concerné** : étape 5 ne consomme pas de LLM. Seules les étapes 1-2 (genèse 134) et 3 retry (re-génération) consomment.
- **Pas de mass-apply sans review.** Bulk apply existe mais chaque item passe par accept individuel ou batch accept explicite (`decision_state.status = approved` requis).
- **Multi-tenant strict** : chaque écriture porte le `shop`, aucune fuite cross-shop.
- **Aucune mutation Shopify hors `LeonieSEO` user-agent** : déjà imposé par `app/apply/shopify_writer.py`.

---

## 12. Mapping fichiers

### Existant à réutiliser

| Fichier | Rôle dans 135 |
|---|---|
| `app/safety.py:14` (`is_pilot_safe_mode`) | Gate global pilot-safe |
| `app/safety.py:19` (`require_shopify_write_allowed`) | Gate live write |
| `app/apply/shopify_writer.py:16` | Writer multi-mutation Shopify |
| `app/apply/bulk_orchestrator.py:84` | Orchestrateur rate-limit + dry-run par défaut |
| `app/api/rollback.py:59` | Endpoints rollback per-item |
| `app/db.py:39` (`seo_changes`) | Table de tracking pour rollback |
| `app/geo/ledger.py:48` (`create_geo_event`) | Event tracking |
| `app/db.py:144` (`geo_impact_events`) | Table d'événements |
| `app/jobs/worker.py:97` | Logs structurés |
| `app/api/plans.py:10` (`can_apply`) | Gate par plan |

### À créer par la tâche d'implémentation (post-135)

| Fichier | Rôle |
|---|---|
| `app/safe_apply/diff.py` | Construction du diff schéma §3 pour tous content_types |
| `app/safe_apply/decisions.py` | Persistance des décisions humaines + édits |
| `app/safe_apply/writer_adapters.py` | Adapters par content_type vers `shopify_writer.py` (FAQ metafield, JSON-LD theme block, etc.) |
| `app/safe_apply/rollback_adapters.py` | Étend `app/api/rollback.py` aux nouveaux content_types |
| `app/api/safe_apply.py` | Routes `POST /safe-apply/diff`, `/decision`, `/dry-run`, `/live`, `/revert` |
| `shopify-app/app/routes/app.safe-apply.tsx` | UI unifiée |
| `shopify-app/app/routes/app.rollback-history.tsx` | UI historique enrichie |
| Migration DB : table `content_action_decisions` | Traçabilité §4 |

### À mettre à jour

| Fichier | Évolution |
|---|---|
| `app/api/generate.py:167` (`/generate/meta/diff`) | Alias deprecated vers `/safe-apply/diff?type=meta_*` |
| `app/api/generate.py:190` (`/generate/meta/review`) | Alias deprecated vers `/safe-apply/decision` |
| `app/api/generate.py:214` (`auto-approve`) | **Supprimé** (incompatible 134/135) |
| `app/jobs/handlers.py:66` (handler `meta_generation`) | Redirigé vers orchestrateur 134 + 135 |
| `app/apply/shopify_writer.py:16` | Ajout mutations FAQ metafield, JSON-LD theme block, descriptions HTML longues |
| `shopify-app/app/routes/app.review.tsx`, `app.descriptions.tsx` | Migrés vers `app.safe-apply.tsx` |

---

## 13. Endpoints — stratégie

| Endpoint actuel | Statut post-135 |
|---|---|
| `GET /generate/meta/diff` | Alias deprecated vers `GET /safe-apply/diff?content_type=meta_*` |
| `POST /generate/meta/review` | Alias deprecated vers `POST /safe-apply/decision` |
| `POST /generate/meta/auto-approve` | **Supprimé** |
| `POST /generate/meta/apply` | Conservé tel quel (déjà aligné) |
| `GET /shops/{shop}/rollback/history` | Conservé, étendu pour nouveaux content_types |
| `POST /shops/{shop}/rollback/{change_id}/revert` | Conservé, étendu |
| **`GET /safe-apply/diff?action_id=...`** | **À créer** — canonique |
| **`POST /safe-apply/decision`** | **À créer** — accept/edit/reject/retry |
| **`POST /safe-apply/dry-run`** | **À créer** — étape 4 obligatoire |
| **`POST /safe-apply/live`** | **À créer** — étape 5 (gates) |
| **`POST /safe-apply/revert`** | **À créer** — par item ou batch |
| **`GET /safe-apply/history?shop=...`** | **À créer** — unifie meta+autres |

---

## 14. Cohérence avec les autres modules Phase 11.7

- **127 Product Scope** : refuse l'apply sur produits non `ACTIVE Online Store` (sauf Pre-launch override explicite).
- **129 LLM Strategy** : pas d'impact direct sur 135 — le LLM n'intervient pas dans review/apply.
- **130 Niche Understanding** : `forbidden_promises` et `do_not_say` propagés depuis 134 → bloquent l'accept tant que non corrigés.
- **131 Readiness Audit** : score `before` capturé à l'étape 6, score `after` recalculé J+7.
- **132 Opportunity Finder** : le `success_metric` issu de 132/133 alimente `metrics_before` / `metrics_after`.
- **133 Priority Engine** : déclencheur, chaque action venue de 133 a son `success_metric` strict — sans elle, 135 refuse l'apply.
- **134 Content Actions** : producteur du draft. Sortie `output` + `facts_used` + `claims_unverified` consommée intégralement par 135.
- **136 Impact Tracker** : consomme `geo_impact_events` créés à l'étape 6, calcule l'impact dans le temps.

---

## 15. Critères d'acceptation de l'implémentation future

À cocher quand une tâche concrétise Safe Apply unifié :

- [ ] Un seul endpoint `GET /safe-apply/diff` couvre les 10 content_types.
- [ ] Schéma `Diff` §3 retourné systématiquement, avec `merchant_view.summary_fr` obligatoire.
- [ ] Accept bloqué si `decision_state.blocked_reasons ≠ ∅`.
- [ ] Retry × 3 plafonné, 4ᵉ refusé.
- [ ] Auto-approve supprimé partout.
- [ ] Dry-run obligatoire avant live, jamais bypassable.
- [ ] `before_drift_detected` détecte les changements latents Shopify.
- [ ] `is_pilot_safe_mode()` bloque toujours live.
- [ ] `confirm_live_write=true` requis pour live, jamais par défaut.
- [ ] Plan Free → bouton "Exporter" au lieu de "Live apply".
- [ ] `seo_changes` capture systématiquement le rollback pour les 10 content_types.
- [ ] `geo_impact_events` créé à chaque apply réussi, branché 136.
- [ ] Logs structurés `job_id + shop + content_type + action_id`.
- [ ] UI unique `app.safe-apply.tsx` remplace `app.review` + `app.descriptions`.
- [ ] Rollback per-item + batch (avec confirmation forte) opérationnel sur tous content_types.
- [ ] Idempotence : 2 apply identiques = no-op silencieux.
- [ ] Tests : pilot-safe bloque live, `forbidden_promise` empêche accept, drift detect re-générer, retry × 4 erreur, plan Free pas live.

---

## 16. Limites V1 explicites

- **Pas de workflow d'approbation à plusieurs niveaux** (manager + admin). 1 utilisateur Shopify Admin = 1 niveau d'approbation en V1.
- **Pas de scheduling d'apply** ("appliquer demain à 8 h"). Live apply est immédiat ou rien.
- **Pas de pre-staging dans un environnement de preview** Shopify (theme preview seulement, déjà supporté par Shopify nativement).
- **Pas de Slack/email notifications post-apply** en V1. À ajouter dans la tâche 102 ou plus tard.
- **Pas de signature cryptographique des changements**. La table `seo_changes` est la source de vérité, sans hash chain.
- **Rollback TTL 90 jours**. Au-delà, le revert reste possible mais demande confirmation explicite ("Ce changement date de plus de 90 jours, la valeur d'origine peut être obsolète").

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Workflow 7 étapes | ✅ Spécifié | Section 2 |
| Schéma `Diff` unifié | ✅ Spécifié | Section 3 |
| Décision humaine (accept/edit/reject/retry × 3) | ✅ Cadrée | Section 4 |
| Dry-run obligatoire + drift detect | ✅ Spécifié | Section 5 |
| Gates live (pilot-safe, confirm_live_write, plan, rate-limit) | ✅ Documentés | Section 6 |
| Event tracking strict (couplage 136) | ✅ Spécifié | Section 7 |
| Rollback per content_type | ✅ Documenté | Section 8 |
| UI unique `app.safe-apply.tsx` + dépréciations | ✅ Documenté | Section 9 |
| Plan-based behavior (Free/Pro/Agency) | ✅ Tableau | Section 10 |
| Garde-fous transversaux | ✅ Documentés | Section 11 |
| Cohérence autres modules 11.7 | ✅ Vérifiée | Section 14 |
| `app/safe_apply/diff.py`, `decisions.py`, `writer_adapters.py`, `rollback_adapters.py` | ⏳ À porter | Section 12 |
| Route `POST /safe-apply/*` canoniques | ⏳ À créer | Section 13 |
| UI `app.safe-apply.tsx`, `app.rollback-history.tsx` | ⏳ À créer | Section 12 |
| Extension `app/apply/shopify_writer.py` aux nouveaux content_types | ⏳ À porter | Section 12 |
| Migration `app.review`, `app.descriptions` | ⏳ À porter | Section 9 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 135. Ils seront pris en charge par la tâche d'implémentation Safe Apply ultérieure et par 136 (Impact Tracker consomme `geo_impact_events`) + 137 (Dashboard).
