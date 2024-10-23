Usage Guide
===========

Basic Usage
-----------
Here's how to use STJLib for common tasks:

Loading STJ Files
~~~~~~~~~~~~~~~~~
.. code-block:: python

   from stjlib import StandardTranscriptionJSON

   # Load without validation
   stj = StandardTranscriptionJSON.from_file('file.stj.json')

   # Load with validation
   stj = StandardTranscriptionJSON.from_file('file.stj.json', validate=True)

Validation
~~~~~~~~~~
.. code-block:: python

   # Validate and get issues
   issues = stj.validate(raise_exception=False)
   for issue in issues:
       print(issue)

   # Validate and raise exception on issues
   try:
       stj.validate(raise_exception=True)
   except ValidationError as e:
       print("Validation failed:", e)

Working with Metadata
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Access metadata
   print(stj.metadata.transcriber.name)
   print(stj.metadata.created_at)

   # Modify metadata
   stj.metadata.confidence_threshold = 0.8