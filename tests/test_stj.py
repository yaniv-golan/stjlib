# tests/test_stj.py

"""
Unit tests for the StandardTranscriptionJSON (STJ) implementation.

This module contains comprehensive tests for the STJ format wrapper,
including validation, serialization, and deserialization tests.

The tests verify:
1. Loading and parsing STJ data
2. Validation of STJ format requirements
3. Serialization of STJ objects
4. Error handling for invalid data
"""

import pytest
import json
from datetime import datetime, timezone
from deepdiff import DeepDiff

from stjlib import (
    StandardTranscriptionJSON,
    STJError,
    ValidationError,
)
from stjlib.core.data_classes import (
    STJ,
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Transcriber,
)
from stjlib.core.enums import WordTimingMode


def test_load_valid_stj():
    """Test loading a valid STJ file.

    This test verifies that:
    1. Valid STJ data can be deserialized into a StandardTranscriptionJSON object
    2. The deserialized object contains the expected values
    3. Basic metadata fields are correctly parsed
    """
    stj_data = {
        "stj": {
            "version": "0.6.0",
            "metadata": {
                "transcriber": {"name": "TestTranscriber", "version": "1.0.0"},
                "created_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "languages": ["en", "es"],
            },
            "transcript": {
                "speakers": [{"id": "speaker1", "name": "Speaker One"}],
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "Hello world",
                        "speaker_id": "speaker1",
                        "words": [
                            {"start": 0.0, "end": 1.0, "text": "Hello"},
                            {"start": 1.0, "end": 2.0, "text": "world"},
                        ],
                    }
                ],
            },
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    assert isinstance(stj, StandardTranscriptionJSON)
    assert stj.metadata.transcriber.name == "TestTranscriber"
    assert stj.stj.version == "0.6.0"
    assert stj.transcript.segments[0].text == "Hello world"


def test_validate_valid_stj():
    """Test validation of a valid STJ instance.

    This test verifies that:
    1. A properly constructed STJ object passes validation
    2. All required fields are accepted
    3. Optional fields with valid values are accepted
    4. Language codes are properly handled as strings
    """
    transcriber = Transcriber(name="TestTranscriber", version="1.0.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime.now(timezone.utc),
        languages=["en"],
    )

    words = [
        Word(start=0.0, end=1.0, text="Hello", confidence=0.95),
        Word(start=1.0, end=2.0, text="world", confidence=0.9),
    ]

    speaker = Speaker(id="speaker1", name="Speaker One")

    segment = Segment(
        start=0.0,
        end=5.0,
        text="Hello world",
        speaker_id="speaker1",
        confidence=0.9,
        language="en",
        words=words,
        word_timing_mode=WordTimingMode.COMPLETE,
    )

    transcript = Transcript(segments=[segment], speakers=[speaker])

    stj_instance = STJ(version="0.6.0", metadata=metadata, transcript=transcript)
    stj = StandardTranscriptionJSON(stj=stj_instance)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0


def test_validate_invalid_confidence():
    """Test validation of invalid confidence scores.

    This test verifies that:
    1. Confidence threshold > 1.0 is rejected
    2. Negative confidence scores are rejected
    3. Validation issues contain appropriate error messages
    """
    stj_data = {
        "stj": {
            "version": "0.6.0",
            "metadata": {
                "transcriber": {"name": "TestTranscriber", "version": "1.0"},
                "created_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "confidence_threshold": 1.5,  # Invalid: > 1.0
            },
            "transcript": {
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "Test segment",
                        "confidence": -0.1,  # Invalid: negative
                    }
                ]
            },
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    issues = stj.validate(raise_exception=False)
    assert any("confidence_threshold" in issue.message.lower() for issue in issues)
    assert any(
        "confidence" in issue.message.lower() and "-0.1" in issue.message
        for issue in issues
    )


def test_validate_invalid_language_code():
    """Test validation of invalid language codes.

    This test verifies that:
    1. Invalid language codes are rejected
    2. Language codes are validated in both metadata and segments
    3. Validation issues contain appropriate error messages
    """
    stj_data = {
        "stj": {
            "version": "0.6.0",
            "metadata": {
                "transcriber": {"name": "TestTranscriber", "version": "1.0"},
                "created_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "languages": ["invalid-code"],
            },
            "transcript": {
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "Test segment",
                        "language": "invalid-code",
                    }
                ]
            },
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    issues = stj.validate(raise_exception=False)
    assert any("invalid language code" in issue.message.lower() for issue in issues)


def test_missing_required_fields():
    """Test validation of missing required fields.

    This test verifies that:
    1. An empty 'transcript.segments' array is detected as invalid
    2. Validation issues contain appropriate error messages
    """
    stj_data = {
        "stj": {
            "version": "0.6.0",
            "metadata": {
                "created_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            "transcript": {"segments": []},
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    issues = stj.validate(raise_exception=False)
    # Remove assertions about 'transcriber' fields since they are optional
    assert any(
        "transcript.segments cannot be empty" in issue.message for issue in issues
    )


def test_serialization():
    """Test STJ object serialization.

    This test verifies that:
    1. STJ objects serialize to the expected JSON structure
    2. All fields are correctly represented in the output
    3. Optional fields are handled appropriately
    4. Language codes are properly serialized as strings
    5. DateTime values are formatted correctly
    """
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        confidence_threshold=0.8,
        languages=["en", "es"],
    )
    word1 = Word(start=0.0, end=1.0, text="Hello")
    word2 = Word(start=1.0, end=2.0, text="world")
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Hello world",
        words=[word1, word2],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=metadata, transcript=transcript)
    stj = StandardTranscriptionJSON(stj=stj_instance)
    stj_dict = stj.to_dict()
    expected_dict = {
        "stj": {
            "stj": {
                "version": "0.6.0",
                "metadata": {
                    "transcriber": {"name": "TestTranscriber", "version": "1.0"},
                    "created_at": "2023-01-01T00:00:00Z",
                    "confidence_threshold": 0.8,
                    "languages": ["en", "es"],
                },
                "transcript": {
                    "speakers": [],
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 2.0,
                            "text": "Hello world",
                            "word_timing_mode": "complete",
                            "words": [
                                {"start": 0.0, "end": 1.0, "text": "Hello"},
                                {"start": 1.0, "end": 2.0, "text": "world"},
                            ],
                        }
                    ],
                },
            }
        }
    }

    diff = DeepDiff(expected_dict, stj_dict, ignore_order=True)
    assert not diff, f"Differences found: {diff}"
