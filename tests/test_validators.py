# tests/test_validators.py

"""
Unit tests for the validation functions in the STJ implementation.

This module tests the validators to ensure they correctly identify
validation issues as per the STJ specification.
"""

import pytest
from stjlib.core.data_classes import (
    STJ,
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Transcriber,
    Style,
    Source,
)
from stjlib.core.enums import WordTimingMode
from stjlib.validation import (
    ValidationIssue,
    ValidationSeverity,
    validate_stj,
)
from datetime import datetime, timezone
from decimal import Decimal


def test_validate_version():
    """Test validation of the STJ version."""
    stj_instance = STJ(version="0.7.0", metadata=None, transcript=Transcript())
    issues = validate_stj(stj_instance)
    assert any(
        "Incompatible version: 0.7.0. Supported major.minor version is '0.6.x'."
        in issue.message
        for issue in issues
    )


def test_validate_missing_transcript():
    """Test validation when transcript is missing."""
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=None)
    issues = validate_stj(stj_instance)
    assert any(
        "Missing required field: 'transcript'" in issue.message for issue in issues
    )


def test_validate_empty_segments():
    """Test validation when segments are empty."""
    stj_instance = STJ(
        version="0.6.0", metadata=None, transcript=Transcript(segments=[])
    )
    issues = validate_stj(stj_instance)
    assert any(
        "transcript.segments cannot be empty" in issue.message for issue in issues
    )


def test_validate_invalid_time_format():
    """Test validation of invalid time formats."""
    word = Word(start=-1.0, end=1.0, text="Hello")
    segment = Segment(
        start=-1.0,
        end=1.0,
        text="Hello",
        words=[word],
        word_timing_mode="complete",
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)
    assert any("Time value must be non-negative" in issue.message for issue in issues)


def test_validate_metadata():
    """Test validation of metadata fields."""
    metadata = Metadata(
        transcriber=Transcriber(name="", version="1.0"),  # Empty name should fail
        created_at=datetime.now(),  # Non-timezone-aware should fail
        confidence_threshold=2.0,  # Out of range should fail
    )
    stj_instance = STJ(
        version="0.6.0",
        metadata=metadata,
        transcript=Transcript(segments=[Segment(text="Test segment")]),
    )
    issues = validate_stj(stj_instance)

    assert any(
        "datetime object must be timezone-aware" in issue.message for issue in issues
    )
    assert any(
        "confidence_threshold" in issue.message and "out of range" in issue.message
        for issue in issues
    )


def test_validate_word_timing_modes():
    """Test validation of word timing modes."""
    # Test complete word timing mode with missing timing
    segment_incomplete = Segment(
        text="Test segment",
        word_timing_mode="complete",
        words=[Word(text="Test", start=None, end=None)],
    )
    transcript_incomplete = Transcript(segments=[segment_incomplete])
    stj_incomplete = STJ(
        version="0.6.0", metadata=None, transcript=transcript_incomplete
    )
    issues_incomplete = validate_stj(stj_incomplete)

    assert any(
        "timing data when word_timing_mode is 'complete'" in issue.message
        for issue in issues_incomplete
    )


def test_validate_overlapping_segments():
    """Test validation of overlapping segments."""
    transcript = Transcript(
        segments=[
            Segment(text="First", start=0.0, end=2.0),
            Segment(text="Second", start=1.0, end=3.0),  # Overlaps with first segment
        ]
    )
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any("Segments must not overlap" in issue.message for issue in issues)


def test_validate_style_references():
    """Test validation of style references."""
    transcript = Transcript(
        segments=[Segment(text="Test", style_id="non_existent_style")],
        styles=[Style(id="existing_style")],
    )
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Invalid style_id reference: non_existent_style" in issue.message
        for issue in issues
    )


def test_validate_extensions():
    """Test validation of extensions."""
    segment = Segment(
        text="Test",
        extensions={
            "stj": {},  # Reserved namespace
            "custom": {"extensions": {"custom": {}}},  # Circular reference
        },
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Reserved namespace 'stj' cannot be used" in issue.message for issue in issues
    )
    assert any(
        "Circular reference detected in extensions" in issue.message for issue in issues
    )


def test_validate_zero_duration():
    """Test validation of zero duration segments and words."""
    segment = Segment(
        text="Test",
        start=1.0,
        end=1.0,
        is_zero_duration=False,  # Should be True for zero duration
        words=[Word(text="Test", start=1.0, end=1.0, is_zero_duration=False)],
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Zero duration item must have is_zero_duration set to true" in issue.message
        for issue in issues
    )


def test_validate_confidence_scores():
    """Test validation of confidence scores."""
    segment = Segment(
        text="Test",
        confidence=1.5,  # Invalid confidence score > 1.0
        words=[
            Word(text="Test", confidence=-0.1, start=0.0, end=1.0)
        ],  # Added timing data
        word_timing_mode="complete",
        start=0.0,  # Added segment timing
        end=1.0,
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "confidence" in issue.message
        and "1.5" in issue.message
        and "out of range" in issue.message
        for issue in issues
    )


def test_validate_speaker_references():
    """Test validation of speaker references."""
    transcript = Transcript(
        segments=[Segment(text="Test", speaker_id="non_existent_speaker")],
        speakers=[Speaker(id="existing_speaker", name="Test Speaker")],
    )
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Invalid speaker_id reference: non_existent_speaker" in issue.message
        for issue in issues
    )


def test_validate_segment_text_matches_words():
    """Test validation that segment text matches concatenated word texts."""
    segment = Segment(
        text="Hello world",
        word_timing_mode="complete",
        start=0.0,
        end=1.0,
        words=[
            Word(text="Hello", start=0.0, end=0.5),
            Word(
                text="there", start=0.5, end=1.0
            ),  # Different word instead of capitalization mismatch
        ],
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Segment text does not match concatenated word texts" in issue.message
        for issue in issues
    )


def test_validate_word_timing_sequence():
    """Test validation of word timing sequence within segments."""
    segment = Segment(
        text="Test sequence",
        words=[
            Word(text="Test", start=1.0, end=2.0),
            Word(text="sequence", start=1.5, end=2.5),  # Overlapping with previous word
        ],
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Words within segment must not overlap in time" in issue.message
        for issue in issues
    )


def test_validate_unique_ids():
    """Test validation of unique IDs for speakers and styles."""
    transcript = Transcript(
        segments=[Segment(text="Test")],
        speakers=[
            Speaker(id="speaker1", name="Speaker 1"),
            Speaker(id="speaker1", name="Speaker 2"),  # Duplicate ID
        ],
        styles=[Style(id="style1"), Style(id="style1")],  # Duplicate ID
    )
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any("Duplicate speaker ID: speaker1" in issue.message for issue in issues)
    assert any("Duplicate style ID: style1" in issue.message for issue in issues)


def test_validate_decimal_precision():
    """Test validation of decimal precision for timing values."""
    segment = Segment(
        text="Test",
        start=Decimal("1.2345678"),  # Too many decimal places
        end=Decimal("2.0"),
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=None, transcript=transcript)
    issues = validate_stj(stj_instance)

    assert any(
        "Time value has too many decimal places; maximum allowed is 3 decimal places"
        in issue.message
        for issue in issues
    )


def test_validate_time_formats():
    """Test validation of time formats according to spec requirements."""

    def create_stj_with_time(time_value):
        return STJ(
            version="0.6.0",
            transcript=Transcript(
                segments=[
                    # Use time_value for both start and end to avoid exceeding max
                    Segment(text="Test", start=time_value, end=time_value)
                ]
            ),
        )

    # Test valid times
    valid_times = [0, 0.0, 0.000, 1.5, 10.100, 999999.999]
    for time in valid_times:
        stj = create_stj_with_time(time)
        issues = validate_stj(stj)
        assert not any(
            (
                "time value" in issue.message.lower()
                and (
                    "invalid" in issue.message.lower()
                    or "must be non-negative" in issue.message.lower()
                    or "exceeds maximum" in issue.message.lower()
                    or "decimal places" in issue.message.lower()
                )
            )
            for issue in issues
        ), f"Time {time} should be valid"

    # Test invalid times
    invalid_times = [
        -1.0,  # Negative values not allowed
        1000000.0,  # Exceeds maximum value
        1.2345,  # Too many decimal places
    ]

    for time in invalid_times:
        stj = create_stj_with_time(time)
        issues = validate_stj(stj)
        assert any(
            (
                "time value" in issue.message.lower()
                and (
                    "invalid" in issue.message.lower()
                    or "must be non-negative" in issue.message.lower()
                    or "exceeds maximum" in issue.message.lower()
                    or "decimal places" in issue.message.lower()
                )
            )
            for issue in issues
        ), f"Time {time} should be invalid"


def test_invalid_additional_properties():
    """Test validation of unexpected fields in root object."""
    stj_data = {
        "stj": {
            "version": "0.6.0",
            "unexpected_field": "unexpected",  # Invalid additional property
            "transcript": {
                "segments": [{"start": 0.0, "end": 5.0, "text": "Sample text"}]
            },
        }
    }
    stj = STJ.from_dict(stj_data)
    validation_issues = validate_stj(stj)

    assert validation_issues  # Should have validation issues
    assert any(
        "Unexpected fields in stj: unexpected_field" in issue.message
        for issue in validation_issues
    ), "Should detect unexpected field in root object"


def test_validate_invalid_iso639_1_code():
    """Test validation of invalid ISO 639-1 code."""
    metadata = Metadata(
        languages=["xx"],  # Invalid ISO 639-1 code
    )
    stj_instance = STJ(
        version="0.6.0",
        metadata=metadata,
        transcript=Transcript(segments=[Segment(text="Test")]),
    )
    issues = validate_stj(stj_instance)

    messages = [issue.message for issue in issues]

    assert any("Invalid ISO 639-1 language code 'xx'" in msg for msg in messages)


def test_validate_iso639_3_code_with_iso639_1_available():
    """Test validation enforcing ISO 639-1 code when available."""
    metadata = Metadata(
        languages=["eng"],  # Should use 'en' instead
    )
    stj_instance = STJ(
        version="0.6.0",
        metadata=metadata,
        transcript=Transcript(segments=[Segment(text="Test")]),
    )
    issues = validate_stj(stj_instance)

    messages = [issue.message for issue in issues]

    assert any(
        "Must use ISO 639-1 code 'en' instead of ISO 639-3 code 'eng'" in msg
        for msg in messages
    )
