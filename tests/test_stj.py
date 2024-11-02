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
    Source,
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
    assert stj._stj.version == "0.6.0"
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

    stj = StandardTranscriptionJSON(
        metadata=metadata, transcript=transcript, validate=False
    )
    issues = stj.validate(raise_exception=False)
    assert issues is None, "Expected no validation issues"


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
    """Test STJ object serialization with specific fields."""
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
    # Explicitly create transcript with empty speakers list to indicate
    # speaker identification was attempted but found none
    transcript = Transcript(
        segments=[segment],
        speakers=[],  # Explicitly indicate speaker identification attempted
    )
    stj = StandardTranscriptionJSON(
        metadata=metadata, transcript=transcript, validate=False
    )
    stj_dict = stj.to_dict()
    expected_dict = {
        "stj": {  # Single nesting as per spec
            "version": "0.6.0",
            "metadata": {
                "transcriber": {"name": "TestTranscriber", "version": "1.0"},
                "created_at": "2023-01-01T00:00:00Z",
                "confidence_threshold": 0.8,
                "languages": ["en", "es"],
            },
            "transcript": {
                "speakers": [],  # Empty list indicates speaker id was attempted
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

    diff = DeepDiff(expected_dict, stj_dict, ignore_order=True)
    assert not diff, f"Differences found: {diff}"


def test_stj_serialization_structure():
    """Test STJ serialization produces correct structure."""
    # Test basic structure
    stj = StandardTranscriptionJSON()
    data = stj.to_dict()

    assert isinstance(data, dict)
    assert len(data) == 1
    assert "stj" in data
    assert isinstance(data["stj"], dict)
    assert "version" in data["stj"]
    assert "transcript" in data["stj"]


def test_stj_metadata_serialization():
    """Test metadata serialization is optional and correct."""
    # Test with metadata
    stj = StandardTranscriptionJSON(
        metadata=Metadata(transcriber=Transcriber(name="Test", version="1.0"))
    )
    data = stj.to_dict()

    assert "metadata" in data["stj"]
    assert isinstance(data["stj"]["metadata"], dict)

    # Test without metadata
    stj = StandardTranscriptionJSON(metadata=None)
    data = stj.to_dict()

    assert "metadata" not in data["stj"]


def test_stj_no_double_nesting():
    """Test there is no double nesting of 'stj' key."""
    stj = StandardTranscriptionJSON()
    data = stj.to_dict()

    assert "stj" not in data["stj"]


def test_empty_transcript_serialization():
    """Test serialization of empty transcript."""
    stj = StandardTranscriptionJSON(transcript=Transcript(segments=[]))
    data = stj.to_dict()

    assert data["stj"]["transcript"]["segments"] == []
    assert data["stj"]["transcript"]["speakers"] == []


def test_complex_metadata_serialization():
    """Test serialization with complex metadata."""
    metadata = Metadata(
        transcriber=Transcriber(name="Test", version="1.0"),
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        confidence_threshold=0.8,
        languages=["en", "es"],
        # Create a Source object instead of using a dict
        source=Source(uri="test.mp3", duration=100.5, languages=["fr"]),
    )
    stj = StandardTranscriptionJSON(metadata=metadata)
    data = stj.to_dict()

    assert data["stj"]["metadata"]["transcriber"]["name"] == "Test"
    assert data["stj"]["metadata"]["confidence_threshold"] == 0.8
    assert data["stj"]["metadata"]["source"]["duration"] == 100.5


def test_round_trip_serialization():
    """Test round-trip serialization (to_dict -> from_dict)."""
    original = StandardTranscriptionJSON(
        metadata=Metadata(transcriber=Transcriber(name="Test", version="1.0")),
        transcript=Transcript(
            segments=[Segment(text="Test segment", start=0.0, end=1.0)]
        ),
    )

    # Serialize and deserialize
    data = original.to_dict()
    roundtrip = StandardTranscriptionJSON.from_dict(data)

    # Verify data is preserved
    assert roundtrip.metadata.transcriber.name == "Test"
    assert roundtrip.transcript.segments[0].text == "Test segment"
    assert roundtrip.transcript.segments[0].start == 0.0


def test_invalid_metadata_structure():
    """Test error handling for invalid metadata structure."""
    # Test invalid metadata type
    stj = StandardTranscriptionJSON.from_dict(
        {
            "stj": {
                "version": "0.6.0",
                "metadata": "invalid",  # Should be dict
                "transcript": {"segments": [{"text": "Test"}]},
            }
        }
    )
    issues = stj.validate(raise_exception=False)
    assert any("metadata must be a dictionary" in issue.message for issue in issues)

    # Test invalid transcriber structure
    stj = StandardTranscriptionJSON.from_dict(
        {
            "stj": {
                "version": "0.6.0",
                "metadata": {
                    "transcriber": "invalid",  # Should be dict
                },
                "transcript": {"segments": [{"text": "Test"}]},
            }
        }
    )
    issues = stj.validate(raise_exception=False)
    assert any("transcriber must be a dictionary" in issue.message for issue in issues)


def test_invalid_transcript_structure():
    """Test error handling for invalid transcript structure."""
    # Test missing segments
    with pytest.raises(ValidationError) as exc_info:
        StandardTranscriptionJSON.from_dict(
            {"stj": {"version": "0.6.0", "transcript": {}}},  # Missing segments array
            validate=True,
        )
    assert "transcript.segments cannot be empty" in str(exc_info.value)

    # Test invalid segments type
    with pytest.raises(ValidationError) as exc_info:
        StandardTranscriptionJSON.from_dict(
            {
                "stj": {
                    "version": "0.6.0",
                    "transcript": {"segments": "invalid"},  # Should be array
                }
            },
            validate=True,
        )
    assert "segments must be an array" in str(exc_info.value)


def test_invalid_version():
    """Test error handling for invalid version."""
    # Test missing version
    with pytest.raises(ValidationError) as exc_info:
        StandardTranscriptionJSON.from_dict(
            {"stj": {"transcript": {"segments": [{"text": "Test"}]}}},
            validate=True,  # Ensure validation is performed
        )
    assert "Missing or invalid 'stj.version'" in str(exc_info.value)

    # Test incompatible version
    with pytest.raises(ValidationError) as exc_info:
        StandardTranscriptionJSON.from_dict(
            {
                "stj": {
                    "version": "0.7.0",  # Incompatible version
                    "transcript": {"segments": [{"text": "Test"}]},
                }
            },
            validate=True,  # Ensure validation is performed
        )
    assert "Incompatible version" in str(exc_info.value)


def test_add_segment():
    """Test adding segments to transcript."""
    stj = StandardTranscriptionJSON()

    # Test adding basic segment
    stj.add_segment(text="Hello world", start=0.0, end=1.0)
    assert len(stj.transcript.segments) == 1
    assert stj.transcript.segments[0].text == "Hello world"

    # Test adding segment with speaker
    stj.add_speaker("s1", "Speaker One")
    stj.add_segment(text="Test", start=1.0, end=2.0, speaker_id="s1")
    assert len(stj.transcript.segments) == 2
    assert stj.transcript.segments[1].speaker_id == "s1"

    # Test validation of segment parameters
    with pytest.raises(ValueError):
        stj.add_segment(text="", start=0.0, end=1.0)  # Empty text

    with pytest.raises(ValueError):
        stj.add_segment(text="Test", start=2.0, end=1.0)  # End before start


def test_add_speaker():
    """Test adding speakers to transcript."""
    stj = StandardTranscriptionJSON()

    # Test adding basic speaker
    stj.add_speaker("s1", "Speaker One")
    assert len(stj.transcript.speakers) == 1
    assert stj.transcript.speakers[0].id == "s1"
    assert stj.transcript.speakers[0].name == "Speaker One"

    # Test duplicate speaker ID
    with pytest.raises(ValueError):
        stj.add_speaker("s1", "Another Speaker")

    # Test empty speaker ID
    with pytest.raises(ValueError):
        stj.add_speaker("", "Invalid Speaker")


def test_get_speaker():
    """Test retrieving speakers by ID."""
    stj = StandardTranscriptionJSON()

    stj.add_speaker("s1", "Speaker One")
    speaker = stj.get_speaker("s1")
    assert speaker is not None
    assert speaker.id == "s1"
    assert speaker.name == "Speaker One"

    # Test non-existent speaker
    assert stj.get_speaker("non_existent") is None

    # Test invalid speaker ID
    with pytest.raises(ValueError):
        stj.get_speaker("")


def test_get_segments_by_speaker():
    """Test retrieving segments by speaker ID."""
    stj = StandardTranscriptionJSON()

    stj.add_speaker("s1", "Speaker One")
    stj.add_segment(text="Test 1", start=0.0, end=1.0, speaker_id="s1")
    stj.add_segment(text="Test 2", start=1.0, end=2.0, speaker_id="s1")
    stj.add_segment(text="Test 3", start=2.0, end=3.0)  # No speaker

    segments = stj.get_segments_by_speaker("s1")
    assert len(segments) == 2
    assert all(s.speaker_id == "s1" for s in segments)

    # Test non-existent speaker
    assert len(stj.get_segments_by_speaker("non_existent")) == 0

    # Test invalid speaker ID
    with pytest.raises(ValueError):
        stj.get_segments_by_speaker("")
