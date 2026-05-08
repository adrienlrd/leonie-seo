# CLAUDE.md — SEO Leoniedelacroix.com

## 1. CONTEXTE BUSINESS
- Site Shopify **accessoires premium pour chiens et chats**, fabriqués en France — mode/luxe animalier
- URL : https://www.leoniedelacroix.com · Domaine : 287c4a-bb.myshopify.com
- **Catalogue** : vêtements chien/chat (pardessus, pull, harnais), fontaines eau, griffoirs, bols design
- **Objectif 12 mois** : 5 000–10 000 visites organiques/mois, 40–100 conversions/mois
- **Vision** : outil personnel → produit vendable → app Shopify publique
- Concurrents : Miacara, Zara Pets, Ferplast, boutiques mode animaux premium FR

## 2. DÉBUT DE SESSION — OBLIGATOIRE
**À chaque session, dans cet ordre avant toute action :**
1. Lire `PROGRESS.md` — état actuel, tâches faites, blocages
2. Lire `ROADMAP.md` — identifier la prochaine tâche ⏳ non faite
3. Proposer explicitement cette tâche à l'utilisateur avant de coder

**Ne jamais sauter de tâches.** Suivre l'ordre du PROJECT_BRIEF.md sauf demande explicite.
**Ne jamais coder sans que le plan soit validé par l'utilisateur.**

## 3. ÉTAT DES PHASES
| Phase | Tâches | Horizon | Statut |
|---|---|---|---|
| 1 — Audit & Fondations | 1–15 | Semaine 1-2 | ✅ Complète |
| 2 — Application supervisée | 16–29 | Semaine 3-6 | 🔄 En cours (8/14) |
| 3 — Contenu SEO & Niche | 30–39 | Mois 2-4 | ⏳ Non démarrée |
| 4 — Productisation | 40–44 | Mois 6 | ⏳ Non démarrée |
| 5 — App Shopify publique | 45–50 | Mois 12 | ⏳ Non démarrée |

**Phase 2 — tâches restantes (dans l'ordre) :**
- `16` Matrice ICE — priorisation issues par Impact/Coût/Effort
- `22` `create_redirects.py` — import 301 en bulk depuis CSV validé
- `23` Structured data JSON-LD Product + AggregateRating via metafields
- `24` Commande rollback SQLite (logging ✅, CLI de rollback manquant)
- `25` Détecteur opportunités GSC — positions 11–20 à optimiser
- `26` Analyse concurrentielle longue traîne petfood FR
- `27` Rapport comparaison avant/après par page (delta score SEO)
- `28` GitHub Actions cron hebdomadaire — audit auto + commit rapport
- `29` Alertes email — régression CWV, nouveaux 404, chute de position

## 4. RÈGLES NON NÉGOCIABLES
1. **Plan avant code** — toute tâche >15 lignes → plan validé d'abord
2. **Dry-run par défaut** — scripts `apply/` : `--dry-run` par défaut, `--apply` explicite
3. **Confirmation humaine** avant chaque écriture Shopify
4. **Jamais de secrets en dur** — `.env` uniquement, `.env.example` tenu à jour
5. **Pas de modification de handles** — risque 404 massif, interdit définitivement
6. **Commits atomiques** — format `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
7. **Tests minimaux** — un test unitaire mocké par fonction qui touche une API
8. **Pas d'hallucination** — si une donnée manque, lever une exception explicite
9. **ROADMAP.md** — mettre à jour statut + date après chaque tâche terminée
10. **shopify-safety** — lancer ce subagent avant tout `--apply`

## 5. WORKFLOW OBLIGATOIRE
1. **Explore** → lire PROGRESS.md + ROADMAP.md + fichiers concernés
2. **Plan** → bullet points soumis à l'utilisateur, pas de code avant validation
3. **Implement** → coder le plan approuvé uniquement
4. **Verify** → tests verts + ruff clean + prouver que ça marche
5. **Update** → ROADMAP.md (statut + date) + PROGRESS.md + commit atomique

## 6. STACK TECHNIQUE
- Python 3.11+ · Shopify Admin API GraphQL (2025-01 minimum) · SQLite stdlib
- Google Search Console API · PageSpeed Insights API · GA4 Data API
- Screaming Frog Free (crawl manuel) · GitHub Actions (cron)
- Dépendances autorisées : `requests`, `pandas`, `python-dotenv`, `pydantic`, `click`, `rich`, `google-auth`, `google-api-python-client`, `pyyaml`
- **Demander confirmation avant toute autre dépendance**

## 7. GESTION DU CONTEXTE
| Seuil | Action |
|---|---|
| 0–70% | Travail normal |
| 70–90% | `/compact` obligatoire |
| 90%+ | `/clear` obligatoire — hallucinations probables |

## 8. SUBAGENTS (`.claude/agents/`)
- `shopify-safety` — review sécurité avant tout `--apply`
- `python-quality` — review qualité avant chaque commit

## 9. ARBORESCENCE
```
scripts/audit/       ← lecture seule, sans risque
scripts/apply/       ← écriture Shopify, dry-run par défaut
scripts/report/      ← rapports Markdown
config/              ← keywords.yaml, seo_rules.yaml
skills/              ← règles SEO, patterns GraphQL, niche petfood
data/raw/            ← exports bruts (gitignored)
data/history.db      ← SQLite historique (69 changements loggés)
reports/YYYY-MM-DD/  ← rapports horodatés
```

## 10. COMMANDES FRÉQUENTES
```bash
python -m scripts.audit.crawl_shopify                          # snapshot Shopify
python -m scripts.audit.fetch_gsc                              # données GSC 90j
python -m scripts.audit.fetch_pagespeed                        # Core Web Vitals
python -m scripts.audit.detect_issues                          # détection problèmes
python -m scripts.report.generate_report --week                # rapport Markdown
python -m scripts.apply.generate_suggestions                   # générer suggestions
python -m scripts.apply.update_meta --updates data/raw/meta_suggestions.json --dry-run
python -m scripts.apply.update_meta --updates data/raw/meta_suggestions.json --apply
python -m scripts.apply.update_alt_text --dry-run
python -m scripts.apply.update_alt_text --apply
```

## 11. FICHIERS DE RÉFÉRENCE
- `PROJECT_BRIEF.md` — vision complète, 50 tâches, règles d'or Claude Code
- `ROADMAP.md` — statuts ✅/🔄/⏳ des 50 tâches, **mettre à jour après chaque tâche**
- `PROGRESS.md` — état session par session, blocages, prochaines étapes
- `DECISIONS.md` — journal des choix techniques (compléter à chaque décision)
- `CONTEXT.md` — fiche marché, concurrents, mots-clés stratégiques
- `skills/seo-technique.md` — seuils et règles de scoring SEO
- `skills/shopify-graphql.md` — patterns GraphQL sûrs et rate limiting
- `skills/pet-accessories-niche.md` — mots-clés, positionnement, règles E-E-A-T
