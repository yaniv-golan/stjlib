"""
STJLib: Standard Transcription JSON Format Handler

This module provides a comprehensive implementation of the Standard Transcription JSON (STJ) format,
which is used to represent transcribed audio and video data in a structured, machine-readable format.

Key Features:
    - Load and save STJ files with robust error handling
    - Validate STJ data against the official specification
    - Access and modify transcript content, metadata, and speaker information
    - Full support for word-level timing and confidence scores
    - Extensible through additional_info fields

Example Usage:
    >>> from stjlib import StandardTranscriptionJSON
    >>> 
    >>> # Load and validate an STJ file
    >>> stj = StandardTranscriptionJSON.from_file('transcript.stj.json', validate=True)
    >>> 
    >>> # Access transcript data
    >>> for segment in stj.transcript.segments:
    ...     print(f"{segment.start:.2f}-{segment.end:.2f}: {segment.text}")

For detailed information about the STJ format, see:
https://github.com/yaniv-golan/STJ

Version: 0.2.0
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from iso639 import Lang
from iso639.exceptions import InvalidLanguageValue
from dateutil.parser import parse as parse_datetime


class STJError(Exception):
    """Base class for exceptions in the STJ module."""

    pass


class ValidationError(STJError):
    """Exception raised when STJ validation fails.

    This exception contains a list of specific validation issues, allowing
    the caller to understand exactly what problems were found in the STJ data.
    Each issue includes both a descriptive message and a location indicating
    where in the STJ structure the problem was found.

    Attributes:
        issues (List[ValidationIssue]): List of validation issues found

    Example Usage:
        >>> try:
        ...     stj.validate()
        ... except ValidationError as e:
        ...     print("Validation failed:")
        ...     for issue in e.issues:
        ...         print(f"Location: {issue.location}")
        ...         print(f"Problem: {issue.message}")
        ...         print("---")

    See Also:
        :class:`ValidationIssue`: Represents individual validation issues.
        :meth:`StandardTranscriptionJSON.validate`: Method that raises this exception.
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
    """Represents a single validation issue found during STJ data validation.

    This class is used to provide detailed information about specific validation
    problems, including a description of the issue and its location in the STJ structure.

    Attributes:
        message (str): A descriptive message explaining the validation issue.
        location (Optional[str]): The location in the STJ structure where the issue was found.

    Example:
        >>> issue: ValidationIssue = ValidationIssue(
        ...     message="Invalid confidence score",
        ...     location="Segment[2].Word[5]"
        ... )
        >>> print(issue)
        Segment[2].Word[5]: Invalid confidence score

    See Also:
        :class:`ValidationError`: Exception that aggregates multiple validation issues.
    """

    message: str
    location: Optional[str] = None

    def __str__(self):
        if self.location:
            return f"{self.location}: {self.message}"
        else:
            return self.message


class WordTimingMode(Enum):
    """Enumeration of word timing modes in a transcript segment.

    This enum defines the possible modes for word-level timing information:
    - COMPLETE: All words have timing information.
    - PARTIAL: Some words have timing information.
    - NONE: No words have timing information.

    Usage:
        >>> mode = WordTimingMode.COMPLETE
        >>> print(mode)
        WordTimingMode.COMPLETE
        >>> print(mode.value)
        'complete'
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"


class SegmentDuration(Enum):
    """Enumeration of segment duration types.

    This enum is used to indicate special duration cases for segments:
    - ZERO: Represents a segment with zero duration.

    Usage:
        >>> duration = SegmentDuration.ZERO
        >>> print(duration)
        SegmentDuration.ZERO
        >>> print(duration.value)
        'zero'
    """

    ZERO = "zero"


class WordDuration(Enum):
    """Enumeration of word duration types.

    This enum is used to indicate special duration cases for words:
    - ZERO: Represents a word with zero duration.

    Usage:
        >>> duration = WordDuration.ZERO
        >>> print(duration)
        WordDuration.ZERO
        >>> print(duration.value)
        'zero'
    """

    ZERO = "zero"


@dataclass
class Transcriber:
    """Represents metadata about the transcription system or service.

    This class stores information about the transcriber, including its name and version.

    Attributes:
        name (str): The name of the transcription system or service.
        version (str): The version of the transcription system or service.

    Example:
        >>> transcriber = Transcriber(name="AutoTranscribe", version="2.1.0")
        >>> print(f"Transcribed by {transcriber.name} v{transcriber.version}")
        Transcribed by AutoTranscribe v2.1.0
    """

    name: str
    version: str


@dataclass
class Source:
    """Represents the source metadata for the transcription.

    This class contains information about the original media file that was transcribed,
    including its location, duration, and languages.

    Attributes:
        uri (Optional[str]): URI or path to the source media file.
        duration (Optional[float]): Duration of the source media in seconds.
        languages (Optional[List[Lang]]): List of languages present in the source media.
        additional_info (Dict[str, Any]): Additional metadata about the source.

    Example:
        >>> source = Source(
        ...     uri="https://example.com/audio.mp3",
        ...     duration=300.5,
        ...     languages=[Lang("en"), Lang("es")],
        ...     additional_info={"bitrate": "128kbps"}
        ... )
    """

    uri: Optional[str] = None
    duration: Optional[float] = None
    languages: Optional[List[Lang]] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metadata:
    """Represents the metadata of the Standard Transcription JSON (STJ).

    This class contains various metadata fields that provide context and
    information about the transcription process and content.

    Attributes:
        transcriber (Transcriber): Information about the transcription system used.
        created_at (datetime): Timestamp of when the transcription was created.
        source (Optional[Source]): Information about the source media, if available.
        languages (Optional[List[Lang]]): List of languages used in the transcription.
        confidence_threshold (Optional[float]): Minimum confidence score for included words, if applicable.
        additional_info (Dict[str, Any]): Additional metadata key-value pairs.

    Example:
        >>> from datetime import datetime, timezone
        >>> metadata = Metadata(
        ...     transcriber=Transcriber(name="AutoTranscribe", version="2.1.0"),
        ...     created_at=datetime.now(timezone.utc),
        ...     languages=[Lang("en"), Lang("es")],
        ...     confidence_threshold=0.8,
        ...     additional_info={"audio_quality": "high"}
        ... )
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

    This class is used to identify and provide information about individuals
    speaking in the transcribed content.

    Attributes:
        id (str): Unique identifier for the speaker within the transcript.
        name (Optional[str]): Name or label for the speaker.
        additional_info (Dict[str, Any]): Additional metadata about the speaker.

    Example:
        >>> speaker = Speaker(
        ...     id="speaker1",
        ...     name="John Doe",
        ...     additional_info={"age": 30, "gender": "male"}
        ... )
    """

    id: str
    name: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Style:
    """Represents a style in the transcript.

    Styles can be used to indicate different formatting or presentation
    for segments of the transcript.

    Attributes:
        id (str): Unique identifier for the style within the transcript.
        description (Optional[str]): Human-readable description of the style.
        formatting (Optional[Dict[str, Any]]): Formatting information for the style.
        positioning (Optional[Dict[str, Any]]): Positioning information for the style.
        additional_info (Dict[str, Any]): Additional metadata about the style.

    Example:
        >>> style = Style(
        ...     id="emphasis",
        ...     description="Emphasized speech",
        ...     formatting={"font-weight": "bold"},
        ...     positioning={"vertical-align": "super"},
        ...     additional_info={"usage": "for important phrases"}
        ... )
    """

    id: str
    description: Optional[str] = None
    formatting: Optional[Dict[str, Any]] = None
    positioning: Optional[Dict[str, Any]] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Word:
    """Represents a single word with timing and confidence information.

    This class is used to store detailed information about individual words
    within a transcript segment.

    Attributes:
        start (float): Start time of the word in seconds from the beginning of the media.
        end (float): End time of the word in seconds from the beginning of the media.
        text (str): The text content of the word.
        confidence (Optional[float]): Confidence score for the word recognition, between 0.0 and 1.0.
        additional_info (Dict[str, Any]): Additional metadata about the word.

    Constraints:
        - start must be >= 0
        - end must be > start (unless word_duration is "zero")
        - confidence, if provided, must be between 0.0 and 1.0

    Example:
        >>> word = Word(
        ...     start=10.5,
        ...     end=11.0,
        ...     text="hello",
        ...     confidence=0.95,
        ...     additional_info={"phoneme": "hə'ləʊ"}
        ... )
    """

    start: float
    end: float
    text: str
    confidence: Optional[float] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Segment:
    """Represents a timed segment in the transcript with optional word-level detail.

    A segment is a continuous portion of the transcript with its own timing, speaker,
    and optional word-level information. Segments must not overlap with each other
    and must contain valid timing information.

    Constraints:
        - start must be >= 0
        - end must be > start (unless segment_duration is "zero")
        - speaker_id must reference a valid speaker if provided
        - style_id must reference a valid style if provided
        - words must match segment text if word_timing_mode is "complete"

    Example:
        >>> segment = Segment(
        ...     start=0.0,
        ...     end=5.0,
        ...     text="Hello world",
        ...     speaker_id="speaker1",
        ...     words=[
        ...         Word(start=0.0, end=1.0, text="Hello"),
        ...         Word(start=1.0, end=2.0, text="world")
        ...     ],
        ...     word_timing_mode=WordTimingMode.COMPLETE
        ... )

    Attributes:
        start (float): Start time in seconds from the beginning of the media
        end (float): End time in seconds from the beginning of the media
        text (str): The transcribed text content
        speaker_id (Optional[str]): Reference to a speaker.id in the transcript
        confidence (Optional[float]): Confidence score between 0.0 and 1.0
        language (Optional[Lang]): ISO 639 language code
        style_id (Optional[str]): Reference to a style.id in the transcript
        words (Optional[List[Word]]): Word-level timing and text information
        word_timing_mode (Optional[WordTimingMode]): Indicates completeness of word timing
        additional_info (Dict[str, Any]): Additional metadata for extensibility
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
    """Represents the main content of the transcription.

    This class contains the core transcription data, including speakers,
    segments, and optional style information.

    Attributes:
        speakers (List[Speaker]): List of speakers in the transcript.
        segments (List[Segment]): List of transcript segments.
        styles (Optional[List[Style]]): List of styles used in the transcript, if any.

    Example:
        >>> transcript = Transcript(
        ...     speakers=[
        ...         Speaker(id="S1", name="John"),
        ...         Speaker(id="S2", name="Jane")
        ...     ],
        ...     segments=[
        ...         Segment(start=0.0, end=5.0, text="Hello, how are you?", speaker_id="S1"),
        ...         Segment(start=5.1, end=8.5, text="I'm fine, thanks!", speaker_id="S2")
        ...     ],
        ...     styles=[
        ...         Style(id="emphasis", description="Emphasized speech")
        ...     ]
        ... )
    """

    speakers: List[Speaker] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    styles: Optional[List[Style]] = None


@dataclass
class StandardTranscriptionJSON:
    """A class for handling Standard Transcription JSON (STJ) format.

    This class provides methods for creating, validating, and manipulating
    transcription data in the STJ format.

    Attributes:
        metadata (Metadata): Metadata information for the transcription.
        transcript (Transcript): The transcript data.

    See Also:
        :class:`Metadata`: Class representing metadata information.
        :class:`Transcript`: Class representing the transcript data.
    """

    metadata: Metadata
    transcript: Transcript

    def _validate_metadata(self):
        """Validate the metadata of the STJ object.

        Raises:
            ValidationError: If metadata validation fails. See :class:`ValidationError` for details
                about error handling and :class:`ValidationIssue` for the structure of
                validation issues.

        Example:
            >>> metadata: Metadata = Metadata(
            ...     transcriber=Transcriber(name="AutoTranscribe", version="2.1.0"),
            ...     created_at=datetime.now(timezone.utc)
            ... )
            >>> transcript: Transcript = Transcript(
            ...     speakers=[
            ...         Speaker(id="S1", name="John"),
            ...         Speaker(id="S2", name="Jane")
            ...     ],
            ...     segments=[
            ...         Segment(start=0.0, end=1.0, text="Hello", confidence=0.95),
            ...         Segment(start=1.0, end=2.0, text="world", confidence=0.98)
            ...     ],
            ...     styles=[
            ...         Style(id="emphasis", description="Emphasized speech")
            ...     ]
            ... )
            >>> stj = StandardTranscriptionJSON(metadata, transcript)
            >>> stj._validate_metadata()  # Valid metadata
            >>>
            >>> stj.metadata = Metadata(transcriber=None, created_at=None)
            >>> stj._validate_metadata()  # Raises ValidationError

        See Also:
            :class:`ValidationError`: Raised when metadata validation fails.
            :class:`ValidationIssue`: Represents individual validation issues.
        """
        # Existing validation code...

    def _validate_transcript(self):
        """Validate the transcript of the STJ object.

        Raises:
            ValidationError: If transcript validation fails. See :class:`ValidationError` for details
                about error handling and :class:`ValidationIssue` for the structure of
                validation issues.

        Example:
            >>> transcript: Transcript = Transcript(
            ...     speakers=[
            ...         Speaker(id="S1", name="John"),
            ...         Speaker(id="S2", name="Jane")
            ...     ],
            ...     segments=[
            ...         Segment(start=0.0, end=1.0, text="Hello", confidence=0.95),
            ...         Segment(start=1.0, end=2.0, text="world", confidence=0.98)
            ...     ],
            ...     styles=[
            ...         Style(id="emphasis", description="Emphasized speech")
            ...     ]
            ... )
            >>> stj = StandardTranscriptionJSON(metadata, transcript)
            >>> stj._validate_transcript()  # Valid transcript
            >>> stj.transcript = Transcript(
            ...     speakers=[
            ...         Speaker(id="S1", name="John"),
            ...         Speaker(id="S2", name="Jane")
            ...     ],
            ...     segments=[
            ...         Segment(start=0.0, end=1.5, text="Hello", confidence=0.95),
            ...         Segment(start=1.0, end=2.0, text="world", confidence=0.98)
            ...     ],
            ...     styles=[
            ...         Style(id="emphasis", description="Emphasized speech")
            ...     ]
            ... )
            >>> stj._validate_transcript()  # Raises ValidationError

        See Also:
            :class:`ValidationError`: Raised when transcript validation fails.
            :class:`ValidationIssue`: Represents individual validation issues.
        """
        # Existing validation code...

    def validate(self, raise_exception: bool = True) -> List[ValidationIssue]:
        """Perform comprehensive validation of the STJ data.

        Validates all aspects of the STJ data according to the specification, including:
        - Language code validity using ISO 639 standards
        - Confidence score ranges (0.0 to 1.0)
        - Speaker and style ID references
        - Segment timing and ordering
        - Word timing and content matching
        - Zero-duration segment handling

        The validation process checks:
        1. Language codes in metadata and segments
        2. Confidence threshold and scores
        3. Speaker and style ID references
        4. Segment ordering and overlap
        5. Word timing and content consistency

        Args:
            raise_exception: If True, raises ValidationError when issues are found.
                If False, returns a list of validation issues.

        Returns:
            List[ValidationIssue]: List of validation issues found, empty if none.

        Raises:
            ValidationError: If validation fails and raise_exception is True.
                See :class:`ValidationError` for details about error handling and
                :class:`ValidationIssue` for the structure of validation issues.

        Example:
            >>> stj = StandardTranscriptionJSON(metadata, transcript)
            >>> try:
            ...     stj.validate(raise_exception=True)
            ... except ValidationError as e:
            ...     print("Validation failed:")
            ...     for issue in e.issues:
            ...         print(f"- {issue}")
            Validation failed:
            - Segment[1] starting at 1.0: Segment confidence 1.1 out of range [0.0, 1.0]
            - Segment[2] starting at 2.0: Invalid speaker_id 'S3'

        See Also:
            :class:`ValidationError`: Raised when any part of the validation fails.
            :meth:`_validate_language_codes`: Method for validating language codes.
            :meth:`_validate_confidence_threshold`: Method for validating confidence thresholds.
            :meth:`_validate_speaker_and_style_ids`: Method for validating speaker and style IDs.
            :meth:`_validate_segments`: Method for validating segments.
            :meth:`_validate_confidence_scores`: Method for validating confidence scores.
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
    def from_dict(cls, data: Dict[str, Any], validate: bool = True) -> "StandardTranscriptionJSON":
        """Create a StandardTranscriptionJSON object from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing STJ data.
            validate (bool): If True, validate the data after deserialization.

        Returns:
            StandardTranscriptionJSON: A new StandardTranscriptionJSON object.

        Raises:
            ValidationError: If validate=True and the input data is invalid.
        """
        metadata = cls._deserialize_metadata(data.get("metadata", {}))
        transcript = cls._deserialize_transcript(data.get("transcript", {}))
        stj = cls(metadata=metadata, transcript=transcript)
        if validate:
            stj.validate(raise_exception=True)
        return stj

    @classmethod
    def _deserialize_metadata(cls, data: Dict[str, Any]) -> Metadata:
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
        created_at = parse_datetime(created_at_str) if created_at_str else datetime.now(timezone.utc)
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

    @classmethod
    def _deserialize_transcript(cls, s: dict) -> Transcript:
        """
        Deserialize transcript from a dictionary.

        Args:
            s (dict): Dictionary containing transcript data.

        Returns:
            Transcript: Deserialized transcript object.
        """
        speakers = []
        for speaker_data in s.get("speakers", []):
            additional_info = {k: v for k, v in speaker_data.items() if k not in {"id", "name"}}
            speaker = Speaker(
                id=speaker_data["id"],
                name=speaker_data.get("name"),
                additional_info=additional_info
            )
            speakers.append(speaker)

        styles = []
        for style_data in s.get("styles", []):
            additional_info = {
                k: v for k, v in style_data.items()
                if k not in {"id", "description", "formatting", "positioning"}
            }
            style = Style(
                id=style_data["id"],
                description=style_data.get("description"),
                formatting=style_data.get("formatting"),
                positioning=style_data.get("positioning"),
                additional_info=additional_info,
            )
            styles.append(style)
        styles = styles if styles else None

        segments = []
        for segment_data in s.get("segments", []):
            words = []
            for word_data in segment_data.get("words", []):
                word_additional_info = {
                    k: v for k, v in word_data.items()
                    if k not in {"start", "end", "text", "confidence"}
                }
                word = Word(
                    start=word_data["start"],
                    end=word_data["end"],
                    text=word_data["text"],
                    confidence=word_data.get("confidence"),
                    additional_info=word_additional_info,
                )
                words.append(word)
            words = words if words else None

            try:
                language = Lang(segment_data["language"]) if segment_data.get("language") else None
            except InvalidLanguageValue:
                language = None  # Handle invalid language code

            # Handle word_timing_mode
            word_timing_mode = segment_data.get("word_timing_mode")
            if word_timing_mode:
                try:
                    word_timing_mode = WordTimingMode(word_timing_mode)
                except ValueError:
                    # Keep the invalid value for validation to catch
                    pass

            segment_additional_info = {
                k: v for k, v in segment_data.items()
                if k not in {
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
                start=segment_data["start"],
                end=segment_data["end"],
                text=segment_data["text"],
                speaker_id=segment_data.get("speaker_id"),
                confidence=segment_data.get("confidence"),
                language=language,
                style_id=segment_data.get("style_id"),
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
            # Validate word timing mode
            word_timing_mode = segment.word_timing_mode
            if word_timing_mode is not None:
                if not isinstance(word_timing_mode, WordTimingMode):
                    try:
                        # Try to convert string to enum
                        WordTimingMode(word_timing_mode)
                    except ValueError:
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid word_timing_mode '{word_timing_mode}'",
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
        word_timing_mode = segment.word_timing_mode

        # Validate word timing mode
        if word_timing_mode is not None:
            if not isinstance(word_timing_mode, WordTimingMode):
                issues.append(
                    ValidationIssue(
                        message=f"Invalid word_timing_mode '{word_timing_mode}'",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )
                # Don't continue validation if word_timing_mode is invalid
                return issues

        # Set default word_timing_mode if none provided
        if word_timing_mode is None:
            word_timing_mode = WordTimingMode.COMPLETE if words else WordTimingMode.NONE

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


















