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

import count
import util

tests_config = ""


def check_regression(pkg_dir, skip_tests, test_round):
    """Check the build log for test regressions using the count module."""
    if skip_tests:
        return

    log_path = os.path.join(pkg_dir, 'results', 'build.log')
    result = count.parse_log(log_path)
    if len(result) == 0 or result[0:2] == ',0':
        log_path = os.path.join(pkg_dir, 'results', f"round{test_round}-build.log")
        result = count.parse_log(log_path)

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


def scan_for_tests(src_dir, config, requirements, content):
    """Scan source directory for test files and set tests_config accordingly."""
    global tests_config

    if config.config_opts.get('skip_tests') or tests_config:
        return

    make_command = "ninja" if config.config_opts.get('use_ninja') else "make"
    makeflags = "%{?_smp_mflags} " if config.parallel_build else ""
    make_check = "{} {}check".format(make_command, makeflags)
    cmake_check = "{} test".format(make_command)
    make_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                         "{} {}check\nmodule unload openmpi".format(make_command, makeflags)
    cmake_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                          "{} test\nmodule unload openmpi".format(make_command)

    if config.config_opts.get('allow_test_failures'):
        make_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                             "{} {}check || :\nmodule unload openmpi".format(make_command, makeflags)
        cmake_check_openmpi = "module load openmpi\nexport OMPI_MCA_rmaps_base_oversubscribe=1\n" \
                              "{} test || :\nmodule unload openmpi".format(make_command)

    perl_check = "{} TEST_VERBOSE=1 test".format(make_command)
    meson_check = "meson test -C builddir --print-errorlogs"
    if config.config_opts.get('allow_test_failures'):
        make_check += " || :"
        cmake_check += " || :"
        perl_check += " || :"
        meson_check += " || :"

    testsuites = {
        "makecheck": make_check,
        "perlcheck": perl_check,
        "cmake": "cd clr-build; " + cmake_check,
        "meson": meson_check,
    }
    if config.config_opts.get('32bit'):
        testsuites["makecheck"] += "\ncd ../build32;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../../build32/clr-build32;\n" + cmake_check + " || :"
        testsuites["meson"] += "\ncd ../build32;\n" + meson_check + " || :"
    if config.config_opts.get('use_avx2'):
        testsuites["makecheck"] += "\ncd ../buildavx2;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../../buildavx2/clr-build-avx2;\n" + cmake_check + " || :"
        testsuites["meson"] += "\ncd ../buildavx2;\n" + meson_check + " || :"
    if config.config_opts.get('use_avx512'):
        testsuites["makecheck"] += "\ncd ../buildavx512;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../../buildavx512/clr-build-avx512;\n" + cmake_check + " || :"
        testsuites["meson"] += "\ncd ../buildavx512;\n" + meson_check + " || :"
    if config.config_opts.get('use_apx'):
        testsuites["makecheck"] += "\ncd ../buildapx;\n" + make_check + " || :"
        testsuites["cmake"] += "\ncd ../../buildapx/clr-build-apx;\n" + cmake_check + " || :"
        testsuites["meson"] += "\ncd ../buildapx;\n" + meson_check + " || :"
    if config.config_opts.get('openmpi'):
        testsuites["makecheck"] += "\ncd ../build-openmpi;\n" + make_check_openmpi
        testsuites["cmake"] += "\ncd ../../build-openmpi/clr-build-openmpi;\n" + cmake_check_openmpi

    files = os.listdir(src_dir)

    if config.default_pattern == "cmake":
        makefile_path = os.path.join(src_dir, "CMakeLists.txt")
        if not os.path.isfile(makefile_path):
            return

        if "enable_testing" in util.open_auto(makefile_path).read():
            tests_config = testsuites["cmake"]

    elif config.default_pattern in ["cpan", "configure", "configure_ac", "autogen"] and "Makefile.in" in files:
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

    elif config.default_pattern in ["configure", "configure_ac", "autogen"] and "Makefile.am" in files:
        tests_config = testsuites["makecheck"]

    elif config.default_pattern in ["cpan"] and "Makefile.PL" in files:
        tests_config = testsuites["perlcheck"]

    elif config.default_pattern == "R":
        tests_config = "export _R_CHECK_FORCE_SUGGESTS_=false\n"              \
                       "R CMD check --no-manual --no-examples --no-codoc . "    \
                       "|| :"
    elif config.default_pattern == "meson":
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
        requirements.add_buildreq("pypi-tox")
        requirements.add_buildreq("pypi-pytest")
        requirements.add_buildreq("pypi-virtualenv")
        requirements.add_buildreq("pypi-pluggy")
        requirements.add_buildreq("pypi(py)")


def load_specfile(specfile):
    """Load the specfile object."""
    specfile.tests_config = tests_config
