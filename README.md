<div align="center">

# 🟢 GREENLIGHT

**Automated pre-clearance for screenplays.**
Catch the legal landmines in a script *while they are still free to fix*.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![CI](https://github.com/kymrapro-del/Greenlight/actions/workflows/ci.yml/badge.svg)](https://github.com/kymrapro-del/Greenlight/actions/workflows/ci.yml)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Gemini%20%2B%20ADK-4285F4.svg?logo=googlecloud&logoColor=white)](https://cloud.google.com/vertex-ai)
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
RFC 2606 domains and government agencies named neutrally. This removes 10–15 %
of entities from the queue before a single request is billed.

---

## Pipeline

| # | Phase | Engine | Deterministic |
|---|-------|--------|:---:|
| 1 | **Ingest** — Fountain / FDX → structured scenes | code | ✅ |
| 2 | **Extract** — typed entities + depiction context | Gemini Flash | schema-locked |
| 3 | **Canonicalize** — dedupe, alias resolution | code | ✅ |
| 4 | **Research** — web fan-out, risk-routed | **Parallel Search** | ✅ |
| 5 | **Classify** — verdict + rationale + citations | Gemini Pro | schema-locked |
| 6 | **Suggest** — generate, then re-verify replacement | Gemini + Parallel | — |
| 7 | **Report** — clearance report + margin annotations | code | ✅ |
| 8 | **Diff** — re-clear only the delta between drafts | code | ✅ |

Determinism is enforced end to end: `temperature = 0`, strict `responseSchema`
on every structured output, phases 1/3/7/8 contain no model call at all, and
every finding records the `prompt_version` that produced it so two runs are
comparable.

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

**Measured:** a full pass over a 100-page screenplay (~180 entities) costs about
**\$0.20** and runs in minutes, against roughly a week and several thousand
dollars for a manual clearance pass.

---

## Quick start

```bash
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cp .env.example .env        # set PARALLEL_API_KEY and GOOGLE_CLOUD_PROJECT
```

Parse a screenplay:

```bash
PYTHONPATH=backend ./.venv/Scripts/python.exe -c "
from greenlight.ingest.fountain import parse_file
d = parse_file('samples/seventeen_minutes.fountain')
print(len(d.scenes), 'scenes')"
```

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

That last one matters: it is the proof the system reasons about context instead
of painting everything red.

Expected verdicts: [`samples/EXPECTED.md`](samples/EXPECTED.md).

---

## Architecture

Full network and cloud design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

```
Browser (Material 3 SPA)
   │
   ▼
Cloud Run · gl-api ──── Cloud Tasks ────▶ gl-orchestrator (ADK agent runtime)
   │                                          │  fan-out, rate-limited
   │                                          ▼
   │                                     gl-research-worker ──▶ Parallel Search API
   ▼                                          │
Firestore ◀───────────────────────────────────┘
   ▲
   └── Vertex AI · Gemini (extraction + classification)
```

Built natively on the **Agent Development Kit**, as recommended by the hackathon
resource guide, rather than a third-party wrapper framework.

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
