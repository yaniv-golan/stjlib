# tests/test_stj.py

import pytest
from stjlib import (
    StandardTranscriptionJSON,
    STJError,
    ValidationError,
    ValidationIssue,
    WordTimingMode,
    SegmentDuration,
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
    """Test loading a valid STJ file."""
    stj_data = {
        "metadata": {
            "transcriber": {
                "name": "TestTranscriber",
                "version": "1.0"
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        "transcript": {
            "speakers": [
                {"id": "speaker1", "name": "Speaker One"}
            ],
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Hello world",
                    "speaker_id": "speaker1",
                    "words": [
                        {"start": 0.0, "end": 1.0, "text": "Hello"},
                        {"start": 1.0, "end": 2.0, "text": "world"}
                    ],
                    "word_timing_mode": "complete"
                }
            ]
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    assert stj.metadata.transcriber.name == "TestTranscriber"
    assert stj.transcript.segments[0].text == "Hello world"

def test_validate_valid_stj():
    """Test validating a valid STJ instance."""
    stj_data = {
        "metadata": {
            "transcriber": {
                "name": "TestTranscriber",
                "version": "1.0"
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "confidence_threshold": 0.8
        },
        "transcript": {
            "speakers": [
                {"id": "speaker1", "name": "Speaker One"}
            ],
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Hello world",
                    "speaker_id": "speaker1",
                    "confidence": 0.9,
                    "words": [
                        {"start": 0.0, "end": 1.0, "text": "Hello", "confidence": 0.95},
                        {"start": 1.0, "end": 2.0, "text": "world", "confidence": 0.9}
                    ],
                    "word_timing_mode": "complete"
                }
            ]
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0

def test_validate_invalid_confidence():
    """Test validation catching invalid confidence scores."""
    stj_data = {
        "metadata": {
            "transcriber": {
                "name": "TestTranscriber",
                "version": "1.0"
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "confidence_threshold": 1.5  # Invalid confidence_threshold
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test segment",
                    "confidence": -0.1  # Invalid confidence
                }
            ]
        }
    }
    stj = StandardTranscriptionJSON.from_dict(stj_data)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 2
    assert any("confidence_threshold" in issue.location for issue in issues)
    assert any("Segment[0]" in issue.location for issue in issues)

def test_validate_invalid_language_code():
    """Test validation catching invalid language codes."""
    stj_data = {
        "metadata": {
            "transcriber": {
                "name": "TestTranscriber",
                "version": "1.0"
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "languages": ["invalid-code"]
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test segment",
                    "language": "invalid-code"
                }
            ]
        }
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
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        "transcript": {
            "segments": []
        }
    }
    with pytest.raises(KeyError) as excinfo:
        StandardTranscriptionJSON.from_dict(stj_data)
    assert "transcriber" in str(excinfo.value)

def test_serialization():
    """Test that serialization produces the correct dictionary."""
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        confidence_threshold=0.8
    )
    word1 = Word(start=0.0, end=1.0, text="Hello")
    word2 = Word(start=1.0, end=2.0, text="world")
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Hello world",
        words=[word1, word2],
        word_timing_mode=WordTimingMode.COMPLETE
    )
    transcript = Transcript(segments=[segment])
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    stj_dict = stj.to_dict()
    expected_dict = {
        "metadata": {
            "transcriber": {
                "name": "TestTranscriber",
                "version": "1.0"
            },
            "created_at": "2023-01-01T00:00:00Z",
            "confidence_threshold": 0.8,
            "additional_info": {}  # Matches stj_dict
        },
        "transcript": {
            "speakers": [],
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello world",
                    "words": [
                        {"start": 0.0, "end": 1.0, "text": "Hello", "additional_info": {}},  # Added additional_info
                        {"start": 1.0, "end": 2.0, "text": "world", "additional_info": {}}   # Added additional_info
                    ],
                    "word_timing_mode": "complete",
                    "additional_info": {}  # Matches stj_dict
                }
            ]
        }
    }

    diff = DeepDiff(expected_dict, stj_dict, ignore_order=True)
    assert not diff, f"Differences found: {diff}"

def test_loading_from_file(tmp_path):
    """Test loading an STJ file from disk."""
    stj_data = {
        "metadata": {
            "transcriber": {
                "name": "TestTranscriber",
                "version": "1.0"
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test segment"
                }
            ]
        }
    }
    file_path = tmp_path / "test.stj.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(stj_data, f)
    stj = StandardTranscriptionJSON.from_file(str(file_path))
    assert stj.transcript.segments[0].text == "Test segment"

def test_saving_to_file(tmp_path):
    """Test saving an STJ instance to disk."""
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Hello world"
    )
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
        start=0.0,
        end=1.0,
        text="Hello",
        additional_info={"word_duration": "zero"}
    )
    segment = Segment(
        start=0.0,
        end=1.0,
        text="Hello",
        words=[word],
        additional_info={"segment_duration": "zero"}
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0

def test_invalid_word_timing_mode():
    """Test validation catching invalid word_timing_mode."""
    stj_data = {
        "metadata": {
            "transcriber": {"name": "TestTranscriber", "version": "1.0"},
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        "transcript": {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Hello world",
                    "word_timing_mode": "invalid_mode"
                }
            ]
        }
    }

    with pytest.raises(ValueError) as exc_info:
        stj = StandardTranscriptionJSON.from_dict(stj_data)
        stj.validate()

    assert "invalid_mode" in str(exc_info.value)

def test_word_timings_outside_segment():
    """Test validation catching word timings outside segment timings."""
    word = Word(start=6.0, end=7.0, text="Test")
    segment = Segment(
        start=0.0,
        end=5.0,
        text="Test",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
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
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Segments overlap or are out of order" in issues[0].message

def test_invalid_speaker_id():
    """Test validation catching invalid speaker_id."""
    segment = Segment(
        start=0.0,
        end=5.0,
        text="Test",
        speaker_id="invalid_speaker"
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Invalid speaker_id" in issues[0].message

def test_invalid_style_id():
    """Test validation catching invalid style_id."""
    segment = Segment(
        start=0.0,
        end=5.0,
        text="Test",
        style_id="invalid_style"
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Invalid style_id" in issues[0].message

def test_zero_duration_segment():
    """Test validation of zero-duration segment with proper segment_duration."""
    segment = Segment(
        start=5.0,
        end=5.0,
        text="",
        additional_info={"segment_duration": "zero"}
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0

def test_zero_duration_word():
    """Test validation of zero-duration word with proper word_duration."""
    word = Word(
        start=1.0,
        end=1.0,
        text="",
        additional_info={"word_duration": "zero"}
    )
    segment = Segment(
        start=0.0,
        end=2.0,
        text="",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 0

def test_word_confidence_out_of_range():
    """Test validation catching word confidence out of range."""
    word = Word(
        start=0.0,
        end=1.0,
        text="Test",
        confidence=1.5  # Invalid confidence
    )
    segment = Segment(
        start=0.0,
        end=2.0,
        text="Test",
        words=[word],
        word_timing_mode=WordTimingMode.COMPLETE
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(transcriber=transcriber, created_at=datetime.now(timezone.utc))
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
        word_timing_mode=WordTimingMode.COMPLETE
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(name="TestTranscriber", version="1.0")
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime.now(timezone.utc)
    )
    stj = StandardTranscriptionJSON(metadata=metadata, transcript=transcript)
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Concatenated words do not match segment text" in issues[0].message

def test_word_overlap():
    """Test validation catching overlapping words."""
    word1 = Word(start=0.0, end=2.0, text="Hello")
    word2 = Word(start=1.5, end=3.0, text="world")  # Overlaps with word1
    segment = Segment(
        start=0.0,
        end=3.0,
        text="Hello world",
        words=[word1, word2],
        word_timing_mode=WordTimingMode.COMPLETE
    )
    transcript = Transcript(segments=[segment])
    transcriber = Transcriber(
        name="TestTranscriber",
        version="1.0"
    )
    metadata = Metadata(
        transcriber=transcriber,
        created_at=datetime.now(timezone.utc)
    )
    stj = StandardTranscriptionJSON(
        metadata=metadata,
        transcript=transcript
    )
    issues = stj.validate(raise_exception=False)
    assert len(issues) == 1
    assert "Words overlap or are out of order" in issues[0].message

