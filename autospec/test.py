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
import glob
import os
import tarball
import subprocess
import config
from collections import OrderedDict

tests_config = ""
new_pkg = True
unit_pass_written = False


def check_regression(dir):

    if config.config_opts['skip_tests']:
        return

    build_log_path = os.path.join(dir, "results/build.log")
    perl_cmd = ["perl", os.path.dirname(__file__) + "/count.pl", build_log_path]
    result = subprocess.check_output(perl_cmd)
    result = result.decode("utf-8")
    lines = result.strip('\n').split('\n')
    titles = ['package name', 'total tests', 'tests passing', 'tests failing',
              'tests skipped', 'expected fail']

    output_format = OrderedDict([
        ('total tests', 'Total'),
        ('tests passing', 'Pass'),
        ('tests failing', 'Fail'),
        ('tests skipped', 'Skip'),
        ('expected fail', 'XFail')
    ])

    mapping = dict()

    if len(lines) > 1:
        for l in lines:
            split_lines = l.split(',')
            for x in range(0, len(split_lines)):
                print(titles[x] + ": " + split_lines[x])
                if titles[x] in output_format:
                    mapping[output_format[titles[x]]] = split_lines[x]
    else:
        split_list = lines[0].split(',')
        for x in range(1, len(split_list)):
            print(titles[x] + ": " + split_list[x])
            if titles[x] in output_format:
                mapping[output_format[titles[x]]] = split_list[x]

    with open(os.path.join(dir, "testresults"), "w", encoding="utf-8") as resfile:
        for key in output_format.keys():
            of = output_format[key]
            val = mapping[of]
            resfile.write("{} : {}\n".format(of, val))


def scan_for_tests(dir):
    global tests_config

    if config.config_opts['skip_tests']:
        return

    if len(tests_config) > 0:
        return

    makeflags = "%{?_smp_mflags} " if config.parallel_build else ""
    testsuites = {
        "makecheck": "make VERBOSE=1 V=1 {}check".format(makeflags),
        "perlcheck": "make TEST_VERBOSE=1 test",
        "setup.py": "PYTHONPATH=%{buildroot}/usr/lib/python2.7/site-packages python2 setup.py test",
        "cmake": "pushd clr-build ; make test ; popd",
        "rakefile": "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix + "\nrake --trace test TESTOPTS=\"-v\"\npopd",
        # "rubygems": "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix + "\nruby -I\"lib:test*\" test*/*_test.rb \nruby -I\"lib:test*\" test*/test_*.rb\npopd",
        "rspec": "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix + "\nrspec -I.:lib spec/\npopd"
    }

    files = os.listdir(dir)

    if "CMakeLists.txt" in files:
        makefile_path = os.path.join(dir, "CMakeLists.txt")
        if not os.path.isfile(makefile_path):
            return
        with open(makefile_path, encoding="latin-1") as fp:
            lines = fp.readlines()
        for line in lines:
            if line.find("enable_testing") >= 0:
                tests_config = testsuites["cmake"]
                break

    if "Makefile.in" in files:
        makefile_path = os.path.join(dir, "Makefile.in")
        if not os.path.isfile(makefile_path):
            return
        with open(makefile_path, encoding="latin-1") as fp:
            lines = fp.readlines()
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
        if "test" in files or "tests" in files:
            r_testdir = [f for f in files if "test" in f if "." not in f].pop()
            pre_test = glob.glob(os.path.join(dir, "test*/test_*.rb"))
            post_test = glob.glob(os.path.join(dir, "test*/*_test.rb"))
            tests_config = "pushd %{buildroot}%{gem_dir}/gems/" + tarball.tarball_prefix
            if len(pre_test) > 0:
                tests_config += "\nruby -v -I.:lib:" + r_testdir + " test*/test_*.rb"
            if len(post_test) > 0:
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
            with open(os.path.join(dir, "Rakefile"), encoding="ascii", errors="surrogateescape") as fp:
                setup_contents = fp.read()
                # if setup_contents.find("task :test") >= 0 or setup_contents.find("task 'test'") >= 0:
                tests_config = testsuites["rakefile"]
                buildreq.add_buildreq("ruby")
                buildreq.add_buildreq("rubygem-rake")
                buildreq.add_buildreq("rubygem-test-unit")
                buildreq.add_buildreq("rubygem-minitest")
    elif "Makefile.PL" in files:
        tests_config = testsuites["perlcheck"]
    elif "setup.py" in files:
        with open(os.path.join(dir, "setup.py"), encoding="ascii", errors="surrogateescape") as fp:
            setup_contents = fp.read()
            if "test_suite" in setup_contents or "pbr=True" in setup_contents:
                tests_config = testsuites["setup.py"]
    elif buildpattern.default_pattern == "R":
        tests_config = "export _R_CHECK_FORCE_SUGGESTS_=false\nR CMD check --no-manual --no-examples --no-codoc -l %{buildroot}/usr/lib64/R/library " + tarball.rawname

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
        print(tests_config)

def load_specfile(specfile):
    specfile.tests_config = tests_config
