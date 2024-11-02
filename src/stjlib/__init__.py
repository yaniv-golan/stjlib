# src/stjlib/__init__.py

"""
STJLib: Standard Transcription JSON Format Handler.

This package provides a comprehensive implementation of the Standard Transcription
JSON (STJ) format for representing transcribed audio and video data.
"""

from .stj import (
    StandardTranscriptionJSON,
    STJError,
    ValidationError,
)
from .core.data_classes import (
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Style,
    Source,
    Transcriber,
)
from .core.enums import WordTimingMode
from .validation import ValidationIssue

__all__ = [
    "StandardTranscriptionJSON",
    "STJError",
    "ValidationError",
    "Metadata",
    "Transcript",
    "Segment",
    "Word",
    "Speaker",
    "Style",
    "Source",
    "Transcriber",
    "WordTimingMode",
    "ValidationIssue",
]

__version__ = "0.5.0"
