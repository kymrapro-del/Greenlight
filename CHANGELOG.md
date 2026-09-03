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
- **Pipeline runner** (`greenlight.pipeline`) — chains phases 1→3 and prints the
  measured report: entity count, entities resolved with no search, search-budget
  split, and dropped hallucinations. `python -m greenlight.pipeline <script>`.

### Planned
- Phase 5 — verdict classification with citations
- Phase 6 — re-verified replacement suggestions
- Phase 8 — draft-to-draft diff mode
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
