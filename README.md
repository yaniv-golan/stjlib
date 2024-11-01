# STJLib

[![PyPI](https://img.shields.io/pypi/v/stjlib)](https://pypi.org/project/stjlib/)
[![Build Status](https://github.com/yaniv-golan/stjlib/actions/workflows/python-package.yml/badge.svg)](https://github.com/yaniv-golan/stjlib/actions)
[![Documentation Status](https://readthedocs.org/projects/stjlib/badge/?version=latest)](https://stjlib.readthedocs.io/latest/?badge=latest)

A Python library for the Standard Transcription JSON (STJ) format.

## Overview

**STJLib** provides data classes and utilities for working with STJ files, which are used to represent transcribed audio and video data in a structured, machine-readable JSON format.

For more information about the STJ format, please refer to the [STJ Specification](https://github.com/yaniv-golan/STJ).

## Documentation

Full documentation is available at [stjlib.readthedocs.io](https://stjlib.readthedocs.io/). This includes:

- Detailed API reference
- Usage examples
- Advanced usage guides
- Contributing guidelines

## Features

- Full support for STJ format version 0.6.0
- Comprehensive validation system with severity levels (ERROR, WARNING, INFO)
- Time value precision handling with IEEE 754 round-to-nearest-even
- Strict language code validation (ISO 639-1/639-3)
- Support for zero-duration segments
- Word timing modes (complete, partial, none)
- Enhanced speaker and style validation
- Extensions field validation with reserved namespace protection

## Quick Start

### Installation

```bash
pip install stjlib
```

### Basic Usage

```python
from stjlib import StandardTranscriptionJSON

# Load and validate an existing STJ file
stj = StandardTranscriptionJSON.from_file('path/to/file.stjson', validate=True)

# Or create a new STJ document
stj = StandardTranscriptionJSON(version="0.6.0")

# Add transcriber information
stj.metadata.transcriber = {
    "name": "TestTranscriber",
    "version": "1.0"
}

# Add a simple segment
segment = {
    "start": 0.0,
    "end": 2.0,
    "text": "Hello world"
}
stj.transcript.segments.append(segment)

# Save to file
stj.save('output.stjson')

# Access metadata and transcript data
print(stj.metadata)
print(stj.transcript)
```

For more examples and detailed usage instructions, please refer to our [documentation](https://stjlib.readthedocs.io/).

## File Format Support

STJLib supports the Standard Transcription JSON (STJ) format with the following file extensions:

- Primary (Recommended): `.stjson`
- Alternative: `.stj`
- Alternative: `.stj.json` (systems supporting double extensions)

MIME Type: `application/vnd.stj+json`

## Validation Features

- Severity levels: ERROR, WARNING, INFO
- Detailed location information in error messages
- Time value precision validation
- Language code validation (ISO 639-1/639-3)
- Segment ordering and overlap validation
- Speaker and style validation
- URI format validation
- Extensions validation with namespace protection

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/yaniv-golan/stjlib.git
cd stjlib

# Install development dependencies
pip install -e .
pip install -r requirements-dev.txt
```

### Running Tests

```bash
pytest
```

### Building Documentation Locally

```bash
cd docs
make html
```

The documentation will be available in `docs/build/html`.

## Contributing

We welcome contributions to stjlib! Please see our [Contributing Guide](CONTRIBUTING.md) for more details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- For bugs and feature requests, please [open an issue](https://github.com/yaniv-golan/stjlib/issues)
- For other questions, start a [GitHub Discussion](https://github.com/yaniv-golan/stjlib/discussions)
