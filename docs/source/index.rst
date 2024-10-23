Welcome to STJLib's Documentation
=================================

**STJLib** is a Python library for working with Standard Transcription JSON (STJ) format files.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   usage
   api
   advanced
   modules

Features
--------
* Load and save STJ files
* Validate STJ data according to specification
* Access and manipulate metadata and transcript data
* Flexible error handling and validation reporting

Quick Start
-----------
Install STJLib:

.. code-block:: bash

   pip install stjlib

Basic usage:

.. code-block:: python

   from stjlib import StandardTranscriptionJSON

   # Load an STJ file
   stj = StandardTranscriptionJSON.from_file('path/to/file.stj.json')

   # Access metadata and transcript
   print(stj.metadata)
   print(stj.transcript)

For more detailed information, check out the :doc:`usage` guide.