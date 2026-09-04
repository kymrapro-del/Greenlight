# GREENLIGHT — Architecture

> Pré-clearance de scénario automatisé.
> Google Cloud (Gemini / ADK) + Parallel Search API.
> Hackathon *Agentic Cinema* — track **Parallel**.

---

## 0. Comment lire ce document

Ce document décrit deux choses, et il serait malhonnête de les confondre.

| Marque | Signification |
|:---:|---|
| 🟢 | **Construit.** Le code existe dans ce dépôt, les tests le couvrent. |
| 🔵 | **Conçu.** La décision est prise et documentée, rien n'est déployé. |
| ⚪ | **Écarté.** Étudié, puis coupé — la raison est indiquée. |

Une architecture cible sans mise en œuvre reste un travail utile : elle dit où
le système va, et pourquoi les raccourcis d'aujourd'hui sont des raccourcis et
non des impasses. Mais elle ne doit jamais se lire comme un inventaire de ce qui
tourne. La distinction est portée par ces marques, section par section.

**État au 4 septembre 2026.** Ce qui tourne : le parser Fountain, les huit
phases du pipeline, la couche ADK, l'API HTTP et l'interface Material 3 —
en local, et en CI sans un appel réseau. Le reste de ce document est la cible.

---

## 1. Vue d'ensemble

### 1.1 🟢 Ce qui tourne aujourd'hui

```
  navigateur
      │  POST /api/analyze  ·  lit le flux SSE de progression
      ▼
  greenlight.api.server            FastAPI, un processus
      │  passes gardées en mémoire, plafonnées
      ▼
  greenlight.pipeline              les 8 phases, en appelant un PhaseHook
      ├─ ingest/fountain           Fountain → scènes            phase 1
      ├─ agents/extract            Gemini, une scène = un appel phase 2
      ├─ agents/dedupe             canonicalisation, sans LLM   phase 3
      ├─ agents/research           Parallel, fan-out en threads phase 4
      ├─ agents/classify           Gemini, verdicts sourcés     phase 5
      ├─ agents/replace            générer → re-vérifier        phase 6
      ├─ api/report                → la charge utile du rapport phase 7
      └─ agents/diff               réutiliser d'un jet à l'autre phase 8
      │
      ├──▶ Gemini      (Vertex AI ou AI Studio, un drapeau)
      └──▶ Parallel Search
              ↑
        harnais de fixtures : live / record / replay
```

Un processus, pas de base de données, pas de file. Le fan-out est un
`ThreadPoolExecutor`, la reprise n'existe pas, et les passes vivent en mémoire.
C'est suffisant pour un scénario de long métrage et c'est écrit tel quel dans
`greenlight/store/runs.py`, avec la limite que ça pose.

### 1.2 🔵 La cible, à l'échelle

Ce qui suit n'est pas déployé. C'est la topologie vers laquelle le système va
quand plusieurs passes tournent en même temps et qu'une reprise doit survivre à
un redémarrage.

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

## 2. 🔵 Architecture réseau

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

## 3. 🔵 Services Cloud Run

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

### 4.1 🟢 Les huit phases, telles qu'elles tournent

```
PHASE 1  INGEST                                     [déterministe]
  Fountain → parser natif  ·  FDX → parser XML natif
  ↓ scènes {numéro, INT/EXT, lieu, moment, action, dialogue, page estimée}
  Le PDF est écarté : voir §12.

PHASE 2  EXTRACT                                    [Gemini · sortie structurée]
  UNE scène = UN appel, en parallèle sur un ThreadPoolExecutor
  → entités typées ET contexte de dépiction, par occurrence
  temperature = 0, responseSchema pydantic strict
  garde-fou : une entité absente verbatim du texte est écartée avant tout achat

PHASE 3  CANONICALIZE                               [déterministe, pas de LLM]
  normalisation, résolution d'alias, dédup à l'échelle du script
  ids stables, pour que la phase 8 puisse comparer deux jets

PHASE 4  RESEARCH                                   [Parallel Search · fan-out]
  pré-verdicts par règle d'abord — 555-01XX, RFC 2606, agences neutres —
  puis cache global, puis fan-out en threads sur ce qui reste
  profondeur choisie par entité : `fast` en masse, `advanced` là où le
  verdict est réellement en jeu

PHASE 5  CLASSIFY                                   [Gemini · sortie structurée]
  le modèle ne juge QUE sur les extraits fournis
  une URL citée mais absente des résultats est écartée
  un verdict défavorable sans source vérifiable retombe à UNRESOLVED
  puis la règle de dépiction combine existence et mise en scène

PHASE 6  SUGGEST                                    [Gemini + Parallel]
  téléphone et e-mail : convention professionnelle, sans appel ni recherche
  le reste : générer un remplacement → le repasser par la même recherche
  proposé quand même s'il n'est pas vérifiable, mais étiqueté comme tel
  rien n'est proposé là où renommer serait un mauvais conseil (une licence)

PHASE 7  REPORT                                     [déterministe]
  `api/report.to_payload` — un seul endroit décide de la forme envoyée
  une scène perdue apparaît dans la charge utile ; une passe entièrement
  perdue est une erreur, pas un rapport à zéro entité

PHASE 8  DIFF                                       [déterministe]
  un verdict n'est repris que si l'entité, sa pire dépiction ET la version
  du prompt sont inchangées ; tout le reste repasse dans le pipeline
```

**Déterminisme.** Le brief du hackathon exige un agent déterministe :
`temperature = 0`, `responseSchema` sur toutes les sorties structurées, phases
1, 3, 7 et 8 en code pur, et `prompt_version` stocké sur chaque finding pour que
deux passes soient comparables.

**Modèles.** Gemini sur Vertex AI ou AI Studio selon un seul drapeau. Les
identifiants exacts sont dans `.env`, jamais en dur, et
`greenlight.tools.models` demande à l'API quels modèles les credentials
atteignent réellement plutôt que de se fier à une doc.

### 4.2 🟢 Structure ADK

```python
Workflow(
    name="greenlight_clearance",
    nodes=[
        WorkflowNode(agent=IngestAgent()),         # phase 1
        WorkflowNode(agent=ExtractAgent()),        # phase 2
        WorkflowNode(agent=CanonicalizeAgent()),   # phase 3
        WorkflowNode(agent=ResearchAgent()),       # phase 4
        WorkflowNode(agent=ClassifyAgent()),       # phase 5
    ],
)
```

Des agents de workflow, pas un `LlmAgent` : l'ordre des phases est connu, ne
dépend d'aucune entrée, et un rapport de clearance doit être reproductible.
`Workflow` et non `SequentialAgent`, que l'ADK 2.8 déprécie.

La couche ADK ne réimplémente rien — elle enveloppe les mêmes fonctions que la
bibliothèque, et un test affirme que les deux chemins rendent les mêmes verdicts,
entité par entité. Les clients vivants sont portés par `ClearanceDeps` et non par
l'état de session, qui doit rester sérialisable.

Outils exposés en `FunctionTool` : `choose_search_mode`, `build_entity_search`,
`rule_pre_verdict`.

### 4.3 🔵 Fan-out et reprise, à l'échelle

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

## 5. 🔵 Données

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

## 6. 🔵 Sécurité et IAM

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

## 7. 🟢 Frontend — Material 3

### 7.1 Stack

React 19 + TypeScript + Vite. Que du M3 : aucun Tailwind, aucun shadcn, aucun hex en dur.

**`@material/web`** (Material Web Components, l'implémentation M3 officielle) est utilisé là où il a le composant :

| Composant | Rôle |
|---|---|
| `md-ripple` | la couche d'état complète de chaque surface interactive, onde de pression comprise |
| `md-focus-ring` | l'anneau de focus, affiché sur `:focus-visible` seulement |
| `md-chip-set` + `md-filter-chip` | les filtres de verdict, qui *sont* des filter chips M3 |
| `md-linear-progress` | une passe en cours, en mode indéterminé |
| `md-outlined-text-field` | la recherche d'entité dans le rapport |

La librairie est en maintenance et n'expose qu'une vingtaine de composants — ni carte, ni composer, ni volet de navigation — donc la coquille conversationnelle (volet, saisie, tours, rapport) est bâtie sur les **tokens** M3, pas sur des composants. C'est le seul écart, et il tient à ce que la librairie ne couvre pas. Rien n'est importé pour allonger la liste : `md-divider` ne l'est pas, parce que la mise en page ne trace aucun filet.

Les icônes sont des SVG inline plutôt que la police Material Symbols : une police d'icônes qui ne charge pas affiche le *nom* de l'icône en toutes lettres au milieu de l'interface.

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
- **Courier Prime** — uniquement là où du scénario est cité : les occurrences dans le détail d'une entité. Les scénarios s'écrivent en Courier 12pt depuis toujours ; utiliser autre chose casserait la crédibilité auprès d'un juge qui connaît le métier.

### 7.4 Layout — window size classes

Le volet de navigation change de nature avec la classe de fenêtre, comme M3 le
demande. C'est vérifié par le test de bout en bout, aux deux largeurs.

| Classe | Largeur | Volet | État |
|---|---|---|:---:|
| Compact | < 600 | **modal** — se superpose, voile, se referme au clic dehors | 🟢 |
| Medium | 600–839 | modal, même comportement | 🟢 |
| Expanded | ≥ 840 | **permanent**, posé à côté du contenu | 🟢 |
| Large / XL | ≥ 1200 | supporting pane — scénario et rapport côte à côte | 🔵 |

Aucune navigation rail : M3 en prévoit une pour trois à sept destinations, et
l'application en a une. Un rail avec un seul bouton serait du décor.

### 7.5 Écrans

L'interface est **un fil de conversation**, pas une suite d'écrans. C'est la
forme que prend un assistant, et le rapport de clearance est rendu *dans* la
réponse plutôt que sur une page à part.

| État | Ce qu'il fait | État |
|---|---|:---:|
| **Accueil** | titre, saisie, et les scénarios livrés en amorces. Chaque amorce lance une vraie passe. | 🟢 |
| **Passe en cours** | `md-linear-progress` indéterminé et les phases qui se cochent, dès que le serveur les annonce. | 🟢 |
| **Rapport dans la réponse** | statistiques, recherche d'entité, filtres par verdict, entités dépliables sur place avec sources, occurrences et remplacement. | 🟢 |
| **Diff** | bandeau de comparaison, entités reprises marquées comme telles. | 🟢 |
| **Question de suivi** | la saisie change de régime et le dit ; la réponse s'ancre dans le rapport. | 🟢 |
| **Panneau scénario** | Courier, surlignage inline des entités, clic → l'entité s'ouvre. | 🔵 |

### 7.6 Motion

Tokens M3 exclusivement : `emphasized` pour le morphing de forme d'une entité qui s'ouvre, `emphasized-decelerate` pour l'entrée du volet modal, `standard` pour les changements d'état. `prefers-reduced-motion` coupe les transitions, partout.

L'échelle de rayons porte les dix crans, dont les trois ajoutés par M3 Expressive que la librairie ne livre pas encore. Une entité ouverte s'arrondit franchement : le rapport signale ce qui est ouvert indépendamment de la couleur.

---

## 8. API

### 8.1 🟢 Ce qui est servi

```
GET    /api/health          état de l'instance : appelle-t-elle vraiment les API,
                            combien d'appels sait-elle rejouer, peut-elle analyser
GET    /api/samples         les scénarios livrés, avec leur vrai nombre de scènes
POST   /api/analyze         un scénario en entrée, les 8 phases, et la progression
                            diffusée en text/event-stream phase par phase ;
                            le rapport est le dernier événement du flux
GET    /api/runs/{runId}    une passe terminée, pour qu'un fil survive à un F5
POST   /api/ask             une question de suivi, répondue à partir de ce
                            rapport et de rien d'autre
```

Pas d'authentification, pas de cookie : `CORS: *` est le réglage honnête pour ce
qui est servi. Un scénario déposé est parsé en mémoire et n'est jamais écrit sur
disque.

### 8.2 🔵 Ce que la cible ajoute

```
POST   /api/projects                          → {projectId}
POST   /api/projects/:pid/drafts/upload-url   → {gcsUri, signedUrl}
POST   /api/projects/:pid/drafts              → {draftId}   (confirme l'upload)
POST   /api/projects/:pid/drafts/:did/run     → {jobId}     (202 Accepted)
GET    /api/jobs/:jobId                       → état        (fallback si pas de SDK)
GET    /api/projects/:pid/drafts/:did/findings?verdict=&type=&cursor=
POST   /api/findings/:fid/apply               → applique le remplacement
GET    /api/projects/:pid/drafts/:did/diff?against=:draftId
```

Interne (OIDC uniquement) :
```
POST   /internal/orchestrate       ← Cloud Tasks
POST   /internal/research          ← Cloud Tasks (1 entité)
POST   /internal/research-complete ← Pub/Sub push
```

---

## 9. 🔵 Observabilité

- **Cloud Logging** — logs structurés JSON, corrélés par `jobId` et `traceId`.
- **Cloud Trace** — traces distribuées de bout en bout ; propagation du contexte à travers Cloud Tasks (indispensable pour voir où passent les 8 minutes).
- **Métriques custom** : `entities_extracted`, `cache_hit_ratio`, `parallel_latency_ms`, `verdict_distribution`, `job_duration_s`.
- **Dashboard Cloud Monitoring** + alertes : taux d'échec de job > 5 %, p95 durée > 15 min, erreurs Parallel > 2 %.
- **Error Reporting** sur tous les services.

*(Note : la stack Grafana appartient à un autre track du hackathon — reste sur l'observabilité GCP native, sinon tu brouilles ton positionnement.)*

---

## 10. CI/CD

### 10.1 🟢 Ce qui tourne

```
GitHub push / pull request
  → .github/workflows/ci.yml
      ├─ quality   ruff check · ruff format --check · pytest    (backend)
      ├─ frontend  oxlint · tsc -b · vite build
      ├─ e2e       Playwright, 5 parcours × 2 largeurs, contre le vrai
      │            serveur et le bundle de production
      └─ secrets   aucun .env suivi, aucune clé dans les .example
```

`FIXTURE_MODE=replay` partout : la CI ne consomme ni token ni crédit, et le
serveur du test de bout en bout script ses transports depuis l'arbre de tests —
jamais depuis le paquet livré, qui ne contient aucun mode « démonstration ».

`.github/workflows/deploy.yml` déploie sur Cloud Run à chaque CI verte sur
`main`, par Workload Identity Federation — aucune clé de compte de service dans
le dépôt. Le job s'ignore proprement tant que les variables GCP ne sont pas
renseignées, plutôt que d'échouer en rouge.

### 10.2 🔵 Ce que la cible ajoute

```
      ├─ build images → Artifact Registry (scan de vulnérabilités)
      ├─ terraform plan/apply (infra)
      ├─ deploy Cloud Run --no-traffic --tag=candidate
      ├─ smoke test sur l'URL taguée
      └─ bascule 100 % du trafic
```

Infrastructure en **Terraform**, intégralement. Pas de clic dans la console : un
juge qui regarde le repo doit pouvoir reconstruire l'environnement.

---

## 11. Coûts

### 11.1 🟢 Mesuré, sur le scénario de test

12 pages, 14 scènes, 26 entités canoniques, cache froid.

| Poste | Volume | Mesuré |
|---|---|---|
| Gemini extraction | 14 appels — une scène, un appel | compteur de tokens dans `usage_summary()` |
| Gemini classification | 21 appels courts | idem |
| Recherches Parallel évitées par règle | 5 entités sur 26 | **0 crédit** |
| Recherches Parallel facturées | 21 | poste dominant |
| Entités hallucinées écartées avant achat | 14 | **0 crédit** |

Le coût en dollars n'est **pas** affiché tant que les prix au million de tokens
ne sont pas renseignés dans l'environnement. Un montant inventé serait pire que
pas de montant : le chiffre annoncé dans la démo doit tenir sous vérification.

Sur la réécriture, le diff reprend 22 verdicts sur 27 — **81 % de la recherche
évitée**, mesuré, pas estimé.

### 11.2 🔵 Projeté, sur un long métrage

100 pages, ~180 entités, cache froid, extrapolé depuis la répartition
`fast` / `advanced` mesurée ci-dessus.

| Poste | Ordre de grandeur |
|---|---|
| Parallel Search | **poste dominant** |
| Gemini extraction + classification | faible |
| Cloud Run | négligeable, `min-instances = 0` |

Avec le cache chaud, le nombre de requêtes Parallel chute fortement — c'est là
que se joue la viabilité économique. **Mesurer sur un vrai scénario** plutôt que
d'estimer : un chiffre mesuré dans la vidéo vaut dix fois une projection.

### 11.3 ⚪ Ce qu'on n'allume pas

`min-instances = 0` pendant tout le développement : une instance allumée en
permanence est facturée en continu et sort du free tier. À passer à 1 la veille
du jugement seulement, pour épargner un démarrage à froid aux juges, puis à
remettre à 0.

Un budget d'alerte à 5 € est posé avant la première ligne de code, et le projet
GCP est supprimé une fois le jugement terminé — c'est la seule garantie qu'aucun
service oublié ne tourne.

---

## 12. ⚪ Écarté, et pourquoi

Ces choix figuraient dans la première version de ce document. Ils ont été
coupés, et il vaut mieux le dire que laisser croire qu'ils existent.

| Écarté | Raison |
|---|---|
| **Parsing PDF / Document AI** | Facturé à la page, et chronophage à fiabiliser. Fountain et FDX couvrent le format dans lequel un scénario s'écrit. |
| **Export PDF du rapport** | Le rapport à l'écran suffit, et le chat le rend consultable. |
| **Load Balancer global + Cloud Armor** | ~23 $/mois dès la première minute, zéro point au jury. Cloud Run expose directement. |
| **Cloud NAT + VPC** | ~32 $/mois. L'egress Cloud Run par défaut fait le travail. |
| **Firestore + Cloud Tasks + Pub/Sub** | Un seul processus suffit à la charge actuelle. Le store en mémoire porte sa propre limite, écrite dans le module. |
| **Extension Google Docs** | Hors budget temps. |
| **VPC Service Controls** | Documenté ci-dessus, pas construit. |

Le fil commun : rien de tout cela ne rend un verdict meilleur. Ce qui rend un
verdict meilleur, c'est la règle de dépiction, la vérification des citations et
le diff — et c'est là qu'est allé le temps.

---

## 13. Conformité hackathon

| Exigence | État | Réponse |
|---|:---:|---|
| Gemini + Google Cloud appelés au runtime | 🟡 | `google-adk` + `google-genai` importés et appelés par `greenlight.agents.gemini`. **Aucune fixture Gemini enregistrée à ce jour** : le chemin réel n'a pas encore été exercé faute de credentials. |
| Parallel appelé au runtime | 🟢 | SDK `parallel-web`, appelé par `greenlight.tools.parallel_search`. Une réponse réelle est enregistrée dans `fixtures/`. |
| Aucune IA non-Google | 🟢 | Gemini uniquement. Aucun SDK OpenAI / Anthropic / autre, ni en Python ni en JavaScript — vérifiable par `grep`. |
| Plateforme web | 🟢 | SPA Material 3 + API HTTP. |
| URL du projet hébergé | 🔴 | Pas encore déployée. |
| Repo public + licence | 🟢 | GitHub public, Apache 2.0 détectée dans « About ». |
| Projet nouveau | 🟢 | créé pendant la période du concours. |
| Équipe ≤ 4 | 🟢 | — |
| Agent déterministe multi-étapes | 🟢 | 8 phases, `temperature = 0`, schémas stricts, prompts versionnés. |

Les deux lignes qui ne sont pas vertes le sont pour la même raison : il manque
`GOOGLE_API_KEY` et `PARALLEL_API_KEY`. Un passage en `FIXTURE_MODE=record` les
règle toutes les deux, et `/api/health` dit à l'écran, en permanence, si
l'instance appelle réellement les API ou rejoue un disque.

---

## 14. Cadrage honnête

GREENLIGHT **ne remplace pas** le rapport de clearance officiel exigé par l'assureur E&O, et ne constitue pas un avis juridique. C'est un outil de **triage en amont** : attraper les problèmes pendant l'écriture, quand la correction est gratuite, et faire arriver le scénario chez le prestataire de clearance déjà propre.

Écris-le dans le README, dis-le dans la vidéo, affiche-le dans l'app. Un scope assumé se défend ; une promesse gonflée se démonte en une question du jury.
