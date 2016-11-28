================
Autospec Testing
================

Functional
==========

Autospec has limited functional testing capabilities that can be invoked by
running ``make test_autospec`` from the root of the autospec directory.

The tests first create a tarball of each source directory within
``tests/testfiles/`` and run autospec against each. Each package is handled in
its own thread, so the total time of the test run is equivalent to the total
time of the longest autospec run.

Once the build is complete, the output of autospec and the resulting spec file
are searched for terms defined in a special ``expectations.py`` file within the
test source directories. Several terms can be defined in ``expectations.py``
which determine what will be tested after a successful autospec run.

- buildreqs (list of strings) - build requirements expected to be detected by
  autospec.

- license (string) - name of the license to be detected by autospec.

- output_strings (list of strings) - strings expected to be in the output of the
  autospec run.

- specfile (string) - this string is read in from the ``spec-expectations``
  file, which contains the exact text of the specfile expected to be generated
  from the autospec run. If there are discrepancies between the generated and
  expected spec files a diff will be displayed in the results.

- conffile (string) - this string is read in from the ``conf-expectations``
  file, which contains the exact text of the ``options.conf`` file expected to
  be generated (or changed, or left unchanged) from the autospec run. If there
  are discrepancies between the generated and expected ``options.conf`` files a
  diff will be displayed in the results.

There is also a directory within the source file directory called
``autospecdir`` that contains the package-specific configuration files used by
the autospec run. Here you can set specific configuration files such as the
deprecated boolean configs for testing ``options.conf`` generation, or
``buildreq_add`` to test build requirement detection.

If an autospec build fails for some reason, the build log will be placed in
``tests/testfiles/results/<pkgname>.log``. Any old logs are removed at the
beginning of a test run to avoid any indication that a build failed when it did
not.

The overall test directory structure looks like this:

::

  tests/
      test_autospec.py     # functional tests
      pkg_integrity.py     # unit tests
      testfiles/
          <source1>/
              expectations.py
              spec-expectations
              conf-expectations
              <source files>
              autospecdir/
                  <configuration files for autospec>
          <source2>/
              ...
          ...
          results/
              <may contain failed build log>


Unit
====

One autospec module, ``pkg_integrity.py`` also has unit testing available via
``make test_pkg_integrity``.
