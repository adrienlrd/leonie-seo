# Advanced Tools Hiding Strategy — Tâche 158

## Objectif

Garder toutes les routes existantes accessibles par URL directe (pour pilote, debug, marchands experts) mais les retirer du parcours marchand principal et de la navigation visible.

## Routes classées "avancées" (hors parcours principal)

| Route | Nom technique | Accès |
|---|---|---|
| `/app/audit` | Audit SEO complet | Section avancée d'un hub |
| `/app/geo-readiness` | AI Search Readiness | Section avancée |
| `/app/geo-facts` | Product Facts GEO | Section avancée |
| `/app/geo-risk-guard` | GEO Risk Guard | Section avancée |
| `/app/geo-ledger` | GEO Impact Ledger | Section avancée |
| `/app/jsonld` | JSON-LD / Schema | Section avancée |
| `/app/crawl` | Crawl L3 | Section avancée (déjà optionnel dans onboarding) |
| `/app/jobs` | Job management | Section avancée |
| `/app/pagespeed` | PageSpeed | Section avancée (déjà optionnel dans onboarding) |
| `/app/product-facts` | Product Facts | Section avancée |
| `/app/llms-txt` | llms.txt | Section avancée |
| `/app/validation-timeline` | Timeline validation | Section avancée |
| `/app/snapshots` | Snapshots GEO | Section avancée |
| `/app/control-groups` | Groupes contrôle | Section avancée |
| `/app/impact-report` | Rapport impact | Lien depuis app.impact |
| `/app/retention-milestones` | Jalons de validation | Lien depuis app.impact |
| `/app/next-best-actions` | Prochaines actions | Lien depuis app.impact |

## Navigation principale (4 entrées, aucun changement de code requis)

La navigation `app.tsx` expose déjà uniquement :
1. Accueil → `/app`
2. Actions → `/app/optimization`
3. Mesure → `/app/insights`
4. Compte & configuration → `/app/account`

Les routes avancées n'apparaissent pas dans ce NavMenu. ✓

## Règle de présentation

- Les routes avancées sont mentionnées dans les hubs (app.optimization, app.insights) sous un bloc `<details>` replié par défaut intitulé "Outils avancés".
- Elles ne font pas partie du parcours marchand guidé.
- Elles ne sont jamais mises en avant comme étape nécessaire pour qu'une fonctionnalité principale fonctionne.

## Contrainte immuable

**Ne jamais supprimer ces routes.** Elles servent au debug pilote, aux marchands experts et aux imports manuels. Les retirer de la navigation suffit.
