# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [0.6.4] - 2025-11-15

### Changed

- Dropped support for Python 3.8. STJLib now requires Python 3.9 or newer.
- Added automated release workflow via GitHub Actions & PyPI Trusted Publishing.
- Bumped development tooling (DeepDiff 8.6.1+, Black 24.3+) to address upstream
  vulnerabilities.

## [0.6.0] - 2025-11-15

### Changed

- Bumped the default STJ specification version to 0.6.1, ensuring documentation, tests, and runtime defaults all reference the latest spec patch release.
- Enforced STJ 0.6.1 validation requirements for non-empty `languages` arrays, uniform segment timing once any segment is timed, stricter word timing/text alignment (including partial mode), and preservation of confidence-null semantics.
- Updated core data classes to retain explicit `null` confidence values plus intentionally empty metadata/extension objects during serialization.
- Expanded validator and data-class test coverage to capture the new compliance rules.
- Data-class loaders now preserve malformed input for validation instead of raising, and validation reporting covers bad speaker/style/word arrays even when inputs are arbitrary types.
- Validation pipeline now reports all issues in one run (no short-circuiting after version/root errors) and word/segment text comparisons normalize punctuation/whitespace to avoid noisy warnings.
- `StandardTranscriptionJSON.to_dict()` delegates to the underlying STJ object so unknown root fields survive round-trips; docs now pick up the real package version automatically.
- Removed the unused `jsonschema` dependency mention from installation docs and added the missing Code of Conduct referenced by CONTRIBUTING.
- Test harness inserts `src/` on `sys.path` automatically for pytest, guaranteeing tests run from a fresh checkout without manual PYTHONPATH tweaks.

## [0.5.0]

### Changed

- Updated iso639-lang requirement to >=2.5.0
- Improved language code validation to enforce ISO 639-1 when available
- Enhanced error handling for invalid input types in metadata and transcript
- Improved validation of transcript structure and segments
- Better handling of empty speakers list to indicate attempted speaker identification
- More robust validation of dictionary types throughout the codebase

### Fixed

- Fixed handling of invalid input types in STJ data structures
- Improved validation messages for language codes
- Better error handling for invalid metadata structures
- Fixed validation of confidence scores
- More precise error messages for invalid data types

## [0.4.0]

### Added

- Support for STJ format version 0.6.0
- Comprehensive validation system with severity levels (ERROR, WARNING, INFO)
- Time value precision handling with IEEE 754 round-to-nearest-even
- Zero-duration segment support with `is_zero_duration` field
- Strict language code validation (ISO 639-1/639-3)
- Support for new file extensions (.stjson, .stj, .stj.json)
- MIME type support: application/vnd.stj+json
- Word timing modes (complete, partial, none)
- Enhanced speaker and style validation
- URI format validation
- Extensions field validation with reserved namespace protection

### Changed

- Updated validation to match STJ 0.6.0 specification
- Improved error messages with detailed location information
- Enhanced time value handling with 3-decimal precision
- Stricter validation for segment ordering and overlap
- Updated language code handling to prefer ISO 639-1

### Deprecated

- Old file extension recommendations (.stj.json as primary)
- Previous validation severity system

## [0.3.2] - 2024-10-26

### Changed

- Changed JSON output to consistently order speakers before segments in transcript section

### Fixed

- Fixed handling of empty speakers list in validation and serialization

## [0.3.0] - 2024-10-26

### Added

- Comprehensive validation system with detailed error messages
- Core data classes for improved type safety and structure
- Support for extensions in all major components
- Enhanced language code validation and handling
- Improved datetime handling with timezone support
- New validation module with extensive checks
- Detailed docstrings following Google style

### Changed

- Restructured package into modular components
- Improved error handling and validation messages
- Enhanced type checking and validation
- Updated version handling to require 0.5.x or higher
- Standardized code formatting and documentation
- Improved test coverage and organization

### Fixed

- Fixed datetime parsing issues with different timezone formats
- Corrected validation of zero-duration segments
- Improved handling of empty extensions
- Fixed language code validation edge cases

## [0.2.0] - 2024-10-23

- Initial public release
- Basic functionality in `src/stjlib/stj.py`
- README.md with project description and usage instructions
- Documentation structure

[0.3.0]: https://github.com/yaniv-golan/stjlib/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yaniv-golan/stjlib/releases/tag/v0.2.0
