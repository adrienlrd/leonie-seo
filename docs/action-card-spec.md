# Action Detail Unification — Tâche 159

## Objectif

Chaque recommandation d'action exposée au marchand suit un modèle de carte unique, quel que soit l'écran (accueil, Top 3 Actions, mode avancé). Cette uniformité réduit la charge cognitive et simplifie la décision.

## Modèle de carte action unifiée

```
┌──────────────────────────────────────────────────┐
│  #1  [Nom du produit]                            │
│  [Libellé de l'action]                           │
│                                                  │
│  Pourquoi maintenant :                           │
│  [why_now en langage marchand]                   │
│                                                  │
│  Confiance: [badge]  Effort: [badge]  Risque: [badge]  │
│  Gain estimé : [revenue_estimate_eur] €          │ ← si disponible
│                                                  │
│  Métrique de succès :                            │
│  [name]: [current] → [target] (mesure à Jxx)    │
│                                                  │
│  [!] Avertissement niche (si présent)            │
│                                                  │
│  [  Préparer cette action  ]  ← CTA primaire    │
└──────────────────────────────────────────────────┘
```

## Champs obligatoires

| Champ | Source backend | Affichage |
|---|---|---|
| Rang | `rank` | Badge "#1", "#2", "#3" |
| Nom produit | `product_title` | Titre heading |
| Libellé action | `action_label` | Texte semibold |
| Pourquoi maintenant | `why_now` | Bloc encadré |
| Confiance | `estimates.confidence` | Badge coloré (high=success, medium=info, low=warning) |
| Effort | `estimates.effort` | Badge coloré |
| Risque | `risk_guard.status` | Badge coloré (safe=success, review_required=warning, protected=critical) |
| Gain estimé | `estimates.revenue_estimate_eur` | Badge success "Gain estimé : X €" (si > 0) |
| Métrique de succès | `success_metric` | Texte current→target |
| Alertes niche | `niche_alerts` | Banners warning |
| CTA | lien vers `/app/safe-apply` | Button variant="primary" |

## Champs exclus du premier niveau

- `priority_score` brut (remplacé par le rang et la barre de progression)
- `evidence[]` (mode avancé uniquement)
- `risk_guard.reasons[]` (accessible en detail si risque = protected)
- `estimates.estimate_basis` (mode avancé)

## Implémentation

- `shopify-app/app/routes/app.priorities.tsx` — carte action complète
- `shopify-app/app/routes/app._index.tsx` `ActionCard` — carte résumée (rang + label + why_now + effort/impact + CTA)

La carte accueil est intentionnellement plus courte (pas de métrique de succès, pas d'alertes niche) pour rester dans un InlineGrid 3 colonnes.
