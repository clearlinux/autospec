========
Autospec
========

autospec is a tool to assist in the automated creation and maintainence
of RPM packaging. It will continuously run updated builds based on new
information discovered from build failures, until it has a complete and
valid .spec file. The tool makes use of mock to achieve this.

License
=======
autospec is available under the terms of the GPL, version 3.0

Copyright (C) 2015 Intel Corporation


Configuration of autospec
=========================
autospec is configured by means of a simple INI-style configuration file.
The default location of this file is assumed to be ``common/autospec.conf``,
relative to the directory in which autospec is executed.

Example ``autospec.conf`` file::

    [autospec]
    git = git@someurl.com/%(NAME)s
    license_fetch = http://yourhost/hash.php
    license_show = http://yourhost/showone.php?hash=%(HASH)s
    upstream = http://yourhost/tarballs/%(HASH)s/%(NAME)s


**git**
    The upstream git repository URL base

**license_fetch**
    Optional URL to use for scanning license files

**license_show**
    Optional URL to interact with online license checker

**upstream**
    Base URL for stored upstream tarballs

Synopsis
========

Usage: ``python3 autospec.py [options] URL``


-h, --help                                      show help message and exit
-g, --skip-git                                  Don't commit result to git
-n NAME, --name NAME                            Override the package name
-a ARCHIVES, --archives ARCHIVES
                                                tarball URLs for additional source archives and a
                                                location for the sources to be extacted to (e.g.
                                                http://example.com/downloads/dependency.tar.gz
                                                /directory/relative/to/extract/root )
-l, --license-only                              Only scan for license files
-b, --skip-bump                                 Don't bump release number
-c CONFIG, --config CONFIG                      Set configuration file to use
-t DIRECTORY --target DIRECTORY                 Set location to create or use



Requirements
=============

In order to run correctly, ``autospec`` requires the following components:

 * python3
 * correctly configured mock

If ``autospec`` is not configured to use a license server, then you will
need a ``common/licenses`` file -  which should be an up to date list of
licenses to facilitate automatic license detection during the scan of a
tarball. For correctness, license names should be in the SPDX identifier
format. Each line in the file constitutes a license definition, for example::

    750b9d9cc986bfc80b47c9672c48ca615cac0c87 | BSD-3-Clause
    175e59be229a5bedc6be93e958a970385bb04a62 | Apache-2.0
    794a893e510ca5c15c9c97a609ce47b0df74fc1a | BSD-2-Clause


Control files
==============

It is possible to influence precisely how autospec will behave in order to
gain fine control over the build itself. These files may be used to alter
the default behaviour of the configure routine, to blacklist build dependencies
from being automatically added, and such.

These files are expected to live in same directory that the resulting ``.spec``
will live.

Common files
------------

**release**

    This file contains the current release number that will be used in the
    ``.spec``. This is also bumped and generated on existing and new packages,
    respectively. This results in less manual work via automatic management.

**$package.license**

    In certain cases, the package license may not be automatically discovered.
    In this instance, ``autospec`` will exit with an error. Update this file
    to contain the valid SPDX identifier for any license(s) for the package,
    replacing ``$package`` in the filename with the actual package name.

Controlling dependencies
-------------------------

**buildreq_add**

    Each line in the file provides the name of a package to add
    as a build dependency to the ``.spec``.

**pkgconfig_add**

    Each line in the file is assumed to be a pkgconfig() build dependency.
    Add the pkg-config names here, as ``autospec`` will automatically transform
    the names into their ``pkgconfig($name)`` style when generating the ``.spec``.

**buildreq_ban**

    Each line in the file is a build dependency that under no circumstance
    should be automatically added to the build dependencies. This is useful
    to block automatic configuration routines adding undesired functionality,
    or to omit any automatically discovered dependencies during tarball scanning.

**pkgconfig_ban**

    Each line in this file is a pkgconfig() build dependency that should not
    be added automatically to the build, much the same as ``buildreq_ban``.
    As with ``pkgconfig_add``, these names are automatically transformed by
    ``autospec`` into their correct ``pkgconfig($name))`` style.


Controlling the build process
------------------------------

**configure**

    This file contains configuration flags to pass to the ``%configure``
    macro for autotools based tarballs. As an example, adding ``--disable-static``
    to ``./configure`` for an autootools based tarball would result in
    ``%configure --disable-static`` being emitted in the ``.spec``.

**cmake_args**

    This file contains arguments that should be passed to the ``%cmake``
    macro for CMake based tarballs. As an example, adding ``-DUSE_LIB64=ON`` to
    ``./cmake_args`` would result in ``%cmake -DUSE_LIB64=ON`` being emitted
    in the ``.spec``.

**broken_parallel_build**

    This option is set in the ``options.conf`` file described below. If this
    option is set, then parallelisation will be disabled in the build.
    This usually means that ``%{?_smp_mflags}`` will not be passed to ``make``

**make_args**

    The contents of this file are appended to the ``make`` invocation. This
    may be useful for passing arguments to ``make``, i.e. ``make TOOLDIR=/usr``

**make_install_args**

    Much like ``make_args``, this will pass arguments to the ``make install``
    macro in the ``.spec``

**make_install_append**

    Additional actions that should take place after the ``make install`` step
    has completed. This will be placed in the resulting ``.spec``, and is used
    for situations where fine-grained control is required.

**install_macro**

    The contents of this file be used instead of the automatically detected
    ``install`` routine, i.e. use this if ``%make_install`` is insufficient.

**subdir**

    Not all packages have their ``Makefile``'s available in the root of the tarball.
    An example of this may be cross-platform projects that split Makefile's into
    the ``unix`` subdirectory. Set the name in this file and the ``.spec`` will
    emit the correct ``pushd`` and ``popd`` lines to utilise these directories
    for each step in the build.

**build_pattern**

    In certain situations, the automatically detected build pattern may not
    work for the given package. This one line file allows you to override the
    build pattern that ``autospec`` will use. The supported build_pattern types are:

        - configure: Traditional ``%configure`` autotools route
        - configure_ac: Like ``configure, but performs ``%reconfigure`` to regenerate ``./configure``
        - autogen: Similar to ``configure_ac`` but uses the existing ``./autogen.sh`` instead of ``%reconfigure``
        - distutils: Only build the Pythonic package with Python 2
        - distutils3: Only build the Pythonic package with Python 3
        - distutils23: Build the Pythonic package using both Python 2 and Python 3

**series**

    This file contains a list of patches to apply during the build, using the ``%patch``
    macro. As such it is affected by ``-p1`` style modifiers.

**golang_libpath**

    When building go packages, the go import path will be guessed automatically
    (e.g. building ``https://github.com/go-yaml/yaml/`` would get
    ``github.com/go-yaml/yaml``). While this is handy, it's not always correct
    (in the previous example, the correct import path should be
    ``gopkg.in/yaml.v2``). This could be easily fixed by placing
    ``gopkg.in/yaml.v`` in this file, changing where the go bits will be placed.

Controlling files and subpackages
---------------------------------

**excludes**

    This file is used to generate ``%exclude`` lines in the ``.spec``. This
    is useful for omitting files from being included in the resulting package.
    Each line in the file should be a full path name.

**keepstatic**

    This option is set in the ``options.conf`` file described below. If this
    option is set, then ``%define keepstatic 1`` is emitted in the ``.spec``.
    As a result, any static archive (``.a``) files will not be removed by rpmbuild.

**extras**

    Each line in the file should be a full path within the resulting package,
    that you wish to be placed into an automatic ``-extras`` subpackage. This
    allows one to keep the main package slim and split out optional functionality
    or files.

**no_autostart**

    This option is set in the ``options.conf`` file described below. If this
    option is set the autostart subpackage (which contains all files matching
    /usr/lib/systemd/system/*.target.wants/) will not be required by the base package.

**setuid**

    Each line in this file should contain the full path to a binary in the resulting
    build that should have the ``setuid`` attribute set with the ``%attr`` macro.

**attrs**

    Each line in this file should be a full ``%attr`` macro line that will be included
    in the ``.spec`` to have fine-grained control over the permissions and ownership
    of files in the package.


Controlling test suites
-----------------------

By default, ``autospec`` will attempt to detect potential test suites that
can be run in the ``%check`` portion of the ``.spec``.

**skip_test_suite**

    If this file exists, ``autospec`` will not emit any ``%check`` functionality.
    This file has been deprecated and will be removed during an autospec run and
    replaced with a ``skip_tests`` option in ``options.conf``.

**unit_tests_must_pass**

    This file is automatically created upon successful completion of a package build.
    This allows one to identify regressions in test failures when updating or
    altering a package.
    ``autospec`` will fail a package that does not pass it's test suite if this file
    exists.

**make_check_command**

    Override or set the command to use in the ``%check`` portion of the ``.spec``.
    This may be useful when a package uses a custom test suite, or requires
    additional work/parameters, to work correctly.

**allow_test_failures**

    This option is set in the ``options.conf`` file described below. If this
    option is set it will allow test failures, and will still emit the
    ``%check`` code in a way that allows the build to continue.


Controlling flags and optimisation
----------------------------------

Further control of the build can be achieved through the use of the
``options.conf`` file. If this file does not exist it is created by autospec.
Autospec generates this file based on the presence of deprecated 'file-exists'
files, then removes the deprecated files.

The options that can be set in ``options.conf`` are as follows:

**asneeded**

    If this is option set, the ``.spec`` will disable the LD_AS_NEEDED variable.
    Supporting binutils (such as found in Clear Linux Project for Intel Architecture)
    will then revert to their normal behaviour, instead of enforcing ``-Wl,-as-needed``
    in the most correct sense.

**optimize_size**

    If this option is set, the ``CFLAGS/LDFLAGS`` will be extended to build
    the package optimised for *size*, and not for *speed*. Use this when
    size is more critical than performance.

**funroll-loops**

    If this option is set, the ``CFLAGS/LDFLAGS`` will be extended to build
    the package optimised for *speed*. In short this where speed is of
    paramount importance, and will use ``-03`` by default.

**insecure_build**

    If this option is set, the ``CFLAGS/LDFLAGS`` will be **replaced**, using
    the smallest ``-02`` based generic flags possible. This is useful for
    operating systems employing heavy optimisations or full RELRO by default.

**pgo**

    If this option is set, the ``CFLAGS/CXXFLAGS`` will be extended to build
    the package with profile-guided optimization data. It will add ``-O3``,
    ``-fprofile-use``, ``-fprofile-correction`` and ``-fprofile-dir=pgo``.

**use_lto**

    If this option is set, link time optimization is enabled for the build.

**use_avx2**

    If this option is set, a second set of libraries, for AVX2, is built.

**fast-math**

    If this option is set, -ffast-math is passed to the compiler.

**broken_c++**

    If this option is set, flags are extended with -std=gnu++98.

**allow_test_failures**

    If this option is set it will allow test failures, and will still emit the
    ``%check`` code in a way that allows the build to continue.

**no_autostart**

    If this option is set the autostart subpackage (which contains all files matching
    /usr/lib/systemd/system/*.target.wants/) will not be required by the base package.

**conservative_flags**

    If this option is set autospec will set conservative build flags

**use_clang**

    If this option is set autospec will utilize clang. This unsets the
    funroll-loops optimization if it is set.

**keepstatic**

    If this option is set, then ``%define keepstatic 1`` is emitted in the ``.spec``.
    As a result, any static archive (``.a``) files will not be removed by rpmbuild.

**32bit**

    This option will trigger the creation of 32-bit libraries for a 32-bit
    build.


Name and version resolution
===========================

``autospec`` will attempt to use a number of patterns to determine the name
and version of the package by examining the URL. For most tarballs this is
simple, if they are of the format ``$name-$version.tar.$compression``.

For websites such as ``bitbucket`` or ``GitHub``, using ``get$`` and ``v$.tar.*``
style links, the project name itself is used from the URL and the version is
determined by stripping down the tag.

CPAN Perl packages, R packages, and rubygems.org rubygems are automatically
prefixed with their language name: ``perl-``, ``R-`` and ``rubygem-`` respectively.

When these automated detections are not desirable, it is possible to override
these with the ``--name`` flag when invoking ``autospec``


Automatic license server support
================================
``autospec`` can optionally talk to a license server instead of checking
local hashsum files, which enables greater coverage for license detection.
The URL set in ``license_fetch`` is expected to be a simple script that
talks HTTP.

This URL should accept ``POST`` requests with the following keys:

**hash**
    Contains the SHA-1 hash of the potential license file being checked.

**package**
    The name of the package being examined

**text**
    The contents of the potential license file

Implementations return a *plain text* response with the SPDX identifier
of the license, if known. An empty response is assumed to mean that this
license is unknown, in which case ``autospec`` will emit the ``license_show``
URL. The implementation should show the now-stored license file via a
web page, and enable a human to make a decision on the license. This is
then stored internally, allowing future requests to automatically know
the license type when this hash is encounted again. 
