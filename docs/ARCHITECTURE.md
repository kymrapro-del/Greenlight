# GREENLIGHT — Architecture

> Pré-clearance de scénario automatisé.
> Google Cloud (Gemini / ADK) + Parallel Search API.
> Hackathon *Agentic Cinema* — track **Parallel**.

---

## 1. Vue d'ensemble

```
                                  INTERNET
                                      │
                          ┌───────────┴───────────┐
                          │      Cloud DNS        │  greenlight.app
                          └───────────┬───────────┘
                                      │
                        ┌─────────────┴─────────────┐
                        │  Global External ALB      │  IP anycast + cert managé
                        │  + Cloud Armor (WAF)      │  OWASP, rate-limit, geo
                        └─────────────┬─────────────┘
                    ┌─────────────────┴─────────────────┐
            path /* │                                   │ path /api/*, /events/*
        ┌───────────▼──────────┐              ┌─────────▼──────────┐
        │  Backend Bucket      │              │  Serverless NEG    │
        │  + Cloud CDN         │              │  → Cloud Run       │
        │  (SPA M3 statique)   │              │     gl-api         │
        └──────────────────────┘              └─────────┬──────────┘
                                                        │
    ════════════════════════════════════════════════════╪════════════════════
                        VPC  gl-vpc  (us-central1)      │
    ════════════════════════════════════════════════════╪════════════════════
                                                        │
     ┌──────────────────────────────────────────────────┼───────────────┐
     │                                                  │               │
     │   ┌──────────────┐   Cloud Tasks    ┌────────────▼───────────┐   │
     │   │  gl-api      │─────────────────▶│  gl-orchestrator       │   │
     │   │  (ingress:   │   queue:orch     │  ADK agent runtime     │   │
     │   │   LB only)   │                  │  (ingress: internal)   │   │
     │   └──────┬───────┘                  └────────────┬───────────┘   │
     │          │                                       │ fan-out N     │
     │          │                          Cloud Tasks  │ (rate-limited)│
     │          │                          queue:research               │
     │          │                                       ▼               │
     │          │                          ┌────────────────────────┐   │
     │          │                          │  gl-research-worker    │   │
     │          │                          │  1 entité = 1 task     │   │
     │          │                          │  (ingress: internal)   │   │
     │          │                          └────────────┬───────────┘   │
     │          │                                       │               │
     │          │                          ┌────────────▼───────────┐   │
     │          │                          │  gl-render (PDF)       │   │
     │          │                          └────────────────────────┘   │
     │          │                                                       │
     │   ┌──────▼──────────────────────────────────────────────────┐    │
     │   │        Direct VPC egress  →  Cloud NAT (IP statique)    │    │
     │   └──────┬──────────────────────────────────┬───────────────┘    │
     └──────────┼──────────────────────────────────┼────────────────────┘
                │ Private Google Access            │ egress 443 allowlist
                │ (199.36.153.8/30)                │
     ┌──────────▼──────────┐            ┌──────────▼──────────┐
     │ Vertex AI (Gemini)  │            │  api.parallel.ai    │
     │ Firestore           │            │  Parallel Search    │
     │ Cloud Storage       │            └─────────────────────┘
     │ Document AI         │
     │ Secret Manager      │
     └─────────────────────┘
```

**Région unique : `us-central1`.** Choisie pour la disponibilité Gemini sur Vertex AI et la latence vers Parallel (US). Firestore en `nam5` (multi-région) pour la durabilité.

---

## 2. Architecture réseau

### 2.1 VPC

VPC custom-mode `gl-vpc` (jamais le réseau `default`).

| Sous-réseau | CIDR | Rôle |
|---|---|---|
| `gl-run-subnet` | `10.10.0.0/24` | Direct VPC egress des services Cloud Run |
| `gl-proxy-subnet` | `10.10.200.0/24` | Proxy-only subnet (`REGIONAL_MANAGED_PROXY`) |
| `gl-psc-subnet` | `10.10.10.0/28` | Endpoints Private Service Connect |

`privateIpGoogleAccess = true` sur `gl-run-subnet`.

### 2.2 Ingress

1. **Cloud DNS** — zone publique, A/AAAA vers l'IP anycast de l'ALB.
2. **Global External Application Load Balancer** — certificat managé Google, HTTP→HTTPS, HTTP/3 activé.
3. **Cloud Armor** — policy attachée au backend service :
   - règles préconfigurées OWASP (`sqli-v33-stable`, `xss-v33-stable`, `lfi`, `rce`)
   - rate limiting : 60 req/min/IP en `RATE_BASED_BAN` (ban 600 s)
   - `preview` d'abord, `enforce` ensuite — sinon tu te bloques toi-même en démo
4. **URL map** :
   - `/api/*`, `/events/*` → serverless NEG `gl-api`
   - `/*` → backend bucket `gl-frontend` + Cloud CDN (`CACHE_ALL_STATIC`, `index.html` en `no-cache`)

Tous les services Cloud Run sauf `gl-api` sont en `ingress = internal`.
`gl-api` est en `ingress = internal-and-cloud-load-balancing` — **il n'est pas joignable via son URL `run.app`**, uniquement via l'ALB. C'est ce qui rend Cloud Armor non contournable.

### 2.3 Egress

Les workers doivent joindre `api.parallel.ai`. Chemin :

```
gl-research-worker
  → Direct VPC egress (gl-run-subnet)
  → route par défaut
  → Cloud NAT (gl-nat)
  → IP externe statique réservée  ← Parallel voit toujours la même IP
  → api.parallel.ai:443
```

L'IP statique est le détail qui compte : elle est **allowlistable** côté Parallel, et elle donne une empreinte réseau stable pour l'audit.

Règles de pare-feu (`--direction=EGRESS`, priorité croissante) :

| Prio | Règle | Action |
|---|---|---|
| 1000 | `443/tcp` vers `199.36.153.8/30` (Private Google Access) | ALLOW |
| 1010 | `443/tcp` vers les plages Parallel | ALLOW |
| 65534 | `0.0.0.0/0` tout protocole | **DENY** |

Deny-all par défaut en sortie. Pour un allowlist par FQDN plutôt que par IP, remplacer par **Secure Web Proxy** (`api.parallel.ai` uniquement).

Trafic vers Vertex AI, Firestore, GCS, Document AI et Secret Manager : **Private Google Access**, jamais par l'internet public. Route statique `199.36.153.8/30` → `default-internet-gateway`, avec une zone Cloud DNS privée `googleapis.com` → CNAME `private.googleapis.com`.

### 2.4 Durcissement optionnel

**VPC Service Controls** — périmètre autour du projet incluant `storage.googleapis.com`, `firestore.googleapis.com`, `aiplatform.googleapis.com`. Les scénarios non tournés sont parmi les documents les plus confidentiels de l'industrie ; un périmètre qui rend l'exfiltration impossible même avec des credentials volés est un argument de vente réel, pas de la décoration.

---

## 3. Services Cloud Run

| Service | Ingress | CPU / RAM | Concurrency | Min / Max | Rôle |
|---|---|---|---|---|---|
| `gl-api` | LB only | 1 / 512 Mi | 80 | 1 / 20 | REST, auth, signed URLs, lecture rapports |
| `gl-orchestrator` | internal | 2 / 2 Gi | 4 | 0 / 10 | Runtime ADK, phases 1-3 et 5-7 |
| `gl-research-worker` | internal | 1 / 512 Mi | 20 | 0 / 60 | Fan-out Parallel, phase 4 |
| `gl-render` | internal | 2 / 2 Gi | 4 | 0 / 5 | Chromium headless → PDF |

`min-instances = 1` sur `gl-api` uniquement : les juges cliquent sur ton lien, ils ne doivent pas attendre un cold start.

Chaque service a **son propre service account**. Appels service-à-service authentifiés par **jeton OIDC** (`roles/run.invoker` accordé nominativement).

**Repli hackathon** — si le temps manque, fusionne `gl-orchestrator` + `gl-render` dans un seul service. Garde `gl-research-worker` séparé : c'est lui qui porte le parallélisme, et c'est le cœur de l'argument Parallel.

---

## 4. Le pipeline agentique

```
PHASE 1  INGEST
  PDF  → Document AI (Form/Layout Parser) → texte + coordonnées
  FDX  → parser XML natif
  Fountain → parser markdown natif           ← chemin le plus fiable
  ↓ normalisation : scènes {numéro, INT/EXT, lieu, moment, action, dialogue, page}

PHASE 2  EXTRACT                                    [Gemini · structured output]
  batch de 10 scènes par appel, en parallèle
  → entités typées + contexte de dépiction par occurrence
  temperature = 0, responseSchema strict

PHASE 3  CANONICALIZE                               [déterministe, pas de LLM]
  normalisation, résolution d'alias, dédup à l'échelle du script
  300 occurrences → ~120 entités uniques

PHASE 4  RESEARCH                                   [Parallel Search · fan-out]
  cache-lookup → miss → 1 Cloud Task par entité
  stratégie de requêtes spécifique par type
  → résultats + citations, écrits en Firestore

PHASE 5  CLASSIFY                                   [Gemini · structured output]
  entité + résultats + contexte de scène → verdict + justification + citations
  temperature = 0

PHASE 6  SUGGEST                                    [Gemini + Parallel]
  génère un remplacement → le re-cherche → ne le propose que si zéro résultat réel
  boucle max 3 tentatives

PHASE 7  REPORT
  rapport de clearance + annotations en marge → Firestore + PDF

PHASE 8  DIFF  (runs suivants)
  hash des entités v(n) vs v(n-1) → ne recherche que le delta
```

### 4.1 Structure ADK

```python
root = SequentialAgent(
    name="greenlight_clearance",
    sub_agents=[
        IngestAgent(),                                  # phase 1
        ParallelAgent(sub_agents=[ExtractionAgent()]),  # phase 2, batché
        CanonicalizeAgent(),                            # phase 3
        ResearchDispatchAgent(),                        # phase 4, enqueue + await
        ClassificationAgent(),                          # phase 5
        SuggestionAgent(),                              # phase 6
        ReportAgent(),                                  # phase 7
    ],
)
```

Tools exposés : `parallel_search`, `firestore_read`, `firestore_write`, `docai_parse`, `enqueue_research_task`.

**Modèle** : Gemini sur Vertex AI. Épingle l'ID exact du modèle dans la config au moment du build — vérifie la version courante dans la doc Vertex AI, ne code pas un identifiant en dur depuis une doc obsolète.

**Déterminisme** — le brief du hackathon exige un agent déterministe. Concrètement : `temperature = 0`, `responseSchema` sur toutes les sorties structurées, phase 3 en code pur sans LLM, et versionnage des prompts (`prompt_version` stocké sur chaque finding, pour que deux runs soient comparables).

### 4.2 Fan-out et reprise

```
orchestrator
  ├─ écrit jobs/{jobId}.counters = {total: 120, done: 0, failed: 0}
  ├─ enqueue 120 tasks → queue "research"
  └─ termine (pas d'attente bloquante)

queue "research"
  max_dispatches_per_second = 8       ← protège le quota Parallel
  max_concurrent_dispatches = 40
  max_attempts = 5, backoff 2s → 60s

chaque worker
  ├─ cache hit ? → écrit le résultat, fin
  ├─ sinon → Parallel Search → écrit le résultat + peuple le cache
  └─ transaction : counters.done += 1
       si done + failed == total → publie sur Pub/Sub "research-complete"

Pub/Sub "research-complete" → push → orchestrator reprend en phase 5
```

Pas d'attente synchrone : aucune requête ne peut dépasser le timeout Cloud Run. Idempotence par `taskName = hash(jobId, entityId)` — un rejeu ne duplique rien.

---

## 5. Données

### 5.1 Firestore (Native mode)

```
users/{uid}
  email, displayName, plan, createdAt

projects/{projectId}
  ownerUid, title, memberUids[], createdAt
  ├─ drafts/{draftId}
  │    version, gcsUri, format, pageCount, sceneCount,
  │    parentDraftId, uploadedAt
  │    └─ scenes/{sceneId}
  │         number, heading, intExt, location, timeOfDay,
  │         action, dialogue[], pageStart, pageEnd
  ├─ entities/{entityId}
  │    canonicalName, type, aliases[],
  │    occurrences[{draftId, sceneId, page, line}],
  │    worstContextTier          # neutral | unflattering | illegal
  └─ findings/{findingId}
       entityId, draftId, verdict, confidence,
       rationale, citations[{url, title, publisher, snippet, retrievedAt}],
       suggestedReplacement, replacementVerified, promptVersion

jobs/{jobId}
  projectId, draftId, state, phase,
  counters{total, done, failed}, startedAt, finishedAt, errorRef

entity_cache/{sha256(type + ':' + normalizedName)}
  type, name, payload, citations[], fetchedAt, ttlAt   # TTL policy 30j
```

**Index composites requis** :
`findings` → `(draftId ASC, verdict ASC, confidence DESC)`
`entities` → `(type ASC, worstContextTier DESC)`

**Le cache est le levier économique principal.** Il est global, pas par utilisateur : « Coca-Cola », « NYPD », « Mercy General » reviennent dans tous les scénarios. Au troisième script traité, le taux de hit dépasse largement les 50 %.

### 5.2 Cloud Storage

| Bucket | Contenu | Lifecycle | Accès |
|---|---|---|---|
| `gl-scripts-raw` | scénarios uploadés | delete 30 j | signed URL PUT, 15 min |
| `gl-reports` | PDF générés | delete 90 j | signed URL GET, 1 h |
| `gl-frontend` | build SPA | — | backend bucket + CDN |

Uniform bucket-level access, public access prevention **enforced**, versioning activé sur `gl-scripts-raw`. CMEK via Cloud KMS sur les deux premiers.

### 5.3 Taxonomie

**Types d'entités** — `CHARACTER_NAME`, `BUSINESS`, `PRODUCT_BRAND`, `PHONE`, `ADDRESS`, `LICENSE_PLATE`, `URL_EMAIL`, `SONG`, `ARTWORK`, `PUBLICATION`, `INSTITUTION`, `REAL_PERSON`, `REAL_EVENT`, `SPORTS_TEAM`, `VEHICLE`, `GOVERNMENT_AGENCY`.

**Verdicts** — `CLEAR`, `CAUTION`, `CHANGE_RECOMMENDED`, `LICENSE_REQUIRED`, `UNRESOLVED`.

`UNRESOLVED` est obligatoire. Un système qui prétend n'avoir aucune incertitude ment, et les juges le verront.

**Contexte de dépiction** — `neutral`, `unflattering`, `illegal`. C'est le multiplicateur de risque : la même entité réelle est `CLEAR` en contexte neutre et `CHANGE_RECOMMENDED` dès qu'un personnage y commet un délit. Cette règle-là est le cœur du produit, et c'est ce que Gemini apporte qu'une recherche seule n'apporte pas.

---

## 6. Sécurité et IAM

### 6.1 Authentification

Identity Platform (Google Sign-In). Le SPA obtient un ID token, `gl-api` le vérifie en middleware, et les Firestore Security Rules appliquent l'isolation :

```
match /projects/{pid} {
  allow read: if request.auth.uid in resource.data.memberUids;
  allow write: if request.auth.uid == resource.data.ownerUid;
}
match /jobs/{jid} {
  allow read: if request.auth.uid ==
    get(/databases/$(db)/documents/projects/$(resource.data.projectId)).data.ownerUid;
  allow write: if false;   // serveur uniquement
}
```

Le SPA lit `jobs/{jobId}` **en direct** via `onSnapshot` pour la progression temps réel — pas besoin de SSE, pas d'infra supplémentaire, et ça reste sécurisé par les rules.

### 6.2 Service accounts

| SA | Rôles |
|---|---|
| `sa-gl-api` | `datastore.user`, `storage.objectAdmin` (bucket raw), `cloudtasks.enqueuer`, `iam.serviceAccountTokenCreator` (signed URLs) |
| `sa-gl-orchestrator` | `aiplatform.user`, `datastore.user`, `cloudtasks.enqueuer`, `pubsub.publisher`, `documentai.apiUser` |
| `sa-gl-research` | `datastore.user`, `secretmanager.secretAccessor` **sur le seul secret `parallel-api-key`** |
| `sa-gl-render` | `datastore.viewer`, `storage.objectCreator` (bucket reports) |

Aucun rôle primitif (`editor`, `owner`). Aucune clé de SA exportée : identités managées uniquement.

### 6.3 Secrets

`parallel-api-key` dans Secret Manager, monté en variable d'environnement par référence de version. Rotation trimestrielle. La clé n'existe que dans `gl-research-worker` — les trois autres services ne peuvent pas la lire, même compromis.

---

## 7. Frontend — Material 3 intégral

### 7.1 Stack

React 19 + TypeScript + Vite. **`@material/web`** (Material Web Components, l'implémentation M3 officielle) — aucun composant maison, aucun Tailwind, aucun shadcn. Que du M3.

`@material/material-color-utilities` génère le schéma dynamique à partir d'une couleur source.

### 7.2 Système de couleur

Couleur source : **`#1B7F3B`** (le vert du feu vert de studio). Le générateur produit les palettes tonales complètes (primary, secondary, tertiary, error, neutral, neutral-variant, tons 0→100) et les deux schémas light et dark.

Tokens exposés en custom properties CSS : `--md-sys-color-*`, `--md-sys-typescale-*`, `--md-sys-shape-corner-*`, `--md-sys-elevation-level0..5`, `--md-sys-motion-easing-*`, `--md-sys-motion-duration-*`.

**Couleurs de verdict — via des rôles M3 étendus, jamais des hex bruts.** M3 supporte les couleurs personnalisées harmonisées avec la source ; c'est le mécanisme prévu, utilise-le.

| Verdict | Rôle |
|---|---|
| `CLEAR` | `--md-sys-color-tertiary-container` / `on-tertiary-container` |
| `CAUTION` | rôle étendu `warning` (source `#B8860B`, harmonisée) |
| `CHANGE_RECOMMENDED` | `--md-sys-color-error-container` / `on-error-container` |
| `LICENSE_REQUIRED` | `--md-sys-color-secondary-container` |
| `UNRESOLVED` | `--md-sys-color-surface-variant` |

Les contrastes sont garantis par construction — les paires `container` / `on-container` de M3 sont calculées pour respecter les seuils d'accessibilité.

### 7.3 Typographie

- **Roboto Flex** — l'axe variable de M3, sur toute l'interface. Échelle : `display-large` → `label-small`.
- **Courier Prime** — uniquement dans le panneau scénario. Les scénarios s'écrivent en Courier 12pt depuis toujours ; utiliser autre chose casserait immédiatement la crédibilité auprès d'un juge qui connaît le métier.

### 7.4 Layout — window size classes

| Classe | Largeur | Navigation | Layout canonique |
|---|---|---|---|
| Compact | < 600 | Navigation bar (bas) | pane unique + bottom sheet |
| Medium | 600–839 | Navigation rail | list-detail replié |
| Expanded | 840–1199 | Navigation rail | **list-detail** |
| Large / XL | ≥ 1200 | Navigation drawer | **supporting pane** (script + findings côte à côte) |

### 7.5 Écrans

1. **Dashboard** — grille de `md-elevated-card`, FAB « Nouveau scénario », large top app bar qui se réduit au scroll.
2. **Upload** — zone drag & drop, détection de format, `md-linear-progress`.
3. **Run** — stepper des 7 phases, compteur live via `onSnapshot`, progression déterminée dès la phase 4.
4. **Rapport** *(écran principal)* — list-detail. Gauche : liste filtrable, `md-filter-chip` par verdict et par type, badges de compte. Droite : détail du finding, citations cliquables, remplacement suggéré, bouton « Appliquer ».
5. **Script** — supporting pane. Panneau Courier avec surlignage inline des entités, clic → détail à droite.
6. **Diff** — v(n-1) vs v(n), `md-tabs` secondaires, seules les entités modifiées.
7. **Export** — PDF du rapport de clearance.

### 7.6 Motion

Tokens M3 exclusivement : `emphasized` (600 ms) pour les transitions d'écran, `standard` (300 ms) pour les changements d'état, `emphasized-decelerate` pour les entrées. Transitions **shared axis X** entre list et detail, **fade through** entre onglets. `prefers-reduced-motion` respecté globalement.

---

## 8. API

```
POST   /api/projects                          → {projectId}
POST   /api/projects/:pid/drafts/upload-url   → {gcsUri, signedUrl}
POST   /api/projects/:pid/drafts              → {draftId}   (confirme l'upload)
POST   /api/projects/:pid/drafts/:did/run     → {jobId}     (202 Accepted)
GET    /api/jobs/:jobId                       → état        (fallback si pas de SDK)
GET    /api/projects/:pid/drafts/:did/findings?verdict=&type=&cursor=
POST   /api/findings/:fid/apply               → applique le remplacement
GET    /api/projects/:pid/drafts/:did/diff?against=:draftId
POST   /api/projects/:pid/drafts/:did/report  → {reportUrl}  (signed URL PDF)
```

Interne (OIDC uniquement) :
```
POST   /internal/orchestrate      ← Cloud Tasks
POST   /internal/research         ← Cloud Tasks (1 entité)
POST   /internal/research-complete ← Pub/Sub push
POST   /internal/render           ← Cloud Tasks
```

---

## 9. Observabilité

- **Cloud Logging** — logs structurés JSON, corrélés par `jobId` et `traceId`.
- **Cloud Trace** — traces distribuées de bout en bout ; propagation du contexte à travers Cloud Tasks (indispensable pour voir où passent les 8 minutes).
- **Métriques custom** : `entities_extracted`, `cache_hit_ratio`, `parallel_latency_ms`, `verdict_distribution`, `job_duration_s`.
- **Dashboard Cloud Monitoring** + alertes : taux d'échec de job > 5 %, p95 durée > 15 min, erreurs Parallel > 2 %.
- **Error Reporting** sur tous les services.

*(Note : la stack Grafana appartient à un autre track du hackathon — reste sur l'observabilité GCP native, sinon tu brouilles ton positionnement.)*

---

## 10. CI/CD

```
GitHub push
  → Cloud Build
      ├─ lint + tests unitaires
      ├─ build images → Artifact Registry (scan de vulnérabilités)
      ├─ terraform plan/apply (infra)
      ├─ deploy Cloud Run --no-traffic --tag=candidate
      ├─ smoke test sur l'URL taguée
      └─ bascule 100 % du trafic
```

Infrastructure en **Terraform**, intégralement. Pas de clic dans la console : un juge qui regarde le repo doit pouvoir reconstruire l'environnement.

---

## 11. Coûts

Estimation pour **un scénario de 100 pages, ~120 entités uniques, cache froid** :

| Poste | Volume | Ordre de grandeur |
|---|---|---|
| Document AI | 100 pages | quelques centimes |
| Gemini extraction | ~15 appels, contexte moyen | faible |
| Parallel Search | ~120 requêtes | **poste dominant** |
| Gemini classification | ~120 appels courts | faible |
| Cloud Run | ~10 min cumulées | négligeable |
| Firestore / GCS | quelques milliers d'opérations | négligeable |

Avec le cache chaud, le nombre de requêtes Parallel chute fortement — c'est là que se joue la viabilité économique. Vérifie la grille tarifaire Parallel avant de chiffrer quoi que ce soit en public, et **mesure ton coût réel sur un vrai scénario** plutôt que de l'estimer : un chiffre mesuré dans la vidéo vaut dix fois une projection.

Les 100 $ de crédits GCP du hackathon couvrent largement le développement et la démo.

---

## 12. Plan de build — 6 jours

| Jour | Livrable |
|---|---|
| **1** | Terraform : VPC, NAT, Cloud Run × 2, Firestore, buckets, Secret Manager. Parser Fountain. Un appel Gemini d'extraction qui marche. |
| **2** | Pipeline phases 1→3 de bout en bout. Modèle de données Firestore figé. |
| **3** | Intégration Parallel + fan-out Cloud Tasks + cache. Phases 4→5. |
| **4** | Squelette M3 : thème, navigation, écrans Upload / Run / Rapport. Progression live. |
| **5** | Phases 6→8 : suggestions vérifiées, rapport PDF, **mode diff**. ALB + Cloud Armor + domaine. |
| **6** | Polish M3, README + licence, **tournage de la vidéo 3 min**, soumission Devpost. |

**Chemin critique** : le mode diff. C'est lui qui matérialise l'argument *shift-left* et qui différencie ton projet d'un simple « LLM + recherche web ». Si tu dois couper, coupe le PDF, coupe l'extension Google Docs — garde le diff.

**Ne repousse pas la vidéo au jour 6 au soir.** Tourne une version brouillon dès le jour 4 : ça révèle immédiatement ce qui manque à la démo.

---

## 13. Conformité hackathon

| Exigence | Réponse |
|---|---|
| Gemini + Google Cloud appelés au runtime | `google-adk` + `google-genai`, importés et appelés dans `gl-orchestrator` |
| Parallel appelé au runtime | SDK `parallel-web` dans `gl-research-worker` |
| Aucune IA non-Google | Gemini uniquement. **Aucun modèle OpenAI / Anthropic / autre dans le produit.** |
| Plateforme web | SPA hébergée derrière l'ALB |
| URL du projet hébergé | domaine public servi par l'ALB |
| Repo public + licence | GitHub, licence Apache 2.0 à la racine, détectable dans « About » |
| Projet nouveau | créé pendant la période du concours |
| Équipe ≤ 4 | ok |
| Agent déterministe multi-étapes | 8 phases, `temperature = 0`, schémas stricts, prompts versionnés |

---

## 14. Cadrage honnête

GREENLIGHT **ne remplace pas** le rapport de clearance officiel exigé par l'assureur E&O, et ne constitue pas un avis juridique. C'est un outil de **triage en amont** : attraper les problèmes pendant l'écriture, quand la correction est gratuite, et faire arriver le scénario chez le prestataire de clearance déjà propre.

Écris-le dans le README, dis-le dans la vidéo, affiche-le dans l'app. Un scope assumé se défend ; une promesse gonflée se démonte en une question du jury.
