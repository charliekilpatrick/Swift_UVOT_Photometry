#######################################
Welcome to SwiftPhotom's documentation!
#######################################

Swift UVOT Photometry is a Python package for aperture and template-subtracted
photometry on Swift UVOT data. It runs HEASoft commands from Python and is
aimed at transient studies. The package is built from this repository and
documented with NumPy-style docstrings where applicable.

Installing SwiftPhotom
======================

**Requirements:** Python 3.11 or 3.12, and HEASoft (Swift/UVOT). See the
`README <https://github.com/charliekilpatrick/Swift_UVOT_Photometry>`_ for
Conda (recommended) and manual HEASoft setup.

From the repository root (after cloning):

.. code-block:: bash

   pip install .

Editable install with optional docs and test dependencies:

.. code-block:: bash

   pip install -e ".[doc,dev]"

Package structure and documentation
-----------------------------------

- **SwiftPhotom/** — main package: ``commands`` (HEASoft wrappers), ``uvot``
  (filters, aspect correction, products, photometry), ``errors``, ``help``
  (CLI strings).
- **bin/** — command-line entry points; see :ref:`scripts`.

Please consult these pages for more details:

.. toctree::
   :maxdepth: 1

   scripts
   inputs/index
   extraction/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
