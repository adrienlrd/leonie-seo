# Merchant Language Pass — Tâche 157

## Objectif

Remplacer les termes techniques visibles dans l'app par des termes compréhensibles par un marchand sans formation SEO ou IA. Les termes techniques restent dans le code (noms de variables, logs, mode avancé).

## Glossaire FR / EN

| Terme technique | Terme marchand FR | Terme marchand EN | Niveau |
|---|---|---|---|
| GEO / AI Search | Visibilité IA | AI Visibility | Masqué au premier niveau |
| AI Search Readiness | Santé SEO de votre boutique | Your store's SEO health | Score tooltip |
| Product Facts Layer | Informations produit fiables | Reliable product info | Mode avancé uniquement |
| JSON-LD / Schema | Données produit structurées | Structured product data | Mode avancé uniquement |
| Crawl L3 | Vérification technique | Technical check | Mode avancé uniquement |
| GSC Opportunities | Opportunités Google | Google opportunities | Niveau 2 |
| Priority Engine | Actions prioritaires | Priority actions | Standard |
| Safe Apply / dry-run | Prévisualiser | Preview | Standard |
| live_apply | Publier | Publish | Standard |
| decision: accept | Valider | Approve | Standard |
| decision: reject | Refuser | Decline | Standard |
| Impact Ledger | Historique des optimisations | Optimization history | Standard |
| Niche Understanding | Ce que l'IA a compris | What the AI understood | Standard |
| Content Actions | Améliorations proposées | Proposed improvements | Standard |
| Rollback | Annuler une modification | Undo a change | Standard |
| status: draft | En attente | Pending | Standard |
| status: needs_review | À valider | To review | Standard |
| status: approved | Validé | Approved | Standard |
| status: applied | Publié | Published | Standard |
| status: rejected | Refusé | Declined | Standard |
| product_title (content type) | Titre produit | Product title | Standard |
| product_description | Description produit | Product description | Standard |
| meta_title | Titre SEO | SEO title | Standard |
| meta_description | Description SEO | SEO description | Standard |
| revenue_estimate_eur | Gain estimé | Estimated gain | Standard |

## Termes interdits au premier niveau (page principale, visible sans clic)

- GEO, AI Search Readiness, JSON-LD, llms.txt, Crawl L3, Product Facts, Impact Ledger (utiliser "Historique"), dry-run (utiliser "Prévisualiser"), content_type / resource_id bruts, level strings bruts ("excellent", "bon", "faible" — passer par i18n)

## Règles i18n

1. Toute chaîne visible par le marchand passe par `t(locale, key)`.
2. Aucun texte hardcodé dans les JSX sauf dans le mode avancé repliable.
3. Les valeurs internes du backend (statuts, types) sont mappées côté frontend avant affichage.
4. Les erreurs techniques ("length_out_of_bounds", "language_mismatch") sont traduites en libellés marchands.

## Clés i18n ajoutées (task 157)

Voir `shopify-app/app/lib/i18n.ts` — nouvelles clés :
`safeApplyNoBadPublish`, `statusDraft`, `statusNeedsReview`, `statusApproved`, `statusApplied`, `statusRejected`, `acceptAction` (→ Valider), `dryRunAction` (→ Prévisualiser), `applyLive` (→ Publier), `rejectAction` (→ Refuser), `lengthOutOfBounds`, `languageMismatch`, `contentTypeProductTitle`, `contentTypeProductDescription`, `contentTypeMetaTitle`, `contentTypeMetaDescription`, `dashboardScoreTooltip`, `estimatedGain`, `prepareAction`, `impactRetentionMessage`, `impactNextMilestoneLabel`, `impactViewNextActions`, `productReference`
