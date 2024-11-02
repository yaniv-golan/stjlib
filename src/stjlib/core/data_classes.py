"""STJLib core data classes for Standard Transcription JSON Format.

IMPORTANT: This module only defines data structures and serialization.
All validation is handled separately in stjlib.validation.validators.
Data classes should NOT perform validation - they should preserve data
as-is for validation to happen later.

This module provides the core data structures that represent STJ format components.
Each class corresponds to a specific part of the STJ structure and includes
serialization/deserialization capabilities.

Key Components:
    * STJ - Root object containing version, metadata, and transcript
    * Metadata - Information about the transcription process and source
    * Transcript - Core content with segments, speakers, and styles
    * Segment - Individual timed portions of the transcript
    * Word - Individual words with timing and confidence
    * Speaker - Speaker identification and metadata
    * Style - Text formatting and display properties

Features:
    * Complete STJ structure representation
    * JSON serialization/deserialization
    * Type hints for static analysis
    * Clean attribute management via dataclasses
    * Preserves data for validation layer

Example:
    ```python
    from stjlib.core.data_classes import STJ, Transcript, Segment

    # Create a basic STJ document
    transcript = Transcript(
        segments=[
            Segment(
                text="Hello world",
                start=0.0,
                end=1.5
            )
        ]
    )
    
    stj = STJ(
        version="0.6.0",
        transcript=transcript
    )

    # Serialize to dictionary
    data = stj.to_dict()
    
    # Deserialize from dictionary
    stj = STJ.from_dict(data)
    ```

Note:
    All classes use Python's dataclass decorator for clean attribute management
    and include from_dict/to_dict methods for JSON serialization. Data is preserved
    as-is without validation to maintain separation of concerns.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from iso639.exceptions import InvalidLanguageValue
from .enums import WordTimingMode


def _deserialize_language(code: Optional[str]) -> Optional[str]:
    """Deserializes a single language code without raising exceptions.

    Preserves the original language code for later validation, allowing validation
    to happen at a dedicated validation stage rather than during deserialization.

    Args:
        code (Optional[str]): Language code to deserialize or None

    Returns:
        Optional[str]: Original language code or None if None was provided

    Example:
        ```python
        lang = _deserialize_language("en")  # Returns "en"
        lang = _deserialize_language(None)  # Returns None
        lang = _deserialize_language("xxx") # Returns "xxx" for later validation
        ```

    Note:
        This function intentionally does not validate the language code,
        leaving that responsibility to the validation layer.
    """
    return code


def _deserialize_languages(languages_data: Optional[List[str]]) -> Optional[List[str]]:
    """Deserializes a list of language codes.

    Preserves the original language codes for later validation, allowing validation
    to happen at a dedicated validation stage rather than during deserialization.

    Args:
        languages_data (Optional[List[str]]): List of language codes to deserialize

    Returns:
        Optional[List[str]]: List of language codes or None if no languages provided

    Example:
        ```python
        langs = _deserialize_languages(["en", "es"])  # Returns ["en", "es"]
        langs = _deserialize_languages(None)  # Returns None
        langs = _deserialize_languages(["xxx"])  # Returns ["xxx"] for later validation
        ```

    Note:
        This function intentionally does not validate the language codes,
        leaving that responsibility to the validation layer.
    """
    if not languages_data:
        return None
    return languages_data


@dataclass
class STJ:
    """Root object representing the STJ structure.

    This class represents the root of an STJ document, containing the version,
    transcript, and optional metadata.

    Attributes:
        version (str): STJ specification version (e.g., "0.6.0")
        transcript (Transcript): Main content of the transcription
        metadata (Optional[Metadata]): Optional metadata about the transcription
        _additional_fields (Dict[str, Any]): Additional fields not included in the STJ structure
        _invalid_type (Optional[str]): Type of invalid input for later validation

    Example:
        ```python
        # Create a basic STJ document
        stj = STJ(
            version="0.6.0",
            transcript=transcript,
            metadata=Metadata(
                transcriber=Transcriber(name="MyTranscriber", version="1.0")
            )
        )

        # Serialize to dictionary
        data = stj.to_dict()

        # Create from dictionary
        stj = STJ.from_dict(data)
        ```

    Note:
        - version must follow semantic versioning (MAJOR.MINOR.PATCH)
        - transcript is required and must be a valid Transcript object
        - metadata is optional but must be a valid Metadata object if present
    """

    version: str
    transcript: Optional["Transcript"]
    metadata: Optional["Metadata"] = None
    _additional_fields: Dict[str, Any] = field(default_factory=dict, repr=False)
    _invalid_type: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "STJ":
        # For non-dict input, record the invalid type for later validation
        if not isinstance(data, dict):
            return cls(
                version="",
                transcript=None,
                _invalid_type=type(data).__name__,
            )
        # Handle wrapped STJ format
        if "stj" in data:
            data = data["stj"]
        # Extract known fields
        known_fields = {"version", "metadata", "transcript"}
        additional_fields = {k: v for k, v in data.items() if k not in known_fields}

        return cls(
            version=data.get("version", ""),
            metadata=Metadata.from_dict(data["metadata"])
            if "metadata" in data
            else None,
            transcript=Transcript.from_dict(data.get("transcript"))
            if "transcript" in data
            else None,
            _additional_fields=additional_fields,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the STJ instance to a dictionary."""
        if self.transcript is None:
            result = {"version": self.version}
        else:
            result = {"version": self.version, "transcript": self.transcript.to_dict()}
        if self.metadata is not None:
            result["metadata"] = self.metadata.to_dict()

        # Add any additional fields
        result.update(self._additional_fields)

        return {"stj": result}


@dataclass
class Transcriber:
    """Metadata about the transcription system or service.

    This class stores information about the system that created the transcription,
    including its name and version.

    Attributes:
        name (str): Name of the transcription system or service
        version (str): Version identifier of the transcription system

    Example:
        ```python
        # Create a transcriber instance
        transcriber = Transcriber(
            name="AutoTranscribe",
            version="2.1.0"
        )

        # Access transcriber information
        print(f"Created by {transcriber.name} v{transcriber.version}")
        ```

    Note:
        - Both name and version are optional but should be non-empty if present
        - Version format is not strictly specified but should be consistent
        - Empty or whitespace-only values are considered invalid
    """

    name: str
    version: str
    _invalid_type: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "Transcriber":
        """Creates a Transcriber instance from a dictionary.

        Args:
            data: Input that should be a dictionary containing transcriber data

        Returns:
            Transcriber: A new Transcriber instance

        Example:
            ```python
            data = {"name": "AutoTranscribe", "version": "2.1.0"}
            transcriber = Transcriber.from_dict(data)
            ```
        """
        # For non-dict input, return instance with type info for validation
        if not isinstance(data, dict):
            return cls(name="", version="", _invalid_type=type(data).__name__)

        return cls(
            name=data.get("name"),
            version=data.get("version"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Transcriber instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the transcriber.
            Returns None if no fields are set.

        Example:
            ```python
            transcriber = Transcriber(name="AutoTranscribe", version="2.1.0")
            data = transcriber.to_dict()
            # {'name': 'AutoTranscribe', 'version': '2.1.0'}
            ```
        """
        result = {}
        if self.name is not None:
            result["name"] = self.name
        if self.version is not None:
            result["version"] = self.version
        return result if result else None


@dataclass
class Source:
    """Source metadata for the transcription.

    This class contains information about the original media file that was
    transcribed, including its location, duration, languages, and additional metadata.

    Attributes:
        uri (Optional[str]): URI or path to the source media file
        duration (Optional[float]): Duration of the source media in seconds
        languages (Optional[List[str]]): List of languages present in the source media
        extensions (Dict[str, Any]): Additional metadata about the source

    Example:
        ```python
        # Create a source instance
        source = Source(
            uri="https://example.com/audio.mp3",
            duration=300.5,
            languages=["en", "es"],
            extensions={"bitrate": "128kbps"}
        )

        # Access source information
        print(f"Media duration: {source.duration} seconds")
        print(f"Languages: {', '.join(source.languages)}")
        ```

    Note:
        - All fields are optional
        - URI should be a valid URI according to RFC 3986
        - Duration must be non-negative if present
        - Languages must be valid ISO 639-1 or ISO 639-3 codes
        - Extensions can contain arbitrary metadata
    """

    uri: Optional[str] = None
    duration: Optional[float] = None
    languages: Optional[List[str]] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        """Creates a Source instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing source data

        Returns:
            Source: A new Source instance

        Example:
            ```python
            data = {
                "uri": "https://example.com/audio.mp3",
                "duration": 300.5,
                "languages": ["en", "es"]
            }
            source = Source.from_dict(data)
            ```
        """
        return cls(
            uri=data.get("uri"),
            duration=data.get("duration"),
            languages=_deserialize_languages(data.get("languages")),
            extensions=data.get("extensions", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Source instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the source

        Example:
            ```python
            source = Source(uri="https://example.com/audio.mp3", duration=300.5)
            data = source.to_dict()
            # {'uri': 'https://example.com/audio.mp3', 'duration': 300.5}
            ```
        """
        result = {}
        if self.uri is not None:
            result["uri"] = self.uri
        if self.duration is not None:
            result["duration"] = self.duration
        if self.languages is not None:
            result["languages"] = self.languages
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class Metadata:
    """Metadata for the Standard Transcription JSON (STJ).

    This class contains various metadata fields that provide context and
    information about the transcription process and content.

    Attributes:
        transcriber (Optional[Transcriber]): Information about the transcription system
        created_at (Optional[datetime]): Timestamp when transcription was created
        source (Optional[Source]): Information about the source media
        languages (Optional[List[str]]): List of languages in the transcription
        confidence_threshold (Optional[float]): Minimum confidence score for words
        extensions (Optional[Dict[str, Any]]): Additional metadata key-value pairs

    Example:
        ```python
        # Create metadata with transcriber and timestamp
        metadata = Metadata(
            transcriber=Transcriber(
                name="AutoTranscribe",
                version="2.1.0"
            ),
            created_at=datetime.now(timezone.utc),
            languages=["en", "es"],
            confidence_threshold=0.8
        )

        # Access metadata information
        print(f"Created: {metadata.created_at.isoformat()}")
        print(f"Languages: {', '.join(metadata.languages)}")
        ```

    Note:
        - All fields are optional
        - created_at must be timezone-aware if present
        - confidence_threshold must be between 0.0 and 1.0
        - languages must be valid ISO 639-1 or ISO 639-3 codes
        - extensions can contain arbitrary metadata
    """

    transcriber: Optional["Transcriber"] = None
    created_at: Optional[datetime] = None
    source: Optional["Source"] = None
    languages: Optional[List[str]] = None
    confidence_threshold: Optional[float] = None
    extensions: Optional[Dict[str, Any]] = None
    _invalid_type: Optional[str] = field(
        default=None, repr=False
    )  # Store type of invalid input

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metadata":
        """Creates a Metadata instance from a dictionary.

        Handles timestamp parsing but preserves all other data as-is without validation.

        Args:
            data (Dict[str, Any]): Dictionary containing metadata fields

        Returns:
            Metadata: A new Metadata instance

        Example:
            ```python
            data = {
                "transcriber": {"name": "AutoTranscribe", "version": "2.1.0"},
                "created_at": "2023-01-01T12:00:00Z",
                "languages": ["en", "es"]
            }
            metadata = Metadata.from_dict(data)
            ```
        """
        # For non-dict input, return instance with type info for validation
        if not isinstance(data, dict):
            return cls(_invalid_type=type(data).__name__)

        # Handle both 'Z' and '+00:00' timezone formats
        created_at_str = data.get("created_at")
        if created_at_str:
            try:
                # Handle 'Z' at the end of the timestamp
                if created_at_str.endswith("Z"):
                    created_at = datetime.fromisoformat(created_at_str[:-1]).replace(
                        tzinfo=timezone.utc
                    )
                else:
                    created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                created_at = created_at_str  # Preserve invalid timestamp for validation
        else:
            created_at = None

        return cls(
            transcriber=Transcriber.from_dict(data["transcriber"])
            if "transcriber" in data
            else None,
            created_at=created_at,
            source=Source.from_dict(data["source"]) if "source" in data else None,
            languages=_deserialize_languages(data.get("languages")),
            confidence_threshold=data.get("confidence_threshold"),
            extensions=data.get("extensions"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Metadata instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the metadata.
            Returns None if no fields are set.

        Example:
            ```python
            metadata = Metadata(
                transcriber=Transcriber(name="AutoTranscribe"),
                created_at=datetime.now(timezone.utc)
            )
            data = metadata.to_dict()
            ```

        Note:
            - created_at is converted to UTC and ISO format with 'Z' suffix
            - Empty optional fields are omitted from the output
        """
        result = {}
        if self.transcriber:
            result["transcriber"] = self.transcriber.to_dict()
        if self.created_at:
            iso_str = (
                self.created_at.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
            result["created_at"] = iso_str
        if self.source:
            result["source"] = self.source.to_dict()
        if self.languages:
            result["languages"] = self.languages
        if self.confidence_threshold is not None:
            result["confidence_threshold"] = self.confidence_threshold
        if self.extensions:
            result["extensions"] = self.extensions
        return result if result else None


@dataclass
class Speaker:
    """Speaker in the transcript.

    This class identifies and provides information about individuals
    speaking in the transcribed content.

    Attributes:
        id (str): Unique identifier for the speaker. Must follow format requirements:
            - 1 to 64 characters
            - Only letters, digits, underscores, and hyphens
            - Case sensitive
        name (Optional[str]): Display name or label for the speaker
        extensions (Dict[str, Any]): Additional metadata about the speaker

    Example:
        ```python
        # Create a speaker with basic information
        speaker = Speaker(
            id="speaker-1",
            name="John Doe"
        )

        # Create a speaker with extensions
        speaker = Speaker(
            id="SPKR_001",
            name="Jane Smith",
            extensions={
                "metadata": {
                    "age": 30,
                    "gender": "female",
                    "language": "en"
                }
            }
        )
        ```

    Note:
        - id must be unique within the transcript
        - name is optional but should be non-empty if present
        - extensions can contain arbitrary metadata
        - id format is strictly enforced
    """

    id: str
    name: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Speaker":
        """Creates a Speaker instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing speaker data with fields:
                - id (required): Speaker identifier
                - name (optional): Speaker name
                - extensions (optional): Additional metadata

        Returns:
            Speaker: A new Speaker instance

        Example:
            ```python
            data = {
                "id": "speaker-1",
                "name": "John Doe",
                "extensions": {"role": "host"}
            }
            speaker = Speaker.from_dict(data)
            ```
        """
        return cls(
            id=data["id"], name=data.get("name"), extensions=data.get("extensions", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Speaker instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary containing speaker data.
            Only includes non-None and non-empty fields.

        Example:
            ```python
            speaker = Speaker(id="speaker-1", name="John Doe")
            data = speaker.to_dict()
            # {'id': 'speaker-1', 'name': 'John Doe'}
            ```
        """
        result = {"id": self.id}
        if self.name is not None:
            result["name"] = self.name
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class Style:
    """Style for transcript formatting.

    This class defines formatting and presentation options for segments of the transcript,
    including text appearance and positioning properties.

    Attributes:
        id (str): Unique identifier for the style. Must follow format requirements:
            - 1 to 64 characters
            - Only letters, digits, underscores, and hyphens
            - Case sensitive
        text (Optional[Dict[str, Any]]): Text appearance properties:
            - color: Text color in #RRGGBB format
            - background: Background color in #RRGGBB format
            - bold: Boolean for bold text
            - italic: Boolean for italic text
            - underline: Boolean for underlined text
            - size: Percentage value (e.g., "120%")
            - opacity: Percentage value (0% to 100%)
        display (Optional[Dict[str, Any]]): Display positioning properties:
            - align: "left", "center", or "right"
            - vertical: "top", "middle", or "bottom"
            - position: {"x": "10%", "y": "90%"}
        extensions (Dict[str, Any]): Additional style properties

    Example:
        ```python
        # Create a style with text properties
        style = Style(
            id="highlight",
            text={
                "color": "#FF0000",
                "bold": True,
                "size": "120%"
            }
        )

        # Create a style with positioning
        style = Style(
            id="subtitle",
            text={"color": "#FFFFFF"},
            display={
                "align": "center",
                "vertical": "bottom",
                "position": {"x": "50%", "y": "90%"}
            }
        )
        ```

    Note:
        - id must be unique within the transcript
        - Color values must be in #RRGGBB format
        - Size and opacity must be percentage values
        - Position coordinates must be percentage values
        - Empty dictionaries are not allowed for text and display
    """

    id: str
    text: Optional[Dict[str, Any]] = None
    display: Optional[Dict[str, Any]] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Style":
        """Creates a Style instance from a dictionary.

        Args:
            data: Dictionary containing style data.

        Returns:
            A new Style instance.
        """
        return cls(
            id=data["id"],
            text=data.get("text"),
            display=data.get("display"),
            extensions=data.get("extensions", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Style instance to a dictionary.

        Returns:
            Dictionary representation of the style.
        """
        result = {"id": self.id}
        if self.text is not None:
            result["text"] = self.text
        if self.display is not None:
            result["display"] = self.display
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class Word:
    """Single word with timing and confidence information.

    This class represents an individual word in the transcript, including its timing,
    text content, confidence score, and optional metadata.

    Attributes:
        text (str): The text content of the word
        start (Optional[float]): Start time in seconds from beginning of media
        end (Optional[float]): End time in seconds from beginning of media
        is_zero_duration (Optional[bool]): Flag indicating if word has zero duration
        confidence (Optional[float]): Confidence score between 0.0 and 1.0
        extensions (Dict[str, Any]): Additional word-level metadata

    Example:
        ```python
        # Create a word with timing and confidence
        word = Word(
            text="hello",
            start=10.5,
            end=11.0,
            confidence=0.95
        )

        # Create a zero-duration word
        word = Word(
            text="[noise]",
            start=15.0,
            end=15.0,
            is_zero_duration=True
        )
        ```

    Note:
        - text must be non-empty
        - start and end must both be present or both absent
        - start must be >= 0 and end must be >= start
        - confidence must be between 0.0 and 1.0 if present
        - is_zero_duration must be True if start equals end
    """

    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    is_zero_duration: Optional[bool] = None
    confidence: Optional[float] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Word":
        """Creates a Word instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing word data with fields:
                - text (required): Word text content
                - start (optional): Start time in seconds
                - end (optional): End time in seconds
                - is_zero_duration (optional): Zero duration flag
                - confidence (optional): Confidence score
                - extensions (optional): Additional metadata

        Returns:
            Word: A new Word instance

        Example:
            ```python
            data = {
                "text": "hello",
                "start": 10.5,
                "end": 11.0,
                "confidence": 0.95
            }
            word = Word.from_dict(data)
            ```
        """
        return cls(
            start=data.get("start"),
            end=data.get("end"),
            is_zero_duration=data.get("is_zero_duration"),
            text=data["text"],
            confidence=data.get("confidence"),
            extensions=data.get("extensions", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Word instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary containing word data.
            Only includes non-None and non-empty fields.

        Example:
            ```python
            word = Word(text="hello", start=10.5, end=11.0)
            data = word.to_dict()
            # {'text': 'hello', 'start': 10.5, 'end': 11.0}
            ```
        """
        result = {"text": self.text}
        if self.start is not None:
            result["start"] = self.start
        if self.end is not None:
            result["end"] = self.end
        if self.is_zero_duration is not None:
            result["is_zero_duration"] = self.is_zero_duration
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class Segment:
    """Timed segment in the transcript with optional word-level detail.

    A segment represents a continuous portion of the transcript with its own
    timing, speaker, and optional word-level information.

    Attributes:
        text (str): The transcribed text content
        start (Optional[float]): Start time in seconds from beginning of media
        end (Optional[float]): End time in seconds from beginning of media
        is_zero_duration (Optional[bool]): Flag for zero-duration segments
        speaker_id (Optional[str]): Reference to a speaker.id
        confidence (Optional[float]): Confidence score between 0.0 and 1.0
        language (Optional[str]): ISO 639-1 or ISO 639-3 language code
        style_id (Optional[str]): Reference to a style.id
        word_timing_mode (Optional[WordTimingMode]): Word timing completeness
        words (Optional[List[Word]]): Word-level timing and text information
        extensions (Optional[Dict[str, Any]]): Additional segment metadata

    Example:
        ```python
        # Create a basic segment
        segment = Segment(
            text="Hello world",
            start=0.0,
            end=1.5,
            speaker_id="speaker-1"
        )

        # Create a segment with word timing
        segment = Segment(
            text="Hello world",
            start=0.0,
            end=1.5,
            words=[
                Word(text="Hello", start=0.0, end=0.8),
                Word(text="world", start=0.9, end=1.5)
            ],
            word_timing_mode=WordTimingMode.COMPLETE
        )
        ```

    Note:
        - Segments must not overlap with each other
        - start and end must both be present or both absent
        - start must be >= 0 and end must be >= start
        - confidence must be between 0.0 and 1.0 if present
        - speaker_id must reference a valid speaker
        - style_id must reference a valid style
        - language must be a valid ISO code if present
    """

    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    is_zero_duration: Optional[bool] = None
    speaker_id: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    style_id: Optional[str] = None
    word_timing_mode: Optional[Union[WordTimingMode, str]] = None
    words: Optional[List["Word"]] = None
    extensions: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Segment":
        """Creates a Segment instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing segment data with fields:
                - text (required): Segment text content
                - start (optional): Start time in seconds
                - end (optional): End time in seconds
                - is_zero_duration (optional): Zero duration flag
                - speaker_id (optional): Reference to speaker
                - confidence (optional): Confidence score
                - language (optional): Language code
                - style_id (optional): Reference to style
                - word_timing_mode (optional): Word timing mode
                - words (optional): List of word data
                - extensions (optional): Additional metadata

        Returns:
            Segment: A new Segment instance

        Example:
            ```python
            data = {
                "text": "Hello world",
                "start": 0.0,
                "end": 1.5,
                "speaker_id": "speaker-1"
            }
            segment = Segment.from_dict(data)
            ```
        """

        if not isinstance(data, dict):
            data = {}  # Convert non-dict input to empty dict to preserve data

        return cls(
            start=data.get("start"),
            end=data.get("end"),
            is_zero_duration=data.get("is_zero_duration"),
            text=data.get("text", ""),  # Provide default for required field
            speaker_id=data.get("speaker_id"),
            confidence=data.get("confidence"),
            language=_deserialize_language(data.get("language")),
            style_id=data.get("style_id"),
            word_timing_mode=WordTimingMode(data["word_timing_mode"])
            if "word_timing_mode" in data
            else None,
            words=[Word.from_dict(w) for w in data["words"]]
            if "words" in data
            else None,
            extensions=data.get("extensions"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Segment instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary containing segment data.
            Only includes non-None and non-empty fields.

        Example:
            ```python
            segment = Segment(
                text="Hello world",
                start=0.0,
                end=1.5,
                speaker_id="speaker-1"
            )
            data = segment.to_dict()
            ```
        """
        result = {"text": self.text}
        if self.start is not None:
            result["start"] = self.start
        if self.end is not None:
            result["end"] = self.end
        if self.is_zero_duration is not None:
            result["is_zero_duration"] = self.is_zero_duration
        if self.speaker_id is not None:
            result["speaker_id"] = self.speaker_id
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.language is not None:
            result["language"] = self.language
        if self.style_id is not None:
            result["style_id"] = self.style_id
        if self.word_timing_mode is not None:
            # Handle both string and enum values
            result["word_timing_mode"] = (
                self.word_timing_mode.value
                if isinstance(self.word_timing_mode, WordTimingMode)
                else self.word_timing_mode
            )
        if self.words is not None:
            result["words"] = [w.to_dict() for w in self.words]
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class Transcript:
    """Main content of the transcription.

    This class contains the core transcription data, including speakers,
    segments, and optional style information. It represents the complete
    transcribed content with timing and formatting.

    Attributes:
        speakers (List[Speaker]): List of speakers in the transcript.
            Each speaker has a unique ID and optional metadata.
            Empty list indicates speaker identification was attempted but found none.
            Non-empty list indicates speakers were found.
        segments (List[Segment]): List of transcript segments.
            Segments contain the actual transcribed content with timing.
            Must not be empty.
        styles (Optional[List[Style]]): Optional list of text formatting styles.
            Styles can be referenced by segments for formatting. Can be:
            - None: Style processing was not attempted
            - Empty list: Style processing performed but no styles defined
            - List of styles: One or more styles defined

    Example:
        ```python
        # Create a basic transcript with one speaker and segment
        transcript = Transcript(
            speakers=[
                Speaker(id="S1", name="John")
            ],
            segments=[
                Segment(
                    text="Hello world",
                    start=0.0,
                    end=1.5,
                    speaker_id="S1"
                )
            ]
        )

        # Create a transcript where speaker identification found none
        transcript = Transcript(
            speakers=[],  # Empty list indicates attempted but none found
            segments=[
                Segment(text="Hello world")
            ]
        )

        # Create a basic transcript (implicitly attempts speaker identification)
        transcript = Transcript(
            segments=[
                Segment(text="Hello world")
            ]
        )

        # Create a transcript with multiple speakers and styles
        transcript = Transcript(
            speakers=[
                Speaker(id="S1", name="John"),
                Speaker(id="S2", name="Jane")
            ],
            segments=[
                Segment(
                    text="How are you?",
                    start=0.0,
                    end=1.5,
                    speaker_id="S1",
                    style_id="question"
                ),
                Segment(
                    text="I'm fine, thanks!",
                    start=1.6,
                    end=3.0,
                    speaker_id="S2"
                )
            ],
            styles=[
                Style(
                    id="question",
                    text={"color": "#0000FF"}
                )
            ]
        )
        ```

    Note:
        - segments list must not be empty
        - speakers list will be empty if none found, non-empty if speakers found
        - styles can be:
          - None: style processing not attempted
          - Empty list: styles were processed but none defined
          - List with items: styles were defined
        - segments must be ordered by time and must not overlap
        - all IDs must be unique within their respective lists
        - if speakers/styles are included, references to them must be valid
    """

    segments: List[Segment] = field(default_factory=list)
    speakers: List[Speaker] = field(default_factory=list)
    styles: Optional[List[Style]] = None
    _invalid_segments_type: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transcript":
        """Creates a Transcript instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing transcript data with fields:
                - speakers (optional): List of speaker data. Treated as empty list
                  if key missing (indicating speaker identification attempted but
                  none found)
                - segments (required): List of segment data
                - styles (optional): List of style data. If key missing, treated
                  as "not attempted". If present but empty, treated as "none defined"

        Returns:
            Transcript: A new Transcript instance

        Example:
            ```python
            # Transcript with speakers found
            data = {
                "speakers": [{"id": "S1", "name": "John"}],
                "segments": [{
                    "text": "Hello",
                    "start": 0.0,
                    "end": 1.0,
                    "speaker_id": "S1"
                }]
            }

            # Transcript where speaker identification found none
            data = {
                "speakers": [],  # Empty list = none found
                "segments": [{
                    "text": "Hello",
                    "start": 0.0,
                    "end": 1.0
                }]
            }

            # Basic transcript (implicitly attempts speaker identification)
            data = {
                "segments": [{
                    "text": "Hello",
                    "start": 0.0,
                    "end": 1.0
                }]
            }

            transcript = Transcript.from_dict(data)
            ```
        """

        segments = data.get("segments", [])
        if not isinstance(segments, list):
            return cls(segments=[], _invalid_segments_type=type(segments).__name__)

        return cls(
            segments=[Segment.from_dict(s) for s in segments],
            speakers=[Speaker.from_dict(s) for s in data.get("speakers", [])],
            styles=[Style.from_dict(s) for s in data["styles"]]
            if "styles" in data
            else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Transcript instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary containing transcript data.
            Always includes segments and speakers (even if empty).
            Styles included only if style processing was attempted.

        Example:
            ```python
            # Basic transcript (implicitly attempted speaker identification)
            transcript = Transcript(
                segments=[Segment(text="Hello")]
            )
            # Result includes empty speakers list:
            # {"speakers": [], "segments": [...]}

            # Transcript with speakers found
            transcript = Transcript(
                speakers=[Speaker(id="S1", name="John")],
                segments=[
                    Segment(text="Hello", start=0.0, end=1.0, speaker_id="S1")
                ]
            )
            # Result includes non-empty speakers list:
            # {"speakers": [{"id": "S1", "name": "John"}], "segments": [...]}
            ```
        """
        result = {
            "segments": [s.to_dict() for s in self.segments],
            "speakers": [s.to_dict() for s in self.speakers],
        }

        # Only include styles if processing was attempted
        if self.styles is not None:
            result["styles"] = [s.to_dict() for s in self.styles]

        return result
