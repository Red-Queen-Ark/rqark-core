# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Packaging metadata: `license`, `authors`, `keywords`, `classifiers`, and
  `[project.urls]` so the PyPI page is not blank.
- `py.typed` marker so type checkers pick up the inline annotations.
- This changelog.

## [0.4.1] - 2026-10-22

### Fixed

- Sub agent now builds the child core on the parent's provider route.

## [0.4.0] - 2026-10-20

### Added

- `Provider` carries an `id`, and `api_key` is optional for keyless endpoints.

## [0.3.2] - 2026-10-19

### Added

- Usage now records cache and reasoning tokens.

## [0.3.1] - 2026-10-19

### Fixed

- Tool prompts are rebuilt on every chat iteration.

## [0.3.0] - 2026-10-18

### Added

- `extras` are passed through to tools and prompts.

### Changed

- Codebase formatted with `ruff format`.

## [0.1.0] - [0.2.13] - 2026-09 to 2026-10

Initial public releases: stateless agent engine, event stream API, base prompts,
tool kit (shell, file, grep, git, web search), image messages, message ids,
per-tool timeouts, and usage reporting.

[Unreleased]: https://gitea.carhyme.top/RedQueenArk/rqark-core/compare/v0.4.1...main
[0.4.1]: https://gitea.carhyme.top/RedQueenArk/rqark-core/compare/v0.4.0...v0.4.1
[0.4.0]: https://gitea.carhyme.top/RedQueenArk/rqark-core/compare/v0.3.2...v0.4.0
[0.3.2]: https://gitea.carhyme.top/RedQueenArk/rqark-core/compare/v0.3.1...v0.3.2
[0.3.1]: https://gitea.carhyme.top/RedQueenArk/rqark-core/compare/v0.3.0...v0.3.1
[0.3.0]: https://gitea.carhyme.top/RedQueenArk/rqark-core/compare/v0.2.13...v0.3.0
