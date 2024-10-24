# tests/test_stj.py

"""
Unit tests for the StandardTranscriptionJSON (STJ) implementation.

This module contains comprehensive tests for the STJ format wrapper,
including validation, serialization, and deserialization tests.
"""

import pytest
from stjlib import (
    StandardTranscriptionJSON,
    STJError,
    ValidationError,
    ValidationIssue,
    WordTimingMode,
    WordDuration,
    Transcriber,
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Style,
)
from iso639 import Lang
from datetime import datetime, timezone
import json
import os
from deepdiff import DeepDiff


def test_load_valid_stj():
    """
    Test loading a valid STJ file.

    This test creates a valid STJ dictionary and verifies that it can
    correctly loaded into a StandardTranscriptionJSON object.
    """
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0.0"},
            "version": "0.5.0",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),  # Already a string
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
                    "word_timing_mode": "complete",  # Use string directly instead of enum value
                    "is_zero_duration": False,
                }
            ],
        },
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    assert isinstance(stj, StandardTranscriptionJSON)
    assert stj.metadata.transcriber.name == "TestTranscriber"
    # Update the test to compare Lang objects
    assert [lang.pt1 for lang in stj.metadata.languages] == ["en", "es"]  # Compare primary language codes
    assert stj.metadata.version == "0.5.0"  # Verify metadata.version
    assert stj.transcript.segments[0].text == "Hello world"


def test_validate_valid_stj():
    """
    Test validating a valid STJ instance.

    This test creates a valid STJ dictionary with various fields and
    verifies that it passes validation without any issues.
    """
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0.0"},  # Changed from "1.0" to "1.0.0"
            "version": "0.5.0",  # Added metadata.version as per spec v0.5.0
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "confidence_threshold": 0.8,
        },
        "transcript": {
            "speakers": [{"id": "speaker1", "name": "Speaker One"}],
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Hello world",
                    "speaker_id": "speaker1",
                    "confidence": 0.9,
                    "words": [
                        {"start": 0.0, "end": 1.0, "text": "Hello", "confidence": 0.95},
                        {"start": 1.0, "end": 2.0, "text": "world", "confidence": 0.9},
                    ],
                    "word_timing_mode": "complete",
                }
            ],
        },
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
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
            "version": "0.5.0",  # Added required version field
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
    # Create the object without validation
    stj = StandardTranscriptionJSON.from_dict(stj_data, validate=False)

    # Then validate and check the issues
    with pytest.raises(ValidationError) as exc_info:
        stj.validate()

    # Verify both validation issues are present in the error message
    error_message = str(exc_info.value)
    assert "confidence_threshold 1.5 out of range" in error_message
    assert "Segment confidence -0.1 out of range" in error_message


def test_validate_invalid_language_code():
    """Test validation catching invalid language codes."""
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",  # Added required version field
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "languages": ["invalid-code"],  # Invalid language code for testing
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

    with pytest.raises(ValidationError) as exc_info:
        stj = StandardTranscriptionJSON.from_dict(stj_data)
        stj.validate()

    assert "Invalid language code" in str(exc_info.value)


def test_missing_required_fields():
    """Test that missing required fields raise KeyError."""
    stj_data = {
        "metadata": {
            # 'transcriber' field is missing
            "version": "0.5.0",  # Added required version field
            "created_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        },
        "transcript": {"segments": []},
    }
    with pytest.raises(KeyError) as excinfo:
        StandardTranscriptionJSON.from_dict(stj_data)
    assert "transcriber" in str(excinfo.value)


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
            "version": "0.5.0",  # Added required version field
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
        version="0.5.0",  # Added required version field
    )
    segment = Segment(start=0.0, end=2.0, text="Hello world")
    transcript = Transcript(segments=[segment])
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    file_path = tmp_path / "test_output.stj.json"
    stj.to_file(str(file_path))
    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["metadata"]["transcriber"]["name"] == "TestTranscriber"
    assert data["transcript"]["segments"][0]["text"] == "Hello world"


def test_additional_info():
    """Test handling of additional_info fields."""
    word = Word(
        start=1.0,
        end=1.0,  # Changed to match start for zero duration
        text="Hello",
        extensions={
            "word_duration": "zero"
        },  # Renamed from "additional_info" to "extensions"
    )
    segment = Segment(
        start=1.0,
        end=1.0,  # Changed to match start for zero duration
        text="Hello",
        words=[word],
        is_zero_duration=True,  # This is now valid since start equals end
        word_timing_mode=WordTimingMode.COMPLETE,
        extensions={},  # Renamed from "additional_info" to "extensions"
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0


def test_invalid_word_timing_mode():
    """Test validation catching invalid word_timing_mode."""
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",  # Added required version field
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Hello world",
                    "word_timing_mode": "invalid_mode",
                }
            ]
        },
    }

    with pytest.raises(ValidationError) as exc_info:
        stj = StandardTranscriptionJSON.from_dict(stj_data)

    assert "Invalid word_timing_mode" in str(exc_info.value)


def test_word_timings_outside_segment():
    """Test validation catching word timings outside segment timings."""
    word = Word(start=6.0, end=7.0, text="Test")  # Word outside segment timing
    segment = Segment(
        start=0.0,
        end=5.0,
        text="Test",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Word timings are outside segment timings" in issues[0].message


def test_segments_overlap():
    """Test validation catching overlapping segments."""
    segment1 = Segment(start=0.0, end=5.0, text="Segment 1")
    segment2 = Segment(start=4.0, end=6.0, text="Segment 2")  # Overlaps with segment1
    transcript = Transcript(segments=[segment1, segment2])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Segments overlap or are out of order" in issues[0].message


def test_invalid_speaker_id():
    """Test validation catching invalid speaker_id."""
    segment = Segment(start=0.0, end=5.0, text="Test", speaker_id="invalid_speaker")
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Invalid speaker_id" in issues[0].message


def test_invalid_style_id():
    """Test validation catching invalid style_id."""
    segment = Segment(start=0.0, end=5.0, text="Test", style_id="invalid_style")
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Invalid style_id" in issues[0].message


def test_zero_duration_segment():
    """Test validation of zero-duration segment with proper segment_duration."""
    segment = Segment(
        start=5.0, 
        end=5.0, 
        text="Test",  # Empty text is not allowed
        is_zero_duration=True,  # Set is_zero_duration directly
        extensions={}  # Remove segment_duration from extensions
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime.now(timezone.utc),
        version="0.5.0",
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0


def test_zero_duration_word():
    """Test validation of zero-duration word with proper word_duration."""
    word = Word(
        start=1.0, 
        end=1.0, 
        text="Test",  # Empty text is not allowed
        extensions={"word_duration": "zero"}
    )
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Test",  # Match the word text
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime.now(timezone.utc),
        version="0.5.0",
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0


def test_word_confidence_out_of_range():
    """Test validation catching word confidence out of range."""
    word = Word(start=0.0, end=1.0, text="Test", confidence=1.5)  # Invalid confidence
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Test",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Word confidence" in issues[0].message


def test_segment_text_word_mismatch():
    """Test validation catching mismatch between segment text and concatenated words."""
    word1 = Word(start=0.0, end=1.0, text="Hello")
    word2 = Word(start=1.0, end=2.0, text="Universe")  # Mismatch here
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Hello world",
        words=[word1, word2],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "does not match concatenated word texts" in issues[0].message


def test_word_overlap():
    """Test validation catching overlapping words."""
    word1 = Word(start=0.0, end=2.0, text="Hello")
    word2 = Word(start=1.5, end=3.0, text="world")  # Overlaps with word1
    segment = Segment(
        start=0.0,
        end=3.0,
        text="Hello world",
        words=[word1, word2],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber, 
        created_at=datetime.now(timezone.utc),
        version="0.5.0",  # Added required version field
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Words overlap or are out of order" in issues[0].message


def test_validate_languages_field():
    """
    Test validation of the 'languages' field in STJ.

    Ensures that only supported language codes are accepted.
    """
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",  # Add required version field
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "languages": ["en", "invalid-lang"],
        },
        "transcript": {"speakers": [], "segments": []},
    }
    with pytest.raises(ValidationError) as exc_info:
        stj = StandardTranscriptionJSON.from_dict(stj_data)
    assert "Invalid language code" in str(exc_info.value)


def test_validate_metadata_version():
    """
    Test validation of the 'metadata.version' field in STJ.

    Ensures that the version follows the semantic versioning format.
    """
    # Test with valid version format
    stj_data_valid = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "0.5.0",  # Valid semantic version
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "languages": ["en", "es"],
        },
        "transcript": {"speakers": [], "segments": []},
    }
    stj_valid = StandardTranscriptionJSON.from_dict(stj_data_valid)
    issues_valid = stj_valid.validate(raise_exception=False)
    assert len(issues_valid) == 0

    # Test with invalid version format
    stj_data_invalid = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "version": "invalid-version",  # Invalid version format
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "languages": ["en", "es"],
        },
        "transcript": {"speakers": [], "segments": []},
    }
    stj_invalid = StandardTranscriptionJSON.from_dict(stj_data_invalid, validate=False)
    issues_invalid = stj_invalid.validate(raise_exception=False)
    assert len(issues_invalid) == 1
    assert "Invalid version format" in issues_invalid[0].message
    assert issues_invalid[0].location == "metadata.version"




















