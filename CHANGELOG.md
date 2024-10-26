# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.3.0] - 2024-10-26

### Added

- Comprehensive docstrings following Google style
- Improved datetime handling with support for both 'Z' and '+00:00' timezone formats
- Enhanced validation for language codes and time formats

### Changed

- Standardized timezone output to use 'Z' format
- Improved error messages for validation issues
- Updated documentation structure and examples

### Fixed

- Fixed datetime parsing issues with different timezone formats
- Corrected validation of zero-duration segments
- Improved handling of empty extensions

## [0.2.0] - 2024-10-23

- Initial public release
- Basic functionality in `src/stjlib/stj.py`
- README.md with project description and usage instructions
- Documentation structure

[Unreleased]: https://github.com/yaniv-golan/stjlib/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/yaniv-golan/stjlib/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yaniv-golan/stjlib/releases/tag/v0.2.0
