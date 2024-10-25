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
import re
import unicodedata

from iso639 import Lang
import iso639
from iso639.exceptions import InvalidLanguageValue
from dateutil.parser import parse as parse_datetime
from urllib.parse import urlparse
from decimal import Decimal, ROUND_HALF_EVEN


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
        extensions (Dict[str, Any]): Additional metadata about the source.

    Example:
        >>> source = Source(
        ...     uri="https://example.com/audio.mp3",
        ...     duration=300.5,
        ...     languages=[Lang("en"), Lang("es")],
        ...     extensions={"bitrate": "128kbps"}
        ... )
    """

    uri: Optional[str] = None
    duration: Optional[float] = None
    languages: Optional[List[Lang]] = None
    extensions: Dict[str, Any] = field(
        default_factory=dict
    )  # Ensure extensions is used instead of additional_info


@dataclass
class Metadata:
    """Represents the metadata of the Standard Transcription JSON (STJ).

    This class contains various metadata fields that provide context and
    information about the transcription process and content.

    Attributes:
        transcriber (Transcriber): Information about the transcription system used.
        created_at (datetime): Timestamp of when the transcription was created.
        version (str): STJ specification version (e.g., "0.5.0").
        source (Optional[Source]): Information about the source media, if available.
        languages (Optional[List[Lang]]): List of languages used in the transcription.
        confidence_threshold (Optional[float]): Minimum confidence score for included words, if applicable.
        extensions (Dict[str, Any]): Additional metadata key-value pairs.

    Example:
        >>> from datetime import datetime, timezone
        >>> metadata = Metadata(
        ...     transcriber=Transcriber(name="AutoTranscribe", version="2.1.0"),
        ...     created_at=datetime.now(timezone.utc),
        ...     version="0.5.0",
        ...     languages=[Lang("en"), Lang("es")],
        ...     confidence_threshold=0.8,
        ...     extensions={"audio_quality": "high"}
        ... )
    """

    transcriber: Transcriber
    created_at: datetime
    version: str  # Added for v0.5.0 compliance
    source: Optional[Source] = None
    languages: Optional[List[Lang]] = None
    confidence_threshold: Optional[float] = None
    extensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Speaker:
    """Represents a speaker in the transcript.

    This class is used to identify and provide information about individuals
    speaking in the transcribed content.

    Attributes:
        id (str): Unique identifier for the speaker within the transcript.
        name (Optional[str]): Name or label for the speaker.
        extensions (Dict[str, Any]): Additional metadata about the speaker.

    Example:
        >>> speaker = Speaker(
        ...     id="speaker1",
        ...     name="John Doe",
        ...     extensions={"age": 30, "gender": "male"}
        ... )
    """

    id: str
    name: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Style:
    """Represents a style in the transcript.

    Styles can be used to indicate different formatting or presentation
    for segments of the transcript.

    Attributes:
        id (str): Unique identifier for the style within the transcript.
        text (Optional[Dict[str, Any]]): Text appearance information.
        display (Optional[Dict[str, Any]]): Display information for the style.
        extensions (Dict[str, Any]): Additional metadata about the style.

    Example:
        >>> style = Style(
        ...     id="emphasis",
        ...     text={"font-weight": "bold"},
        ...     display={"vertical-align": "super"},
        ...     extensions={"usage": "for important phrases"}
        ... )
    """

    id: str
    text: Optional[Dict[str, Any]] = None
    display: Optional[Dict[str, Any]] = None
    extensions: Dict[str, Any] = field(default_factory=dict)


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
        extensions (Dict[str, Any]): Additional metadata about the word.

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
        ...     extensions={"phoneme": "hə'ləʊ"}
        ... )
    """

    start: float
    end: float
    text: str
    confidence: Optional[float] = None
    extensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Segment:
    """Represents a timed segment in the transcript with optional word-level detail.

    A segment is a continuous portion of the transcript with its own timing, speaker,
    and optional word-level information. Segments must not overlap with each other
    and must contain valid timing information.

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
        is_zero_duration (bool): Indicates if the segment is zero-duration
        extensions (Dict[str, Any]): Additional metadata for extensibility
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
    is_zero_duration: bool = field(default=False)
    extensions: Dict[str, Any] = field(default_factory=dict)


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

    def validate(self, raise_exception: bool = True) -> List[ValidationIssue]:
        """Perform comprehensive validation of the STJ data.

        Validates all aspects of the STJ data according to the specification, including:
        - Language code validity using ISO 639 standards
        - Confidence score ranges (0.0 to 1.0)
        - Speaker and style ID references
        - Segment timing and ordering
        - Word timing and content matching
        - Zero-duration segment handling

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

        # Add required fields validation
        issues.extend(self._validate_required_fields())
        issues.extend(self._validate_types())

        # Version validation
        issues.extend(self._validate_version(self.metadata.version))

        # URI validation
        if self.metadata.source and self.metadata.source.uri:
            issues.extend(
                self._validate_uri(self.metadata.source.uri, "metadata.source.uri")
            )

        # Extensions validation at all levels
        issues.extend(
            self._validate_extensions(self.metadata.extensions, "metadata.extensions")
        )
        if self.metadata.source:
            issues.extend(
                self._validate_extensions(
                    self.metadata.source.extensions, "metadata.source.extensions"
                )
            )

        # Add existing validation calls
        issues.extend(self._validate_language_codes())
        issues.extend(self._validate_confidence_threshold())
        issues.extend(self._validate_speaker_and_style_ids())
        issues.extend(self._validate_segments())
        issues.extend(self._validate_confidence_scores())
        issues.extend(self._validate_style_format())

        # Validate metadata.languages
        if hasattr(self.metadata, 'languages'):
            for lang in self.metadata.languages:
                try:
                    Lang(lang)
                except iso639.exceptions.InvalidLanguageValue:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid language code in metadata.languages: '{lang}'",
                            location="metadata.languages"
                        )
                    )
        
        # Validate language in each segment
        for idx, segment in enumerate(self.transcript.segments):
            if hasattr(segment, 'language'):
                try:
                    Lang(segment.language)
                except iso639.exceptions.InvalidLanguageValue:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid language code in segment[{idx}].language: '{segment.language}'",
                            location=f"Segment[{idx}].language"
                        )
                    )
        
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
            validate (bool): If True, perform validation after loading. Defaults to False.
            raise_exception (bool): If True and validation issues are found, raises ValidationError.

        Returns:
            StandardTranscriptionJSON: Loaded STJ instance.

        Raises:
            FileNotFoundError: If the specified file is not found.
            json.JSONDecodeError: If there's an error decoding the JSON.
            STJError: For unexpected errors during file loading.
            ValidationError: If validation fails and raise_exception is True.
        """
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            stj_instance = cls.from_dict(data)
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
    def from_dict(
        cls, data: Dict[str, Any], validate: bool = False
    ) -> "StandardTranscriptionJSON":
        """Create a StandardTranscriptionJSON object from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing STJ data.
            validate (bool): If True, validate the data after deserialization. Defaults to False.

        Returns:
            StandardTranscriptionJSON: A new StandardTranscriptionJSON object.
        """
        metadata = cls._deserialize_metadata(data.get("metadata", {}))
        transcript = cls._deserialize_transcript(data.get("transcript", {}))
        stj = cls(metadata=metadata, transcript=transcript)
        return stj

    @classmethod
    def _deserialize_metadata(cls, data: Dict[str, Any]) -> Metadata:
        """Deserialize metadata from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing metadata.

        Returns:
            Metadata: Deserialized metadata object.
        """
        # Removed exception raising for missing required fields
        # if "transcriber" not in data:
        #     raise KeyError("Missing required field: 'transcriber' in metadata.")
        # if "created_at" not in data:
        #     raise KeyError("Missing required field: 'created_at' in metadata.")
        # if "version" not in data:
        #     raise KeyError("Missing required field: 'version' in metadata.")

        # Handle first-class fields explicitly
        transcriber_data = data.get("transcriber", {})
        transcriber = Transcriber(
            name=transcriber_data.get("name"),
            version=transcriber_data.get("version")
        )
        
        created_at_str = data.get("created_at")
        if created_at_str:
            created_at = parse_datetime(created_at_str)
        else:
            created_at = None  # Will be checked during validation
        
        version = data.get("version")
        
        # Handle optional first-class fields
        source = cls._deserialize_source(data.get("source"))
        languages = cls._deserialize_languages(data.get("languages"))
        confidence_threshold = data.get("confidence_threshold")
        
        # Extensions is its own field in the input
        extensions = data.get("extensions", {})
        
        return Metadata(
            transcriber=transcriber,
            created_at=created_at,
            version=version,
            source=source,
            languages=languages,
            confidence_threshold=confidence_threshold,
            extensions=extensions,
        )

    @classmethod
    def _deserialize_transcript(cls, s: dict) -> Transcript:
        """
        Deserialize transcript from a dictionary without raising exceptions for invalid data.

        Args:
            s (dict): Dictionary containing transcript data.

        Returns:
            Transcript: Deserialized transcript object.
        """
        speakers = []
        for speaker_data in s.get("speakers", []):
            speaker = Speaker(
                id=speaker_data.get("id", ""),  # Default to empty string if missing
                name=speaker_data.get("name"),
                extensions=speaker_data.get("extensions", {}),
            )
            speakers.append(speaker)

        styles = []
        for style_data in s.get("styles", []):
            style = Style(
                id=style_data.get("id", ""),  # Default to empty string if missing
                text=style_data.get("text"),
                display=style_data.get("display"),
                extensions=style_data.get("extensions", {}),
            )
            styles.append(style)
        styles = styles if styles else None

        segments = []
        for segment_data in s.get("segments", []):
            words = []
            for word_data in segment_data.get("words", []):
                word = Word(
                    start=word_data.get("start", 0.0),
                    end=word_data.get("end", 0.0),
                    text=word_data.get("text", ""),
                    confidence=word_data.get("confidence"),
                    extensions=word_data.get("extensions", {}),
                )
                words.append(word)
            words = words if words else None

            # Adjusted to handle invalid language codes without raising exceptions
            language_code = segment_data.get("language")
            if language_code:
                try:
                    language = Lang(language_code)
                except InvalidLanguageValue:
                    language = None  # Will be checked during validation
            else:
                language = None

            word_timing_mode = segment_data.get("word_timing_mode")
            if word_timing_mode:
                try:
                    word_timing_mode = WordTimingMode(word_timing_mode).value  # Convert to string value
                except ValueError:
                    word_timing_mode = None  # Set to None instead of raising exception

            segment = Segment(
                start=segment_data.get("start", 0.0),
                end=segment_data.get("end", 0.0),
                text=segment_data.get("text", ""),
                speaker_id=segment_data.get("speaker_id"),
                confidence=segment_data.get("confidence"),
                language=cls._deserialize_language(segment_data.get("language")),
                style_id=segment_data.get("style_id"),
                words=words,
                word_timing_mode=word_timing_mode,  # Use string value or None
                is_zero_duration=segment_data.get("is_zero_duration", False),
                extensions=segment_data.get("extensions", {}),
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
        # Create a shallow copy of self to avoid modifying the original
        data = {
            'metadata': {
                'transcriber': asdict(self.metadata.transcriber),
                'created_at': self.metadata.created_at,
                'version': self.metadata.version,
                'confidence_threshold': self.metadata.confidence_threshold,
                'languages': [lang.pt1 or lang.pt3 for lang in self.metadata.languages] if self.metadata.languages else None,
                'extensions': self.metadata.extensions,
            },
            'transcript': {
                'speakers': [asdict(speaker) for speaker in self.transcript.speakers],
                'segments': [{
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text,
                    'speaker_id': segment.speaker_id,
                    'confidence': segment.confidence,
                    'language': segment.language.pt1 or segment.language.pt3 if segment.language else None,
                    'style_id': segment.style_id,
                    'words': [asdict(word) for word in segment.words] if segment.words else None,
                    'word_timing_mode': segment.word_timing_mode.value if segment.word_timing_mode else None,
                    'is_zero_duration': segment.is_zero_duration,
                    'extensions': segment.extensions,
                } for segment in self.transcript.segments],
                'styles': [asdict(style) for style in self.transcript.styles] if self.transcript.styles else None,
            }
        }

        # Add source if it exists
        if self.metadata.source:
            data['metadata']['source'] = {
                'uri': self.metadata.source.uri,
                'duration': self.metadata.source.duration,
                'languages': [lang.pt1 or lang.pt3 for lang in self.metadata.source.languages] if self.metadata.source.languages else None,
                'extensions': self.metadata.source.extensions,
            }

        return self._custom_serialize(data)

    def _custom_serialize(self, data: Any) -> Any:
        """Recursively serialize data, handling custom types.

        Args:
            data (Any): Data to serialize.

        Returns:
            Any: Serialized data.
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Skip is_zero_duration if it's False
                if key == "is_zero_duration" and value is False:
                    continue
                if value is not None:  # Keep existing None check
                    result[key] = self._custom_serialize(value)
            return result
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
        elif isinstance(data, str):
            # Normalize string to NFC
            return unicodedata.normalize("NFC", data)
        else:
            return data

    def _validate_language_codes(self) -> List[ValidationIssue]:
        """
        Validate language codes in metadata and segments.

        This method checks the validity of language codes in the metadata,
        source information, and individual segments. It also enforces that
        the same language is not represented using both ISO 639-1 and ISO 639-3 codes.

        Returns:
            List[ValidationIssue]: List of validation issues related to language codes.
        """
        issues = []
        language_code_map = {}

        # Helper function to map language codes to their ISO 639-1 and ISO 639-3 equivalents
        def map_language_codes(codes: List[str], context: str):
            for code in codes:
                try:
                    # Use Lang directly instead of Language.from_part1/3
                    lang = Lang(code)
                    primary = lang.pt1 or lang.pt3
                    language_code_map.setdefault(lang.name.lower(), set()).add(code)
                except (KeyError, InvalidLanguageValue):
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid language code in {context}: {code}",
                            location=context,
                        )
                    )

        # Validate raw string codes in metadata.languages
        if self.metadata.languages:
            raw_codes = [lang.pt1 or lang.pt3 if isinstance(lang, Lang) else str(lang) 
                        for lang in self.metadata.languages]
            map_language_codes(raw_codes, "metadata.languages")

        # Validate raw string codes in metadata.source.languages
        if self.metadata.source and self.metadata.source.languages:
            raw_codes = [lang.pt1 or lang.pt3 if isinstance(lang, Lang) else str(lang) 
                        for lang in self.metadata.source.languages]
            map_language_codes(raw_codes, "metadata.source.languages")

        # Check for consistency: same language should not have both ISO 639-1 and ISO 639-3 codes
        for language, codes in language_code_map.items():
            has_part1 = any(len(code) == 2 for code in codes)
            has_part3 = any(len(code) == 3 for code in codes)
            if has_part1 and has_part3:
                issues.append(
                    ValidationIssue(
                        message=f"Language code inconsistency for '{language}': Mix of ISO 639-1 and ISO 639-3 codes ({', '.join(codes)})",
                        location="metadata.languages and metadata.source.languages",
                    )
                )

        # Additional validation using validate_language_code
        # Validate metadata.languages
        if self.metadata.languages:
            for lang in self.metadata.languages:
                if isinstance(lang, Lang):
                    code = lang.pt1 or lang.pt3  # Using correct attributes
                    if not self.validate_language_code(code):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid language code in metadata.languages: {code}",
                                location="metadata.languages",
                            )
                        )

        # Validate source languages
        if self.metadata.source and self.metadata.source.languages:
            for lang in self.metadata.source.languages:
                if isinstance(lang, Lang):
                    code = lang.pt1 or lang.pt3  # Using correct attributes
                    if not self.validate_language_code(code):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid language code in metadata.source.languages: {code}",
                                location="metadata.source.languages",
                            )
                        )

        # Validate segment languages
        for idx, segment in enumerate(self.transcript.segments):
            if segment.language:
                if isinstance(segment.language, Lang):
                    code = segment.language.pt1 or segment.language.pt3  # Using correct attributes
                    if not self.validate_language_code(code):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid language code in segment: {code}",
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

        Ensures that all speaker_id and style_id values in segments refer to
        valid speakers and styles and conform to specified format constraints.
        """
        issues = []
        # Collect valid speaker and style IDs
        valid_speaker_ids = {speaker.id for speaker in self.transcript.speakers}
        valid_style_ids = (
            {style.id for style in self.transcript.styles}
            if self.transcript.styles
            else set()
        )

        for idx, segment in enumerate(self.transcript.segments):
            # Validate speaker_id format and constraints
            if segment.speaker_id:
                # Check allowed characters and length
                if not re.match(r"^[A-Za-z0-9_-]{1,64}$", segment.speaker_id):
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid speaker_id format: '{segment.speaker_id}'. Must be 1-64 characters long and contain only letters, digits, underscores, or hyphens.",
                            location=f"Segment[{idx}].speaker_id",
                        )
                    )
                elif segment.speaker_id not in valid_speaker_ids:
                    issues.append(
                        ValidationIssue(
                            message=f"speaker_id '{segment.speaker_id}' does not exist in the speakers list.",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )
            # Validate style_id format and constraints
            if segment.style_id:
                # Check allowed characters and length
                if not re.match(r"^[A-Za-z0-9_-]{1,64}$", segment.style_id):
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid style_id format: '{segment.style_id}'. Must be 1-64 characters long and contain only letters, digits, underscores, or hyphens.",
                            location=f"Segment[{idx}].style_id",
                        )
                    )
                elif segment.style_id not in valid_style_ids:
                    issues.append(
                        ValidationIssue(
                            message=f"style_id '{segment.style_id}' does not exist in the styles list.",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )
        return issues

    def _validate_segments(self) -> List[ValidationIssue]:
        """Validate segments according to STJ spec requirements."""
        issues = []
        previous_end = -1

        # Check segments are ordered by start time and don't overlap
        for i in range(len(self.transcript.segments)):
            current = self.transcript.segments[i]

            # Validate time format for start and end
            issues.extend(
                self._validate_time_format(current.start, f"Segment[{i}].start")
            )
            issues.extend(self._validate_time_format(current.end, f"Segment[{i}].end"))

            # Check ordering and overlap
            if i > 0:
                previous = self.transcript.segments[i - 1]

                # Ensure current segment starts after or at the end of the previous segment
                if current.start < previous.start:
                    issues.append(
                        ValidationIssue(
                            message="Segments must be ordered by start time",
                            location=f"Segment[{i}] starting at {current.start}",
                        )
                    )
                elif current.start == previous.start and current.end < previous.end:
                    issues.append(
                        ValidationIssue(
                            message="Segments with identical start times must be ordered by end time in ascending order",
                            location=f"Segment[{i}] starting at {current.start}",
                        )
                    )

                # Check for overlap, allowing zero-duration segments to share timestamps
                if current.start < previous.end and not (
                    current.start
                    == previous.end
                    == current.end  # Allow zero-duration segments
                ):
                    issues.append(
                        ValidationIssue(
                            message=f"Segments must not overlap. Previous segment ends at {previous.end}",
                            location=f"Segment[{i}] starting at {current.start}",
                        )
                    )

            # Update 'previous_end' for the next iteration
            previous_end = current.end

            # Validate zero-duration segments
            if current.start == current.end:
                if not current.is_zero_duration:
                    issues.append(
                        ValidationIssue(
                            message="Zero duration segment must have is_zero_duration set to true",
                            location=f"Segment[{i}] starting at {current.start}",
                        )
                    )
                if current.words:
                    issues.append(
                        ValidationIssue(
                            message="Zero duration segment must not have words array",
                            location=f"Segment[{i}] starting at {current.start}",
                        )
                    )
                if current.word_timing_mode:
                    issues.append(
                        ValidationIssue(
                            message="Zero duration segment must not specify word_timing_mode",
                            location=f"Segment[{i}] starting at {current.start}",
                        )
                    )
            elif current.is_zero_duration:
                issues.append(
                    ValidationIssue(
                        message="Non-zero duration segment cannot have is_zero_duration set to true",
                        location=f"Segment[{i}] starting at {current.start}",
                    )
                )

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

        # **New Validation Added Below**
        if segment.is_zero_duration:
            if words:
                issues.append(
                    ValidationIssue(
                        message="Zero duration segment must not have words array",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )
            if word_timing_mode:
                issues.append(
                    ValidationIssue(
                        message="Zero duration segment must not specify word_timing_mode",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )
            # No further word validations needed for zero-duration segments
            return issues

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
            if words:
                # Determine if all words have timing
                all_words_have_timing = all(
                    word.start is not None and word.end is not None for word in words
                )
                if all_words_have_timing:
                    word_timing_mode = WordTimingMode.COMPLETE
                elif any(
                    word.start is not None and word.end is not None for word in words
                ):
                    issues.append(
                        ValidationIssue(
                            message="Incomplete word timing data requires 'word_timing_mode' to be explicitly set to 'partial'",
                            location=f"Segment[{segment_idx}] starting at {segment.start}",
                        )
                    )
                else:
                    word_timing_mode = WordTimingMode.NONE
            else:
                word_timing_mode = WordTimingMode.NONE

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
            # Add time format validation for word start and end times
            issues.extend(
                self._validate_time_format(
                    word.start, f"Segment[{segment_idx}].Word[{word_idx}].start"
                )
            )
            issues.extend(
                self._validate_time_format(
                    word.end, f"Segment[{segment_idx}].Word[{word_idx}].end"
                )
            )

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
                word_duration = word.extensions.get("word_duration")
                if word_duration != WordDuration.ZERO.value:
                    issues.append(
                        ValidationIssue(
                            message=f"Zero-duration word must have 'word_duration' set to '{WordDuration.ZERO.value}'",
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
            else:
                # **New Validation Added Here**
                if "word_duration" in word.extensions:
                    issues.append(
                        ValidationIssue(
                            message="word_duration should not be present for non-zero-duration words",
                            location=f"Segment[{segment_idx}].Word[{word_idx}] starting at {word.start}",
                        )
                    )

            previous_word_end = word.end
            concatenated_words += word.text + " "

        if word_timing_mode == WordTimingMode.COMPLETE:
            # All words must have timing info
            if not all(
                word.start is not None and word.end is not None for word in words
            ):
                issues.append(
                    ValidationIssue(
                        message="COMPLETE word timing mode requires timing for all words",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )
        elif word_timing_mode == WordTimingMode.PARTIAL:
            # At least one word must have timing info
            if not any(
                word.start is not None and word.end is not None for word in words
            ):
                issues.append(
                    ValidationIssue(
                        message="PARTIAL word timing mode requires timing for at least one word",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )

        if word_timing_mode == WordTimingMode.COMPLETE:
            # Normalize texts by removing extra whitespace and punctuation
            segment_text = re.sub(r"[^\w\s]", "", segment.text).lower()
            segment_text = " ".join(segment_text.split())

            words_text = re.sub(r"[^\w\s]", "", concatenated_words).lower()
            words_text = " ".join(words_text.split())

            if segment_text != words_text:
                issues.append(
                    ValidationIssue(
                        message=f"Segment text does not match concatenated word texts (ignoring whitespace/punctuation). Segment: '{segment.text}', Words: '{concatenated_words}'",
                        location=f"Segment[{segment_idx}] starting at {segment.start}",
                    )
                )

        return issues

    def _validate_confidence_scores(self) -> List[ValidationIssue]:
        """
        Validate confidence scores in segments and words.

        Ensures that all confidence scores are within the valid range [0.0, 1.0] and have at most three decimal places.

        Returns:
            List[ValidationIssue]: List of validation issues related to confidence scores.
        """

        def _has_at_most_three_decimals(value: float) -> bool:
            """Check whether a float has at most three decimal places."""
            str_value = (
                f"{value:.10f}".rstrip("0").rstrip(".")
                if "." in f"{value:.10f}"
                else f"{value}"
            )
            if "." in str_value:
                decimal_places = len(str_value.split(".")[1])
                return decimal_places <= 3
            return True

        issues = []

        for idx, segment in enumerate(self.transcript.segments):
            if segment.confidence is not None:
                if not (0.0 <= segment.confidence <= 1.0):
                    issues.append(
                        ValidationIssue(
                            message=f"Segment confidence {segment.confidence} out of range [0.0, 1.0]",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )

                if not _has_at_most_three_decimals(segment.confidence):
                    rounded_confidence = float(
                        Decimal(str(segment.confidence)).quantize(
                            Decimal("0.001"), rounding=ROUND_HALF_EVEN
                        )
                    )
                    segment.confidence = rounded_confidence
                    issues.append(
                        ValidationIssue(
                            message=f"Segment confidence rounded to three decimal places: {segment.confidence}",
                            location=f"Segment[{idx}] starting at {segment.start}",
                        )
                    )

            for word_idx, word in enumerate(segment.words or []):
                if word.confidence is not None:
                    if not (0.0 <= word.confidence <= 1.0):
                        issues.append(
                            ValidationIssue(
                                message=f"Word confidence {word.confidence} out of range [0.0, 1.0]",
                                location=f"Segment[{idx}].Word[{word_idx}] starting at {word.start}",
                            )
                        )

                    if not _has_at_most_three_decimals(word.confidence):
                        rounded_word_confidence = float(
                            Decimal(str(word.confidence)).quantize(
                                Decimal("0.001"), rounding=ROUND_HALF_EVEN
                            )
                        )
                        word.confidence = rounded_word_confidence
                        issues.append(
                            ValidationIssue(
                                message=f"Word confidence rounded to three decimal places: {word.confidence}",
                                location=f"Segment[{idx}].Word[{word_idx}] starting at {word.start}",
                            )
                        )

        return issues

    def _validate_style_format(self) -> List[ValidationIssue]:
        """Validate style format according to the specification."""
        issues = []

        if not self.transcript.styles:
            return issues

        VALID_TEXT_PROPERTIES = {
            "color",  # RGB hex color (#RRGGBB)
            "background",  # RGB hex color (#RRGGBB)
            "bold",  # boolean
            "italic",  # boolean
            "underline",  # boolean
            "size",  # percentage (e.g., "120%")
            "opacity",  # percentage (e.g., "80%")
        }

        for idx, style in enumerate(self.transcript.styles):
            # Validate required id field
            if not style.id:
                issues.append(
                    ValidationIssue(
                        message="Style ID is required and must be non-empty",
                        location=f"Style[{idx}]",
                    )
                )

            # Validate text properties
            if style.text:
                for key, value in style.text.items():
                    if key not in VALID_TEXT_PROPERTIES:
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid text property: {key}",
                                location=f"Style[{idx}].text",
                            )
                        )
                    if key in {"bold", "italic", "underline"} and not isinstance(
                        value, bool
                    ):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid {key} value: {value}. Must be boolean",
                                location=f"Style[{idx}].text.{key}",
                            )
                        )
                    if key in {"color", "background"} and not re.match(
                        r"^#[0-9A-Fa-f]{6}$", str(value)
                    ):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid color format for {key}: {value}. Must be in #RRGGBB format",
                                location=f"Style[{idx}].text.{key}",
                            )
                        )
                    if key == "size":
                        if not re.match(r"^\d+%$", str(value)):
                            issues.append(
                                ValidationIssue(
                                    message=f"Invalid size format: {value}. Must be percentage (e.g., '120%')",
                                    location=f"Style[{idx}].text.size",
                                )
                            )
                        else:
                            size_value = int(value.rstrip("%"))
                            if size_value <= 0:
                                issues.append(
                                    ValidationIssue(
                                        message=f"'size' must be greater than 0%, got {value}",
                                        location=f"Style[{idx}].text.size",
                                    )
                                )
                    if key == "opacity":
                        if not re.match(r"^\d+%$", str(value)):
                            issues.append(
                                ValidationIssue(
                                    message=f"Invalid opacity format: {value}. Must be percentage (e.g., '80%')",
                                    location=f"Style[{idx}].text.opacity",
                                )
                            )
                        else:
                            opacity_value = int(value.rstrip("%"))
                            if not (0 <= opacity_value <= 100):
                                issues.append(
                                    ValidationIssue(
                                        message=f"'opacity' must be between 0% and 100%, got {value}",
                                        location=f"Style[{idx}].text.opacity",
                                    )
                                )

            # Validate display properties
            if style.display:
                if "align" in style.display and style.display["align"] not in {
                    "left",
                    "center",
                    "right",
                }:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid align value: {style.display['align']}",
                            location=f"Style[{idx}].display.align",
                        )
                    )
                if "vertical" in style.display and style.display["vertical"] not in {
                    "top",
                    "middle",
                    "bottom",
                }:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid vertical value: {style.display['vertical']}",
                            location=f"Style[{idx}].display.vertical",
                        )
                    )
                if "position" in style.display:
                    pos = style.display["position"]
                    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
                        issues.append(
                            ValidationIssue(
                                message="Position must contain 'x' and 'y' coordinates",
                                location=f"Style[{idx}].display.position",
                            )
                        )
                    else:
                        for coord in ["x", "y"]:
                            if not re.match(r"^\d+%$", str(pos[coord])):
                                issues.append(
                                    ValidationIssue(
                                        message=f"Invalid {coord} position: {pos[coord]}. Must be percentage",
                                        location=f"Style[{idx}].display.position.{coord}",
                                    )
                                )
                            else:
                                percent_value = int(pos[coord].rstrip("%"))
                                if not (0 <= percent_value <= 100):
                                    issues.append(
                                        ValidationIssue(
                                            message=f"'{coord}' position must be between 0% and 100%, got {pos[coord]}",
                                            location=f"Style[{idx}].display.position.{coord}",
                                        )
                                    )

            # Validate extensions for styles
            if style.extensions:
                issues.extend(
                    self._validate_extensions(
                        style.extensions, f"Style[{idx}].extensions"
                    )
                )

        return issues

    def _validate_extensions(
        self, extensions: Dict[str, Any], location: str
    ) -> List[ValidationIssue]:
        """Validate extensions field according to specification."""
        issues = []

        RESERVED_NAMESPACES = {"stj", "webvtt", "ttml", "ssa", "srt", "dfxp", "smptett"}

        if not isinstance(extensions, dict):
            issues.append(
                ValidationIssue(
                    message="Extensions must be a dictionary", location=location
                )
            )
            return issues

        namespace_pattern = re.compile(r"^[a-z0-9\-]+$")

        for namespace, value in extensions.items():
            # Validate namespace naming convention
            if not namespace_pattern.match(namespace):
                issues.append(
                    ValidationIssue(
                        message=f"Invalid extension namespace '{namespace}'. Namespaces must be lowercase alphanumeric with optional hyphens.",
                        location=f"{location}.{namespace}",
                    )
                )

            if namespace in RESERVED_NAMESPACES:
                issues.append(
                    ValidationIssue(
                        message=f"Reserved namespace '{namespace}' cannot be used",
                        location=f"{location}.{namespace}",
                    )
                )

            if not isinstance(value, dict):
                issues.append(
                    ValidationIssue(
                        message=f"Extension namespace '{namespace}' must contain a dictionary",
                        location=f"{location}.{namespace}",
                    )
                )
                continue  # Cannot traverse further if value is not a dict

            # Recursively validate nested extensions if present
            if "extensions" in value:
                nested_extensions = value["extensions"]
                nested_location = f"{location}.{namespace}.extensions"
                issues.extend(
                    self._validate_extensions(nested_extensions, nested_location)
                )

        return issues

    def _validate_speaker_id(
        self, speaker_id: str, location: str
    ) -> List[ValidationIssue]:
        """Validate speaker ID format according to specification."""
        issues = []

        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", speaker_id):
            issues.append(
                ValidationIssue(
                    message=f"Invalid speaker ID format: {speaker_id}. Must contain only letters, digits, underscores, or hyphens, with length between 1 and 64 characters.",
                    location=location,
                )
            )

        return issues

    def _validate_version(self, version: str) -> List[ValidationIssue]:
        """Validate STJ version format.

        Ensures that the version follows the semantic versioning and is compatible with allowed versions.

        """
        issues = []

        # Check semantic versioning format
        semver_pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(semver_pattern, version):
            issues.append(
                ValidationIssue(
                    message=f"Invalid version format: {version}. Must follow semantic versioning (e.g., 'x.y.z').",
                    location="metadata.version",
                )
            )

        # Check version compatibility
        try:
            major, minor, patch = map(int, version.split("."))
            if major != 0 or minor < 5:
                issues.append(
                    ValidationIssue(
                        message=f"Invalid version: {version}. Must be '0.5.x' or higher.",
                        location="metadata.version",
                    )
                )
        except ValueError:
            issues.append(
                ValidationIssue(
                    message=f"Version components must be integers: {version}.",
                    location="metadata.version",
                )
            )

        return issues

    def _validate_uri(self, uri: str, location: str) -> List[ValidationIssue]:
        issues = []
        parsed = urlparse(uri)

        # Validate scheme presence
        if not parsed.scheme:
            issues.append(
                ValidationIssue(
                    message="URI must include a scheme (e.g., http, https, file).",
                    location=location,
                )
            )
        else:
            # Validate allowed schemes
            allowed_schemes = ["http", "https", "file"]
            if parsed.scheme not in allowed_schemes:
                issues.append(
                    ValidationIssue(
                        message=f"Invalid URI scheme '{parsed.scheme}'. Allowed schemes are: {', '.join(allowed_schemes)}.",
                        location=location,
                    )
                )

        # Validate netloc or path based on scheme
        if parsed.scheme in ["http", "https"]:
            if not parsed.netloc:
                issues.append(
                    ValidationIssue(
                        message=f"{parsed.scheme.upper()} URI must include a network location (e.g., domain name).",
                        location=location,
                    )
                )
        elif parsed.scheme == "file":
            if not parsed.path:
                issues.append(
                    ValidationIssue(
                        message="File URI must include a valid file path.",
                        location=location,
                    )
                )

        # Validate overall URI conformity to RFC 3986
        # Example: Check for prohibited characters
        if re.search(r"[^\w\-\.~:/?#\[\]@!$&\'()*+,;=%]", uri):
            issues.append(
                ValidationIssue(
                    message="URI contains invalid characters not allowed by RFC 3986.",
                    location=location,
                )
            )

        # Additional validations can be added here as needed

        return issues

    def _validate_zero_duration(
        self, start: float, end: float, is_zero_duration: bool, location: str
    ) -> List[ValidationIssue]:
        """Validate zero duration handling."""
        issues = []

        if start == end and not is_zero_duration:
            issues.append(
                ValidationIssue(
                    message="Zero duration item must have is_zero_duration set to true",
                    location=location,
                )
            )
        elif start != end and is_zero_duration:
            issues.append(
                ValidationIssue(
                    message="Non-zero duration item cannot have is_zero_duration set to true",
                    location=location,
                )
            )

        return issues

    def _validate_style_id(self, style_id: str, location: str) -> List[ValidationIssue]:
        """Validate style ID format according to specification."""
        issues = []

        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", style_id):
            issues.append(
                ValidationIssue(
                    message=f"Invalid style ID format: {style_id}. Must contain only letters, digits, underscores, or hyphens, with length between 1 and 64 characters.",
                    location=location,
                )
            )

        return issues

    def _validate_required_fields(self) -> List[ValidationIssue]:
        """Validate the presence and content of required metadata fields."""
        issues = []
        metadata = self.metadata

        # Validate transcriber.name
        if not metadata.transcriber or not metadata.transcriber.name:
            issues.append(
                ValidationIssue(
                    message="Missing or invalid 'transcriber.name'. It must be a non-empty string.",
                    location="metadata.transcriber.name",
                )
            )

        # Validate transcriber.version
        if not metadata.transcriber or not metadata.transcriber.version:
            issues.append(
                ValidationIssue(
                    message="Missing or invalid 'transcriber.version'. It must be a non-empty string.",
                    location="metadata.transcriber.version",
                )
            )

        # Validate created_at
        if not metadata.created_at or not isinstance(metadata.created_at, datetime):
            issues.append(
                ValidationIssue(
                    message="Missing or invalid 'created_at'. It must be a valid datetime object.",
                    location="metadata.created_at",
                )
            )
        else:
            # Ensure created_at is timezone-aware
            if metadata.created_at.tzinfo is None:
                issues.append(
                    ValidationIssue(
                        message="'created_at' must be timezone-aware.",
                        location="metadata.created_at",
                    )
                )

        # Validate version
        if not metadata.version or not isinstance(metadata.version, str):
            issues.append(
                ValidationIssue(
                    message="Missing or invalid 'metadata.version'. It must be a non-empty string.",
                    location="metadata.version",
                )
            )
        else:
            # Validate semantic versioning
            if not re.match(r"^\d+\.\d+\.\d+$", metadata.version):
                issues.append(
                    ValidationIssue(
                        message=f"Invalid 'metadata.version' format: {metadata.version}. Must follow semantic versioning (e.g., 'x.y.z').",
                        location="metadata.version",
                    )
                )
            else:
                # Check version compatibility as per specification
                try:
                    major, minor, patch = map(int, metadata.version.split("."))
                    if major != 0 or minor < 5:
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid 'metadata.version': {metadata.version}. Must be '0.5.x' or higher.",
                                location="metadata.version",
                            )
                        )
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            message=f"Version components must be integers: {metadata.version}.",
                            location="metadata.version",
                        )
                    )

        if not self.transcript.speakers:
            issues.append(
                ValidationIssue(
                    message="Missing 'transcript.speakers'. There must be at least one speaker.",
                    location="transcript.speakers",
                )
            )

        if not self.transcript.segments:
            issues.append(
                ValidationIssue(
                    message="Missing 'transcript.segments'. There must be at least one segment.",
                    location="transcript.segments",
                )
            )

        return issues

    def _validate_types(self) -> List[ValidationIssue]:
        """
        Validate the types of all fields in the STJ data according to the schema.

        Returns:
            List[ValidationIssue]: A list of issues found during type validation.
        """
        issues = []

        for idx, segment in enumerate(self.transcript.segments):
            # Validate start and end are numbers
            if not isinstance(segment.start, (int, float)):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].start must be a number.",
                        location=f"Segment[{idx}].start",
                    )
                )
            if not isinstance(segment.end, (int, float)):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].end must be a number.",
                        location=f"Segment[{idx}].end",
                    )
                )

            # Validate confidence is a number if present
            if segment.confidence is not None and not isinstance(
                segment.confidence, (int, float)
            ):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].confidence must be a number.",
                        location=f"Segment[{idx}].confidence",
                    )
                )

            # Validate speaker_id is a string if present
            if segment.speaker_id is not None and not isinstance(
                segment.speaker_id, str
            ):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].speaker_id must be a string.",
                        location=f"Segment[{idx}].speaker_id",
                    )
                )

            # Validate style_id is a string if present
            if segment.style_id is not None and not isinstance(segment.style_id, str):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].style_id must be a string.",
                        location=f"Segment[{idx}].style_id",
                    )
                )

            # Validate words is a list if present
            if segment.words is not None:
                if not isinstance(segment.words, list):
                    issues.append(
                        ValidationIssue(
                            message=f"Segment[{idx}].words must be a list.",
                            location=f"Segment[{idx}].words",
                        )
                    )
                else:
                    for word_idx, word in enumerate(segment.words):
                        if not isinstance(word.start, (int, float)):
                            issues.append(
                                ValidationIssue(
                                    message=f"Segment[{idx}].words[{word_idx}].start must be a number.",
                                    location=f"Segment[{idx}].words[{word_idx}].start",
                                )
                            )
                        if not isinstance(word.end, (int, float)):
                            issues.append(
                                ValidationIssue(
                                    message=f"Segment[{idx}].words[{word_idx}].end must be a number.",
                                    location=f"Segment[{idx}].words[{word_idx}].end",
                                )
                            )
                        if not isinstance(word.text, str):
                            issues.append(
                                ValidationIssue(
                                    message=f"Segment[{idx}].words[{word_idx}].text must be a string.",
                                    location=f"Segment[{idx}].words[{word_idx}].text",
                                )
                            )
                        if word.confidence is not None and not isinstance(
                            word.confidence, (int, float)
                        ):
                            issues.append(
                                ValidationIssue(
                                    message=f"Segment[{idx}].words[{word_idx}].confidence must be a number.",
                                    location=f"Segment[{idx}].words[{word_idx}].confidence",
                                )
                            )
                        # Removed the check for word.word_timing_mode

                        # Validate extensions is a dict if present
                        if word.extensions is not None and not isinstance(
                            word.extensions, dict
                        ):
                            issues.append(
                                ValidationIssue(
                                    message=f"Segment[{idx}].words[{word_idx}].extensions must be a dictionary.",
                                    location=f"Segment[{idx}].words[{word_idx}].extensions",
                                )
                            )

            # Validate language is a string if present
            if segment.language is not None and not isinstance(segment.language, str):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].language must be a string.",
                        location=f"Segment[{idx}].language",
                    )
                )

            # Validate word_timing_mode is a string or WordTimingMode enum if present
            if segment.word_timing_mode is not None and not isinstance(
                segment.word_timing_mode, (str, WordTimingMode)
            ):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].word_timing_mode must be a string or WordTimingMode enum.",
                        location=f"Segment[{idx}].word_timing_mode",
                    )
                )

            # Validate is_zero_duration is a bool
            if not isinstance(segment.is_zero_duration, bool):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].is_zero_duration must be a boolean.",
                        location=f"Segment[{idx}].is_zero_duration",
                    )
                )

            # Validate extensions is a dict if present
            if segment.extensions is not None and not isinstance(
                segment.extensions, dict
            ):
                issues.append(
                    ValidationIssue(
                        message=f"Segment[{idx}].extensions must be a dictionary.",
                        location=f"Segment[{idx}].extensions",
                    )
                )

        # Validate metadata fields
        if not isinstance(self.metadata.transcriber.name, str):
            issues.append(
                ValidationIssue(
                    message="metadata.transcriber.name must be a string.",
                    location="metadata.transcriber.name",
                )
            )
        if not isinstance(self.metadata.transcriber.version, str):
            issues.append(
                ValidationIssue(
                    message="metadata.transcriber.version must be a string.",
                    location="metadata.transcriber.version",
                )
            )
        if not isinstance(self.metadata.created_at, datetime):  # Changed from str to datetime
            issues.append(
                ValidationIssue(
                    message="metadata.created_at must be a datetime object.",  # Updated message
                    location="metadata.created_at",
                )
            )
        if not isinstance(self.metadata.version, str):
            issues.append(
                ValidationIssue(
                    message="metadata.version must be a string.",
                    location="metadata.version",
                )
            )
        if self.metadata.source is not None:
            if not isinstance(self.metadata.source.uri, str):
                issues.append(
                    ValidationIssue(
                        message="metadata.source.uri must be a string.",
                        location="metadata.source.uri",
                    )
                )
            if self.metadata.source.duration is not None and not isinstance(
                self.metadata.source.duration, (int, float)
            ):
                issues.append(
                    ValidationIssue(
                        message="metadata.source.duration must be a number.",
                        location="metadata.source.duration",
                    )
                )
            if self.metadata.source.languages is not None:
                if not isinstance(self.metadata.source.languages, list):
                    issues.append(
                        ValidationIssue(
                            message="metadata.source.languages must be a list of strings.",
                            location="metadata.source.languages",
                        )
                    )
                else:
                    for lang_idx, lang in enumerate(self.metadata.source.languages):
                        if not isinstance(lang, str):
                            issues.append(
                                ValidationIssue(
                                    message=f"metadata.source.languages[{lang_idx}] must be a string.",
                                    location=f"metadata.source.languages[{lang_idx}]",
                                )
                            )
            if self.metadata.languages is not None:
                if not isinstance(self.metadata.languages, list):
                    issues.append(
                        ValidationIssue(
                            message="metadata.languages must be a list of strings.",
                            location="metadata.languages",
                        )
                    )
                else:
                    for lang_idx, lang in enumerate(self.metadata.languages):
                        if not isinstance(lang, str):
                            issues.append(
                                ValidationIssue(
                                    message=f"metadata.languages[{lang_idx}] must be a string.",
                                    location=f"metadata.languages[{lang_idx}]",
                                )
                            )
            if self.metadata.confidence_threshold is not None and not isinstance(
                self.metadata.confidence_threshold, (int, float)
            ):
                issues.append(
                    ValidationIssue(
                        message="metadata.confidence_threshold must be a number.",
                        location="metadata.confidence_threshold",
                    )
                )
            if self.metadata.extensions is not None and not isinstance(
                self.metadata.extensions, dict
            ):
                issues.append(
                    ValidationIssue(
                        message="metadata.extensions must be a dictionary.",
                        location="metadata.extensions",
                    )
                )

        # Validate speakers
        if self.transcript.speakers:
            if not isinstance(self.transcript.speakers, list):
                issues.append(
                    ValidationIssue(
                        message="transcript.speakers must be a list.",
                        location="transcript.speakers",
                    )
                )
            else:
                for speaker_idx, speaker in enumerate(self.transcript.speakers):
                    if not isinstance(speaker.id, str):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.speakers[{speaker_idx}].id must be a string.",
                                location=f"transcript.speakers[{speaker_idx}].id",
                            )
                        )
                    if speaker.name is not None and not isinstance(speaker.name, str):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.speakers[{speaker_idx}].name must be a string.",
                                location=f"transcript.speakers[{speaker_idx}].name",
                            )
                        )
                    if speaker.extensions is not None and not isinstance(
                        speaker.extensions, dict
                    ):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.speakers[{speaker_idx}].extensions must be a dictionary.",
                                location=f"transcript.speakers[{speaker_idx}].extensions",
                            )
                        )

        # Validate styles
        if self.transcript.styles:
            if not isinstance(self.transcript.styles, list):
                issues.append(
                    ValidationIssue(
                        message="transcript.styles must be a list.",
                        location="transcript.styles",
                    )
                )
            else:
                for style_idx, style in enumerate(self.transcript.styles):
                    if not isinstance(style.id, str):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.styles[{style_idx}].id must be a string.",
                                location=f"transcript.styles[{style_idx}].id",
                            )
                        )
                    if style.text is not None and not isinstance(style.text, dict):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.styles[{style_idx}].text must be a dictionary.",
                                location=f"transcript.styles[{style_idx}].text",
                            )
                        )
                    if style.display is not None and not isinstance(
                        style.display, dict
                    ):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.styles[{style_idx}].display must be a dictionary.",
                                location=f"transcript.styles[{style_idx}].display",
                            )
                        )
                    if style.extensions is not None and not isinstance(
                        style.extensions, dict
                    ):
                        issues.append(
                            ValidationIssue(
                                message=f"transcript.styles[{style_idx}].extensions must be a dictionary.",
                                location=f"transcript.styles[{style_idx}].extensions",
                            )
                        )

                    # Validate extensions for styles
                    if style.extensions:
                        issues.extend(
                            self._validate_extensions(
                                style.extensions, f"Style[{idx}].extensions"
                            )
                        )

        # Validate transcript nested objects if any other type validations are needed

        return issues

    def _validate_time_format(
        self, time_value: float, location: str
    ) -> List[ValidationIssue]:
        """Validate time value according to STJ spec requirements."""
        issues = []

        # Must be non-negative
        if time_value < 0:
            issues.append(
                ValidationIssue(
                    message=f"Time value must be non-negative, got {time_value}",
                    location=location,
                )
            )

        # Must not exceed 999999.999
        if time_value > 999999.999:
            issues.append(
                ValidationIssue(
                    message=f"Time value exceeds maximum allowed (999999.999), got {time_value}",
                    location=location,
                )
            )

        # Check decimal precision (max 3 places)
        str_value = str(time_value)
        if "." in str_value:
            decimals = len(str_value.split(".")[1])
            if decimals > 3:
                issues.append(
                    ValidationIssue(
                        message=f"Time value has too many decimal places (max 3), got {decimals}",
                        location=location,
                    )
                )

        return issues

    def validate_language_code(self, code: str) -> bool:
        """
        Validate that the language code follows STJ spec requirements:
        - Must use ISO 639-1 (2-letter) when available
        - Can only use ISO 639-3 (3-letter) for languages without ISO 639-1 codes
        """
        if not code or not isinstance(code, str):
            return False

        try:
            # Try to get language entry from the code
            lang = Lang(code)  # Use Lang directly instead of Language.from_part1/3

            # If it's a 3-letter code but has a 2-letter equivalent, it's invalid per spec
            if len(code) == 3 and lang.pt1:  # Use pt1 instead of part1
                return False

            return True
        except (KeyError, InvalidLanguageValue):  # Use InvalidLanguageValue from iso639.exceptions
            return False

    # Add this method to handle deserialization of languages
    @classmethod
    def _deserialize_languages(cls, languages_data: Optional[List[str]]) -> List[Lang]:
        """Deserialize languages from a list of language codes.

        Args:
            languages_data (Optional[List[str]]): List of language codes to deserialize.

        Returns:
            List[Lang]: List of Lang objects. Invalid codes are skipped.
        """
        if not languages_data:
            return []

        languages = []
        for code in languages_data:
            try:
                # Attempt to create a Lang object from the code
                lang = Lang(code)
                languages.append(lang)
            except InvalidLanguageValue:
                # Skip invalid language codes
                continue

        return languages

    # Modified _deserialize_language method to handle invalid language codes without raising exceptions
    @classmethod
    def _deserialize_language(cls, code: Optional[str]) -> Optional[Lang]:
        """Deserialize a single language code without raising exceptions.
        
        Args:
            code (Optional[str]): Language code to deserialize.
        
        Returns:
            Optional[Lang]: Deserialized Lang object or None if invalid.
        """
        if code:
            try:
                return Lang(code)
            except InvalidLanguageValue:
                return None  # Will be handled during validation
        return None

    @classmethod
    def _deserialize_source(cls, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Deserialize source data from a dictionary.
        
        Args:
            data (Optional[Dict[str, Any]]): Dictionary containing source data, or None.
        
        Returns:
            Optional[Dict[str, Any]]: The source data dictionary, or None if no data provided.
        """
        return data if data is not None else None
