# STJLib

[![PyPI](https://img.shields.io/pypi/v/stjlib)](https://pypi.org/project/stjlib/)
[![Build Status](https://github.com/yourusername/stjlib/actions/workflows/python-package.yml/badge.svg)](https://github.com/yourusername/stjlib/actions)

A Python library for the Standard Transcription JSON (STJ) format.

## Overview

**STJLib** provides data classes and utilities for working with STJ files, which are used to represent transcribed audio and video data in a structured, machine-readable JSON format.

For more information about the STJ format, please refer to the [STJ Specification](https://github.com/yaniv-golan/STJ).

## Features

- Load and save STJ files.
- Validate STJ data according to the specification.
- Access and manipulate metadata and transcript data.
- Flexible error handling and validation reporting.

## Installation

You can install **STJLib** from PyPI:

```bash
pip install stjlib
```

## Usage

### Loading an STJ File

```python
from stjlib import StandardTranscriptionJSON

# Load an STJ file without validation
stj = StandardTranscriptionJSON.from_file('path/to/your_file.stj.json')

# Perform validation when ready
issues = stj.validate(raise_exception=False)
if issues:
    print("Validation issues found:")
    for issue in issues:
        print(issue)
else:
    print("Validation succeeded.")

# Access metadata and transcript data
print(stj.metadata)
print(stj.transcript)

# Save the STJ data back to a file
stj.to_file('path/to/output_file.stj.json')
```

### Handling Validation Issues

```python
from stjlib import ValidationError

try:
    # Load and validate the STJ file
    stj = StandardTranscriptionJSON.from_file('path/to/your_file.stj.json', validate=True)
except ValidationError as e:
    print("Validation failed:")
    print(e)
    # Access the list of issues
    for issue in e.issues:
        print(issue)
else:
    print("File loaded and validated successfully.")
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a Pull Request.

## Running Tests

We use `pytest` for testing. To run tests:

```bash
pip install -e .
pip install -r requirements-dev.txt
pytest
```

## Building Documentation

Documentation is generated using Sphinx. To build the documentation:

```bash
cd docs
make html
```

The documentation will be available in `docs/_build/html`.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For questions or comments, please open an issue on GitHub.
