<div align="center">

# 🟢 GREENLIGHT

**Automated pre-clearance for screenplays.**
Catch the legal landmines in a script *while they are still free to fix*.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![CI](https://github.com/kymrapro-del/Greenlight/actions/workflows/ci.yml/badge.svg)](https://github.com/kymrapro-del/Greenlight/actions/workflows/ci.yml)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Gemini%20%2B%20Vertex%20AI-4285F4.svg?logo=googlecloud&logoColor=white)](https://cloud.google.com/vertex-ai)
[![Parallel](https://img.shields.io/badge/Parallel-Search%20API-000000.svg)](https://docs.parallel.ai/search/search-quickstart)
[![Hackathon](https://img.shields.io/badge/Agentic%20Cinema-Parallel%20track-E4405F.svg)](https://agentic-cinema.devpost.com)

</div>

---

## The problem nobody codes for

Before a film can be shot, the production must obtain a **script clearance
report**. Without it there is no E&O insurance, and without insurance no
distributor will touch the film. It is not optional.

A human reads the screenplay and catalogues **every named entity** — character
names, businesses, brands, phone numbers, addresses, licence plates, songs,
artworks, hospitals, publications — then researches each one to determine
whether it exists in the real world and whether using it invites a lawsuit.

That takes roughly a week and costs several thousand dollars per script.

**And it happens too late.** Clearance runs on the locked script. By then,
renaming a bar means rebuilding set dressing, remaking props, and re-recording
ADR. So productions negotiate, take risks, or pay for a licence.

## The idea: shift clearance left

Software security moved from the end-of-cycle pentest to a linter in the
editor. Screenplay clearance never made that move.

GREENLIGHT reads a screenplay, extracts every entity, verifies each one against
the live web with traceable sources, and returns a clearance report in minutes —
fast enough and cheap enough to run on **every draft**, not once at the end.

> A writer who learns on page 12 that *The Black Cat Tavern* is a real, operating
> business fixes it in three seconds. The same fix six months later costs a
> shooting day.

---

## Why this is not "an LLM with web search"

**Depiction context is the risk multiplier.**
Naming a real bar is harmless. The *same* bar where a character deals drugs is
defamation exposure. GREENLIGHT assigns a different verdict to the same entity
depending on what the scene does with it — a judgement that requires reading the
scene, not matching a string.

**Replacements are re-verified.**
When an entity must change, the system generates an alternative, **searches for
it in turn**, and only proposes it once it returns nothing real. A suggestion
that has not been cleared is not a suggestion.

**Diff mode makes per-draft runs viable.**
Draft v2 against v1: only changed entities are re-researched. Second pass in
seconds instead of minutes. This is what turns clearance into CI.

**Deterministic pre-verdicts cost nothing.**
A phone number in the 555-0100–555-0199 range is reserved for fiction by the
North American Numbering Plan — `CLEAR` by rule, no network call. Same for
RFC 2606 domains and government agencies named neutrally. On the test
screenplay this settles **5 of 15 entities** before a single request is billed.

**A hallucinated entity never costs a search.**
Any entity the model returns that does not appear verbatim in the scene text is
dropped before the fan-out. Deterministic, free, and it removes the worst
failure mode: paying to research a name the writer never wrote.

**Citations are verified, not trusted.**
Cited URLs absent from the search results are discarded, and any adverse verdict
left with no verifiable source falls back to `UNRESOLVED`. An unsourced
accusation is not a clearance finding.

---

## Pipeline

| # | Phase | Engine | Deterministic |
|---|-------|--------|:---:|
| 1 | **Ingest** — Fountain → structured scenes | code | ✅ |
| 2 | **Extract** — typed entities + depiction context | Gemini Flash | schema-locked |
| 3 | **Canonicalize** — dedupe, alias resolution | code | ✅ |
| 4 | **Research** — web fan-out, risk-routed | **Parallel Search** | ✅ |
| 5 | **Classify** — verdict + rationale + citations | Gemini Pro | schema-locked |
| 6 | **Suggest** — generate, then re-verify replacement | Gemini + Parallel | — |
| 7 | **Report** — sorted, sourced clearance report | code | ✅ |
| 8 | **Diff** — re-clear only the delta between drafts | code | ✅ |

Determinism is enforced where it decides a verdict: `temperature = 0` on
extraction and classification, strict `responseSchema` on every structured
output, phases 1/3/7/8 with no model call at all, and a `prompt_version` on
every finding so two runs stay comparable — and so a stale verdict is never
reused after the prompt changes.

Phase 6 is the one deliberate exception. Asking for three replacement names at
temperature 0 returns three variants of the same name, so it runs warmer; the
verification pass that follows is what makes the suggestion trustworthy, not the
sampling temperature.

### Verdicts

| Verdict | Meaning |
|---|---|
| `CLEAR` | No real-world collision, or protected use. |
| `CAUTION` | Real entity exists; depiction is defensible but worth a look. |
| `CHANGE_RECOMMENDED` | Real entity + unflattering or illegal depiction. |
| `LICENSE_REQUIRED` | Rights holder identified; clearance must be purchased. |
| `UNRESOLVED` | Insufficient evidence. Surfaced honestly, never guessed. |

`UNRESOLVED` is a first-class verdict. A clearance tool that claims certainty it
does not have is worse than no tool.

---

## Risk-routed search

Parallel pricing: `fast` at **\$1 / 1 000 requests**, `advanced` at **\$5 / 1 000**.

`fast` is enough to establish whether a neutrally-mentioned entity exists.
`advanced` is spent only where the verdict is genuinely in play — entities shown
unflatteringly, or high-exposure categories (songs, artworks, real people).

Five times cheaper across the bulk of the fan-out, with no loss of quality where
it matters.

### What is actually measured

Two numbers, and the difference between them is deliberate.

**Measured, on the test screenplay:** 15 canonical entities, 5 settled by
rule with no billed request, 10 researched, 3 verdicts escalated by the depiction
rule, 6 hallucinated entities dropped before the fan-out. On the rewrite, the
diff re-analyses 5 of 16 entities and reuses 11 verdicts — **68 % of the research
skipped**. Reproduce it with the commands below; it costs nothing in `replay`.

**Projected, for a 100-page screenplay** (~180 entities, extrapolated from the
per-entity mode split above): roughly **\$0.20** of Parallel search. Against
roughly a week and several thousand dollars for a manual clearance pass.

The projection is labelled as such on purpose. A measured figure for a
feature-length script requires a feature-length run, and this README will carry
one only once that run has happened.

---

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

**The test suite and the report screen run fully offline** — no key, no credits,
no network:

```bash
.venv/bin/python -m pytest          # 127 tests, all offline
```

**The pipeline CLI needs credentials for its first run.** Model responses are
replayed from disk, and this repository ships no recorded Gemini fixtures — a
recording of somebody's API responses is not something to commit blindly. Set up
`.env`, record once, and every later run is free:

```bash
cp .env.example .env                # GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT
                                    # + PARALLEL_API_KEY

# Record once — this is the only run that spends anything
FIXTURE_MODE=record PYTHONPATH=backend .venv/bin/python -m greenlight.pipeline \
    samples/seventeen_minutes.fountain --clearance --suggest

# Every run after that replays from disk, for free
PYTHONPATH=backend .venv/bin/python -m greenlight.pipeline \
    samples/seventeen_minutes.fountain --clearance --suggest

# Phase 8 — re-clear only what the rewrite touched
PYTHONPATH=backend .venv/bin/python -m greenlight.pipeline \
    samples/seventeen_minutes_v2.fountain \
    --against samples/seventeen_minutes.fountain
```

Run it in `replay` with no fixtures and it tells you so on the first line rather
than reporting an empty success.

### The product

Two processes: the API runs the pipeline, the interface talks to it. Nothing is
pre-computed and no report is committed — the screen shows what the server
actually returned, or says the server did not answer.

```bash
# The API
PYTHONPATH=backend .venv/bin/python -m uvicorn greenlight.api.server:app --port 8000

# The interface, in another shell
cd frontend
npm install
npm run theme        # regenerate the M3 palettes from the source colour
npm run dev          # proxies /api to localhost:8000
```

| Route | What it does |
| --- | --- |
| `GET /api/health` | whether this instance really calls Gemini and Parallel, or replays fixtures |
| `GET /api/samples` | the screenplays shipped with the repo, with their real scene counts |
| `POST /api/analyze` | a screenplay in, the eight phases run, **the progress streams back** phase by phase over SSE, the report is the last event |
| `GET /api/runs/{id}` | a completed pass, so a thread survives a reload |
| `POST /api/ask` | a follow-up question, answered from that report and nothing else |

A pasted screenplay is parsed in memory and never written to disk. Passes are
held in a capped in-memory store: a restart empties it, and two instances share
nothing — stated here because that is the point at which this design stops being
enough.

An analysis where every scene fails comes back as an error naming the cause, not
as a report with zero entities. Those two are indistinguishable to a reader, and
one of them is a lie about a screenplay full of landmines.

### Offline fixture harness

Credits are finite. `FIXTURE_MODE` prevents paying twice for identical calls:

| Mode | Behaviour |
|---|---|
| `live` | calls the API, stores nothing |
| `record` | calls the API **and** writes the response to disk |
| `replay` | reads disk only — no network, no credits |

Record once, then develop entirely in `replay`. The test suite runs in `replay`,
so **CI is free and deterministic**.

---

## Test screenplay

[`samples/seventeen_minutes.fountain`](samples/seventeen_minutes.fountain) is a
short screenplay written for this project and deliberately seeded with clearance
landmines covering every report category — including one **intentionally
harmless** trap the system must return as `CLEAR`.

It is six scenes, about three pages by the parser's own estimate: dense enough
to hold fifteen landmines, short enough that a full pass costs almost nothing to
re-run. It is a test fixture, not a feature film, and it is described that way
rather than inflated.

That last one matters: it is the proof the system reasons about context instead
of painting everything red.

Expected verdicts: [`samples/EXPECTED.md`](samples/EXPECTED.md). Every one of the
15 hand-verified verdicts is reproduced by the pipeline, and the depiction rule
escalates exactly the three entities it should.

[`samples/seventeen_minutes_v2.fountain`](samples/seventeen_minutes_v2.fountain)
is the rewrite a writer would actually produce — two entities renamed, a phone
number fixed, a scene added, and one entity kept under the same name but
re-depicted. That last one is the case a naive cache would carry over silently,
so it is the one the diff has to catch.

---

## Interface — Material 3

One source colour (`#1B7F3B`, the studio green light) generates the six tonal
palettes and both schemes through `@material/material-color-utilities`. No
component hard-codes a hex, a corner radius, a duration or a type size, so
changing that one colour recolours the whole screen.

Verdicts map to M3 colour **roles**, never to raw hex — `error-container` for
*change recommended*, `tertiary-container` for *clear*, and a harmonised custom
`warning` role for *caution*, since M3 defines no warning role of its own.
Contrast is guaranteed by construction, because M3 computes every
`container` / `on-container` pair to meet the thresholds.

**The interface is a conversation**, on the pattern of Gemini: a history pane, a
prompt composer, and answers in the thread. The clearance report is rendered
*inside* the answer rather than on a separate screen — that is how an assistant
returns a structured result, and the verdicts keep their reading affordances
without leaving the thread.

**What comes from the library, and what does not.** `@material/web` is in
maintenance mode and ships twenty components — no card, no chat composer, no
navigation drawer. So the shell (drawer, composer, turns, report) is built from
M3 **design tokens**, and the library is used where it actually has the
component:

| Used | Why the library rather than hand-rolled |
| --- | --- |
| `md-ripple` | The full M3 state layer. A hand-written `::after` does hover and focus, but not the press wave — it starts at the contact point, is sized from the container, and takes three times longer to leave than to arrive. |
| `md-focus-ring` | The focus ring with its grow animation, shown on `:focus-visible` only, so never after a mouse click. |
| `md-filter-chip` | The verdict filters *are* M3 filter chips: same role, same `aria-pressed`, same check mark on selection. |

Said plainly because a reader who knows the library will notice, and the shape
of the gap is worth knowing. Nothing is imported to pad the list: `md-divider`
is not used because the layout has no rule to draw.

Icons are inline SVG rather than the Material Symbols font: a webfont that fails
to load renders the icon's *name* as literal text across the interface. The
screenshots in this repository were taken with Google Fonts unreachable.

The corner radius scale carries all ten steps, including the three added by M3
Expressive that the library does not yet ship — an opened entity morphs to a
wider radius, so the report signals what is open independently of colour.

---

## Architecture

**What runs today** — a Python service plus a Material 3 interface that talks to it:

```
frontend/            Material 3 conversational interface (Vite + React)
   │  POST /api/analyze, reads the SSE progress stream
   ▼
backend/greenlight/api/server.py   FastAPI · streams the phases, holds the runs
   ▼
backend/greenlight/
   ingest/           Fountain → scenes                         phase 1
   agents/extract    Gemini · structured output, per scene     phase 2
   agents/dedupe     canonicalisation, no model                phase 3
   agents/research   Parallel Search · concurrent fan-out      phase 4
   agents/classify   Gemini · sourced verdicts                 phase 5
   agents/replace    generate → re-verify replacement          phase 6
   agents/diff       reuse verdicts across drafts              phase 8
   api/report        pipeline → the report the screen consumes phase 7
   tools/            fixtures, entity cache, query strategy
```

**Where it is designed to run** — the Cloud Run topology, VPC, Cloud Tasks
fan-out, Firestore schema and IAM are specified in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). That deployment is designed and
documented, not built: the pipeline currently runs in-process, with a bounded
thread pool where the cloud design uses Cloud Tasks.

The eight phases are also packaged as a native **Agent Development Kit**
pipeline in `backend/greenlight/adk/`, deployable to Vertex AI Agent Engine:

```bash
PYTHONPATH=backend .venv/bin/python -m greenlight.pipeline \
    samples/seventeen_minutes.fountain --clearance --adk
```

Each phase is a `BaseAgent` wired into an ADK `Workflow` graph, and the search
strategy is exposed as ADK `FunctionTool`s. **Workflow agents rather than an
`LlmAgent`**, deliberately: an `LlmAgent` lets the model choose which tool to
call and in what order, which is right when the plan depends on the
conversation. Here the order of the eight phases is known, depends on no input,
and a clearance report has to be reproducible run to run — the hackathon rules
ask for a deterministic agent. The model is still called where it brings
judgement (extraction, classification, suggestion); it does not drive the
orchestration.

`Workflow` and not `SequentialAgent`: the latter is deprecated as of ADK 2.8.

The ADK layer reimplements nothing — every phase delegates to the same function
the library uses, and a test asserts the two execution paths return identical
verdicts. The model layer underneath is `google-genai` calling Gemini with
strict structured output on every call. No third-party wrapper framework, and no
non-Google model anywhere in the product.

---

## Versioning & releases

This project follows [Semantic Versioning](https://semver.org) and
[Keep a Changelog](https://keepachangelog.com).

- Version of record: `pyproject.toml` → `project.version`
- History: [`CHANGELOG.md`](CHANGELOG.md)
- Releases are git tags `vX.Y.Z`

**`main` is the production branch. Every push to `main` deploys.**
CI runs lint and the offline test suite on every push and pull request; a green
run on `main` triggers the Cloud Run deployment.

---

## Scope, stated honestly

GREENLIGHT **does not replace** the official clearance report required by an E&O
insurer, and it is not legal advice.

It is upstream triage: catch problems during writing, when the fix is free, and
hand the clearance vendor a script that is already clean.

---

## License

[Apache 2.0](LICENSE)

<div align="center">
<sub>Built for the <a href="https://agentic-cinema.devpost.com">Agentic Cinema</a> hackathon · Parallel track</sub>
</div>
