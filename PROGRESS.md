# PROGRESS — SEO Leoniedelacroix.com

## État global
- Dernière session : **2026-05-16** (clôture tâche 87)
- Phase 1 : **15/15** ✅
- Phase 2 : **14/14** ✅
- Phase 3 : **10/10** ✅
- Phase 4 : **5/5** ✅
- Phase 5 : **5/6** ✅ (tâche 49 supersédée par la tâche 75)
- Phase 6 : **7/7** ✅ (terminée 2026-05-10)
- Phase 7 : **11/11** ✅ (terminée 2026-05-11)
- Phase 8 : **7/7** ✅ (tâches 69-75 terminées côté repo ; soumission publique différée après Phase 10)
- Phase 9 : **7/7** ✅ (pilote réel terminé ; pass avec lacunes de mesure)
- Phase 10 : **4/21** 🔄 (tâches 83-86 clôturées ; prochaine tâche 87)
- Phase 11 : **0/2** ⏳ (go/no-go + soumission publique Shopify App Store)
- **Audit post-Phase 8** : 4 livrables + corrections TDD le 2026-05-12 (Vagues 1 à 5)
- Tests : **1101/1101** ✅ — ruff clean ✅ — Remix typecheck/build ✅

## Tâche 87 — Audit UI étendu dans l'app le 2026-05-16

- Ajout de `app/api/audit.py` : filtre `resource_type` sur `GET /api/shops/{shop}/audit/issues`.
- Nouvelle route Remix `shopify-app/app/routes/app.audit.tsx` :
  - loader : fetch issues Shopify (depuis snapshot), score SEO et issues crawl en parallèle ;
  - fusion et tri des issues Shopify + crawl par sévérité ;
  - filtres client-side par sévérité (critical / high / medium / low / info) et par type de ressource (produit / collection / image / page / redirect) avec compteurs ;
  - score global + composants + résumé sévérités en haut de page ;
  - liste des issues avec badge sévérité, badge type ressource, label lisible issue_type, titre ressource tronqué et détail lisible ;
  - état vide si aucune donnée ou backend hors-ligne ;
  - limite d'affichage à 200 issues avec message si dépassé.
- Ajout du lien "Audit" dans le NavMenu (`app.tsx`), entre Dashboard et Review IA.
- Ajout de la clé i18n `audit` FR/EN dans `i18n.ts`.
- 1 nouveau test `test_get_issues_resource_type_filter` dans `tests/test_api/test_audit.py`.
- Vérification :
  - `pytest tests/test_api/test_audit.py` : **11 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1102 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **88 — Ajouter la matrice ICE dans l'app**.

## Tâche 86 — Import crawl technique ajouté dans l'app le 2026-05-16

- Ajout du module `app/crawl/` :
  - parse CSV Screaming Frog overview + redirects depuis bytes uploadés ;
  - détection 404, chaînes de redirection, 302 temporaires, titres dupliqués, descriptions dupliquées, canonical manquant, canonical non-self ;
  - stockage shop-scopé `data/raw/{shop}/crawl_report.json` + horodaté ;
  - `latest_crawl_status(shop)` retourne disponibilité, url_count, issue_count, by_severity et liste d'issues.
- Ajout des endpoints :
  - `GET /api/shops/{shop}/crawl/status` ;
  - `POST /api/shops/{shop}/crawl/upload` (multipart CSV, traitement synchrone).
- Ajout de `callBackendMultipartForShop` dans `shopify-app/app/lib/api.server.ts` pour les uploads multipart sans Content-Type forcé.
- L'Onboarding Shopify affiche maintenant :
  - un Step `Crawl technique` dans la checklist d'installation ;
  - une card dédiée avec statut, compteurs par sévérité, top issues critiques, et formulaire d'upload CSV (overview obligatoire + redirects optionnel).
- `python-multipart` ajouté à `pyproject.toml` (dépendance standard FastAPI pour les uploads).
- Vérification :
  - ciblée : `pytest tests/test_crawl/ tests/test_api/test_crawl.py` : **17 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1101 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **87 — Étendre l'audit UI**.

## État courant pour Codex

- Fichier de règles actif : `AGENTS.md`
- Ancien fichier `CLAUDE.md` : archive legacy, ne pas l'utiliser comme source de vérité
- Gestion du contexte : Codex compacte automatiquement ; ne pas utiliser `/compact` ou `/clear`
- Tâche suivante : **88 — Ajouter la matrice ICE dans l'app**

## Checkpoint de pause — 2026-05-12

- La tâche **76** est terminée côté repo.
- La reprise a redémarré sur la tâche **77**, clôturée le 2026-05-15.
- Le repo est prêt à être checkpointé puis poussé sur Git.
- Historique des actions Shopify Partner prévues avant ou pendant la tâche 77, réalisées depuis :
  - créer l'app pilote distincte en **Custom distribution** ;
  - cibler `287c4a-bb.myshopify.com` ;
  - générer le lien d'installation marchand ;
  - relier la config CLI `pilot` avec `shopify app config link --config pilot` ;
  - déployer la config publique une fois l'URL HTTPS prête.

## Reprise 2026-05-13 → 2026-05-15 — Tâche 77 terminée

- L'app Shopify `Léonie SEO Pilot` a été créée dans l'organisation `Léonie Delacroix`.
- `shopify-app/shopify.app.pilot.toml` est lié à cette app et versionné dans le repo.
- L'origine stable retenue est `https://pilot.leoniedelacroix.com`.
- Un Blueprint Render `render.yaml` prépare deux services :
  - `leonie-seo-pilot-web` pour Remix ;
  - `leonie-seo-pilot-api` pour FastAPI.
- Les deux services Render sont déployés et répondent :
  - `https://leonie-seo-pilot-api.onrender.com/health` retourne `status=ok` ;
  - `https://leonie-seo-pilot-web.onrender.com/healthz` retourne `ok`.
- `PYTHON_BACKEND_URL` du service web pointe bien vers `https://leonie-seo-pilot-api.onrender.com`.
- Le domaine custom `https://pilot.leoniedelacroix.com` est vérifié dans Render.
- La configuration Shopify `pilot` a été déployée et publiée en version `leonie-seo-pilot-2`.
- L'app pilote a été retrouvée dans le Developer Dashboard via l'URL directe et installée sur la boutique réelle `Léonie Delacroix`.
- Point d'organisation à traiter plus tard : clarifier/supprimer l'organisation legacy `Léonie Delacroic` pour ne garder que `Léonie Delacroix` comme espace Partner opérationnel.
- Validation pilote réelle :
  - OAuth et chargement embedded dans l'Admin Shopify fonctionnent ;
  - la navigation entre Dashboard, Review IA, Niche, Onboarding, Jobs SEO, Facturation, Réglage et Confidentialité fonctionne ;
  - le plan Free remonte correctement ;
  - le lancement d'audit crée un job côté UI, mais la page Jobs SEO ne le listait pas à cause d'un endpoint backend qui exigeait un token OAuth Python pour lire la queue.
- Correctifs prêts à déployer :
  - `LEONIE_BILLING_MODE=disabled` bloque toute création d'abonnement pendant le pilote ;
  - `/api/shops/{shop}/jobs` vérifie l'appel interne Remix sans exiger de token Shopify stocké côté Python.
- À redéployer sur Render puis retester : relancer un audit, recharger Jobs SEO, vérifier que le job apparaît et passe `pending` → `completed` ou expose une erreur claire.
- Retest après redéploiement : les jobs d'audit apparaissent bien et passent `completed`.
- Nouveau bug pilote identifié : la navigation App Bridge sélectionnait parfois un onglet sans charger la route Remix, ou nécessitait plusieurs clics/rechargements.
- Correctif prêt à déployer : `NavMenu` utilise maintenant des ancres HTML `<a href=...>` au lieu de `Link` Remix, conformément à App Bridge v4.
- Retest navigation : amélioration confirmée.
- Nouveau bug pilote identifié : Review IA affichait `403`, Onboarding affichait Shopify en `TODO`, et Niche restait vide car le backend Python ne recevait pas le token OAuth géré par Remix.
- Correctif prêt à déployer : Remix relaie le token `authenticate.admin` au backend uniquement sur le canal interne protégé (`X-Leonie-Shop` + `X-Internal-Secret`), et Python accepte ce token comme contexte d'installation sans l'exposer au navigateur.
- Données attendues après correctif : Onboarding doit passer Shopify en `OK`; Review IA ne doit plus afficher `403` mais probablement `Aucune donnée disponible`; Niche restera vide tant qu'un vrai snapshot crawl/GSC n'est pas produit.
- Retest OAuth/backend : Onboarding affiche Shopify `OK`, Review IA n'affiche plus `403`, Niche reste vide faute de crawl réel.
- Correctif prêt à déployer : le job `seo_audit` exécute maintenant un crawl Shopify GraphQL en lecture seule, sauvegarde `data/raw/{shop}/shopify_snapshot.json`, `data/raw/{shop}/snapshot_<timestamp>.json`, et insère les lignes `snapshots` avec le shop.
- Sécurité pilote : le token Shopify transmis par Remix est sauvegardé via `token_store` chiffré, pas dans le payload persistant du job.
- À retester après redéploiement : lancer un audit SEO, attendre `completed`, puis vérifier Onboarding `Crawl OK` avec produits/collections et Niche avec clusters produits.
- Bug pilote après retest : le job `seo_audit` passait `completed`, mais Onboarding restait `Crawl TODO / 0 produits`.
- Correctif prêt à déployer : les endpoints Status, Audit et Niche lisent désormais le snapshot depuis `data/raw/{shop}/...` puis basculent sur la table durable `snapshots` si le fichier local manque.
- Retest crawl : Onboarding affiche les produits après audit.
- Correctif prêt à déployer : Review IA dispose d'un bouton `Générer suggestions IA` qui lance un job `meta_generation` depuis le dernier snapshot produit, sans écriture Shopify.
- À retester : cliquer `Générer suggestions IA`, attendre le job `completed`, puis recharger Review IA pour afficher les suggestions pending.
- Bug pilote identifié : un job `meta_generation` est resté en `running` plus de 12 minutes.
- Correctif prêt à déployer : le worker récupère les jobs `running` trop vieux après redémarrage/timeout, les remet en `pending` ou `failed` selon les retries, capture les erreurs LLM configurables, et Jobs SEO affiche maintenant le résultat ou l'erreur du job.
- À retester après redéploiement : recharger Jobs SEO, vérifier que l'ancien job n'est plus bloqué en `running`, puis relancer `Générer suggestions IA` si nécessaire.
- Retest génération IA : le job `meta_generation` est passé `completed` et a généré 21 suggestions, visibles dans Review IA.
- Bug UI pilote identifié : la colonne Produit de Review IA devenait trop large avec un titre produit long et masquait les colonnes à droite.
- Correctif prêt à déployer : Review IA contraint les largeurs Produit/Titre/Description et force le retour à la ligne des textes longs.
- Retest Review IA : approuver/rejeter une suggestion retire bien la ligne du tableau pending.
- Correctif prêt à déployer : Review IA affiche le nombre de suggestions approuvées prêtes, renomme l'action en `Prévisualiser l'application`, bloque l'action si rien n'est approuvé, et confirme qu'aucune modification Shopify n'est faite en mode prévisualisation.
- Retest prévisualisation : le job `bulk_apply` en dry-run passe `completed`.
- Correctif prêt à déployer : le rapport dry-run contient maintenant les produits concernés, le titre courant connu, les nouvelles meta proposées, et Jobs SEO affiche une carte de prévisualisation détaillée sans écriture Shopify.
- Correctif prêt à déployer : la prévisualisation dry-run lit désormais les champs SEO actuels du produit directement dans Shopify quand un token OAuth est disponible, sans mutation, et Jobs SEO indique si l'avant vient de Shopify ou du crawl.
- Correctif prêt à déployer : Review IA affiche désormais un panneau `Audit qualité` pour les suggestions visibles, avec nombre de suggestions OK, suggestions à relire, longueurs moyennes title/description, et principaux motifs de rejet qualité.
- Hotfix prêt à déployer : Review IA normalise les données reçues du backend avant rendu pour éviter une erreur serveur si une suggestion contient une valeur absente ou inattendue.
- Correctif prêt à déployer : les suggestions `À relire` sont maintenant visibles directement dans la colonne Qualité, et l'audit affiche un motif générique quand le backend ne fournit pas de détail technique.

### Clôture 2026-05-15 — Tâche 77

- La tâche **77** est clôturée côté repo et validation locale.
- L'app pilote est installée sur la boutique réelle et les flux critiques ont été validés :
  - OAuth embedded Shopify ;
  - appels internes Remix → Python avec `X-Leonie-Shop`, `X-Internal-Secret` et token Shopify relayé serveur-à-serveur ;
  - sessions et token store chiffré ;
  - Billing désactivable avec `LEONIE_BILLING_MODE=disabled` pour le pilote ;
  - webhooks GDPR/app uninstall présents ;
  - jobs `seo_audit`, `meta_generation` et `bulk_apply` visibles et scopés au shop ;
  - snapshot Shopify réel persisté en fichier et en table `snapshots` ;
  - récupération des jobs `running` obsolètes ;
  - génération IA, review, approbation/rejet et dry-run apply opérationnels.
- La roadmap a été réorganisée :
  - les anciennes tâches App Store finales ont été déplacées après la parité fonctionnelle ;
  - la Phase 10 porte les fonctionnalités restantes des scripts CLI vers l'app Shopify ;
  - la Phase 11 devient le go/no-go puis la soumission publique Shopify App Store.
- Vérifications locales du 2026-05-15 :
  - `ruff check .` : OK ;
  - `pytest` : **1050 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Suite immédiate après tâche 77 : **78 — mode pilot-safe strict**.

## Tâche 78 — Mode pilot-safe strict terminée le 2026-05-15

- Ajout de `app/safety.py` comme garde-fou central des mutations Shopify.
- Nouveau flag backend `LEONIE_PILOT_SAFE_MODE=true` :
  - bloque les écritures live Shopify pendant le pilote ;
  - autorise les dry-runs ;
  - autorise les lectures Shopify nécessaires aux prévisualisations ;
  - bloque aussi les mutations Shopify Billing pendant le pilote.
- Hors pilot-safe, les écritures live via API/apply ou job `bulk_apply` exigent désormais une confirmation explicite `confirm_live_write=true`.
- `bulk_apply` est protégé à deux niveaux :
  - au moment de l'enqueue API ;
  - au moment de l'exécution orchestrateur, pour empêcher un payload de job forgé.
- La page Settings affiche maintenant l'état du mode pilote.
- `render.yaml`, `.env.example` et `docs/pilot-real-store-setup.md` documentent/activent le mode pilote.
- Tests ciblés ajoutés pour :
  - dry-run autorisé en pilot-safe ;
  - live apply bloqué sans confirmation ;
  - live apply bloqué en pilot-safe même avec confirmation ;
  - `bulk_apply` bloqué côté API et côté orchestrateur ;
  - Billing subscribe/cancel bloqués en pilot-safe.
- Vérification ciblée :
  - `pytest tests/test_api/test_apply.py tests/test_apply/test_bulk_orchestrator.py tests/test_api/test_generate.py tests/test_billing/test_router.py` : **50 passed** ;
  - `ruff check app tests` : OK ;
  - `cd shopify-app && npm run typecheck` : OK.
- Vérification complète :
  - `ruff check .` : OK ;
  - `pytest` : **1060 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **79 — tester les parcours métier réels**.

## Tâche 79 — Parcours métier réels terminée le 2026-05-16

- Ajout de `docs/pilot-real-store-test-plan.md` :
  - checklist embedded Shopify Admin ;
  - critères de pass/fail ;
  - preuves à enregistrer ;
  - points de confiance autour du pilot-safe, Billing, Privacy, Review IA et Jobs SEO.
- Ajout de `docs/pilot-real-store-test-log.md` pour journaliser les passes réelles.
- Mise à jour du README : roadmap 11 phases / 105 tâches, Phase 9 à 4/7, liens vers setup + plan de test pilote.
- Ajout de `leonie-seo pilot smoke-public` pour relancer les smoke checks publics du pilote avec un timeout adapté aux cold starts Render Free.
- Smoke checks publics exécutés le 2026-05-15 :
  - `curl -fsS https://pilot.leoniedelacroix.com/healthz` → `ok` ;
  - `curl -fsS https://leonie-seo-pilot-api.onrender.com/health` → `{"status":"ok","missing_env":[]}` ;
  - `curl -fsS -o /dev/null -w '%{http_code}\n' https://leonie-seo-pilot-api.onrender.com/privacy` → `200`.
  - `python -m scripts.cli pilot smoke-public --timeout 90` → 3 checks OK.
- Note : `HEAD /privacy` retourne `405` avec `allow: GET`, comportement acceptable car la page privacy est servie en GET.
- Vérification locale :
  - `pytest tests/test_pilot_smoke.py tests/test_cli.py` : **45 passed** ;
  - `ruff check scripts/pilot_smoke.py scripts/cli.py tests/test_pilot_smoke.py tests/test_cli.py` : OK ;
  - `ruff check .` : OK ;
  - `pytest` : **1066 passed**.
- Parcours embedded Shopify Admin exécuté le 2026-05-16 depuis une session marchand connectée :
  - installation/session : pass ;
  - navigation : pass ;
  - Settings / pilot-safe : pass, avec une note UX car le libellé exact `Mode pilot-safe actif` n'était pas visible ;
  - audit job, crawl produits/collections, niche clusters : pass ;
  - génération meta, suggestions, approbation/rejet : pass ;
  - dry-run job et preview : pass ;
  - Billing bloqué et Privacy : pass ;
  - bugs/frictions : aucun blocage signalé.
- Journal mis à jour dans `docs/pilot-real-store-test-log.md`.
- Décision : **pass**.
- Prochaine tâche : **80 — capturer les retours d'usage et frictions UX/confiance du pilote**.

## Tâche 80 — Retours pilote consolidés le 2026-05-16

- Ajout de `docs/pilot-real-store-feedback.md` comme backlog de feedback pilote.
- Synthèse du passage réel :
  - aucun bug bloquant ;
  - parcours confiance validé : audit, crawl, niche clusters, génération IA, approbation/rejet, dry-run preview, Billing bloqué, Privacy ;
  - aucune écriture live Shopify observée ou demandée ;
  - un seul retour UX direct : le libellé Settings du mode pilot-safe doit être plus explicite/stable.
- Classement des éléments non bloquants :
  - IDs jobs et compteurs non copiés dans le log : amélioration de preuve de test, pas bug produit ;
  - zones dépendantes GSC/GA4/PageSpeed : manques attendus et déjà suivis en Phase 10.
- Décision : **task 80 pass**.
- Prochaine tâche : **81 — corriger la vague pilote prioritaire**, avec un périmètre initial volontairement réduit au wording pilot-safe Settings sauf nouveau retour.

## Tâche 81 — Vague pilote prioritaire terminée le 2026-05-16

- Correction ciblée du seul retour UX confirmé :
  - Settings affiche maintenant `Mode pilot-safe actif` quand le mode pilot-safe est activé ;
  - le badge indique `Écritures live bloquées` ;
  - le texte d'aide précise que les dry-runs restent autorisés et qu'aucune écriture Shopify live ne peut partir.
- Fichier modifié : `shopify-app/app/routes/app.settings.tsx`.
- `docs/pilot-real-store-feedback.md` documente la résolution de P80-001.
- Vérification :
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **82 — mesurer le pilote**.

## Tâche 82 — Mesure pilote terminée le 2026-05-16

- Ajout de `docs/pilot-real-store-measurement.md`.
- Décision : **pass avec lacunes de mesure**.
- Mesures consolidées :
  - public smoke checks : 3/3 ;
  - parcours embedded : 13/13 zones passées ;
  - bugs bloquants finaux : 0 ;
  - suggestion generation : 21 suggestions dans le retest documenté ;
  - écritures live observées : 0 ;
  - mutations Billing autorisées : 0 ;
  - retour UX direct : 1, corrigé en tâche 81.
- Lacunes à corriger dans les prochains passes :
  - IDs et durées des jobs ;
  - compteurs exacts produits/collections ;
  - compteurs generated/approved/rejected ;
  - coût LLM et tokens du shop pilote ;
  - métrique de récupération des jobs `running`.
- Conclusion : Phase 9 terminée ; le pilote réel est assez solide pour démarrer la Phase 10.
- Prochaine tâche : **83 — connecter Google Search Console dans l'app**.

## Tâche 83 — Google Search Console connecté dans l'app le 2026-05-16

- Ajout du module `app/gsc/` :
  - state OAuth Google signé et expirant ;
  - stockage chiffré des credentials Google par shop dans `google_tokens` ;
  - client Search Console `searchanalytics().query(...)` ;
  - import page et query×page en fichiers shop-scopés.
- Ajout des endpoints :
  - `GET /api/shops/{shop}/gsc/status` ;
  - `POST /api/shops/{shop}/gsc/authorize` ;
  - `POST /api/shops/{shop}/gsc/import` ;
  - `GET /api/google/gsc/callback`.
- Ajout du job async `gsc_import`.
- L'Onboarding Shopify affiche maintenant :
  - l'état de connexion GSC ;
  - la propriété GSC cible ;
  - le lien de consentement Google ;
  - l'action `Importer 90 jours` ;
  - la fraîcheur et le nombre de lignes du dernier import.
- Les exports créés alimentent les vues Niche existantes via `data/raw/{shop}/gsc_*.json`.
- Configuration pilote documentée :
  - `GOOGLE_OAUTH_CLIENT_CONFIG` ou `GOOGLE_OAUTH_CLIENT_PATH` ;
  - `GOOGLE_OAUTH_REDIRECT_URI` ;
  - `GOOGLE_OAUTH_STATE_SECRET`.
- Vérification :
  - ciblée : `pytest tests/test_gsc tests/test_api/test_gsc.py tests/test_jobs/test_worker.py tests/audit/test_fetch_gsc.py` : **22 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1075 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **84 — porter les opportunités GSC dans l'app**.

## Tâche 84 — Opportunités GSC portées dans l'app le 2026-05-16

- Ajout de `GET /api/shops/{shop}/gsc/opportunities`.
- L'endpoint réutilise le moteur CLI `scripts.audit.detect_gsc_opportunities` pour conserver une seule logique métier :
  - positions 11-20 comme quick wins ;
  - pages à CTR faible ;
  - opportunités long terme ;
  - estimation de clics gagnables ;
  - priorisation par score d'impact.
- La page Niche Shopify affiche maintenant une carte `Opportunités GSC` avec :
  - total des opportunités détectées ;
  - répartition quick wins / CTR faible ;
  - gain estimé total ;
  - tableau des pages, zones, positions, impressions, CTR et clics gagnables.
- L'état vide explique que Google Search Console doit être connecté et importé avant de calculer ces opportunités.
- Vérification :
  - ciblée : `pytest tests/test_api/test_gsc.py tests/audit/test_detect_gsc_opportunities.py` : **25 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1077 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **85 — ajouter PageSpeed / Core Web Vitals dans l'app**.

## Tâche 85 — PageSpeed / Core Web Vitals ajoutés dans l'app le 2026-05-16

- Ajout du module `app/pagespeed/` :
  - sélection d'URLs prioritaires par shop depuis la config tenant, puis fallback homepage + collections + produits du dernier snapshot ;
  - import PageSpeed mobile/desktop via le moteur CLI existant ;
  - exports shop-scopés `data/raw/{shop}/pagespeed.csv` et `pagespeed_*.csv` ;
  - résumé mobile/desktop, alertes CWV, recommandations non techniques et détection de régressions entre deux imports.
- Ajout des endpoints :
  - `GET /api/shops/{shop}/pagespeed/status` ;
  - `POST /api/shops/{shop}/pagespeed/import`.
- Ajout du job async `pagespeed_import`.
- L'Onboarding Shopify affiche maintenant :
  - l'état PageSpeed / Core Web Vitals ;
  - les moyennes mobile et desktop ;
  - le nombre d'alertes ;
  - un bouton `Analyser les URLs prioritaires` ;
  - les principales alertes avec une recommandation lisible marchand.
- La page Jobs SEO résume les résultats `pagespeed_import` avec nombre d'URLs, scores et régressions.
- La configuration backend bloque l'enqueue si `PAGESPEED_API_KEY` est absente.
- Correction opportuniste : `find_tenant_by_shop_domain` expose aussi `base_url`, `gsc_property` et `pagespeed_urls`, nécessaires aux workflows app GSC/PageSpeed.
- Vérification :
  - ciblée : `pytest tests/test_pagespeed tests/test_api/test_pagespeed.py tests/test_jobs/test_worker.py tests/audit/test_fetch_pagespeed.py` : **20 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1084 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **86 — ajouter un import crawl technique dans l'app**.

## ⚠️ Archive — audit vision gap initial (2026-05-10)

Un audit complet (`RAPPORT_AUDIT.md`) + analyse critique externe ont évalué la couverture vs. la vision App Store cible.
**Couverture évaluée à l'époque : 28 %** — 3 blockers critiques + 4 risques structurels identifiés.
Ces blockers ont été traités depuis dans les phases 6 à 8 et les vagues d'audit 1-2.

### Blockers critiques identifiés à l'époque (résolus depuis)
| Bloquant | État | Impact |
|---|---|---|
| GDPR webhooks (`customers/redact`, `shop/redact`, `data_request`) | ✅ Résolu tâche 51 | Rejet immédiat App Store évité |
| Shopify Billing API (`appSubscriptionCreate`) | ✅ Résolu tâche 52 | Monétisation App Store possible |
| App Bridge + Polaris | ✅ Résolu tâche 56 | App embedded Shopify Admin |
| Async job queue | ✅ Résolu tâche 55 | Jobs longs hors requêtes HTTP |

### Risques structurels identifiés
- **Architecture pivot** : **Option B retenue** — scaffold Remix propre via Shopify CLI (`shopify-app/`), moteur Python conservé (`scripts/`, `app/llm/`, `app/niche/`). `frontend/` React décommissionné après tâche 57. Voir `DECISIONS.md`.
- **Niche Intelligence** : le différenciateur principal — mais risque de générer des recommandations vagues si non cadré. Approche retenue : clusters produits réels + saturation SERP + keyword gaps (jamais "le marché est en croissance").
- **Common Crawl** : déféré en Phase 8 après validation des sources légères (Google Suggest, pytrends, Reddit). Évite un puits de complexité prématuré.
- **Coût LLM** : GPT-4o mini estimé ~4,5 $/1 000 produits si non optimisé. Maîtrisé par : prompts déterministes, templates versionnés, fallbacks gratuits, cost tracker par tenant (tâche 68).

### Axes manquants à l'époque (résolus depuis)
- **IA / LLM** : ✅ tâches 58-61
- **Niche Intelligence engine** : ✅ tâches 62-63
- **Semantic embeddings** : ✅ tâches 64 et 70
- **Theme App Extension** : ✅ tâche 69
- **Observabilité** : ✅ tâche 68
- **GA4 API** : ✅ tâche 73
- **SQLite → Postgres** : ✅ tâche 54

### Ce qui est solide (à conserver dans tous les scénarios)
- Moteur d'audit Python (`scripts/`) — crawl, GSC, PageSpeed, détection ✅
- OAuth Shopify + token store ✅
- FastAPI backend + CLI Click ✅
- Système de plans + licence HMAC ✅
- Multi-tenant YAML ✅
- 537 tests, ruff clean ✅

## ✅ Terminé

### Infrastructure
- Initialisation repo Git + structure dossiers
- Instructions agent réorganisées avec protocole début de session + ordre des tâches (`AGENTS.md` actif pour Codex)
- Setup credentials API : Shopify token, Google OAuth, PageSpeed key, GA4 Property ID
- `.env`, `.env.example`, `.gitignore` configurés
- `pyproject.toml` avec `[tool.setuptools]` pour discovery correcte

### Phase 1 — Fondations & Audit (tâches 1–15) ✅
- `scripts/audit/crawl_shopify.py` — GraphQL paginé, snapshot JSON + SQLite
- `scripts/audit/fetch_gsc.py` — OAuth navigateur, export 90j par URL + query×page
- `scripts/audit/fetch_pagespeed.py` — score mobile/desktop + CWV (timeout 600s, retry)
- `scripts/audit/parse_screaming_frog.py` — parser overview/images/redirects CSV
- `scripts/audit/detect_issues.py` — 5 détecteurs (titles, descriptions, alt, duplicates, redirects/404)
- `scripts/report/generate_report.py` — score /100 pondéré + rapport Markdown horodaté
- `scripts/apply/update_meta.py` — mutation GraphQL, dry-run par défaut, logging SQLite

### Phase 2 — Application supervisée (tâches 16–29) ✅
- **16** `scripts/report/ice_matrix.py` — Matrice ICE pondérée GSC
- **17–21** `generate_suggestions.py` + `update_alt_text.py` — **26 méta + 17 alt texts poussés** sur Shopify
- **22** `scripts/apply/create_redirects.py` — import 301 bulk depuis CSV
- **23** `scripts/apply/add_schema.py` — JSON-LD schema.org/Product via metafield custom.json_ld
- **24** `scripts/apply/rollback.py` — CLI rollback SQLite (`--list`, `--revert-ids`, `--revert-since`)
- **25** `scripts/audit/detect_gsc_opportunities.py` — 3 zones ; **17 opportunités, +148 clics estimés**
- **26** `scripts/audit/analyze_longtail.py` — gap analysis mots-clés vs GSC + Shopify
- **27** `scripts/report/generate_delta_report.py` — **score 56.3 → 83.9 (+27.6 pts), 62/68 issues résolues**
- **28** `.github/workflows/weekly_audit.yml` — pipeline CI complet, 6 secrets GitHub
- **29** `scripts/report/send_alerts.py` — alertes email CWV + positions + CTR, SMTP Gmail

### Phase 3 — Contenu SEO & Intelligence niche (tâches 30–39) ✅
- **30** `scripts/report/generate_blog_briefs.py` — 10 briefs H1/H2/E-E-A-T par requête cible
- **31** `scripts/apply/rewrite_descriptions.py` — 18 descriptions longue traîne, classification title-priority
- **32** `scripts/report/detect_internal_links.py` — 120 opportunités, 5 pages orphelines
- **33** `scripts/report/analyze_semantics.py` — scoring 4 dimensions vs benchmark Miacara/Zooplus
- **34** `scripts/report/generate_faq.py` — 21 Q/R × 5 catégories, JSON-LD FAQPage
- **35** `scripts/audit/detect_cannibalization.py` — query×page GSC, score sévérité 0–1, canonical/consolidation
- **36** `scripts/report/score_eeat.py` — 4 dimensions (Exp 20%, Expert 30%, Auth 25%, Trust 25%)
- **37** `scripts/report/generate_hreflang.py` — Liquid snippet + sitemap XML, fr-FR/fr-BE/fr-CH/x-default
- **38** `scripts/report/generate_monthly_report.py` — rapport HTML print-ready (Ctrl+P → PDF)
- **39** `scripts/report/dashboard.py` — dashboard `rich` snapshot + `--watch` 30s

### Données réelles
- **50 URLs GSC** · 90 jours · 245 clics · 3 736 impressions · position moyenne 6.0
- **69 changements** loggés dans `data/history.db`
- **Score SEO avant : 56.3 → après : 83.9 (+27.6 pts)**
- **Pipeline CI GitHub Actions** validé : tests + audit + tous les rapports Phase 3

### Phase 4 — Productisation (tâches 40–44) ✅
- **40** `config/tenants/leoniedelacroix.yaml` + `scripts/_config.py` — abstraction multi-tenant complète
  - Pydantic v1 `TenantConfig` : base_url, brand, categories, product_categories, hreflang_locales, seo_rules, alert_thresholds
  - 16 scripts migrés : domaine, brand, thresholds SEO → tous via `get_config(tenant_id)`
  - Option `--tenant` ajoutée à tous les CLI
  - 319 tests verts · ruff clean
- **41** `scripts/setup.py` — wizard CLI `init` / `list` / `check`
  - Renommage niche `petfood_fr` → `pet_accessories_fr` (plus fidèle au business)
  - `init` : wizard interactif → génère `config/tenants/<id>.yaml` + met à jour `.env`
  - `list` : tableau de tous les tenants avec marqueur tenant actif
  - `check` : validation config + secrets `.env` requis
  - 342 tests verts · ruff clean
- **42** `NicheConfig` + 4 YAML niches + migration 4 scripts
  - `scripts/_config.py` : modèles `NicheSignals`, `NicheEeatDimensions`, `NicheBlogTemplate`, `NicheConfig` + `load_niche()` lru_cache
  - `config/niches/pet_accessories_fr.yaml` : signals premium/eeat/longtail/category, dimensions EEAT, 21 FAQ Q/R, 5 blog templates
  - 3 nouveaux secteurs : `cosmetics_fr.yaml`, `mode_fr.yaml`, `jardinage_fr.yaml`
  - 4 scripts migrés : `analyze_semantics.py`, `score_eeat.py`, `generate_faq.py`, `generate_blog_briefs.py`
  - `tests/test_niche_config.py` : 23 nouveaux tests
  - **365 tests verts** · ruff clean
- **43** `scripts/license.py` — HMAC-SHA256, CLI `issue`/`check`, intégration 3 scripts
  - **389 tests verts** · ruff clean
- **44** `scripts/cli.py` + `pyproject.toml` + `Dockerfile` + `install.sh`
  - Point d'entrée `leonie-seo` avec 5 groupes : `setup`, `license`, `audit` (7 cmds), `report` (12 cmds), `apply` (7 cmds)
  - `pip install -e .` → `leonie-seo --help` opérationnel
  - `install.sh` : bootstrap en une commande (venv + pip + .env)
  - `Dockerfile` : Python 3.11-slim, volumes pour data/reports/config
  - **428 tests verts** · ruff clean

### Phase 5 — App Shopify publique (tâches 45–50) ✅ (5/6)
- **50** `app/api/help.py` + `frontend/src/components/HelpPanel.jsx` — FAQ bilingue FR/EN 11 entrées, accordéon + recherche
  - `docs/guide-utilisateur.fr.md`, `docs/user-guide.en.md`, `docs/plans.md`
  - `README.md` réécrit : plans, options install, workflow CLI, licences
  - **537/537 tests verts** · ruff clean
- **48** `app/api/plans.py` + `app/api/deps.py` — plans Free/Pro/Agency, `require_feature()` dependency FastAPI
  - `scripts/license.py` étendu : champ `plan` dans clé HMAC, `--plan` CLI option
  - Badge plan dans header React (`tag-plan-free/pro/agency`)
  - 17 tests plans + 10 tests licence
  - **537/537 tests verts** · ruff clean
- **49** Soumission App Store — supersédée par la tâche 75 (soumission finale après phases 6-8)
- **47** `frontend/` — Dashboard React (Vite + React)
  - 3 vues : Dashboard (score + détail composants), Issues (filtrables par sévérité), Appliquer (dry-run → confirm)
  - `api.js` : wrappers fetch vers FastAPI
  - CORS middleware + serve SPA depuis FastAPI en production
  - `npm run build` → `frontend/dist/` servi par FastAPI
  - **469 tests Python verts** · build Vite clean
- **46** `app/api/` — Backend FastAPI (REST → moteur Python)
  - `deps.py` : `ShopContext` — résolution token OAuth ou fallback `.env`
  - `shops.py` : `GET /api/shops` · `GET /api/shops/{shop}/status`
  - `audit.py` : `GET /api/shops/{shop}/audit/issues` · `/score` (depuis snapshot JSON)
  - `apply.py` : `POST /api/shops/{shop}/apply/meta` (`dry_run=true` par défaut)
  - **469 tests verts** · ruff clean
- **45** `app/main.py` + `app/oauth/` — OAuth Shopify complet
  - `hmac_validator.py` : validation HMAC-SHA256 des callbacks Shopify
  - `token_store.py` : SQLite `shop_tokens` (save/get/delete, `installed_at` préservé)
  - `router.py` : `GET /shopify/install` → redirect OAuth + `GET /shopify/callback` → échange code/token
  - Sécurité : HMAC validé, state UUID4 anti-CSRF (TTL 10 min), token jamais exposé en réponse
  - Nouvelles deps : `fastapi`, `uvicorn[standard]`, `httpx`
  - **449 tests verts** · ruff clean

## ✅ Phases 1-7 complètes — Phase 8 en finalisation

## ✅ Tâche 75 — Préparation App Store finale côté repo
Préparation repo terminée le **2026-05-12** :
- preview locale Shopify stabilisée pour tests réels en dev store ;
- frontend Remix déclaré via `shopify.web.toml` ;
- config `shopify.app.local.toml` dédiée au mode localhost ;
- fallback de session storage local corrigé ;
- route embedded `auth.$.tsx` ajoutée ;
- enregistrement des webhooks ignoré automatiquement en localhost ;
- checklist de soumission documentée dans `docs/app-store-submission-checklist.md`.

La publication publique est volontairement différée derrière une nouvelle séquence de pilote réel sur la boutique Shopify de production.

## ⏳ Phase 9 — Pilote marchand réel avant App Store

**Objectif** : installer et tester Léonie SEO sur la vraie boutique Shopify `leoniedelacroix.com`, observer les frictions réelles, adapter le produit, puis seulement soumettre l'app publiquement.

**Séquence ordonnée** :
- **76** ✅ Préparer l'environnement pilote hors App Store : stratégie pilote custom séparée, URL publique de test, callbacks, secrets et workflow d'installation directe documentés.
- **77** ✅ Installer l'app sur la boutique réelle et valider OAuth, sessions, webhooks et garde-fous d'environnement.
- **78** ✅ Mettre le pilote en mode lecture seule / dry-run strict pour éviter tout changement marchand involontaire.
- **79** ✅ Exécuter les parcours clés dans les vraies conditions métier.
- **80** ✅ Collecter les retours d'usage et les bugs terrain.
- **81** ✅ Corriger la vague prioritaire issue du pilote.
- **82** ✅ Mesurer la qualité réelle : valeur des suggestions, coûts, jobs, confiance marchande.
- **83-103** Porter les fonctionnalités scripts CLI restantes dans l'app Shopify embedded.
- **104** Décider le go/no-go App Store public.
- **105** Finaliser et soumettre l'app au Shopify App Store.

## ⏳ Actions manuelles en attente

### Admin Shopify
- [ ] Re-crawler (`python -m scripts.audit.crawl_shopify`) + relancer `add_schema --apply` (pour avoir les prix dans le JSON-LD)
- [ ] Ajouter snippet Liquid dans `product.liquid` (avant `</head>`) pour activer le JSON-LD
- [ ] Corriger 6 méta titles trop courts dans l'admin (Bol Félin Raffiné, L'abreuvoir, Griffoir Dimitrios, Distributeur Pet Feeder, La Fontaine Smart, Le Harnais)
- [ ] Écrire titres descriptifs pour 6 collections courtes

### GitHub Actions — secrets alertes email
- [ ] Ajouter `GMAIL_SENDER` (adresse Gmail expéditeur)
- [ ] Ajouter `GMAIL_APP_PASSWORD` (mot de passe d'application Google)
- [ ] Ajouter `ALERT_EMAIL` = adrien.leredde@outlook.com

### Opportunités GSC prioritaires
- [ ] **L'abreuvoir** — pos 11.5, 344 impr → enrichir contenu + méta
- [ ] **Le Tour De Cou Pour Chat** — pos 4.7, 271 impr, CTR 0.4% → réécrire méta title
- [ ] **Le Tour De Cou Pour Chien** — pos 6.1, 210 impr, CTR 0% → réécrire méta

## 📋 Historique des sessions

### Session 2026-05-12 (Vague 5 — App Store UI)

**Mission** : compléter l'expérience Remix avant la tâche 75, pour que l'app montre clairement le workflow marchand App Store au lieu d'un simple dashboard technique.

**UI Remix ajoutée** :
- Navigation App Bridge enrichie : Review IA, Niche, Onboarding, Jobs, Billing, Settings, Privacy.
- `app.review` : revue des suggestions LLM, qualité, approbation/rejet, auto-approve opt-in, lancement apply en dry-run uniquement.
- `app.niche` : clusters produits, keyword gaps, intents GSC et signaux légers Google Suggest.
- `app.onboarding` : checklist installation/backend/crawl/billing/GSC/GA4/permissions + lancement audit asynchrone.
- `app.settings` : santé backend, installation Shopify, snapshot, budget LLM, locales multilingues.
- `app.privacy` : lien policy + résumé export GDPR marchand.
- i18n minimal FR/EN sans nouvelle dépendance.

**Cadrage niche** :
- `pet_accessories_fr` marqué `production`.
- `cosmetics_fr`, `mode_fr`, `jardinage_fr` marqués `template-demo` avec note de périmètre, pour éviter toute promesse excessive App Store.

**Vérifications** :
- `cd shopify-app && npm run typecheck` : OK
- `cd shopify-app && npm run build` : OK
- `ruff format --check .` : OK
- `ruff check .` : clean
- `pytest` : **1033 passed**

**Reste avant tâche 75** :
- Validation manuelle Shopify Partner : URLs publiques/tunnel, captures App Store, privacy/billing/GDPR côté Partner Dashboard.
- Test navigateur embedded réel à faire avec `shopify app dev` et une boutique de test connectée.

### Session 2026-05-12 (Tâche 75 — testabilité App Store et handoff Partner)

**Mission** : rendre l'app réellement testable dans le dev store et clôturer le livrable de préparation App Store côté repo.

**Corrections de testabilité** :
- `shopify.web.toml` ajouté pour lancer Remix derrière `shopify app dev`.
- `shopify.app.local.toml` ajouté pour une preview localhost sans subscriptions webhook incompatibles.
- `auth.$.tsx` ajouté pour la route `/auth/session-token` de la stratégie embedded Shopify.
- `shopify.server.ts` utilise un session storage mémoire officiel en local si `DATABASE_URL` manque.
- `shopify.server.ts` n'enregistre plus les webhooks pendant les previews `localhost`.

**Documentation / clôture** :
- `docs/app-store-submission-checklist.md` documente le test réel en dev store et les tâches restantes dans le Partner Dashboard.
- `ROADMAP.md` clôt la tâche 75 côté repo.

**Vérifications** :
- `cd shopify-app && npm run typecheck` : OK
- `cd shopify-app && npm run build` : OK

### Session 2026-05-12 (replanification post-75 — pilote réel avant App Store)

**Décision produit** : ne pas publier immédiatement au Shopify App Store. Priorité donnée à un pilote réel sur la boutique `leoniedelacroix.com`, afin d'ajuster l'app sur des retours marchands concrets avant la publication publique.

**Roadmap ajoutée** :
- Phase 9 initiale ajoutée, puis réorganisée depuis en Phase 9 tâches **76 à 82**, Phase 10 tâches **83 à 103**, Phase 11 tâches **104 à 105**.
- Prochaine tâche ordonnée : **76**.
- Publication publique App Store repoussée à la tâche **105**, après le pilote, les retours, les corrections prioritaires et la parité scripts CLI → app Shopify.

### Session 2026-05-12 (Tâche 76 — préparation pilote marchand réel)

**Mission** : préparer le cadre repo et opératoire pour tester Léonie SEO sur la vraie boutique Shopify avant toute soumission publique App Store.

**Livrables** :
- `docs/pilot-real-store-setup.md` ajouté : architecture cible, app pilote custom séparée, lien d'installation direct, config `pilot`, secrets et checklist de readiness.
- `DECISIONS.md` enrichi : le pilote réel utilise une app Shopify distincte de la future app publique.
- `.env.example` et `shopify-app/.env.example` clarifiés pour une URL HTTPS publique stable, sessions persistantes et backend public/pilot.
- `README.md` et `docs/app-store-submission-checklist.md` alignés sur la nouvelle séquence Phase 9 avant publication App Store.
- `shopify-app/shopify.app.pilot.toml` est désormais versionné pour figer l'identité et les URLs du pilote réel.

**État à la sortie** :
- Tâche **76** terminée côté repo.
- Actions Shopify Partner encore manuelles avant **77** : créer l'app pilote custom, générer le lien d'installation ciblé sur `287c4a-bb.myshopify.com`, configurer l'URL publique réelle et déployer la config `pilot`.

### Session 2026-05-12 (audit closure Wave 3 & 4)

**Mission** : re-scanner `AUDIT_CODE.md` et `AUDIT_INFRA.md`, fermer les findings encore ouverts sur l'hygiène code, le cleanup legacy et les tests utiles avant la tâche 75.

**Vague 3 — hygiène code** :
- Remplacé les derniers `except Exception`, `datetime.utcnow()` et `asyncio.get_event_loop()` dans `app/`, `scripts/` et `tests/`.
- Ajouté des APIs publiques pour éviter les accès privés utiles (`LLMRouter.providers`, `CCIndexClient.current_crawl`, `classify_intent`).
- Durci les logs structurés : whitelist de champs `extra=` et test anti-fuite de secrets/tokens.
- `compute_cost()` log désormais un warning explicite pour les modèles LLM inconnus au lieu de sous-estimer silencieusement.

**Vague 4 — cleanup legacy** :
- `Dockerfile` ne build plus le dashboard React legacy.
- `frontend/` suivi par Git supprimé ; `.gitignore` ignore désormais le dossier legacy local complet.
- `app/api/apply.py` n'appelle plus `scripts/apply/update_meta.py` ; il utilise `app/apply/ShopifyWriter`.
- `app/api/plans.py` n'importe plus `scripts/license.py` ; validation self-hosted déplacée dans `app/billing/self_hosted_license.py`.
- Ajout de `app/tenant_config.py` pour les besoins app-layer brand/tenant, sans importer `scripts/_config.py`.
- Ajout de `scripts/README.md` pour clarifier les modules canoniques, legacy et transitoires.

**Tests ajoutés / renforcés** :
- Cross-shop mismatch sur endpoints `apply` et `audit`.
- Test route + vrai token store OAuth chiffré.
- Tests observabilité logging/costs.
- Tests signaux alignés sur erreurs réalistes (`requests.ConnectionError`, `RuntimeError`, `ImportError` non bloquant).

**Vérifications** :
- `pytest` : **1033 passed**
- `ruff check .` : clean
- Re-scan : aucun `except Exception`, `datetime.utcnow`, `asyncio.get_event_loop`, ni build Docker `frontend`.

**Reste avant tâche 75** :
- `app/api/audit.py -> scripts/audit + scripts/report` reste un pont transitoire assumé car `scripts/` est encore le moteur d'audit canonique.
- Tâche 75 toujours ⏳ : soumission App Store finale + checklist Partner.

### Session 2026-05-12 (audit complet + corrections Wave 1 & 2)

**Mission** : auditer chaque .md et chaque ligne de code, corriger en TDD les écarts vs l'objectif final (Shopify App Store SEO niche-first multi-tenant).

**Audits livrés** (read-only) :
- `AUDIT_DOCS.md` — 11 dérives doc + 4 contradictions internes
- `AUDIT_CODE.md` — 17 bugs critiques + 30+ secondaires sur 12 654 LOC `app/`
- `AUDIT_INFRA.md` — `scripts/`, `shopify-app/`, `tests/`, `frontend/`, `config/`

**Corrections D1-D3** (commit `cf2cf74`) : `CONTEXT.md` réécrit (accessoires premium vs petfood), guides utilisateurs ne pointent plus sur `frontend/` mort, plans repositionnent HMAC vs Shopify Billing.

**Vague 1 — 9 commits TDD bloquants App Store** :
- `24421e1` retrait email perso `send_alerts.py:216`
- `dbe745b` `TenantConfig` étendu (locale, ga4_property_id, gsc_property, currency)
- `7caed40` colonne `shop` sur `seo_changes` + `snapshots` + migration + isolation impact
- `f429388` auth sur `GET /api/shops` et `/api/jobs/*`
- `93ed3c7` `/billing/confirm` vérifie HMAC + charge_id + re-query Shopify
- `a518207` LLM router par-shop (plus de cache global cross-tenant)
- `eb83e99` brand-lock retiré de `batch.py` + `multilingual.py` (dynamique via tenant config)
- `24645aa` privacy + FAQ dual-mode (`LEONIE_MODE=app_store|self_hosted`)
- `348d34e` Remix `entry.server.tsx` appelle `addDocumentResponseHeaders` (CSP frame-ancestors)

**Vague 2 — 7 commits TDD bugs comportementaux** :
- `343008f` fuite multi-tenant `_load_snapshot/_load_gsc` (`api/niche.py`) + tuple `except` invalide
- `cf306cc` E5 prefix bug (`encode_texts` requiert `mode="query"|"passage"`) + thread-safety
- `a8ab42e` Cloudflare token tracking (estimation char-based + check `success=false`)
- `fc94a99` GA4 `run_report_async` (httpx.AsyncClient) + cache credentials
- `6816717` `ShopifyWriter` read-before-write, `old_value` persisté dans `seo_changes`
- `cdafc46` anti-hallucination `review.py` : keyword overlap + brand presence + suspicious claims
- `6fb6e1e` `niche/engine.py` câble enfin `intent.py` (intent_clusters) + `ner.py` (entity_summary)

**Tests** : 960 → 1028 (+68 nouveaux tests TDD), ruff clean, TypeScript clean (Remix).

**Bilan** : 30 bugs résolus depuis l'audit (17 Wave 1 + 7 Wave 2 + 6 doc D1-D3 + bonus fuite multi-tenant `api/niche.py`). Les Vagues 3, 4 et 5 ont ensuite fermé l'hygiène code, le cleanup legacy et l'UI Remix App Store. Reste : tâche 75 (soumission).

### Session 2026-05-08 (Tâche 44 — packaging)
- `scripts/cli.py` : agrégateur Click — 5 groupes, 26 commandes (setup/license/audit/report/apply)
- `pyproject.toml` : `[project.scripts]` → `leonie-seo = "scripts.cli:cli"` + description/classifiers
- `Dockerfile` : Python 3.11-slim, `VOLUME ["/app/data", "/app/reports", "/app/config/tenants"]`
- `install.sh` : bootstrap une commande — check Python 3.11+, venv, `pip install -e .[dev]`, .env
- `tests/test_cli.py` : 39 smoke tests (--help sur tous les groupes et sous-commandes)
- **428/428 tests verts** · ruff clean

### Session 2026-05-08 (Tâche 43 — licences API key)
- `scripts/license.py` : `issue_key`, `decode_key`, `validate_key`, `require_valid_license` + CLI `issue`/`check`
- Clé signée HMAC-SHA256, format `LEO-<base64(tenant_id+expiry+sig)>`, sans dépendance externe
- Intégration dans `crawl_shopify.py`, `update_meta.py`, `generate_report.py` — check non-bloquant si clé absente
- `scripts/setup.py cmd check` affiche désormais le statut de licence
- `.env.example` mis à jour avec `LICENSE_SECRET` et `LEONIE_API_KEY`
- `tests/test_license.py` : 24 tests
- **389/389 tests verts** · ruff clean

### Session 2026-05-08 (Tâche 42 — bibliothèque niches)
- `scripts/_config.py` : modèles Pydantic `NicheConfig` + `load_niche()` lru_cache + `reset_config_cache()` étendu aux deux caches
- `config/niches/pet_accessories_fr.yaml` : signals (premium × 43, eeat × 23, longtail × 30, category × 5), EEAT dimensions × 4, 21 FAQ Q/R, 5 blog templates
- 3 nouveaux secteurs : `cosmetics_fr.yaml`, `mode_fr.yaml`, `jardinage_fr.yaml`
- 4 scripts migrés (constantes Python → YAML) : `analyze_semantics.py`, `score_eeat.py`, `generate_faq.py`, `generate_blog_briefs.py`
- `tests/test_niche_config.py` : 23 tests
- **365/365 tests verts** · ruff clean

### Session 2026-05-08 (Tâche 40 — multi-tenant)
- `scripts/_config.py` : TenantConfig Pydantic v1, lru_cache, `get_config(tenant_id)`
- `config/tenants/leoniedelacroix.yaml` : YAML complet (brand, product_categories, hreflang, seo_rules, alert_thresholds)
- Migration complète des 16 scripts : `--tenant` CLI sur tous, domaine/brand/thresholds depuis config
- Fix `seo_rules.title_min_chars = 50` (était 30) pour matcher les contraintes generate_suggestions
- **319/319 tests verts** · ruff clean

### Session 2026-05-08 (Phase 2 tâche 29 + Phase 3 complète)
- Fix pipeline CI GitHub Actions (requirements.txt, ruff PATH, pagespeed timeout, permissions)
- Tâche 29 : send_alerts.py (15 tests)
- Tâches 30–39 : Phase 3 complète — 156 nouveaux tests
- **303/303 tests verts** · ruff clean · toutes les tâches Phase 3 commitées et poussées

### Session 2026-05-06 (Phase 2 tâches 25–28)
- Tâche 25 : detect_gsc_opportunities.py (20 tests)
- Tâche 26 : analyze_longtail.py (15 tests)
- Tâche 27 : generate_delta_report.py (11 tests)
- Tâche 28 : weekly_audit.yml pipeline complet

### Session 2026-05-05 → 2026-05-06 (Phase 2 tâches 16–24)
- Instructions agent réorganisées
- Tâches 16, 22, 23, 24 (37 tests)

### Session 2026-05-05 (Phase 1 + tâches 17–21)
- Phase 1 complète : 14 fichiers, 49 tests
- 26 méta + 17 alt texts poussés sur Shopify
- GSC connecté : 50 URLs · 3 736 impressions

### Sessions précédentes
- 2026-04-28 : Setup Google Cloud OAuth
- 2026-04-22 : Custom App Shopify
- 2026-04-20 : Initialisation projet
