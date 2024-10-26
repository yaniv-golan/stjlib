"""STJLib core data classes for Standard Transcription JSON Format.

This module provides the core data structures that represent STJ format components.
Each class corresponds to a specific part of the STJ structure and includes
serialization/deserialization capabilities.

The module implements:
    * Metadata classes (Transcriber, Source)
    * Content classes (Transcript, Segment, Word)
    * Formatting classes (Speaker, Style)
    * Language handling utilities

Note:
    All classes use dataclasses for clean attribute management and include
    from_dict/to_dict methods for JSON serialization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from iso639.exceptions import InvalidLanguageValue
from .enums import WordTimingMode, WordDuration


def _deserialize_language(code: Optional[str]) -> Optional[str]:
    """Deserializes a single language code without raising exceptions.

    Args:
        code: Language code to deserialize.

    Returns:
        Original language code or None if None was provided.

    Note:
        This function preserves the original code for validation,
        allowing validation to happen at a later stage.
    """
    return code


def _deserialize_languages(languages_data: Optional[List[str]]) -> Optional[List[str]]:
    """Deserializes a list of language codes.

    Args:
        languages_data: List of language codes to deserialize.

    Returns:
        List of language codes or None if no languages provided.

    Note:
        This function preserves original codes for validation,
        allowing validation to happen at a later stage.
    """
    if not languages_data:
        return None
    return languages_data


@dataclass
class Transcriber:
    """Metadata about the transcription system or service.

    This class stores information about the system that created the transcription,
    including its name and version.

    Args:
        name: Name of the transcription system.
        version: Version of the transcription system.

    Example:
        >>> transcriber = Transcriber(name="AutoTranscribe", version="2.1.0")
        >>> print(f"Transcribed by {transcriber.name} v{transcriber.version}")
        Transcribed by AutoTranscribe v2.1.0
    """

    name: str
    version: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transcriber":
        """Creates a Transcriber instance from a dictionary.

        Args:
            data: Dictionary containing transcriber data.

        Returns:
            A new Transcriber instance.
        """
        return cls(name=data.get("name", ""), version=data.get("version", ""))

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Transcriber instance to a dictionary.

        Returns:
            Dictionary representation of the transcriber.
        """
        return {"name": self.name, "version": self.version}


@dataclass
class Source:
    """Source metadata for the transcription.

    This class contains information about the original media file that was
    transcribed, including its location, duration, and languages.

    Args:
        uri: URI or path to the source media file.
        duration: Duration of the source media in seconds.
        languages: List of languages present in the source media.
        extensions: Additional metadata about the source.

    Example:
        >>> source = Source(
        ...     uri="https://example.com/audio.mp3",
        ...     duration=300.5,
        ...     languages=["en", "es"],
        ...     extensions={"bitrate": "128kbps"}
        ... )
    """

    uri: Optional[str] = None
    duration: Optional[float] = None
    languages: Optional[List[str]] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        """Creates a Source instance from a dictionary.

        Args:
            data: Dictionary containing source data.

        Returns:
            A new Source instance.
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
            Dictionary representation of the source.
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

    Args:
        transcriber: Information about the transcription system used.
        created_at: Timestamp of when the transcription was created.
        version: STJ specification version.
        source: Information about the source media.
        languages: List of languages used in the transcription.
        confidence_threshold: Minimum confidence score for included words.
        extensions: Additional metadata key-value pairs.

    Example:
        >>> from datetime import datetime, timezone
        >>> metadata = Metadata(
        ...     transcriber=Transcriber(name="AutoTranscribe", version="2.1.0"),
        ...     created_at=datetime.now(timezone.utc),
        ...     version="0.5.0",
        ...     languages=["en", "es"],
        ...     confidence_threshold=0.8
        ... )
    """

    transcriber: Transcriber
    created_at: datetime
    version: str
    source: Optional[Source] = None
    languages: Optional[List[str]] = None
    confidence_threshold: Optional[float] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metadata":
        """Creates a Metadata instance from a dictionary.

        Args:
            data: Dictionary containing metadata.

        Returns:
            A new Metadata instance.
        """
        # Handle both 'Z' and '+00:00' timezone formats
        created_at_str = data["created_at"]
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            # If direct parsing fails, try converting 'Z' to '+00:00'
            if created_at_str.endswith("Z"):
                created_at = datetime.fromisoformat(created_at_str[:-1] + "+00:00")
            else:
                raise

        return cls(
            transcriber=Transcriber.from_dict(data.get("transcriber", {})),
            created_at=created_at,
            version=data["version"],
            source=Source.from_dict(data["source"]) if "source" in data else None,
            languages=_deserialize_languages(data.get("languages")),
            confidence_threshold=data.get("confidence_threshold"),
            extensions=data.get("extensions", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Metadata instance to a dictionary.

        Returns:
            Dictionary representation of the metadata.
        """
        result = {
            "transcriber": self.transcriber.to_dict(),
            "version": self.version,
            # Convert UTC timezone to 'Z' format
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "extensions": self.extensions or {},
        }

        if self.languages:
            result["languages"] = self.languages
        if self.confidence_threshold is not None:
            result["confidence_threshold"] = self.confidence_threshold
        return result


@dataclass
class Speaker:
    """Speaker in the transcript.

    This class identifies and provides information about individuals
    speaking in the transcribed content.

    Args:
        id: Unique identifier for the speaker.
        name: Name or label for the speaker.
        extensions: Additional metadata about the speaker.

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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Speaker":
        """Creates a Speaker instance from a dictionary.

        Args:
            data: Dictionary containing speaker data.

        Returns:
            A new Speaker instance.
        """
        return cls(
            id=data["id"], name=data.get("name"), extensions=data.get("extensions", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Speaker instance to a dictionary.

        Returns:
            Dictionary representation of the speaker.
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

    This class defines formatting and presentation options for
    segments of the transcript.

    Args:
        id: Unique identifier for the style.
        text: Text appearance properties.
        display: Display positioning properties.
        extensions: Additional style properties.

    Example:
        >>> style = Style(
        ...     id="emphasis",
        ...     text={"bold": True, "color": "#FF0000"},
        ...     display={"align": "center"},
        ...     extensions={"animation": "fade"}
        ... )
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

    This class stores detailed information about individual words
    within a transcript segment.

    Args:
        start: Start time of the word in seconds.
        end: End time of the word in seconds.
        text: The text content of the word.
        confidence: Confidence score for the word recognition.
        extensions: Additional word-level metadata.

    Note:
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Word":
        """Creates a Word instance from a dictionary.

        Args:
            data: Dictionary containing word data.

        Returns:
            A new Word instance.
        """
        return cls(
            start=data["start"],
            end=data["end"],
            text=data["text"],
            confidence=data.get("confidence"),
            extensions=data.get("extensions", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Word instance to a dictionary.

        Returns:
            Dictionary representation of the word.
        """
        result = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }
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

    Args:
        start: Start time in seconds.
        end: End time in seconds.
        text: The transcribed text content.
        speaker_id: Reference to a speaker.id.
        confidence: Confidence score for the segment.
        language: ISO 639 language code.
        style_id: Reference to a style.id.
        words: Word-level timing and text information.
        word_timing_mode: Completeness of word timing.
        is_zero_duration: Whether the segment is zero-duration.
        extensions: Additional segment metadata.

    Note:
        Segments must not overlap with each other and must contain
        valid timing information.
    """

    start: float
    end: float
    text: str
    speaker_id: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    style_id: Optional[str] = None
    words: Optional[List[Word]] = None
    word_timing_mode: Optional[WordTimingMode] = None
    is_zero_duration: bool = field(default=False)
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Segment":
        """Creates a Segment instance from a dictionary.

        Args:
            data: Dictionary containing segment data.

        Returns:
            A new Segment instance.
        """
        return cls(
            start=data["start"],
            end=data["end"],
            text=data["text"],
            speaker_id=data.get("speaker_id"),
            confidence=data.get("confidence"),
            language=_deserialize_language(data.get("language")),
            style_id=data.get("style_id"),
            words=[Word.from_dict(w) for w in data["words"]]
            if "words" in data
            else None,
            word_timing_mode=WordTimingMode(data["word_timing_mode"])
            if "word_timing_mode" in data
            else None,
            is_zero_duration=data.get("is_zero_duration", False),
            extensions=data.get("extensions", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Segment instance to a dictionary.

        Returns:
            Dictionary representation of the segment.
        """
        result = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }
        if self.speaker_id is not None:
            result["speaker_id"] = self.speaker_id
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.language is not None:
            result["language"] = self.language
        if self.style_id is not None:
            result["style_id"] = self.style_id
        if self.words is not None:
            result["words"] = [w.to_dict() for w in self.words]
        if self.word_timing_mode is not None:
            result["word_timing_mode"] = self.word_timing_mode.value
        if self.is_zero_duration:
            result["is_zero_duration"] = self.is_zero_duration
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class Transcript:
    """Main content of the transcription.

    This class contains the core transcription data, including speakers,
    segments, and optional style information.

    Args:
        speakers: List of speakers in the transcript.
        segments: List of transcript segments.
        styles: List of styles used in the transcript.

    Example:
        >>> transcript = Transcript(
        ...     speakers=[
        ...         Speaker(id="S1", name="John"),
        ...         Speaker(id="S2", name="Jane")
        ...     ],
        ...     segments=[
        ...         Segment(start=0.0, end=5.0, text="Hello", speaker_id="S1"),
        ...         Segment(start=5.1, end=8.5, text="Hi", speaker_id="S2")
        ...     ]
        ... )
    """

    speakers: List[Speaker] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    styles: Optional[List[Style]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transcript":
        """Creates a Transcript instance from a dictionary.

        Args:
            data: Dictionary containing transcript data.

        Returns:
            A new Transcript instance.
        """
        return cls(
            speakers=[Speaker.from_dict(s) for s in data.get("speakers", [])],
            segments=[Segment.from_dict(s) for s in data.get("segments", [])],
            styles=[Style.from_dict(s) for s in data["styles"]]
            if "styles" in data
            else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Transcript instance to a dictionary.

        Returns:
            Dictionary representation of the transcript.
        """
        result = {
            "speakers": [s.to_dict() for s in self.speakers],
            "segments": [s.to_dict() for s in self.segments],
        }
        if self.styles is not None:
            result["styles"] = [s.to_dict() for s in self.styles]
        return result
