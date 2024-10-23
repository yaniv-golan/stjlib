Advanced Usage
==============

Custom Validation
-----------------
Learn how to implement custom validation rules:

.. code-block:: python

   from stjlib import StandardTranscriptionJSON, ValidationIssue

   class CustomSTJ(StandardTranscriptionJSON):
       def validate(self, raise_exception: bool = True):
           issues = super().validate(raise_exception=False)
           
           # Add custom validation
           for segment in self.transcript.segments:
               if len(segment.text) > 1000:
                   issues.append(ValidationIssue(
                       message="Segment text too long",
                       location=f"Segment starting at {segment.start}"
                   ))
           
           if issues and raise_exception:
               raise ValidationError(issues)
           return issues

Working with Additional Info
----------------------------
Examples of using the additional_info fields:

.. code-block:: python

   segment = Segment(
       start=0.0,
       end=1.0,
       text="Hello",
       additional_info={
           "confidence_scores": [0.9, 0.8, 0.95],
           "speaker_gender": "female"
       }
   )