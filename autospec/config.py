#!/bin/true
#
# config.py - part of autospec
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
# Parse config files
#

import buildpattern
import buildreq
import files
import license
import os
import sys
import patches
import re
import subprocess
import tarball
import test
import textwrap
import configparser
import commitmessage
from os.path import exists as file_exists

from util import call

extra_configure = ""
keepstatic = 0
asneeded = 1
optimize_size = False
optimize_speed = False
insecure_build = False
conservative_flags = False
broken_cpp = False
clang_flags = False
want_clang = False
pgo = False
config_files = set()
parallel_build = " %{?_smp_mflags} "
config_path = ""
urlban = ""

license_fetch = None
license_show = None
git_uri = None
config_file = None
old_version = None
old_patches = list()
profile_payload = None


def filter_blanks(lines):
    return [l.strip() for l in lines if not l.strip().startswith("#") and l.split()]


def read_conf_file(name):
    try:
        with open(config_path + "/" + name) as f:
            config_files.add(name)
            return filter_blanks(f.readlines())
    except EnvironmentError:
        return []


def parse_existing_spec(path, name):
    global old_version
    global old_patches

    spec = os.path.join(path, "{}.spec".format(name))
    if not os.path.exists(spec):
        return

    with open(spec, "r") as inp:
        for line in inp.readlines():
            line = line.strip().replace("\r", "").replace("\n", "")
            if ":" not in line:
                continue
            spl = line.split(":")
            key = spl[0].lower().strip()
            value = ":".join(spl[1:]).strip()
            if key == "version":
                old_version = value
            elif key.startswith("patch"):
                old_patches.append(value)

    # Ignore nopatch
    cves = [p for p in patches.patches if p.lower() not in old_patches and p.lower().endswith(".patch") and p.lower().startswith("cve-")]
    for cve in cves:
        commitmessage.new_cve(cve.upper().split(".PATCH")[0])


def parse_config_files(path, bump):
    global extra_configure
    global keepstatic
    global asneeded
    global optimize_size
    global optimize_speed
    global insecure_build
    global conservative_flags
    global clang_flags
    global want_clang
    global pgo
    global config_files
    global config_path
    global parallel_build
    global license_fetch
    global license_show
    global git_uri
    global urlban
    global config_file
    global profile_payload
    global broken_cpp

    config_path = path

    # Require autospec.conf for additional features
    if os.path.exists(config_file):
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_file)

        if "autospec" not in config.sections():
            print("Missing autospec section..")
            sys.exit(1)

        git_uri = config['autospec'].get('git', None)
        license_fetch = config['autospec'].get('license_fetch', None)
        license_show = config['autospec'].get('license_show', None)
        urlban = config['autospec'].get('urlban', None)

    if not git_uri:
        print("Warning: Set [autospec][git] upstream template for git support")
    if not license_fetch:
        print("Warning: Set [autospec][license_fetch] uri for license fetch support")
    if not license_show:
        print("Warning: Set [autospec][license_show] uri for license link check support")

    wrapper = textwrap.TextWrapper()
    wrapper.initial_indent = "# "
    wrapper.subsequent_indent = "# "

    def write_default_conf_file(name, description):
        config_files.add(name)
        filename = path + "/" + name
        if os.path.isfile(filename):
            return

        with open(filename, "w") as f:
            f.write(wrapper.fill(description) + "\n")

    write_default_conf_file("buildreq_ban", "This file contains build requirements that get picked up but are undesirable. One entry per line, no whitespace.")
    write_default_conf_file("pkgconfig_ban", "This file contains pkgconfig build requirements that get picked up but are undesirable. One entry per line, no whitespace.")

    write_default_conf_file("buildreq_add", "This file contains additional build requirements that did not get picked up automatically. One name per line, no whitespace.")
    write_default_conf_file("pkgconfig_add", "This file contains additional pkgconfig build requirements that did not get picked up automatically. One name per line, no whitespace.")

    write_default_conf_file("excludes", "This file contains the output files that need %exclude. Full path names, one per line.")

    content = read_conf_file("release")
    if content and content[0]:
        r = int(content[0])
        if bump:
            r += 1
        tarball.release = str(r)
        print("Release     :", tarball.release)

    content = read_conf_file("buildreq_ban")
    for banned in content:
        print("Banning build requirement: %s." % banned)
        buildreq.banned_buildreqs.add(banned)

    content = read_conf_file("pkgconfig_ban")
    for banned in content:
        banned = "pkgconfig(%s)" % banned
        print("Banning build requirement: %s." % banned)
        buildreq.banned_buildreqs.add(banned)

    content = read_conf_file("buildreq_add")
    for extra in content:
        print("Adding additional build requirement: %s." % extra)
        buildreq.add_buildreq(extra)

    content = read_conf_file("pkgconfig_add")
    for extra in content:
        extra = "pkgconfig(%s)" % extra
        print("Adding additional build requirement: %s." % extra)
        buildreq.add_buildreq(extra)

    content = read_conf_file("excludes")
    for exclude in content:
            print("%%exclude for: %s." % exclude)
    files.excludes += content

    content = read_conf_file("extras")
    for extra in content:
            print("extras for: %s." % extra)
    files.extras += content

    content = read_conf_file("setuid")
    for suid in content:
            print("setuid for: %s." % suid)
    files.setuid += content

    content = read_conf_file("attrs")
    for line in content:
            attr = re.split('\(|\)|,', line)
            attr = [a.strip() for a in attr]
            filename = attr.pop()
            print("attr for: %s." % filename)
            files.attrs[filename] = attr

    patches.patches += read_conf_file("series")
    pfiles = [("%s/%s" % (path, x.split(" ")[0])) for x in patches.patches]
    cmd = "egrep \"(\+\+\+|\-\-\-).*((Makefile.am|Makefile.in)|(configure.ac|configure.in))\" %s" % \
        " ".join(pfiles)
    if len(patches.patches) > 0 and call(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        patches.autoreconf = True

    content = read_conf_file("configure")
    extra_configure = " \\\n".join(content)

    if file_exists("keepstatic"):
        keepstatic = 1
        buildpattern.disable_static = ""

    if file_exists("asneeded"):
        print("Disabling LD_AS_NEEDED\n")
        asneeded = 0

    if file_exists("optimize_size"):
        optimize_size = True
    if file_exists("funroll-loops"):
        optimize_speed = True
    if file_exists("insecure_build"):
        insecure_build = True
    if file_exists("conservative_flags"):
        conservative_flags = True
    if file_exists("pgo"):
        pgo = True
    if file_exists("broken_parallel_build"):
        parallel_build = ""

    content = read_conf_file("make_args")
    if content and content[0]:
        buildpattern.extra_make = content[0]

    content = read_conf_file("make_install_args")
    if content and content[0]:
        buildpattern.extra_make_install = content[0]

    content = read_conf_file("install_macro")
    if content and content[0]:
        buildpattern.install_macro = content[0]

    content = read_conf_file("cmake_args")
    if content and content[0]:
        buildpattern.extra_cmake = content[0]

    content = read_conf_file("subdir")
    if content and content[0]:
        buildpattern.subdir = content[0]

    content = read_conf_file("build_pattern")
    if content and content[0]:
        buildpattern.set_build_pattern(content[0], 20)
        patches.autoreconf = False

    if file_exists("skip_test_suite"):
        test.skip_tests = True

    if file_exists("unit_tests_must_pass"):
        test.new_pkg = False

    if file_exists("broken_c++"):
        broken_cpp = True

    content = read_conf_file("make_check_command")
    if content and content[0]:
        test.tests_config = content[0]

    content = read_conf_file("allow_test_failures")
    if content and content[0]:
        test.allow_test_failures = True

    content = read_conf_file(tarball.name + ".license")
    if content and content[0]:
        words = content[0].split()
        for word in words:
            if word.find(":") < 0:
                license.add_license(word)

    content = read_conf_file("golang_libpath")
    if content and content[0]:
        tarball.golibpath = content[0]
        print("golibpath   : {}".format(tarball.golibpath))

    if file_exists("use_clang"):
        clang_flags = True
        optimize_speed = False
        want_clang = True
        buildreq.add_buildreq("llvm-dev")

    buildpattern.make_install_append = read_conf_file("make_install_append")

    profile_payload = read_conf_file("profile_payload")
