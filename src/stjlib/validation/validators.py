"""
STJLib validation module for Standard Transcription JSON Format.

This module provides comprehensive validation functionality for STJ data structures,
ensuring they conform to the official STJ specification requirements.

The module includes validators for:
    * Data types and required fields
    * Time formats and ranges
    * Language codes
    * Speaker and style identifiers
    * Text content and consistency
    * Extensions and custom properties

Note:
    All validation functions return a list of ValidationIssue objects that describe
    any problems found during validation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
import re
from typing import Any, Dict, List, Optional, Union, Type, Callable
from urllib.parse import urlparse
from enum import Enum, auto
import math

from iso639 import Lang
import iso639
from iso639.exceptions import InvalidLanguageValue

from ..core.data_classes import (
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Style,
    Source,
)
from ..core.enums import WordTimingMode, WordDuration

# Validation constants
MAX_TIME_VALUE = 999999.999
MAX_DECIMAL_PLACES = 3
MAX_SPEAKER_ID_LENGTH = 64

# Regular expression patterns
SPEAKER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
NAMESPACE_PATTERN = r"^[a-z0-9\-]+$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
TEXT_NORMALIZATION_PATTERN = r"[^\w\s]"
URI_INVALID_CHARS_PATTERN = r"[^\w\-\.~:/?#\[\]@!$&\'()*+,;=%]"

# Reserved namespaces
RESERVED_NAMESPACES = frozenset(
    {"stj", "webvtt", "ttml", "ssa", "srt", "dfxp", "smptett"}
)

# Update ALLOWED_URI_SCHEMES to be recommended schemes
RECOMMENDED_URI_SCHEMES = frozenset({"http", "https", "file"})

# Style validation constants
VALID_TEXT_PROPERTIES = frozenset(
    {"color", "background", "bold", "italic", "underline", "size", "opacity"}
)

VALID_ALIGN_VALUES = frozenset({"left", "center", "right"})

VALID_VERTICAL_VALUES = frozenset({"top", "middle", "bottom"})


class WordTimingStatus(Enum):
    """Enum for word timing validation status."""

    COMPLETE = auto()
    NONE = auto()
    INVALID = auto()


@dataclass
class ValidationIssue:
    """A validation issue found during STJ data validation.

    This class represents a specific validation problem, including both a descriptive
    message and the location where the issue was found in the STJ structure.

    Args:
        message: Description of the validation issue.
        location: Path to the problematic field in the STJ structure.

    Attributes:
        message: Descriptive message explaining the validation issue.
        location: Location in the STJ structure where the issue was found.
    """

    message: str
    location: Optional[str] = None

    def __str__(self) -> str:
        """Returns a formatted string representation of the validation issue.

        Returns:
            A string combining the location (if any) and the message.
        """
        if self.location:
            return f"{self.location}: {self.message}"
        else:
            return self.message


def validate_extensions(
    extensions: Dict[str, Any],
    location: str,
    parent_namespaces: Optional[List[str]] = None,
    depth: int = 0,
) -> List[ValidationIssue]:
    """Validates extension fields according to STJ specification.

    Args:
        extensions: Dictionary of extension data to validate.
        location: Path to the extensions field in the STJ structure.
        parent_namespaces: List of parent namespace names for circular reference detection.
        depth: Current recursion depth for nested extensions.

    Returns:
        List of validation issues found.

    Note:
        The STJ specification requires that:
        * Extensions must be an object/dictionary
        * Namespaces must be non-empty strings
        * Namespace values must be objects/dictionaries
        * No circular references are allowed
    """
    issues = []
    parent_namespaces = parent_namespaces or []

    # Type checking handled by validate_types()
    if extensions is None:
        issues.append(
            ValidationIssue(message="Extensions must be an object", location=location)
        )
        return issues

    for namespace, value in extensions.items():
        current_namespace_path = parent_namespaces + [namespace]

        # Check for circular references
        if namespace in parent_namespaces:
            issues.append(
                ValidationIssue(
                    message=f"Circular reference detected in extensions: {' -> '.join(current_namespace_path)}",
                    location=f"{location}.{namespace}",
                )
            )
            continue

        # Validate namespace is a non-empty string
        if not isinstance(namespace, str) or not namespace:
            issues.append(
                ValidationIssue(
                    message=f"Invalid extension namespace '{namespace}'. Namespaces must be non-empty strings.",
                    location=f"{location}.{namespace}",
                )
            )

        # Check reserved namespaces
        if namespace in RESERVED_NAMESPACES:
            issues.append(
                ValidationIssue(
                    message=f"Reserved namespace '{namespace}' cannot be used",
                    location=f"{location}.{namespace}",
                )
            )

        # Value must be an object/dictionary
        if not isinstance(value, dict):
            issues.append(
                ValidationIssue(
                    message=f"Extension value for namespace '{namespace}' must be an object",
                    location=f"{location}.{namespace}",
                )
            )
            continue

        # Recursively validate nested extensions if present
        if "extensions" in value:
            nested_extensions = value["extensions"]
            nested_location = f"{location}.{namespace}.extensions"
            issues.extend(
                validate_extensions(
                    nested_extensions,
                    nested_location,
                    current_namespace_path,
                    depth + 1,
                )
            )

    return issues


def validate_metadata(metadata: Metadata) -> List[ValidationIssue]:
    """Validates metadata according to STJ specification requirements.

    Args:
        metadata: Metadata object to validate.

    Returns:
        List of validation issues found.

    Note:
        Validates:
        * Required fields (transcriber, created_at)
        * Version format
        * Confidence threshold range
        * Source information
        * Language codes
    """
    issues = []

    # Validate transcriber fields independently
    if not metadata.transcriber:
        issues.append(
            ValidationIssue(
                message="Missing 'transcriber' field", location="metadata.transcriber"
            )
        )

    if metadata.transcriber:
        if not metadata.transcriber.name or metadata.transcriber.name.isspace():
            issues.append(
                ValidationIssue(
                    message="'transcriber.name' must be a non-empty string and not just whitespace",
                    location="metadata.transcriber.name",
                )
            )

        if not metadata.transcriber.version or metadata.transcriber.version.isspace():
            issues.append(
                ValidationIssue(
                    message="'transcriber.version' must be a non-empty string and not just whitespace",
                    location="metadata.transcriber.version",
                )
            )

    if not metadata.created_at:
        issues.append(
            ValidationIssue(
                message="Missing 'created_at' field",
                location="metadata.created_at",
            )
        )

    # Validate version
    issues.extend(validate_version(metadata.version))

    # Validate confidence threshold
    if metadata.confidence_threshold is not None:
        if not (0.0 <= metadata.confidence_threshold <= 1.0):
            issues.append(
                ValidationIssue(
                    message=f"confidence_threshold {metadata.confidence_threshold} out of range [0.0, 1.0]",
                    location="metadata.confidence_threshold",
                )
            )

    # Validate source if present
    if metadata.source:
        if metadata.source.uri:
            issues.extend(validate_uri(metadata.source.uri, "metadata.source.uri"))
        if metadata.source.duration is not None and metadata.source.duration < 0:
            issues.append(
                ValidationIssue(
                    message="source.duration must be non-negative",
                    location="metadata.source.duration",
                )
            )
        if metadata.source.languages:
            issues.extend(
                _validate_language_code_list(
                    metadata.source.languages, "metadata.source.languages"
                )
            )
        if metadata.source.extensions:
            issues.extend(
                validate_extensions(
                    metadata.source.extensions, "metadata.source.extensions"
                )
            )

    # Validate metadata languages if present
    if metadata.languages:
        issues.extend(
            _validate_language_code_list(metadata.languages, "metadata.languages")
        )

    # Validate metadata extensions
    if metadata.extensions:
        issues.extend(validate_extensions(metadata.extensions, "metadata.extensions"))

    return issues


def validate_version(version: str) -> List[ValidationIssue]:
    """Validate STJ version format."""
    issues = []

    if not version or not isinstance(version, str):
        issues.append(
            ValidationIssue(
                message="Missing or invalid 'metadata.version'. It must be a non-empty string.",
                location="metadata.version",
            )
        )
    else:
        # Check semantic versioning format
        semver_pattern = SEMVER_PATTERN
        if not re.match(semver_pattern, version):
            issues.append(
                ValidationIssue(
                    message=f"Invalid version format: {version}. Must follow semantic versioning (e.g., 'x.y.z').",
                    location="metadata.version",
                )
            )
        else:
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


def validate_uri(uri: str, location: str) -> List[ValidationIssue]:
    """
    Validate URI format and structure.

    According to the STJ specification:
    - URIs MUST include a scheme
    - http and https URIs MUST include a network location
    - file URIs MUST include a path
    - All URIs must conform to RFC 3986
    """
    issues = []
    parsed = urlparse(uri)

    if not parsed.scheme:
        issues.append(
            ValidationIssue(
                message="URI must include a scheme.",
                location=location,
            )
        )
    else:
        # For http and https, check netloc
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

    # Validate URI characters according to RFC 3986
    if re.search(URI_INVALID_CHARS_PATTERN, uri):
        issues.append(
            ValidationIssue(
                message="URI contains invalid characters not allowed by RFC 3986.",
                location=location,
            )
        )

    return issues


def validate_language_code(code: str, location: str) -> List[ValidationIssue]:
    """Validates a single language code.

    Args:
        code: Language code to validate.
        location: Path to the language code in the STJ structure.

    Returns:
        List of validation issues found.

    Note:
        Language codes must be valid ISO 639-1 or ISO 639-3 codes.
    """
    issues = []

    try:
        lang = Lang(str(code))
    except Exception as e:
        issues.append(
            ValidationIssue(
                message=f"Invalid language code '{code}'",
                location=location,
            )
        )

    return issues


def validate_language_codes(
    metadata: Metadata, transcript: Transcript
) -> List[ValidationIssue]:
    """Validates all language codes in metadata and transcript.

    Args:
        metadata: Metadata object containing language codes.
        transcript: Transcript object containing segment language codes.

    Returns:
        List of validation issues found.

    Note:
        Validates language codes in:
        * Metadata languages
        * Source languages
        * Segment languages
    """
    issues = []

    # Validate metadata languages
    if metadata.languages:
        issues.extend(
            _validate_language_code_list(metadata.languages, "metadata.languages")
        )

    # Validate source languages if present
    if metadata.source and metadata.source.languages:
        issues.extend(
            _validate_language_code_list(
                metadata.source.languages, "metadata.source.languages"
            )
        )

    # Validate segment languages
    if transcript.segments:
        for idx, segment in enumerate(transcript.segments):
            if segment.language:
                issues.extend(
                    validate_language_code(
                        segment.language, f"transcript.segments[{idx}].language"
                    )
                )

    return issues


def _validate_language_code_list(
    codes: List[str], location: str
) -> List[ValidationIssue]:
    """
    Helper function to validate a list of language codes.
    """
    issues = []
    for code_idx, code in enumerate(codes):
        code_location = f"{location}[{code_idx}]"
        issues.extend(validate_language_code(code, code_location))
    return issues


def validate_language_consistency(
    metadata: Metadata, transcript: Transcript
) -> List[ValidationIssue]:
    """
    Validate language code consistency across the entire document.
    This function checks for inconsistencies between all language codes.
    """
    issues = []
    language_code_map = {}

    # Helper function to add codes to the map
    def track_codes(codes: List[str], source: str) -> None:
        for code in codes:
            try:
                lang = Lang(str(code))
                primary = lang.pt1 or lang.pt3
                entry = language_code_map.setdefault(
                    lang.name.lower(), {"codes": set(), "locations": set()}
                )
                entry["codes"].add(code)
                entry["locations"].add(source)
            except (KeyError, InvalidLanguageValue):
                pass  # Error already reported by validate_language_code

    # Track all language codes
    if metadata.languages:
        track_codes(metadata.languages, "metadata.languages")
    if metadata.source and metadata.source.languages:
        track_codes(metadata.source.languages, "metadata.source.languages")
    if transcript.segments:
        for idx, segment in enumerate(transcript.segments):
            if segment.language:
                track_codes([segment.language], f"transcript.segments[{idx}].language")

    # Check for inconsistencies
    for language, data in language_code_map.items():
        codes = data["codes"]
        has_part1 = any(len(str(code)) == 2 for code in codes)
        has_part3 = any(len(str(code)) == 3 for code in codes)
        if has_part1 and has_part3:
            issues.append(
                ValidationIssue(
                    message=f"Language code inconsistency for '{language}': Mix of ISO 639-1 and ISO 639-3 codes ({', '.join(sorted(codes))})",
                    location=", ".join(sorted(data["locations"])),
                )
            )

    return issues


def validate_time_format(time_value: float, location: str) -> List[ValidationIssue]:
    """Validates time value format according to STJ specification.

    Args:
        time_value: Time value to validate.
        location: Path to the time value in the STJ structure.

    Returns:
        List of validation issues found.

    Note:
        Time values must:
        * Be finite numbers
        * Be non-negative
        * Not exceed MAX_TIME_VALUE
        * Not use scientific notation
        * Have at most MAX_DECIMAL_PLACES decimal places
    """
    issues = []

    # Add validation for finite float values
    if not isinstance(time_value, (int, float)) or not math.isfinite(time_value):
        issues.append(
            ValidationIssue(
                message=f"Time value must be a finite number, got {time_value}",
                location=location,
            )
        )
        return issues

    if time_value < 0:
        issues.append(
            ValidationIssue(
                message=f"Time value must be non-negative, got {time_value}",
                location=location,
            )
        )

    if time_value > MAX_TIME_VALUE:
        issues.append(
            ValidationIssue(
                message=f"Time value exceeds maximum allowed ({MAX_TIME_VALUE}), got {time_value}",
                location=location,
            )
        )

    str_value = str(time_value)
    if "e" in str_value.lower():
        issues.append(
            ValidationIssue(
                message=f"Scientific notation is not allowed for time values, got {time_value}",
                location=location,
            )
        )

    # Validate decimal places
    if "." in str_value:
        decimals = len(str_value.split(".")[1])
        if decimals > MAX_DECIMAL_PLACES:
            issues.append(
                ValidationIssue(
                    message=f"Time value has too many decimal places (max {MAX_DECIMAL_PLACES}), got {decimals}",
                    location=location,
                )
            )

    return issues


def validate_confidence_scores(transcript: Transcript) -> List[ValidationIssue]:
    """
    Validate confidence scores in segments and words.
    Type checking is handled by validate_types()
    """
    issues = []

    for idx, segment in enumerate(transcript.segments):
        if segment.confidence is not None:
            if not (0.0 <= segment.confidence <= 1.0):
                issues.append(
                    ValidationIssue(
                        message=f"Segment confidence {segment.confidence} out of range [0.0, 1.0]",
                        location=f"transcript.segments[{idx}].confidence",
                    )
                )

        for word_idx, word in enumerate(segment.words or []):
            if word.confidence is not None:
                if not (0.0 <= word.confidence <= 1.0):
                    issues.append(
                        ValidationIssue(
                            message=f"Word confidence {word.confidence} out of range [0.0, 1.0]",
                            location=f"transcript.segments[{idx}].words[{word_idx}].confidence",
                        )
                    )

    return issues


def validate_zero_duration(
    start: float, end: float, is_zero_duration: bool, location: str
) -> List[ValidationIssue]:
    """
    Validate zero duration handling according to spec requirements.

    Args:
        start: Start time of the item
        end: End time of the item
        is_zero_duration: Flag indicating if item is marked as zero duration
        location: Location in the STJ structure for error reporting

    Returns:
        List[ValidationIssue]: List of validation issues found
    """
    issues = []

    if start == end:
        if not is_zero_duration:
            issues.append(
                ValidationIssue(
                    message="Zero duration item must have is_zero_duration set to true",
                    location=location,
                )
            )
    else:  # start != end
        if is_zero_duration:
            issues.append(
                ValidationIssue(
                    message="Non-zero duration item cannot have is_zero_duration set to true",
                    location=location,
                )
            )
        elif start > end:
            issues.append(
                ValidationIssue(
                    message=f"Start time ({start}) cannot be greater than end time ({end})",
                    location=location,
                )
            )

    return issues


def validate_segments(transcript: Transcript) -> List[ValidationIssue]:
    """Validates segments according to STJ specification requirements.

    Args:
        transcript: Transcript object containing segments to validate.

    Returns:
        List of validation issues found.

    Note:
        Validates:
        * Segment ordering and overlap
        * Time formats
        * Zero-duration segments
        * Word timing consistency
        * Speaker and style references
    """
    issues = []
    previous_end = -1

    for i in range(len(transcript.segments)):
        current = transcript.segments[i]

        # Check zero duration segment constraints independently
        if current.start == current.end:
            if current.words:
                issues.append(
                    ValidationIssue(
                        message="Zero duration segment must not have words array",
                        location=f"transcript.segments[{i}]",
                    )
                )
            if current.word_timing_mode:
                issues.append(
                    ValidationIssue(
                        message="Zero duration segment must not specify word_timing_mode",
                        location=f"transcript.segments[{i}]",
                    )
                )

        # Fix location format in time validations
        issues.extend(
            validate_time_format(current.start, f"transcript.segments[{i}].start")
        )
        issues.extend(
            validate_time_format(current.end, f"transcript.segments[{i}].end")
        )

        # Check ordering and overlap
        if i > 0:
            previous = transcript.segments[i - 1]

            # Add missing validation for segments with identical start times
            if current.start == previous.start:
                if current.end < previous.end:
                    issues.append(
                        ValidationIssue(
                            message="Segments with identical start times must be ordered by end time in ascending order",
                            location=f"transcript.segments[{i}]",
                        )
                    )
            elif current.start < previous.start:
                issues.append(
                    ValidationIssue(
                        message="Segments must be ordered by start time",
                        location=f"transcript.segments[{i}]",
                    )
                )

            # Validate overlap, allowing zero-duration segments to share timestamps
            if current.start < previous.end and not (
                current.start == previous.end == current.end
            ):
                issues.append(
                    ValidationIssue(
                        message=f"Segments must not overlap. Previous segment ends at {previous.end}",
                        location=f"transcript.segments[{i}]",
                    )
                )

        # Validate zero-duration segments
        issues.extend(
            validate_zero_duration(
                current.start,
                current.end,
                current.is_zero_duration,
                f"transcript.segments[{i}]",
            )
        )

        # Validate words in segment
        issues.extend(validate_words_in_segment(current, i))

        # Validate style_id if present
        if current.style_id is not None:
            issues.extend(
                validate_style_id(
                    current.style_id, f"transcript.segments[{i}].style_id"
                )
            )

        # Validate speaker_id if present
        if current.speaker_id is not None:
            issues.extend(
                validate_speaker_id(
                    current.speaker_id, f"transcript.segments[{i}].speaker_id"
                )
            )

        # Validate segment languages
        if current.language:
            issues.extend(
                validate_language_code(
                    current.language, f"transcript.segments[{i}].language"
                )
            )

    return issues


def validate_words_in_segment(
    segment: Segment, segment_idx: int
) -> List[ValidationIssue]:
    """Validate words within a segment."""
    issues = []
    words = segment.words or []
    word_timing_mode = segment.word_timing_mode

    # Early return for zero duration segments
    if segment.is_zero_duration:
        return _validate_zero_duration_segment(segment, segment_idx)

    # Validate word timing mode
    issues.extend(_validate_word_timing_mode(segment, segment_idx, words))

    # Validate word timings and order
    issues.extend(_validate_word_timings(segment, segment_idx, words))

    # Validate word text consistency
    if word_timing_mode == WordTimingMode.COMPLETE:
        issues.extend(_validate_word_text_consistency(segment, segment_idx, words))

    return issues


def _validate_zero_duration_segment(
    segment: Segment, segment_idx: int
) -> List[ValidationIssue]:
    """Validate constraints for zero duration segments."""
    issues = []

    if segment.words:
        issues.append(
            ValidationIssue(
                message="Zero duration segment must not have words array",
                location=f"transcript.segments[{segment_idx}]",
            )
        )
    if segment.word_timing_mode:
        issues.append(
            ValidationIssue(
                message="Zero duration segment must not specify word_timing_mode",
                location=f"transcript.segments[{segment_idx}]",
            )
        )
    return issues


def _validate_word_timing_mode(
    segment: Segment, segment_idx: int, words: List[Word]
) -> List[ValidationIssue]:
    """Validate word timing mode settings."""
    issues = []
    word_timing_mode = segment.word_timing_mode

    if word_timing_mode is not None:
        if not isinstance(word_timing_mode, WordTimingMode):
            issues.append(
                ValidationIssue(
                    message=f"Invalid word_timing_mode '{word_timing_mode}'",
                    location=f"transcript.segments[{segment_idx}].word_timing_mode",
                )
            )
            return issues

    # Determine implicit word timing mode
    if word_timing_mode is None and words:
        timing_status = _determine_word_timing_mode(words)
        if timing_status == WordTimingStatus.INVALID:
            issues.append(
                ValidationIssue(
                    message="Incomplete word timing data requires 'word_timing_mode' to be explicitly set to 'partial'",
                    location=f"transcript.segments[{segment_idx}]",
                )
            )
        elif timing_status == WordTimingStatus.COMPLETE:
            # Implicitly complete is allowed by spec
            pass
        elif timing_status == WordTimingStatus.NONE:
            issues.append(
                ValidationIssue(
                    message="Words array present but no timing data found",
                    location=f"transcript.segments[{segment_idx}]",
                )
            )

    # Validate mode constraints
    if word_timing_mode == WordTimingMode.NONE and words:
        issues.append(
            ValidationIssue(
                message="word_timing_mode 'none' must not include words array",
                location=f"transcript.segments[{segment_idx}]",
            )
        )

    return issues


def _determine_word_timing_mode(words: List[Word]) -> WordTimingStatus:
    """
    Determine the word timing mode based on word timing data.

    Args:
        words: List of Word objects to analyze

    Returns:
        WordTimingStatus: The determined timing status
    """
    if not words:
        return WordTimingStatus.NONE

    all_words_have_timing = all(
        word.start is not None and word.end is not None for word in words
    )
    if all_words_have_timing:
        return WordTimingStatus.COMPLETE
    elif any(word.start is not None and word.end is not None for word in words):
        return WordTimingStatus.INVALID
    return WordTimingStatus.NONE


def _validate_word_timings(
    segment: Segment, segment_idx: int, words: List[Word]
) -> List[ValidationIssue]:
    """
    Validate timing information for words within a segment.
    """
    issues = []
    previous_word_end = segment.start

    for word_idx, word in enumerate(words):
        # Validate word time format
        issues.extend(
            validate_time_format(
                word.start,
                f"transcript.segments[{segment_idx}].words[{word_idx}].start",
            )
        )
        issues.extend(
            validate_time_format(
                word.end, f"transcript.segments[{segment_idx}].words[{word_idx}].end"
            )
        )

        # Check if word timings are within segment boundaries
        if word.start < segment.start:
            issues.append(
                ValidationIssue(
                    message=f"Word start time ({word.start}) cannot be before segment start time ({segment.start})",
                    location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                )
            )
        if word.end > segment.end:
            issues.append(
                ValidationIssue(
                    message=f"Word end time ({word.end}) cannot be after segment end time ({segment.end})",
                    location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                )
            )

        # Check word ordering and overlap
        if word.start < previous_word_end and not (word.start == word.end):
            issues.append(
                ValidationIssue(
                    message=f"Words must be ordered and not overlap. Previous word ended at {previous_word_end}",
                    location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                )
            )

        # Validate zero-duration words
        issues.extend(
            validate_zero_duration(
                word.start,
                word.end,
                word.extensions.get("word_duration") == WordDuration.ZERO.value
                if word.extensions
                else False,
                f"transcript.segments[{segment_idx}].words[{word_idx}]",
            )
        )

        previous_word_end = word.end

    return issues


def _validate_word_duration(
    word: Word, segment_idx: int, word_idx: int
) -> List[ValidationIssue]:
    """Validate word duration settings."""
    issues = []

    if word.start == word.end:
        word_duration = word.extensions.get("word_duration")
        if word_duration != WordDuration.ZERO.value:
            issues.append(
                ValidationIssue(
                    message=f"Zero-duration word must have 'word_duration' set to '{WordDuration.ZERO.value}'",
                    location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                )
            )
        elif word_duration not in [e.value for e in WordDuration]:
            issues.append(
                ValidationIssue(
                    message=f"Invalid 'word_duration' value: {word_duration}",
                    location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                )
            )
    else:
        if "word_duration" in word.extensions:
            issues.append(
                ValidationIssue(
                    message="word_duration should not be present for non-zero-duration words",
                    location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                )
            )

    return issues


def _validate_word_text_consistency(
    segment: Segment, segment_idx: int, words: List[Word]
) -> List[ValidationIssue]:
    """
    Validate consistency between segment text and concatenated word texts.
    Only called when word_timing_mode is "complete".
    """
    issues = []
    concatenated_words = " ".join(word.text for word in words)

    # Normalize texts by removing extra whitespace and punctuation
    segment_text = re.sub(TEXT_NORMALIZATION_PATTERN, "", segment.text).lower()
    segment_text = " ".join(segment_text.split())

    words_text = re.sub(TEXT_NORMALIZATION_PATTERN, "", concatenated_words).lower()
    words_text = " ".join(words_text.split())

    if segment_text != words_text:
        issues.append(
            ValidationIssue(
                message=(
                    f"Segment text does not match concatenated word texts "
                    f"(ignoring whitespace/punctuation). "
                    f"Segment: '{segment.text}', Words: '{concatenated_words}'"
                ),
                location=f"transcript.segments[{segment_idx}]",
            )
        )

    return issues


def validate_speaker_id(speaker_id: str, location: str) -> List[ValidationIssue]:
    """
    Validate speaker ID format and type according to specification.
    Note: Type checking is handled by validate_types()

    Args:
        speaker_id: The speaker ID to validate
        location: The location in the STJ structure for error reporting

    Returns:
        List[ValidationIssue]: List of validation issues found
    """
    issues = []

    if not re.match(SPEAKER_ID_PATTERN, speaker_id):
        issues.append(
            ValidationIssue(
                message=f"Invalid speaker ID format: {speaker_id}. Must contain only letters, digits, underscores, or hyphens, with length between 1 and {MAX_SPEAKER_ID_LENGTH} characters.",
                location=location,
            )
        )

    return issues


def validate_speakers(transcript: Transcript) -> List[ValidationIssue]:
    """Validate speakers according to STJ specification requirements."""
    issues = []

    # Always validate if speakers exists (even if empty) to check extensions
    if transcript.speakers is not None:
        # Validate speakers if any exist
        if len(transcript.speakers) > 0:
            speaker_ids = set()
            for idx, speaker in enumerate(transcript.speakers):
                # Use the consolidated speaker_id validation
                issues.extend(
                    validate_speaker_id(speaker.id, f"transcript.speakers[{idx}].id")
                )

                if speaker.id in speaker_ids:
                    issues.append(
                        ValidationIssue(
                            message=f"Duplicate speaker ID: {speaker.id}",
                            location=f"transcript.speakers[{idx}].id",
                        )
                    )
                speaker_ids.add(speaker.id)

                if speaker.extensions:
                    issues.extend(
                        validate_extensions(
                            speaker.extensions, f"transcript.speakers[{idx}].extensions"
                        )
                    )

    return issues


def validate_transcript(transcript: Transcript) -> List[ValidationIssue]:
    """Validate transcript according to STJ specification requirements."""
    issues = []

    # Validate speakers if present
    if transcript.speakers is not None:
        issues.extend(validate_speakers(transcript))

    # Validate segments
    if transcript.segments is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: transcript.segments",
                location="transcript.segments",
            )
        )
    elif not transcript.segments:
        issues.append(
            ValidationIssue(
                message="transcript.segments cannot be empty",
                location="transcript.segments",
            )
        )
    else:
        issues.extend(validate_segments(transcript))

    # Validate styles if present
    if transcript.styles is not None:  # Only check for None
        issues.extend(validate_styles(transcript))

    return issues


# Add these helper functions after the existing imports and constants


def _validate_optional_field(
    value: Any, expected_type: Type, location: str, issues: List[ValidationIssue]
) -> None:
    """Validate an optional field's type if present."""
    if value is not None and not isinstance(value, expected_type):
        issues.append(
            ValidationIssue(
                message=f"{location} must be a {expected_type.__name__}, got {type(value).__name__}",
                location=location,
            )
        )


def _validate_list_field(
    items: List[Any],
    location: str,
    issues: List[ValidationIssue],
    validator_fn: Callable[[Any, int, str, List[ValidationIssue]], None],
    item_type: str = "items",
    allow_empty: bool = False,
) -> None:
    """Validate a list field and its items using a validator function."""
    if not isinstance(items, list):
        issues.append(
            ValidationIssue(
                message=f"{location} must be a list of {item_type}, got {type(items).__name__}",  # Add actual type
                location=location,
            )
        )
        return

    if not items and not allow_empty:
        issues.append(
            ValidationIssue(
                message=f"{location} must contain at least one {item_type[:-1] if item_type.endswith('s') else item_type}",  # Better message
                location=location,
            )
        )
        return

    for idx, item in enumerate(items):
        if item is None:
            issues.append(
                ValidationIssue(
                    message=f"{location}[{idx}] cannot be None, expected {item_type[:-1] if item_type.endswith('s') else item_type}",  # Handle singular form better
                    location=f"{location}[{idx}]",
                )
            )
            continue
        validator_fn(item, idx, location, issues)


def _validate_required_field(
    value: Any, expected_type: Type, location: str, issues: List[ValidationIssue]
) -> None:
    """Validate a required field's type and presence."""
    if value is None:
        issues.append(
            ValidationIssue(
                message=f"Missing required field: {location}", location=location
            )
        )
    elif not isinstance(value, expected_type):
        issues.append(
            ValidationIssue(
                message=f"{location} must be a {expected_type.__name__}, got {type(value).__name__}",
                location=location,
            )
        )


# Add new helper function after _validate_required_field
def _validate_non_empty_string(
    value: Optional[str],
    location: str,
    issues: List[ValidationIssue],
    required: bool = True,
) -> None:
    """
    Validate that a string is not None, empty, or just whitespace.

    Args:
        value: The string value to validate
        location: Location in the STJ structure for error reporting
        issues: List to collect validation issues
        required: If True, None values will raise an issue
    """
    if value is None:
        if required:
            issues.append(
                ValidationIssue(
                    message=f"Missing required field: {location}", location=location
                )
            )
    elif not value or value.isspace():
        issues.append(
            ValidationIssue(
                message=f"{location} cannot be empty or just whitespace",
                location=location,
            )
        )


# Update _validate_speaker to use simplified check
def _validate_speaker(
    speaker: Speaker, idx: int, base_location: str, issues: List[ValidationIssue]
) -> None:
    """Validate types for a speaker object."""
    _validate_required_field(speaker.id, str, f"{base_location}[{idx}].id", issues)
    _validate_non_empty_string(
        speaker.id, f"{base_location}[{idx}].id", issues, required=True
    )

    _validate_optional_field(speaker.name, str, f"{base_location}[{idx}].name", issues)
    _validate_non_empty_string(
        speaker.name, f"{base_location}[{idx}].name", issues, required=False
    )

    _validate_optional_field(
        speaker.extensions, dict, f"{base_location}[{idx}].extensions", issues
    )


# Update _validate_style similarly
def _validate_style(
    style: Style, idx: int, base_location: str, issues: List[ValidationIssue]
) -> None:
    """Validate types for a style object."""
    # Validate ID with all requirements
    _validate_required_field(style.id, str, f"{base_location}[{idx}].id", issues)
    if style.id is not None:
        _validate_non_empty_string(
            style.id, f"{base_location}[{idx}].id", issues, required=True
        )
        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", style.id):
            issues.append(
                ValidationIssue(
                    message=f"Invalid style ID format: {style.id}. Must contain only letters, digits, underscores, or hyphens, with length between 1 and 64 characters.",
                    location=f"{base_location}[{idx}].id",
                )
            )

    _validate_optional_field(style.text, dict, f"{base_location}[{idx}].text", issues)
    _validate_optional_field(
        style.display, dict, f"{base_location}[{idx}].display", issues
    )
    _validate_optional_field(
        style.extensions, dict, f"{base_location}[{idx}].extensions", issues
    )


# Update _validate_word similarly
def _validate_word(
    word: Word, idx: int, base_location: str, issues: List[ValidationIssue]
) -> None:
    """Validate types for a word object."""
    _validate_required_field(
        word.start, (int, float), f"{base_location}[{idx}].start", issues
    )
    _validate_required_field(
        word.end, (int, float), f"{base_location}[{idx}].end", issues
    )
    _validate_required_field(word.text, str, f"{base_location}[{idx}].text", issues)
    _validate_non_empty_string(
        word.text, f"{base_location}[{idx}].text", issues, required=True
    )

    _validate_optional_field(
        word.confidence, (int, float), f"{base_location}[{idx}].confidence", issues
    )
    _validate_optional_field(
        word.extensions, dict, f"{base_location}[{idx}].extensions", issues
    )


# Update language validation
def _validate_language(
    lang: str, idx: int, location: str, issues: List[ValidationIssue]
) -> None:
    """Validate a language code string."""
    # First validate type and non-emptiness
    _validate_optional_field(lang, str, f"{location}[{idx}]", issues)
    _validate_non_empty_string(lang, f"{location}[{idx}]", issues, required=True)

    # Then validate the language code itself
    if lang is not None:
        issues.extend(validate_language_code(lang, f"{location}[{idx}]"))


# Update validate_types for languages
def validate_types(metadata: Metadata, transcript: Transcript) -> List[ValidationIssue]:
    issues = []

    if metadata is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: metadata", location="metadata"
            )
        )
        return issues

    if transcript is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: transcript", location="transcript"
            )
        )
        return issues

    # Add transcriber check and validate all required metadata fields together
    if metadata.transcriber is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: metadata.transcriber",
                location="metadata.transcriber",
            )
        )
    else:
        _validate_required_field(
            metadata.transcriber.name, str, "metadata.transcriber.name", issues
        )
        _validate_required_field(
            metadata.transcriber.version, str, "metadata.transcriber.version", issues
        )
        _validate_non_empty_string(
            metadata.transcriber.name,
            "metadata.transcriber.name",
            issues,
            required=True,
        )
        _validate_non_empty_string(
            metadata.transcriber.version,
            "metadata.transcriber.version",
            issues,
            required=True,
        )

    # Validate metadata.source fields if present
    if metadata.source is not None:
        _validate_optional_field(
            metadata.source.uri, str, "metadata.source.uri", issues
        )
        _validate_optional_field(
            metadata.source.duration, (int, float), "metadata.source.duration", issues
        )
        if metadata.source.languages is not None:
            _validate_list_field(
                metadata.source.languages,
                "metadata.source.languages",
                issues,
                _validate_language,
                "strings",
                allow_empty=True,
            )
        _validate_optional_field(
            metadata.source.extensions, dict, "metadata.source.extensions", issues
        )

    # Validate metadata.languages if present
    if metadata.languages is not None:
        _validate_list_field(
            metadata.languages,
            "metadata.languages",
            issues,
            _validate_language,
            "strings",
        )

    _validate_optional_field(
        metadata.confidence_threshold,
        (int, float),
        "metadata.confidence_threshold",
        issues,
    )
    _validate_optional_field(metadata.extensions, dict, "metadata.extensions", issues)

    # Validate transcript speakers
    if transcript.speakers is not None:  # Only check for None
        _validate_list_field(
            transcript.speakers,
            "transcript.speakers",
            issues,
            _validate_speaker,
            "speakers",
        )

    # Validate transcript styles
    if transcript.styles is not None:
        _validate_list_field(
            transcript.styles, "transcript.styles", issues, _validate_style, "styles"
        )

    # Validate transcript segments
    if transcript.segments is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: transcript.segments",
                location="transcript.segments",
            )
        )
    else:
        for idx, segment in enumerate(transcript.segments):
            if segment is None:
                issues.append(
                    ValidationIssue(
                        message=f"transcript.segments[{idx}] cannot be None",
                        location=f"transcript.segments[{idx}]",
                    )
                )
                continue

            # Required fields - only need _validate_non_empty_string for text
            _validate_required_field(
                segment.start, (int, float), f"transcript.segments[{idx}].start", issues
            )
            _validate_required_field(
                segment.end, (int, float), f"transcript.segments[{idx}].end", issues
            )
            _validate_non_empty_string(
                segment.text, f"transcript.segments[{idx}].text", issues, required=True
            )

            # Optional fields
            _validate_optional_field(
                segment.confidence,
                (int, float),
                f"transcript.segments[{idx}].confidence",
                issues,
            )
            _validate_optional_field(
                segment.word_timing_mode,
                (str, WordTimingMode),
                f"transcript.segments[{idx}].word_timing_mode",
                issues,
            )
            _validate_optional_field(
                segment.is_zero_duration,
                bool,
                f"transcript.segments[{idx}].is_zero_duration",
                issues,
            )
            _validate_optional_field(
                segment.extensions,
                dict,
                f"transcript.segments[{idx}].extensions",
                issues,
            )

            # Optional string fields with empty check
            _validate_non_empty_string(
                segment.speaker_id,
                f"transcript.segments[{idx}].speaker_id",
                issues,
                required=False,
            )
            _validate_non_empty_string(
                segment.style_id,
                f"transcript.segments[{idx}].style_id",
                issues,
                required=False,
            )
            _validate_non_empty_string(
                segment.language,
                f"transcript.segments[{idx}].language",
                issues,
                required=False,
            )

            # Validate words in segment
            if segment.words is not None:
                _validate_list_field(
                    segment.words,
                    f"transcript.segments[{idx}].words",
                    issues,
                    _validate_word,
                    "words",
                )

    return issues


def validate_styles(transcript: Transcript) -> List[ValidationIssue]:
    """Validates style format according to STJ specification.

    Args:
        transcript: Transcript object containing styles to validate.

    Returns:
        List of validation issues found.

    Note:
        Validates:
        * Style ID uniqueness and format
        * Text properties (color, size, etc.)
        * Display properties (alignment, position)
        * Extensions
    """
    issues = []

    if transcript.styles is None:
        return issues

    style_ids = set()
    for idx, style in enumerate(transcript.styles):
        # Validate style ID uniqueness
        if style.id in style_ids:
            issues.append(
                ValidationIssue(
                    message=f"Duplicate style ID: {style.id}",
                    location=f"transcript.styles[{idx}].id",
                )
            )
        style_ids.add(style.id)

        # Validate text properties
        if style.text:
            if not style.text:  # Empty dictionary check
                issues.append(
                    ValidationIssue(
                        message="Style text dictionary cannot be empty",
                        location=f"transcript.styles[{idx}].text",
                    )
                )

            for key, value in style.text.items():
                if value is None:
                    issues.append(
                        ValidationIssue(
                            message=f"Text property '{key}' cannot be None",
                            location=f"transcript.styles[{idx}].text.{key}",
                        )
                    )
                    continue

                if key not in VALID_TEXT_PROPERTIES:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid text property: {key}",
                            location=f"transcript.styles[{idx}].text",
                        )
                    )
                    continue

                # Validate property values based on type
                if key in {"bold", "italic", "underline"}:
                    if not isinstance(value, bool):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid {key} value: {value}. Must be a boolean",
                                location=f"transcript.styles[{idx}].text.{key}",
                            )
                        )

                # Validate color format
                elif key in {"color", "background"}:
                    if not isinstance(value, str) or not re.match(
                        r"^#[0-9A-Fa-f]{6}$", value
                    ):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid color format for {key}: {value}. Must be in #RRGGBB format",
                                location=f"transcript.styles[{idx}].text.{key}",
                            )
                        )

                # Validate percentage values
                elif key in {"size", "opacity"}:
                    if not isinstance(value, str) or not re.match(r"^\d+%$", value):
                        issues.append(
                            ValidationIssue(
                                message=f"Invalid {key} format: {value}. Must be percentage (e.g., '80%')",
                                location=f"transcript.styles[{idx}].text.{key}",
                            )
                        )
                        continue

                    # Additional validation for size and opacity values
                    percent_value = int(value.rstrip("%"))
                    if key == "size" and percent_value <= 0:
                        issues.append(
                            ValidationIssue(
                                message=f"'size' must be greater than 0%, got {value}",
                                location=f"transcript.styles[{idx}].text.size",
                            )
                        )
                    elif key == "opacity" and not (0 <= percent_value <= 100):
                        issues.append(
                            ValidationIssue(
                                message=f"'opacity' must be between 0% and 100%, got {value}",
                                location=f"transcript.styles[{idx}].text.opacity",
                            )
                        )

        # Validate display properties - skip type checking as it's done in validate_types()
        if style.display:
            if not style.display:  # Empty dictionary check
                issues.append(
                    ValidationIssue(
                        message="Style display dictionary cannot be empty",
                        location=f"transcript.styles[{idx}].display",
                    )
                )

            # Validate align property
            if "align" in style.display:
                align_value = style.display["align"]
                if align_value not in VALID_ALIGN_VALUES:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid align value: {align_value}. Must be one of: {', '.join(VALID_ALIGN_VALUES)}",
                            location=f"transcript.styles[{idx}].display.align",
                        )
                    )

            # Validate vertical property
            if "vertical" in style.display:
                vertical_value = style.display["vertical"]
                if vertical_value not in VALID_VERTICAL_VALUES:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid vertical value: {vertical_value}. Must be one of: {', '.join(VALID_VERTICAL_VALUES)}",
                            location=f"transcript.styles[{idx}].display.vertical",
                        )
                    )

            # Validate position
            if "position" in style.display:
                pos = style.display["position"]
                if not isinstance(pos, dict):
                    issues.append(
                        ValidationIssue(
                            message="Position must be a dictionary",
                            location=f"transcript.styles[{idx}].display.position",
                        )
                    )
                else:
                    for coord in ["x", "y"]:
                        if coord in pos:
                            if not isinstance(pos[coord], str):
                                issues.append(
                                    ValidationIssue(
                                        message=f"Position {coord} must be a string percentage value",
                                        location=f"transcript.styles[{idx}].display.position.{coord}",
                                    )
                                )
                            elif not re.match(r"^\d+%$", pos[coord]):
                                issues.append(
                                    ValidationIssue(
                                        message=f"Invalid {coord} position: {pos[coord]}. Must be percentage",
                                        location=f"transcript.styles[{idx}].display.position.{coord}",
                                    )
                                )

        # Validate extensions (type checking is done in validate_types())
        if style.extensions:
            issues.extend(
                validate_extensions(
                    style.extensions, f"transcript.styles[{idx}].extensions"
                )
            )

        # Add empty dictionary validation
        if style.text is not None and not style.text:
            issues.append(
                ValidationIssue(
                    message="Style text dictionary cannot be empty",
                    location=f"transcript.styles[{idx}].text",
                )
            )

        if style.display is not None and not style.display:
            issues.append(
                ValidationIssue(
                    message="Style display dictionary cannot be empty",
                    location=f"transcript.styles[{idx}].display",
                )
            )

    return issues


def validate_style_id(style_id: str, location: str) -> List[ValidationIssue]:
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


def validate_stj(metadata: Metadata, transcript: Transcript) -> List[ValidationIssue]:
    """Performs comprehensive validation of STJ data.

    This function coordinates all validation checks to ensure the STJ data
    fully complies with the specification.

    Args:
        metadata: Metadata object to validate.
        transcript: Transcript object to validate.

    Returns:
        List of all validation issues found.

    Note:
        Performs validation of:
        * Types and required fields
        * Metadata content
        * Transcript content
        * Language codes
        * Confidence scores
    """
    issues = []

    issues.extend(validate_types(metadata, transcript))
    issues.extend(validate_metadata(metadata))
    issues.extend(validate_transcript(transcript))
    issues.extend(validate_language_codes(metadata, transcript))
    issues.extend(validate_confidence_scores(transcript))

    return issues
