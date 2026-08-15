# Changelog

All notable project changes are documented in this file.

The format follows *Keep a Changelog*, and versions follow Semantic
Versioning.

## [Unreleased]

### Added

- German, Italian, Latin, Portuguese, and Spanish language profiles, in
  addition to French and English, selecting the official Vatican source,
  IntraText navigation labels, structural headings, generated metadata, and
  output file names.
- `--language {de,en,es,fr,it,la,pt}` CLI option and `LANGUAGE` Make variable.
- parsing of the Vatican's legacy flat HTML indexes alongside IntraText.
- Deterministic English integration corpus covering localized parsing,
  orphan-page discovery, Texinfo generation, and JSON reporting.
- English README used as the main GitHub and PyPI presentation while retaining
  the complete French documentation in `README.fr.md`.
- package metadata links for the repository, issues, and changelog.

### Changed

- common CLI messages, reports, errors, community files, comments, and
  docstrings are now in English.
- the JSON generation report now records the selected language.
- distribution size units now use the language-neutral `B`, `KiB`, `MiB`, and
  `GiB` symbols.
- the short package description is in English for international discovery.

### Fixed

- HTTPS canonicalization for absolute HTTP links in the English IntraText
  corpus, preventing linked pages from being treated as orphan pages.
- exclusion of IntraText footnote blocks and Bible references from CCC
  paragraph indexing.
- recovery of a paragraph number merged into malformed English source HTML.
- language-safe cache names and handling of malformed paragraph numbers in the
  German and Portuguese source editions.

## [3.5.0] - 2026-08-15

### Added

- progressive static type checking with mypy across all modules.
- local IntraText mini-corpus and deterministic integration test through JSON
  report generation.
- security policy and GitHub private vulnerability reporting channel.
- full-SHA GitHub Action pinning with weekly Dependabot monitoring.

## [3.4.0] - 2026-08-15

### Added

- network retries with progressive backoff and atomic cache writes.
- tests for the CLI, network errors, duplicate and cyclic pages, HTML
  extraction, and missing system tools.
- Ruff analysis and a minimum 95% branch-coverage threshold in CI.
- compatibility tests on macOS and Windows.
- contribution guide, code of conduct, issue forms, and pull request template.

### Changed

- separated argument parsing from converter execution.
- split downloading, discovery, and page assignment responsibilities.
- derive the HTTP agent version from package metadata.
- split networking, HTML parsing, output generation, and the data model into
  focused modules while preserving the historical public interface.

### Fixed

- use POSIX URL path separators on Windows.
- reject negative delays in direct download API calls.
- invoke verified compiler executables without shell interpretation.

## [3.3.1] - 2026-08-15

### Added

- automatic GitHub Releases from `vX.Y.Z` tags.
- automatic wheel and source-distribution builds.
- secretless PyPI Trusted Publishing setup.
- weekly Dependabot updates for Python and GitHub Actions.
- CI, release, and license badges in the README.

### Changed

- avoid duplicate CI runs for pull request branches.
- cancel obsolete CI runs when a newer commit starts.
- migrate license metadata to the `GPL-3.0-or-later` SPDX expression.

## [3.3.0] - 2026-08-15

### Added

- complete GNU Info, PDF, and EPUB 3 generation.
- installable `cec2info` command and `pyproject.toml` metadata.
- human-readable and JSON generation reports.
- actual compilation tests for all three formats.
- continuous integration on Python 3.10 and 3.13.
- GNU GPL version 3 or later license for the converter.

### Fixed

- retain every paragraph from 1 through 2865 exactly once.
- recover orphan pages missing from the main navigation.
- separate caches for non-official source URLs.
- install the `Archive::Zip` dependency required for EPUB generation in CI.

### Changed

- make generation deterministic and validate it before creating output.
- document installation, CI, and generation reports.

[3.5.0]: https://github.com/fmaillar/cec-info/compare/v3.4.0...v3.5.0
[3.4.0]: https://github.com/fmaillar/cec-info/compare/v3.3.1...v3.4.0
[3.3.1]: https://github.com/fmaillar/cec-info/compare/v3.3.0...v3.3.1
[3.3.0]: https://github.com/fmaillar/cec-info/releases/tag/v3.3.0
