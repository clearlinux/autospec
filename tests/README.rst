================
Autospec Testing
================

Code Style
==========

Autospec changes are scanned to vet code style issues with the ``flake8`` tool.
To check for issues, run ``make check`` from the root of the autospec source
tree, which executes ``flake8`` with appropriate arguments.

Unit
====

Autospec ships with several test modules that correspond to individual modules
from the toplevel ``autospec`` directory.

Each module can be tested in isolation by running ``make test_<MODULE>``, where
``<MODULE>`` corresponds to the module name. For example, ``make
test_pkg_integrity`` runs unit tests for the ``pkg_integrity.py`` module.

To run *all* unit tests, run ``make unittests``. If all tests pass, a code
coverage report is also generated.
