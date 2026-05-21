# Dashboard as Single Command Center — Tâche 155

## Objectif

L'accueil est le seul endroit où un marchand décide quoi faire ensuite. Il ne doit pas ressembler à un tableau de bord technique mais à une réponse simple à la question : "Que dois-je faire aujourd'hui pour progresser ?"

## Structure cible (6 zones ordonnées par priorité)

| Zone | Contenu | Condition d'affichage |
|---|---|---|
| **Zone 1** | Score SEO global + résumé de ce que l'IA a compris + CTA principal | Toujours visible |
| **Zone 2** | 3 actions prioritaires (ou gate si IA non validée) | Toujours visible |
| **Zone 3** | Optimisations en cours + sparkline + prochain bilan | Si optimisations actives |
| **Zone 4** | Étapes de configuration restantes | Si pending_steps > 0 |
| **Zone 5** | Alertes actives (3 max) | Si alerts > 0 |
| **Zone 6** | — (retiré de l'affichage V1) | Aucune (V2) |

## Règles

1. **Un CTA dominant par état** :
   - Si IA non validée → Zone 1 affiche le CTA primaire "Valider ce que l'IA a compris"
   - Si IA validée → chaque ActionCard affiche son propre CTA primaire

2. **Aucun terme technique visible en Zone 1-3** :
   - Pas de "GEO", "crawl", "JSON-LD", "schema", "GSC raw data"
   - Le score affiché = "Santé SEO de votre boutique"
   - Le badge de niveau = libellé marchand ("Excellent", "Bon", "En progrès", "À améliorer")

3. **Zone 6 masquée** :
   - "Visibilité IA" est une fonctionnalité V2 non disponible
   - L'afficher vide crée de la confusion et de la fausse attente

## Briques existantes réutilisées

- `app/api/dashboard.py` — endpoint `GET /dashboard` avec 6 zones
- `shopify-app/app/routes/app._index.tsx` — composants Zone1-6 inline
- `shopify-app/app/lib/i18n.ts` — clés `dashboard*`

## Critères de validation

- [ ] Le marchand voit son score SEO + résumé IA dès la première ligne
- [ ] S'il n'a pas validé l'IA → un seul bouton vert ("Valider ce que l'IA a compris")
- [ ] S'il a validé → 3 cartes d'action chacune avec un bouton "Préparer cette action"
- [ ] Aucune mention de "GEO", "crawl", "schema", "JSON-LD" en Zone 1-3
- [ ] Zone 6 absente de la page
