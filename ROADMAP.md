# ROADMAP — SEO Leoniedelacroix.com
> Mise à jour à chaque tâche complétée. Statuts : ✅ Fait · 🔄 En cours · ⏳ À faire

## PHASE 1 — Fondations & Audit (Semaine 1-2)
*Objectif : premier rapport d'audit fonctionnel sur leoniedelacroix.com*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 1 | Structure repo + `.env` + `.gitignore` + `CLAUDE.md` | 🟢 | ✅ | 2026-04-20 |
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
| 49 | Soumission et validation Shopify App Store | 🔴 | ⏳ | |
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
| 73 | GA4 Data API — corrélation trafic organique × conversions × recettes par tenant | 🔴 | ⏳ | |
| 74 | Common Crawl / Web Graph — backlinks, graph liens concurrents, mentions marque non-linkées (après validation tâche 63) | 🔴 | ⏳ | |
| 75 | Soumission App Store finale — après GDPR + Billing + App Bridge validés (tâches 51-57) | 🔴 | ⏳ | |
