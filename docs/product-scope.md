# Product Scope Simplification — Giulio Geo

> Référence canonique du périmètre produit V1 public. Tout module qui calcule un score, classe des recommandations, ou affiche une liste de produits doit respecter les règles documentées ici.
>
> Statut : décisions produit figées au 2026-05-19 (tâche 127, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche : ces règles seront appliquées incrémentalement par les modules concernés.

---

## 1. Pourquoi ce cadrage

Le score GEO/SEO actuel et les recommandations agrègent **tous les produits** du snapshot Shopify, quel que soit leur statut (`ACTIVE`, `DRAFT`, `ARCHIVED`, `UNLISTED`). Un marchand non technique voit donc :

- des scores artificiellement bas à cause de produits archivés ;
- des recommandations sur des `DRAFT` qui ne sont pas encore vendus ;
- des "Next Best Actions" sur des produits supprimés depuis longtemps ;
- aucune distinction visuelle entre les produits qui rapportent et ceux qui n'existent plus côté Online Store.

La tâche 127 fixe les règles pour que le **score principal et les actions prioritaires soient calculés uniquement sur les produits ACTIVE visibles sur Online Store**. Les autres statuts restent accessibles dans des vues dédiées, sans polluer le scoring principal.

---

## 2. Définitions de statut

| Statut Shopify | Définition | Inclus dans score principal ? | Vue dédiée |
|---|---|---|---|
| `ACTIVE` + visible Online Store | Produit publié et accessible publiquement | ✅ Oui | **Active Products** |
| `ACTIVE` mais hors canal Online Store (`UNLISTED`) | Publié sur d'autres canaux mais pas web | ❌ Non | **Hidden / Unlisted** |
| `DRAFT` | Produit en préparation, non publié | ❌ Non | **Pre-launch Drafts** |
| `ARCHIVED` | Produit retiré du catalogue actif | ❌ Non, exclu par défaut | **Cleanup / Archived** (accès via filtre avancé) |

> Note : le champ Shopify `publishedAt` (null si non publié) et `onlineStorePublication` (présence dans le canal Online Store) doivent être vérifiés en plus du `status` brut. Un produit `ACTIVE` mais sans `onlineStorePublication` est traité comme `UNLISTED`, pas comme `ACTIVE` Online Store.

---

## 3. Règle de scope principal

**Le score GEO global, le score SEO global, et la liste des recommandations prioritaires sont calculés uniquement sur les produits `ACTIVE` et publiés sur Online Store.**

Conséquences pratiques :

- `score_catalog_readiness()` (`app/geo/readiness.py:199`) doit recevoir un catalogue déjà filtré ou filtrer en amont.
- `prioritize_catalog()` (`app/geo/prioritization.py:167`) idem.
- `build_weekly_actions()` (`app/geo/weekly.py:68`) idem.
- `build_next_best_actions()` (`app/geo/next_best_actions.py`) idem, y compris `_similar_products()` qui ne suggère que des produits `ACTIVE` Online Store.
- `generate_catalog_content()` (`app/geo/faq_generator.py:441`) ne génère du contenu GEO que pour les produits `ACTIVE` Online Store. Les `DRAFT` ont un workflow séparé "Pre-launch check" (cf. section 4).

---

## 4. Mapping module par module

### Modules à aligner (filtrer par `status=ACTIVE` Online Store)

| Module | Fichier | Action |
|---|---|---|
| AI Search Readiness Score | `app/geo/readiness.py:199` (`score_catalog_readiness`) | Filtrer en entrée. Conserver pénalité individuelle `_commerce_score:123` pour le cas où un produit ACTIVE devient DRAFT en cours de vie. |
| Revenue-Aware Prioritization | `app/geo/prioritization.py:167` (`prioritize_catalog`) | Filtrer en entrée. Conserver `_inventory_signal:36` pour gérer rupture stock. |
| Weekly GEO Actions | `app/geo/weekly.py:68` (`build_weekly_actions`) | Filtrer en entrée. |
| Next Best Actions | `app/geo/next_best_actions.py` (`build_next_best_actions`, `_similar_products`) | Filtrer en entrée + suggestions de produits similaires. |
| FAQ & Buying Guide Automation | `app/geo/faq_generator.py:441` (`generate_catalog_content`) | Filtrer en entrée. Les drafts passent par "Pre-launch check" (cf. ci-dessous). |
| Product Facts Layer | `app/geo/facts.py` (à vérifier au moment de l'implémentation) | Le scan de faits manquants reste utile pour tous les statuts ; seul le score d'agrégation est limité à ACTIVE Online Store. |

### Vues séparées (consomment le même snapshot, filtres différents)

| Vue | Filtre | Affichage |
|---|---|---|
| **Active Products** | `status=ACTIVE` ET `onlineStorePublication=true` | Score GEO, score SEO, 3 actions prioritaires, dashboard impact. C'est la vue par défaut. |
| **Pre-launch Drafts** | `status=DRAFT` | Audit des faits manquants + recommandations préparées (pas appliquées tant que le produit n'est pas publié). Affiche un message "Préparez vos produits avant publication". |
| **Hidden / Unlisted** | `status=ACTIVE` ET `onlineStorePublication=false` | Diagnostic léger sans score principal. Affiche un message "Ces produits ne sont pas accessibles depuis votre site." |
| **Cleanup / Archived** | `status=ARCHIVED` | Liste seulement, pas de recommandation, accessible via filtre avancé. Permet au marchand de retrouver l'historique. |

---

## 5. Comportement UI cible

### Vue par défaut

L'écran principal de chaque module GEO (`/app/geo-readiness`, `/app/geo-priorities`, `/app/next-best-actions`, `/app/impact`, `/app/geo-faq-content`) affiche **Active Products** uniquement. Un bandeau indique le nombre de produits inclus et un lien vers les autres vues.

### Sélecteur de vue

Pattern Polaris recommandé : `Tabs` ou `Select` en haut de page, valeurs `Active`, `Pre-launch`, `Hidden`, `Archived`. La vue active est l'URL canonique ; les autres ajoutent un query param `?scope=draft|unlisted|archived`.

### Score principal

Le score affiché en grand (dashboard `/app/impact` notamment) est **toujours calculé sur Active Products**. Aucun mélange. Si un calcul élargi est nécessaire (audit historique), il doit être annoté explicitement avec son scope.

### Garde-fou UI

Aucun bouton "Appliquer" sur un produit `DRAFT` ou `ARCHIVED`. La review et la génération restent possibles en mode preview, mais l'écriture Shopify est désactivée tant que le produit n'est pas `ACTIVE` Online Store.

---

## 6. Backend : helper canonique à implémenter

Quand la première tâche consommatrice en aura besoin (probablement 131 Audit unifié), ajouter un helper canonique :

```python
# app/snapshot/scope.py (à créer plus tard, pas dans 127)
def filter_products_by_scope(products, scope="active"):
    """Filtre les produits par scope V1 public.

    scope: "active" | "draft" | "unlisted" | "archived" | "all"
    """
    if scope == "active":
        return [p for p in products if _is_active_online_store(p)]
    if scope == "draft":
        return [p for p in products if p.get("status") == "DRAFT"]
    if scope == "unlisted":
        return [p for p in products if p.get("status") == "ACTIVE" and not _is_online_store_published(p)]
    if scope == "archived":
        return [p for p in products if p.get("status") == "ARCHIVED"]
    return list(products)
```

> Helper à implémenter une seule fois. Tout module consommateur l'utilise. Aucun re-filtrage ad hoc dans chaque module.

---

## 7. Snapshot — pas de changement

Le snapshot Shopify (`app/snapshot/`, `app/api/snapshot_store.py:12`) continue à capturer **tous les produits** indépendamment du statut. Le filtrage est appliqué en aval, au moment du scoring / de l'affichage. Cela permet :

- de basculer entre vues sans re-fetcher Shopify ;
- de tracer un produit qui passe de DRAFT à ACTIVE ;
- de garder l'audit "Cleanup / Archived" disponible sans appel supplémentaire.

---

## 8. Critères d'acceptation des modules consommateurs

À cocher quand une tâche applique cette stratégie :

- [ ] Le module accepte explicitement un paramètre `scope` (`active` par défaut).
- [ ] Le module appelle `filter_products_by_scope()` (ou équivalent) avant tout scoring / agrégation.
- [ ] Le module n'expose pas de bouton "Apply" sur un produit hors scope `active`.
- [ ] La vue UI principale affiche Active Products par défaut.
- [ ] Le bandeau "x produits inclus" et le sélecteur de vue sont présents si la page liste des produits.
- [ ] Aucun score global n'agrège DRAFT / UNLISTED / ARCHIVED sans annotation explicite.
- [ ] La vue Pre-launch Drafts (si pertinente) propose review en preview sans écriture.

---

## 9. Garde-fous

- **Pas de masquage caché.** Le marchand peut toujours voir ses DRAFT et ARCHIVED via les vues dédiées. On simplifie le score principal, on ne supprime aucune information.
- **Pas de re-fetch Shopify** pour basculer entre vues : le snapshot couvre tous les statuts.
- **Pas de filtrage ad hoc** dans chaque module : un seul helper canonique.
- **Compatibilité ascendante.** Les API existantes qui retournent tous statuts ne sont pas cassées ; un nouveau paramètre `scope` est ajouté avec `active` par défaut au moment de l'implémentation, et les UI sont migrées en conséquence.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Définitions de statut et 4 vues | ✅ Documenté ici | Section 2 |
| Règle de scope principal = ACTIVE Online Store | ✅ Documenté ici | Section 3 |
| Mapping module par module | ✅ Documenté ici | Section 4 |
| Comportement UI cible | ✅ Documenté ici | Section 5 |
| Helper canonique `filter_products_by_scope` | ✅ Implémenté tâche 139 | `app/snapshot/scope.py` |
| Filtrage appliqué à `readiness`, `prioritization`, `weekly`, `next_best_actions`, `faq_generator` | ✅ Implémenté tâche 139 | `app/geo/*.py` + `app/api/geo.py` |
| Sélecteur de vue UI + vues séparées | ⏳ À implémenter par 137 (dashboard simplification) ou par chaque tâche concernée | Section 5 |
| Garde-fou UI "Apply" désactivé hors scope active | ⏳ À implémenter par 135 (Human Review & Safe Apply) | Section 5 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 127. Ils seront réalisés par les tâches consommatrices ou par la tâche d'infra qui aura le scope produit en dépendance directe.
