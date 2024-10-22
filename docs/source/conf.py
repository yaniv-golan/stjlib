# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import sphinx_rtd_theme

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'STJLib'
copyright = '2024, Yaniv Golan'
author = 'Yaniv Golan'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [    
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_rtd_theme'
]

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
# html_static_path = ['_static']

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('../..'))

# Debugging information
print("Python version:", sys.version)
print(f"sphinx_rtd_theme version: {sphinx_rtd_theme.__version__}")

try:
    import stjlib
    print("Successfully imported stjlib")
except ImportError as e:
    print("Failed to import stjlib:", str(e))

autodoc_type_aliases = {
    'Transcriber': 'stjlib.stj.Transcriber',
    'Source': 'stjlib.stj.Source',
    'Lang': 'iso639.Lang',
}

autodoc_typehints = 'description'

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True
