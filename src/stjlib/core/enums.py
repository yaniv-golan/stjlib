# stjlib/core/enums.py

"""STJLib enumerations for Standard Transcription JSON Format.

This module provides enumeration classes that define valid values for
various STJ format fields. These enums help ensure data consistency
and provide type safety for STJ data structures.

The module includes:
    * WordTimingMode - Defines word timing completeness levels
    * WordDuration - Defines special word duration cases

Note:
    All enums use string values to maintain JSON compatibility.
"""

from enum import Enum


class WordTimingMode(Enum):
    """Word timing modes for transcript segments.

    This enum defines the possible modes for word-level timing information
    within a segment. It indicates whether all, some, or no words have
    timing data.

    Args:
        value: String value representing the timing mode.

    Attributes:
        COMPLETE: All words have timing information.
        PARTIAL: Some words have timing information.
        NONE: No words have timing information.

    Example:
        >>> mode = WordTimingMode.COMPLETE
        >>> print(mode)
        WordTimingMode.COMPLETE
        >>> print(mode.value)
        'complete'

    Note:
        The timing mode affects validation requirements for word timing data
        within segments.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"


class WordDuration(Enum):
    """Special duration types for words.

    This enum is used to indicate special duration cases for words,
    particularly zero-duration words that represent instantaneous events
    or markers in the transcript.

    Args:
        value: String value representing the duration type.

    Attributes:
        ZERO: Represents a word with zero duration (instantaneous).

    Example:
        >>> duration = WordDuration.ZERO
        >>> print(duration)
        WordDuration.ZERO
        >>> print(duration.value)
        'zero'

    Note:
        Zero-duration words must have equal start and end times.
    """

    ZERO = "zero"
