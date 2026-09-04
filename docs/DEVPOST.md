# Devpost — brouillon de soumission

> À relire et à coller dans le formulaire. Rien ici n'est inventé : chaque
> chiffre vient d'une mesure reproductible, et les cases non cochées sont
> marquées comme telles plutôt que passées sous silence.

---

## Nom du projet

**GREENLIGHT**

## Tagline (une ligne)

> Automated screenplay pre-clearance — catch the legal landmines while they are
> still free to fix.

## Track

**Parallel** (Google Cloud + Parallel Search API).

---

## Inspiration

Before a film can be shot, the production must obtain a **script clearance
report**. Without it there is no E&O insurance, and without insurance no
distributor will touch the film. It is not optional, it takes about a week, and
it costs several thousand dollars per script.

The part that bothered us is not the price. It is the *timing*. Clearance runs
on the **locked** script — after the sets are designed and the props are bought.
By then, discovering that the bar your character deals drugs in is a real,
operating business means rebuilding set dressing, remaking props and
re-recording ADR. So productions negotiate, take the risk, or pay for a licence
they should never have needed.

Software security made this move twenty years ago: the end-of-cycle pentest
became a linter in the editor. Screenplay clearance never did.

---

## What it does

You give GREENLIGHT a screenplay. It reads it, finds **every named entity** —
characters, businesses, brands, phone numbers, addresses, licence plates, songs,
artworks, hospitals, publications, real people, real events — checks each one
against the live web with traceable sources, and hands back a clearance report
in minutes.

Then you can ask it questions about that report, in the same thread.

The thing that makes it a clearance tool rather than a search wrapper is that it
reasons about **depiction**, not just existence:

| Entity | Real? | What the scene does | Verdict |
|---|:---:|---|:---:|
| Coca-Cola | yes | a can on a windowsill | **CLEAR** |
| Chicago Cubs | yes | a cap on a shelf | **CLEAR** |
| Blackhawks | yes | jersey worn during an offence | **CAUTION** |
| Walgreens | yes | fills a forged prescription | **CHANGE RECOMMENDED** |

A system that flags Coca-Cola has learned *real ⇒ risky*. That control case is
in our test screenplay on purpose, and it stays green.

There is a second, sharper test in there. Two characters with ordinary names
commit the same crime in the same scene. **Marcus Webb** escalates to *change
recommended*; **Daniel Reyes** stays at *caution*. The difference is that search
comes back with specific real physicians named Marcus Webb, and nothing for
Daniel Reyes. Escalating on the word "crime" alone would flag every protagonist
in cinema.

---

## How we built it

**Eight phases, and only three of them call a model.**

| # | Phase | Engine |
|---|---|---|
| 1 | Ingest — Fountain/FDX → structured scenes | code |
| 2 | Extract — typed entities **and** depiction tier, one scene per call | Gemini Flash |
| 3 | Canonicalize — alias resolution, stable ids | code |
| 4 | Research — risk-routed web fan-out | **Parallel Search** |
| 5 | Classify — verdict + rationale + citations | Gemini Pro |
| 6 | Suggest — generate a replacement, then search for it | Gemini + Parallel |
| 7 | Report — sorted by severity, then by having a source | code |
| 8 | Diff — re-clear only what actually moved between drafts | code |

**Google stack.** `google-genai` for every model call, with a strict pydantic
`responseSchema` on each one — the pipeline never parses prose. The same eight
phases are also packaged as a native **ADK `Workflow`** graph (not
`SequentialAgent`, which 2.8 deprecates), deployable to Vertex AI Agent Engine,
with the search strategy exposed as `FunctionTool`s. Workflow agents rather than
an `LlmAgent`, deliberately: the phase order is known, depends on no input, and a
clearance report has to be reproducible.

**Parallel Search**, risk-routed. `fast` at \$1/1 000 is enough to establish
whether a neutrally-mentioned entity exists; `advanced` at \$5/1 000 is spent
only where the verdict is genuinely in play. Five times cheaper across the bulk
of the fan-out with no loss where it matters.

**The interface is a conversation**, in Material 3. One source colour generates
both schemes and every role through `@material/material-color-utilities`; no
component hard-codes a hex, a radius, a duration or a type size. The clearance
report is rendered *inside* the assistant's answer rather than on a separate
screen. Progress streams over SSE phase by phase, because a pass takes tens of
seconds and a silent loading screen is the one thing a demo cannot afford.

---

## Challenges we ran into

**Paying twice for nothing.** Our first fan-out billed a search for every entity
the model returned — including ones it invented. A deterministic guard now drops
any entity that does not appear verbatim in the scene text, before the queue.
On our test screenplay that is 14 entities that never cost a cent.

**Verdicts with no evidence behind them.** The model would cite URLs that were
not in the search results it had been given. Cited URLs absent from the results
are now discarded, and any adverse verdict left with no verifiable source falls
back to `UNRESOLVED`. An unsourced accusation is not a clearance finding.

**A cache that lied.** The first diff implementation reused a verdict whenever
the entity name was unchanged. But a newspaper that was a neutral prop in draft
one and the instrument of a forgery in draft two is a *different* risk under the
same name. A verdict is now reused only when the entity, its worst depiction and
the prompt version are all unchanged.

**Reporting an empty success.** An analysis where every scene failed came back
as a report with zero entities — indistinguishable, to a reader, from a clean
screenplay. It now returns the diagnostic.

---

## Accomplishments we're proud of

- **The control cases hold.** Coca-Cola, a Cubs cap, a public-domain hymn, a real
  author on a shelf and a historical event in dialogue all come back `CLEAR`,
  three scenes away from entities that do not.
- **`UNRESOLVED` is a first-class verdict.** A clearance tool that claims
  certainty it does not have is worse than no tool.
- **Zero credits in CI.** A recording harness means the whole test suite — 152
  offline tests plus 10 browser journeys across two screen widths — runs without
  a single network call.
- **The measured diff.** On the rewrite, 5 of 27 entities are re-analysed and
  22 verdicts reused: **81 % of the research skipped**. That is what makes
  per-draft clearance viable rather than aspirational.

---

## What we learned

Existence is the easy half. Every entity extractor can tell you that a bar
exists. The half that decides whether a production gets sued is what the *scene*
does with it, and that turned out to be a separate signal the model has to be
asked for explicitly, per occurrence — not something you can infer afterwards
from the entity alone.

The second thing: **a number you did not measure is worth less than no number.**
We report tokens and no dollars until per-million prices are supplied in the
environment, because an invented cost figure comes apart in one question.

---

## What's next for GREENLIGHT

- Record the live fixtures and publish a hosted URL on Cloud Run.
- The screenplay pane: Courier, with entities highlighted inline where they sit.
- Apply-a-replacement, writing the fix back into the Fountain source.
- A Google Docs / Final Draft extension so the check runs where the writing does.

---

## Built with

`python` · `google-adk` · `google-genai` · `gemini` · `vertex-ai` ·
`parallel-search` · `fastapi` · `pydantic` · `react` · `typescript` · `vite` ·
`material-design-3` · `material-web` · `playwright` · `cloud-run` · `docker`

---

## Try it out

- **Repository** — https://github.com/kymrapro-del/Greenlight
- **Hosted demo** — *(à remplir une fois déployé)*
- **Video** — *(à remplir)*

---

## ⚠️ À faire avant de soumettre

Ces points ne sont pas encore vrais. Ne pas cocher au hasard.

| | À faire |
|:---:|---|
| ☐ | Enregistrer les fixtures réelles (`FIXTURE_MODE=record`) — c'est ce qui rend « Gemini appelé au runtime » vérifiable |
| ☐ | Déployer sur Cloud Run et remplir l'URL ci-dessus |
| ☐ | Tourner la vidéo de 3 minutes, la publier en **public** sur YouTube, sous-titres anglais |
| ☐ | Vérifier l'URL publique depuis une navigation privée, sur un autre réseau |
| ☐ | Sélectionner le track **Parallel** dans le formulaire |
| ☐ | Soumettre en brouillon dès que possible — Devpost autorise l'édition après |

## 🎥 Plan de la vidéo, à la seconde

| Temps | Contenu |
|---|---|
| **0:00–0:25** | Le problème, en langage humain. « Votre personnage entre dans un bar appelé The Black Cat Tavern et y achète de la drogue. Ce bar existe. » Puis : pas de rapport de clearance, pas d'assurance ; pas d'assurance, pas de distribution. Une semaine, plusieurs milliers de dollars. **Aucun jargon technique.** |
| **0:25–0:40** | L'insight : ça se fait à la fin, quand les décors sont construits. Le corriger pendant l'écriture est gratuit. |
| **0:40–1:10** | Dépôt du scénario, les phases qui défilent en direct. |
| **1:10–1:50** | Le rapport. Zoom sur Walgreens en rouge, avec ses sources cliquables. Puis, juste après, **Coca-Cola en vert** — voilà le raisonnement. |
| **1:50–2:10** | Marcus Webb monte, Daniel Reyes non. Même délit, même scène. |
| **2:10–2:40** | Le diff. Draft v2, 5 entités réanalysées sur 27, 81 % de recherche évitée. « Le clearance en intégration continue. » |
| **2:40–3:00** | Le chiffre mesuré + le cadrage honnête (triage en amont, pas d'avis juridique) + le stack en une phrase. |

Règles de tournage : capture nette, voix off enregistrée séparément, sous-titres
anglais, **aucune seconde d'écran de chargement non coupée**. Si une étape prend
40 secondes, accélérer à l'image avec un badge « ×8 » visible — ne pas mentir sur
la vitesse.
