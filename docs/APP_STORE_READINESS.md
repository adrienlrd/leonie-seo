# App Store Readiness — GEO by Organically

> Audit pré-soumission Shopify App Store + feuille de route badge **Built for Shopify (BFS)**.
> Date : 2026-07-05. Sources : audit complet du code (Remix `shopify-app/` + FastAPI `app/`), exigences officielles [App Store requirements](https://shopify.dev/docs/apps/launch/shopify-app-store/app-store-requirements) et [Built for Shopify requirements](https://shopify.dev/docs/apps/launch/built-for-shopify/requirements).

---

## Synthèse

| | Verdict |
|---|---|
| **Conformité technique App Store** | 🟢 Très bonne base — auth, billing, webhooks, scopes, sécurité sont corrects |
| **Bloqueurs avant soumission** | 🔴 4 points à corriger (détail §1) |
| **Listing & processus de review** | 🟠 Tout reste à préparer (assets, screencast, credentials de test) |
| **Badge Built for Shopify** | ⚪ Inatteignable au lancement par design : exige **50 installs payantes nettes + 5 avis + 28 jours de métriques**. Le code doit être prêt dès maintenant (il l'est presque), le badge se gagne après lancement |

Résumé du check de conformité automatisé (sous-ensemble vérifiable dans le code) :
**✅ Probablement conformes : 22 · ❌ Probablement non conformes : 1 · ⚠️ À vérifier manuellement : 5**
Note : Shopify re-vérifiera ces points et d'autres (navigateur, listing) lors de la review officielle.

---

## 1. Bloqueurs — à corriger AVANT de soumettre

### 1.1 ❌ `shop/redact` ne supprime pas les données de la boutique (GDPR)

- **Où :** `app/oauth/gdpr.py:79-96`
- **Problème :** le webhook `shop/redact` supprime uniquement le token OAuth (`delete_token`). Les fichiers `data/raw/{shop}/` (snapshots, analyses, exports) et les lignes dérivées en base **restent sur le serveur**. Shopify exige la suppression de *toutes* les données de la boutique 48 h après ce webhook.
- **À faire :** dans le handler `shop/redact`, purger le répertoire `data/raw/{shop}/` et toutes les tables liées au shop (billing, jobs, settings…). Ajouter un test.
- **Risque si ignoré :** rejet quasi certain — les webhooks GDPR sont vérifiés systématiquement.

### 1.2 ⚠️ Champ de saisie de clé API PageSpeed visible par le marchand

- **Où :** `shopify-app/app/onboarding/PageSpeedCard.tsx:63-83` (TextField password, placeholder `AIzaSy…`). `app.settings.tsx` est propre.
- **Problème :** demander au marchand de coller une clé API Google est un anti-pattern App Store (« Users should be able to start using the app immediately after installing it, without having to complete another sign up »). Décision déjà actée : masquer avant App Store, usage interne uniquement.
- **À faire :** retirer la carte du flux d'onboarding (ou la cacher derrière un flag env interne).

### 1.3 ⚠️ Hypothèse non vérifiée sur le serving des templates `llms.txt`

- **Où :** `app/apply/shopify_theme_files.py:31-36` (`REVIEW_NOTE` dans le code).
- **Problème :** tout le cas d'usage `write_themes` repose sur l'hypothèse que Shopify sert `/llms.txt`, `/llms-full.txt`, `/agents.md` depuis des templates Liquid `templates/llms.txt.liquid`. **Non confirmé sur une vraie boutique.** Si ça ne marche pas : fonctionnalité morte + scope `write_themes` injustifié = double motif de rejet (« deliver features described in listing » + « request only necessary scopes »).
- **À faire :** tester sur la boutique de dev. Si ça marche → supprimer la note. Si ça ne marche pas → retirer la feature du listing, garder `LEONIE_THEME_WRITE_MODE=disabled` et **retirer `read_themes,write_themes` des scopes**.

### 1.4 ⚠️ Badge « TODO » affiché au marchand

- **Où :** `shopify-app/app/routes/app.settings.tsx:70,119` — Badge Polaris avec le texte littéral « TODO ».
- **Problème :** texte placeholder visible = signal « app pas finie » pour le reviewer, et non-conforme au critère BFS « clear, grammatically correct language ».
- **À faire :** remplacer par un libellé réel (ex. « À configurer » / « To set up ») via `i18n.ts` (FR + EN).

---

## 2. À vérifier manuellement avant soumission (le code ne suffit pas)

1. **Billing — parcours complet sur boutique de dev :**
   - `app.billing.tsx:84-85` fait un `redirect(data.confirmation_url)` serveur depuis l'iframe embarqué. Vérifier que la page de confirmation Shopify s'ouvre bien **hors iframe** (sinon utiliser `open(url, '_top')` via App Bridge).
   - Tester : souscription → **refus** de la charge (l'app doit gérer le décliné proprement, pas de 500) → re-souscription. Puis **désinstaller / réinstaller** → l'app doit redemander l'approbation du plan sans erreur (`afterAuth` re-synchronise déjà le token, `shopify.server.ts:96-110` — bon signe).
   - Pas de flag `test: true` côté `appSubscriptionCreate` (`app/billing/client.py:28-33`) : sur une boutique de dev les charges sont automatiquement en mode test, mais ajouter le paramètre `test` piloté par env est plus sûr pour la review.
2. **Réinstallation complète :** désinstaller → réinstaller → OAuth immédiat → retour direct dans l'UI de l'app (pas de dead-end). Le code gère le cas (upsert token), à confirmer en réel.
3. **Incognito Chrome :** ouvrir l'app en navigation privée (cookies tiers bloqués). L'architecture session-token doit passer — à confirmer.
4. **TLS :** Render fournit HTTPS ; vérifier qu'aucune ressource n'est chargée en `http://` (mixed content) et que `application_url` + `redirect_urls` sont bien en prod.
5. **Persistance des données (fiabilité) :** les résultats d'analyse vivent dans `data/raw/{shop}/` sur disque Render. Si le disque est éphémère (pas de Persistent Disk attaché), un redéploiement efface les analyses des marchands → « core functionality must work reliably » en danger. Vérifier le plan Render actuel et attacher un disque persistant (ou migrer le stockage vers Postgres/S3) avant d'avoir de vrais marchands.
6. **Webhooks déployés :** `shopify app deploy` exécuté après le dernier changement de `shopify.app.toml` (les subscriptions produits/collections le nécessitent — noté dans le TOML lui-même).

---

## 3. Ce qui est déjà conforme (ne pas y retoucher)

| Exigence | Preuve |
|---|---|
| Session tokens, pas de cookies tiers | `authenticate.admin()` dans 100 % des routes `app.*` ; App Bridge CDN dernier (`root.tsx:24`) ; token exchange (`unstable_newEmbeddedAuthStrategy`) |
| OAuth immédiat à l'install & réinstall | Stratégie embedded + `afterAuth` re-sync token backend (`shopify.server.ts:96-110`) |
| Pas de saisie manuelle de domaine myshopify | Seul le formulaire de login boilerplate Shopify (`auth.login.tsx`) — accepté par la review |
| Billing via Billing API Shopify | `appSubscriptionCreate` GraphQL (`app/billing/client.py`), plan gratuit présent, changement de plan in-app, annulation in-app |
| Webhooks HMAC + réponse rapide | Vérification timing-safe, 401 si invalide, 200 immédiat, travail lourd déporté (`webhooks.tsx`) |
| Webhooks de conformité GDPR déclarés | `customers/data_request`, `customers/redact`, `shop/redact` dans le TOML + handlers (reste le bug §1.1) |
| Thèmes : API moderne, pas d'Asset API | `themeFilesUpsert/Delete` GraphQL 2025-01, allowlist stricte de 3 templates, Theme App Extension passive |
| Scopes tous justifiés | `write_products`→productUpdate/metafieldsSet, `write_content`→articleCreate, `themes`→templates llms.txt (sous réserve §1.3) |
| Pas de checkout/paiement/commande externe | Aucun code checkout, refund, ordre — confirmé |
| Pas de fake data / dark patterns | Aucun faux avis, fausse notification, countdown — confirmé |
| GraphQL Admin API (pas de REST déprécié) | Toutes les mutations en GraphQL, versions cohérentes (2025-01 / LATEST) |
| Sécurité interne | `X-Internal-Secret` comparé en temps constant (`deps.py:86-95`), pas de secret hardcodé, `.env` non tracké |
| UX embarquée | Polaris 13, `NavMenu`, error boundary (`app.tsx:52-57`), redirections externes uniquement pour le consentement Google OAuth (`_blank noopener`, justifié) |

---

## 4. Listing App Store — à préparer (hors code)

Tout ceci est requis pour la soumission et n'existe pas encore dans le repo :

1. **Nom & branding** : « GEO by Organically » cohérent entre Partner Dashboard, TOML et listing.
2. **Icône** : sans texte de prix, sans logo Shopify.
3. **Captures d'écran** : UI réelle uniquement, uniques, **sans URL `myshopify.com` visible**, sans fenêtre de navigateur, sans fond de bureau.
4. **Screencast de démo** : onboarding + fonctionnalités cœur, en anglais ou sous-titré anglais. C'est le point le plus souvent oublié.
5. **Description** : factuelle, **sans superlatifs** (« best », « first », « only »), sans stats invérifiables, sans « coming soon », sans témoignages. Mentionner clairement les prérequis (canal Online Store, thème OS 2.0 pour le bloc FAQ).
6. **Tarifs** : chaque plan payant clairement décrit ; aucun coût caché (les clés API tierces internes ne doivent pas être un prérequis, cf. §1.2).
7. **Credentials de test** : compte de démonstration fonctionnel donnant accès à toutes les features + **instructions de test** pour le reviewer (notamment : comment déclencher une analyse sans attendre des heures ; prévoir des données pré-chargées).
8. **Contact d'urgence développeur** dans le Partner Dashboard.
9. **Politique de confidentialité** : URL publique valide (servie par `app/api/privacy.py` — vérifier qu'elle est accessible sans auth).
10. **Support** : email/URL de support valides dans le listing.

---

## 5. Badge Built for Shopify — feuille de route

Le badge ne se demande pas à la soumission : il s'obtient **après** le lancement, quand tous les seuils sont atteints. Shopify ré-évalue ensuite au moins une fois par an.

### 5.1 Seuils d'adoption (non-code — c'est le vrai chemin critique)

| Critère | Seuil | État |
|---|---|---|
| Installs nettes sur boutiques actives payantes | ≥ 50 | 0 — post-lancement |
| Avis sur le listing | ≥ 5 | 0 — post-lancement |
| Note minimale récente | Seuil non publié | — |
| Compte Partner sans infraction | Obligatoire | À maintenir |

### 5.2 Performance admin (Web Vitals, p75, ≥ 100 mesures / 28 jours)

Mesuré automatiquement via App Bridge (déjà en place — le script CDN collecte les métriques) :

| Métrique | Seuil BFS | Risques identifiés dans le code |
|---|---|---|
| LCP | ≤ 2,5 s | Backend Render Free/Starter qui « dort » → premier load lent. Loaders qui attendent le backend Python : garder les fallbacks null (déjà fait) et éviter tout appel bloquant non essentiel dans le loader de `app._index` |
| CLS | ≤ 0,1 | Skeletons Polaris pendant les chargements pour éviter les sauts de layout (pattern polling 5 s : réserver la hauteur des cartes de résultats) |
| INP | ≤ 200 ms | `app._index.tsx` (128 Ko) et `app.blog.tsx` (110 Ko) sont volumineux ; Remix code-split par route donc acceptable, mais surveiller après lancement |

**Action clé :** garder le backend chaud (plan Render payant sans sleep, ou health-check ping) — c'est le premier facteur de LCP ici.

### 5.3 Performance storefront

- L'app ne doit pas dégrader le score Lighthouse de plus de **10 points**. Le seul code storefront est la Theme App Extension (`leonie-seo-jsonld`, bloc FAQ) : JSON-LD inline = impact quasi nul. ✅ par design — vérifier une fois avec Lighthouse avant/après activation du bloc.

### 5.4 Design & UX (critères BFS au-delà de l'App Store)

- [x] App entièrement utilisable dans l'admin (aucune étape hors admin sauf consentement Google OAuth, toléré car techniquement imposé par Google)
- [x] Polaris + NavMenu + latest App Bridge
- [ ] **Contextual save bar** sur les formulaires (settings, onboarding) — critère BFS explicite, à vérifier/ajouter
- [ ] Page d'accueil montrant **statut de setup + métriques de performance** — l'index actuel s'en approche, à confirmer contre la [checklist design](https://shopify.dev/docs/apps/design)
- [ ] Contraste WCAG 2.1 AA (Polaris le garantit si aucune couleur custom — vérifier les composants custom)
- [ ] Onboarding guidé et concis (existe : `app.onboarding.tsx` — retirer la carte PageSpeed, §1.2)
- [x] Pas de dark patterns, pas d'incitation aux avis 5 étoiles, pas de modales auto-ouvertes
- [ ] Features gatées par plan : visuellement **et** fonctionnellement désactivées (à vérifier écran par écran)

### 5.5 Utilisation immédiate après install

Critère BFS : « start using the app immediately after installing, without another sign-up ». Les intégrations GSC/GA4 (consentement Google) sont **optionnelles** — s'assurer que l'app délivre de la valeur (audit, analyse catalogue) sans elles, dès le premier écran.

---

## 6. Checklist d'exécution (ordre recommandé)

**Avant soumission (code)**
- [ ] 1.1 Purge complète des données shop sur `shop/redact` + test
- [ ] 1.2 Masquer la carte PageSpeed de l'onboarding
- [ ] 1.3 Vérifier le serving `llms.txt` sur boutique de dev → garder ou retirer `write_themes`
- [ ] 1.4 Remplacer les badges « TODO » (i18n FR + EN)
- [ ] Ajouter le flag `test` env-piloté sur `appSubscriptionCreate`
- [ ] Combler l'asymétrie i18n (~12 clés EN sans FR)

**Avant soumission (manuel)**
- [ ] Parcours billing complet : souscrire / refuser / changer de plan / désinstaller / réinstaller
- [ ] Test incognito Chrome
- [ ] Vérifier persistance disque Render (ou migrer le stockage)
- [ ] `shopify app deploy` (webhooks TOML)
- [ ] Politique de confidentialité accessible publiquement

**Soumission**
- [ ] Assets listing (§4) : icône, screenshots, screencast, description, tarifs
- [ ] Credentials + instructions de test pour le reviewer
- [ ] Contact d'urgence Partner Dashboard

**Post-lancement (badge BFS)**
- [ ] Backend toujours chaud (LCP)
- [ ] Contextual save bar + audit design BFS écran par écran
- [ ] Suivre Web Vitals dans le Partner Dashboard (28 jours glissants)
- [ ] Atteindre 50 installs payantes nettes + 5 avis → candidater au badge

---

## Ressources

- [App Store requirements](https://shopify.dev/docs/apps/launch/shopify-app-store/app-store-requirements)
- [Built for Shopify requirements](https://shopify.dev/docs/apps/launch/built-for-shopify/requirements)
- [Best practices for apps](https://shopify.dev/docs/apps/launch/shopify-app-store/best-practices)
- [About billing for your app](https://shopify.dev/docs/apps/launch/billing)
- [Submitting your app for review](https://shopify.dev/docs/apps/launch/app-store-review/submit-app-for-review)
- [New perks and criteria for Built for Shopify (2025)](https://www.shopify.com/partners/blog/built-for-shopify-updates)
- [How to pass the Shopify app store review the first time (Gadget)](https://gadget.dev/blog/how-to-pass-the-shopify-app-store-review-the-first-time-part-1-the-technical-bit)
