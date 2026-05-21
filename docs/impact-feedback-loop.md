# Impact Feedback Loop UX — Tâche 161

## Objectif

La page Mesure répond à une question simple : "Est-ce que ça a marché ?" Elle doit être lue en moins de 2 minutes, avec un verdict immédiat, avant les courbes techniques.

## Structure cible (ordre de lecture)

```
1. [Banner info] Rappel de valeur : les résultats sont mesurables uniquement si l'app reste active
2. [Verdict Win/Neutre/Risque] — chiffres par catégorie (déjà implémenté)
3. [Prochain résultat mesurable] — jalon J+7/J+30/J+60/J+90 le plus proche
4. [Courbes techniques] — score GEO/SEO, GSC, GA4 (détail)
5. [Optimisations en validation] — tableau
6. [Prochaines actions recommandées] — résumé NBA
7. [Visibilité IA] — encart V2 désactivé
8. [Bouton primaire] "Voir prochaines actions" → /app/next-best-actions
9. [Totaux] — metadata technique (snapshots, events)
```

## Jalons de mesure (J+X)

| Jalon | Signification marchand |
|---|---|
| J+7 | Premier signal de tendance (impressions, clics) |
| J+30 | Résultat stable sur 1 mois |
| J+60 | Confirmation de tendance |
| J+90 | Bilan complet — décision de répliquer ou de rollback |

## Retention message

Texte affiché en permanence (Banner info) :
- FR : "Les résultats sont mesurables uniquement si l'app reste active"
- EN : "Results are measurable only while the app stays active"

Ce message est affiché **une fois** (en haut de page), pas répété dans chaque section.

## Verdict widget (déjà implémenté)

- **Gain probable** (positif_probable) → badge success
- **Neutre** → badge warning
- **Inconclusif** → badge neutre
- **Risque** (négatif_possible) → badge critical

## CTA primaire en bas de page

Un seul bouton `variant="primary"` : "Voir prochaines actions" → `/app/next-best-actions`

Les liens "Rapport complet" et "Jalons de validation" restent en secondary.

## Fichier concerné

`shopify-app/app/routes/app.impact.tsx`
