# ROADMAP — SEO Leoniedelacroix.com
> Mise à jour à chaque tâche complétée. Statuts : ✅ Fait · 🔄 En cours · ⏳ À faire · ↪ Supersédée

## PHASE 1 — Fondations & Audit (Semaine 1-2)
*Objectif : premier rapport d'audit fonctionnel sur leoniedelacroix.com*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 1 | Structure repo + `.env` + `.gitignore` + instructions agent (`AGENTS.md`, ex-`CLAUDE.md`) | 🟢 | ✅ | 2026-04-20 |
| 2 | Connexion Shopify Admin API GraphQL — lister tous les produits | 🟢 | ✅ | 2026-05-05 |
| 3 | Connexion Google Search Console API — export 90 jours | 🟡 | ✅ | 2026-05-05 |
| 4 | Connexion PageSpeed Insights API — score mobile/desktop par URL | 🟢 | ✅ | 2026-05-05 |
| 5 | Parser l'export CSV Screaming Frog | 🟢 | ✅ | 2026-05-05 |
| 6 | Détecteur : meta titles manquants / trop longs / trop courts | 🟢 | ✅ | 2026-05-05 |
| 7 | Détecteur : meta descriptions manquantes / dupliquées | 🟢 | ✅ | 2026-05-05 |
| 8 | Détecteur : images sans alt text | 🟢 | ✅ | 2026-05-05 |
| 9 | Détecteur : duplicate content `/collections/*/products/*` | 🟡 | ✅ | 2026-05-05 |
| 10 | Détecteur : redirections en chaîne + pages 404 | 🟡 | ✅ | 2026-05-05 |
| 11 | Calcul du score SEO global 0-100 pondéré par impact | 🟡 | ✅ | 2026-05-05 |
| 12 | Génération rapport Markdown horodaté dans `/reports/` | 🟢 | ✅ | 2026-05-05 |
| 13 | Initialisation base SQLite — état initial du site | 🟢 | ✅ | 2026-05-05 |
| 14 | Script `update_meta.py` avec `--dry-run` par défaut | 🟡 | ✅ | 2026-05-05 |
| 15 | Premier commit propre + README avec instructions d'usage | 🟢 | ✅ | 2026-05-05 |

---

## PHASE 2 — Recommandations & Application supervisée (Semaine 3-6)
*Objectif : corriger automatiquement les issues détectées, avec validation humaine*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 16 | Matrice ICE — priorisation issues par Impact/Coût/Effort | 🟡 | ✅ | 2026-05-05 |
| 17 | Générateur de meta titles optimisés par produit | 🟡 | ✅ | 2026-05-05 |
| 18 | Générateur de meta descriptions optimisées par produit | 🟡 | ✅ | 2026-05-05 |
| 19 | Générateur d'alt text intelligent basé sur nom produit + contexte | 🟡 | ✅ | 2026-05-05 |
| 20 | Script `update_meta.py --apply` — push meta vers Shopify (26 items) | 🟡 | ✅ | 2026-05-05 |
| 21 | Script `update_alt_text.py --apply` — push alt text vers Shopify (17 images) | 🟡 | ✅ | 2026-05-05 |
| 22 | Script `create_redirects.py` — import 301 en bulk depuis CSV validé | 🟡 | ✅ | 2026-05-05 |
| 23 | Structured data JSON-LD `Product` + `AggregateRating` via metafields | 🔴 | ✅ | 2026-05-05 |
| 24 | Système de rollback SQLite — logging ✅, commande CLI rollback manquante | 🔴 | ✅ | 2026-05-05 |
| 25 | Détecteur d'opportunités GSC — requêtes positions 11-20 à optimiser | 🟡 | ✅ | 2026-05-06 |
| 26 | Analyse concurrentielle longue traîne — requêtes niche petfood FR | 🔴 | ✅ | 2026-05-06 |
| 27 | Rapport comparaison avant/après par page (delta score SEO) | 🟡 | ✅ | 2026-05-06 |
| 28 | GitHub Actions cron hebdomadaire — audit auto + commit rapport | 🔴 | ✅ | 2026-05-06 |
| 29 | Alertes email — régression CWV, nouveaux 404, chute de position | 🔴 | ✅ | 2026-05-08 |

---

## PHASE 3 — Contenu SEO & Intelligence niche (Mois 2-4)
*Objectif : produire du contenu SEO contextualisé pour la niche petfood FR*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 30 | Générateur de briefs articles blog (H1/H2, mots-clés, angle E-E-A-T) | 🟡 | ✅ | 2026-05-08 |
| 31 | Réécriture descriptions produits longue traîne — ton premium petfood FR | 🔴 | ✅ | 2026-05-08 |
| 32 | Maillage interne automatique — détection opportunités liens blog → produits | 🔴 | ✅ | 2026-05-08 |
| 33 | Analyse sémantique fiches produits vs concurrents (Zooplus, Wanimo) | 🔴 | ✅ | 2026-05-08 |
| 34 | Générateur de FAQ structurée par catégorie produit | 🟡 | ✅ | 2026-05-08 |
| 35 | Détecteur de cannibalisation — pages en compétition sur un même mot-clé | 🔴 | ✅ | 2026-05-08 |
| 36 | Score E-E-A-T par page — auteur, sources, date, expertise vétérinaire | 🔴 | ✅ | 2026-05-08 |
| 37 | Générateur balises hreflang si extension BE/CH francophone | 🟡 | ✅ | 2026-05-08 |
| 38 | Rapport mensuel synthétique PDF — trafic, conversions, gains cumulés | 🟡 | ✅ | 2026-05-08 |
| 39 | Dashboard CLI interactif `rich` — vue temps réel santé SEO du site | 🟡 | ✅ | 2026-05-08 |

---

## PHASE 4 — Productisation & Monétisation (Mois 6)
*Objectif : transformer l'outil en produit vendable à d'autres boutiques Shopify*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 40 | Abstraction multi-boutiques — config par tenant dans YAML | 🔴 | ✅ | 2026-05-08 |
| 41 | Interface CLI universelle — sélecteur de secteur/niche au démarrage | 🟡 | ✅ | 2026-05-08 |
| 42 | Bibliothèque de règles métier par secteur (cosmétique, bébé, jardinage…) | 🔴 | ✅ | 2026-05-08 |
| 43 | Système de licences API key — authentification par boutique cliente | 🔴 | ✅ | 2026-05-08 |
| 44 | Packaging PyPI ou Docker — installation en une commande | 🔴 | ✅ | 2026-05-08 |

---

## PHASE 5 — App Shopify publique (Mois 12)
*Objectif : produit SaaS scalable sur le Shopify App Store*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 45 | OAuth Shopify — authentification marchands via App Store | 🔴 | ✅ | 2026-05-09 |
| 46 | Backend FastAPI — API REST entre l'app et le moteur Python | 🔴 | ✅ | 2026-05-09 |
| 47 | Frontend dashboard React — version UI du CLI | 🔴 | ✅ | 2026-05-09 |
| 48 | Système de pricing par plan (Free/Pro/Agency) | 🔴 | ✅ | 2026-05-10 |
| 49 | Soumission et validation Shopify App Store | 🔴 | ↪ Supersédée par tâche 75 | |
| 50 | Support + documentation utilisateur multilingue | 🟡 | ✅ | 2026-05-10 |

---

## PHASE 6 — Conformité App Store & Infrastructure async (Mois 13-14)
*Objectif : lever les 3 blockers critiques (GDPR, Billing, App Bridge) ET poser l'infrastructure async*
*Budget cible : ≤ 12 €/mois en ressources externes*
*Note : la tâche 55 (async queue) est un prérequis pour les jobs LLM de Phase 7*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 51 | GDPR mandatory webhooks — `customers/data_request`, `customers/redact`, `shop/redact` | 🔴 | ✅ | 2026-05-10 |
| 52 | Shopify Billing API — `appSubscriptionCreate` / `appSubscriptionCancel` (remplace HMAC license) | 🔴 | ✅ | 2026-05-10 |
| 53 | Privacy policy page + GDPR data export endpoint (`GET /api/gdpr/export`) | 🟡 | ✅ | 2026-05-10 |
| 54 | SQLite → Neon Postgres — migration multi-tenant (pools, connexions async) | 🔴 | ✅ | 2026-05-10 |
| 55 | Async job queue — Postgres-backed background jobs (audits, LLM batch, retry, rate-limit Shopify) | 🔴 | ✅ | 2026-05-10 |
| 56 | Scaffold Shopify App Remix — `shopify app create`, App Bridge v4 + Polaris + OAuth + sessions multi-tenant | 🔴 | ✅ | 2026-05-10 |
| 57 | Intégration Remix ↔ Python backend — proxy HTTP, auth partagée, Neon Postgres commun, décommission frontend/ | 🔴 | ✅ | 2026-05-10 |

---

## PHASE 7 — Moteur IA & Intelligence niche (Mois 15-17)
*Objectif : générations LLM utiles (pas vagues), Niche Intelligence concrète, observabilité dès le départ*
*Principe : prompts déterministes + validation humaine + fallbacks + coût LLM maîtrisé*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 58 | LLM provider abstraction — GPT-4o mini (primary) + Cloudflare Workers AI + Groq (fallbacks gratuits) | 🔴 | ✅ | 2026-05-11 |
| 59 | Templates de prompts externalisés en YAML (`config/prompts/`) — meta, alt, description, brief | 🟡 | ✅ | 2026-05-11 |
| 60 | Batch generation meta titles + descriptions via LLM — 100 produits en < 60 s via queue (tâche 55) | 🔴 | ✅ | 2026-05-11 |
| 61 | Validation + review mode — diff LLM vs Shopify actuel, approbation par batch, auto-approve opt-in | 🟡 | ✅ | 2026-05-11 |
| 62 | Niche Intelligence engine — détection clusters produits réels, saturation SERP, keyword gaps vs concurrents | 🔴 | ✅ | 2026-05-11 |
| 63 | Niche signals légers — Google Suggest + pytrends + Reddit (base de données keywords, valide avant Common Crawl) | 🟡 | ✅ | 2026-05-11 |
| 64 | Semantic clustering GSC — sentence-transformers + UMAP, regroupement requêtes par intent | 🔴 | ✅ | 2026-05-11 |
| 65 | Génération briefs pages/collections + articles blog via LLM (niche-aware, templates 59) | 🟡 | ✅ | 2026-05-11 |
| 66 | Bulk apply orchestrator — utilise queue 55, rate-limit Shopify, retry exponentiel, progress UI | 🟡 | ✅ | 2026-05-11 |
| 67 | spaCy NER — extraction entités produit (matières, certifications, origines) pour enrichissement contextuel | 🔴 | ✅ | 2026-05-11 |
| 68 | Observabilité — logs structurés JSON, métriques par tenant, coût LLM par requête, alertes seuil budget | 🟡 | ✅ | 2026-05-11 |

---

## PHASE 8 — Scale, Contenu & App Store final (Mois 18-24)
*Objectif : injection de contenu propre via Theme Extension, suivi ROI réel, multilinguisme IA, soumission finale*
*Common Crawl déféré ici : sources légères (tâche 63) d'abord, Web Graph seulement si gap avéré*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 69 | Theme App Extension — injection JSON-LD sans modifier `theme.liquid` (Shopify CLI, sandbox thème) | 🔴 | ✅ | 2026-05-11 |
| 70 | Semantic embeddings store — pgvector (Neon) pour similarité produit / requête GSC | 🔴 | ✅ | 2026-05-11 |
| 71 | Impact dashboard — vue ROI (clics gagnés × taux conv × panier moyen) par URL modifiée | 🟡 | ✅ | 2026-05-11 |
| 72 | Multilinguisme IA — génération meta EN/DE/NL via LLM pour expansion marché | 🟡 | ✅ | 2026-05-11 |
| 73 | GA4 Data API — corrélation trafic organique × conversions × recettes par tenant | 🔴 | ✅ | 2026-05-11 |
| 74 | Common Crawl / Web Graph — backlinks, graph liens concurrents, mentions marque non-linkées (après validation tâche 63) | 🔴 | ✅ | 2026-05-12 |
| 75 | Soumission App Store finale — après GDPR + Billing + App Bridge validés (tâches 51-57) | 🔴 | ✅ | 2026-05-12 |

> Préparation tâche 75 — 2026-05-12 : audit closure Vagues 3-5 terminé
> (`except Exception`, `datetime.utcnow`, `asyncio.get_event_loop`, cleanup `frontend/`,
> Dockerfile, tests cross-shop/token-store/observability, UI Remix App Store,
> i18n FR/EN, niches secondaires `template-demo`). Vérification :
> `pytest` 1033/1033 ✅, `ruff check .` ✅, `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 75 — 2026-05-12 : configuration locale de preview Shopify stabilisée
> (`shopify.app.local.toml`, `shopify.web.toml`, auth catch-all, fallback session storage,
> skip webhooks en localhost), checklist App Store documentée dans
> `docs/app-store-submission-checklist.md`. Le restant est manuel côté Partner Dashboard
> et nécessite une URL publique capable de recevoir les callbacks Shopify.

---

## PHASE 9 — Pilote marchand réel avant App Store
*Objectif : tester Léonie SEO sur la vraie boutique Shopify `leoniedelacroix.com`, récolter des retours terrain, adapter le produit, puis seulement lancer la publication App Store.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 76 | Préparer l'environnement pilote hors App Store — app non listée / install directe sur la boutique réelle, URLs publiques de test, secrets et callbacks actifs | 🔴 | ✅ | 2026-05-12 |
| 77 | Installer Léonie SEO sur la boutique Shopify réelle et valider OAuth, sessions persistantes, Billing désactivé ou mode test, webhooks GDPR/app uninstall | 🔴 | ✅ | 2026-05-15 |
| 78 | Activer un mode **pilot-safe** : analyses en lecture seule + dry-run obligatoire + confirmations explicites avant toute écriture Shopify | 🔴 | ✅ | 2026-05-15 |
| 79 | Tester les parcours métier réels sur `leoniedelacroix.com` — onboarding, audit, review IA, niche intelligence, jobs, privacy, billing/settings | 🔴 | ✅ | 2026-05-16 |
| 80 | Capturer les retours d'usage, bugs, incompréhensions UX, frictions de confiance et écarts entre promesse produit et réalité marchande | 🟡 | ✅ | 2026-05-16 |
| 81 | Corriger la vague pilote prioritaire — fiabilité, wording, états vides, feedbacks UX, garde-fous mutations, temps de réponse | 🔴 | ✅ | 2026-05-16 |
| 82 | Mesurer le pilote — qualité des recommandations, taux d'approbation, coûts LLM, stabilité des jobs, signaux SEO utiles | 🟡 | ✅ | 2026-05-16 |

> Clôture tâche 76 — 2026-05-12 : stratégie pilote séparée documentée
> (`docs/pilot-real-store-setup.md`), décision enregistrée dans `DECISIONS.md`,
> exemples d'environnement alignés sur une URL HTTPS publique et sessions persistantes,
> config locale `shopify.app.pilot.toml` prévue via `shopify app config link --config pilot`.
> La création de l'app pilote custom et la génération du lien d'installation restent
> des actions Shopify Partner manuelles à exécuter avant la tâche 77.
>
> Clôture tâche 77 — 2026-05-15 : app pilote installée sur la boutique réelle,
> OAuth embedded validé, sessions et appels internes Remix → Python validés,
> Billing désactivable par environnement, webhooks/GDPR présents, jobs audit/IA/apply
> visibles et scopés au shop, snapshot Shopify réel persistant fichier + DB,
> récupération des jobs `running` obsolètes, génération IA et prévisualisation
> dry-run vérifiées. Vérification locale : `ruff check .` ✅, `pytest`
> **1050 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 78 — 2026-05-15 : ajout d'un garde-fou central
> `LEONIE_PILOT_SAFE_MODE=true` qui bloque toute écriture live Shopify pendant
> le pilote, y compris les jobs `bulk_apply` et les mutations Billing. Hors mode
> pilot-safe, les écritures live exigent `confirm_live_write=true`; les dry-runs
> et lectures Shopify restent autorisés. Le Blueprint Render pilote active ce mode.
> Vérification locale : `ruff check .` ✅, `pytest` **1060 passed** ✅,
> `npm run typecheck` ✅, `npm run build` ✅.
>
> Démarrage tâche 79 — 2026-05-15 : ajout du plan de test réel
> `docs/pilot-real-store-test-plan.md` et du journal
> `docs/pilot-real-store-test-log.md`. Smoke checks publics réussis :
> web `/healthz` → `ok`, API `/health` → `status=ok` sans variable manquante,
> privacy GET → HTTP 200. Les parcours embedded Shopify Admin restent à
> exécuter avec une session marchand connectée.
>
> Clôture tâche 79 — 2026-05-16 : parcours embedded Shopify Admin validé
> sur la boutique réelle. Installation/session, navigation, Settings pilot-safe,
> audit, crawl produits/collections, niche clusters, génération de suggestions,
> approbation/rejet, dry-run preview, Billing bloqué et Privacy sont passés.
> Aucun bug bloquant signalé ; seul le libellé exact du mode pilot-safe dans
> Settings est à considérer comme retour UX pour la tâche 80. Décision : pass.
>
> Clôture tâche 80 — 2026-05-16 : retours pilote consolidés dans
> `docs/pilot-real-store-feedback.md`. Aucun bug bloquant ou friction majeure
> n'a été signalé. Une correction candidate est retenue pour la tâche 81 :
> rendre le libellé Settings `Mode pilot-safe actif` plus explicite et stable.
> Les IDs/counts manquants dans le journal sont classés comme amélioration de
> preuve de test, pas comme bug produit. Les manques GSC/GA4/PageSpeed restent
> volontairement différés en Phase 10.
>
> Clôture tâche 81 — 2026-05-16 : vague pilote prioritaire limitée au retour
> UX confirmé. La carte Settings affiche désormais `Mode pilot-safe actif`,
> un badge `Écritures live bloquées`, et une ligne indiquant que les dry-runs
> restent autorisés mais qu'aucune écriture Shopify live ne peut partir.
> Vérification : `npm run typecheck` ✅ et `npm run build` ✅ dans `shopify-app/`.
>
> Clôture tâche 82 — 2026-05-16 : mesure pilote consolidée dans
> `docs/pilot-real-store-measurement.md`. Décision : pass avec lacunes de
> mesure. Le pilote valide le workflow coeur, la sécurité dry-run/pilot-safe,
> Billing bloqué, Privacy, Niche clusters, génération IA, review et preview.
> Les valeurs exactes job IDs/durations, compteurs produits/collections,
> taux d'approbation et coût LLM devront être capturés lors du prochain pass,
> mais ne bloquent pas l'entrée en Phase 10.

---

## PHASE 10 — Parité scripts CLI → App Shopify
*Objectif : porter dans l'app embedded les fonctionnalités SEO encore disponibles uniquement dans `scripts/`, avec une UX marchand simple, des jobs async, du dry-run par défaut, et des garde-fous adaptés à l'App Store.*
*Principe : ne pas exposer chaque script tel quel. Transformer chaque capacité en workflow produit : diagnostic clair, prévisualisation, validation humaine, historique, rollback si écriture.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 83 | Connecter Google Search Console dans l'app — OAuth/consentement marchand, import query×page, état de fraîcheur des données et erreurs actionnables | 🔴 | ✅ | 2026-05-16 |
| 84 | Porter les opportunités GSC — positions 11-20, pages à CTR faible, estimation clics gagnables et priorisation par impact | 🟡 | ✅ | 2026-05-16 |
| 85 | Ajouter PageSpeed / Core Web Vitals — job par URL prioritaire, scores mobile/desktop, alertes de régression et recommandations non techniques | 🟡 | ✅ | 2026-05-16 |
| 86 | Ajouter un import crawl technique — upload CSV Screaming Frog ou crawl externe, détection 404, redirects, canonical, duplicates et chaînes de redirection | 🔴 | ✅ | 2026-05-16 |
| 87 | Étendre l'audit UI — afficher toutes les issues `scripts/audit/detect_issues.py` dans l'app avec filtres, gravité, ressource touchée et cause lisible | 🟡 | ✅ | 2026-05-16 |
| 88 | Ajouter la matrice ICE dans l'app — prioriser les corrections par impact, confiance et effort, avec tri marchand exploitable | 🟡 | ✅ | 2026-05-16 |
| 89 | Porter l'analyse longue traîne — comparer catalogue, GSC et requêtes niche pour révéler les manques mots-clés par produit/collection | 🟡 | ✅ | 2026-05-16 |
| 90 | Porter la détection cannibalisation — identifier les pages en compétition sur une même requête et proposer consolidation, canonical ou différenciation | 🔴 | ⏳ | |
| 91 | Ajouter le maillage interne — détecter opportunités blog/collection/produit, générer ancres suggérées et préparer une prévisualisation sans écriture | 🔴 | ⏳ | |
| 92 | Porter l'alt text IA — générer, revoir, approuver/rejeter et appliquer en dry-run les textes alternatifs images, avec limites qualité et accessibilité | 🟡 | ⏳ | |
| 93 | Porter la réécriture descriptions produits — générer descriptions longue traîne, comparer avec l'existant, review humaine et application batch sécurisée | 🔴 | ⏳ | |
| 94 | Ajouter les redirects 301 supervisés — import/proposition, validation collision/handle, dry-run, application explicite et rapport de résultat | 🔴 | ⏳ | |
| 95 | Finaliser le workflow JSON-LD — preview Organization/Product/Collection, activation Theme App Extension, validation schema et statut par ressource | 🟡 | ⏳ | |
| 96 | Ajouter un rollback marchand — historique des écritures Shopify, diff avant/après, revert par job/ressource/date, confirmations fortes | 🔴 | ⏳ | |
| 97 | Porter les rapports exportables — audit Markdown/PDF, delta avant-après, rapport mensuel, téléchargement depuis l'app et stockage par shop | 🟡 | ⏳ | |
| 98 | Ajouter dashboard impact + GA4 en UI complète — funnel organique, conversions, revenus, ROI par URL modifiée et configuration GA4 guidée | 🔴 | ⏳ | |
| 99 | Ajouter analyse sémantique et E-E-A-T — score contenu, entités manquantes, preuves de confiance, recommandations par page | 🟡 | ⏳ | |
| 100 | Ajouter génération FAQ et briefs blog — workflows de contenu niche-aware, review, export, et option d'application future via pages/blog Shopify | 🟡 | ⏳ | |
| 101 | Ajouter hreflang / international SEO — diagnostic marchés/langues, preview tags, garde-fous Markets Shopify et export technique | 🟡 | ⏳ | |
| 102 | Ajouter alertes marchand — email/in-app alerts pour CWV, 404, chute CTR/position, budget LLM et jobs en échec | 🟡 | ⏳ | |
| 103 | Nettoyer les scripts transitoires après parité — documenter ce qui reste CLI-only, supprimer doublons dangereux et figer les modules canoniques app | 🟡 | ⏳ | |

### Détail des objectifs Phase 10

- **83 GSC** : remplacer les imports locaux par une connexion pilotable depuis l'app, car les opportunités SEO deviennent beaucoup plus crédibles quand elles viennent des vraies requêtes marchand.
- **84 Opportunités GSC** : transformer les données GSC en actions simples : quelles pages optimiser maintenant, pourquoi, et quel gain potentiel viser.
- **85 PageSpeed / CWV** : intégrer la santé performance comme signal SEO visible, sans noyer le marchand dans des métriques Lighthouse brutes.
- **86 Crawl technique** : couvrir les problèmes que Shopify GraphQL ne voit pas bien : 404 publiques, canonical, redirects, duplicates réels et URLs orphelines.
- **87 Audit UI complet** : faire de l'app le lieu de lecture principal des problèmes SEO, au lieu de rapports CLI séparés.
- **88 ICE** : aider à décider quoi corriger en premier, surtout quand l'audit produit trop de recommandations.
- **89 Longue traîne** : trouver les requêtes réalistes que la boutique peut gagner à partir du catalogue réel et de la demande observée.
- **90 Cannibalisation** : éviter que plusieurs pages se concurrencent entre elles et diluent les signaux SEO.
- **91 Maillage interne** : transformer les contenus existants en leviers de ranking via liens contextuels contrôlés.
- **92 Alt text** : améliorer SEO image et accessibilité avec le même modèle de confiance que Review IA.
- **93 Descriptions produits** : étendre la valeur IA au contenu visible, avec un niveau de contrôle plus strict que les meta.
- **94 Redirects 301** : porter une fonctionnalité puissante mais risquée uniquement avec validations, dry-run et rollback.
- **95 JSON-LD** : rendre l'injection structurée auditable et activable proprement via extension Shopify, sans toucher `theme.liquid`.
- **96 Rollback** : donner une vraie confiance avant toute écriture réelle Shopify.
- **97 Rapports** : permettre au marchand de garder une trace exportable des audits, progrès et décisions.
- **98 GA4 / ROI** : relier les changements SEO aux sessions, conversions et revenus, pas seulement aux scores techniques.
- **99 Sémantique / E-E-A-T** : enrichir les pages avec les signaux de confiance et de pertinence qui manquent aujourd'hui dans l'UI.
- **100 FAQ / briefs** : convertir la niche intelligence en production de contenu exploitable.
- **101 Hreflang** : préparer l'expansion internationale sans générer de tags dangereux ou incohérents avec Shopify Markets.
- **102 Alertes** : rendre l'app proactive sur les régressions et les coûts.
- **103 Cleanup** : éviter deux sources de vérité entre CLI et app, en gardant les scripts utiles comme moteur ou outils opérateur seulement.

> Clôture tâche 83 — 2026-05-16 : ajout de la connexion Google Search Console
> côté app embedded. Le backend stocke les credentials Google OAuth chiffrés par
> shop (`google_tokens`), génère une URL de consentement signée, gère le callback
> Google, expose un statut GSC avec fraîcheur du dernier import, et lance un job
> `gsc_import` qui écrit les exports shop-scopés `gsc_performance.csv`,
> `gsc_query_page.csv` et `gsc_*.json` consommables par Niche Intelligence.
> L'Onboarding Shopify affiche maintenant l'état GSC, le lien de consentement
> et l'action `Importer 90 jours`. Configuration pilote documentée via
> `GOOGLE_OAUTH_CLIENT_CONFIG`, `GOOGLE_OAUTH_REDIRECT_URI` et
> `GOOGLE_OAUTH_STATE_SECRET`. Vérification : `ruff check .` ✅,
> `pytest` **1075 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 84 — 2026-05-16 : ajout de l'endpoint
> `GET /api/shops/{shop}/gsc/opportunities`, réutilisant la logique CLI
> `detect_gsc_opportunities` pour transformer les imports GSC en quick wins
> positions 11-20, pages à CTR faible, opportunités long terme, gains de clics
> estimés et priorisation par impact. La page Niche Shopify affiche désormais
> une carte `Opportunités GSC` avec résumé, gain estimé et tableau des pages à
> optimiser, ainsi qu'un état vide quand GSC n'est pas encore connecté/importé.
> Vérification : `ruff check .` ✅, `pytest` **1077 passed** ✅,
> `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 85 — 2026-05-16 : ajout du workflow PageSpeed / Core Web
> Vitals côté app embedded. Le backend expose `GET /api/shops/{shop}/pagespeed/status`
> et `POST /api/shops/{shop}/pagespeed/import`, lance le job async
> `pagespeed_import`, sélectionne des URLs prioritaires par shop, écrit les
> exports `pagespeed.csv` et `pagespeed_*.csv`, calcule les moyennes mobile /
> desktop, les alertes CWV, les régressions de score et des recommandations
> non techniques. L'Onboarding Shopify affiche l'état PageSpeed, le bouton
> `Analyser les URLs prioritaires`, les scores et les alertes principales ;
> Jobs SEO résume aussi les imports PageSpeed. Vérification : `ruff check .` ✅,
> `pytest` **1084 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅.

---

## PHASE 11 — Différenciation GEO : AI Search Readiness & Revenue-Aware Shopify Intelligence
*Objectif : transformer Léonie SEO en assistant GEO Shopify-native capable d'identifier quelles pages, produits et collections sont les plus importants à optimiser pour Google, ChatGPT, Perplexity, Gemini et les moteurs IA, en priorisant selon la complétude factuelle, le potentiel business, le risque SEO, le stock, la marge et la preuve d'impact.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 106 | GEO Product Facts Layer — structurer les faits produits fiables utiles aux IA, JSON-LD, FAQ, descriptions, snippets et recommandations ; détecter faits confirmés/manquants, suggestions à vérifier et score de complétude factuelle | 🔴 | ✅ | 2026-05-18 |
| 107 | AI Search Readiness Score — calculer un score GEO par produit, collection et boutique à partir des faits produits, schema, FAQ, requêtes conversationnelles, preuves de confiance, maillage, stock, performance et crawlabilité | 🔴 | ✅ | 2026-05-18 |
| 108 | Revenue-Aware GEO Prioritization — croiser GSC, GA4, Shopify, stock, marge, conversion, panier moyen, score GEO, risque et effort pour prioriser les actions les plus utiles business et AI Search | 🔴 | ✅ | 2026-05-18 |
| 109 | Weekly GEO Action Assistant — agréger score GEO, priorisation revenue-aware, GSC, GA4, PageSpeed, crawl, stock, saisonnalité et ledger pour afficher seulement 3 actions GEO prioritaires par semaine avec gain potentiel, effort, risque et preview | 🟡 | ✅ | 2026-05-18 |
| 110 | GEO Impact Ledger — historiser chaque optimisation GEO avec snapshot avant/après, faits ajoutés, FAQ, JSON-LD, requêtes conversationnelles ciblées, source, utilisateur, job ID, métriques GSC/GA4 avant puis après 7/30/60 jours et impact estimé vs observé | 🔴 | ✅ | 2026-05-18 |
| 111 | GEO Risk Guard — protéger les pages SEO ou business déjà performantes, éviter les sur-optimisations IA, bloquer les écritures automatiques sauf confirmation forte et propager la protection aux workflows contenu, FAQ, JSON-LD, maillage, collections et redirects | 🟡 | ✅ | 2026-05-18 |
| 112 | AI Search Collection Builder — détecter les opportunités de collections Shopify adaptées aux intentions conversationnelles via catalogue, tags, types produits, requêtes GSC, signaux niche, embeddings et stock ; proposer nom, handle, H1, metas, description, FAQ, produits et dry-run avant création | 🔴 | ✅ | 2026-05-18 |
| 113 | FAQ & Answer Block Generator — générer des FAQ et blocs de réponses orientés moteurs IA à partir des faits produits confirmés, avec review humaine, séparation fait confirmé / suggestion à vérifier et option d'application future sur pages produits, collections ou blogs Shopify | 🟡 | ✅ | 2026-05-18 |
| 114 | llms.txt & AI Crawlability Advisor — préparer un fichier de guidage IA listant les pages, collections, politiques et contenus clés de la boutique, recommander les pages à inclure/exclure et auditer la lisibilité IA sans promettre de ranking ou citation garantie | 🟡 | ✅ | 2026-05-18 |
| 115 | AI Answer Competitor Monitor — comparer les concurrents visibles sur les requêtes conversationnelles prioritaires, d'abord via SERP ou import manuel, puis analyser contenus, prix, avis, FAQ, schema, preuves, angle IA et recommander collection, enrichissement produit, FAQ ou maillage sans copier | 🔴 | ✅ | 2026-05-18 |

### Détail des objectifs Phase 11

1. **106 GEO Product Facts Layer**
   - Créer une base de faits produits fiable pour nourrir le GEO sans hallucination.
   - Extraire depuis Shopify : matières, dimensions, poids, compatibilités, usages, entretien, origine, garanties, livraison, retours, certifications, bénéfices, limites, type d'animal, taille recommandée et problème résolu.
   - Output attendu : fiche faits produit, faits confirmés, faits manquants, suggestions à vérifier, score de complétude et recommandations.
   - Garde-fous : ne jamais inventer origine, matière, certification, garantie ou preuve ; séparer explicitement fait confirmé / suggestion marchande à valider.

2. **107 AI Search Readiness Score**
   - Créer un score boutique / collection / produit.
   - Composants : faits produits complets, JSON-LD, FAQ conversationnelle, alignement requêtes longues, preuves de confiance, maillage interne, stock, performance et crawlabilité.
   - Output attendu : score 0-100, sous-scores, raisons lisibles et actions d'amélioration.
   - Garde-fous : présenter le score comme une readiness interne, pas comme une garantie de visibilité dans ChatGPT, Perplexity, Gemini ou Google AI Overviews.

3. **108 Revenue-Aware GEO Prioritization**
   - Classer les actions GEO par impact business probable.
   - Croiser GSC, GA4, Shopify, stock, statut produit, variantes, panier moyen, marge si disponible, score GEO, risque et effort.
   - Output attendu : tableau pages/actions, gain estimé, effort, risque, raison lisible et confiance faible/moyenne/forte.
   - Garde-fous : fallback GSC + Shopify + panier moyen global si GA4 ou marge manque, et aucune estimation présentée comme une promesse.

4. **109 Weekly GEO Action Assistant**
   - Réduire la complexité à 3 décisions GEO actionnables par semaine.
   - Agréger score GEO, priorisation revenue-aware, opportunités GSC, Risk Guard, PageSpeed, crawl, stock, saisonnalité et ledger.
   - Output attendu : carte dashboard avec 3 actions, gain potentiel, effort, risque, preview et raison simple.
   - Garde-fous : ne pas répéter des recommandations faibles, masquer l'incertain et privilégier l'impact business au volume d'erreurs.

5. **110 GEO Impact Ledger**
   - Transformer l'app en système de preuve pour les optimisations GEO.
   - Enregistrer état avant/après, faits produits ajoutés, FAQ, schema JSON-LD, requêtes conversationnelles ciblées, utilisateur, job ID, source de recommandation, métriques GSC/GA4 et mesures après 7/30/60 jours.
   - Output attendu : journal chronologique, impact estimé vs observé, statut positif/neutre/négatif/inconclusif et rollback si possible.
   - Garde-fous : snapshot obligatoire, distinction corrélation/causalité et état “impact non encore mesurable”.

6. **111 GEO Risk Guard**
   - Éviter qu'une optimisation GEO abîme une page qui performe déjà en SEO ou en revenu.
   - Détecter top trafic, CTR supérieur à la moyenne, revenus organiques élevés, conversion élevée, stabilité 30/60/90 jours et pages déjà suffisamment claires pour l'IA.
   - Output attendu : pages protégées, raison, niveau de risque et recommandation.
   - Garde-fous : blocage des modifications automatiques, confirmation forte avant écriture Shopify et protection appliquée aux workflows contenu, FAQ, JSON-LD, maillage, collections et redirects.

7. **112 AI Search Collection Builder**
   - Proposer des collections Shopify pensées pour les intentions conversationnelles, pas seulement pour les mots-clés courts.
   - Utiliser catalogue, tags, types produits, requêtes GSC, signaux niche, embeddings produit/requête et stock.
   - Output attendu : cartes de collections suggérées avec preview nom, handle, H1, metas, description, FAQ, produits inclus, liens internes et estimation d'opportunité.
   - Garde-fous : éviter collections trop pauvres, cannibales ou déjà existantes, et ne jamais publier sans validation.

8. **113 FAQ & Answer Block Generator**
   - Transformer les faits produits en réponses exploitables par les moteurs IA et compréhensibles par les clients.
   - Générer des questions/réponses sur usage, taille, matière, compatibilité, entretien, différence avec alternatives, livraison, retours et garanties.
   - Output attendu : FAQ par produit/collection, blocs de réponse courts, sources factuelles utilisées, preview et review humaine.
   - Garde-fous : ne pas inventer de faits, ne pas surcharger les pages et permettre l'export sans écriture Shopify.

9. **114 llms.txt & AI Crawlability Advisor**
   - Préparer une couche de guidage IA sans vendre de promesse irréaliste.
   - Lister les pages, collections, politiques, guides et contenus clés à rendre facilement découvrables par les moteurs IA.
   - Ajouter recommandations d'inclusion/exclusion et audit de lisibilité.
   - Output attendu : preview `llms.txt`, pages incluses/exclues, raisons et alertes de pages faibles.
   - Garde-fous : présenter `llms.txt` comme un fichier de guidage émergent, pas comme un standard garanti ni un levier de ranking prouvé.

10. **115 AI Answer Competitor Monitor**
   - Comprendre pourquoi des concurrents sont plus recommandables ou visibles sur des requêtes prioritaires.
   - Utiliser suivi limité des requêtes GSC/conversationnelles prioritaires, import manuel ou SERP au départ, classification des pages et comparaison contenu/prix/avis/FAQ/schema/preuves/angle IA.
   - Output attendu : tableau par requête, concurrents visibles, raisons probables et action recommandée.
   - Garde-fous : plafonner les requêtes, éviter le scraping agressif, proposer un import CSV au départ et interdire la copie de contenu.

### Priorité produit recommandée

1. **106 GEO Product Facts Layer** — Socle indispensable : sans faits fiables, le GEO risque de générer du contenu vague ou halluciné.
2. **107 AI Search Readiness Score** — Rend le positionnement GEO visible et compréhensible dans l'UI.
3. **108 Revenue-Aware GEO Prioritization** — Connecte le GEO au business Shopify : revenu, stock, marge, conversion et risque.
4. **109 Weekly GEO Action Assistant** — Transforme la complexité en 3 actions simples par semaine pour marchands non techniques.
5. **110 GEO Impact Ledger** — Prouve l'impact, prépare le rollback et évite les promesses impossibles à démontrer.
6. **111 GEO Risk Guard** — Protège les pages performantes contre les optimisations IA excessives.
7. **112 AI Search Collection Builder** — Très Shopify-native et différenciant pour capter les intentions conversationnelles.
8. **113 FAQ & Answer Block Generator** — Génère des contenus très utiles aux moteurs IA, mais dépend de la qualité du Facts Layer.
9. **114 llms.txt & AI Crawlability Advisor** — Signal GEO intéressant, à présenter prudemment comme guidage IA.
10. **115 AI Answer Competitor Monitor** — Différenciant mais coûteux ; à garder après validation marché ou avec import manuel au départ.

---

## PHASE 11.5 — GEO Impact Validation & Retention Loop
*Objectif : mesurer l'impact réel des optimisations GEO/SEO appliquées, suivre la progression dans le temps, comparer les pages modifiées à des pages témoins et afficher une courbe de progression claire pour prouver la valeur de l'app au marchand pendant la période de validation.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 116 | Optimization Snapshot — enregistrer l'état avant chaque modification : score GEO/SEO, contenu, facts, FAQ, JSON-LD, GSC, GA4, Shopify, stock, prix et statut produit | 🔴 | ✅ | 2026-05-18 |
| 117 | Optimization Event Tracking — créer un événement traçable pour chaque action appliquée avec page, type d'action, date, utilisateur, job ID, score avant/après, hypothèse et statut | 🟡 | ✅ | 2026-05-18 |
| 118 | Control Group Builder — sélectionner des pages témoins similaires non modifiées pour comparer l'évolution des pages optimisées à une baseline crédible | 🔴 | ✅ | 2026-05-18 |
| 119 | Validation Timeline J+7/J+30/J+60/J+90 — planifier automatiquement les fenêtres de mesure et afficher au marchand quand les premiers signaux et conclusions seront disponibles | 🟡 | ✅ | 2026-05-18 |
| 120 | Progress Curve Dashboard — afficher les courbes score GEO, impressions, clics, CTR, position, sessions organiques, conversions, revenu et impact estimé vs observé | 🔴 | ✅ | 2026-05-19 |
| 121 | Impact Confidence Score — calculer un score de confiance de l'impact selon durée, volume, groupe contrôle, stabilité stock/prix et cohérence GSC/GA4 | 🔴 | ✅ | 2026-05-19 |
| 122 | Before/After Impact Report — générer un rapport lisible par page/action avec score avant/après, métriques GSC/GA4, verdict et recommandations suivantes | 🟡 | ✅ | 2026-05-19 |
| 123 | Retention Milestones — afficher des jalons d'abonnement J+7, J+30, J+60, J+90 pour montrer pourquoi l'app doit rester active pendant la validation | 🟡 | ✅ | 2026-05-19 |
| 124 | Win/Neutral/Risk Detection — classer automatiquement chaque optimisation en impact positif probable, neutre, négatif possible ou inconclusif | 🟡 | ✅ | 2026-05-19 |
| 125 | Next Best Action Loop — transformer les résultats validés en nouvelles recommandations : répliquer, ajuster, attendre ou rollback | 🔴 | ✅ | 2026-05-19 |

### Détail des objectifs Phase 11.5

1. **116 Optimization Snapshot**
   - Enregistrer l’état exact avant chaque modification.
   - Capturer score GEO avant, score SEO avant, contenu avant, facts produits avant, FAQ avant, JSON-LD avant, métriques GSC, métriques GA4, stock, prix, statut produit et contexte saisonnier.
   - Output attendu : snapshot horodaté par page/action, exploitable pour comparaison, rollback et preuve d’impact.
   - Garde-fous : aucun impact ne doit être calculé sans snapshot initial.

2. **117 Optimization Event Tracking**
   - Créer un événement traçable pour chaque optimisation appliquée.
   - Stocker page, action, type d’action, date, utilisateur, job ID, score avant/après, hypothèse d’impact, statut, source de recommandation et éventuel rollback.
   - Output attendu : journal d’événements d’optimisation relié aux jobs et aux pages.
   - Garde-fous : distinguer recommandation, preview, dry-run, application réelle et rollback.

3. **118 Control Group Builder**
   - Sélectionner des pages témoins similaires non modifiées.
   - Matcher par type de page, catégorie, trafic initial, impressions GSC, prix, stock, score GEO initial, saisonnalité et position moyenne.
   - Output attendu : groupe test vs groupe contrôle pour chaque vague d’optimisation.
   - Garde-fous : ne pas présenter une comparaison comme causale si les pages ne sont pas suffisamment comparables.

4. **119 Validation Timeline J+7/J+30/J+60/J+90**
   - Planifier automatiquement les fenêtres de mesure.
   - J+0 : modification appliquée.
   - J+7 : premiers signaux faibles.
   - J+30 : première analyse sérieuse.
   - J+60 : signal plus fiable.
   - J+90 : conclusion complète.
   - Output attendu : timeline visible dans l’UI avec statut pending / measuring / ready / inconclusive.
   - Garde-fous : expliquer que le SEO/GEO nécessite du temps et que les premiers jours ne suffisent pas pour conclure.

5. **120 Progress Curve Dashboard**
   - Afficher une courbe de progression claire pour le marchand.
   - Courbes : score GEO, score SEO si disponible, impressions, clics, CTR, position moyenne, sessions organiques, conversions, revenu, pages améliorées, impact estimé vs observé.
   - Output attendu : dashboard Impact avec courbe globale, courbes par page et résumé des optimisations en validation.
   - Garde-fous : signaler les périodes à faible volume, stock indisponible, changement de prix ou tracking incomplet.

6. **121 Impact Confidence Score**
   - Calculer un score de confiance de l’impact.
   - Facteurs : délai depuis modification, volume d’impressions, évolution vs groupe contrôle, stabilité stock/prix, cohérence GSC/GA4, conversions observées, nouvelles requêtes longues, absence de rollback.
   - Output attendu : score 0-100 avec labels `données insuffisantes`, `signal faible`, `impact probable`, `impact fort`.
   - Garde-fous : ne jamais présenter le score comme une preuve causale absolue.

7. **122 Before/After Impact Report**
   - Générer un rapport clair par page/action.
   - Inclure score GEO avant/après, actions appliquées, requêtes ciblées, métriques GSC avant/après, métriques GA4 avant/après, évolution vs groupe contrôle, verdict et prochaine recommandation.
   - Output attendu : rapport exportable Markdown/PDF ou affichable dans l’app.
   - Garde-fous : distinguer impact estimé, impact observé et impact non encore mesurable.

8. **123 Retention Milestones**
   - Créer des jalons qui expliquent pourquoi l’app doit rester active pendant la validation.
   - Afficher J+7, J+30, J+60, J+90 avec les prochaines étapes.
   - Exemple de message : “Vos optimisations GEO sont appliquées. Les moteurs de recherche et IA ont besoin de temps pour recrawler et réévaluer vos pages. Gardez l’app active pour mesurer les résultats, éviter les pertes et recevoir les prochaines actions prioritaires.”
   - Output attendu : jalons visibles dans le dashboard et dans les rapports.
   - Garde-fous : ne pas utiliser de dark pattern ; la rétention doit être justifiée par la mesure réelle et la valeur du suivi.

9. **124 Win/Neutral/Risk Detection**
   - Classer automatiquement chaque optimisation.
   - Verdicts : `Win`, `Neutral`, `Risk`, `Inconclusive`.
   - Critères : évolution pages test vs pages contrôle, GSC, GA4, revenu, stabilité contexte, volume disponible.
   - Output attendu : verdict par optimisation avec explication simple.
   - Garde-fous : `Inconclusive` doit être utilisé si volume trop faible, tracking incomplet, changement de prix, rupture stock ou période trop courte.

10. **125 Next Best Action Loop**
   - Transformer les résultats validés en nouvelles recommandations.
   - Si Win : répliquer sur pages similaires.
   - Si Neutral : ajuster FAQ, facts, schema ou maillage.
   - Si Risk : proposer rollback ou pause.
   - Si Inconclusive : attendre plus de données ou choisir des pages à plus fort volume.
   - Output attendu : boucle d’amélioration continue reliant validation, recommandations et nouvelles actions.
   - Garde-fous : toute recommandation d’application doit rester en dry-run par défaut et passer par validation humaine.

### Priorité produit recommandée Phase 11.5

1. **116 Optimization Snapshot** — Socle obligatoire pour toute mesure avant/après.
2. **117 Optimization Event Tracking** — Rend chaque optimisation traçable.
3. **119 Validation Timeline J+7/J+30/J+60/J+90** — Donne au marchand une attente claire et justifie le suivi dans le temps.
4. **120 Progress Curve Dashboard** — Rend la progression visible et compréhensible.
5. **121 Impact Confidence Score** — Évite les fausses certitudes et structure la preuve.
6. **122 Before/After Impact Report** — Transforme les résultats en preuve partageable.
7. **124 Win/Neutral/Risk Detection** — Simplifie la lecture des résultats.
8. **125 Next Best Action Loop** — Crée la boucle de rétention et d’amélioration continue.
9. **118 Control Group Builder** — Renforce la crédibilité statistique, mais peut être simplifié en V1.
10. **123 Retention Milestones** — Utile commercialement, mais doit rester basé sur une vraie valeur produit.

---

## PHASE 11.6 — GEO Content Automation
*Objectif : industrialiser la génération IA de contenus GEO utiles (FAQ produits/collections, Answer Blocks, guides d'achat courts, JSON-LD FAQPage) à partir des faits produits confirmés et des intentions conversationnelles réelles, avec revue humaine obligatoire avant publication.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 126 | GEO FAQ & Buying Guide Automation — générer automatiquement des FAQ, Answer Blocks et guides d'achat GEO à partir des faits produits confirmés, requêtes GSC, intentions conversationnelles et catalogue Shopify ; proposer review humaine, scoring qualité, preview, export et application future sur produits, collections ou blogs | 🔴 | ✅ | 2026-05-19 |

### Détail objectif tâche 126

## 126 GEO FAQ & Buying Guide Automation

- **But :** transformer les faits produits confirmés et les requêtes réelles des clients en contenus GEO utiles, prêts à être validés par le marchand.
- **Automatisation attendue :**
  - générer des FAQ produit ;
  - générer des FAQ collection ;
  - générer des blocs courts de réponses IA / Answer Blocks ;
  - générer des guides d'achat courts ;
  - proposer des comparatifs simples ;
  - suggérer des blocs "choisir ce produit si…" ;
  - suggérer des blocs "à savoir avant achat" ;
  - proposer des liens internes vers produits, collections ou guides ;
  - générer le JSON-LD `FAQPage` quand pertinent.
- **Sources à utiliser :**
  - Product Facts Layer ;
  - catalogue Shopify ;
  - descriptions produits existantes ;
  - collections ;
  - Google Search Console ;
  - clusters de niche ;
  - requêtes longues ;
  - intentions conversationnelles ;
  - données de stock ;
  - avis ou preuves de confiance si disponibles.
- **Revue humaine obligatoire :**
  - afficher chaque suggestion en mode preview ;
  - montrer les faits utilisés ;
  - séparer faits confirmés, faits manquants et suggestions à vérifier ;
  - permettre d'accepter, modifier, rejeter ou exporter ;
  - aucune publication automatique par défaut ;
  - toute écriture Shopify doit passer par confirmation explicite.
- **Output attendu :**
  - FAQ par produit ;
  - FAQ par collection ;
  - Answer Blocks courts ;
  - guides d'achat courts ;
  - suggestions de liens internes ;
  - JSON-LD FAQPage ;
  - score qualité / confiance ;
  - statut : `draft`, `needs_review`, `approved`, `rejected`, `exported`, `applied`.
- **Garde-fous :**
  - ne jamais inventer matière, origine, garantie, certification, compatibilité ou bénéfice médical ;
  - ne pas générer de contenu générique sans lien avec le catalogue ;
  - ne pas créer d'articles de blog en masse ;
  - ne pas publier sans validation humaine ;
  - éviter les FAQ artificielles, répétitives ou trop longues ;
  - privilégier les contenus qui répondent à une vraie intention client ou GEO.
- **Valeur GEO attendue :**
  - rendre les produits plus compréhensibles par les moteurs IA ;
  - couvrir les requêtes conversationnelles ;
  - améliorer la clarté des pages produits et collections ;
  - enrichir le JSON-LD ;
  - renforcer le maillage interne ;
  - aider les moteurs IA à associer les produits aux bons cas d'usage.

### Principe contenu GEO

> La génération de contenu GEO ne doit pas être pensée comme un générateur automatique d'articles de blog en masse. L'objectif est de produire des réponses utiles, factuelles et validées à partir du catalogue réel : FAQ produits, FAQ collections, Answer Blocks, guides d'achat courts et comparatifs simples. L'IA automatise la préparation, mais le marchand garde toujours la validation finale avant publication.

---

## PHASE 11.7 — GEO Autopilot Simplification before Public Launch
*Objectif : avant de publier sur l'App Store, fusionner et simplifier la trentaine d'outils existants en une expérience marchand unique, lisible, IA-native et orientée preuve d'impact. Cette phase est une phase de documentation stratégique : elle prépare la roadmap d'implémentation suivante. Claude Code ne doit pas encore coder les modules fusionnés ; il doit d'abord cadrer le périmètre V1 public.*

### Contexte

Phases 1 à 11.6 ont produit une boîte à outils puissante : audit, GSC, GA4, PageSpeed, Product Facts Layer, AI Search Readiness, Revenue-Aware Prioritization, Weekly GEO Actions, GEO Impact Ledger, Risk Guard, Collection Builder, FAQ Generator, validation J+7/J+30/J+60/J+90, Progress Curve, Confidence Score, Before/After Report, Win/Neutral/Risk, Next Best Action Loop, FAQ & Buying Guide Automation. Un marchand Shopify non technique ne peut pas absorber autant de surfaces.

Cette phase reformule l'app autour d'un workflow unique :

> **Connecter → Comprendre → Proposer → Valider → Appliquer → Mesurer**

### Promesse produit V1 publique

Trouver les pages produits actives à améliorer, comprendre la niche marketing de la boutique, générer les modifications SEO/GEO avec l'IA, les faire valider par le marchand, les appliquer proprement sur Shopify, puis mesurer l'impact réel dans le temps sur Google, GA4 et la visibilité IA.

### Principes produit V1

- Le scope principal est limité aux produits **ACTIVE et visibles sur Online Store**. `DRAFT` est traité séparément en *Pre-launch check*. `ARCHIVED` est exclu par défaut. `UNLISTED` est traité à part, sans polluer le score principal.
- Le crawl externe complet type Screaming Frog n'est plus un prérequis. On garde un crawl niveau 3 : Shopify API snapshot + sitemap scan automatique + mini-crawl interne des URLs prioritaires. Import CSV Screaming Frog devient une option avancée.
- Toute écriture Shopify reste en **dry-run par défaut**. La validation humaine est obligatoire par défaut. L'auto-apply n'est mentionné que comme option future opt-in pour les actions à faible risque.
- L'IA (GPT / Claude / Gemini) est une brique centrale de valeur, pas un simple générateur de texte. Elle sert à comprendre la boutique, la niche, les segments clients, les motivations d'achat, et à transformer les signaux Shopify / GSC / GA4 en recommandations.
- Le coût LLM est maîtrisé dès la conception : provider configurable, routing par tâche, cache, batching, outputs JSON, quotas par plan, budget par shop, fallback, mode `low-cost only`.
- La mesure d'impact (Google / GA4 / Shopify / visibilité IA) est la fonctionnalité différenciante centrale. L'app ne se contente pas de générer des contenus : elle prouve si les changements ont aidé.
- Aucune promesse n'est faite sur l'apparition garantie dans ChatGPT, Perplexity, Gemini ou Google AI Overviews. La visibilité IA est présentée comme un signal mesurable mais imparfait.
- Search Performance (GSC/GA4) et AI Visibility (prompts, mentions, citations) sont affichés sur deux axes séparés. Ils ne sont jamais agrégés en un score unique.
- Le terme "autopilot" est utilisé pour décrire la simplification du workflow, pas pour justifier une publication automatique sans contrôle humain.

### Modules fusionnés

L'app expose six modules métier au lieu de la liste actuelle d'outils :

1. **AI Search Readiness Audit** — fusionne Product Facts Layer, SEO Issues, AI Search Readiness Score, GEO Crawlability, JSON-LD, PageSpeed, crawl niveau 3 et statut produit Shopify.
2. **Opportunity Finder** — fusionne GSC Opportunities, longue traîne, Keyword Gaps, Intent Clusters, Niche Clusters, cannibalisation, maillage interne et AI Answer Competitor Monitor (version simplifiée).
3. **Priority Engine** — fusionne ICE, Revenue-Aware GEO Prioritization, Weekly GEO Actions, GEO Risk Guard, signaux stock / marge / trafic / risque / effort / confiance.
4. **AI Content Actions** — fusionne meta titles, meta descriptions, descriptions produits, alt text, FAQ, Answer Blocks, guides d'achat courts, JSON-LD FAQPage et suggestions de collections.
5. **Human Review & Safe Apply** — fusionne diff avant/après, faits utilisés vs suggestions à vérifier, accept/edit/reject, dry-run, apply Shopify, rollback et journal d'écriture.
6. **Impact Tracker** — fusionne Optimization Snapshot, GEO Impact Ledger, Event Tracking, Validation Timeline J+7/J+30/J+60/J+90, Progress Curve, Impact Confidence Score, Before/After Impact Report, Win/Neutral/Risk Detection, Next Best Action Loop, Retention Milestones (intégrées comme logique de dashboard, plus comme outil séparé).

### Briques repoussées hors MVP public

- `llms.txt` Advisor — gardé comme expérimentation / option avancée.
- Web Graph / Common Crawl / backlinks / Brand Signals — trop complexe pour V1.
- Hreflang international et génération multilingue — phase ultérieure, seulement pour boutiques multilingues avancées.
- Control Groups avancés — V1 garde une version simplifiée ou optionnelle.
- Génération massive de briefs blog — non prioritaire, l'app ne fait pas de production blog de masse.
- Redirections 301 en bulk — option avancée hors cœur GEO autopilot.
- Crawl externe complet type Screaming Frog — plus un prérequis ; import CSV reste optionnel.

### Workflow GEO Autopilot cible

1. Onboarding Shopify.
2. Analyse automatique de la boutique par LLM.
3. Compréhension de la niche marketing.
4. Compréhension précise des produits actifs.
5. Identification des segments clients.
6. Identification des motivations d'achat.
7. Présentation des hypothèses au marchand.
8. Ajustement manuel possible par le marchand.
9. Sélection des produits actifs prioritaires.
10. Génération IA des optimisations SEO/GEO.
11. Review humaine obligatoire par défaut.
12. Application Shopify sécurisée (dry-run par défaut).
13. Snapshot avant/après.
14. Mesure d'impact Google / GSC / GA4.
15. Mesure de visibilité IA (ChatGPT / Perplexity / Gemini) quand disponible.
16. Verdict simple : Win / Neutral / Risk / Inconclusive.
17. Next Best Action.

### Tâches Phase 11.7

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 127 | Product Scope Simplification — recentrer le score et les recommandations MVP sur les produits ACTIVE visibles Online Store, isoler Pre-launch Drafts, Hidden/Unlisted et Cleanup/Archived dans des vues séparées | 🟡 | ✅ | 2026-05-19 |
| 128 | Crawl Level 3 Replacement Strategy — remplacer le crawl Screaming Frog obligatoire par Shopify API snapshot + sitemap scan + mini-crawl interne des URLs prioritaires, garder l'import CSV Screaming Frog en option avancée | 🟡 | ✅ | 2026-05-19 |
| 129 | Low-Cost LLM Strategy & Provider Routing *(cadrage produit/architecture, pas implémentation complète)* — décider et documenter les règles de routing par tâche, modèles low-cost par défaut, critères d'usage des modèles avancés, cache, quotas par plan, budget par shop, logs de coût, mode low-cost only et fallback ; réutiliser l'abstraction LLM posée en tâche 58 sans la réécrire | 🔴 | ✅ | 2026-05-19 |
| 130 | Merchant Niche Understanding Layer — cadrer l'usage LLM pour comprendre boutique, produits importants, segments clients, motivations d'achat, angles marketing, promesses à éviter, avec validation marchand obligatoire avant génération | 🔴 | ✅ | 2026-05-19 |
| 131 | Unified AI Search Readiness Audit — fusionner facts, SEO issues, schema, FAQ, crawlability, PageSpeed, trust signals et product status dans un seul score lisible | 🔴 | ✅ | 2026-05-19 |
| 132 | Unified Opportunity Finder — fusionner GSC, longue traîne, clusters, cannibalisation, maillage et competitor monitor en une seule question lisible : quelles pages produits actives méritent une action maintenant ? | 🔴 | ✅ | 2026-05-20 |
| 133 | Unified Priority Engine — fusionner ICE, Revenue-Aware, Weekly Actions et Risk Guard pour ne sortir que 3 actions prioritaires, chacune avec impact estimé, confiance, effort, risque, pourquoi maintenant et métrique de succès | 🔴 | ✅ | 2026-05-20 |
| 134 | AI Content Actions Simplification — fusionner meta, descriptions, alt text, FAQ, Answer Blocks, guides courts et JSON-LD en un seul workflow de génération basé uniquement sur faits confirmés + Shopify + GSC/GA4 + hypothèses validées par le marchand | 🔴 | ✅ | 2026-05-20 |
| 135 | Human Review & Safe Apply Workflow — documenter preview, diff, faits utilisés, accept/edit/reject, dry-run, apply, rollback et event tracking ; validation humaine obligatoire par défaut | 🟡 | ✅ | 2026-05-20 |
| 136 | Impact Tracker as Core Product Value — positionner la mesure d'impact (GSC, GA4, Shopify, AI visibility, J+7/J+30/J+60/J+90, verdict, next best action) comme la fonctionnalité différenciante centrale | 🔴 | ✅ | 2026-05-20 |
| 137 | Merchant-Friendly Dashboard Simplification — définir une interface compréhensible par un non-expert : score global, niche détectée, 3 actions prioritaires, impact en cours, graphiques simples, métriques séparées Google / IA, sans jargon technique en premier niveau | 🟡 | ✅ | 2026-05-20 |
| 138 | Public Launch Readiness Criteria — cadrer les critères d'entrée en Phase 12 : compréhension en < 5 min, 3 actions max, LLM-assisté, review humaine, événement mesurable, scope produits actifs, pas de Screaming Frog obligatoire, pas de promesse ranking ChatGPT, séparation Google / IA, coût LLM maîtrisé, rollback documenté, dry-run par défaut, dashboard impact lisible | 🔴 | ✅ | 2026-05-20 |

### Détail des objectifs Phase 11.7

1. **127 Product Scope Simplification**
   - Objectif : éviter qu'un score boutique ou une liste d'actions soit pollué par des produits non publiés ou archivés.
   - Le score GEO global ne prend en compte que `status = ACTIVE` et visibles Online Store.
   - Pre-launch Drafts : vue dédiée, recommandations préparées sans appliquer.
   - Hidden / Unlisted : vue séparée, hors score principal.
   - Cleanup / Archived : exclus par défaut, accessibles via filtre avancé.
   - Output attendu : 4 vues distinctes, un seul score principal `Active Products`.
   - Garde-fous : ne pas masquer les drafts au marchand, mais les sortir du score.

2. **128 Crawl Level 3 Replacement Strategy**
   - Objectif : supprimer la dépendance Screaming Frog du parcours marchand standard.
   - Sources retenues : Shopify Admin API GraphQL, sitemap.xml public, mini-crawl HTTP des URLs prioritaires détectées par GSC + Shopify.
   - Limite mini-crawl : volumétrie raisonnable, respect du `robots.txt`, pas de rendu JS lourd.
   - Import CSV Screaming Frog reste accessible en mode avancé pour parité fonctionnelle.
   - Garde-fous : aucun crawl agressif, aucune dépendance manuelle dans le parcours V1.

3. **129 Low-Cost LLM Strategy & Provider Routing**
   - **Nature de la tâche : cadrage produit/architecture, pas chantier technique complet.** L'objectif est de figer les règles, garde-fous et seuils avant que les tâches 130-134 commencent à appeler les LLM à grande échelle. L'implémentation détaillée (code des couches cache/quotas/budget) sera réalisée incrémentalement par les tâches consommatrices, sur la base des règles décidées ici.
   - Objectif produit : faire de l'IA une brique centrale sans détruire la marge SaaS et sans créer de dette commerciale liée à des appels LLM non plafonnés.
   - Réutilisation : s'appuie sur l'abstraction `LLM provider` déjà posée en tâche 58 (GPT-4o mini + Cloudflare Workers AI + Groq). Ne pas la réécrire ; l'étendre uniquement quand un module consommateur en a besoin.
   - Décisions à documenter dans cette tâche :
     - **Routing par tâche** :
       - low-cost par défaut (meta titles, alt text, classification simple, extraction structurée) ;
       - moyen (FAQ, descriptions produits, Answer Blocks, guides d'achat courts) ;
       - avancé réservé à : compréhension niche (tâche 130), arbitrage stratégique, synthèse multi-signaux, recommandations prioritaires (tâche 133).
     - **Critères d'escalade** vers un modèle plus avancé : volume de contexte, ambiguïté du prompt, valeur business de la sortie. Toute escalade doit être justifiée par tâche, pas par produit.
     - **Cache LLM** par clé `(shop, resource_id, content_hash, prompt_version)` — règle obligatoire, pas option.
     - **Quotas par plan** Free / Pro / Agency : volumes d'appels, niveau de modèle autorisé, fréquence.
     - **Budget par shop** : plafond mensuel, alertes de dépassement, comportement de coupure (dégradation low-cost only ou blocage doux).
     - **Mode `low-cost only`** activable par l'opérateur pour tous les shops, par plan, ou par shop ciblé.
     - **Logs de coût** par job avec coût estimé `(prompt_tokens, completion_tokens, modèle, provider)` — observabilité minimale obligatoire.
     - **Fallback provider** : règle d'ordre et de timeout en cas d'échec.
     - **Prompts** : courts, déterministes, externalisés dans `config/prompts/` avec versioning explicite pour invalider le cache.
     - **Outputs JSON structurés** par défaut quand le modèle le supporte.
   - Output attendu (livrables de cette tâche, sans code applicatif large) :
     - une note d'architecture courte dans `docs/` décrivant les règles ci-dessus ;
     - un tableau de routing par type de tâche listant les futurs consommateurs (130, 131, 132, 133, 134) et le tier LLM cible ;
     - des seuils chiffrés de quotas et budget par plan ;
     - une checklist d'intégration que chaque tâche consommatrice devra cocher avant d'appeler le LLM en production.
   - Garde-fous :
     - aucune analyse LLM massive sans action explicite ou job planifié ;
     - aucun module consommateur ne doit bypasser le routing, le cache, le log de coût ou le budget ;
     - ne pas transformer cette tâche en refonte complète de la couche LLM existante.

4. **130 Merchant Niche Understanding Layer**
   - Objectif : faire en sorte que l'IA comprenne réellement la boutique avant de générer quoi que ce soit.
   - Inputs LLM : produits actifs, titres, descriptions, collections, prix, tags, types, métadonnées SEO, requêtes GSC, pages déjà performantes, concurrents déclarés ou détectés, avis si disponibles.
   - Output attendu :
     - résumé simple de la boutique ;
     - niche principale, sous-niches ;
     - segments clients, personas simples ;
     - motivations d'achat, objections probables ;
     - produits prioritaires ;
     - angles marketing crédibles ;
     - mots-clés / intentions conversationnelles associés ;
     - concurrents probables ;
     - niveau de confiance par hypothèse.
   - Le marchand peut corriger : niche, cible client, ton de marque, concurrents, produits prioritaires, promesses interdites, avantages produits, marchés ciblés.
   - Les hypothèses validées alimentent les modules suivants (Audit, Opportunity Finder, Priority Engine, AI Content Actions, FAQ, mesure d'impact).
   - Garde-fous : l'IA ne pose que des hypothèses, jamais des faits inventés sur matière, origine, certification, garantie.

5. **131 Unified AI Search Readiness Audit**
   - Objectif : un seul score lisible qui résume la santé GEO/SEO d'un produit actif.
   - Composants fusionnés : Product Facts Layer, SEO Issues, AI Search Readiness Score, GEO Crawlability, JSON-LD, PageSpeed, crawl niveau 3, statut produit Shopify, trust signals.
   - Output attendu : score 0-100 par produit + sous-scores lisibles + raisons + actions recommandées.
   - Garde-fous : ne pas multiplier les scores parallèles ; un score principal, des sous-scores explicatifs.

6. **132 Unified Opportunity Finder**
   - Objectif : répondre à une seule question : quelles pages produits actives méritent une action maintenant ?
   - Sources fusionnées : GSC, longue traîne, Keyword Gaps, Intent Clusters, Niche Clusters, cannibalisation, maillage interne, AI Answer Competitor Monitor simplifié.
   - Output attendu : une liste rangée d'opportunités, chacune reliée à un produit actif et à une métrique de succès attendue.
   - Garde-fous : ne pas présenter une opportunité sans page Shopify cible identifiable.

7. **133 Unified Priority Engine**
   - Objectif : ne sortir que 3 actions prioritaires à la fois.
   - Sources fusionnées : ICE, Revenue-Aware GEO Prioritization, Weekly Actions, GEO Risk Guard, stock, marge si dispo, trafic, risque, effort, confiance.
   - Chaque action expose : impact estimé, confiance, effort, risque, pourquoi maintenant, métrique de succès qui sera mesurée.
   - Garde-fous : ne jamais afficher plus de 3 actions premium ; les autres restent accessibles dans une vue secondaire.

8. **134 AI Content Actions Simplification**
   - Objectif : un seul workflow de génération couvrant meta, descriptions, alt text, FAQ, Answer Blocks, guides courts, JSON-LD.
   - Inputs autorisés : faits confirmés, données Shopify, données GSC/GA4, hypothèses marketing validées par le marchand.
   - Output attendu : un paquet d'optimisations cohérent par produit, avec faits utilisés tracés.
   - Garde-fous : aucune publication automatique par défaut, aucun fait inventé, séparation explicite fait confirmé / suggestion à vérifier.

9. **135 Human Review & Safe Apply Workflow**
   - Objectif : verrouiller le workflow d'application.
   - Étapes : preview → diff avant/après → faits utilisés → accept/edit/reject → dry-run → apply → rollback → event tracking.
   - Garde-fous : validation humaine obligatoire par défaut, écriture Shopify uniquement après confirmation explicite, journal d'écriture systématique.

10. **136 Impact Tracker as Core Product Value**
    - Objectif : positionner la mesure d'impact comme la valeur centrale différenciante.
    - Inclut Snapshot, Ledger, Event Tracking, Validation Timeline J+7/J+30/J+60/J+90, Progress Curve, Confidence Score, Before/After Report, Win/Neutral/Risk, Next Best Action.
    - Métriques séparées : Search Performance (GSC + GA4 + Shopify) vs AI Visibility (prompts, mentions, citations).
    - Garde-fous : ne pas mélanger trafic Google et présence ChatGPT ; afficher deux axes distincts ; ne jamais promettre une apparition garantie en IA.

11. **137 Merchant-Friendly Dashboard Simplification**
    - Objectif : un dashboard lisible par un marchand non technique.
    - Affiche : score GEO des produits actifs, nombre de produits actifs analysés, niche détectée, segments clients, 3 actions prioritaires, trafic Google actuel, impact des optimisations en cours, statut des mesures J+7/J+30/J+60/J+90, coût LLM ou budget utilisé si pertinent.
    - Garde-fous : pas de jargon technique en premier niveau ; chaque indicateur est expliqué en une phrase ; les vues avancées restent accessibles mais ne polluent pas le dashboard.

12. **138 Public Launch Readiness Criteria**
    - Objectif : définir précisément les critères d'entrée en Phase 12.
    - Critères :
      - un marchand non expert comprend l'app en moins de 5 minutes ;
      - l'app affiche 3 actions prioritaires maximum ;
      - chaque action est générée ou assistée par LLM ;
      - chaque action est applicable avec review humaine ;
      - chaque action crée un événement mesurable ;
      - les produits actifs sont le scope principal ;
      - aucune dépendance obligatoire à Screaming Frog ;
      - aucune promesse non prouvée de ranking ChatGPT / Perplexity / Gemini ;
      - métriques Google et IA séparées ;
      - coût LLM maîtrisé et observé ;
      - rollback documenté ;
      - dry-run par défaut ;
      - dashboard impact compréhensible.
    - Output attendu : une checklist explicite que la Phase 12 reprend en go/no-go.

### Priorité produit recommandée Phase 11.7

1. **129 Low-Cost LLM Strategy** — sans cette base, toute extension IA est risquée commercialement.
2. **127 Product Scope Simplification** — clarifie immédiatement le périmètre que les autres modules doivent traiter.
3. **130 Merchant Niche Understanding Layer** — débloque la valeur IA différenciante.
4. **131 Unified AI Search Readiness Audit** — unifie la lecture du diagnostic.
5. **132 Unified Opportunity Finder** — unifie la lecture des opportunités.
6. **133 Unified Priority Engine** — simplifie la décision à 3 actions.
7. **134 AI Content Actions Simplification** — unifie la génération.
8. **135 Human Review & Safe Apply Workflow** — verrouille la sécurité d'écriture.
9. **136 Impact Tracker as Core Product Value** — installe la preuve d'impact comme valeur centrale.
10. **137 Merchant-Friendly Dashboard Simplification** — rend le tout lisible.
11. **128 Crawl Level 3 Replacement Strategy** — supprime un obstacle d'onboarding.
12. **138 Public Launch Readiness Criteria** — sert de checklist d'entrée en Phase 12.

### Principe stratégique Phase 11.7

> La Phase 11.7 ne supprime aucune des briques existantes. Elle les regroupe en six modules clairs, recentre l'expérience sur un workflow unique *Connecter → Comprendre → Proposer → Valider → Appliquer → Mesurer*, et fait de l'IA et de la mesure d'impact les deux briques de valeur centrales. La génération de contenu n'est pas l'objectif final ; prouver que les changements ont aidé le marchand est l'objectif final.

---

## PHASE 11.8 — Implémentation GEO Autopilot Simplification
*Objectif : transformer le cadrage Phase 11.7 en fonctionnalités produit testées avant le go/no-go App Store. La Phase 12 ne démarre pas tant que les critères bloquants de `docs/launch-readiness.md` §3 restent seulement documentés.*

### Principes Phase 11.8

- Conserver les décisions de la Phase 11.7 comme source de vérité produit.
- Implémenter par verticales utilisables : domaine/backend, API, UI Remix, tests, puis preuve launch-readiness.
- Préserver les pages existantes en drill-down ou alias dépréciés pendant une release.
- Garder `dry_run=True` par défaut pour toute écriture Shopify.
- Ne pas introduire de promesse de ranking ChatGPT, Perplexity ou Gemini.
- Faire passer chaque tâche par les validations pertinentes de `docs/COMMANDS.md`.

### Tâches Phase 11.8

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 139 | Product Scope Runtime — implémenter le helper canonique de filtrage produits `ACTIVE` visibles Online Store, brancher readiness/prioritization/weekly/next-best-actions/FAQ et ajouter les tests de scope | 🟡 | ✅ | 2026-05-20 |
| 140 | Crawl L3 Native Runtime — créer sitemap/robots/mini-crawl/findings, étendre le snapshot Shopify aux pages/articles/redirects et garder l'import Screaming Frog en mode avancé | 🔴 | ✅ | 2026-05-20 |
| 141 | Niche Understanding Runtime — créer le prompt versionné, l'orchestrateur LLM, les endpoints understand/hypothesis, la persistance validée marchand et l'UI de correction | 🔴 | ✅ | 2026-05-20 |
| 142 | Unified Readiness Audit Runtime — exposer le score unifié actif, sous-scores, recommandations, route canonique `/audit/readiness`, UI `app.audit-readiness` et compatibilité drill-down | 🔴 | ✅ | 2026-05-20 |
| 143 | Opportunity Finder Runtime — agréger les signaux existants en opportunités par produit actif, route `/opportunities`, UI dédiée et tests de scoring déterministe | 🔴 | ✅ | 2026-05-20 |
| 144 | Priority Engine Runtime — produire exactement 3 actions prioritaires avec fallback déterministe, arbitrage LLM plafonné/cache, route `/priorities`, UI cartes et tests budget/fallback | 🔴 | ✅ | 2026-05-20 |
| 145 | AI Content Actions Runtime — créer l'orchestrateur unique, schémas Pydantic, prompts v2.0, table `content_actions`, route `/content-actions/run` et UI unifiée | 🔴 | ✅ | 2026-05-20 |
| 146 | Safe Apply Runtime — créer diff/decisions/writer adapters/rollback adapters, routes `/safe-apply/*`, extension des content types, UI review/apply/rollback et tests de garde-fous | 🔴 | ✅ | 2026-05-21 |
| 147 | Impact Tracker Productization — recentrer l'UI Impact autour de Search Performance, optimisations actives, rétention, next actions, ajouter `ai-visibility/status` désactivé V1 | 🟡 | ✅ | 2026-05-21 |
| 148 | Merchant Dashboard Runtime — créer `GET /api/shops/{shop}/dashboard`, refondre `app._index.tsx` en 6 zones, renommer la navigation et valider responsive/Playwright | 🔴 | ✅ | 2026-05-21 |
| 149 | Launch Readiness Evidence Pass — exécuter `docs/launch-readiness.md` §3, cocher chaque critère avec preuve, ouvrir les manques restants et documenter la décision dans `DECISIONS.md` | 🔴 | ✅ | 2026-05-21 |

### Ordre recommandé Phase 11.8

1. **139 Product Scope Runtime** — dépendance transversale pour éviter de scorer les mauvais produits.
2. **141 Niche Understanding Runtime** — débloque les modules IA aval.
3. **142 Unified Readiness Audit Runtime** — crée le diagnostic lisible.
4. **143 Opportunity Finder Runtime** — transforme les diagnostics et signaux en opportunités.
5. **144 Priority Engine Runtime** — réduit les opportunités à 3 actions.
6. **145 AI Content Actions Runtime** — génère les brouillons exploitables.
7. **146 Safe Apply Runtime** — sécurise review, dry-run, apply, rollback et event tracking.
8. **147 Impact Tracker Productization** — rend la preuve d'impact centrale.
9. **148 Merchant Dashboard Runtime** — assemble l'expérience marchand principale.
10. **140 Crawl L3 Native Runtime** — peut avancer en parallèle après 139, mais ne bloque pas les verticales purement Shopify/GSC.
11. **149 Launch Readiness Evidence Pass** — dernier verrou avant Phase 12.

---

## PHASE 11.9 — Merchant Journey Unification & Friction Reduction
*Objectif : transformer les briques existantes en un parcours marchand unique, explicite et compréhensible par un non-expert : **Connecter → Comprendre → Valider → Analyser → Proposer → Appliquer → Mesurer**.*

Cette phase ne doit pas ajouter de nouveaux moteurs SEO/GEO. Elle doit réorganiser l'expérience produit autour des technologies déjà codées :

- Google Search Console / GA4 ;
- Niche Understanding ;
- Unified Readiness Audit ;
- Opportunity Finder ;
- Priority Engine ;
- AI Content Actions ;
- Safe Apply ;
- Rollback ;
- Impact Tracker ;
- Dashboard marchand.

Le but est de réduire la friction avant les tests marchands pilotes et avant la soumission publique App Store.

### Principes produit Phase 11.9

- Le marchand ne doit jamais avoir l'impression d'utiliser plusieurs modules séparés.
- Le parcours principal doit être linéaire, avec un seul CTA principal par écran.
- Les termes techniques doivent être cachés ou renommés.
- L'app doit expliquer ce qu'elle fait en langage marchand.
- Le parcours standard ne doit pas afficher les détails techniques : crawl, JSON-LD, schema, GSC opportunities, Product Facts Layer, logs LLM, scripts, endpoints.
- Ces briques restent disponibles en interne ou en mode avancé.
- Niche Understanding devient le socle obligatoire avant les analyses SEO/GEO.
- Les informations validées par le marchand doivent alimenter les analyses, recommandations, contenus, priorités et mesures d'impact.
- Les actions affichées au marchand doivent être limitées à 3 priorités maximum.
- Toute application Shopify reste en dry-run par défaut avec validation humaine.
- La mesure d'impact reste une valeur centrale : l'app doit montrer si les optimisations ont aidé ou non.
- Ne pas promettre de ranking garanti dans Google, ChatGPT, Perplexity, Gemini ou Google AI Overviews.
- Search Performance et AI Visibility restent séparés.

### Parcours marchand cible

1. Première connexion à l'application.
2. Écran simple : “Connectez Google pour analyser votre visibilité”.
3. Connexion Google Search Console.
4. Connexion GA4 optionnelle mais recommandée.
5. CTA principal : “Analyser ma boutique avec l'IA”.
6. Écran de progression simple :
   - lecture des produits actifs ;
   - lecture des collections ;
   - analyse des requêtes Google ;
   - compréhension de la niche ;
   - détection des pages prioritaires.
7. Écran “Ce que l'IA a compris” :
   - niche principale ;
   - produits importants ;
   - segments clients ;
   - motivations d'achat ;
   - objections probables ;
   - promesses à éviter ;
   - concurrents ou alternatives probables ;
   - niveau de confiance.
8. Le marchand peut modifier, corriger ou valider ces informations.
9. Après validation, lancement automatique de l'analyse SEO/GEO.
10. Arrivée sur l'accueil avec :
    - score global SEO/GEO lisible ;
    - résumé de ce que l'IA a compris ;
    - 3 actions prioritaires ;
    - état des optimisations en cours ;
    - résultats mesurés ou en attente.
11. Le marchand clique sur une action.
12. L'app affiche :
    - problème détecté ;
    - pourquoi cette page est prioritaire ;
    - ce que l'IA propose ;
    - preview avant/après ;
    - niveau de risque ;
    - gain potentiel ;
    - métrique de succès.
13. Le marchand peut approuver, modifier, rejeter ou appliquer en sécurité.
14. Après application, l'app crée un événement mesurable.
15. L'app suit l'impact à J+7, J+30, J+60 et J+90.
16. Verdict simple :
    - Win ;
    - Neutral ;
    - Risk ;
    - Inconclusive.
17. L'app propose la prochaine meilleure action.

### Navigation cible

La navigation visible doit rester limitée à 4 entrées :

1. **Accueil**
   - score global ;
   - compréhension IA validée ;
   - 3 actions prioritaires ;
   - état des optimisations ;
   - prochains résultats attendus.

2. **Actions**
   - actions à prévisualiser ;
   - actions à valider ;
   - actions prêtes à appliquer ;
   - historique simple des décisions.

3. **Mesure**
   - impact des optimisations ;
   - courbes simples ;
   - jalons J+7/J+30/J+60/J+90 ;
   - verdicts Win/Neutral/Risk/Inconclusive ;
   - prochaine meilleure action.

4. **Compte & configuration**
   - connexions Google ;
   - GA4 ;
   - plan ;
   - budget IA ;
   - mode pilot-safe ;
   - réglages avancés.

Tout le reste doit être masqué du menu principal ou regroupé en mode avancé.

### Renommage des termes techniques

| Terme technique | Terme marchand |
|---|---|
| GEO | Visibilité IA |
| AI Search Readiness | Lisibilité par les IA |
| Product Facts Layer | Informations produit fiables |
| JSON-LD / Schema | Données produit structurées |
| Crawl L3 | Vérification technique |
| GSC Opportunities | Opportunités Google |
| Priority Engine | Actions prioritaires |
| Safe Apply | Application sécurisée |
| Impact Ledger | Historique des optimisations |
| Niche Understanding | Ce que l'IA a compris |
| Content Actions | Améliorations proposées |
| Rollback | Annuler une modification |

### Tâches Phase 11.9

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 152 | First-Run Journey Map — documenter le parcours marchand complet de première connexion jusqu'à la première action appliquée : connecter Google, analyser avec l'IA, valider la compréhension IA, lancer l'analyse SEO/GEO, afficher le score et proposer 3 actions | 🟡 | ✅ | 2026-05-21 |
| 153 | Niche Understanding as Mandatory Gate — cadrer le fait que la compréhension IA validée devient un prérequis logique avant les analyses et recommandations principales, avec possibilité de modifier/relancer avant validation | 🔴 | ✅ | 2026-05-21 |
| 154 | Unified Onboarding Flow — réduire l'onboarding à 4 étapes maximum : connecter Google, lancer analyse IA, valider compréhension IA, voir les 3 actions prioritaires | 🟡 | ✅ | 2026-05-21 |
| 155 | Dashboard as Single Command Center — recentrer l'accueil sur score global, résumé IA validé, 3 actions prioritaires, optimisations en cours et résultats mesurés, sans exposer les modules techniques | 🔴 | ✅ | 2026-05-21 |
| 156 | One Primary CTA per Screen — définir pour chaque écran principal un seul CTA dominant : connecter, analyser, valider, voir actions, prévisualiser, appliquer, mesurer | 🟡 | ✅ | 2026-05-21 |
| 157 | Merchant Language Pass — remplacer les termes techniques visibles par des termes compréhensibles par un marchand non expert, avec tableau de correspondance FR/EN et garde-fous i18n | 🟡 | ✅ | 2026-05-21 |
| 158 | Advanced Tools Hiding Strategy — documenter quelles pages restent accessibles en mode avancé mais disparaissent du parcours principal : crawl, JSON-LD, GSC details, PageSpeed details, Product Facts, logs LLM, llms.txt, AI Visibility V2 | 🟡 | ✅ | 2026-05-21 |
| 159 | Action Detail Unification — cadrer une carte action unique pour toutes les recommandations : problème, raison, page concernée, preview avant/après, risque, gain potentiel, métrique de succès, CTA prévisualiser/appliquer | 🔴 | ✅ | 2026-05-21 |
| 160 | Safe Apply Narrative Simplification — rendre le workflow dry-run/review/apply/rollback compréhensible : aucune modification publiée sans validation, preview obligatoire, historique et annulation visibles | 🟡 | ✅ | 2026-05-21 |
| 161 | Impact Feedback Loop UX — cadrer la suite après application : suivi J+7/J+30/J+60/J+90, verdict simple, prochaine meilleure action et explication de la valeur de garder l'app active | 🔴 | ✅ | 2026-05-21 |
| 162 | Pilot Merchant Test Script — créer un script de test utilisateur pour 3 marchands pilotes afin de vérifier : compréhension en moins de 5 minutes, capacité à lancer l'analyse, valider la compréhension IA, comprendre le score, choisir une action et faire confiance au safe apply | 🟡 | ✅ | 2026-05-21 |
| 163 | Phase 12 Entry Criteria Update — ajouter les critères bloquants avant soumission App Store : parcours compris en moins de 5 minutes, 3 actions maximum, CTA clair, vocabulaire non technique, compréhension IA validée, safe apply compris, mesure d'impact visible | 🔴 | ✅ | 2026-05-21 |

### Détail attendu des tâches Phase 11.9

1. **152 First-Run Journey Map**
   - Objectif : formaliser le parcours de première utilisation depuis l'installation jusqu'à la première action appliquée.
   - Livrable attendu : document de parcours avec étapes, écran attendu, CTA principal, état vide, état erreur et critère de passage. Réalisé dans `docs/first-run-merchant-journey.md`.
   - Garde-fous : ne pas ajouter de nouveau moteur SEO/GEO, ne pas réintroduire un hub technique comme point d'entrée.
   - Lien avec l'existant : s'appuie sur onboarding Google, Niche Understanding, dashboard, Priority Engine, Safe Apply et Impact Tracker.
   - À ne pas ajouter : nouveau module, nouveau score, nouvelle API de recommandation ou nouveau chemin parallèle.
   - Implémentation initiale : le JSON brut de l'écran "Ce que l'IA a compris" est déplacé derrière un bloc "Mode avancé" afin de garder le parcours standard marchand lisible.

2. **153 Niche Understanding as Mandatory Gate**
   - Objectif : cadrer la compréhension IA validée comme prérequis logique avant les analyses et recommandations principales.
   - Livrable attendu : règle produit indiquant quand l'analyse peut démarrer, comment modifier/relancer l'hypothèse, et comment les modules aval consomment la version validée. Réalisé dans `docs/niche-understanding-gate.md`.
   - Garde-fous : ne pas bloquer l'accès aux réglages, au support ou au mode avancé ; ne pas utiliser une hypothèse non validée pour générer des promesses marchand.
   - Lien avec l'existant : consomme `niche_hypothesis`, `get_validated_niche_hypothesis()`, Unified Readiness Audit, Opportunity Finder, Priority Engine et AI Content Actions.
   - À ne pas ajouter : extraction de niche concurrentielle nouvelle, nouveau prompt hors cadrage, ou validation automatique sans marchand.
   - Implémentation initiale : l'accueil masque les cartes d'actions derrière une gate de validation si `zone1.niche_validated` est faux ; la page Top 3 Actions vérifie `/niche/hypothesis` avant de charger les priorités et redirige le marchand vers l'écran de compréhension boutique.

3. **154 Unified Onboarding Flow**
   - Objectif : réduire l'onboarding visible à 4 étapes maximum : connecter Google, lancer l'analyse IA, valider la compréhension IA, voir les 3 actions prioritaires.
   - Livrable attendu : séquence onboarding cible avec textes marchands, CTA, états de progression et fallback si GA4 est absent. Réalisé dans `docs/unified-onboarding-flow.md`.
   - Garde-fous : GA4 reste recommandé mais non bloquant ; Screaming Frog ne redevient jamais un prérequis.
   - Lien avec l'existant : réutilise OAuth Google/GSC, GA4, Crawl L3 natif, Niche Understanding et Dashboard Runtime.
   - À ne pas ajouter : checklist longue, wizard technique multi-écrans, dépendance à un outil desktop externe.
   - Implémentation initiale : `app.onboarding` affiche une carte principale en 4 étapes avec un seul prochain CTA ; la checklist complète, PageSpeed, crawl et jobs restent accessibles derrière "Outils avancés".

4. **155 Dashboard as Single Command Center**
   - Objectif : faire de l'accueil le centre de commande unique du marchand.
   - Livrable attendu : cadrage d'un dashboard affichant score global, résumé IA validé, 3 actions prioritaires, optimisations en cours et résultats mesurés.
   - Garde-fous : pas de liste exhaustive de modules, pas de jargon de type crawl/schema/GSC opportunity au premier niveau.
   - Lien avec l'existant : s'appuie sur `GET /api/shops/{shop}/dashboard`, readiness, priorities, impact, alertes et budget LLM.
   - À ne pas ajouter : widgets personnalisables, analytics avancées, ou score mélangeant Google Search Performance et AI Visibility.

5. **156 One Primary CTA per Screen**
   - Objectif : réduire l'hésitation en définissant un CTA dominant par écran principal.
   - Livrable attendu : matrice écran → intention → CTA principal → CTA secondaire éventuel → action interdite.
   - Garde-fous : ne pas afficher plusieurs actions concurrentes au même niveau ; garder les actions destructives derrière confirmation.
   - Lien avec l'existant : couvre onboarding, compréhension IA, dashboard, action detail, Safe Apply, rollback et mesure.
   - À ne pas ajouter : automatisation d'application Shopify sans dry-run ni validation humaine.

6. **157 Merchant Language Pass**
   - Objectif : remplacer le vocabulaire technique visible par des termes marchands compréhensibles.
   - Livrable attendu : glossaire FR/EN, règles i18n, liste de termes interdits en premier niveau et mapping vers les labels existants.
   - Garde-fous : conserver les termes techniques uniquement en mode avancé ou documentation interne ; ne pas promettre de ranking garanti.
   - Lien avec l'existant : s'applique à `shopify-app/app/lib/i18n.ts`, dashboard, hubs, onboarding, actions et mesure.
   - À ne pas ajouter : nouveau branding produit ambigu, claims marketing non prouvés, ou mélange Search Performance / AI Visibility.

7. **158 Advanced Tools Hiding Strategy**
   - Objectif : documenter précisément quelles pages restent accessibles en mode avancé mais disparaissent du parcours principal.
   - Livrable attendu : inventaire des routes avancées, règle de navigation, libellés “mode avancé”, et critères pour réintégrer une page dans le parcours standard.
   - Garde-fous : ne pas supprimer les routes historiques ; ne pas exposer logs LLM, scripts, endpoints ou détails crawl au marchand standard.
   - Lien avec l'existant : couvre crawl, JSON-LD, PageSpeed, Product Facts, llms.txt, AI Visibility V2, jobs et rapports techniques.
   - À ne pas ajouter : nouveau menu principal, nouveau hub technique visible ou dépendance aux anciens écrans comme chemin recommandé.

8. **159 Action Detail Unification**
   - Objectif : unifier la présentation de toutes les recommandations dans une seule carte action.
   - Livrable attendu : structure canonique affichant problème, raison, page concernée, preview avant/après, risque, gain potentiel, métrique de succès et CTA prévisualiser/appliquer.
   - Garde-fous : 3 actions maximum au premier niveau ; chaque action doit rester explicable sans jargon SEO/GEO.
   - Lien avec l'existant : s'appuie sur Priority Engine, AI Content Actions, Safe Apply diff, risk guard et success metrics Impact Tracker.
   - À ne pas ajouter : nouveau moteur de scoring, nouvelle génération LLM ou action automatique sans review.

9. **160 Safe Apply Narrative Simplification**
   - Objectif : rendre le workflow dry-run/review/apply/rollback compréhensible par un marchand non expert.
   - Livrable attendu : wording et séquence expliquant qu'aucune modification n'est publiée sans validation, preview obligatoire, historique visible et annulation disponible.
   - Garde-fous : dry-run par défaut, validation humaine obligatoire, confirmation live write et pilot-safe inchangés.
   - Lien avec l'existant : réutilise Safe Apply Runtime, rollback adapters, `seo_changes`, `content_action_decisions` et historique rollback.
   - À ne pas ajouter : auto-approve, bulk apply non supervisé, ou rollback masqué.

10. **161 Impact Feedback Loop UX**
    - Objectif : cadrer l'expérience post-application comme une boucle de preuve d'impact.
    - Livrable attendu : parcours J+7/J+30/J+60/J+90 avec verdict Win/Neutral/Risk/Inconclusive, prochaine meilleure action et message de valeur sur la rétention.
    - Garde-fous : ne pas conclure trop tôt sur faible volume ; séparer Search Performance et AI Visibility ; afficher l'incertitude.
    - Lien avec l'existant : s'appuie sur Impact Tracker, validation timeline, progress curve, confidence score, retention milestones et next-best-actions.
    - À ne pas ajouter : attribution cross-channel spéculative, promesse de revenu garanti, ou score unique IA+Google.

11. **162 Pilot Merchant Test Script**
    - Objectif : préparer le test utilisateur avec 3 marchands pilotes avant go/no-go App Store.
    - Livrable attendu : script de session, tâches à observer, questions post-test, seuils de réussite et grille de friction.
    - Garde-fous : mesurer la compréhension réelle en moins de 5 minutes ; ne pas guider excessivement le marchand pendant le test.
    - Lien avec l'existant : teste onboarding, Niche Understanding, dashboard, actions prioritaires, Safe Apply et mesure.
    - À ne pas ajouter : nouveaux écrans pendant le test, promesses commerciales, ou contournement des critères bloquants.

12. **163 Phase 12 Entry Criteria Update**
    - Objectif : ajouter les critères bloquants d'entrée en Phase 12 après unification UX.
    - Livrable attendu : critères go/no-go à jour incluant Phase 11.9 complétée, test 3 marchands, parcours linéaire validé, vocabulaire marchand et dashboard compris sans explication externe.
    - Garde-fous : aucun critère de friction majeur ne peut être contourné par une moyenne globale.
    - Lien avec l'existant : met à jour `docs/launch-readiness.md`, `DECISIONS.md`, Phase 12 et les preuves de validation pilote.
    - À ne pas ajouter : nouvelle fonctionnalité SEO/GEO, nouvelle métrique de ranking, ou soumission App Store avant validation humaine.

### Contraintes Phase 11.9

- Ne pas ajouter de nouvelles fonctionnalités SEO/GEO.
- Ne pas ajouter de nouveau module dans la navigation principale.
- Ne pas remettre Screaming Frog comme prérequis.
- Ne pas rendre l'application automatique sans validation humaine.
- Ne pas mélanger les métriques Google et IA dans un score unique.
- Ne pas promettre de ranking garanti.
- Ne pas exposer les détails LLM au marchand sauf dans les réglages avancés.
- Ne pas supprimer les routes historiques : les garder en drill-down ou mode avancé.
- Ne pas marquer les tâches 152-163 comme terminées tant que le cadrage n'est pas effectivement produit et validé.
- Ne pas coder cette phase maintenant : uniquement documentation roadmap et cadrage UX.

---

## PHASE 12 — Soumission publique Shopify App Store
*Objectif : publier l'app seulement après le pilote réel, la parité fonctionnelle prioritaire entre scripts CLI et app embedded, la simplification GEO Autopilot documentée en Phase 11.7, implémentée en Phase 11.8, puis unifiée côté parcours marchand en Phase 11.9. La soumission publique Shopify App Store ne démarre qu'après validation de la Phase 11.9, tests marchands pilotes, et confirmation que le parcours principal est compris en moins de 5 minutes.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 150 | Décision go/no-go App Store après pilote réel + parité fonctionnelle prioritaire + simplification GEO Autopilot implémentée (Phase 11.8) + Phase 11.9 complétée + test utilisateur 3 marchands + parcours linéaire validé + friction réduite + vocabulaire marchand validé + dashboard compris sans explication externe + verrouillage du périmètre V1 public | 🔴 | ⏳ | |
| 151 | Finaliser la soumission publique Shopify App Store avec preuves issues du pilote, captures à jour, checklist Public Launch Readiness (tâche 149) et configuration de production figée | 🔴 | ⏳ | |
