# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Validation for unexpected fields in all STJ elements (metadata, transcript, segments, words, speakers, styles)

### Changed

### Deprecated

### Removed

### Fixed

### Security

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

[Unreleased]: https://github.com/yaniv-golan/stjlib/compare/v0.3.2...HEAD
[0.3.0]: https://github.com/yaniv-golan/stjlib/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yaniv-golan/stjlib/releases/tag/v0.2.0
