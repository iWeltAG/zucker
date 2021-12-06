# Configuration file for the Sphinx documentation builder.

import sys
from os import path

# Project files are one level above the documentation. That folder is added to the
# Python path so that Sphinx finds it.
sys.path.insert(0, path.abspath(".."))

# General project information
project = "Zucker"
copyright = "2021, iWelt AG"
author = "Yannik Rödel <yannik.roedel@iwelt.de>"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx_rtd_theme",
]
source_suffix = {
    ".rst": "restructuredtext",
}

# HTML Output
html_theme = "sphinx_rtd_theme"

# sphinx.ext.autodoc
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration
autodoc_typehints = "signature"
autodoc_type_aliases = {
    "JsonPrimitive": "~zucker.utils.JsonPrimitive",
    "JsonType": "~zucker.utils.JsonType",
    "JsonMapping": "~zucker.utils.JsonMapping",
    "View": "~zucker.model.view.View",
    "ModuleType": "ModuleType",
}

# sphinx.ext.autosectionlabel
autosectionlabel_prefix_document = True

# sphinx.ext.intersphinx
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
