# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Gemini transport** (`greenlight.agents.gemini`) — one entry point for every
  model call: strict `responseSchema` output, the same `record`/`replay` fixture
  harness as Parallel, and measured token accounting. Vertex AI or AI Studio
  behind a single flag. Token cost is reported only when per-million prices are
  supplied, so no dollar figure is ever invented.
- **Phase 2 — entity extraction** (`greenlight.agents.extract`) — one call per
  scene, returning both what the entity *is* and how the scene *depicts* it.
  A deterministic guard drops any entity absent from the scene text before it
  can reach the billed search queue.
- **Phase 3 — canonicalisation** (`greenlight.agents.dedupe`) — merges the
  spellings of one entity across a screenplay under conservative rules, with
  stable ids so the planned diff mode can compare two drafts.
- **Phase 4 — research fan-out** (`greenlight.agents.research`) — concurrent
  Parallel lookups, with rule-resolved entities never entering the billed queue
  and search depth chosen per entity. A failed lookup is recorded and the entity
  falls back to `UNRESOLVED` rather than taking down the report.
- **Phase 5 — sourced verdicts** (`greenlight.agents.classify`) — the model
  judges only from the search excerpts it was given. Cited URLs absent from
  those results are discarded, and any adverse verdict left with no verifiable
  source falls back to `UNRESOLVED`: an unsourced accusation is not a finding.
- **Depiction rule** — existence and depiction are two separate signals combined
  by one explicit, testable function. A real entity a source specifically
  identifies is escalated when the scene depicts a crime; a common name with no
  matching profile is not. The report shows what was escalated and from what.
- **Pipeline runner** (`greenlight.pipeline`) — chains phases 1→3, or 1→5 with
  `--clearance`, and prints the measured report: entity count, entities resolved
  with no search, search-budget split, dropped hallucinations, verdict
  breakdown, and per-finding sources.
- **Thread-safe cost accounting** — the fan-out increments the Parallel and
  Gemini counters from several threads; the totals the demo quotes are locked so
  they hold up under verification.

- **Phase 6 — re-verified replacements** (`greenlight.agents.replace`) — a
  suggested name is put back through the same search as the original, and marked
  verified only when nothing real comes back; an unverifiable candidate is still
  offered but labelled as such. Phone numbers and e-mail addresses take the
  professional convention (555-01XX, RFC 2606) with no model call and no search.
  Nothing is suggested where renaming would be bad advice — a song under
  copyright needs a licence, not a new title.
- **Phase 8 — draft-to-draft diff** (`greenlight.agents.diff`) — a verdict is
  reused only when the entity, its worst depiction, and the prompt version are
  all unchanged. Everything else goes back through the pipeline: an entity kept
  under the same name but newly implicated in a crime is re-analysed, never
  silently carried over.
- **Second sample draft** (`samples/seventeen_minutes_v2.fountain`) — the rewrite
  a writer would actually produce: two entities renamed, a phone number fixed, a
  scene added, and one entity kept by name but re-depicted.

### Verified
- On `samples/seventeen_minutes.fountain`, the pipeline reproduces all 15
  hand-verified verdicts in `samples/EXPECTED.md`, escalates exactly the three
  entities the depiction rule should touch, and leaves the Coca-Cola control
  case `CLEAR`. On the rewrite, 5 of 16 entities are re-analysed and 68 % of the
  research is skipped. 120 tests, all offline: no token and no credit spent
  in CI.

### Planned
- Material 3 report UI

## [0.1.0] — 2026-09-03

Foundation: ingest, research transport, and the offline harness that makes the
rest affordable to build.

### Added
- **Fountain parser** (`greenlight.ingest.fountain`) — screenplay → structured
  scenes with heading decomposition, character/dialogue separation and page
  estimation.
- **Data model** (`greenlight.models`) — 16 clearance entity types, 3 depiction
  context tiers, 5 verdicts. Doubles as the Gemini `responseSchema` contract.
- **Parallel Search client** (`greenlight.tools.parallel_search`) — built on the
  official `parallel-web` SDK, with real cost tracking from the API `usage`
  field and `client_model` set to the consuming Gemini model.
- **Risk-routed search strategy** (`greenlight.tools.queries`) — per-entity-type
  objectives and query sets; `fast` for bulk lookups, `advanced` reserved for
  entities where the verdict is genuinely in play.
- **Deterministic pre-verdicts** — 555-01XX fictional phone range, RFC 2606
  domains, and neutrally-named government agencies resolve without a network
  call.
- **Fixture harness** (`greenlight.tools.fixtures`) — `live` / `record` /
  `replay` modes so development and CI consume zero API credits.
- **Test screenplay** (`samples/seventeen_minutes.fountain`) — seeded with
  clearance landmines across every report category, including one deliberately
  harmless trap.
- Architecture and delivery plan under `docs/`.

[Unreleased]: https://github.com/kymrapro-del/Greenlight/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kymrapro-del/Greenlight/releases/tag/v0.1.0
