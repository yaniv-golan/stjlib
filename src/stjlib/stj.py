"""
Standard Transcription JSON (STJ) format wrapper.

This module provides data classes and utilities for working with STJ files,
which represent transcribed audio and video data in a structured,
machine-readable JSON format.

For more information about the STJ format, refer to the STJ Specification:
https://github.com/yaniv-golan/STJ

This implementation supports STJ version 0.4 with improved practices.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from iso639 import Lang
from iso639.exceptions import InvalidLanguageValue


class STJError(Exception):
    """Base class for exceptions in the STJ module."""

    pass


class ValidationError(STJError):
    """Exception raised when validation fails.

    Attributes:
        issues (List[ValidationIssue]): List of validation issues.
    """

    def __init__(self, issues: List["ValidationIssue"]):
        self.issues = issues
        super().__init__(self.__str__())

    def __str__(self):
        return "Validation failed with the following issues:\n" + "\n".join(
            str(issue) for issue in self.issues
        )


@dataclass
class ValidationIssue:
    """Represents a single validation issue.

    Attributes:
        message (str): Description of the validation issue.
        location (Optional[str]): Location where the issue occurred.
    """

    message: str
    location: Optional[str] = None

    def __str__(self):
        if self.location:
            return f"{self.location}: {self.message}"
        else:
            return self.message


class WordTimingMode(Enum):
    """Enumeration of word timing modes."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"


class SegmentDuration(Enum):
    """Enumeration of segment duration types."""

    ZERO = "zero"


class WordDuration(Enum):
    """Enumeration of word duration types."""

    ZERO = "zero"


@dataclass
class Transcriber:
    """Represents the transcriber metadata.

    Attributes:
        name (str): Name of the transcriber.
        version (str): Version of the transcriber.
    """

    name: str
    version: str


@dataclass
class Source:
    """Represents the source metadata.

    Attributes:
        uri (Optional[str]): URI of the source file.
        duration (Optional[float]): Duration of the source in seconds.
        languages (Optional[List[Lang]]): List of languages in the source.
        additional_info (Dict[str, Any]): Additional metadata.
    """

    uri: Optional[str] = None
    duration: Optional[float] = None
    languages: Optional[List[Lang]] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metadata:
    """Represents the metadata of the STJ.

    Attributes:
        transcriber (Transcriber): Transcriber information.
        created_at (datetime): Creation timestamp.
        source (Optional[Source]): Source information.
        languages (Optional[List[Lang]]): List of languages.
        confidence_threshold (Optional[float]): Confidence threshold between 0.0 and 1.0.
        additional_info (Dict[str, Any]): Additional metadata.
    """

    transcriber: Transcriber
    created_at: datetime
    source: Optional[Source] = None
    languages: Optional[List[Lang]] = None
    confidence_threshold: Optional[float] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Speaker:
    """Represents a speaker in the transcript.

    Attributes:
        id (str): Unique identifier for the speaker.
        name (Optional[str]): Name of the speaker.
        additional_info (Dict[str, Any]): Additional metadata.
    """

    id: str
    name: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Style:
    """Represents a style in the transcript.

    Attributes:
        id (str): Unique identifier for the style.
        description (Optional[str]): Description of the style.
        formatting (Optional[Dict[str, Any]]): Formatting information.
        positioning (Optional[Dict[str, Any]]): Positioning information.
        additional_info (Dict[str, Any]): Additional metadata.
    """

    id: str
    description: Optional[str] = None
    formatting: Optional[Dict[str, Any]] = None
    positioning: Optional[Dict[str, Any]] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Word:
    """
    Represents a word with timing and confidence information.

    Attributes:
        start (float): The start time of the word in seconds.
        end (float): The end time of the word in seconds.
        text (str): The text of the word.
        confidence (Optional[float]): Confidence score between 0.0 and 1.0.
        additional_info (Dict[str, Any]): Additional metadata.
    """

    start: float
    end: float
    text: str
    confidence: Optional[float] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Segment:
    """
    Represents a segment in the transcript.

    Attributes:
        start (float): The start time of the segment in seconds.
        end (float): The end time of the segment in seconds.
        text (str): The text of the segment.
        speaker_id (Optional[str]): ID of the speaker.
        confidence (Optional[float]): Confidence score between 0.0 and 1.0.
        language (Optional[Lang]): Language of the segment.
        style_id (Optional[str]): ID of the style.
        words (Optional[List[Word]]): List of words in the segment.
        word_timing_mode (Optional[WordTimingMode]): Word timing mode.
        additional_info (Dict[str, Any]): Additional metadata.
    """

    start: float
    end: float
    text: str
    speaker_id: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[Lang] = None
    style_id: Optional[str] = None
    words: Optional[List[Word]] = None
    word_timing_mode: Optional[WordTimingMode] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transcript:
    """
    Represents the transcript.

    Attributes:
        speakers (List[Speaker]): List of speakers.
        segments (List[Segment]): List of segments.
        styles (Optional[List[Style]]): List of styles.
    """

    speakers: List[Speaker] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    styles: Optional[List[Style]] = None


@dataclass
class StandardTranscriptionJSON:
    """
    Represents the entire Standard Transcription JSON (STJ) object.

    This class encapsulates the complete structure of an STJ file, including
    metadata and transcript information. It provides methods for loading from
    and saving to files, as well as comprehensive validation.

    Attributes:
        metadata (Metadata): Metadata of the STJ.
        transcript (Transcript): Transcript data.
    """

    metadata: Metadata
    transcript: Transcript

    @classmethod
    def from_file(
        cls, filename: str, validate: bool = False, raise_exception: bool = True
    ) -> "StandardTranscriptionJSON":
        """Load an STJ instance from a JSON file.

        Args:
            filename (str): Path to the JSON file.
            validate (bool): If True, perform validation after loading.
            raise_exception (bool): If True and validation issues are found, raise ValidationError.

        Returns:
            StandardTranscriptionJSON: Loaded STJ instance.

        Raises:
            FileNotFoundError: If the specified file is not found.
            json.JSONDecodeError: If there's an error decoding the JSON.
            STJError: For unexpected errors during file loading.
            ValidationError: If validation fails and raise_exception is True.
        """
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            stj_instance = cls.from_dict(data)
            if validate:
                stj_instance.validate(raise_exception=raise_exception)
            return stj_instance
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {filename}") from e
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"JSON decode error: {e.msg}", e.doc, e.pos)
        except Exception as e:
            raise STJError(
                f"An unexpected error occurred while loading the file: {e}"
            ) from e

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardTranscriptionJSON":
        """Create an STJ instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing STJ data.

        Returns:
            StandardTranscriptionJSON: Created STJ instance.
        """
        metadata = cls._deserialize_metadata(data.get("metadata", {}))
        transcript = cls._deserialize_transcript(data.get("transcript", {}))
        return cls(metadata=metadata, transcript=transcript)

    @staticmethod
    def _deserialize_metadata(data: Dict[str, Any]) -> Metadata:
        """Deserialize metadata from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing metadata.

        Returns:
            Metadata: Deserialized metadata object.
        """
        # Check for required fields
        if "transcriber" not in data:
            raise KeyError("Missing required field: 'transcriber' in metadata.")
        if "created_at" not in data:
            raise KeyError("Missing required field: 'created_at' in metadata.")

        transcriber_data = data.get("transcriber", {})
        transcriber = Transcriber(**transcriber_data)
        created_at_str = data.get("created_at")
        created_at = (
            datetime.fromisoformat(created_at_str.rstrip("Z"))
            if created_at_str
            else datetime.now(timezone.utc)
        )
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        source = None
        if "source" in data:
            source_data = data["source"]
            source_languages = [Lang(code) for code in source_data.get("languages", [])]
            source_additional_info = {
                k: v
                for k, v in source_data.items()
                if k not in {"uri", "duration", "languages"}
            }
            source = Source(
                uri=source_data.get("uri"),
                duration=source_data.get("duration"),
                languages=source_languages if source_languages else None,
                additional_info=source_additional_info,
            )
        try:
            metadata_languages = (
                [Lang(code) for code in data.get("languages", [])]
                if data.get("languages")
                else None
            )
        except InvalidLanguageValue as e:
            raise ValidationError(
                [
                    ValidationIssue(
                        message=f"Invalid language code: {str(e)}",
                        location="Metadata.languages",
                    )
                ]
            )
        additional_info = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "transcriber",
                "created_at",
                "source",
                "languages",
                "confidence_threshold",
            }
        }
        return Metadata(
            transcriber=transcriber,
            created_at=created_at,
            source=source,
            languages=metadata_languages,
            confidence_threshold=data.get("confidence_threshold"),
            additional_info=additional_info,
        )

    @staticmethod
    def _deserialize_transcript(data: Dict[str, Any]) -> Transcript:
        """Deserialize transcript from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing transcript data.

        Returns:
            Transcript: Deserialized transcript object.
        """
        speakers = []
        for s in data.get("speakers", []):
            additional_info = {k: v for k, v in s.items() if k not in {"id", "name"}}
            speaker = Speaker(
                id=s["id"], name=s.get("name"), additional_info=additional_info
            )
            speakers.append(speaker)

        styles = []
        for s in data.get("styles", []):
            additional_info = {
                k: v
                for k, v in s.items()
                if k not in {"id", "description", "formatting", "positioning"}
            }
            style = Style(
                id=s["id"],
                description=s.get("description"),
                formatting=s.get("formatting"),
                positioning=s.get("positioning"),
                additional_info=additional_info,
            )
            styles.append(style)
        styles = styles if styles else None

        segments = []
        for s in data.get("segments", []):
            words = []
            for w in s.get("words", []):
                word_additional_info = {
                    k: v
                    for k, v in w.items()
                    if k not in {"start", "end", "text", "confidence"}
                }
                word = Word(
                    start=w["start"],
                    end=w["end"],
                    text=w["text"],
                    confidence=w.get("confidence"),
                    additional_info=word_additional_info,
                )
                words.append(word)
            words = words if words else None

            language = Lang(s["language"]) if s.get("language") else None
            word_timing_mode = s.get("word_timing_mode")
            if word_timing_mode:
                word_timing_mode = WordTimingMode(word_timing_mode)
            segment_additional_info = {
                k: v
                for k, v in s.items()
                if k
                not in {
                    "start",
                    "end",
                    "text",
                    "speaker_id",
                    "confidence",
                    "language",
                    "style_id",
                    "words",
                    "word_timing_mode",
                }
            }
            segment = Segment(
                start=s["start"],
                end=s["end"],
                text=s["text"],
                speaker_id=s.get("speaker_id"),
                confidence=s.get("confidence"),
                language=language,
                style_id=s.get("style_id"),
                words=words,
                word_timing_mode=word_timing_mode,
                additional_info=segment_additional_info,
            )
            segments.append(segment)
        return Transcript(speakers=speakers, segments=segments, styles=styles)

    def to_file(self, filename: str):
        """Save the STJ instance to a JSON file.

        Args:
            filename (str): Path to the JSON file.

        Raises:
            IOError: If there's an error writing to the file.
        """
        data = self.to_dict()
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            raise IOError(f"Error writing to file {filename}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the STJ instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the STJ instance.
        """
        data = asdict(self)
        return self._custom_serialize(data)

    def _custom_serialize(self, data: Any) -> Any:
        """Recursively serialize data, handling custom types.

        Args:
            data (Any): Data to serialize.

        Returns:
            Any: Serialized data.
        """
        if isinstance(data, dict):
            return {
                key: self._custom_serialize(value)
                for key, value in data.items()
                if value is not None
            }
        elif isinstance(data, list):
            return [self._custom_serialize(item) for item in data]
        elif isinstance(data, datetime):
            # Convert datetime to ISO format in UTC
            return data.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        elif isinstance(data, Lang):
            # Use the primary or tertiary language code
            return data.pt1 or data.pt3
        elif isinstance(data, Enum):
            # Return the value of the Enum
            return data.value
        else:
            return data

    def validate(self, raise_exception: bool = True) -> List[ValidationIssue]:
        """Perform comprehensive validation according to STJ 0.4 specification.

        Args:
            raise_exception (bool): If True and validation issues are found, raise ValidationError.

        Returns:
            List[ValidationIssue]: List of validation issues.

        Raises:
            ValidationError: If validation fails and raise_exception is True.
        """
        issues = []
        issues.extend(self._validate_language_codes())
        issues.extend(self._validate_confidence_threshold())
        issues.extend(self._validate_speaker_and_style_ids())
        issues.extend(self._validate_segments())
        issues.extend(self._validate_confidence_scores())

        if issues and raise_exception:
            raise ValidationError(issues)
        return issues

    def _validate_language_codes(self) -> List[ValidationIssue]:
        """
        Validate language codes in metadata and segments.

        This method checks the validity of language codes in the metadata,
        source information, and individual segments.

        Returns:
            List[ValidationIssue]: List of validation issues related to language codes.
        """
        issues = []
        # Validate metadata languages
        if self.metadata.languages:
            for lang in self.metadata.languages:
                if not lang.pt1 and not lang.pt3:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid language code in metadata: {lang}",
                            location="Metadata.languages",
                        )
                    )
        # Validate source languages
        if self.metadata.source and self.metadata.source.languages:
            for lang in self.metadata.source.languages:
                if not lang.pt1 and not lang.pt3:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid language code in source: {lang}",
                            location="Metadata.source.languages",
                        )
                    )
        # Validate segment languages
        for idx, segment in enumerate(self.transcript.segments):
            if segment.language:
                if not segment.language.pt1 and not segment.language.pt3:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid language code in segment",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )
        return issues

    def _validate_confidence_threshold(self) -> List[ValidationIssue]:
        """
        Validate confidence_threshold in metadata.

        Ensures that the confidence_threshold, if present, is within the valid range [0.0, 1.0].

        Returns:
            List[ValidationIssue]: List of validation issues related to confidence threshold.
        """
        issues = []
        if self.metadata.confidence_threshold is not None:
            if not (0.0 <= self.metadata.confidence_threshold <= 1.0):
                issues.append(
                    ValidationIssue(
                        message=f"confidence_threshold {self.metadata.confidence_threshold} out of range [0.0, 1.0]",
                        location="Metadata.confidence_threshold",
                    )
                )
        return issues

    def _validate_speaker_and_style_ids(self) -> List[ValidationIssue]:
        """
        Validate speaker_id and style_id references in segments.

        Checks that all speaker_id and style_id values in segments refer to valid speakers and styles.

        Returns:
            List[ValidationIssue]: List of validation issues related to speaker and style IDs.
        """
        issues = []
        # Collect valid speaker and style IDs for reference
        valid_speaker_ids = {speaker.id for speaker in self.transcript.speakers}
        valid_style_ids = (
            {style.id for style in self.transcript.styles}
            if self.transcript.styles
            else set()
        )

        for idx, segment in enumerate(self.transcript.segments):
            if segment.speaker_id and segment.speaker_id not in valid_speaker_ids:
                issues.append(
                    ValidationIssue(
                        message=f"Invalid speaker_id '{segment.speaker_id}'",
                        location=f"Segment[{idx}] starting at {segment.start}",
                    )
                )
            if segment.style_id and segment.style_id not in valid_style_ids:
                issues.append(
                    ValidationIssue(
                        message=f"Invalid style_id '{segment.style_id}'",
                        location=f"Segment[{idx}] starting at {segment.start}",
                    )
                )
        return issues

    def _validate_segments(self) -> List[ValidationIssue]:
        """
        Validate segments for ordering, overlapping, and word consistency.

        Checks that segments are properly ordered, do not overlap, and have consistent word information.

        Returns:
            List[ValidationIssue]: List of validation issues related to segments.
        """
        issues = []
        # Ensure segments are ordered and do not overlap
        previous_end = -1
        for idx, segment in enumerate(self.transcript.segments):
            if segment.start < previous_end:
                issues.append(
                    ValidationIssue(
                        message="Segments overlap or are out of order",
                        location=f"Segment[{idx}] starting at {segment.start}",
                    )
                )
            if segment.start == segment.end:
                segment_duration = segment.additional_info.get("segment_duration")
                if segment_duration != SegmentDuration.ZERO.value:
                    issues.append(
                        ValidationIssue(
                            message=f"Zero-duration segment without 'segment_duration' set to '{SegmentDuration.ZERO.value}'",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )
                elif segment_duration not in [e.value for e in SegmentDuration]:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid 'segment_duration' value: {segment_duration}",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )
            issues.extend(self._validate_words_in_segment(segment, idx))
            previous_end = segment.end
        return issues

    def _validate_words_in_segment(
        self, segment: Segment, segment_idx: int
    ) -> List[ValidationIssue]:
        """
        Validate words within a segment.

        Checks word timings, ordering, and consistency with the segment text.

        Args:
            segment (Segment): The segment containing words to validate.
            segment_idx (int): Index of the segment being validated.

        Returns:
            List[ValidationIssue]: List of validation issues related to words in the segment.
        """
        issues = []
        words = segment.words or []
        word_timing_mode = segment.word_timing_mode or (
            WordTimingMode.COMPLETE if words else WordTimingMode.NONE
        )

        if word_timing_mode not in WordTimingMode:
            issues.append(
                ValidationIssue(
                    message="Invalid 'word_timing_mode'",
                    location=f"Segment[{segment_idx}] starting at {segment.start}",
                )
            )

        if word_timing_mode != WordTimingMode.NONE and not words:
            issues.append(
                ValidationIssue(
                    message=f"'word_timing_mode' is '{word_timing_mode.value}' but no words are provided",
                    location=f"Segment[{segment_idx}] starting at {segment.start}",
                )
            )

        previous_word_end = segment.start
        concatenated_words = ""
        for word_idx, word in enumerate(words):
            # Check if word timings are within segment timings
            if word.start < segment.start or word.end > segment.end:
                issues.append(
                    ValidationIssue(
                        message="Word timings are outside segment timings",
                        location=f"Segment[{segment_idx}].Word[{word_idx}] starting at {word.start}",
                    )
                )

            # Ensure words do not overlap
            if word.start < previous_word_end:
                issues.append(
                    ValidationIssue(
                        message="Words overlap or are out of order",
                        location=f"Segment[{segment_idx}].Word[{word_idx}] starting at {word.start}",
                    )
                )

            if word.start == word.end:
                word_duration = word.additional_info.get("word_duration")
                if word_duration != WordDuration.ZERO.value:
                    issues.append(
                        ValidationIssue(
                            message=f"Zero-duration word without 'word_duration' set to '{WordDuration.ZERO.value}'",
                            location=f"Segment[{segment_idx}].Word[{word_idx}] starting at {word.start}",
                        )
                    )
                elif word_duration not in [e.value for e in WordDuration]:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid 'word_duration' value: {word_duration}",
                            location=f"Segment[{segment_idx}].Word[{word_idx}] starting at {word.start}",
                        )
                    )

            previous_word_end = word.end
            concatenated_words += word.text + " "

        if word_timing_mode == WordTimingMode.COMPLETE:
            # Remove extra whitespace for comparison
            segment_text = "".join(segment.text.split())
            words_text = "".join(concatenated_words.strip().split())
            if segment_text != words_text:
                issues.append(
                    ValidationIssue(
                        message="Concatenated words do not match segment text",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )

        return issues

    def _validate_confidence_scores(self) -> List[ValidationIssue]:
        """
        Validate confidence scores in segments and words.

        Ensures that all confidence scores are within the valid range [0.0, 1.0].

        Returns:
            List[ValidationIssue]: List of validation issues related to confidence scores.
        """
        issues = []
        for idx, segment in enumerate(self.transcript.segments):
            if segment.confidence is not None and not (
                0.0 <= segment.confidence <= 1.0
            ):
                issues.append(
                    ValidationIssue(
                        message=f"Segment confidence {segment.confidence} out of range [0.0, 1.0]",
                        location=f"Segment[{idx}] starting at {segment.start}",
                    )
                )
            for word_idx, word in enumerate(segment.words or []):
                if word.confidence is not None and not (0.0 <= word.confidence <= 1.0):
                    issues.append(
                        ValidationIssue(
                            message=f"Word confidence {word.confidence} out of range [0.0, 1.0]",
                            location=f"Segment[{idx}].Word[{word_idx}] starting at {word.start}",
                        )
                    )
        return issues

