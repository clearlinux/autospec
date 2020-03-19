#!/bin/true
#
# test.py - part of autospec
# Copyright (C) 2015 Intel Corporation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Deduce and emmit the patterns for %check
#

import os
import re

import buildpattern
import buildreq
import count
import tarball
import util

tests_config = ""


def check_regression(pkg_dir, skip_tests):
    """Check the build log for test regressions using the count module."""
    if skip_tests:
        return

    result = count.parse_log(os.path.join(pkg_dir, "results/build.log"))
    titles = [('Package', 'package name', 1),
              ('Total', 'total tests', 1),
              ('Pass', 'total passing', 1),
              ('Fail', 'total failing', 0),
              ('Skip', 'tests skipped', 0),
              ('XFail', 'expected fail', 0)]
    res_str = ""
    for line in result.strip('\n').split('\n'):
        s_line = line.split(',')
        for idx, title in enumerate(titles):
            if s_line[idx]:
                if (s_line[idx] != '0') or (title[2] > 0):
                    print("{}: {}".format(title[1], s_line[idx]))
                res_str += "{} : {}\n".format(title[0], s_line[idx])

    util.write_out(os.path.join(pkg_dir, "testresults"), res_str)


def scan_for_tests(src_dir, config):
    """Scan source directory for test files and set tests_config accordingly."""
    global tests_config

    if config.config_opts.get('skip_tests') or tests_config:
        return

    makeflags = "%{?_smp_mflags} " if config.parallel_build else ""
    make_check = "make VERBOSE=1 V=1 {}check".format(makeflags)
    cmake_check = "make test"
    make_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                         "make VERBOSE=1 V=1 {}check\nmodule unload openmpi".format(makeflags)
    cmake_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                          "make test\nmodule unload openmpi"

    if config.config_opts.get('allow_test_failures'):
        make_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                             "make VERBOSE=1 V=1 {}check || :\nmodule unload openmpi".format(makeflags)
        cmake_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                              "make test || :\nmodule unload openmpi"

    perl_check = "make TEST_VERBOSE=1 test"
    setup_check = """PYTHONPATH=%{buildroot}$(python -c "import sys; print(sys.path[-1])") python setup.py test"""
    meson_check = "meson test -C builddir"
    if config.config_opts.get('allow_test_failures'):
        make_check += " || :"
        cmake_check += " || :"
        perl_check += " || :"
        setup_check += " || :"
        meson_check += " || :"

    testsuites = {
        "makecheck": make_check,
        "perlcheck": perl_check,
        "setup.py": setup_check,
        "cmake": "cd clr-build; " + cmake_check,
        "rakefile": "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix + "\nrake --trace test TESTOPTS=\"-v\"\npopd",
        "rspec": "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix + "\nrspec -I.:lib spec/\npopd",
        "meson": meson_check,
    }
    if config.config_opts.get('32bit'):
        testsuites["makecheck"] += "\ncd ../build32;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../clr-build32;\n" + cmake_check + " || :"
        testsuites["meson"] += "\ncd ../build32;\n" + meson_check + " || :"
    if config.config_opts.get('use_avx2'):
        testsuites["makecheck"] += "\ncd ../buildavx2;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../clr-build-avx2;\n" + cmake_check + " || :"
    if config.config_opts.get('use_avx512'):
        testsuites["makecheck"] += "\ncd ../buildavx512;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../clr-build-avx512;\n" + cmake_check + " || :"
    if config.config_opts.get('openmpi'):
        testsuites["makecheck"] += "\ncd ../build-openmpi;\n" + make_check_openmpi
        testsuites["cmake"] += "\ncd ../clr-build-openmpi;\n" + cmake_check_openmpi

    files = os.listdir(src_dir)

    if buildpattern.default_pattern == "cmake":
        makefile_path = os.path.join(src_dir, "CMakeLists.txt")
        if not os.path.isfile(makefile_path):
            return

        if "enable_testing" in util.open_auto(makefile_path).read():
            tests_config = testsuites["cmake"]

    elif buildpattern.default_pattern in ["cpan", "configure", "configure_ac", "autogen"] and "Makefile.in" in files:
        makefile_path = os.path.join(src_dir, "Makefile.in")
        if os.path.isfile(makefile_path):
            with util.open_auto(makefile_path, 'r') as make_fp:
                lines = make_fp.readlines()
            for line in lines:
                if line.startswith("check:"):
                    tests_config = testsuites["makecheck"]
                    break
                if line.startswith("test:"):
                    tests_config = testsuites["perlcheck"]
                    break

    elif buildpattern.default_pattern in ["configure", "configure_ac", "autogen"] and "Makefile.am" in files:
        tests_config = testsuites["makecheck"]

    elif buildpattern.default_pattern in ["cpan"] and "Makefile.PL" in files:
        tests_config = testsuites["perlcheck"]

    elif buildpattern.default_pattern == "distutils3" and "setup.py" in files:
        with util.open_auto(os.path.join(src_dir, "setup.py"), 'r') as setup_fp:
            setup_contents = setup_fp.read()

        if "test_suite" in setup_contents or "pbr=True" in setup_contents:
            tests_config = testsuites["setup.py"]

    elif buildpattern.default_pattern == "R":
        tests_config = "export _R_CHECK_FORCE_SUGGESTS_=false\n"              \
                       "R CMD check --no-manual --no-examples --no-codoc "    \
                       + tarball.rawname + " || :"
    elif buildpattern.default_pattern == "meson":
        found_tests = False
        makefile_path = os.path.join(src_dir, "meson.build")
        if not os.path.isfile(makefile_path):
            return
        for dirpath, _, files in os.walk(src_dir):
            for f in files:
                if f == "meson.build":
                    with util.open_auto(os.path.join(dirpath, f)) as fp:
                        if any(re.search(r'^\s*test\s*\(.+', line) for line in fp):
                            found_tests = True
                            tests_config = testsuites["meson"]
                            break
            if found_tests:
                break

    if "tox.ini" in files:
        buildreq.add_buildreq("tox")
        buildreq.add_buildreq("pytest")
        buildreq.add_buildreq("virtualenv")
        buildreq.add_buildreq("pluggy")
        buildreq.add_buildreq("py-python")


def load_specfile(specfile):
    """Load the specfile object."""
    specfile.tests_config = tests_config
