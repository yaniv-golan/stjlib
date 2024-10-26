"""
STJLib: Standard Transcription JSON Format Handler

A comprehensive implementation of the Standard Transcription JSON (STJ) format
for representing transcribed audio and video data.

This module provides functionality to work with STJ format including loading,
saving, validation, and manipulation of transcript data.

Features:
    * Load and save STJ files with robust error handling
    * Validate STJ data against the official specification
    * Access and modify transcript content, metadata, and speaker information
    * Full support for word-level timing and confidence scores

Example:
    Basic usage of loading and accessing STJ data::

        from stjlib import StandardTranscriptionJSON
        
        # Load and validate an STJ file
        stj = StandardTranscriptionJSON.from_file('transcript.stj.json', validate=True)
        
        # Access transcript data
        for segment in stj.transcript.segments:
            print(f"{segment.start:.2f}-{segment.end:.2f}: {segment.text}")

Note:
    For detailed information about the STJ format, see:
    https://github.com/yaniv-golan/STJ

Version:
    0.3.0
"""

import json
from typing import Any, Dict, List, Optional

from .core.data_classes import (
    Metadata,
    Transcript,
)
from .validation import (
    ValidationIssue,
    validate_stj,
)


class STJError(Exception):
    """Base class for exceptions in the STJ module."""

    pass


class ValidationError(STJError):
    """Exception raised when STJ validation fails.

    This exception contains a list of specific validation issues that were found
    during STJ data validation.

    Args:
        issues: List of validation issues found during validation.

    Attributes:
        issues: List of ValidationIssue objects containing problem details.

    Example:
        Error handling with validation issues::

            try:
                stj.validate()
            except ValidationError as e:
                print("Validation failed:")
                for issue in e.issues:
                    print(f"Location: {issue.location}")
                    print(f"Problem: {issue.message}")
    """

    def __init__(self, issues: List[ValidationIssue]):
        self.issues = issues
        super().__init__(self.__str__())

    def __str__(self) -> str:
        """Returns a string representation of the validation errors.

        Returns:
            A formatted string containing all validation issues.
        """
        return "Validation failed with the following issues:\n" + "\n".join(
            str(issue) for issue in self.issues
        )


class StandardTranscriptionJSON:
    """Handler for Standard Transcription JSON (STJ) format.

    This class provides a complete interface for working with STJ format data,
    including creation, validation, and manipulation of transcription content.

    Args:
        metadata: Metadata information for the transcription.
        transcript: The transcript data containing segments and words.

    Attributes:
        metadata: Metadata object containing file and transcription information.
        transcript: Transcript object containing the actual transcription data.
    """

    def __init__(self, metadata: Metadata, transcript: Transcript):
        self.metadata = metadata
        self.transcript = transcript

    def validate(self, raise_exception: bool = True) -> Optional[List[ValidationIssue]]:
        """Validates the STJ data according to specification requirements.

        Args:
            raise_exception: If True, raises ValidationError when issues are found.

        Returns:
            List of validation issues if raise_exception is False, None otherwise.

        Raises:
            ValidationError: If validation issues are found and raise_exception is True.
        """
        issues = validate_stj(self.metadata, self.transcript)

        if issues and raise_exception:
            raise ValidationError(issues)
        return issues

    @classmethod
    def from_file(
        cls, filename: str, validate: bool = False, raise_exception: bool = True
    ) -> "StandardTranscriptionJSON":
        """Creates an STJ instance from a JSON file.

        Args:
            filename: Path to the JSON file.
            validate: If True, performs validation after loading.
            raise_exception: If True and validation issues are found, raises ValidationError.

        Returns:
            A new StandardTranscriptionJSON instance.

        Raises:
            FileNotFoundError: If the specified file doesn't exist.
            json.JSONDecodeError: If the JSON is invalid.
            STJError: For unexpected errors during loading.
            ValidationError: If validation fails and raise_exception is True.
        """
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
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
    def from_dict(
        cls, data: Dict[str, Any], validate: bool = False
    ) -> "StandardTranscriptionJSON":
        """Creates a StandardTranscriptionJSON object from a dictionary.

        Args:
            data: Dictionary containing STJ data.
            validate: If True, validates the data after deserialization.

        Returns:
            A new StandardTranscriptionJSON instance.

        Raises:
            ValidationError: If validate is True and validation fails.
        """
        metadata = Metadata.from_dict(data.get("metadata", {}))
        transcript = Transcript.from_dict(data.get("transcript", {}))
        stj = cls(metadata=metadata, transcript=transcript)

        if validate:
            stj.validate()

        return stj

    def to_file(self, filename: str) -> None:
        """Saves the STJ instance to a JSON file.

        Args:
            filename: Path where the JSON file should be saved.

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
        """Converts the STJ instance to a dictionary.

        Returns:
            Dictionary representation of the STJ instance.
        """
        return {
            "metadata": self.metadata.to_dict(),
            "transcript": self.transcript.to_dict(),
        }
