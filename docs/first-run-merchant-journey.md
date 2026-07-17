# First-Run Merchant Journey — GEO by Organically

> Référence Phase 11.9, tâche 152. Ce document définit le parcours marchand de première utilisation, de l'installation à la première action appliquée, sans ajouter de nouveau moteur SEO/GEO.
>
> Statut : implémentation initiale démarrée le 2026-05-21. Le premier ajustement produit associé masque les détails JSON de la compréhension IA derrière un mode avancé.

---

## 1. Promesse du parcours

Le marchand ne doit pas voir une collection d'outils. Il doit suivre un assistant unique qui :

1. connecte les sources utiles ;
2. comprend la boutique ;
3. demande validation humaine ;
4. analyse la visibilité ;
5. propose 3 actions maximum ;
6. applique seulement après accord ;
7. mesure l'impact.

Phrase cible :

> "Je connecte Google, l'IA comprend ma boutique, je valide ce qu'elle a compris, puis elle me propose les 3 meilleures actions à faire maintenant."

---

## 2. Parcours linéaire cible

| Étape | Écran attendu | CTA principal | État vide | État erreur | Critère de passage |
|---|---|---|---|---|---|
| 1 | Accueil première connexion | Connecter Google | Aucune donnée Google connectée | Connexion Google refusée ou expirée | Google Search Console connecté |
| 2 | Connexions | Continuer | GA4 absent, présenté comme recommandé | Compte Google sans propriété lisible | GSC actif ; GA4 optionnel |
| 3 | Compréhension boutique | Analyser ma boutique avec l'IA | L'IA n'a pas encore analysé la boutique | Analyse indisponible, message marchand | Hypothèse IA générée |
| 4 | Ce que l'IA a compris | Valider | Panneaux Boutique, Voix, Clients, Intentions et À éviter vides | Données incohérentes ou JSON avancé invalide | Hypothèse validée par le marchand |
| 5 | Analyse visibilité | Voir mes actions | Analyse en cours | Analyse interrompue, relance possible | Score SEO/GEO lisible et actions calculées |
| 6 | Accueil | Voir l'action prioritaire | Aucune action disponible | Données insuffisantes | 3 actions maximum visibles |
| 7 | Détail action | Prévisualiser | Aucun brouillon généré | Preview impossible | Avant/après visible |
| 8 | Application sécurisée | Appliquer en sécurité | Dry-run disponible uniquement | Application refusée ou validation manquante | Action appliquée ou rejetée explicitement |
| 9 | Mesure | Voir l'impact | Mesure en attente | Données Google absentes | Événement mesurable créé |

---

## 3. Règles UX obligatoires

- Un seul CTA principal par écran.
- Les actions secondaires restent visibles mais moins dominantes.
- Les termes techniques ne sont jamais l'objet principal de l'écran.
- Les détails JSON, logs, endpoints, crawl, schema et données internes restent en mode avancé.
- Les informations validées par le marchand alimentent ensuite les analyses, recommandations, contenus, priorités et mesures.
- Le parcours standard s'arrête si la compréhension IA n'est pas validée, sauf accès aux réglages et au mode avancé.
- L'application Shopify reste en dry-run par défaut.
- Aucune promesse de ranking garanti n'est affichée.
- Search Performance et Visibilité IA restent séparées.

---

## 4. Briques existantes réutilisées

| Besoin parcours | Brique existante |
|---|---|
| Connexion Google | OAuth Google, Google Search Console, GA4 |
| Compréhension boutique | Niche Understanding |
| Validation humaine | `niche_hypothesis.status = validated_by_merchant` |
| Analyse visibilité | Unified Readiness Audit, Opportunity Finder |
| 3 actions maximum | Priority Engine |
| Prévisualisation | AI Content Actions |
| Application | Safe Apply, dry-run, review humaine |
| Annulation | Rollback |
| Mesure | Impact Tracker, Dashboard marchand |

---

## 5. Écran "Ce que l'IA a compris"

Cet écran devient le premier point de confiance. Il doit afficher en clair :

- niche principale ;
- produits importants ;
- segments clients ;
- motivations d'achat ;
- objections probables ;
- promesses à éviter ;
- niveau de confiance.

Le JSON brut ne fait pas partie du parcours marchand standard. Il reste disponible uniquement dans un bloc avancé replié pour correction fine ou diagnostic agent.

CTA principal : **Valider**.

CTA secondaire : **Enregistrer**.

CTA de relance : **Analyser**.

---

## 6. Ce qui ne doit pas être ajouté

- Nouveau moteur SEO/GEO.
- Nouveau score global mélangeant Google et IA.
- Nouvelle route principale.
- Nouveau hub de fonctionnalités.
- Dépendance Screaming Frog.
- Application Shopify automatique sans validation humaine.
- Promesse de ranking Google, ChatGPT, Perplexity, Gemini ou AI Overviews.
- Exposition des détails LLM au marchand hors mode avancé.

---

## 7. Critères de validation tâche 152

- La roadmap pointe vers un parcours marchand complet.
- Le parcours couvre de la première connexion à la première action appliquée.
- Chaque étape a un écran, un CTA, un état vide, un état erreur et un critère de passage.
- Le lien avec les briques Phase 11.8 est explicite.
- Le premier ajustement UX masque au moins un détail technique visible hors mode avancé.
- Aucune fonctionnalité SEO/GEO nouvelle n'est introduite.
