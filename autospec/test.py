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

import buildpattern
import buildreq
import count
import glob
import os
import tarball
import config
import util

tests_config = ""


def check_regression(pkg_dir):
    """
    Check the build log for test regressions using the count module
    """
    if config.config_opts['skip_tests']:
        return

    result = count.parse_log(os.path.join(pkg_dir, "results/logs/build.log"))
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

    util.write_out(os.path.join(pkg_dir, "testresults"), res_str, encode="utf-8")


def scan_for_tests(src_dir):
    """
    Scan source directory for test files and set tests_config accordingly
    """
    global tests_config

    if config.config_opts['skip_tests'] or tests_config:
        return

    makeflags = "%{?_smp_mflags} " if config.parallel_build else ""
    testsuites = {
        "makecheck": "make VERBOSE=1 V=1 {}check".format(makeflags),
        "perlcheck": "make TEST_VERBOSE=1 test",
        "setup.py": "PYTHONPATH=%{buildroot}/usr/lib/python3.6/site-packages "
                    "python3 setup.py test",
        "cmake": "pushd clr-build ; make test ; popd",
        "rakefile": "pushd %{buildroot}%{gem_dir}/gems/" +
                    tarball.tarball_prefix +
                    "\nrake --trace test TESTOPTS=\"-v\"\npopd",
        "rspec": "pushd %{buildroot}%{gem_dir}/gems/" +
                 tarball.tarball_prefix + "\nrspec -I.:lib spec/\npopd"
    }

    files = os.listdir(src_dir)

    if "CMakeLists.txt" in files:
        makefile_path = os.path.join(src_dir, "CMakeLists.txt")
        if not os.path.isfile(makefile_path):
            return

        if "enable_testing" in open(makefile_path, encoding='latin-1').read():
            tests_config = testsuites["cmake"]

    if "Makefile.in" in files:
        makefile_path = os.path.join(src_dir, "Makefile.in")
        if not os.path.isfile(makefile_path):
            return

        with open(makefile_path, 'r', encoding="latin-1") as make_fp:
            lines = make_fp.readlines()

        for line in lines:
            if line.startswith("check:"):
                tests_config = testsuites["makecheck"]
                break
            if line.startswith("test:"):
                tests_config = testsuites["perlcheck"]
                break

    elif "Makefile.am" in files:
        tests_config = testsuites["makecheck"]

    elif tarball.name.startswith("rubygem"):
        if any(t in files for t in ["test", "tests"]):
            r_testdir = [f for f in files if "test" in f if "." not in f].pop()
            pre_test = glob.glob(os.path.join(src_dir, "test*/test_*.rb"))
            post_test = glob.glob(os.path.join(src_dir, "test*/*_test.rb"))
            tests_config = "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix
            if pre_test:
                tests_config += "\nruby -v -I.:lib:" + r_testdir + " test*/test_*.rb"
            if post_test:
                tests_config += "\nruby -v -I.:lib:" + r_testdir + " test*/*_test.rb"

            tests_config += "\npopd"

        elif "spec" in files:
            buildreq.add_buildreq("rubygem-rspec")
            buildreq.add_buildreq("rubygem-rspec-core")
            buildreq.add_buildreq("rubygem-rspec-expectations")
            buildreq.add_buildreq("rubygem-rspec-support")
            buildreq.add_buildreq("rubygem-rspec-mocks")
            buildreq.add_buildreq("rubygem-devise")
            buildreq.add_buildreq("rubygem-diff-lcs")
            tests_config = testsuites["rspec"]
        elif "Rakefile" in files:
            tests_config = testsuites["rakefile"]
            buildreq.add_buildreq("ruby")
            buildreq.add_buildreq("rubygem-rake")
            buildreq.add_buildreq("rubygem-test-unit")
            buildreq.add_buildreq("rubygem-minitest")
    elif "Makefile.PL" in files:
        tests_config = testsuites["perlcheck"]
    elif "setup.py" in files:
        with open(os.path.join(src_dir, "setup.py"), 'r',
                  encoding="ascii",
                  errors="surrogateescape") as setup_fp:
            setup_contents = setup_fp.read()

        if "test_suite" in setup_contents or "pbr=True" in setup_contents:
            tests_config = testsuites["setup.py"]

    elif buildpattern.default_pattern == "R":
        tests_config = "export _R_CHECK_FORCE_SUGGESTS_=false\n"              \
                       "R CMD check --no-manual --no-examples --no-codoc -l " \
                       "%{buildroot}/usr/lib64/R/library "                    \
                       + tarball.rawname + "|| : \ncp ~/.stash/* "                 \
                       "%{buildroot}/usr/lib64/R/library/*/libs/ || :"

    if "tox.ini" in files:
        buildreq.add_buildreq("tox")
        buildreq.add_buildreq("pytest")
        buildreq.add_buildreq("virtualenv")
        buildreq.add_buildreq("pluggy")
        buildreq.add_buildreq("py-python")

    if tests_config != "" and config.config_opts['allow_test_failures']:
        if tarball.name.startswith("rubygem"):
            config_elements = tests_config.split("\n")
            config_elements.pop()
            tests_config = "\n".join(config_elements) + " || :\npopd"
        elif tests_config == testsuites["cmake"]:
            tests_config = "pushd clr-build ; make test ||: ; popd"
        else:
            tests_config = tests_config + " || :"


def load_specfile(specfile):
    """
    Load the specfile object
    """
    specfile.tests_config = tests_config
