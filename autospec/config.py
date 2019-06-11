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

import configparser
import os
import re
import subprocess
import sys
import textwrap

import buildpattern
import buildreq
import check
import license
import tarball
from util import call, print_warning, write_out
from util import open_auto

extra_configure = ""
extra_configure32 = ""
extra_configure64 = ""
extra_configure_avx2 = ""
extra_configure_avx512 = ""
config_files = set()
parallel_build = " %{?_smp_mflags} "
urlban = ""
extra_make = ""
extra32_make = ""
extra_make_install = ""
extra_make32_install = ""
extra_cmake = ""
cmake_srcdir = ""
subdir = ""
install_macro = "%make_install"
disable_static = "--disable-static"
prep_prepend = []
build_prepend = []
make_prepend = []
install_prepend = []
install_append = []
service_restart = []
patches = []
autoreconf = False
custom_desc = ""
set_gopath = True

license_fetch = None
license_show = None
git_uri = None
os_packages = set()
config_file = None
old_version = None
old_patches = list()
old_keyid = None
profile_payload = None
signature = None
yum_conf = None
failed_pattern_dir = None

failed_commands = {}
ignored_commands = {}
maven_jars = {}
gems = {}
license_hashes = {}
license_translations = {}
license_blacklist = {}
qt_modules = {}
cmake_modules = {}

cves = []

# defines which files to rename and copy to autospec directory,
# used in commitmessage.py
transforms = {
    'changes': 'ChangeLog',
    'changelog.txt': 'ChangeLog',
    'changelog': 'ChangeLog',
    'change.log': 'ChangeLog',
    'ChangeLog.md': 'ChangeLog',
    'changes.rst': 'ChangeLog',
    'changes.txt': 'ChangeLog',
    'news': 'NEWS',
    'meson_options.txt': 'meson_options.txt'
}

config_opts = {}
config_options = {
    "broken_c++": "extend flags with '-std=gnu++98",
    "use_lto": "configure build for lto",
    "use_avx2": "configure build for avx2",
    "use_avx512": "configure build for avx512",
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
    "broken_parallel_build": "disable parallelization during build",
    "pgo": "set profile for pgo",
    "use_clang": "add clang flags",
    "32bit": "build 32 bit libraries",
    "nostrip": "disable stripping binaries",
    "verify_required": "require package verification for build",
    "security_sensitive": "set flags for security-sensitive builds",
    "so_to_lib": "add .so files to the lib package instead of dev",
    "dev_requires_extras": "dev package requires the extras to be installed",
    "autoupdate": "this package is trusted enough to automatically update "
                  "(used by other tools)",
    "compat": "this package is a library compatability package and only "
              "ships versioned library files"}

# simple_pattern_pkgconfig patterns
# contains patterns for parsing build.log for missing dependencies
pkgconfig_pats = [
    (r"which: no qmake", "Qt"),
    (r"XInput2 extension not found", "xi"),
    (r"checking for UDEV\.\.\. no", "udev"),
    (r"checking for UDEV\.\.\. no", "libudev"),
    (r"XMLLINT not set and xmllint not found in path", "libxml-2.0"),
    (r"error\: xml2-config not found", "libxml-2.0"),
    (r"error: must install xorg-macros", "xorg-macros")]

# simple_pattern patterns
# contains patterns for parsing build.log for missing dependencies
simple_pats = [
    (r'warning: failed to load external entity "http://docbook.sourceforge.net/release/xsl/.*"', "docbook-xml"),
    (r"gobject-introspection dependency was not found, gir cannot be generated.", "gobject-introspection-dev"),
    (r"gobject-introspection dependency was not found, gir cannot be generated.", "glibc-bin"),
    (r"Cannot find development files for any supported version of libnl", "libnl-dev"),
    (r"/<http:\/\/www.cmake.org>", "cmake"),
    (r"\-\- Boost libraries:", "boost-dev"),
    (r"XInput2 extension not found", "inputproto"),
    (r"^WARNING: could not find 'runtest'$", "dejagnu"),
    (r"^WARNING: could not find 'runtest'$", "expect"),
    (r"^WARNING: could not find 'runtest'$", "tcl"),
    (r"VignetteBuilder package required for checking but installed:", "R-knitr"),
    (r"You must have XML::Parser installed", "perl(XML::Parser)"),
    (r"checking for Apache .* module support", "httpd-dev"),
    (r"checking for.*in -ljpeg... no", "libjpeg-turbo-dev"),
    (r"fatal error\: zlib\.h\: No such file or directory", "zlib-dev"),
    (r"\* tclsh failed", "tcl"),
    (r"\/usr\/include\/python3\.[0-9]+m\/pyconfig.h", "python3-dev"),
    (r"checking \"location of ncurses\.h file\"", "ncurses-dev"),
    (r"Can't exec \"aclocal\"", "automake"),
    (r"Can't exec \"aclocal\"", "libtool"),
    (r"configure: error: no suitable Python interpreter found", "python3-dev"),
    (r"Checking for header Python.h", "python3-dev"),
    (r"configure: error: No curses header-files found", "ncurses-dev"),
    (r" \/usr\/include\/python3\.", "python3-dev"),
    (r"to compile python extensions", "python3-dev"),
    (r"testing autoconf... not found", "autoconf"),
    (r"configure\: error\: could not find Python headers", "python3-dev"),
    (r"checking for libxml libraries", "libxml2-dev"),
    (r"checking for slang.h... no", "slang-dev"),
    (r"configure: error: no suitable Python interpreter found", "python3"),
    (r"configure: error: pcre-config for libpcre not found", "pcre"),
    (r"checking for OpenSSL", "openssl-dev"),
    (r"Package systemd was not found in the pkg-config search path.", "systemd-dev"),
    (r"Unable to find the requested Boost libraries.", "boost-dev"),
    (r"libproc not found. Please configure without procps", "procps-ng-dev"),
    (r"configure: error: glib2", "glib-dev"),
    (r"C library 'efivar' not found", "efivar-dev"),
    (r"Has header \"efi.h\": NO", "gnu-efi-dev"),
    (r".*: error: HAVE_INTROSPECTION does not appear in AM_CONDITIONAL", 'gobject-introspection-dev')]

# failed_pattern patterns
# contains patterns for parsing build.log for missing dependencies
failed_pats = [
    (r"[Dd]ependency (.*) found: NO \(tried pkgconfig and cmake\)", 0, 'pkgconfig'),
    (r"[Dd]ependency (.*) found: NO \(tried pkgconfig\)", 0, 'pkgconfig'),
    (r"[Dd]ependency (.*) found: NO", 0, None),
    (r"C library '(.*)' not found", 0, None),
    (r"Target '[a-zA-Z0-9\-]' can't be generated as '(.*)' could not be found", 0, None),
    (r"Program (.*) found: NO", 0, None),
    (r"meson\.build\:162\:2\: ERROR: C library \'(.*)\' not found", 0, None),
    (r"Native dependency '(.*)' not found", 0, "pkgconfig"),
    (r"checking for library containing (.*)... no", 0, None),
    (r"checking for (.*?)\.\.\. not_found", 0, None),
    (r"checking for (.*?)\.\.\. not found", 0, None),
    (r"Checking for (.*?)\s>=.*\s*: not found", 0, None),
    (r"Checking for (.*?)\s*: not found", 0, None),
    (r"configure: error: pkg-config missing (.*)", 0, None),
    (r"configure: error: Cannot find (.*)\. Make sure", 0, None),
    (r"configure: error: (.*) not found", 0, None),
    (r"checking for (.*?)\.\.\. no", 0, None),
    (r"Checking for (.*?)\.\.\.no", 0, None),
    (r"checking for (.*) support\.\.\. no", 0, None),
    (r"checking (.*?)\.\.\. no", 0, None),
    (r"checking for (.*)... configure: error", 0, None),
    (r"checking for (.*) with pkg-config... no", 0, None),
    (r"Checking for (.*) development files... No", 0, None),
    (r"which\: no ([a-zA-Z\-]*) in \(", 0, None),
    (r"checking for (.*) support\.\.\. no", 0, None),
    (r"checking for (.*) in default path\.\.\. not found", 0, None),
    (r" ([a-zA-Z0-9\-]*\.m4) not found", 0, None),
    (r" exec: ([a-zA-Z0-9\-]+): not found", 0, None),
    (r"configure\: error\: Unable to locate (.*)", 0, None),
    (r"No rule to make target `(.*)',", 0, None),
    (r"ImportError\: No module named (.*)", 0, None),
    (r"ModuleNotFoundError.*No module named (.*)", 0, None),
    (r"/usr/bin/python.*\: No module named (.*)", 0, None),
    (r"ImportError\: cannot import name (.*)", 0, None),
    (r"ImportError\: ([a-zA-Z]+) module missing", 0, None),
    (r"checking for [a-zA-Z0-9\_\-]+ in (.*?)\.\.\. no", 0, None),
    (r"No library found for -l([a-zA-Z\-])", 0, None),
    (r"\-\- Could NOT find ([a-zA-Z0-9]+)", 0, None),
    (r"By not providing \"([a-zA-Z0-9]+).cmake\" in CMAKE_MODULE_PATH this project", 0, None),
    (r"CMake Error at cmake\/modules\/([a-zA-Z0-9]+).cmake", 0, None),
    (r"Could NOT find ([a-zA-Z0-9]+)", 0, None),
    (r"  Could not find ([a-zA-Z0-9]+)", 0, None),
    (r"  Did not find ([a-zA-Z0-9]+)", 0, None),
    (r"([a-zA-Z\-]+) [0-9\.]+ is required to configure this module; "
     r"please install it or upgrade your CPAN\/CPANPLUS shell.", 0, None),
    (r"\/bin\/ld: cannot find (-l[a-zA-Z0-9\_]+)", 0, None),
    (r"fatal error\: (.*)\: No such file or directory", 0, None),
    (r"([a-zA-Z0-9\-\_\.]*)\: command not found", 1, None),
    (r"-- (.*) not found.", 1, None),
    (r"You need ([a-zA-Z0-9\-\_]*) to build this program.", 1, None),
    (r"Cannot find ([a-zA-Z0-9\-_\.]*)", 1, None),
    (r"    ([a-zA-Z]+\:\:[a-zA-Z]+) not installed", 1, None),
    (r"([a-zA-Z\-]*) tool not found or not executable", 0, None),
    (r"([a-zA-Z\-]*) validation tool not found or not executable", 0, None),
    (r"Could not find suitable distribution for Requirement.parse\('([a-zA-Z\-\.]*)", 0, None),
    (r"unable to execute '([a-zA-Z\-]*)': No such file or directory", 0, None),
    (r"Unable to find '(.*)'", 0, None),
    (r"Unable to `import (.*)`", 0, None),
    (r"Downloading https?://.*\.python\.org/packages/.*/.?/([A-Za-z]*)/.*", 0, None),
    (r"configure\: error\: ([a-zA-Z0-9]+) is required to build", 0, None),
    (r".* /usr/bin/([a-zA-Z0-9-_]*).*not found", 0, None),
    (r"warning: failed to load external entity "
     r"\"(/usr/share/sgml/docbook/xsl-stylesheets)/.*\"", 0, None),
    (r"Warning\: no usable ([a-zA-Z0-9]+) found", 0, None),
    (r"/usr/bin/env\: (.*)\: No such file or directory", 0, None),
    (r"make: ([a-zA-Z0-9].+): Command not found", 0, None),
    (r"ERROR: dependencies.*['‘]([a-zA-Z0-9\-\.]*)['’] are not available for package ['‘].*['’]", 0, 'R'),
    (r"Package which this enhances but not available for checking: ['‘]([a-zA-Z0-9\-]*)['’]", 0, 'R'),
    (r"Unknown packages ['‘]([a-zA-Z0-9\-]*)['’].* in Rd xrefs", 0, 'R'),
    (r"Unknown package ['‘]([a-zA-Z0-9\-]*)['’].* in Rd xrefs", 0, 'R'),
    (r"ERROR: dependencies ['‘]([a-zA-Z0-9\-\.]*)['’].* are not available for package ['‘].*['’]", 0, 'R'),
    (r"ERROR: dependencies ['‘].*['’], ['‘]([a-zA-Z0-9\-\.]*)['’],.* are not available for package ['‘].*['’]", 0, 'R'),
    (r"ERROR: dependency ['‘]([a-zA-Z0-9\-\.]*)['’] is not available for package ['‘].*['’]", 0, 'R'),
    (r"Error: package ['‘]([a-zA-Z0-9\-\.]*)['’] required by", 0, 'R'),
    (r"Error: Unable to find (.*)", 0, None),
    (r"there is no package called ['‘]([a-zA-Z0-9\-\.]*)['’]", 0, 'R'),
    (r"you may need to install the ([a-zA-Z0-9\-:\.]*) module", 0, 'perl'),
    (r"    !  ([a-zA-Z:]+) is not installed", 0, 'perl'),
    (r"Warning: prerequisite ([a-zA-Z:]+) [0-9\.]+ not found.", 0, 'perl'),
    (r"Can't locate [a-zA-Z\/\.]+ in @INC "
     r"\(you may need to install the ([a-zA-Z:]+) module\)", 0, 'perl'),
    (r"Download error on https://pypi.python.org/simple/([a-zA-Z0-9\-\._:]+)/", 0, 'pypi'),
    (r"No matching distribution found for ([a-zA-Z0-9\-\._]+)", 0, 'pypi'),
    (r"ImportError:..*: No module named ([a-zA-Z0-9\-\._]+)", 0, 'pypi'),
    (r"ImportError: No module named ([a-zA-Z0-9\-\._]+)", 0, 'pypi'),
    (r"ImportError: No module named '([a-zA-Z0-9\-\._]+)'", 0, 'pypi'),
    (r"No local packages or working download links found for ([a-zA-Z0-9\-\._]+)", 0, 'pypi'),
    (r"Perhaps you should add the directory containing `([a-zA-Z0-9\-:]*)\.pc'", 0, 'pkgconfig'),
    (r"No package '([a-zA-Z0-9\-:]*)' found", 0, 'pkgconfig'),
    (r"Package '([a-zA-Z0-9\-:]*)', required by '.*', not found", 0, 'pkgconfig'),
    (r"WARNING:  [a-zA-Z\-\_]+ dependency on ([a-zA-Z0-9\-\_:]*) \([<>=~]+ ([0-9.]+).*\) .*",
     0, 'ruby'),
    (r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-:]*)' \([>=]+ ([0-9.]+).*\), "
     "here is why:", 0, 'ruby'),
    (r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-\_]*)' \([>=]+ ([0-9.]+).*\) "
     r"in any repository", 0, 'ruby'),
    (r"Could not find '([a-zA-Z0-9\-\_]*)' \([~<>=]+ ([0-9.]+).*\) among [0-9]+ total gem",
     0, 'ruby'),
    (r"Could not find gem '([a-zA-Z0-9\-\_]+) \([~<>=0-9\.\, ]+\) ruby'", 0, 'ruby'),
    (r"Gem::LoadError: Could not find '([a-zA-Z0-9\-\_]*)'", 0, 'ruby'),
    (r"[a-zA-Z0-9\-:]* is not installed: cannot load such file -- rdoc/([a-zA-Z0-9\-:]*)",
     0, 'ruby'),
    (r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:]+)/.*", 0, 'ruby'),
    (r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:]+) ", 0, 'ruby'),
    (r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:\/]+)", 0, 'ruby table'),
    (r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:\/\_]+)", 0, 'ruby table'),
    (r".*\.go:.*cannot find package \"(.*)\" in any of:", 0, 'go'),
    (r"\[ERROR\] .* Cannot access central \(.*\) in offline mode and the artifact "
     r".*:(.*):[pom|jar]+:.* has not been downloaded from it before. .*", 0, 'maven'),
    (r"\[ERROR\] .* Cannot access central \(.*\) in offline mode and the artifact "
     r".*:(.*):[jar|pom]+:.* has not been downloaded from it before.*", 0, 'maven'),
    (r"\[WARNING\] The POM for .*:(.*):[jar|pom]+:.* is missing, no dependency information "
     r"available", 0, 'maven'),
    (r"^.*Could not find a package configuration file provided by \"(.*)\".*$", 0, None),
    (r"^.*By not providing \"Find(.*).cmake\" in CMAKE_MODULE_PATH this.*$", 0, None),
    (r"Add the installation prefix of \"(.*)\" to CMAKE_PREFIX_PATH", 0, None),
    (r"^.*\"(.*)\" with any of the following names.*$", 0, None)]


def get_metadata_conf():
    """Gather package metadata from the tarball module."""
    metadata = {}
    metadata['name'] = tarball.name
    if urlban:
        metadata['url'] = re.sub(urlban, "localhost", tarball.url)
        metadata['archives'] = re.sub(urlban, "localhost", " ".join(tarball.archives))
    else:
        metadata['url'] = tarball.url
        metadata['archives'] = " ".join(tarball.archives)

    metadata['giturl'] = tarball.giturl
    return metadata


def create_conf(path):
    """Create options.conf file and use deprecated configuration files or defaults to populate."""
    config_f = configparser.ConfigParser(interpolation=None, allow_no_value=True)

    # first the metadata
    config_f['package'] = get_metadata_conf()

    # next the options
    config_f['autospec'] = {}
    for fname, comment in sorted(config_options.items()):
        config_f.set('autospec', '# {}'.format(comment))
        if os.path.exists(fname):
            config_f['autospec'][fname] = 'true'
            os.remove(fname)
        else:
            config_f['autospec'][fname] = 'false'

    # default lto to true for new things
    config_f['autospec']['use_lto'] = 'true'

    # renamed options need special care
    if os.path.exists("skip_test_suite"):
        config_f['autospec']['skip_tests'] = 'true'
        os.remove("skip_test_suite")
    write_config(config_f, path)


def create_buildreq_cache(path, version):
    """Make the buildreq_cache file."""
    content = read_conf_file(os.path.join(path, "buildreq_cache"))
    # don't create an empty cache file
    if len(buildreq.buildreqs_cache) < 1:
        try:
            # file was possibly added to git so we should clean it up
            os.unlink(content)
        except Exception:
            pass
        return
    if not content:
        pkgs = sorted(buildreq.buildreqs_cache)
    else:
        pkgs = sorted(set(content[1:]).union(buildreq.buildreqs_cache))
    with open(os.path.join(path, 'buildreq_cache'), "w") as cachefile:
        cachefile.write("\n".join([version] + pkgs))
    config_files.add('buildreq_cache')


def create_versions(path, versions):
    """Make versions file."""
    with open(os.path.join(path, "versions"), 'w') as vfile:
        vfile.write('\n'.join(sorted(versions, reverse=True)) + '\n')
    config_files.add("versions")


def write_config(config_f, path):
    """Write the config_f to configfile."""
    with open(os.path.join(path, 'options.conf'), 'w') as configfile:
        config_f.write(configfile)


def read_config_opts(path):
    """Read config options from path/options.conf."""
    global config_opts
    global transforms

    opts_path = os.path.join(path, 'options.conf')
    if not os.path.exists(opts_path):
        create_conf(path)

    config_f = configparser.ConfigParser(interpolation=None)
    config_f.read(opts_path)
    if "autospec" not in config_f.sections():
        print("Missing autospec section in options.conf")
        sys.exit(1)

    for key in config_f['autospec']:
        config_opts[key] = config_f['autospec'].getboolean(key)

    # Rewrite the configuration file in case of formatting changes since a
    # configuration file may exist without any comments (either due to an older
    # version of autospec or if it was user-created)
    rewrite_config_opts(path)

    # Don't use the ChangeLog files if the giturl is set
    # ChangeLog is just extra noise when we can already see the gitlog
    if "package" in config_f.sections() and config_f['package'].get('giturl'):
        keys = []
        for k, v in transforms.items():
            if v == "ChangeLog":
                keys.append(k)
        for k in keys:
            transforms.pop(k)


def rewrite_config_opts(path):
    """Rewrite options.conf file when an option has changed (verify_required for example)."""
    config_f = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    config_f['package'] = get_metadata_conf()
    config_f['autospec'] = {}

    # Populate missing configuration options
    # (in case of a user-created options.conf)
    missing = set(config_options.keys()).difference(set(config_opts.keys()))
    for option in missing:
        config_opts[option] = False

    for fname, comment in sorted(config_options.items()):
        config_f.set('autospec', '# {}'.format(comment))
        config_f['autospec'][fname] = 'true' if config_opts[fname] else 'false'

    write_config(config_f, path)


def filter_blanks(lines):
    """Filter out blank lines from the line list."""
    return [l.strip() for l in lines if not l.strip().startswith("#") and l.split()]


def read_conf_file(path, track=True):
    """Read configuration file at path.

    If the config file does not exist (or is not expected to exist)
    in the package git repo, specify 'track=False'.
    """
    try:
        with open(path, "r") as f:
            if track:
                config_files.add(os.path.basename(path))
            return filter_blanks(f.readlines())
    except EnvironmentError:
        return []


def read_pattern_conf(filename, dest, list_format=False, path=None):
    """Read a fail-pattern configuration file.

    Read fail-pattern config file in the form of <pattern>, <package> and ignore lines starting with '#.'
    """
    file_repo_dir = os.path.dirname(os.path.abspath(__file__))
    file_conf_path = os.path.join(path, filename) if path else None
    file_repo_path = os.path.join(file_repo_dir, filename)
    if not os.path.isfile(file_repo_path):
        return
    if file_conf_path and os.path.isfile(file_conf_path):
        # The file_conf_path version of a pattern will be used in case of conflict
        file_path = [file_repo_path, file_conf_path]
    else:
        file_path = [file_repo_path]
    for fpath in file_path:
        with open(fpath, "r") as patfile:
            for line in patfile:
                if line.startswith("#"):
                    continue
                # Make list format a dict for faster lookup times
                if list_format:
                    dest[line.strip()] = True
                    continue
                # split from the right a maximum of one time, since the pattern
                # string might contain ", "
                pattern, package = line.rsplit(", ", 1)
                dest[pattern] = package.rstrip()


def setup_patterns(path=None):
    """Read each pattern configuration file and assign to the appropriate variable."""
    global failed_commands
    global ignored_commands
    global maven_jars
    global gems
    global license_hashes
    global license_translations
    global license_blacklist
    global qt_modules
    global cmake_modules

    read_pattern_conf("ignored_commands", ignored_commands, list_format=True, path=path)
    read_pattern_conf("failed_commands", failed_commands, path=path)
    read_pattern_conf("maven_jars", maven_jars, path=path)
    read_pattern_conf("gems", gems, path=path)
    read_pattern_conf("license_hashes", license_hashes, path=path)
    read_pattern_conf("license_translations", license_translations, path=path)
    read_pattern_conf("license_blacklist", license_blacklist, list_format=True, path=path)
    read_pattern_conf("qt_modules", qt_modules, path=path)
    read_pattern_conf("cmake_modules", cmake_modules, path=path)


def parse_existing_spec(path, name):
    """Determine the old version, old patch list, old keyid, and cves from old spec file."""
    global old_version
    global old_patches
    global old_keyid
    global cves

    spec = os.path.join(path, "{}.spec".format(name))
    if not os.path.exists(spec):
        return

    with open_auto(spec, "r") as inp:
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
                old_patches.append(value.lower())

    # Ignore nopatch
    for patch in patches:
        patch = patch.lower()
        if patch not in old_patches and patch.endswith(".patch") and patch.startswith("cve-"):
            cves.append(patch.upper().split(".PATCH")[0])


def parse_config_versions(path):
    """Parse the versions configuration file."""
    return set(read_conf_file(os.path.join(path, "versions")))


def parse_config_files(path, bump, filemanager, version):
    """Parse the various configuration files that may exist in the package directory."""
    global extra_configure
    global extra_configure32
    global extra_configure64
    global extra_configure_avx2
    global extra_configure_avx512
    global config_files
    global parallel_build
    global license_fetch
    global license_show
    global git_uri
    global os_packages
    global urlban
    global config_file
    global profile_payload
    global config_opts
    global extra_make
    global extra32_make
    global extra_make_install
    global extra_make32_install
    global extra_cmake
    global cmake_srcdir
    global subdir
    global install_macro
    global disable_static
    global prep_prepend
    global build_prepend
    global make_prepend
    global install_prepend
    global install_append
    global service_restart
    global patches
    global autoreconf
    global set_gopath
    global yum_conf
    global custom_desc
    global failed_pattern_dir

    packages_file = None

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
        packages_file = config['autospec'].get('packages_file', None)
        yum_conf = config['autospec'].get('yum_conf', None)
        failed_pattern_dir = config['autospec'].get('failed_pattern_dir', None)

        # support reading the local files relative to config_file
        if packages_file and not os.path.isabs(packages_file):
            packages_file = os.path.join(os.path.dirname(config_file), packages_file)
        if yum_conf and not os.path.isabs(yum_conf):
            yum_conf = os.path.join(os.path.dirname(config_file), yum_conf)
        if failed_pattern_dir and not os.path.isabs(failed_pattern_dir):
            failed_pattern_dir = os.path.join(os.path.dirname(config_file), failed_pattern_dir)

        if not packages_file:
            print("Warning: Set [autospec][packages_file] path to package list file for "
                  "requires validation")
            packages_file = os.path.join(os.path.dirname(config_file), "packages")

        urlban = config['autospec'].get('urlban', None)

    # Read values from options.conf (and deprecated files) and rewrite as necessary
    read_config_opts(path)

    if not git_uri:
        print("Warning: Set [autospec][git] upstream template for remote git URI configuration")
    if not license_fetch:
        print("Warning: Set [autospec][license_fetch] uri for license fetch support")
    if not license_show:
        print("Warning: Set [autospec][license_show] uri for license link check support")
    if not yum_conf:
        print("Warning: Set [autospec][yum_conf] path to yum.conf file for whatrequires validation")
        yum_conf = os.path.join(os.path.dirname(config_file), "image-creator/yum.conf")

    if packages_file:
        os_packages = set(read_conf_file(packages_file, track=False))
    else:
        os_packages = set(read_conf_file("~/packages", track=False))

    wrapper = textwrap.TextWrapper()
    wrapper.initial_indent = "# "
    wrapper.subsequent_indent = "# "

    def write_default_conf_file(name, description):
        """Write default configuration file with description to file name."""
        config_files.add(name)
        filename = os.path.join(path, name)
        if os.path.isfile(filename):
            return

        write_out(filename, wrapper.fill(description) + "\n")

    write_default_conf_file("buildreq_ban",
                            "This file contains build requirements that get picked up but are "
                            "undesirable. One entry per line, no whitespace.")
    write_default_conf_file("pkgconfig_ban",
                            "This file contains pkgconfig build requirements that get picked up but"
                            " are undesirable. One entry per line, no whitespace.")
    write_default_conf_file("requires_ban",
                            "This file contains runtime requirements that get picked up but are "
                            "undesirable. One entry per line, no whitespace.")
    write_default_conf_file("buildreq_add",
                            "This file contains additional build requirements that did not get "
                            "picked up automatically. One name per line, no whitespace.")
    write_default_conf_file("pkgconfig_add",
                            "This file contains additional pkgconfig build requirements that did "
                            "not get picked up automatically. One name per line, no whitespace.")
    write_default_conf_file("requires_add",
                            "This file contains additional runtime requirements that did not get "
                            "picked up automatically. One name per line, no whitespace.")
    write_default_conf_file("excludes",
                            "This file contains the output files that need %exclude. Full path "
                            "names, one per line.")

    content = read_conf_file(os.path.join(path, "release"))
    if content and content[0]:
        r = int(content[0])
        if bump:
            r += 1
        tarball.release = str(r)
        print("Release     :", tarball.release)

    content = read_conf_file(os.path.join(path, "buildreq_ban"))
    for banned in content:
        print("Banning build requirement: %s." % banned)
        buildreq.banned_buildreqs.add(banned)

    content = read_conf_file(os.path.join(path, "pkgconfig_ban"))
    for banned in content:
        banned = "pkgconfig(%s)" % banned
        print("Banning build requirement: %s." % banned)
        buildreq.banned_buildreqs.add(banned)

    content = read_conf_file(os.path.join(path, "requires_ban"))
    for banned in content:
        print("Banning runtime requirement: %s." % banned)
        buildreq.banned_requires.add(banned)

    content = read_conf_file(os.path.join(path, "buildreq_add"))
    for extra in content:
        print("Adding additional build requirement: %s." % extra)
        buildreq.add_buildreq(extra)

    content = read_conf_file(os.path.join(path, "buildreq_cache"))
    if content and content[0] == version:
        for extra in content[1:]:
            print("Adding additional build (cache) requirement: %s." % extra)
            buildreq.add_buildreq(extra)

    content = read_conf_file(os.path.join(path, "pkgconfig_add"))
    for extra in content:
        extra = "pkgconfig(%s)" % extra
        print("Adding additional build requirement: %s." % extra)
        buildreq.add_buildreq(extra)

    content = read_conf_file(os.path.join(path, "requires_add"))
    for extra in content:
        print("Adding additional runtime requirement: %s." % extra)
        buildreq.add_requires(extra, override=True)

    content = read_conf_file(os.path.join(path, "excludes"))
    for exclude in content:
        print("%%exclude for: %s." % exclude)
    filemanager.excludes += content

    content = read_conf_file(os.path.join(path, "extras"))
    for extra in content:
        print("extras for  : %s." % extra)
    filemanager.extras += content
    filemanager.excludes += content

    for fname in os.listdir(path):
        if not re.search('.+_extras$', fname) or fname == "dev_extras":
            continue
        content = {}
        content['files'] = read_conf_file(os.path.join(path, fname))
        if not content:
            print_warning(f"Error reading custom extras file: {fname}")
            continue
        req_file = os.path.join(path, f'{fname}_requires')
        if os.path.isfile(req_file):
            content['requires'] = read_conf_file(req_file)
        name = fname[:-len("_extras")]
        print(f"extras-{name} for {content['files']}")
        filemanager.custom_extras["extras-" + f"{name}"] = content
        filemanager.excludes += content['files']

    content = read_conf_file(os.path.join(path, "dev_extras"))
    for extra in content:
        print("dev for     : %s." % extra)
    filemanager.dev_extras += content
    filemanager.excludes += content

    content = read_conf_file(os.path.join(path, "setuid"))
    for suid in content:
        print("setuid for  : %s." % suid)
    filemanager.setuid += content
    filemanager.excludes += content

    content = read_conf_file(os.path.join(path, "attrs"))
    for line in content:
        attr = line.split()
        filename = attr.pop()
        print("%attr({0},{1},{2}) for: {3}".format(
            attr[0], attr[1], attr[2], filename))
        filemanager.attrs[filename] = attr

    patches += read_conf_file(os.path.join(path, "series"))
    pfiles = [("%s/%s" % (path, x.split(" ")[0])) for x in patches]
    cmd = "egrep \"(\+\+\+|\-\-\-).*((Makefile.am)|(aclocal.m4)|(configure.ac|configure.in))\" %s" % " ".join(pfiles)  # noqa: W605
    if patches and call(cmd,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL) == 0:
        autoreconf = True

    if any(p.lower().startswith('cve-') for p in patches):
        config_opts['security_sensitive'] = True
        rewrite_config_opts(path)

    content = read_conf_file(os.path.join(path, "configure"))
    extra_configure = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "configure32"))
    extra_configure32 = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "configure64"))
    extra_configure64 = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "configure_avx2"))
    extra_configure_avx2 = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "configure_avx512"))
    extra_configure_avx512 = " \\\n".join(content)

    if config_opts["keepstatic"]:
        disable_static = ""
    if config_opts['broken_parallel_build']:
        parallel_build = ""

    content = read_conf_file(os.path.join(path, "make_args"))
    if content:
        extra_make = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "make32_args"))
    if content:
        extra32_make = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "make_install_args"))
    if content:
        extra_make_install = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "make32_install_args"))
    if content:
        extra_make32_install = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "install_macro"))
    if content and content[0]:
        install_macro = content[0]

    content = read_conf_file(os.path.join(path, "cmake_args"))
    if content:
        extra_cmake = " \\\n".join(content)

    content = read_conf_file(os.path.join(path, "cmake_srcdir"))
    if content and content[0]:
        cmake_srcdir = content[0]

    content = read_conf_file(os.path.join(path, "subdir"))
    if content and content[0]:
        subdir = content[0]

    content = read_conf_file(os.path.join(path, "build_pattern"))
    if content and content[0]:
        buildpattern.set_build_pattern(content[0], 20)
        autoreconf = False

    content = read_conf_file(os.path.join(path, "make_check_command"))
    if content:
        check.tests_config = '\n'.join(content)

    content = read_conf_file(os.path.join(path, tarball.name + ".license"))
    if content and content[0]:
        words = content[0].split()
        for word in words:
            if word.find(":") < 0:
                license.add_license(word)

    content = read_conf_file(os.path.join(path, "golang_libpath"))
    if content and content[0]:
        tarball.golibpath = content[0]
        print("golibpath   : {}".format(tarball.golibpath))

    if config_opts['use_clang']:
        config_opts['funroll-loops'] = False
        buildreq.add_buildreq("llvm")

    if config_opts['32bit']:
        buildreq.add_buildreq("glibc-libc32")
        buildreq.add_buildreq("glibc-dev32")
        buildreq.add_buildreq("gcc-dev32")
        buildreq.add_buildreq("gcc-libgcc32")
        buildreq.add_buildreq("gcc-libstdc++32")

    prep_prepend = read_conf_file(os.path.join(path, "prep_prepend"))
    if os.path.isfile(os.path.join(path, "prep_append")):
        os.rename(os.path.join(path, "prep_append"), os.path.join(path, "build_prepend"))
    make_prepend = read_conf_file(os.path.join(path, "make_prepend"))
    build_prepend = read_conf_file(os.path.join(path, "build_prepend"))
    install_prepend = read_conf_file(os.path.join(path, "install_prepend"))
    if os.path.isfile(os.path.join(path, "make_install_append")):
        os.rename(os.path.join(path, "make_install_append"), os.path.join(path, "install_append"))
    install_append = read_conf_file(os.path.join(path, "install_append"))
    service_restart = read_conf_file(os.path.join(path, "service_restart"))

    profile_payload = read_conf_file(os.path.join(path, "profile_payload"))

    custom_desc = read_conf_file(os.path.join(path, "description"))


def load_specfile(specfile):
    """Load specfile object with configuration."""
    specfile.urlban = urlban
    specfile.keepstatic = config_opts['keepstatic']
    specfile.no_autostart = config_opts['no_autostart']
    specfile.extra_make = extra_make
    specfile.extra32_make = extra32_make
    specfile.extra_make_install = extra_make_install
    specfile.extra_make32_install = extra_make32_install
    specfile.extra_cmake = extra_cmake
    specfile.cmake_srcdir = cmake_srcdir or specfile.cmake_srcdir
    specfile.subdir = subdir
    specfile.install_macro = install_macro
    specfile.disable_static = disable_static
    specfile.prep_prepend = prep_prepend
    specfile.build_prepend = build_prepend
    specfile.make_prepend = make_prepend
    specfile.install_prepend = install_prepend
    specfile.install_append = install_append
    specfile.service_restart = service_restart
    specfile.patches = patches
    specfile.autoreconf = autoreconf
    specfile.set_gopath = set_gopath
