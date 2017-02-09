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
import build
import buildreq
import files
import license
import os
import sys
import re
import subprocess
import tarball
import test
import textwrap
import configparser
from os.path import exists as file_exists

from util import call

extra_configure = ""
extra_configure32 = ""
config_files = set()
parallel_build = " %{?_smp_mflags} "
config_path = ""
urlban = ""
extra_make = ""
extra_make_install = ""
extra_cmake = ""
prep_append = []
subdir = ""
install_macro = "%make_install"
disable_static = "--disable-static"
make_install_append = []
patches = []
autoreconf = False

license_fetch = None
license_show = None
git_uri = None
config_file = None
old_version = None
old_patches = list()
old_keyid = None
profile_payload = None
signature = None

failed_commands = {}
maven_jars = {}
gems = {}

cves = []

config_opts = {}
config_options = {
    "broken_c++": "extend flags with '-std=gnu++98",
    "use_lto": "configure build for lto",
    "use_avx2": "configure build for avx2",
    "keepstatic": "do not remove static libraries",
    "asneeded": "unset %build LD_AS_NEEDED variable",
    "allow_test_failures": "allow package to build with test failures",
    "skip_tests": "Do not run test suite",
    "no_autostart": "do not require autostart subpackage",
    "optimize_size": "optimize build for size over speed",
    "funroll-loops": "optimize build for speed over size",
    "fast-math": "pass -ffast-math to compiler",
    "insecure_build": "set flags to smallest -02 flags possible",
    "conservative_flags": "set conservative build flags",
    "broken_parallel_build":  "disable parallelization during build",
    "pgo": "set profile for pgo",
    "use_clang": "add clang flags",
    "32bit" : "build 32 bit libraries",
    "nostrip" : "disable stripping binaries",
    "verify_required": "require package verification for build"}

def create_conf():
    config_f = configparser.ConfigParser(allow_no_value=True)
    config_f['autospec'] = {}
    for fname, comment in sorted(config_options.items()):
        config_f.set('autospec', '# {}'.format(comment))
        if file_exists(fname):
            config_f['autospec'][fname] = 'true'
            os.remove(fname)
        else:
            config_f['autospec'][fname] = 'false'

    # renamed options need special care
    if file_exists("skip_test_suite"):
        config_f['autospec']['skip_tests'] = 'true'
        os.remove("skip_test_suite")
    write_config(config_f)


def write_config(config_f):
    with open('options.conf', 'w') as configfile:
        config_f.write(configfile)


def read_config_opts():
    global config_opts
    if not file_exists('options.conf'):
        create_conf()

    config_f = configparser.ConfigParser()
    config_f.read('options.conf')
    if "autospec" not in config_f.sections():
        print("Missing autospec section in options.conf")
        sys.exit(1)

    for key in config_f['autospec']:
        config_opts[key] = config_f['autospec'].getboolean(key)

    # Rewrite the configuration file in case of formatting changes since a
    # configuration file may exist without any comments (either due to an older
    # version of autospec or if it was user-created)
    rewrite_config_opts()


def rewrite_config_opts():
    config_f = configparser.ConfigParser(allow_no_value=True)
    config_f['autospec'] = {}

    # Populate missing configuration options
    # (in case of a user-created options.conf)
    missing = set(config_options.keys()).difference(set(config_opts.keys()))
    for option in missing:
        config_opts[option] = False

    for fname, comment in sorted(config_options.items()):
        config_f.set('autospec', '# {}'.format(comment))
        config_f['autospec'][fname] = 'true' if config_opts[fname] else 'false'

    write_config(config_f)


def filter_blanks(lines):
    return [l.strip() for l in lines if not l.strip().startswith("#") and l.split()]


def read_conf_file(name):
    try:
        with open(config_path + "/" + name) as f:
            config_files.add(name)
            return filter_blanks(f.readlines())
    except EnvironmentError:
        return []


def read_pattern_conf(filename, dest):
    """
    Read a fail-pattern configuration file in the form of
    <pattern>, <package> and ignore lines starting with "#"
    """
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(file_dir, filename)
    with open(file_path, "r") as patfile:
        for line in patfile:
            if line.startswith("#"):
                continue
            pattern, package = line.split(", ", 2)
            dest[pattern] = package.rstrip()


def setup_patterns():
    global failed_commands
    global maven_jars
    global gems
    read_pattern_conf("failed_commands", failed_commands)
    read_pattern_conf("maven_jars", maven_jars)
    read_pattern_conf("gems", gems)


def parse_existing_spec(path, name):
    global old_version
    global old_patches
    global old_keyid
    global cves

    spec = os.path.join(path, "{}.spec".format(name))
    if not os.path.exists(spec):
        return

    with open(spec, "r", encoding="latin-1") as inp:
        for line in inp.readlines():
            line = line.strip().replace("\r", "").replace("\n", "")
            if "Source0 file verified with key" in line:
                keyidx = line.find('0x') + 2
                old_keyid = line[keyidx:].split()[0] if keyidx > 2 else old_keyid
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
    for patch in patches:
        patch = patch.lower()
        if patch not in old_patches and patch.endswith(".patch") and patch.startswith("cve-"):
            cves.append(patch.upper().split(".PATCH")[0])


def parse_config_files(path, bump):
    global extra_configure
    global extra_configure32
    global config_files
    global config_path
    global parallel_build
    global license_fetch
    global license_show
    global git_uri
    global urlban
    global config_file
    global profile_payload
    global config_opts
    global extra_make
    global extra_make_install
    global extra_cmake
    global prep_append
    global subdir
    global install_macro
    global disable_static
    global make_install_append
    global patches
    global autoreconf

    config_path = path

    read_config_opts()

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

    patches += read_conf_file("series")
    pfiles = [("%s/%s" % (path, x.split(" ")[0])) for x in patches]
    cmd = "egrep \"(\+\+\+|\-\-\-).*((Makefile.am)|(configure.ac|configure.in))\" %s" % \
        " ".join(pfiles)
    if len(patches) > 0 and call(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        autoreconf = True

    content = read_conf_file("configure")
    extra_configure = " \\\n".join(content)

    content = read_conf_file("configure32")
    extra_configure32 = " \\\n".join(content)

    if config_opts["keepstatic"]:
        disable_static = ""
    if config_opts['broken_parallel_build']:
        parallel_build = ""

    content = read_conf_file("make_args")
    if content and content[0]:
        extra_make = content[0]

    content = read_conf_file("make_install_args")
    if content and content[0]:
        extra_make_install = content[0]

    content = read_conf_file("install_macro")
    if content and content[0]:
        install_macro = content[0]

    content = read_conf_file("cmake_args")
    if content and content[0]:
        extra_cmake = content[0]

    content = read_conf_file("subdir")
    if content and content[0]:
        subdir = content[0]

    content = read_conf_file("build_pattern")
    if content and content[0]:
        buildpattern.set_build_pattern(content[0], 20)
        autoreconf = False

    content = read_conf_file("make_check_command")
    if content and content[0]:
        test.tests_config = content[0]

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

    if config_opts['use_clang']:
        config_opts['funroll-loops'] = False
        buildreq.add_buildreq("llvm-dev")

    if config_opts['32bit']:
        buildreq.add_buildreq("glibc-libc32")
        buildreq.add_buildreq("glibc-dev32")
        buildreq.add_buildreq("gcc-dev32")
        buildreq.add_buildreq("gcc-libgcc32")
        buildreq.add_buildreq("gcc-libstdc++32")

    make_install_append = read_conf_file("make_install_append")
    prep_append = read_conf_file("prep_append")

    profile_payload = read_conf_file("profile_payload")

def load_specfile(specfile):
    specfile.urlban = urlban
    specfile.keepstatic = config_opts['keepstatic']
    specfile.no_autostart = config_opts['no_autostart']
    specfile.extra_make = extra_make
    specfile.extra_make_install = extra_make_install
    specfile.extra_cmake = extra_cmake
    specfile.prep_append = prep_append
    specfile.subdir = subdir
    specfile.install_macro = install_macro
    specfile.disable_static = disable_static
    specfile.make_install_append = make_install_append
    specfile.patches = patches
    specfile.autoreconf = autoreconf
