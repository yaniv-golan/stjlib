"""
STJLib validation module for Standard Transcription JSON Format.

This module provides comprehensive validation functionality for STJ data structures,
ensuring they conform to the official STJ specification requirements.

The module implements a hierarchical validation system that checks:
    1. Structure Validation - Root object and basic structure
    2. Field Validation - Types, required fields, and value constraints
    3. Reference Validation - Speaker and style ID references
    4. Content Validation - Time formats, language codes, etc.
    5. Extensions Validation - Custom extension namespaces and values

Key Features:
    * Complete validation against STJ specification
    * Detailed error reporting with locations and severity levels
    * Support for all STJ data types and structures
    * Extensible validation framework
    * Comprehensive language code validation
    * Time format and range validation
    * Speaker and style reference validation

Example:
    ```python
    from stjlib.validation import validate_stj
    from stjlib.core import STJ

    # Load or create an STJ object
    stj = STJ(version="0.6.0", transcript=transcript_data)

    # Validate the STJ data
    validation_issues = validate_stj(stj)

    # Check for validation issues
    if validation_issues:
        for issue in validation_issues:
            print(f"{issue.severity}: {issue}")
    ```

Note:
    All validation functions return a list of ValidationIssue objects that describe
    any problems found during validation. Each issue includes:
    * A descriptive message
    * The location in the STJ structure
    * Severity level (ERROR, WARNING, INFO)
    * Reference to relevant specification section
"""

from dataclasses import dataclass, fields, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
import re
from typing import Any, Dict, List, Optional, Union, Type, Callable, Tuple
from urllib.parse import urlparse, urljoin
from enum import Enum, auto
import math
from decimal import Decimal, InvalidOperation

from iso639 import Lang, is_language
from iso639.exceptions import InvalidLanguageValue, DeprecatedLanguageValue

from ..core.data_classes import (
    STJ,
    Metadata,
    Transcript,
    Segment,
    Word,
    Speaker,
    Style,
    Source,
    Transcriber,
)
from ..core.enums import WordTimingMode

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


class ValidationSeverity(Enum):
    """Validation issue severity levels as defined in STJ specification.

    The severity levels help categorize validation issues based on their impact:

    Attributes:
        ERROR: Must violations - file is invalid and unusable
        WARNING: Should violations - may lead to unexpected behavior
        INFO: May violations - suggestions for best practices

    Example:
        ```python
        issue = ValidationIssue(
            message="Invalid time format",
            severity=ValidationSeverity.ERROR
        )
        ```
    """

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    """A validation issue found during STJ data validation.

    This class represents a specific validation problem, providing detailed information
    about where and why the validation failed.

    Attributes:
        message (str): Human-readable description of the validation issue.
        location (Optional[str]): Path to the problematic field in the STJ structure.
            Example: "transcript.segments[0].words[2].start"
        severity (ValidationSeverity): Severity level of the issue (ERROR, WARNING, INFO).
        spec_ref (Optional[str]): Reference to relevant specification section.
        error_code (Optional[str]): Add error code
        suggestion (Optional[str]): Add suggestion for fix

    Example:
        ```python
        issue = ValidationIssue(
            message="Invalid language code 'xx'",
            location="metadata.languages[0]",
            severity=ValidationSeverity.ERROR,
            spec_ref="#language-codes"
        )
        print(issue)  # "metadata.languages[0]: Invalid language code 'xx'"
        ```
    """

    message: str
    location: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    spec_ref: Optional[str] = None
    error_code: Optional[str] = None  # Add error code
    suggestion: Optional[str] = None  # Add suggestion for fix

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation issue to structured dictionary format."""
        return {
            "message": self.message,
            "location": self.location,
            "severity": self.severity.value,
            "spec_ref": self.spec_ref,
            "error_code": self.error_code,
            "suggestion": self.suggestion,
        }

    def __str__(self) -> str:
        """Returns a formatted string representation of the validation issue.

        Returns:
            str: A string combining the location (if any) and the message.
                Format: "<location>: <message>" or just "<message>" if no location.
        """
        if self.location:
            return f"{self.location}: {self.message}"
        else:
            return self.message


def validate_metadata(metadata: Metadata) -> List[ValidationIssue]:
    """Validates metadata according to STJ specification requirements.

    Performs comprehensive validation of the metadata section, including:
    * Required fields (transcriber, created_at)
    * Version format validation
    * Confidence threshold range checking
    * Source information validation
    * Language code validation
    * Extension validation

    Args:
        metadata (Metadata): Metadata object to validate. Can be None as metadata
            is optional in STJ.

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if no issues.

    Example:
        ```python
        metadata = Metadata(
            transcriber=Transcriber(name="MyTranscriber", version="1.0"),
            created_at=datetime.now(timezone.utc)
        )
        issues = validate_metadata(metadata)
        ```

    Note:
        - Metadata is optional in STJ, so None is valid
        - created_at must be timezone-aware if present
        - confidence_threshold must be between 0.0 and 1.0
        - Language codes must be valid ISO 639-1 or ISO 639-3
    """
    issues = []

    if metadata is None:
        # Metadata is optional; no issues if it's missing
        return issues

    # Validate transcriber if present
    if metadata.transcriber:
        if metadata.transcriber.name and not metadata.transcriber.name.strip():
            issues.append(
                ValidationIssue(
                    message="'transcriber.name' must not be empty or whitespace.",
                    location="metadata.transcriber.name",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-transcriber-name",
                )
            )
        if metadata.transcriber.version and not metadata.transcriber.version.strip():
            issues.append(
                ValidationIssue(
                    message="'transcriber.version' must not be empty or whitespace.",
                    location="metadata.transcriber.version",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-transcriber-version",
                )
            )
    # Validate created_at if present
    if metadata.created_at:
        if isinstance(metadata.created_at, datetime):
            # Check if datetime object is timezone-aware
            if metadata.created_at.tzinfo is None:
                issues.append(
                    ValidationIssue(
                        message="'created_at' datetime object must be timezone-aware.",
                        location="metadata.created_at",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#metadata-created-at",
                    )
                )
        elif isinstance(metadata.created_at, str):
            try:
                datetime.fromisoformat(metadata.created_at.replace("Z", "+00:00"))
            except ValueError:
                issues.append(
                    ValidationIssue(
                        message="Invalid 'created_at' format. Must be a valid ISO 8601 timestamp.",
                        location="metadata.created_at",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#metadata-created-at",
                    )
                )
        else:
            issues.append(
                ValidationIssue(
                    message="'created_at' must be a datetime object or ISO 8601 string.",
                    location="metadata.created_at",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-created-at",
                )
            )

    # Validate confidence threshold
    if metadata.confidence_threshold is not None:
        if not (0.0 <= metadata.confidence_threshold <= 1.0):
            issues.append(
                ValidationIssue(
                    message=f"'confidence_threshold' {metadata.confidence_threshold} out of range [0.0, 1.0]",
                    location="metadata.confidence_threshold",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-confidence-threshold",
                )
            )

    # Validate source if present
    if metadata.source:
        if metadata.source.uri:
            issues.extend(validate_uri(metadata.source.uri, "metadata.source.uri"))
        if metadata.source.duration is not None and metadata.source.duration < 0:
            issues.append(
                ValidationIssue(
                    message="'source.duration' must be non-negative",
                    location="metadata.source.duration",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-source-duration",
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
    """Validate STJ version format and compatibility.

    Validates that the version string follows semantic versioning (MAJOR.MINOR.PATCH)
    and is compatible with the supported STJ specification version (0.6.x).

    Args:
        version (str): Version string to validate (e.g., "0.6.0")

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        issues = validate_version("0.6.1")
        if not issues:
            print("Version is valid")
        ```

    Note:
        - Must follow semantic versioning format (MAJOR.MINOR.PATCH)
        - Currently only supports 0.6.x versions
        - All components must be non-negative integers
    """
    issues = []

    if not version or not isinstance(version, str):
        issues.append(
            ValidationIssue(
                message="Missing or invalid 'stj.version'. It must be a non-empty string.",
                location="stj.version",
                severity=ValidationSeverity.ERROR,
                spec_ref="#stj-version",
            )
        )
    else:
        # Check semantic versioning format
        semver_pattern = SEMVER_PATTERN
        if not re.match(semver_pattern, version):
            issues.append(
                ValidationIssue(
                    message=f"Invalid 'stj.version' format: '{version}'. Must follow semantic versioning 'MAJOR.MINOR.PATCH' (e.g., '0.6.0').",
                    location="stj.version",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#stj-version-format",
                )
            )
        else:
            try:
                major, minor, patch = map(int, version.split("."))
                if major != 0 or minor != 6:
                    issues.append(
                        ValidationIssue(
                            message=f"Incompatible version: {version}. Supported major.minor version is '0.6.x'.",
                            location="stj.version",
                            severity=ValidationSeverity.ERROR,
                            spec_ref="#stj-version-compatibility",
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        message=f"Version components must be integers: {version}.",
                        location="stj.version",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#stj-version-format",
                    )
                )
    return issues


def validate_uri(
    uri: str, location: str, base_uri: Optional[str] = None
) -> List[ValidationIssue]:
    """Validate URI format and structure according to STJ specification.

    Performs comprehensive URI validation including:
    * Scheme validation (must be present)
    * Network location validation for http/https URIs
    * Path validation for file URIs
    * Character validation according to RFC 3986

    Args:
        uri (str): URI string to validate
        location (str): Path to the URI field in the STJ structure
        base_uri (Optional[str]): Base URI for resolving relative URIs

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate a source URI
        issues = validate_uri("https://example.com/audio.wav", "metadata.source.uri")
        ```

    Note:
        - HTTP(S) URIs must include network location
        - File URIs must include valid file path
        - All URIs must conform to RFC 3986 character restrictions
        - Recommended schemes are: http, https, file
    """
    issues = []
    parsed = urlparse(uri)

    # Handle relative URIs
    if not parsed.scheme and base_uri:
        issues.append(
            ValidationIssue(
                message="Relative URIs should be avoided. Consider using absolute URIs.",
                location=location,
                severity=ValidationSeverity.WARNING,
                spec_ref="#uri-relative",
            )
        )
        # Try to resolve relative to base
        try:
            resolved = urljoin(base_uri, uri)
            parsed = urlparse(resolved)
        except Exception:
            issues.append(
                ValidationIssue(
                    message="Failed to resolve relative URI",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#uri-resolution",
                )
            )

    # Validate scheme presence
    if not parsed.scheme:
        issues.append(
            ValidationIssue(
                message="URI must include a scheme.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#uri-scheme",
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
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#uri-netloc",
                    )
                )
        elif parsed.scheme == "file":
            if not parsed.path:
                issues.append(
                    ValidationIssue(
                        message="File URI must include a valid file path.",
                        location=location,
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#uri-file-path",
                    )
                )

    # Validate URI characters according to RFC 3986
    if re.search(URI_INVALID_CHARS_PATTERN, uri):
        issues.append(
            ValidationIssue(
                message="URI contains invalid characters not allowed by RFC 3986.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#uri-invalid-characters",
            )
        )

    return issues


def validate_language_code(code: str, location: str) -> List[ValidationIssue]:
    """Validates a single language code against ISO standards.

    Validates that a language code conforms to either ISO 639-1 (2-letter) or
    ISO 639-3 (3-letter) standards, enforcing the use of ISO 639-1 when available.

    Args:
        code (str): Language code to validate (e.g., "en" or "eng")
        location (str): Path to the language code in the STJ structure

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate a language code
        issues = validate_language_code("en", "metadata.languages[0]")

        # Invalid code example
        issues = validate_language_code("xx", "metadata.languages[0]")
        # Returns error: Invalid language code 'xx'
        ```

    Note:
        - Must be either 2-letter ISO 639-1 or 3-letter ISO 639-3 code
        - Case sensitive according to ISO standards
        - Empty or whitespace-only codes are invalid
    """
    issues = []

    if not isinstance(code, str) or not code.strip():
        issues.append(
            ValidationIssue(
                message="Language code must be a non-empty string.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#language-codes",
            )
        )
        return issues

    code = code.strip()

    # Check if code is valid ISO 639-1 or ISO 639-3 code
    if len(code) == 2:
        if not is_language(code, identifiers_or_names="pt1"):
            issues.append(
                ValidationIssue(
                    message=f"Invalid ISO 639-1 language code '{code}'.",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#language-codes",
                )
            )
    elif len(code) == 3:
        if not is_language(code, identifiers_or_names="pt3"):
            issues.append(
                ValidationIssue(
                    message=f"Invalid ISO 639-3 language code '{code}'.",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#language-codes",
                )
            )
        else:
            # Enforce the use of ISO 639-1 code if available
            lang = Lang(code)
            if lang.pt1:
                issues.append(
                    ValidationIssue(
                        message=f"Must use ISO 639-1 code '{lang.pt1}' instead of ISO 639-3 code '{code}'.",
                        location=location,
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#language-codes",
                    )
                )
    else:
        issues.append(
            ValidationIssue(
                message=f"Invalid language code '{code}'. Language codes must be 2-letter (ISO 639-1) or 3-letter (ISO 639-3) codes.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#language-codes",
            )
        )

    return issues


def validate_language_codes(
    metadata: Metadata, transcript: Optional[Transcript]
) -> List[ValidationIssue]:
    """Validates all language codes throughout the STJ document.

    Performs comprehensive validation of language codes in metadata and transcript,
    including:
    * Metadata languages
    * Source languages
    * Segment languages

    Args:
        metadata (Metadata): Metadata object containing language codes
        transcript (Optional[Transcript]): Transcript object containing segment languages

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if all valid.

    Example:
        ```python
        # Validate all language codes in an STJ document
        issues = validate_language_codes(stj.metadata, stj.transcript)
        ```

    Note:
        - All language codes must be valid ISO 639-1 or ISO 639-3
        - Language codes are optional in all locations
        - Validates consistency between different language code usages
        - Empty lists of language codes are valid
    """
    issues = []

    if metadata is not None:
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

    if transcript is not None and transcript.segments:
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
    """Validate consistency of language codes across the entire document.

    Checks for consistency in language code usage throughout the document,
    particularly focusing on:
    * Consistent use of ISO 639-1 vs ISO 639-3 codes
    * Language code compatibility between metadata and segments
    * Consistent language representation across the document

    Args:
        metadata (Metadata): Metadata object containing language information
        transcript (Transcript): Transcript object containing segment languages

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if consistent.

    Example:
        ```python
        # Check language code consistency
        issues = validate_language_consistency(stj.metadata, stj.transcript)
        # Will warn if mixing "en" and "eng" for English
        ```

    Note:
        - Mixing ISO 639-1 and ISO 639-3 codes for the same language generates warnings
        - Checks apply across metadata, source, and segment languages
        - Warnings rather than errors as mixing codes is allowed but discouraged
    """
    issues = []
    language_code_map = {}

    # Helper function to add codes to the map
    def track_codes(codes: List[str], source: str) -> None:
        for code in codes:
            try:
                lang = Lang(code)
                # Check if ISO 639-1 code exists but ISO 639-3 was used
                if len(code) == 3 and lang.pt1:
                    issues.append(
                        ValidationIssue(
                            message=f"Must use ISO 639-1 code '{lang.pt1}' instead of ISO 639-3 code '{code}'",
                            location=source,
                            severity=ValidationSeverity.ERROR,
                            spec_ref="#language-codes",
                        )
                    )

                # Track the language for consistency checking
                primary = lang.pt1 or lang.pt3
                entry = language_code_map.setdefault(
                    lang.name.lower(), {"codes": set(), "locations": set()}
                )
                entry["codes"].add(code)
                entry["locations"].add(source)
            except (KeyError, InvalidLanguageValue):
                pass  # Error already reported by validate_language_code

    # Track all language codes
    if metadata:
        if metadata.languages:
            track_codes(metadata.languages, "metadata.languages")
        if metadata.source and metadata.source.languages:
            track_codes(metadata.source.languages, "metadata.source.languages")

    if transcript and transcript.segments:
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
                    message=f"Inconsistent language codes used for '{language}': {', '.join(sorted(codes))}. Must use consistent codes throughout the file.",
                    location=", ".join(sorted(data["locations"])),
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#language-codes",
                )
            )
        elif len(codes) > 1:  # Multiple different codes used for same language
            issues.append(
                ValidationIssue(
                    message=f"Inconsistent language codes used for '{language}': {', '.join(sorted(codes))}. Must use consistent codes throughout the file.",
                    location=", ".join(sorted(data["locations"])),
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#language-codes",
                )
            )

    return issues


def validate_time_format(
    time_value: Union[float, int, Decimal, str], location: str
) -> List[ValidationIssue]:
    """Validates time value format according to STJ specification.

    Performs comprehensive validation of time values including:
    * Format validation (numeric, non-scientific notation)
    * Range validation (0 to MAX_TIME_VALUE)
    * Decimal precision validation (max 3 decimal places)
    * Finiteness validation

    Args:
        time_value (Union[float, int, Decimal, str]): Time value to validate
        location (str): Path to the time value in the STJ structure

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Valid time values
        issues = validate_time_format(123.456, "transcript.segments[0].start")
        issues = validate_time_format(Decimal("45.789"), "transcript.segments[0].end")

        # Invalid time values
        issues = validate_time_format(-1.0, "transcript.segments[0].start")
        issues = validate_time_format(1e6, "transcript.segments[0].end")  # Scientific notation
        ```

    Note:
        - Must be non-negative finite number
        - Maximum value is 999999.999
        - Maximum 3 decimal places
        - Scientific notation is not allowed
        - String values must be convertible to Decimal
    """
    issues = []

    try:
        # Convert to Decimal based on input type, preserving the original value
        if isinstance(time_value, Decimal):
            decimal_value = time_value
        elif isinstance(time_value, int):
            decimal_value = Decimal(time_value)
        elif isinstance(time_value, float):
            # Use string conversion for float to avoid binary float precision issues
            decimal_value = Decimal(str(time_value))
        elif isinstance(time_value, str):
            decimal_value = Decimal(time_value)
        else:
            issues.append(
                ValidationIssue(
                    message=f"Time value must be a number, got {type(time_value).__name__}",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )
            return issues

        # Check range
        if decimal_value < 0:
            issues.append(
                ValidationIssue(
                    message=f"Time value must be non-negative, got {time_value}",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )
            return issues

        # Check if value exceeds maximum
        max_value = Decimal(str(MAX_TIME_VALUE))
        if decimal_value > max_value:
            issues.append(
                ValidationIssue(
                    message=f"Time value exceeds maximum allowed ({MAX_TIME_VALUE}), got {time_value}",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )
            return issues

        # Check if value would round above maximum
        rounded_value = decimal_value.quantize(
            Decimal("0.001"), rounding=ROUND_HALF_EVEN
        )
        if rounded_value > max_value:
            issues.append(
                ValidationIssue(
                    message=f"Time value would round above maximum allowed ({MAX_TIME_VALUE}), got {time_value}",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )
            return issues

        # Check decimal places
        decimal_places = abs(decimal_value.as_tuple().exponent)
        if decimal_places > MAX_DECIMAL_PLACES:
            issues.append(
                ValidationIssue(
                    message=f"Time value has too many decimal places; maximum allowed is {MAX_DECIMAL_PLACES} decimal places",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )

        # Check finiteness
        if not decimal_value.is_finite():
            issues.append(
                ValidationIssue(
                    message=f"Time value must be a finite number, got {time_value}",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )

        # Check for scientific notation in original value
        str_value = str(time_value)
        if "e" in str_value.lower():
            issues.append(
                ValidationIssue(
                    message=f"Scientific notation is not allowed for time values, got {time_value}",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#time-format",
                )
            )

    except InvalidOperation:
        issues.append(
            ValidationIssue(
                message=f"Invalid time value: {time_value}",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#time-format",
            )
        )

    return issues


def validate_confidence_scores(
    transcript: Optional[Transcript],
) -> List[ValidationIssue]:
    """Validates confidence scores in segments and words.

    Validates that all confidence scores throughout the transcript meet the
    specification requirements:
    * Range validation (0.0 to 1.0)
    * Type validation (handled by validate_types())
    * Optional presence validation

    Args:
        transcript (Optional[Transcript]): Transcript object containing segments and words
            with confidence scores

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if all valid.

    Example:
        ```python
        # Validate confidence scores
        issues = validate_confidence_scores(transcript)
        ```

    Note:
        - Confidence scores must be between 0.0 and 1.0 inclusive
        - Confidence scores are optional for both segments and words
        - Both integer and float values are accepted
        - Type validation is handled separately by validate_types()
    """
    issues = []

    if transcript is None:
        return issues

    for idx, segment in enumerate(transcript.segments or []):
        if segment.confidence is not None:
            if not (0.0 <= segment.confidence <= 1.0):
                issues.append(
                    ValidationIssue(
                        message=f"Segment confidence {segment.confidence} out of range [0.0, 1.0]",
                        location=f"transcript.segments[{idx}].confidence",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#segment-confidence",
                    )
                )

        for word_idx, word in enumerate(segment.words or []):
            if word.confidence is not None:
                if not (0.0 <= word.confidence <= 1.0):
                    issues.append(
                        ValidationIssue(
                            message=f"Word confidence {word.confidence} out of range [0.0, 1.0]",
                            location=f"transcript.segments[{idx}].words[{word_idx}].confidence",
                            severity=ValidationSeverity.ERROR,
                            spec_ref="#word-confidence",
                        )
                    )

    return issues


def validate_zero_duration(
    start: float, end: float, is_zero_duration: bool, location: str
) -> List[ValidationIssue]:
    """Validates zero duration handling according to specification requirements.

    Validates the relationship between start/end times and is_zero_duration flag:
    * Zero duration items must have is_zero_duration=True
    * Non-zero duration items must have is_zero_duration=False
    * Start time must not be greater than end time

    Args:
        start (float): Start time of the item
        end (float): End time of the item
        is_zero_duration (bool): Flag indicating if item is marked as zero duration
        location (str): Path in the STJ structure for error reporting

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Valid zero duration
        issues = validate_zero_duration(10.0, 10.0, True, "transcript.segments[0]")

        # Invalid: zero duration without flag
        issues = validate_zero_duration(10.0, 10.0, False, "transcript.segments[0]")

        # Invalid: non-zero duration with flag
        issues = validate_zero_duration(10.0, 11.0, True, "transcript.segments[0]")
        ```

    Note:
        - Zero duration occurs when start equals end time
        - is_zero_duration must be True for zero duration items
        - is_zero_duration must be False for non-zero duration items
        - Start time must be less than or equal to end time
    """
    issues = []

    if start == end:
        if not is_zero_duration:
            issues.append(
                ValidationIssue(
                    message="Zero duration item must have is_zero_duration set to true",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#zero-duration",
                )
            )
    else:  # start != end
        if is_zero_duration:
            issues.append(
                ValidationIssue(
                    message="Non-zero duration item cannot have is_zero_duration set to true",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#zero-duration",
                )
            )
        elif start > end:
            issues.append(
                ValidationIssue(
                    message=f"Start time ({start}) cannot be greater than end time ({end})",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#zero-duration",
                )
            )
    return issues


def validate_segments(transcript: Transcript) -> List[ValidationIssue]:
    """Validates segments according to STJ specification requirements.

    Performs comprehensive validation of transcript segments including:
    * Segment ordering and overlap validation
    * Time format validation
    * Zero-duration segment validation
    * Word timing consistency
    * Speaker and style reference validation
    * Language code validation

    Args:
        transcript (Transcript): Transcript object containing segments to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if all valid.

    Example:
        ```python
        # Validate all segments in a transcript
        issues = validate_segments(transcript)
        ```

    Note:
        - Segments must be ordered by start time
        - Segments must not overlap
        - All time values must be valid
        - Zero duration segments have special requirements
        - Word timing must be consistent within segments
        - Speaker and style references must be valid
    """
    issues = []

    segments = transcript.segments or []
    previous_end = -1.0  # Initialize previous_end to a negative value

    for idx, segment in enumerate(segments):
        location = f"transcript.segments[{idx}]"

        # Check presence of 'start' and 'end'
        has_start = segment.start is not None
        has_end = segment.end is not None

        if has_start != has_end:
            issues.append(
                ValidationIssue(
                    message="If 'start' or 'end' is present, both must be present.",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#segment-times",
                )
            )

        if has_start and has_end:
            # Validate time formats first
            start_issues = validate_time_format(segment.start, f"{location}.start")
            end_issues = validate_time_format(segment.end, f"{location}.end")
            issues.extend(start_issues)
            issues.extend(end_issues)

            # Only proceed with other time-based validations if time formats are valid
            if not start_issues and not end_issues:
                # Validate zero-duration segments
                issues.extend(
                    validate_zero_duration(
                        segment.start, segment.end, segment.is_zero_duration, location
                    )
                )

                # Check segment ordering and overlap
                if idx > 0:
                    if segment.start < previous_end:
                        issues.append(
                            ValidationIssue(
                                message="Segments must not overlap and must be ordered by start time.",
                                location=location,
                                severity=ValidationSeverity.ERROR,
                                spec_ref="#segment-ordering",
                            )
                        )
                    elif segment.start == previous_end:
                        # Segments can touch but not overlap
                        pass
                    elif segment.start < previous_end:
                        issues.append(
                            ValidationIssue(
                                message="Segments must be ordered by start time.",
                                location=location,
                                severity=ValidationSeverity.ERROR,
                                spec_ref="#segment-ordering",
                            )
                        )

                previous_end = segment.end

        else:
            # If 'start' and 'end' are absent, 'is_zero_duration' must not be present
            if segment.is_zero_duration:
                issues.append(
                    ValidationIssue(
                        message="'is_zero_duration' must not be present when 'start' and 'end' are absent.",
                        location=location,
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#zero-duration",
                    )
                )

        # Validate words in segment
        issues.extend(validate_words_in_segment(segment, idx))

        # Validate style_id if present
        if segment.style_id is not None:
            issues.extend(validate_style_id(segment.style_id, f"{location}.style_id"))

        # Validate speaker_id if present
        if segment.speaker_id is not None:
            issues.extend(
                validate_speaker_id(segment.speaker_id, f"{location}.speaker_id")
            )

        # Validate segment language
        if segment.language:
            issues.extend(
                validate_language_code(segment.language, f"{location}.language")
            )

    return issues


def validate_words_in_segment(
    segment: Segment, segment_idx: int
) -> List[ValidationIssue]:
    """Validate words within a segment."""
    issues = []
    words = segment.words or []
    location = f"transcript.segments[{segment_idx}]"

    # Early return for zero-duration segments
    if segment.is_zero_duration:
        if words:
            issues.append(
                ValidationIssue(
                    message="Zero-duration segment must not have 'words' array.",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#zero-duration",
                )
            )
        if segment.word_timing_mode:
            issues.append(
                ValidationIssue(
                    message="Zero-duration segment must not have 'word_timing_mode'.",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#zero-duration",
                )
            )
        return issues

    # Convert and validate word_timing_mode
    word_timing_mode = segment.word_timing_mode
    if isinstance(word_timing_mode, str):
        try:
            word_timing_mode = WordTimingMode(word_timing_mode.lower())
        except ValueError:
            issues.append(
                ValidationIssue(
                    message=f"Invalid word_timing_mode '{word_timing_mode}'. Must be one of 'complete', 'partial', or 'none'.",
                    location=f"{location}.word_timing_mode",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#word-timing-mode-field",
                )
            )
            return issues

    # Get the effective mode
    effective_word_timing_mode = word_timing_mode
    if word_timing_mode is None:
        timing_status = _determine_word_timing_mode(words)
        if timing_status == WordTimingStatus.COMPLETE:
            effective_word_timing_mode = WordTimingMode.COMPLETE
        elif timing_status == WordTimingStatus.NONE:
            effective_word_timing_mode = WordTimingMode.NONE
        elif timing_status == WordTimingStatus.INVALID:
            issues.append(
                ValidationIssue(
                    message="Incomplete word timing data requires explicit 'word_timing_mode: partial'",
                    location=location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#word-timing-mode-field",
                )
            )
            # Set effective mode to None to avoid further processing
            effective_word_timing_mode = None

    # Validate based on effective mode
    if effective_word_timing_mode == WordTimingMode.COMPLETE:
        for word_idx, word in enumerate(words):
            if word.start is None or word.end is None:
                issues.append(
                    ValidationIssue(
                        message="All words must have timing data when word_timing_mode is 'complete'",
                        location=f"{location}.words[{word_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing-mode-field",
                    )
                )

    # Validate individual words
    for word_idx, word in enumerate(words):
        word_location = f"{location}.words[{word_idx}]"

        # Check presence of 'start' and 'end'
        has_start = word.start is not None
        has_end = word.end is not None

        if has_start != has_end:
            issues.append(
                ValidationIssue(
                    message="If 'start' or 'end' is present in a word, both must be present.",
                    location=word_location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#word-timing",
                )
            )

        if has_start and has_end:
            # Validate time formats
            issues.extend(validate_time_format(word.start, f"{word_location}.start"))
            issues.extend(validate_time_format(word.end, f"{word_location}.end"))

            # Validate zero-duration words
            issues.extend(
                validate_zero_duration(
                    word.start, word.end, word.is_zero_duration, word_location
                )
            )
        else:
            # If 'start' and 'end' are absent, 'is_zero_duration' must not be present
            if word.is_zero_duration:
                issues.append(
                    ValidationIssue(
                        message="'is_zero_duration' must not be present when 'start' and 'end' are absent in a word.",
                        location=word_location,
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#zero-duration",
                    )
                )

    # Validate word timings and order
    issues.extend(_validate_word_timings(segment, segment_idx, words))

    # Validate word text consistency when effective mode is COMPLETE
    if effective_word_timing_mode == WordTimingMode.COMPLETE:
        # Join word texts with single spaces, comparing ignoring case
        concatenated_word_text = " ".join(word.text for word in words).lower()
        segment_text = segment.text.lower()
        if concatenated_word_text != segment_text:
            issues.append(
                ValidationIssue(
                    message="Segment text does not match concatenated word texts",
                    location=location,
                    severity=ValidationSeverity.WARNING,
                    spec_ref="#word-timing-mode-field",
                )
            )

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
    """Validate word timing mode settings according to specification."""
    issues = []
    word_timing_mode = segment.word_timing_mode

    # Zero duration segments should not have word timing mode
    if segment.is_zero_duration:
        if word_timing_mode is not None:
            issues.append(
                ValidationIssue(
                    message="Zero duration segment must not specify word_timing_mode",
                    location=f"transcript.segments[{segment_idx}].word_timing_mode",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#word-timing-mode-field",
                )
            )
        return issues

    if word_timing_mode is not None:
        # Convert string to WordTimingMode if necessary
        if isinstance(word_timing_mode, str):
            try:
                word_timing_mode = WordTimingMode(word_timing_mode.lower())
            except ValueError:
                issues.append(
                    ValidationIssue(
                        message=f"Invalid word_timing_mode '{word_timing_mode}'. Must be one of 'complete', 'partial', or 'none'.",
                        location=f"transcript.segments[{segment_idx}].word_timing_mode",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing-mode-field",
                    )
                )
                return issues
        elif not isinstance(word_timing_mode, WordTimingMode):
            issues.append(
                ValidationIssue(
                    message=f"Invalid word_timing_mode '{word_timing_mode}'. Must be a string or WordTimingMode Enum.",
                    location=f"transcript.segments[{segment_idx}].word_timing_mode",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#word-timing-mode-field",
                )
            )
            return issues

        # Validate mode constraints
        if word_timing_mode == WordTimingMode.NONE:
            if words:
                issues.append(
                    ValidationIssue(
                        message="word_timing_mode 'none' must not include words array",
                        location=f"transcript.segments[{segment_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing-mode-field",
                    )
                )
        elif word_timing_mode == WordTimingMode.COMPLETE:
            # Verify all words have timing and array is not empty
            if not words:
                issues.append(
                    ValidationIssue(
                        message="word_timing_mode 'complete' must include non-empty words array",
                        location=f"transcript.segments[{segment_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing-mode-field",
                    )
                )
            for word_idx, word in enumerate(words):
                if word.start is None or word.end is None:
                    issues.append(
                        ValidationIssue(
                            message="All words must have timing data when word_timing_mode is 'complete'",
                            location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                            severity=ValidationSeverity.ERROR,
                            spec_ref="#word-timing-mode-field",
                        )
                    )
        elif word_timing_mode == WordTimingMode.PARTIAL:
            # Verify array is not empty for partial mode
            if not words:
                issues.append(
                    ValidationIssue(
                        message="word_timing_mode 'partial' must include non-empty words array",
                        location=f"transcript.segments[{segment_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing-mode-field",
                    )
                )

    # Determine implicit word timing mode when not specified
    elif words is not None:  # words array present but no mode specified
        if not words:  # Empty array not allowed in any mode
            issues.append(
                ValidationIssue(
                    message="Empty words array is not allowed. Use word_timing_mode: 'none' instead.",
                    location=f"transcript.segments[{segment_idx}]",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#word-timing-mode-field",
                )
            )
        else:
            timing_status = _determine_word_timing_mode(words)
            if timing_status == WordTimingStatus.INVALID:
                issues.append(
                    ValidationIssue(
                        message="Incomplete word timing data requires explicit 'word_timing_mode: partial'",
                        location=f"transcript.segments[{segment_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing-mode-field",
                    )
                )

    return issues


def _determine_word_timing_mode(words: List[Word]) -> WordTimingStatus:
    """
    Determine the word timing mode based on word timing data.

    According to spec:
    - When words array is absent: Treated as "none"
    - When words array is present with complete timing coverage: Treated as "complete"
    - When words array is present but timing is incomplete or absent: Invalid—must explicitly specify mode

    Args:
        words: List of Word objects to analyze

    Returns:
        WordTimingStatus: The determined timing status: COMPLETE, NONE, or INVALID
    """
    if not words:
        return WordTimingStatus.NONE

    words_with_timing = [
        word for word in words if word.start is not None and word.end is not None
    ]

    if len(words_with_timing) == len(words):
        return WordTimingStatus.COMPLETE
    else:
        # If words array is present but incomplete or no timing,
        # must explicitly specify word_timing_mode
        return WordTimingStatus.INVALID


def _validate_word_timings(
    segment: Segment, segment_idx: int, words: List[Word]
) -> List[ValidationIssue]:
    """
    Validate timing information for words within a segment.
    """
    issues = []
    previous_word_end = None

    for word_idx, word in enumerate(words):
        # Skip timing validation if start/end are None
        if word.start is None or word.end is None:
            continue

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

        # Validate zero-duration words
        issues.extend(
            validate_zero_duration(
                word.start,
                word.end,
                word.is_zero_duration,
                f"transcript.segments[{segment_idx}].words[{word_idx}]",
            )
        )

        # Check if word timings are within segment boundaries
        # Only compare if both values are not None
        if word.start is not None and segment.start is not None:
            if word.start < segment.start:
                issues.append(
                    ValidationIssue(
                        message=f"Word start time ({word.start}) cannot be before segment start time ({segment.start})",
                        location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing",
                    )
                )

        if word.end is not None and segment.end is not None:
            if word.end > segment.end:
                issues.append(
                    ValidationIssue(
                        message=f"Word end time ({word.end}) cannot be after segment end time ({segment.end})",
                        location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing",
                    )
                )

        # Check word ordering and overlap with previous word
        if previous_word_end is not None:
            if word.start < previous_word_end:
                issues.append(
                    ValidationIssue(
                        message="Words within segment must not overlap in time",
                        location=f"transcript.segments[{segment_idx}].words[{word_idx}]",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#word-timing",
                    )
                )

        previous_word_end = word.end

    return issues


def _validate_word_text_consistency(
    segment: Segment, segment_idx: int, words: List[Word]
) -> List[ValidationIssue]:
    """
    Validate consistency between segment text and concatenated word texts.
    According to the spec, the concatenation of words[].text SHOULD match segment.text,
    accounting for whitespace and punctuation.
    """
    issues = []
    concatenated_words = " ".join(word.text for word in words)

    # Normalize texts by removing extra whitespace and punctuation
    segment_text = re.sub(TEXT_NORMALIZATION_PATTERN, "", segment.text)
    segment_text = " ".join(segment_text.split())

    words_text = re.sub(TEXT_NORMALIZATION_PATTERN, "", concatenated_words)
    words_text = " ".join(words_text.split())

    # Perform case-insensitive comparison
    if segment_text.lower() != words_text.lower():
        issues.append(
            ValidationIssue(
                message=(
                    f"Segment text does not match concatenated word texts "
                    f"(accounting for whitespace and punctuation). "
                    f"Segment: '{segment.text}', Words: '{concatenated_words}'"
                ),
                location=f"transcript.segments[{segment_idx}]",
                severity=ValidationSeverity.WARNING,
                spec_ref="#word-timing-mode-field",
            )
        )

    return issues


def validate_speaker_id(speaker_id: str, location: str) -> List[ValidationIssue]:
    """Validates speaker ID format and type according to specification.

    Validates that a speaker ID meets the STJ specification requirements:
    * Format validation (letters, digits, underscores, hyphens only)
    * Length validation (1 to 64 characters)
    * Character set validation

    Args:
        speaker_id (str): The speaker ID to validate
        location (str): Path to the speaker ID in the STJ structure

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Valid speaker IDs
        issues = validate_speaker_id("speaker-1", "transcript.segments[0].speaker_id")
        issues = validate_speaker_id("SPEAKER_A", "transcript.speakers[0].id")

        # Invalid speaker ID
        issues = validate_speaker_id("speaker@1", "transcript.segments[0].speaker_id")
        ```

    Note:
        - Must be 1 to 64 characters long
        - Can only contain letters, digits, underscores, and hyphens
        - Case sensitive
        - Must match pattern: ^[A-Za-z0-9_-]{1,64}$
    """
    issues = []

    if not re.match(SPEAKER_ID_PATTERN, speaker_id):
        issues.append(
            ValidationIssue(
                message=f"Invalid 'speaker_id' format '{speaker_id}'. Must be 1 to {MAX_SPEAKER_ID_LENGTH} characters long, containing only letters, digits, underscores, or hyphens.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#speaker-id-format",
            )
        )

    return issues


def validate_speakers(transcript: Transcript) -> List[ValidationIssue]:
    """Validates speakers according to STJ specification requirements.

    Performs comprehensive validation of transcript speakers including:
    * Speaker ID uniqueness
    * Speaker ID format validation
    * Extension validation
    * Required field validation

    Args:
        transcript (Transcript): Transcript object containing speakers to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate all speakers in a transcript
        issues = validate_speakers(transcript)
        ```

    Note:
        - Speaker IDs must be unique within the transcript
        - Speaker IDs must follow format requirements
        - Extensions are optional but must be valid if present
        - Speakers array is optional but must be valid if present
    """
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
                            severity=ValidationSeverity.ERROR,
                            spec_ref="#speaker-id-unique",
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


def validate_transcript(transcript: Optional[Transcript]) -> List[ValidationIssue]:
    """Validates transcript according to STJ specification requirements.

    Performs comprehensive validation of the transcript section including:
    * Required fields validation
    * Speaker validation
    * Segment validation
    * Style validation
    * Structural validation

    Args:
        transcript (Optional[Transcript]): Transcript object to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate a transcript
        issues = validate_transcript(transcript)
        ```

    Note:
        - Transcript is required in STJ
        - Segments array is required and must not be empty
        - Speakers and styles are optional but must be valid if present
        - All references (speaker_id, style_id) must be valid
    """
    issues = []

    if transcript is None:
        return [
            ValidationIssue(
                message="Missing required field: 'transcript'",
                severity=ValidationSeverity.ERROR,
                spec_ref="#transcript-field",
            )
        ]

    # Check for invalid segments type
    if transcript._invalid_segments_type is not None:
        issues.append(
            ValidationIssue(
                message=f"segments must be an array, got {transcript._invalid_segments_type}",
                location="transcript.segments",
                severity=ValidationSeverity.ERROR,
                spec_ref="#segments-field",
            )
        )
        return issues

    # Validate segments array is present and is an array
    if not isinstance(transcript.segments, list):
        issues.append(
            ValidationIssue(
                message="segments must be an array",
                location="transcript.segments",
                severity=ValidationSeverity.ERROR,
                spec_ref="#segments-field",
            )
        )
    elif not transcript.segments:  # Check if segments array is empty
        issues.append(
            ValidationIssue(
                message="transcript.segments cannot be empty",  # Match expected error message
                location="transcript.segments",
                severity=ValidationSeverity.ERROR,
                spec_ref="#empty-array-rules",
            )
        )
    else:
        issues.extend(validate_segments(transcript))

    # Validate speakers if present
    if transcript.speakers is not None:
        issues.extend(validate_speakers(transcript))

    # Validate styles if present
    if transcript.styles is not None:
        issues.extend(validate_styles(transcript))

    return issues


def _validate_optional_field(
    value: Any,
    expected_type: Type,
    location: str,
    issues: List[ValidationIssue],
    severity: ValidationSeverity = ValidationSeverity.ERROR,
    spec_ref: Optional[str] = None,
) -> None:
    """Validates an optional field's type if the field is present.

    Internal helper function for type validation of optional fields.

    Args:
        value: The value to validate
        expected_type: Type or tuple of types that are valid
        location: Path in STJ structure for error reporting
        issues: List to append validation issues to
        severity: Severity level for validation issues
        spec_ref: Reference to relevant specification section

    Note:
        - None is always valid for optional fields
        - Type checking is strict (no automatic conversion)
        - For numeric types, Decimal is accepted where float/int is expected
    """
    if value is not None and not isinstance(value, expected_type):
        issues.append(
            ValidationIssue(
                message=f"Field {location} must be of type {expected_type.__name__} if present",
                location=location,
                severity=severity,
                spec_ref=spec_ref,
            )
        )


def _validate_list_field(
    items: List[Any],
    location: str,
    issues: List[ValidationIssue],
    item_validator: Callable[[Any, int, str, List[ValidationIssue]], None],
    item_name: str,
    allow_empty: bool = True,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
    spec_ref: Optional[str] = None,
) -> None:
    """Validates a list field and its items using a provided validator function.

    Internal helper function for validating arrays/lists of items.

    Args:
        items: List of items to validate
        location: Path in STJ structure for error reporting
        issues: List to append validation issues to
        item_validator: Function to validate each item
        item_name: Name of items for error messages
        allow_empty: Whether empty lists are valid
        severity: Severity level for validation issues
        spec_ref: Reference to relevant specification section

    Note:
        - Validates both list structure and individual items
        - Empty lists are allowed by default
        - Item validator is called for each item with index
    """
    if not isinstance(items, list):
        issues.append(
            ValidationIssue(
                message=f"Field {location} must be a list of {item_name}",
                location=location,
                severity=severity,
                spec_ref=spec_ref or "#list-fields",
            )
        )
        return

    if not items and not allow_empty:
        issues.append(
            ValidationIssue(
                message=f"Field {location} must not be empty",
                location=location,
                severity=severity,
                spec_ref=spec_ref or "#non-empty-list",
            )
        )

    for idx, item in enumerate(items):
        item_validator(item, idx, location, issues)


def _check_unexpected_fields(
    obj: Any, expected_fields: set, location: str
) -> List[ValidationIssue]:
    """Check for unexpected fields in a dataclass instance.

    Args:
        obj: The dataclass instance to check
        expected_fields: Set of expected field names
        location: Location in the STJ structure for error reporting

    Returns:
        List of validation issues found
    """
    issues = []
    obj_dict = asdict(obj)
    # Exclude internal fields (starting with underscore) from validation
    unexpected_fields = {
        k for k in obj_dict.keys() if not k.startswith("_")
    } - expected_fields
    if unexpected_fields:
        issues.append(
            ValidationIssue(
                message=f"Unexpected fields in {location}: {', '.join(sorted(unexpected_fields))}",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#unexpected-fields",
            )
        )
    return issues


def _validate_required_field(
    value,
    expected_type,
    location,
    issues,
    severity=ValidationSeverity.ERROR,
    spec_ref=None,
):
    """Validate a required field's type.

    Args:
        value: The value to validate
        expected_type: Type or tuple of types that are valid
        location: Location in STJ structure for error reporting
        issues: List to append validation issues to
        severity: Severity level for validation issues
        spec_ref: Reference to relevant specification section
    """
    if value is None:
        issues.append(
            ValidationIssue(
                message=f"Missing required field: {location}",
                location=location,
                severity=severity,
                spec_ref=spec_ref,
            )
        )
    # Special handling for numeric types - allow Decimal where float/int is expected
    elif (
        isinstance(expected_type, tuple)
        and float in expected_type
        and isinstance(value, Decimal)
    ):
        return  # Accept Decimal as valid
    elif not isinstance(value, expected_type):
        type_names = (
            [expected_type.__name__]
            if hasattr(expected_type, "__name__")
            else [t.__name__ for t in expected_type]
        )
        type_str = " or ".join(type_names)

        issues.append(
            ValidationIssue(
                message=f"Field {location} must be of type {type_str}",
                location=location,
                severity=severity,
                spec_ref=spec_ref,
            )
        )


def _validate_non_empty_string(
    value, location, issues, required, severity=ValidationSeverity.ERROR, spec_ref=None
):
    if required and not value:
        issues.append(
            ValidationIssue(
                message=f"Field {location} is required and must be a non-empty string",
                location=location,
                severity=severity,
                spec_ref=spec_ref,
            )
        )
    elif value is not None and (not isinstance(value, str) or not value.strip()):
        issues.append(
            ValidationIssue(
                message=f"Field {location} must be a non-empty string",
                location=location,
                severity=severity,
                spec_ref=spec_ref,
            )
        )


def _validate_speaker(
    speaker: Speaker, idx: int, base_location: str, issues: List[ValidationIssue]
) -> None:
    """Validates types and required fields for a speaker object.

    Internal helper function that performs comprehensive validation of a speaker:
    * Required field validation (id)
    * Optional field validation (name, extensions)
    * Type validation for all fields
    * Format validation for speaker ID

    Args:
        speaker (Speaker): Speaker object to validate
        idx (int): Index of the speaker in the speakers array
        base_location (str): Base path in STJ structure for error reporting
        issues (List[ValidationIssue]): List to append validation issues to

    Note:
        - Speaker ID is required and must follow format requirements
        - Name is optional but must be non-empty if present
        - Extensions are optional but must be valid if present
        - All fields must have correct types
    """
    location = f"{base_location}[{idx}]"
    # Validate 'id' field
    _validate_required_field(
        speaker.id,
        str,
        f"{location}.id",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#speaker-id",
    )
    _validate_non_empty_string(
        speaker.id,
        f"{location}.id",
        issues,
        required=True,
        severity=ValidationSeverity.ERROR,
        spec_ref="#speaker-id",
    )

    # Validate 'name' field
    _validate_optional_field(
        speaker.name,
        str,
        f"{location}.name",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#speaker-name",
    )
    _validate_non_empty_string(
        speaker.name,
        f"{location}.name",
        issues,
        required=False,
        severity=ValidationSeverity.ERROR,
        spec_ref="#speaker-name",
    )

    # Validate 'extensions' field
    _validate_optional_field(
        speaker.extensions,
        dict,
        f"{location}.extensions",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#extensions-field",
    )


def _validate_style(
    style: Style, idx: int, base_location: str, issues: List[ValidationIssue]
) -> None:
    """Validates types and required fields for a style object.

    Internal helper function that performs comprehensive validation of a style:
    * Required field validation (id)
    * Optional field validation (text, display, extensions)
    * Type validation for all fields
    * Format validation for style ID and properties

    Args:
        style (Style): Style object to validate
        idx (int): Index of the style in the styles array
        base_location (str): Base path in STJ structure for error reporting
        issues (List[ValidationIssue]): List to append validation issues to

    Note:
        - Style ID is required and must follow format requirements
        - Text and display properties must be valid if present
        - Extensions are optional but must be valid if present
        - All fields must have correct types
    """
    location = f"{base_location}[{idx}]"
    # Validate 'id' field
    _validate_required_field(
        style.id,
        str,
        f"{location}.id",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#style-id",
    )
    _validate_non_empty_string(
        style.id,
        f"{location}.id",
        issues,
        required=True,
        severity=ValidationSeverity.ERROR,
        spec_ref="#style-id",
    )
    if style.id is not None and not re.match(r"^[A-Za-z0-9_-]{1,64}$", style.id):
        issues.append(
            ValidationIssue(
                message=f"Invalid style ID format: {style.id}. Must contain only letters, digits, underscores, or hyphens, with length between 1 and 64 characters.",
                location=f"{location}.id",
                severity=ValidationSeverity.ERROR,
                spec_ref="#style-id-format",
            )
        )

    # Validate 'text' field
    _validate_optional_field(
        style.text,
        dict,
        f"{location}.text",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#style-text",
    )
    # Validate 'display' field
    _validate_optional_field(
        style.display,
        dict,
        f"{location}.display",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#style-display",
    )
    # Validate 'extensions' field
    _validate_optional_field(
        style.extensions,
        dict,
        f"{location}.extensions",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#extensions-field",
    )


def _validate_word(
    word: Word, idx: int, base_location: str, issues: List[ValidationIssue]
) -> None:
    """Validates types and required fields for a word object.

    Internal helper function that performs comprehensive validation of a word:
    * Required field validation (text)
    * Optional field validation (start, end, confidence, extensions)
    * Type validation for all fields
    * Time format validation
    * Confidence score validation

    Args:
        word (Word): Word object to validate
        idx (int): Index of the word in the words array
        base_location (str): Base path in STJ structure for error reporting
        issues (List[ValidationIssue]): List to append validation issues to

    Note:
        - Text is required and must be non-empty
        - Start and end times must both be present or both absent
        - Confidence must be between 0.0 and 1.0 if present
        - Extensions are optional but must be valid if present
        - Empty words arrays are not allowed in any mode
    """
    location = f"{base_location}[{idx}]"
    # Validate 'text' field
    _validate_required_field(
        word.text,
        str,
        f"{location}.text",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#word-text",
    )
    _validate_non_empty_string(
        word.text,
        f"{location}.text",
        issues,
        required=True,
        severity=ValidationSeverity.ERROR,
        spec_ref="#word-text",
    )

    # Validate 'start' and 'end' fields if present
    has_start = word.start is not None
    has_end = word.end is not None
    if has_start != has_end:
        issues.append(
            ValidationIssue(
                message="If 'start' or 'end' is present in a word, both must be present.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#word-timing",
            )
        )
    else:
        if has_start and has_end:
            _validate_required_field(
                word.start,
                (int, float),
                f"{location}.start",
                issues,
                severity=ValidationSeverity.ERROR,
                spec_ref="#word-start-end",
            )
            _validate_required_field(
                word.end,
                (int, float),
                f"{location}.end",
                issues,
                severity=ValidationSeverity.ERROR,
                spec_ref="#word-start-end",
            )

    # Validate 'confidence' field
    _validate_optional_field(
        word.confidence,
        (int, float),
        f"{location}.confidence",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#word-confidence",
    )

    # Validate 'extensions' field
    _validate_optional_field(
        word.extensions,
        dict,
        f"{location}.extensions",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#extensions-field",
    )


def _validate_language(
    lang: str, idx: int, location: str, issues: List[ValidationIssue]
) -> None:
    """Validates a language code string in a list context.

    Internal helper function that validates a language code within a list:
    * Type validation (must be string)
    * Non-empty validation
    * ISO 639-1/639-3 code validation

    Args:
        lang (str): Language code to validate
        idx (int): Index of the language code in the list
        location (str): Base path in STJ structure for error reporting
        issues (List[ValidationIssue]): List to append validation issues to

    Note:
        - Must be a valid ISO 639-1 or ISO 639-3 code
        - Must be a non-empty string
        - Case sensitive according to ISO standards
    """
    # First validate type and non-emptiness
    _validate_optional_field(
        lang,
        str,
        f"{location}[{idx}]",
        issues,
        severity=ValidationSeverity.ERROR,
        spec_ref="#language-codes",
    )
    _validate_non_empty_string(
        lang,
        f"{location}[{idx}]",
        issues,
        required=True,
        severity=ValidationSeverity.ERROR,
        spec_ref="#language-codes",
    )

    # Then validate the language code itself
    if lang is not None:
        issues.extend(validate_language_code(lang, f"{location}[{idx}]"))


def validate_types(stj: STJ) -> List[ValidationIssue]:
    """Validates types and required fields in STJ data structure.

    Performs comprehensive type validation throughout the STJ structure:
    * Root object validation
    * Required field presence and type validation
    * Optional field type validation
    * Nested object validation
    * Array type validation

    Args:
        stj (STJ): The STJ object containing version, transcript, and optional metadata

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if all valid.

    Example:
        ```python
        # Validate types in an STJ object
        issues = validate_types(stj)
        ```

    Note:
        - Validates all fields recursively
        - Checks both presence and type of required fields
        - Validates type of optional fields if present
        - Ensures correct array types for lists
        - Validates nested object structures
    """
    issues = []

    # Validate STJ root
    if stj is None:
        issues.append(
            ValidationIssue(
                message="Missing required root object: 'stj'",
                location="stj",
                severity=ValidationSeverity.ERROR,
                spec_ref="#stj-root",
            )
        )
        return issues

    # Validate STJ version
    if not stj.version or not isinstance(stj.version, str):
        issues.append(
            ValidationIssue(
                message="Missing or invalid 'stj.version'. It must be a non-empty string.",
                location="stj.version",
                severity=ValidationSeverity.ERROR,
                spec_ref="#stj-version",
            )
        )

    # Validate transcript
    transcript = stj.transcript
    if transcript is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: 'transcript'",
                location="stj.transcript",
                severity=ValidationSeverity.ERROR,
                spec_ref="#transcript-field",
            )
        )
        return issues

    # Check for unexpected fields in transcript
    issues.extend(
        _check_unexpected_fields(
            transcript, {field.name for field in fields(Transcript)}, "transcript"
        )
    )

    # Validate transcript speakers
    if transcript.speakers is not None:
        _validate_list_field(
            transcript.speakers,
            "transcript.speakers",
            issues,
            _validate_speaker,
            "speakers",
            allow_empty=True,
        )

    # Validate transcript styles
    if transcript.styles is not None:
        _validate_list_field(
            transcript.styles,
            "transcript.styles",
            issues,
            _validate_style,
            "styles",
        )

    # Validate transcript segments
    if transcript.segments is None:
        issues.append(
            ValidationIssue(
                message="Missing required field: 'transcript.segments'",
                location="transcript.segments",
                severity=ValidationSeverity.ERROR,
                spec_ref="#segments-field",
            )
        )
    else:
        for idx, segment in enumerate(transcript.segments):
            location = f"transcript.segments[{idx}]"
            if segment is None:
                issues.append(
                    ValidationIssue(
                        message=f"{location} cannot be None",
                        location=location,
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#segments-array",
                    )
                )
                continue

            # Check for unexpected fields in segment
            issues.extend(
                _check_unexpected_fields(
                    segment, {field.name for field in fields(Segment)}, location
                )
            )

            # Required field: 'text'
            _validate_non_empty_string(
                segment.text,
                f"{location}.text",
                issues,
                required=True,
            )

            # Optional fields: 'start' and 'end' must be both present or both absent
            has_start = segment.start is not None
            has_end = segment.end is not None
            if has_start != has_end:
                issues.append(
                    ValidationIssue(
                        message="If 'start' or 'end' is present, both must be present.",
                        location=location,
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#segment-times",
                    )
                )
            else:
                # Validate 'start' and 'end' if present
                if has_start and has_end:
                    _validate_required_field(
                        segment.start, (int, float), f"{location}.start", issues
                    )
                    _validate_required_field(
                        segment.end, (int, float), f"{location}.end", issues
                    )

            # Optional fields
            _validate_optional_field(
                segment.confidence,
                (int, float),
                f"{location}.confidence",
                issues,
            )
            _validate_optional_field(
                segment.word_timing_mode,
                (str, WordTimingMode),
                f"{location}.word_timing_mode",
                issues,
            )
            _validate_optional_field(
                segment.is_zero_duration,
                bool,
                f"{location}.is_zero_duration",
                issues,
            )
            _validate_optional_field(
                segment.extensions,
                dict,
                f"{location}.extensions",
                issues,
            )

            # Optional string fields with empty check
            _validate_non_empty_string(
                segment.speaker_id,
                f"{location}.speaker_id",
                issues,
                required=False,
            )
            _validate_non_empty_string(
                segment.style_id,
                f"{location}.style_id",
                issues,
                required=False,
            )
            _validate_non_empty_string(
                segment.language,
                f"{location}.language",
                issues,
                required=False,
            )

            # Validate words in segment
            if segment.words is not None:
                _validate_list_field(
                    segment.words,
                    f"{location}.words",
                    issues,
                    _validate_word,
                    "words",
                    allow_empty=False,
                )
                for word_idx, word in enumerate(segment.words):
                    word_location = f"{location}.words[{word_idx}]"
                    if word is None:
                        issues.append(
                            ValidationIssue(
                                message=f"{word_location} cannot be None",
                                location=word_location,
                                severity=ValidationSeverity.ERROR,
                                spec_ref="#words-array",
                            )
                        )
                        continue
                    # Check for unexpected fields in word
                    issues.extend(
                        _check_unexpected_fields(
                            word, {field.name for field in fields(Word)}, word_location
                        )
                    )

    # Validate metadata if present
    metadata = stj.metadata
    if metadata is not None:
        # Check if we received invalid input type
        if metadata._invalid_type is not None:
            issues.append(
                ValidationIssue(
                    message=f"metadata must be a dictionary, got {metadata._invalid_type}",
                    location="metadata",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-section",
                )
            )
            return issues

        if not isinstance(metadata, Metadata):
            issues.append(
                ValidationIssue(
                    message="metadata must be a dictionary",
                    location="metadata",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-section",
                )
            )
            return issues

        if metadata.transcriber is not None:
            # Check if transcriber had invalid input type
            if metadata.transcriber._invalid_type is not None:
                issues.append(
                    ValidationIssue(
                        message=f"transcriber must be a dictionary, got {metadata.transcriber._invalid_type}",
                        location="metadata.transcriber",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#metadata-section",
                    )
                )
                return issues

        # Check for unexpected fields in metadata
        issues.extend(
            _check_unexpected_fields(
                metadata, {field.name for field in fields(Metadata)}, "metadata"
            )
        )

        # Validate transcriber if present
        if metadata.transcriber is not None:
            transcriber_location = "metadata.transcriber"
            issues.extend(
                _check_unexpected_fields(
                    metadata.transcriber,
                    {field.name for field in fields(Transcriber)},
                    transcriber_location,
                )
            )

            # Validate 'name' field if present
            if metadata.transcriber.name is not None:
                _validate_non_empty_string(
                    metadata.transcriber.name,
                    f"{transcriber_location}.name",
                    issues,
                    required=False,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-transcriber-name",
                )

            # Validate 'version' field if present
            if metadata.transcriber.version is not None:
                _validate_non_empty_string(
                    metadata.transcriber.version,
                    f"{transcriber_location}.version",
                    issues,
                    required=False,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#metadata-transcriber-version",
                )
        # Do not add validation issues if transcriber is missing, since it's optional

        # Validate created_at if present
        if metadata.created_at is not None:
            if not isinstance(metadata.created_at, datetime):
                issues.append(
                    ValidationIssue(
                        message="'metadata.created_at' must be a datetime object.",
                        location="metadata.created_at",
                        severity=ValidationSeverity.ERROR,
                        spec_ref="#metadata-created-at",
                    )
                )

        # Validate source if present
        if metadata.source is not None:
            source_location = "metadata.source"
            issues.extend(
                _check_unexpected_fields(
                    metadata.source,
                    {field.name for field in fields(Source)},
                    source_location,
                )
            )
            # Optional fields
            _validate_optional_field(
                metadata.source.uri, str, f"{source_location}.uri", issues
            )
            _validate_optional_field(
                metadata.source.duration,
                (int, float),
                f"{source_location}.duration",
                issues,
            )
            if metadata.source.languages is not None:
                _validate_list_field(
                    metadata.source.languages,
                    f"{source_location}.languages",
                    issues,
                    _validate_language,
                    "strings",
                    allow_empty=True,
                )
            _validate_optional_field(
                metadata.source.extensions,
                dict,
                f"{source_location}.extensions",
                issues,
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
        _validate_optional_field(
            metadata.extensions, dict, "metadata.extensions", issues
        )

    return issues


def validate_styles(transcript: Transcript) -> List[ValidationIssue]:
    """Validates style format according to STJ specification.

    Performs comprehensive validation of transcript styles:
    * Style ID uniqueness and format
    * Text property validation (color, size, etc.)
    * Display property validation (alignment, position)
    * Extension validation
    * Required field validation

    Args:
        transcript (Transcript): Transcript object containing styles to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate all styles in a transcript
        issues = validate_styles(transcript)
        ```

    Note:
        - Style IDs must be unique within the transcript
        - Text properties must have valid values (colors, sizes, etc.)
        - Display properties must have valid values (alignment, position)
        - Extensions are optional but must be valid if present
        - Empty style dictionaries are not allowed
    """
    issues = []

    if transcript.styles is None:
        return issues

    style_ids = set()
    style_ids = set()
    for idx, style in enumerate(transcript.styles):
        # Validate style ID uniqueness
        if style.id in style_ids:
            issues.append(
                ValidationIssue(
                    message=f"Duplicate style ID: {style.id}",
                    location=f"transcript.styles[{idx}].id",
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#style-id",
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
    """Validates style ID format according to STJ specification.

    Validates that a style ID meets the format requirements:
    * Length validation (1 to 64 characters)
    * Character set validation (letters, digits, underscores, hyphens)
    * Format pattern matching

    Args:
        style_id (str): Style ID to validate
        location (str): Path to the style ID in the STJ structure

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Valid style IDs
        issues = validate_style_id("style-1", "transcript.styles[0].id")
        issues = validate_style_id("HIGHLIGHT_A", "transcript.segments[0].style_id")

        # Invalid style ID
        issues = validate_style_id("style@1", "transcript.styles[0].id")
        ```

    Note:
        - Must be 1 to 64 characters long
        - Can only contain letters, digits, underscores, and hyphens
        - Case sensitive
        - Must match pattern: ^[A-Za-z0-9_-]{1,64}$
    """
    issues = []

    if not re.match(r"^[A-Za-z0-9_-]{1,64}$", style_id):
        issues.append(
            ValidationIssue(
                message=f"Invalid 'style_id' format '{style_id}'. Must be 1 to 64 characters long, containing only letters, digits, underscores, or hyphens.",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#style-id-format",
            )
        )

    return issues


def validate_references(transcript: Optional[Transcript]) -> List[ValidationIssue]:
    """Validates all references in the transcript.

    Performs comprehensive validation of references:
    * Speaker ID references to speakers list
    * Style ID references to styles list
    * Reference existence validation
    * Reference format validation

    Args:
        transcript (Optional[Transcript]): Transcript object containing references to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if all valid.

    Example:
        ```python
        # Validate all references in a transcript
        issues = validate_references(transcript)
        ```

    Note:
        - All referenced speaker_ids must exist in speakers list
        - All referenced style_ids must exist in styles list
        - References must follow format requirements
        - Missing references are reported as errors
    """
    issues = []

    if transcript is None:
        return issues

    # Build reference sets
    speaker_ids = {s.id for s in transcript.speakers} if transcript.speakers else set()
    style_ids = {s.id for s in transcript.styles} if transcript.styles else set()

    # Check references
    for idx, segment in enumerate(transcript.segments):
        if segment.speaker_id and segment.speaker_id not in speaker_ids:
            issues.append(
                ValidationIssue(
                    message=f"Invalid speaker_id reference: {segment.speaker_id}",
                    location=f"transcript.segments[{idx}].speaker_id",
                    severity=ValidationSeverity.ERROR,
                )
            )

        if segment.style_id and segment.style_id not in style_ids:
            issues.append(
                ValidationIssue(
                    message=f"Invalid style_id reference: {segment.style_id}",
                    location=f"transcript.segments[{idx}].style_id",
                    severity=ValidationSeverity.ERROR,
                )
            )

    return issues


def validate_extensions(
    extensions: Dict[str, Any],
    location: str,
    parent_namespaces: Optional[List[str]] = None,
    depth: int = 0,
) -> List[ValidationIssue]:
    """Validates extension fields according to STJ specification.

    Performs comprehensive validation of extensions:
    * Namespace format validation
    * Reserved namespace checking
    * Circular reference detection
    * Value type validation
    * Nested extension validation

    Args:
        extensions (Dict[str, Any]): Extensions dictionary to validate
        location (str): Path to the extensions in the STJ structure
        parent_namespaces (Optional[List[str]]): List of parent namespace names for circular reference detection
        depth (int): Current depth in nested extensions

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate extensions
        extensions = {
            "custom": {"key": "value"},
            "metadata": {"source": "ASR"}
        }
        issues = validate_extensions(extensions, "metadata.extensions")
        ```

    Note:
        - Namespace must be non-empty strings
        - Reserved namespaces cannot be used
        - Extension values must be objects/dictionaries
        - Circular references are not allowed
        - Nested extensions are validated recursively
    """
    issues = []
    parent_namespaces = parent_namespaces or []

    # Type checking handled by validate_types()
    if extensions is None:
        issues.append(
            ValidationIssue(
                message="Extensions must be an object",
                location=location,
                severity=ValidationSeverity.ERROR,
                spec_ref="#extensions-field",
            )
        )
        return issues

    for namespace, value in extensions.items():
        current_namespace_path = parent_namespaces + [namespace]
        namespace_location = f"{location}.{namespace}"

        # Check for circular references
        if namespace in parent_namespaces:
            issues.append(
                ValidationIssue(
                    message=f"Circular reference detected in extensions: {' -> '.join(current_namespace_path)}",
                    location=namespace_location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#extensions-circular",
                )
            )
            continue

        # Validate namespace is a non-empty string
        if not isinstance(namespace, str) or not namespace:
            issues.append(
                ValidationIssue(
                    message=f"Invalid extension namespace '{namespace}'. Namespaces must be non-empty strings.",
                    location=namespace_location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#extensions-namespace",
                )
            )

        # Check reserved namespaces
        if namespace in RESERVED_NAMESPACES:
            issues.append(
                ValidationIssue(
                    message=f"Reserved namespace '{namespace}' cannot be used",
                    location=namespace_location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#extensions-reserved",
                )
            )

        # Value must be an object/dictionary
        if not isinstance(value, dict):
            issues.append(
                ValidationIssue(
                    message=f"Extension value for namespace '{namespace}' must be an object",
                    location=namespace_location,
                    severity=ValidationSeverity.ERROR,
                    spec_ref="#extensions-value",
                )
            )
            continue

        # Recursively validate nested extensions if present
        if "extensions" in value:
            nested_extensions = value["extensions"]
            nested_location = f"{namespace_location}.extensions"
            issues.extend(
                validate_extensions(
                    nested_extensions,
                    nested_location,
                    current_namespace_path,
                    depth + 1,
                )
            )

    return issues


def validate_all_extensions(stj: STJ) -> List[ValidationIssue]:
    """Validates all extensions fields throughout the STJ data.

    Performs comprehensive validation of all extension fields in:
    * Metadata extensions
    * Source extensions
    * Segment extensions
    * Word extensions
    * Speaker extensions
    * Style extensions

    Args:
        stj (STJ): STJ object containing all extensions to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if all valid.

    Example:
        ```python
        # Validate all extensions in an STJ document
        issues = validate_all_extensions(stj)
        ```

    Note:
        - Validates extensions at all levels of the STJ structure
        - Each extension must follow extension validation rules
        - Extensions are optional but must be valid if present
        - Nested extensions are validated recursively
    """
    issues = []
    metadata = stj.metadata
    transcript = stj.transcript

    # Metadata extensions
    if metadata:
        if metadata.extensions:
            issues.extend(
                validate_extensions(metadata.extensions, "metadata.extensions")
            )
        if metadata.source and metadata.source.extensions:
            issues.extend(
                validate_extensions(
                    metadata.source.extensions, "metadata.source.extensions"
                )
            )

    # Transcript extensions - only validate if transcript exists
    if transcript:
        # Validate segment extensions
        for idx, segment in enumerate(transcript.segments or []):
            if segment.extensions:
                issues.extend(
                    validate_extensions(
                        segment.extensions, f"transcript.segments[{idx}].extensions"
                    )
                )

            for word_idx, word in enumerate(segment.words or []):
                if word.extensions:
                    issues.extend(
                        validate_extensions(
                            word.extensions,
                            f"transcript.segments[{idx}].words[{word_idx}].extensions",
                        )
                    )

        # Speaker extensions
        for idx, speaker in enumerate(transcript.speakers or []):
            if speaker.extensions:
                issues.extend(
                    validate_extensions(
                        speaker.extensions, f"transcript.speakers[{idx}].extensions"
                    )
                )

        # Style extensions
        for idx, style in enumerate(transcript.styles or []):
            if style.extensions:
                issues.extend(
                    validate_extensions(
                        style.extensions, f"transcript.styles[{idx}].extensions"
                    )
                )

    return issues


def validate_root_structure(stj: STJ) -> List[ValidationIssue]:
    """Validates the root structure of the STJ object.

    Performs basic validation of the STJ root object structure:
    * Type validation (must be STJ instance)
    * Required field presence
    * Basic structural validation
    * Unexpected field validation

    Args:
        stj (STJ): STJ object to validate

    Returns:
        List[ValidationIssue]: List of validation issues found. Empty list if valid.

    Example:
        ```python
        # Validate root structure
        issues = validate_root_structure(stj)
        ```

    Note:
        - Must be an instance of STJ class
        - Must contain required fields (version, transcript)
        - Must not contain unexpected fields
        - Additional root structure validation can be added here

    Implementation Note:
        Root validation is handled directly rather than using _check_unexpected_fields()
        because we need to check the raw dictionary representation. The STJ class may
        contain additional fields in its dictionary form that aren't part of its
        dataclass definition, so we can't rely on dataclass field inspection here.
    """
    issues = []

    if not isinstance(stj, STJ):
        issues.append(
            ValidationIssue(
                message="Invalid STJ root object.",
                location="stj",
                severity=ValidationSeverity.ERROR,
                spec_ref="#stj-root",
            )
        )
        return issues

    if stj._invalid_type is not None:
        issues.append(
            ValidationIssue(
                message=f"STJ data must be a dictionary, got {stj._invalid_type}",
                location="stj",
                severity=ValidationSeverity.ERROR,
                spec_ref="#stj-root",
            )
        )
        return issues

    # Proceed with the existing validation
    # Get the raw dictionary to check for unexpected fields
    stj_dict = stj.to_dict()

    # First check for stj root object
    if "stj" not in stj_dict:
        issues.append(
            ValidationIssue(
                message="STJ data must contain a 'stj' root object",
                severity=ValidationSeverity.ERROR,
                spec_ref="#stj-root",
            )
        )
        return issues  # Return early if missing stj root

    # Then check for unexpected fields

    # Check for unexpected fields directly - see implementation note above
    # for reason why we are not using _check_unexpected_fields()
    root_dict = stj_dict["stj"]
    allowed_fields = {"version", "transcript", "metadata"}
    unexpected_fields = {
        k for k in root_dict.keys() if not k.startswith("_")
    } - allowed_fields
    if unexpected_fields:
        issues.append(
            ValidationIssue(
                message=f"Unexpected fields in stj: {', '.join(sorted(unexpected_fields))}",
                location="stj",
                severity=ValidationSeverity.ERROR,
                spec_ref="#unexpected-fields",
            )
        )
    return issues


def validate_stj(stj: STJ) -> List[ValidationIssue]:
    """Performs comprehensive validation of STJ data following the specification sequence.

    Executes the complete validation sequence according to STJ specification:
    1. Structure Validation - Root object and basic structure
    2. Field Validation - Types, required fields, and constraints
    3. Reference Validation - Speaker and style ID references
    4. Content Validation - Time formats, language codes, etc.
    5. Extensions Validation - Custom extension validation

    Args:
        stj (STJ): STJ object to validate

    Returns:
        List[ValidationIssue]: List of all validation issues found. Empty list if valid.

    Example:
        ```python
        # Perform complete STJ validation
        stj = STJ(version="0.6.0", transcript=transcript_data)
        issues = validate_stj(stj)

        # Check validation results
        if not issues:
            print("STJ document is valid")
        else:
            for issue in issues:
                print(f"{issue.severity}: {issue}")
        ```

    Note:
        - Validates all aspects of the STJ specification
        - Returns all found issues, not just the first error
        - Includes errors, warnings, and informational messages
        - Provides detailed location information for issues
        - References relevant specification sections
    """
    issues = []

    # Structure Validation
    issues.extend(validate_root_structure(stj))
    if issues:  # Stop if root structure is invalid
        return issues

    # Version Validation
    issues.extend(validate_version(stj.version))
    if issues:
        return issues

    # Validate transcript (including empty segments check)
    issues.extend(validate_transcript(stj.transcript))

    # Only proceed with other validations if basic structure is valid
    if not issues:
        # Field Validation
        issues.extend(validate_types(stj))

        # Reference Validation
        issues.extend(validate_references(stj.transcript))

        # Validate metadata if present
        if stj.metadata:
            issues.extend(validate_metadata(stj.metadata))

        # Validate language codes and consistency
        issues.extend(validate_language_codes(stj.metadata, stj.transcript))
        issues.extend(validate_language_consistency(stj.metadata, stj.transcript))

        # Validate confidence scores
        issues.extend(validate_confidence_scores(stj.transcript))

        # Extensions Validation
        issues.extend(validate_all_extensions(stj))

    return issues


# Add recovery strategies for overlapping segments
def _handle_segment_overlap(
    segment1: Segment, segment2: Segment
) -> Tuple[List[ValidationIssue], Optional[Segment]]:
    """Handle overlapping segments with recovery strategies.

    Implements recovery strategies for overlapping segments according to STJ spec:
    1. Merge Strategy: Combines overlapping segments if they have compatible properties
    2. Adjust Strategy: Adjusts segment boundaries to eliminate overlap
    3. Split Strategy: Splits overlap into separate segments

    Args:
        segment1: First segment in time order
        segment2: Second segment in time order

    Returns:
        Tuple containing:
        - List of validation issues
        - Optional merged/adjusted segment if recovery was successful
    """
    issues = []

    if segment1.end <= segment2.start:
        return issues, None  # No overlap

    # Report the overlap
    issues.append(
        ValidationIssue(
            message=f"Segments overlap detected between {segment1.start}-{segment1.end} and {segment2.start}-{segment2.end}",
            severity=ValidationSeverity.ERROR,
            spec_ref="#segment-overlap",
            error_code="SEGMENT_OVERLAP",
        )
    )

    # Try recovery strategies in order:

    # 1. Merge Strategy - if segments have compatible properties
    if _can_merge_segments(segment1, segment2):
        merged = _merge_segments(segment1, segment2)
        issues.append(
            ValidationIssue(
                message="Segments merged to resolve overlap",
                severity=ValidationSeverity.INFO,
                suggestion="Review merged segment for accuracy",
                error_code="SEGMENT_MERGED",
            )
        )
        return issues, merged

    # 2. Adjust Strategy - modify end/start times
    if abs(segment1.end - segment2.start) < 0.5:  # Small overlap
        segment1.end = segment2.start
        issues.append(
            ValidationIssue(
                message="Adjusted segment boundary to resolve small overlap",
                severity=ValidationSeverity.WARNING,
                suggestion="Verify adjusted timing is acceptable",
                error_code="SEGMENT_ADJUSTED",
            )
        )
        return issues, None

    # 3. Split Strategy - create new segment for overlap
    overlap_start = segment2.start
    overlap_end = segment1.end

    segment1.end = overlap_start
    segment2.start = overlap_end

    # Create new segment for overlap region
    overlap_segment = Segment(
        text=f"{segment1.text} {segment2.text}",
        start=overlap_start,
        end=overlap_end,
        speaker_id=segment1.speaker_id,  # Use properties from first segment
        confidence=min(segment1.confidence, segment2.confidence)
        if segment1.confidence and segment2.confidence
        else None,
    )

    issues.append(
        ValidationIssue(
            message="Created new segment for overlap region",
            severity=ValidationSeverity.WARNING,
            suggestion="Review split segments and overlap handling",
            error_code="SEGMENT_SPLIT",
        )
    )

    return issues, overlap_segment


def _can_merge_segments(segment1: Segment, segment2: Segment) -> bool:
    """Check if two segments can be safely merged."""
    return (
        segment1.speaker_id == segment2.speaker_id
        and segment1.style_id == segment2.style_id
        and segment1.language == segment2.language
    )


def _merge_segments(segment1: Segment, segment2: Segment) -> Segment:
    """Merge two overlapping segments into one."""
    return Segment(
        text=f"{segment1.text} {segment2.text}",
        start=min(segment1.start, segment2.start),
        end=max(segment1.end, segment2.end),
        speaker_id=segment1.speaker_id,
        style_id=segment1.style_id,
        language=segment1.language,
        confidence=min(segment1.confidence, segment2.confidence)
        if segment1.confidence and segment2.confidence
        else None,
        word_timing_mode=WordTimingMode.PARTIAL
        if segment1.words or segment2.words
        else None,
        words=_merge_word_lists(segment1.words, segment2.words)
        if segment1.words and segment2.words
        else None,
    )


def _merge_word_lists(words1: List[Word], words2: List[Word]) -> List[Word]:
    """Merge two lists of words, preserving timing where possible."""
    if not words1 or not words2:
        return words1 or words2

    merged = []
    # Add words with timing info
    for word in words1 + words2:
        if word.start is not None and word.end is not None:
            merged.append(word)

    # Sort by start time
    merged.sort(key=lambda w: w.start if w.start is not None else float("inf"))
    return merged
