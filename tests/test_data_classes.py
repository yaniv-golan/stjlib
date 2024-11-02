# tests/test_data_classes.py

"""
Unit tests for the core data classes in the STJ implementation.

This module tests the serialization and deserialization of data classes,
ensuring that they correctly handle various input scenarios.
"""

import pytest
from datetime import datetime, timezone

from stjlib.core.data_classes import (
    STJ,
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Style,
    Transcriber,
)
from stjlib.core.enums import WordTimingMode


def test_transcriber_serialization():
    """Test serialization and deserialization of Transcriber."""
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    data = transcriber.to_dict()
    expected = {"name": "TestTranscriber", "version": "1.0"}
    assert data == expected
    transcriber_deserialized = Transcriber.from_dict(data)
    assert transcriber == transcriber_deserialized


def test_metadata_serialization():
    """Test serialization and deserialization of Metadata."""
    metadata = Metadata(
        transcriber=Transcriber(name="TestTranscriber", version="1.0"),
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        confidence_threshold=0.8,
        languages=["en", "es"],
    )
    data = metadata.to_dict()
    expected = {
        "transcriber": {"name": "TestTranscriber", "version": "1.0"},
        "created_at": "2023-01-01T00:00:00Z",
        "confidence_threshold": 0.8,
        "languages": ["en", "es"],
    }
    assert data == expected
    metadata_deserialized = Metadata.from_dict(data)
    assert metadata == metadata_deserialized


def test_segment_serialization():
    """Test serialization and deserialization of Segment."""
    word1 = Word(start=0.0, end=1.0, text="Hello")
    word2 = Word(start=1.0, end=2.0, text="world")
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Hello world",
        words=[word1, word2],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    data = segment.to_dict()
    expected = {
        "start": 0.0,
        "end": 2.0,
        "text": "Hello world",
        "word_timing_mode": "complete",
        "words": [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "world"},
        ],
    }
    assert data == expected
    segment_deserialized = Segment.from_dict(data)
    assert segment == segment_deserialized


def test_transcript_serialization():
    """Test serialization and deserialization of Transcript."""
    speaker = Speaker(id="speaker1", name="Speaker One")
    word = Word(start=0.0, end=1.0, text="Hello")
    segment = Segment(
        start=0.0,
        end=1.0,
        text="Hello",
        speaker_id="speaker1",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(speakers=[speaker], segments=[segment])
    data = transcript.to_dict()
    expected = {
        "speakers": [{"id": "speaker1", "name": "Speaker One"}],
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hello",
                "speaker_id": "speaker1",
                "word_timing_mode": "complete",
                "words": [{"start": 0.0, "end": 1.0, "text": "Hello"}],
            }
        ],
    }
    assert data == expected
    transcript_deserialized = Transcript.from_dict(data)
    assert transcript == transcript_deserialized


def test_stj_serialization():
    """Test serialization and deserialization of STJ."""
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        confidence_threshold=0.8,
        languages=["en", "es"],
    )
    word = Word(start=0.0, end=1.0, text="Hello")
    segment = Segment(
        start=0.0,
        end=1.0,
        text="Hello",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE,
    )
    transcript = Transcript(segments=[segment])
    stj_instance = STJ(version="0.6.0", metadata=metadata, transcript=transcript)
    data = stj_instance.to_dict()
    expected = {
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
                        "end": 1.0,
                        "text": "Hello",
                        "word_timing_mode": "complete",
                        "words": [{"start": 0.0, "end": 1.0, "text": "Hello"}],
                    }
                ],
            },
        }
    }
    assert data == expected
    stj_deserialized = STJ.from_dict(data["stj"])
    assert stj_instance == stj_deserialized


def test_metadata_optional_created_at():
    """Test handling of optional created_at field in metadata."""
    # Test with created_at omitted
    data = {
        "title": "Test Title",
        "language": "en",
    }
    metadata = Metadata.from_dict(data)
    assert metadata.created_at is None

    # Test with valid created_at
    data_with_timestamp = {
        "title": "Test Title",
        "language": "en",
        "created_at": "2024-03-20T12:00:00Z",
    }
    metadata = Metadata.from_dict(data_with_timestamp)
    expected_datetime = datetime(2024, 3, 20, 12, 0, tzinfo=timezone.utc)
    assert metadata.created_at == expected_datetime
