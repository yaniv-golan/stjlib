"""
STJLib: Standard Transcription JSON Format Handler

A comprehensive implementation of the Standard Transcription JSON (STJ) format
for representing transcribed audio and video data.

Module Organization:
    * Type definitions and type hints
    * Exception classes for error handling
    * Main STJ handler class
    * Helper functions and utilities

Key Features:
    * Complete STJ format implementation
    * Load and save STJ files with robust error handling
    * Comprehensive validation against specification
    * Type-safe data structures
    * Extensible architecture
    * Full support for all STJ components:
        - Metadata and source information
        - Transcript content and timing
        - Speaker identification
        - Word-level timing and confidence
        - Text formatting and styles
        - Custom extensions

Example:
    ```python
    from stjlib import StandardTranscriptionJSON

    # Create new transcript
    stj = StandardTranscriptionJSON(
        metadata=Metadata(
            transcriber=Transcriber(name="MyTranscriber", version="1.0")
        )
    )

    # Adding content
    stj.add_speaker("s1", "John")
    stj.add_segment(
        text="Hello world",
        start=0.0,
        end=1.5,
        speaker_id="s1"
    )

    # Loading existing data
    existing = StandardTranscriptionJSON.from_file("transcript.stjson")
    ```

Note:
    For detailed format information, see: https://github.com/yaniv-golan/STJ

Format Structure:
    The STJ format wraps content in a root "stj" object:
    {
        "stj": {
            "version": "0.6.0",
            "metadata": {
                "transcriber": {"name": str, "version": str},
                "created_at": str,  # ISO 8601 UTC timestamp
                ...
            },
            "transcript": {
                "segments": [...],
                "speakers": [...],
                ...
            }
        }
    }
"""

# Standard library imports
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Iterator

# Local imports
from .core.data_classes import (
    STJ,
    Metadata,
    Transcript,
    Segment,
    Speaker,
)
from .validation import (
    ValidationIssue,
    validate_stj,
)

# Type definitions
ValidationIssues = List[ValidationIssue]  # Type for validation result collections
STJDict = Dict[str, Any]  # Type for STJ format dictionaries (with 'stj' root)
SpeakerId = str  # Type for speaker identifiers used throughout the API
_InternalDict = Dict[str, Any]  # Type for internal STJ structure (without 'stj' root)

# Type usage examples:
# -----------------------------
# STJDict (format with root):
#     {"stj": {"version": "0.6.0", ...}}
# _InternalDict: {"version": "0.6.0", ...}


class STJError(Exception):
    """Base class for exceptions in the STJ module.

    This class serves as the parent class for all STJ-specific exceptions,
    allowing for specific error handling of STJ-related issues.

    Example:
        ```python
        try:
            stj = StandardTranscriptionJSON.from_file("invalid.json")
        except STJError as e:
            print(f"STJ error occurred: {e}")
        ```
    """

    pass


class ValidationError(STJError):
    """Exception raised when STJ validation fails.

    This exception includes a list of validation issues that describe
    the specific problems found during validation.

    Attributes:
        issues (List[ValidationIssue]): List of validation issues found

    Example:
        ```python
        try:
            stj = StandardTranscriptionJSON.from_file(
                "transcript.json",
                validate=True
            )
        except ValidationError as e:
            print("Validation failed:")
            for issue in e.issues:
                print(f"{issue.severity}: {issue}")
        ```
    """

    def __init__(self, issues: List[ValidationIssue]):
        self.issues = issues
        super().__init__(self.__str__())

    def __str__(self) -> str:
        """Returns a formatted string of all validation issues.

        Returns:
            str: Multi-line string containing all validation issues
        """
        return "Validation failed with the following issues:\n" + "\n".join(
            str(issue) for issue in self.issues
        )


class StandardTranscriptionJSON:
    """Handler for Standard Transcription JSON (STJ) format.

    This class implements version 0.6.0 of the STJ specification, providing
    a high-level interface for working with STJ documents.

    Format Structure:
        The STJ format wraps content in a root "stj" object:
        {
            "stj": {
                "version": "0.6.0",
                "metadata": {
                    "transcriber": {"name": str, "version": str},
                    "created_at": str,  # ISO 8601 UTC timestamp
                    ...
                },
                "transcript": {
                    "segments": [...],
                    "speakers": [...],
                    ...
                }
            }
        }

    Features:
        - Create new transcripts
        - Load existing STJ files
        - Add/modify transcript content
        - Validate STJ data
        - Save transcripts to files

    Example:
        >>> stj = StandardTranscriptionJSON(
        ...     metadata=Metadata(
        ...         transcriber=Transcriber(name="MyTranscriber", version="1.0")
        ...     )
        ... )
        >>> stj.add_speaker("s1", "John")
        >>> stj.add_segment(text="Hello", start=0.0, end=1.5, speaker_id="s1")

    Note:
        The STJ format is a standardized way to represent transcribed audio/video
        content with support for timing, speakers, and metadata.
    """

    _SUPPORTED_VERSION = "0.6.0"

    #
    # Core interface
    #
    def __init__(
        self,
        metadata: Optional[Metadata] = None,
        transcript: Optional[Transcript] = None,
        validate: bool = False,
    ):
        """Create a new StandardTranscriptionJSON instance.

        Args:
            metadata: Optional metadata about the transcription. If None, metadata will be omitted entirely.
            transcript: Optional transcript content. If None, creates empty transcript.
            validate: Whether to validate the instance after creation

        Raises:
            ValidationError: If validate=True and the instance is invalid
        """
        self._stj = STJ(
            version=self._SUPPORTED_VERSION,
            metadata=metadata,  # Don't create default metadata when none is provided
            transcript=transcript or Transcript(segments=[]),
        )
        if validate:
            self.validate()

    def validate(self, raise_exception: bool = True) -> Optional[ValidationIssues]:
        """Validates the STJ data according to specification requirements.

        Args:
            raise_exception: If True, raises ValidationError for any issues.

        Returns:
            Optional[ValidationIssues]: List of validation issues if found, None if valid.

        Raises:
            ValidationError: If validation fails and raise_exception is True.
        """
        issues = validate_stj(self._stj)
        if issues and raise_exception:
            raise ValidationError(issues)
        return issues if issues else None

    #
    # File operations
    #
    @classmethod
    def from_file(
        cls, filename: str, validate: bool = False
    ) -> "StandardTranscriptionJSON":
        """Creates a StandardTranscriptionJSON instance from a JSON file.

        Args:
            filename: Path to the JSON file to load
            validate: Whether to validate the loaded data

        Returns:
            StandardTranscriptionJSON: New instance with loaded data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If validation fails or data structure is invalid
        """
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return cls.from_dict(data, validate=validate)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {filename}") from e
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"JSON decode error: {e.msg}", e.doc, e.pos)

    @classmethod
    def from_dict(
        cls, data: STJDict, validate: bool = False
    ) -> "StandardTranscriptionJSON":
        """Creates a StandardTranscriptionJSON instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing STJ data
            validate (bool): Whether to validate the data (defaults to False)

        Returns:
            StandardTranscriptionJSON: A new StandardTranscriptionJSON instance

        Raises:
            ValidationError: If validate=True and the data fails validation
        """
        # Create the STJ object
        stj = STJ.from_dict(data)
        instance = cls.create_from_stj(stj)

        # Validate if requested
        if validate:
            instance.validate()

        return instance

    def to_file(self, filename: str) -> None:
        """Saves the STJ instance to a JSON file.

        Args:
            filename: Path where the JSON file should be written

        Raises:
            IOError: If there's an error writing to the file
        """
        data = self.to_dict()
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            raise IOError(f"Error writing to file {filename}: {e}")

    def to_dict(self) -> STJDict:
        """Convert to STJ format dictionary.

        Returns:
            STJDict: Dictionary in the STJ format with structure:
            {
                "stj": {
                    "version": str,
                    "metadata": Optional[Dict[str, Any]],
                    "transcript": Dict[str, Any]
                }
            }
        """
        raw_dict: _InternalDict = {
            "version": self._stj.version,
            "transcript": self._stj.transcript.to_dict(),
        }
        if self._stj.metadata is not None:
            raw_dict["metadata"] = self._stj.metadata.to_dict()

        return {"stj": raw_dict}

    #
    # Properties
    #
    @property
    def metadata(self) -> Optional[Metadata]:
        """Access to the STJ metadata.

        Returns:
            Optional[Metadata]: The metadata object or None if not present

        Raises:
            ValueError: If STJ instance is not properly initialized
        """
        if self._stj is None:
            raise ValueError("STJ instance not properly initialized")
        return self._stj.metadata

    @property
    def transcript(self) -> Transcript:
        """Access to the STJ transcript.

        Returns:
            Transcript: The transcript object containing all content

        Raises:
            ValueError: If STJ instance is not properly initialized
        """
        if self._stj is None:
            raise ValueError("STJ instance not properly initialized")
        return self._stj.transcript

    #
    # Content manipulation
    #
    def add_segment(
        self,
        text: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
        *,
        speaker_id: Optional[SpeakerId] = None,
        language: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Add a new transcript segment.

        Args:
            text: The transcribed text
            start: Start time in seconds
            end: End time in seconds
            speaker_id: Optional ID of the speaker
            language: Optional language code
            **kwargs: Additional segment properties

        Raises:
            ValueError: If text is empty or if end time is before start time
        """
        if not text or not text.strip():
            raise ValueError("Segment text cannot be empty or contain only whitespace")

        if start is not None and end is not None:
            if end < start:
                raise ValueError(
                    "Segment end time must be greater than or equal to start time"
                )

        segment = Segment(
            text=text,
            start=start,
            end=end,
            speaker_id=speaker_id,
            language=language,
            **kwargs,
        )
        self._stj.transcript.segments.append(segment)

    def add_speaker(self, id: SpeakerId, name: Optional[str] = None) -> None:
        """Add a new speaker.

        Args:
            id: Unique speaker identifier
            name: Optional display name for the speaker

        Raises:
            ValueError: If id is empty or if speaker with same id already exists
        """
        if not id or not id.strip():
            raise ValueError("Speaker ID cannot be empty or contain only whitespace")

        # Check for duplicate speaker id
        existing_speakers = [s.id for s in self._stj.transcript.speakers]
        if id in existing_speakers:
            raise ValueError(f"Speaker with id '{id}' already exists")

        speaker = Speaker(id=id, name=name)
        self._stj.transcript.speakers.append(speaker)

    def clear_segments(self) -> None:
        """Remove all segments from the transcript."""
        self._stj.transcript.segments = []

    #
    # Query methods
    #
    def get_speaker(self, speaker_id: SpeakerId) -> Optional[Speaker]:
        """Get speaker by ID.

        Args:
            speaker_id: ID of the speaker to find

        Returns:
            Optional[Speaker]: Speaker if found, None if not found

        Raises:
            ValueError: If speaker_id is empty or whitespace
        """
        if not speaker_id or not speaker_id.strip():
            raise ValueError("Speaker ID cannot be empty or contain only whitespace")

        return next(
            (s for s in self._stj.transcript.speakers if s.id == speaker_id), None
        )

    def get_segments_by_speaker(self, speaker_id: SpeakerId) -> List[Segment]:
        """Get all segments for a specific speaker.

        Args:
            speaker_id: ID of the speaker to find segments for

        Returns:
            List[Segment]: List of segments with matching speaker_id. Empty list if none found.

        Raises:
            ValueError: If speaker_id is empty or whitespace
        """
        if not speaker_id or not speaker_id.strip():
            raise ValueError("Speaker ID cannot be empty or contain only whitespace")

        return [s for s in self._stj.transcript.segments if s.speaker_id == speaker_id]

    #
    # Internal helpers
    #
    @staticmethod
    def _create_default_metadata() -> Metadata:
        """Create default metadata with current timestamp.

        Returns:
            Metadata: A new metadata object with current UTC timestamp
        """
        return Metadata(created_at=datetime.now(timezone.utc))

    @classmethod
    def create_from_stj(cls, stj: STJ) -> "StandardTranscriptionJSON":
        """Internal method to create instance from STJ object.

        This method is used internally by:
        - from_dict()
        - from_file()

        For new instances, use the constructor.

        Args:
            stj: An existing STJ object

        Returns:
            StandardTranscriptionJSON: New instance wrapping the STJ object

        Note:
            This is an internal method and should not be used directly.
            Use the constructor for creating new instances.
        """
        instance = cls.__new__(cls)
        instance._stj = stj
        return instance
