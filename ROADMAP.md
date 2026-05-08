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
| 36 | Score E-E-A-T par page — auteur, sources, date, expertise vétérinaire | 🔴 | ⏳ | |
| 37 | Générateur balises hreflang si extension BE/CH francophone | 🟡 | ⏳ | |
| 38 | Rapport mensuel synthétique PDF — trafic, conversions, gains cumulés | 🟡 | ⏳ | |
| 39 | Dashboard CLI interactif `rich` — vue temps réel santé SEO du site | 🟡 | ⏳ | |

---

## PHASE 4 — Productisation & Monétisation (Mois 6)
*Objectif : transformer l'outil en produit vendable à d'autres boutiques Shopify*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 40 | Abstraction multi-boutiques — config par tenant dans YAML | 🔴 | ⏳ | |
| 41 | Interface CLI universelle — sélecteur de secteur/niche au démarrage | 🟡 | ⏳ | |
| 42 | Bibliothèque de règles métier par secteur (cosmétique, bébé, jardinage…) | 🔴 | ⏳ | |
| 43 | Système de licences API key — authentification par boutique cliente | 🔴 | ⏳ | |
| 44 | Packaging PyPI ou Docker — installation en une commande | 🔴 | ⏳ | |

---

## PHASE 5 — App Shopify publique (Mois 12)
*Objectif : produit SaaS scalable sur le Shopify App Store*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 45 | OAuth Shopify — authentification marchands via App Store | 🔴 | ⏳ | |
| 46 | Backend FastAPI — API REST entre l'app et le moteur Python | 🔴 | ⏳ | |
| 47 | Frontend dashboard React — version UI du CLI | 🔴 | ⏳ | |
| 48 | Système de pricing par plan (Free/Pro/Agency) | 🔴 | ⏳ | |
| 49 | Soumission et validation Shopify App Store | 🔴 | ⏳ | |
| 50 | Support + documentation utilisateur multilingue | 🟡 | ⏳ | |
