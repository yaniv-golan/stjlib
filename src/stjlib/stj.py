"""
STJLib: Standard Transcription JSON Format Handler

A comprehensive implementation of the Standard Transcription JSON (STJ) format
for representing transcribed audio and video data.

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

    # Load and validate an STJ file
    stj = StandardTranscriptionJSON.from_file(
        'transcript.stj.json',
        validate=True
    )

    # Access transcript content
    for segment in stj.transcript.segments:
        print(f"{segment.start:.2f}-{segment.end:.2f}: {segment.text}")
        if segment.speaker_id:
            print(f"Speaker: {segment.speaker_id}")

    # Modify content
    stj.transcript.segments[0].text = "Updated text"

    # Save changes
    stj.to_file('updated.stj.json')
    ```

Note:
    This implementation follows version 0.6.x of the STJ specification.
    For detailed format information, see: https://github.com/yaniv-golan/STJ

Version: 0.4.0
"""

import json
from typing import Any, Dict, List, Optional

from .core.data_classes import (
    STJ,
    Metadata,
    Transcript,
)
from .validation import (
    ValidationIssue,
    validate_stj,
)


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

    This class provides the main interface for working with STJ documents,
    including loading, saving, validation, and access to transcript content.

    Attributes:
        stj (STJ): The root STJ object containing all transcript data

    Example:
        ```python
        # Create from file
        stj = StandardTranscriptionJSON.from_file(
            "transcript.json",
            validate=True
        )

        # Access content
        print(f"Version: {stj.version}")
        if stj.metadata:
            print(f"Created: {stj.metadata.created_at}")

        # Validate
        issues = stj.validate(raise_exception=False)
        if issues:
            print("Validation issues found:")
            for issue in issues:
                print(issue)

        # Save changes
        stj.to_file("output.json")
        ```

    Note:
        - All modifications are made directly to the internal STJ object
        - Validation can be performed at any time
        - File operations use UTF-8 encoding
    """

    def __init__(self, stj: STJ):
        """Initialize with an STJ object.

        Args:
            stj (STJ): The root STJ object containing all transcript data
        """
        self.stj = stj

    def validate(self, raise_exception: bool = True) -> Optional[List[ValidationIssue]]:
        """Validates the STJ data according to specification requirements.

        Performs comprehensive validation of the STJ data structure,
        checking all requirements from the specification.

        Args:
            raise_exception (bool): If True, raises ValidationError for any issues.
                If False, returns the list of issues.

        Returns:
            Optional[List[ValidationIssue]]: List of validation issues if
                raise_exception is False and issues were found. None otherwise.

        Raises:
            ValidationError: If validation fails and raise_exception is True.

        Example:
            ```python
            # Validate and handle issues
            try:
                stj.validate()
                print("Validation passed")
            except ValidationError as e:
                print("Validation failed:")
                for issue in e.issues:
                    print(issue)

            # Get issues without raising
            issues = stj.validate(raise_exception=False)
            if issues:
                print("Found validation issues")
            ```
        """
        issues = validate_stj(self.stj)

        if issues and raise_exception:
            raise ValidationError(issues)
        return issues

    @classmethod
    def from_file(
        cls, filename: str, validate: bool = False, raise_exception: bool = True
    ) -> "StandardTranscriptionJSON":
        """Creates a StandardTranscriptionJSON instance from a JSON file.

        Loads and optionally validates an STJ document from a JSON file.

        Args:
            filename (str): Path to the JSON file to load
            validate (bool): Whether to validate the loaded data
            raise_exception (bool): Whether to raise exceptions for validation issues

        Returns:
            StandardTranscriptionJSON: New instance with loaded data

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
            ValidationError: If validation fails and raise_exception is True
            STJError: For other STJ-related errors

        Example:
            ```python
            # Load and validate
            try:
                stj = StandardTranscriptionJSON.from_file(
                    "transcript.json",
                    validate=True
                )
            except FileNotFoundError:
                print("File not found")
            except json.JSONDecodeError:
                print("Invalid JSON format")
            except ValidationError as e:
                print("Validation failed:", e)
            ```
        """
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            stj_instance = cls.from_dict(
                data, validate=validate, raise_exception=raise_exception
            )
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
        cls, data: Dict[str, Any], validate: bool = False, raise_exception: bool = True
    ) -> "StandardTranscriptionJSON":
        """Creates a StandardTranscriptionJSON object from a dictionary.

        Converts a dictionary containing STJ data into a StandardTranscriptionJSON
        instance, optionally validating the data.

        Args:
            data (Dict[str, Any]): Dictionary containing STJ data
            validate (bool): Whether to validate the data
            raise_exception (bool): Whether to raise exceptions for validation issues

        Returns:
            StandardTranscriptionJSON: New instance with loaded data

        Raises:
            ValidationError: If validation fails or data structure is invalid

        Example:
            ```python
            # Create from dictionary
            data = {
                "stj": {
                    "version": "0.6.0",
                    "transcript": {
                        "segments": [
                            {"text": "Hello world", "start": 0.0, "end": 1.5}
                        ]
                    }
                }
            }
            stj = StandardTranscriptionJSON.from_dict(data, validate=True)
            ```
        """
        if not isinstance(data, dict):
            raise ValidationError([ValidationIssue("STJ data must be a dictionary")])

        stj_data = data.get("stj")
        if not isinstance(stj_data, dict):
            raise ValidationError(
                [ValidationIssue("STJ data must contain a 'stj' root object")]
            )

        version = stj_data.get("version")
        if not version:
            raise ValidationError([ValidationIssue("STJ version is required")])

        # Extract known fields
        known_fields = {"version", "metadata", "transcript"}
        additional_fields = {k: v for k, v in stj_data.items() if k not in known_fields}

        # Create Metadata and Transcript instances
        metadata = (
            Metadata.from_dict(stj_data.get("metadata"))
            if "metadata" in stj_data
            else None
        )
        transcript = Transcript.from_dict(stj_data.get("transcript"))

        # Create the STJ instance with additional fields
        stj = STJ(
            version=version,
            metadata=metadata,
            transcript=transcript,
            _additional_fields=additional_fields,
        )

        # Create the StandardTranscriptionJSON instance
        stj_handler = cls(stj=stj)

        if validate:
            stj_handler.validate(raise_exception=raise_exception)

        return stj_handler

    def to_file(self, filename: str) -> None:
        """Saves the STJ instance to a JSON file.

        Serializes the STJ data to JSON format and writes it to a file.

        Args:
            filename (str): Path where the JSON file should be written

        Raises:
            IOError: If there's an error writing to the file

        Example:
            ```python
            try:
                stj.to_file("output.stj.json")
                print("File saved successfully")
            except IOError as e:
                print(f"Error saving file: {e}")
            ```
        """
        data = self.to_dict()
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            raise IOError(f"Error writing to file {filename}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the STJ object to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the STJ data

        Example:
            ```python
            # Convert to dictionary
            data = stj.to_dict()
            print(json.dumps(data, indent=2))
            ```
        """
        return {"stj": self.stj.to_dict()}

    @property
    def metadata(self) -> Optional[Metadata]:
        """Access to the STJ metadata.

        Returns:
            Optional[Metadata]: The metadata object or None if not present
        """
        return self.stj.metadata

    @property
    def transcript(self) -> Transcript:
        """Access to the STJ transcript.

        Returns:
            Transcript: The transcript object containing all content
        """
        return self.stj.transcript

    @property
    def version(self) -> str:
        """Access to the STJ version.

        Returns:
            str: The STJ specification version
        """
        return self.stj.version
