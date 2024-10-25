# tests/test_stj.py

"""
Unit tests for the StandardTranscriptionJSON (STJ) implementation.

This module contains comprehensive tests for the STJ format wrapper,
including validation, serialization, and deserialization tests.
"""

import pytest
import json
import os
from datetime import datetime, timezone
from iso639 import Lang
from deepdiff import DeepDiff

# Import necessary classes and functions from stjlib
from stjlib import (
    StandardTranscriptionJSON,
    STJError,
    ValidationError,
    ValidationIssue,
    Transcriber,
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Style,
    WordTimingMode,
    WordDuration,
)


def test_load_valid_stj():
    """
    Test loading a valid STJ file.

    This test creates a valid STJ dictionary and verifies that it can
    correctly be loaded into a StandardTranscriptionJSON object.
    """
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0.0"},
            "version": "0.5.0",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
                    "word_timing_mode": "complete",
                    "is_zero_duration": False,
                }
            ],
        },
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    assert isinstance(stj, StandardTranscriptionJSON)
    assert stj.metadata.transcriber.name == "TestTranscriber"
    assert [lang.pt1 for lang in stj.metadata.languages] == ["en", "es"]
    assert stj.metadata.version == "0.5.0"
    assert stj.transcript.segments[0].text == "Hello world"


def test_validate_valid_stj():
    """
    Test validating a valid STJ instance.

    This test creates a valid STJ dictionary with various fields and
    verifies that it passes validation without any issues.
    """
    # Create objects directly instead of using dictionary
    transcriber = Transcriber(name="TestTranscriber", version="1.0.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime.now(timezone.utc),
        version="0.5.0",
        confidence_threshold=0.8,
        languages=[Lang("en")]
    )
    
    words = [
        Word(start=0.0, end=1.0, text="Hello", confidence=0.95),
        Word(start=1.0, end=2.0, text="world", confidence=0.9)
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
        word_timing_mode=WordTimingMode.COMPLETE  # Use enum value
    )
    
    transcript = Transcript(segments=[segment], speakers=[speaker])
    
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0


def test_validate_invalid_confidence():
    """
    Test validation catching invalid confidence scores.

    This test creates an STJ with invalid confidence scores and verifies
    that the validation process correctly identifies these issues.
    """
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "confidence_threshold": 1.5,  # Invalid confidence_threshold
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test segment",
                    "confidence": -0.1,  # Invalid confidence
                }
            ]
        },
    }
    # Deserialize without validation
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    # Validate explicitly
    issues = stj.validate(raise_exception=False)
    assert any("confidence_threshold" in issue.message for issue in issues)
    assert any("Segment confidence -0.1 out of range" in issue.message for issue in issues)


def test_validate_invalid_language_code():
    """Test validation catching invalid language codes."""
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "languages": ["invalid-code"],  # Invalid language code
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test segment",
                    "language": "invalid-code",  # Invalid language code in segment
                }
            ]
        },
    }
    # Deserialize without validation
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    # Validate explicitly
    issues = stj.validate(raise_exception=False)
    assert any("Invalid language code" in issue.message for issue in issues)


def test_missing_required_fields():
    """Test that missing required fields are caught during validation."""
    stj_data = {
        "metadata": {
            # 'transcriber' field is missing
            "version": "0.5.0",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "transcript": {"segments": []},
    }
    # Deserialize without validation
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    # Validate explicitly
    issues = stj.validate(raise_exception=False)
    assert any("Missing or invalid 'transcriber.name'" in issue.message for issue in issues)
    assert any("Missing or invalid 'transcriber.version'" in issue.message for issue in issues)
    assert any("Missing 'transcript.speakers'" in issue.message for issue in issues)
    assert any("There must be at least one segment" in issue.message for issue in issues)


def test_serialization():
    """
    Test that serialization includes the 'languages' field.

    This test verifies that the serialized dictionary matches the expected structure with the new field.
    """
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        version="0.5.0",
        confidence_threshold=0.8,
        languages=[Lang("en"), Lang("es")],
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
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    stj_dict = stj.to_dict()
    expected_dict = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",
            "created_at": "2023-01-01T00:00:00Z",
            "confidence_threshold": 0.8,
            "languages": ["en", "es"],
            "extensions": {},
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
                        {"start": 0.0, "end": 1.0, "text": "Hello", "extensions": {}},
                        {"start": 1.0, "end": 2.0, "text": "world", "extensions": {}},
                    ],
                    "extensions": {},
                }
            ],
        },
    }

    diff = DeepDiff(expected_dict, stj_dict, ignore_order=True)
    assert not diff, f"Differences found: {diff}"


def test_loading_from_file(tmp_path):
    """
    Test loading an STJ file from disk.

    This test creates a temporary STJ file, writes JSON data to it,
    and then verifies that it can be correctly loaded into an STJ object.
    """
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "transcript": {
            "segments": [{"start": 0.0, "end": 5.0, "text": "Test segment"}]
        },
    }
    file_path = tmp_path / "test.stj.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(stj_data, f)
    stj = StandardTranscriptionJSON.from_file(str(file_path))
    assert stj.transcript.segments[0].text == "Test segment"


def test_saving_to_file(tmp_path):
    """
    Test saving an STJ instance to disk.

    This test creates an STJ object, saves it to a file, and then
    verifies that the file contains the correct JSON data.
    """
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        version="0.5.0",
    )
    segment = Segment(start=0.0, end=2.0, text="Hello world")
    transcript = Transcript(segments=[segment])
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)

