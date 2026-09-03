# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Phase 2 — Gemini entity extraction with strict `responseSchema`
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
