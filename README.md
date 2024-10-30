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

- Load and save STJ files
- Validate STJ data according to the specification
- Access and manipulate metadata and transcript data
- Flexible error handling and validation reporting

## Quick Start

### Installation

```bash
pip install stjlib
```

### Basic Usage

```python
from stjlib import StandardTranscriptionJSON

# Load and validate an STJ file
stj = StandardTranscriptionJSON.from_file('path/to/file.stjson', validate=True)

# Access metadata and transcript data
print(stj.metadata)
print(stj.transcript)

# Add a segment with word timing
segment = {
    "start": 0.0,
    "end": 5.0,
    "text": "Hello world",
    "word_timing_mode": "complete",
    "words": [
        {"start": 0.0, "end": 1.0, "text": "Hello"},
        {"start": 1.0, "end": 2.0, "text": "world"}
    ]
}
stj.transcript.segments.append(segment)

# Save to file
stj.to_file('output.stjson')
```

For more examples and detailed usage instructions, please refer to our [documentation](https://stjlib.readthedocs.io/).

## File Format Support

STJLib supports the Standard Transcription JSON (STJ) format with the following file extensions:

- Primary (Recommended): `.stjson`
- Alternative: `.stj`
- Alternative: `.stj.json` (systems supporting double extensions)

MIME Type: `application/vnd.stj+json` (fallback: `application/json`)

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
