# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

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
    'sphinx.ext.napoleon'
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('../..'))

# Debugging information
print("Current working directory:", os.getcwd())
print("Python path:", sys.path)

try:
    import stjlib
    print("Successfully imported stjlib")
except ImportError as e:
    print("Failed to import stjlib:", str(e))
