# GREENLIGHT — Plan podium

**Deadline : mardi 9 septembre 2026, 14:00 PT = 23:00 heure de Paris.**
Il reste 6 jours pleins.

---

## 0. Principe directeur

Le jury voit, dans cet ordre : **la vidéo**, puis **le lien hébergé** (2 minutes de clics max), puis **le repo** (survolé), puis la description. Tout effort qui n'améliore pas ces quatre choses est du temps perdu.

Classement de la valeur par heure investie :

1. La vidéo de 3 minutes
2. Les 3 preuves « ce n'est pas un wrapper » : **diff**, **contexte de dépiction**, **remplacement re-vérifié**
3. Une démo hébergée qui affiche un rapport complet **en 3 secondes**
4. L'écran Rapport en M3, impeccable
5. Le README
6. Tout le reste

---

## 1. Coupes immédiates

Supprime, aujourd'hui, sans regret :

| Coupé | Pourquoi |
|---|---|
| Parsing PDF | Un piège chronophage. **Fountain + FDX uniquement.** Zéro point perdu au jury. |
| Document AI | Découle du point précédent. Économise aussi de l'argent. |
| Load Balancer + Cloud Armor | ~20 $/mois, zéro point. Le doc d'archi les documente en *design* : ça suffit. |
| Cloud NAT + VPC | ~32 $/mois, zéro point. Egress Cloud Run par défaut. |
| Export PDF | Le rapport à l'écran suffit largement. |
| Extension Google Docs | Belle idée, hors budget temps. Une slide « next step ». |
| VPC Service Controls | Documenté, pas construit. |

Ce qui reste à construire : **parser Fountain → pipeline 8 phases → Firestore → écran Rapport M3 → diff**. C'est tout.

---

## 2. Les trois leviers qui font le podium

### Levier 1 — Le scénario piégé

N'utilise pas un vrai scénario de film : problème de droits (l'ironie serait fatale) et tu ne contrôles pas les résultats.

**Écris toi-même un court scénario de 12-15 pages, délibérément truffé de pièges de clearance.** Un bar dont le nom existe vraiment, un personnage médecin homonyme d'un vrai praticien, un vrai numéro de téléphone (pas en 555), une marque citée dans une scène de délit, une chanson sous droits, une plaque d'immatriculation valide.

Trois avantages décisifs :
- tu contrôles chaque finding, donc zéro surprise pendant le tournage de la vidéo
- tu peux vérifier à la main que chaque verdict est **juste**
- ça devient une bonne ligne de README : *« nous avons écrit un scénario de test contenant 23 pièges connus ; le système en détecte 21 et signale 2 cas en UNRESOLVED »*

Et surtout : glisse **un piège volontairement inoffensif** — une entreprise réelle citée dans un contexte parfaitement neutre — pour que le système la classe `CLEAR`. C'est ta démonstration qu'il raisonne au lieu de tout peindre en rouge.

### Levier 2 — Le chiffre mesuré

Une seule phrase, mais mesurée, pas estimée :

> « Sur un scénario de 98 pages : 187 entités extraites, 23 signalées, 4 min 12 s, X $ d'API. Une passe de clearance manuelle prend environ une semaine et coûte plusieurs milliers de dollars. »

Un chiffre mesuré vaut dix projections. Chronomètre un vrai run et note-le.

### Levier 3 — La voix du métier

Contacte un scénariste ou un producteur cette semaine — LinkedIn, Reddit (r/Screenwriting), une école de cinéma, un festival. Une seule phrase de leur part, en citation dans le README ou en 5 secondes de voix dans la vidéo :

> « J'ai payé ça trois fois. C'est une semaine d'attente à chaque fois. »

Coût : quelques DM. Impact sur le critère *Potential Impact* : énorme. C'est la preuve que tu n'as pas inventé le problème depuis ton bureau. Aucun autre concurrent ne fera cet effort.

---

## 3. La démo hébergée

**Les juges ne vont pas uploader leur propre scénario et attendre 8 minutes.** S'ils tombent sur un écran d'upload vide, ils ferment l'onglet.

L'application doit s'ouvrir directement sur **un rapport pré-calculé**, complet, navigable, instantané. Un projet de démonstration seedé en base, chargé sans authentification.

À côté, un bouton **« Lancer une analyse réelle (2 min) »** sur un extrait de 5 pages, pour prouver que ce n'est pas une maquette.

Ce détail seul vaut plusieurs places au classement.

---

## 4. La vidéo — plan à la seconde

C'est 60 % de ta note. Tourne-la deux fois : un brouillon jour 3, la version finale jour 6.

| Temps | Contenu |
|---|---|
| **0:00–0:25** | **Le problème, en langage humain.** « Votre personnage entre dans un bar appelé Le Chat Noir et y achète de la drogue. Ce bar existe. Le patron vous attaque. » Puis : sans rapport de clearance, pas d'assurance ; sans assurance, pas de distribution. Une semaine, plusieurs milliers de dollars. **Aucun jargon technique ici.** |
| **0:25–0:40** | L'insight : ça se fait à la fin, quand les décors sont construits. Le corriger pendant l'écriture est gratuit. |
| **0:40–1:10** | Dépôt du scénario, pipeline qui tourne en direct, compteurs qui montent. |
| **1:10–1:50** | Le rapport. Zoom sur **un drapeau rouge avec ses sources cliquables**. Puis, juste après, la **même entreprise en contexte neutre, classée CLEAR** — voilà le raisonnement. |
| **1:50–2:10** | Bouton « suggérer une alternative » → nom généré → re-vérifié → zéro résultat réel. |
| **2:10–2:40** | **Le diff.** Draft v2, seules 6 entités re-analysées, 40 secondes. « Le clearance en intégration continue. » |
| **2:40–3:00** | Le chiffre mesuré + le cadrage honnête (triage en amont, pas d'avis juridique) + le stack en une phrase. |

Règles de tournage : capture d'écran nette, voix off enregistrée séparément et propre, sous-titres anglais, **aucune seconde d'écran de chargement non coupée**. Si une étape prend 40 secondes, accélère à l'image avec un badge « ×8 » visible — ne mens pas sur la vitesse.

---

## 5. Planning jour par jour

### Jour 1 — mercredi 3 (ce qu'il reste) + jeudi 4 matin
- Créer le compte Google Cloud (**essai gratuit 300 $** si nouveau compte)
- Créer le compte Parallel, **récupérer la clé API et chercher les crédits hackathon**
- Repo GitHub public + licence Apache 2.0 dès maintenant
- Parser Fountain fonctionnel
- Un appel Gemini d'extraction qui rend du JSON structuré valide sur une scène
- **Écrire le scénario piégé de 12-15 pages**

### Jour 2 — jeudi 4
- Pipeline phases 1→3 de bout en bout
- Schéma Firestore figé (ne plus y toucher après ce soir)
- **Enregistrer les fixtures Parallel** : capture des vraies réponses sur disque, rejouées en local. À partir d'ici, itérer ne coûte plus rien.

### Jour 3 — vendredi 5
- Intégration Parallel réelle + fan-out Cloud Tasks + cache global
- Phases 4→5, verdicts qui sortent
- **Brouillon de vidéo, même moche.** Il révèle immédiatement ce qui manque.

### Jour 4 — samedi 6
- Thème M3 (couleur source, palettes tonales, rôles de verdict)
- **Écran Rapport uniquement**, en list-detail, impeccable
- Progression live via `onSnapshot`

### Jour 5 — dimanche 7
- Phase 6 (remplacements re-vérifiés) + phase 8 (**diff**)
- Seeding du projet de démonstration
- Déploiement Cloud Run + Firebase Hosting, URL publique testée depuis une navigation privée
- **Soumission Devpost en brouillon dès ce soir** — Devpost autorise l'édition après soumission. Une panne lundi ne doit pas te mettre à zéro.

### Jour 6 — lundi 8
- Écrans Upload et Run (le minimum viable)
- README complet, description Devpost
- **Vidéo finale**
- Finalisation de la soumission

### Mardi 9 — tampon
Rien de prévu. C'est le jour où tu rattrapes ce qui a dérapé. Ne planifie rien dessus.

---

## 6. Coûts — objectif zéro euro

### Crédits — vérifiés sur les pages ressources du Devpost

**Parallel — automatique, aucun code promo.**
Citation de la page ressources Parallel : *« No separate hackathon promo code needed — everyone who signs up for Parallel automatically receives credits (between $20–$80, depending on email type, region, and other factors). »*
En plus : **5 $ de crédits gratuits récurrents chaque mois** en ajoutant une carte bancaire, **sans prélèvement**.
→ Inscris-toi aujourd'hui et note le montant exact reçu : c'est lui qui dimensionne ton budget de requêtes.

**Google Cloud — deux voies.**
1. **Essai gratuit : 300 $ sur 90 jours** pour un compte neuf (`cloud.google.com/free`). C'est la voie principale.
2. **Formulaire de 100 $ de crédits hackathon** pour un compte existant. ⚠️ Contradiction dans les documents : le règlement officiel donne comme limite le **31 août 2026** (passée), alors que la page ressources liste toujours le formulaire sans date, avec la mention *« while supplies last »* et *« approved within 1–5 business days »*.
→ Remplis-le quand même, ça coûte 2 minutes. Mais **ne planifie rien dessus** : même approuvé, le délai de 1 à 5 jours ouvrés peut tomber après la deadline.

**Replit** dispose aussi d'un formulaire de crédits dédié — sans objet pour toi, tu es sur le track Parallel.

**Conclusion : le projet est finançable à 0 € de ta poche.** Les crédits Parallel couvrent le poste le plus incertain, et l'essai GCP couvre tout le reste. Les coupes ci-dessous restent valables : elles évitent de brûler les crédits pour rien.

### Ce qui reste gratuit (free tier permanent)

| Service | Free tier | Ton usage |
|---|---|---|
| Cloud Run | 2 M requêtes, 180 k vCPU-s / mois | largement dedans |
| Firestore | 50 k lectures, 20 k écritures / jour | dedans |
| Cloud Storage | 5 Go | dedans |
| Cloud Tasks | 1 M opérations / mois | dedans |
| Pub/Sub | 10 Go / mois | dedans |
| Secret Manager | 6 versions actives | dedans |
| Cloud Build | 2 500 min / mois | dedans |
| Cloud Logging | 50 Gio / mois | dedans |
| Firebase Hosting | 10 Go, domaine + SSL inclus | dedans |

### Ce qui coûte vraiment

**1. Les tokens Gemini** — pas de free tier sur Vertex AI.
→ Astuce : `google-genai` fonctionne **aussi** avec l'API Gemini via AI Studio, **qui a un free tier**, et ce package est explicitement accepté par le règlement. Développe dessus, puis bascule sur Vertex pour le déploiement final : c'est un seul flag (`vertexai=True`) et une variable d'environnement.
→ Deuxième levier : utilise le **modèle Flash** pour l'extraction (gros volume, tâche simple) et réserve le modèle Pro à la classification. Divise la facture par un ordre de grandeur.

**2. Parallel Search API** — couvert par les crédits automatiques (20–80 $), mais c'est un budget fini.
→ Levier technique : les **fixtures enregistrées**. Capture les vraies réponses une fois, rejoue-les depuis le disque pour toutes tes itérations d'UI et de pipeline. Tu ne paies que quelques dizaines de requêtes réelles sur toute la semaine — sinon tu brûles tes crédits en deux jours de debug.
→ En cas de problème : `support@parallel.ai`, indiqué sur la page ressources.
→ Développe sur le scénario de 12 pages (~30 entités), pas sur 100 pages (~180 entités).

**3. Ce qu'il ne faut surtout pas allumer**

| Piège | Coût |
|---|---|
| Load Balancer global | ~18 $/mois, dès la première minute |
| Cloud NAT | ~32 $/mois |
| Cloud Armor | ~5 $/mois + par règle |
| `min-instances = 1` | facturation permanente, casse le free tier |
| Document AI | facturé à la page |

Laisse `min-instances = 0` pendant tout le développement. Passe à 1 **uniquement le 8 au soir**, pour que les juges n'aient pas de cold start — et remets à 0 après la période de jugement.

### Garde-fous

```bash
# Alerte budget à 5 € — à faire AVANT d'écrire la moindre ligne de code
gcloud billing budgets create \
  --billing-account=BILLING_ID \
  --display-name="greenlight-guard" \
  --budget-amount=5EUR \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9
```

Et une fois le jugement terminé : **supprime le projet GCP**. C'est la seule garantie qu'aucun service oublié ne tourne.

### Total réaliste

**0 € de ta poche.** Crédits Parallel (20–80 $) + essai GCP (300 $) couvrent tout, à condition de ne pas allumer les services facturés en permanence et d'utiliser les fixtures pendant le développement.

---

## 6 bis. Signal important de la page ressources

Le guide officiel dit textuellement : *« We recommend building your agents natively using the Agent Development Kit (ADK) instead of external wrapper libraries »*, et pousse le déploiement sur **Vertex AI Agent Engine** plutôt que sur Cloud Run.

C'est une indication directe de ce que les juges veulent voir. Deux conséquences :

- **Utilise ADK nativement**, pas LangChain ni un wrapper tiers. Installation officielle recommandée :
  ```
  pip install "google-cloud-aiplatform[agent_engines,adk]>=1.101.0"
  ```
- **Déployer l'agent sur Agent Engine** plutôt que sur Cloud Run coche une case supplémentaire sur le critère *Technological Implementation*. Compare le coût avec ton reliquat de crédits avant de trancher ; en cas de doute, Cloud Run reste acceptable, mais mentionne Agent Engine dans le README.

Autre détail utile : la page ressources référence **Gemini 3.1 Flash**. Confirme l'identifiant exact du modèle dans la doc Vertex AI au moment du build, mais tu es bien sur la famille Gemini 3.x.

---

## 7. Point de vigilance règlement

Le règlement interdit toute IA non-Google **dans le projet** : « No other AI models, agent frameworks, or AI APIs are permitted », en citant nommément OpenAI et Anthropic.

Cette clause vise clairement la stack du produit, et non l'outillage de développement — les tracks IBM et Replit *exigent* d'ailleurs l'usage de leurs propres agents pour coder. Mais la formulation reste ambiguë sur les assistants de code.

**Action, 5 minutes, à faire aujourd'hui :** envoie un mail au hackathon manager pour faire confirmer que l'usage d'un assistant de code non-Google pendant le développement ne pose pas de problème, tant que le produit livré n'appelle que Gemini. Garde la réponse. Le risque est faible mais la conséquence serait la disqualification — ça ne vaut pas le pari.

Dans tous les cas : **aucun modèle non-Google dans le code livré.**

---

## 8. Checklist de soumission

- [ ] Repo public, licence Apache 2.0 **détectable dans la section About de GitHub**
- [ ] `google-adk` ou `google-genai` importé et **réellement appelé**
- [ ] `parallel-web` importé et **réellement appelé**
- [ ] Aucun SDK d'IA non-Google dans les dépendances (vérifie `requirements.txt` / `package.json`)
- [ ] URL publique testée en navigation privée, sur un autre réseau
- [ ] Vidéo YouTube **publique** (pas « non répertoriée »), en anglais ou sous-titrée
- [ ] Vidéo ≤ 3 minutes
- [ ] Track **Parallel** sélectionné dans le formulaire
- [ ] Description : features, technos, sources de données, apprentissages
- [ ] README avec instructions de lancement reproductibles
- [ ] Disclaimer de cadrage visible dans l'app et le README
- [ ] Soumis **le 7 en brouillon**, finalisé le 8
