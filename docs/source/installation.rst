Installation
============

Requirements
------------
* Python 3.7 or higher
* iso639-lang>=2.5.0
* jsonschema>=4.0.0  # For STJ schema validation

File Format Support
------------------
STJLib supports the Standard Transcription JSON (STJ) format version 0.6.0 with the following file extensions:

* Primary (Recommended): ``.stjson``
* Alternative: ``.stj``
* Alternative: ``.stj.json`` (systems supporting double extensions)

The MIME type for STJ files is ``application/vnd.stj+json``. Until IANA registration is complete, 
``application/json`` may be used as a fallback.

Installing from PyPI
--------------------
The recommended way to install STJLib is via pip:

.. code-block:: bash

   pip install stjlib

Installing from Source
----------------------
To install from source:

.. code-block:: bash

   git clone https://github.com/yaniv-golan/stjlib.git
   cd stjlib
   pip install -e .
   pip install -r requirements-dev.txt  # For development dependencies