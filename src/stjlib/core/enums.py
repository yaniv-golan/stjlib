# stjlib/core/enums.py

"""STJLib enumerations for Standard Transcription JSON Format.

This module provides enumeration classes that define valid values for
various STJ format fields. These enums help ensure data consistency
and provide type safety for STJ data structures.

Key Features:
    * String-based enums for JSON compatibility
    * Type safety for STJ fields
    * Clear value definitions
    * Documentation of valid options
    * Integration with validation system

Available Enums:
    * WordTimingMode - Defines word timing completeness levels

Example:
    ```python
    from stjlib.core.enums import WordTimingMode

    # Use enum in segment definition
    segment = Segment(
        text="Hello world",
        word_timing_mode=WordTimingMode.COMPLETE,
        words=[
            Word(text="Hello", start=0.0, end=0.5),
            Word(text="world", start=0.6, end=1.0)
        ]
    )

    # Compare timing modes
    if segment.word_timing_mode == WordTimingMode.COMPLETE:
        print("All words must have timing")
    ```

Note:
    All enums use string values to maintain JSON compatibility when
    serializing/deserializing STJ data. The string values are defined
    by the STJ specification.
"""

from enum import Enum


class WordTimingMode(Enum):
    """Word timing modes for transcript segments.

    This enum defines the possible modes for word-level timing information
    within a segment. It indicates the completeness of timing data for words
    in the segment.

    Values:
        COMPLETE: All words in the segment have timing information.
            Use this when every word has start and end times.
        PARTIAL: Some words in the segment have timing information.
            Use this when only some words have timing data.
        NONE: No words in the segment have timing information.
            Use this when words array exists but has no timing data.

    Example:
        ```python
        # Create a segment with complete word timing
        segment = Segment(
            text="Hello world",
            word_timing_mode=WordTimingMode.COMPLETE,
            words=[
                Word(text="Hello", start=0.0, end=0.5),
                Word(text="world", start=0.6, end=1.0)
            ]
        )

        # Create a segment with partial word timing
        segment = Segment(
            text="Hello world",
            word_timing_mode=WordTimingMode.PARTIAL,
            words=[
                Word(text="Hello", start=0.0, end=0.5),
                Word(text="world")  # No timing for this word
            ]
        )

        # Create a segment with no word timing
        segment = Segment(
            text="Hello world",
            word_timing_mode=WordTimingMode.NONE,
            words=[
                Word(text="Hello"),
                Word(text="world")
            ]
        )
        ```

    Note:
        - The word_timing_mode field affects validation requirements
        - COMPLETE mode requires all words to have timing data
        - PARTIAL mode allows mixed timing presence
        - NONE mode requires no timing data
        - The mode must match the actual timing data presence
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"
