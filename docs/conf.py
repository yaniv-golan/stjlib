# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import sphinx_rtd_theme

# Add debugging information
print("Current working directory:", os.getcwd())
print("Python path before:", sys.path)

# Adjust the path to your source code
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, src_path)

print("Added to Python path:", src_path)
print("Python path after:", sys.path)

# Try to import your module
try:
    import stjlib
    print("Successfully imported stjlib")
except ImportError as e:
    print("Failed to import stjlib:", str(e))

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
    'sphinx_rtd_theme',
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
# html_static_path = ['_static']  # Commented out if _static directory doesn't exist
