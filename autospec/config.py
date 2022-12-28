#!/bin/true
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
from collections import OrderedDict

import check
import license
from util import call, print_info, print_warning, write_out
from util import open_auto


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
                if line.startswith(r"\#"):
                    line = line[1:]
                # Make list format a dict for faster lookup times
                if list_format:
                    dest[line.strip()] = True
                    continue
                # split from the right a maximum of one time, since the pattern
                # string might contain ", "
                pattern, package = line.rsplit(", ", 1)
                dest[pattern] = package.rstrip()


class Config(object):
    """Class to handle autospec configuration."""

    def __init__(self, download_path):
        """Initialize Default configuration settings."""
        self.content = None  # hack to avoid circular init dependency
        self.extra_configure = ""
        self.extra_configure32 = ""
        self.extra_configure64 = ""
        self.extra_configure_avx2 = ""
        self.extra_configure_avx512 = ""
        self.extra_configure_openmpi = ""
        self.config_files = set()
        self.parallel_build = " %{?_smp_mflags} "
        self.urlban = ""
        self.make_command = ""
        self.extra_make = ""
        self.extra32_make = ""
        self.extra_make_install = ""
        self.extra_make32_install = ""
        self.extra_cmake = ""
        self.extra_cmake_openmpi = ""
        self.cmake_srcdir = ".."
        self.subdir = ""
        self.install_macro = "%make_install"
        self.disable_static = "--disable-static"
        self.prep_prepend = []
        self.build_prepend = []
        self.build_prepend_once = []
        self.build_append = []
        self.make_prepend = []
        self.install_prepend = []
        self.install_append = []
        self.service_restart = []
        self.patches = []
        self.pypi_overrides = []
        self.verpatches = OrderedDict()
        self.extra_sources = []
        self.autoreconf = False
        self.custom_desc = ""
        self.custom_summ = ""
        self.set_gopath = True
        self.license_fetch = None
        self.license_show = None
        self.git_uri = None
        self.os_packages = set()
        self.config_file = None
        self.old_version = None
        self.old_patches = list()
        self.old_keyid = None
        self.profile_payload = None
        self.signature = None
        self.yum_conf = None
        self.failed_pattern_dir = None
        self.alias = None
        self.failed_commands = {}
        self.ignored_commands = {}
        self.gems = {}
        self.license_hashes = {}
        self.license_translations = {}
        self.license_blacklist = {}
        self.qt_modules = {}
        self.cmake_modules = {}
        self.cves = []
        self.download_path = download_path
        self.default_pattern = "make"
        self.pattern_strength = 0
        self.sources = {"unit": [], "gcov": [], "tmpfile": [], "sysuser": [], "archive": [], "destination": [], "godep": [], "version": []}
        self.archive_details = {}
        self.conf_args_openmpi = '--program-prefix=  --exec-prefix=$MPI_ROOT \\\n' \
            '--libdir=$MPI_LIB --bindir=$MPI_BIN --sbindir=$MPI_BIN --includedir=$MPI_INCLUDE \\\n' \
            '--datarootdir=$MPI_ROOT/share --mandir=$MPI_MAN -exec-prefix=$MPI_ROOT --sysconfdir=$MPI_SYSCONFIG \\\n' \
            '--build=x86_64-generic-linux-gnu --host=x86_64-generic-linux-gnu --target=x86_64-clr-linux-gnu '
        # Keep track of the package versions
        self.versions = OrderedDict()
        # Only parse the versions file once, and save the result for later
        self.parsed_versions = OrderedDict()
        # defines which files to rename and copy to autospec directory,
        # used in commitmessage.py
        self.transforms = {
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
        self.config_opts = {}
        self.config_options = {
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
            "full-debug-info": "compile full (traditional) debug info",
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
            "autoupdate": "this package is trusted enough to automatically update (used by other tools)",
            "compat": "this package is a library compatibility package and only ships versioned library files",
            "nodebug": "do not generate debuginfo for this package",
            "openmpi": "configure build also for openmpi",
            "server": "Package is only used by servers",
            "no_glob": "Do not use the replacement pattern for file matching"
        }
        # simple_pattern_pkgconfig patterns
        # contains patterns for parsing build.log for missing dependencies
        self.pkgconfig_pats = [
            (r"which: no qmake", "Qt"),
            (r"XInput2 extension not found", "xi"),
            (r"checking for UDEV\.\.\. no", "udev"),
            (r"checking for UDEV\.\.\. no", "libudev"),
            (r"XMLLINT not set and xmllint not found in path", "libxml-2.0"),
            (r"error\: xml2-config not found", "libxml-2.0"),
            (r"error: must install xorg-macros", "xorg-macros")
        ]
        # simple_pattern patterns
        # contains patterns for parsing build.log for missing dependencies
        self.simple_pats = [
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
            (r"Unable to find the requested Boost libraries.", "boost-dev"),
            (r"libproc not found. Please configure without procps", "procps-ng-dev"),
            (r"configure: error: glib2", "glib-dev"),
            (r"C library 'efivar' not found", "efivar-dev"),
            (r"Has header \"efi.h\": NO", "gnu-efi-dev"),
            (r"ERROR: Could not execute Vala compiler", "vala"),
            (r".*: error: HAVE_INTROSPECTION does not appear in AM_CONDITIONAL", 'gobject-introspection-dev')
        ]
        # failed_pattern patterns
        # contains patterns for parsing build.log for missing dependencies
        self.failed_pats = [
            (r"    !  ([a-zA-Z:]+) is not installed", 0, 'perl'),
            (r"    ([a-zA-Z]+\:\:[a-zA-Z]+) not installed", 1, None),
            (r"(?:-- )?(?:Could|Did) (?:NOT|not) find ([a-zA-Z0-9_-]+)", 0, None),
            (r" ([a-zA-Z0-9\-]*\.m4) not found", 0, None),
            (r" exec: ([a-zA-Z0-9\-]+): not found", 0, None),
            (r"([a-zA-Z0-9\-\_\.]*)\: command not found", 1, None),
            (r"([a-zA-Z\-]*) (?:validation )?tool not found or not executable", 0, None),
            (r"([a-zA-Z\-]+) [0-9\.]+ is required to configure this module; "
             r"please install it or upgrade your CPAN\/CPANPLUS shell.", 0, None),
            (r"-- (.*) not found.", 1, None),
            (r".* /usr/bin/([a-zA-Z0-9-_]*).*not found", 0, None),
            (r".*\.go:.*cannot find package \"(.*)\" in any of:", 0, 'go'),
            (r"/usr/bin/env\: (.*)\: No such file or directory", 0, None),
            (r"/usr/bin/python.*\: No module named (.*)", 0, None),
            (r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:\/]+)", 0, 'ruby table'),
            (r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:]+) ", 0, 'ruby'),
            (r"Add the installation prefix of \"(.*)\" to CMAKE_PREFIX_PATH", 0, None),
            (r"By not providing \"([a-zA-Z0-9]+).cmake\" in CMAKE_MODULE_PATH this project", 0, None),
            (r"C library '(.*)' not found", 0, None),
            (r"CMake Error at cmake\/modules\/([a-zA-Z0-9]+).cmake", 0, None),
            (r"Can't locate [a-zA-Z0-9_\-\/\.]+ in @INC " r"\(you may need to install the ([a-zA-Z0-9_\-:]+) module\)", 0, 'perl'),
            (r"Cannot find ([a-zA-Z0-9\-_\.]*)", 1, None),
            (r"Checking for (.*?)\.\.\.no", 0, None),
            (r"Checking for (.*?)\s*: not found", 0, None),
            (r"Checking for (.*?)\s>=.*\s*: not found", 0, None),
            (r"Could not find '([a-zA-Z0-9\-\_]*)' \([~<>=]+ ([0-9.]+).*\) among [0-9]+ total gem", 0, 'ruby'),
            (r"Could not find gem '([a-zA-Z0-9\-\_]+) \([~<>=0-9\.\, ]+\) ruby'", 0, 'ruby'),
            (r"Could not find suitable distribution for Requirement.parse\('([a-zA-Z\-\.]*)", 0, None),
            (r"Download error on https://pypi.python.org/simple/([a-zA-Z0-9\-\._:]+)/", 0, 'pypi'),
            (r"Downloading https?://.*\.python\.org/packages/.*/.?/([A-Za-z]*)/.*", 0, None),
            (r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-\_\:]*)' \([>=]+ ([0-9.]+).*\)", 0, 'ruby'),
            (r"ERROR: dependencies ['‘]([a-zA-Z0-9\-\.]*)['’].* are not available for package ['‘].*['’]", 0, 'R'),
            (r"ERROR: dependencies ['‘].*['’], ['‘]([a-zA-Z0-9\-\.]*)['’],.* are not available for package ['‘].*['’]", 0, 'R'),
            (r"ERROR: dependencies.*['‘]([a-zA-Z0-9\-\.]*)['’] are not available for package ['‘].*['’]", 0, 'R'),
            (r"ERROR: dependency ['‘]([a-zA-Z0-9\-\.]*)['’] is not available for package ['‘].*['’]", 0, 'R'),
            (r"Error: Unable to find (.*)", 0, None),
            (r"Error: package ['‘]([a-zA-Z0-9\-\.]*)['’] required by", 0, 'R'),
            (r"Gem::LoadError: Could not find '([a-zA-Z0-9\-\_]*)'", 0, 'ruby'),
            (r"ImportError:.* No module named '?([a-zA-Z0-9\-\._]+)'?", 0, 'pypi'),
            (r"ImportError\: ([a-zA-Z]+) module missing", 0, None),
            (r"ImportError\: (?:No module|cannot import) named? (.*)", 0, None),
            (r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:\/\_]+)", 0, 'ruby table'),
            (r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:]+)/.*", 0, 'ruby'),
            (r"ModuleNotFoundError.*No module named (.*)", 0, None),
            (r"Native dependency '(.*)' not found", 0, "pkgconfig"),
            (r"No library found for -l([a-zA-Z\-])", 0, None),
            (r"No (?:matching distribution|local packages or working download links) found for ([a-zA-Z0-9\-\.\_]+)", 0, 'pypi'),
            (r"No package '([a-zA-Z0-9\-:]*)' found", 0, 'pkgconfig'),
            (r"No rule to make target `(.*)',", 0, None),
            (r"Package (.*) was not found in the pkg-config search path.", 0, 'pkgconfig'),
            (r"Package '([a-zA-Z0-9\-:]*)', required by '.*', not found", 0, 'pkgconfig'),
            (r"Package which this enhances but not available for checking: ['‘]([a-zA-Z0-9\-]*)['’]", 0, 'R'),
            (r"Perhaps you should add the directory containing `([a-zA-Z0-9\-:]*)\.pc'", 0, 'pkgconfig'),
            (r"Program (.*) found: NO", 0, None),
            (r"Target '[a-zA-Z0-9\-]' can't be generated as '(.*)' could not be found", 0, None),
            (r"Unable to `import (.*)`", 0, None),
            (r"Unable to find '(.*)'", 0, None),
            (r"WARNING:  [a-zA-Z\-\_]+ dependency on ([a-zA-Z0-9\-\_:]*) \([<>=~]+ ([0-9.]+).*\) .*", 0, 'ruby'),
            (r"Warning: prerequisite ([a-zA-Z:]+) [0-9\.]+ not found.", 0, 'perl'),
            (r"Warning\: no usable ([a-zA-Z0-9]+) found", 0, None),
            (r"You need ([a-zA-Z0-9\-\_]*) to build this program.", 1, None),
            (r"[Dd]ependency (.*) found: NO \(tried pkgconfig(?: and cmake)?\)", 0, 'pkgconfig'),
            (r"[Dd]ependency (.*) found: NO", 0, None),
            (r"[a-zA-Z0-9\-:]* is not installed: cannot load such file -- rdoc/([a-zA-Z0-9\-:]*)", 0, 'ruby'),
            (r"\/bin\/ld: cannot find (-l[a-zA-Z0-9\_]+)", 0, None),
            (r"^.*By not providing \"Find(.*).cmake\" in CMAKE_MODULE_PATH this.*$", 0, None),
            (r"^.*Could not find a package configuration file provided by \"(.*)\".*$", 0, None),
            (r"^.*\"(.*)\" with any of the following names.*$", 0, None),
            (r"[Cc]hecking for (.*) (?:support|development files|with pkg-config)?\.\.\. [Nn]o", 0, None),
            (r"checking (.*?)\.\.\. no", 0, None),
            (r"checking for (.*) in default path\.\.\. not found", 0, None),
            (r"checking for (.*)... configure: error", 0, None),
            (r"checking for (.*?)\.\.\. no", 0, None),
            (r"checking for [a-zA-Z0-9\_\-]+ in (.*?)\.\.\. no", 0, None),
            (r"checking for library containing (.*)... no", 0, None),
            (r"checking for perl module ([a-zA-Z:]+) [0-9\.]+... no", 0, 'perl'),
            (r"configure: error: (?:pkg-config missing|Unable to locate) (.*)", 0, None),
            (r"configure: error: ([a-zA-Z0-9]+) (?:is required to build|not found)", 0, None),
            (r"configure: error: Cannot find (.*)\. Make sure", 0, None),
            (r"fatal error\: (.*)\: No such file or directory", 0, None),
            (r"make: ([a-zA-Z0-9].+): (?:Command not found|No such file or directory)", 0, None),
            (r"meson\.build\:[\d]+\:[\d]+\: ERROR: C(?: shared or static)? library \'(.*)\' not found", 0, None),
            (r"there is no package called ['‘]([a-zA-Z0-9\-\.]*)['’]", 0, 'R'),
            (r"unable to execute '([a-zA-Z\-]*)': No such file or directory", 0, None),
            (r"warning: failed to load external entity " r"\"(/usr/share/sgml/docbook/xsl-stylesheets)/.*\"", 0, None),
            (r"which\: no ([a-zA-Z\-]*) in \(", 0, None),
            (r"you may need to install the ([a-zA-Z0-9_\-:\.]*) module", 0, 'perl'),
            (r"(a-zA-Z0-9\-) not found (re-run dependencies script to install)", 0, None),
        ]

    def set_build_pattern(self, pattern, strength):
        """Set the global default pattern and pattern strength."""
        if strength <= self.pattern_strength:
            return
        self.default_pattern = pattern
        self.pattern_strength = strength

    def detect_build_from_url(self, url):
        """Detect build patterns and build requirements from the patterns detected in the url."""
        # R package
        if "cran.r-project.org" in url or "cran.rstudio.com" in url:
            self.set_build_pattern("R", 10)

        # python
        if "pypi.python.org" in url or "pypi.debian.net" in url:
            self.set_build_pattern("distutils3", 10)

        # cpan
        if ".cpan.org/" in url or ".metacpan.org/" in url:
            self.set_build_pattern("cpan", 10)

        # ruby
        if "rubygems.org/" in url:
            self.set_build_pattern("ruby", 10)

        # rust crate
        if "crates.io" in url:
            self.set_build_pattern("cargo", 10)

        # go dependency
        if "proxy.golang.org" in url:
            self.set_build_pattern("godep", 10)

        # php modules from PECL
        if "pecl.php.net" in url:
            self.set_build_pattern("phpize", 10)

    def add_sources(self, archives, content):
        """Add archives to sources and archive_details."""
        for srcf in os.listdir(self.download_path):
            if re.search(r".*\.(mount|service|socket|target|timer|path)$", srcf):
                self.sources["unit"].append(srcf)
        self.sources["unit"].sort()
        #
        # systemd-tmpfiles uses the configuration files from
        # /usr/lib/tmpfiles.d/ directories to describe the creation,
        # cleaning and removal of volatile and temporary files and
        # directories which usually reside in directories such as
        # /run or /tmp.
        #
        if os.path.exists(os.path.normpath(
                self.download_path + "/{0}.tmpfiles".format(content.name))):
            self.sources["tmpfile"].append(
                "{}.tmpfiles".format(content.name))
        # ditto sysusers
        if os.path.exists(os.path.normpath(
                self.download_path + "/{0}.sysusers".format(content.name))):
            self.sources["sysuser"].append(
                "{}.sysusers".format(content.name))

        if content.gcov_file:
            self.sources["gcov"].append(content.gcov_file)
        self.sources["archive"] = archives[::2]
        self.sources["destination"] = archives[1::2]
        for archive, destination in zip(archives[::2], archives[1::2]):
            self.archive_details[archive + "destination"] = destination

    def write_config(self, config_f):
        """Write the config_f to configfile."""
        with open(os.path.join(self.download_path, 'options.conf'), 'w') as configfile:
            config_f.write(configfile)

    def get_metadata_conf(self):
        """Gather package metadata from the content."""
        metadata = {}
        metadata['name'] = self.content.name
        if self.urlban:
            metadata['url'] = re.sub(self.urlban, "localhost", self.content.url)
            metadata['archives'] = re.sub(self.urlban, "localhost", " ".join(self.content.archives))
        else:
            metadata['url'] = self.content.url
            metadata['archives'] = " ".join(self.content.archives)

        metadata['giturl'] = self.content.giturl
        metadata['domain'] = self.content.domain

        if self.alias:
            metadata['alias'] = self.alias
        else:
            metadata['alias'] = ""
        return metadata

    def rewrite_config_opts(self):
        """Rewrite options.conf file when an option has changed (verify_required for example)."""
        config_f = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        config_f['package'] = self.get_metadata_conf()
        config_f['autospec'] = {}

        # Populate missing configuration options
        # (in case of a user-created options.conf)
        missing = set(self.config_options.keys()).difference(set(self.config_opts.keys()))
        for option in missing:
            self.config_opts[option] = False

        for fname, comment in sorted(self.config_options.items()):
            config_f.set('autospec', '# {}'.format(comment))
            config_f['autospec'][fname] = 'true' if self.config_opts[fname] else 'false'
        self.write_config(config_f)

    def create_conf(self):
        """Create options.conf file and use deprecated configuration files or defaults to populate."""
        config_f = configparser.ConfigParser(interpolation=None, allow_no_value=True)

        # first the metadata
        config_f['package'] = self.get_metadata_conf()

        # next the options
        config_f['autospec'] = {}
        for fname, comment in sorted(self.config_options.items()):
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
        self.write_config(config_f)

    def create_buildreq_cache(self, version, buildreqs_cache):
        """Make the buildreq_cache file."""
        content = self.read_conf_file(os.path.join(self.download_path, "buildreq_cache"))
        # don't create an empty cache file
        if len(buildreqs_cache) < 1:
            try:
                # file was possibly added to git so we should clean it up
                os.unlink(content)
            except Exception:
                pass
            return
        if not content:
            pkgs = sorted(buildreqs_cache)
        else:
            pkgs = sorted(set(content[1:]).union(buildreqs_cache))
        with open(os.path.join(self.download_path, 'buildreq_cache'), "w") as cachefile:
            cachefile.write("\n".join([version] + pkgs))
        self.config_files.add('buildreq_cache')

    def create_versions(self, versions):
        """Make versions file."""
        with open(os.path.join(self.download_path, "versions"), 'w') as vfile:
            for version in versions:
                vfile.write(version)
                if versions[version]:
                    vfile.write('\t' + versions[version])
                vfile.write('\n')
        self.config_files.add("versions")

    def read_config_opts(self):
        """Read config options from path/options.conf."""
        opts_path = os.path.join(self.download_path, 'options.conf')
        if not os.path.exists(opts_path):
            self.create_conf()

        config_f = configparser.ConfigParser(interpolation=None)
        config_f.read(opts_path)
        if "autospec" not in config_f.sections():
            print("Missing autospec section in options.conf")
            sys.exit(1)

        if 'package' in config_f.sections() and config_f['package'].get('alias'):
            self.alias = config_f['package']['alias']

        for key in config_f['autospec']:
            self.config_opts[key] = config_f['autospec'].getboolean(key)

        # Rewrite the configuration file in case of formatting changes since a
        # configuration file may exist without any comments (either due to an older
        # version of autospec or if it was user-created)
        self.rewrite_config_opts()

        # Don't use the ChangeLog files if the giturl is set
        # ChangeLog is just extra noise when we can already see the gitlog
        if "package" in config_f.sections() and config_f['package'].get('giturl'):
            keys = []
            for k, v in self.transforms.items():
                if v == "ChangeLog":
                    keys.append(k)
            for k in keys:
                self.transforms.pop(k)

    def write_file(self, path, content):
        """Write the conf file name's content."""
        with open(path, 'w') as conffile:
            conffile.writelines(content)

    def read_file(self, path, track=True):
        """Read full file at path.

        If the file does not exist (or is not expected to exist)
        in the package git repo, specify 'track=False'.
        """
        try:
            with open(path, "r") as f:
                if track:
                    self.config_files.add(os.path.basename(path))
                return f.readlines()
        except EnvironmentError:
            return []

    def read_conf_file(self, path, track=True):
        """Read configuration file at path.

        If the config file does not exist (or is not expected to exist)
        in the package git repo, specify 'track=False'.
        """
        lines = self.read_file(path, track=track)
        return [line.strip() for line in lines if not line.strip().startswith("#") and line.split()]

    def validate_extras_content(self, lines, fname):
        """Verify extras file contents are valid match strings."""
        newlines = []
        for line in lines:
            if '*' not in line:
                newlines.append(line)
                continue
            nline = line.split('/')
            invalid = False
            for itm in nline:
                if itm.count('*') > 1:
                    invalid = True
                    break
            if invalid:
                print_warning(f"Ignoring '{line}' from {fname} (can only use a single '*' between each '/')")
            else:
                newlines.append(nline)
        return newlines

    def process_extras_file(self, fname, name, filemanager):
        """Process extras type subpackages configuration."""
        content = {}
        data = self.read_conf_file(os.path.join(self.download_path, fname))
        content['files'] = self.validate_extras_content(data, fname)
        req_file = os.path.join(self.download_path, f'{fname}_requires')
        if os.path.isfile(req_file):
            content['requires'] = self.read_conf_file(req_file)

        filemanager.file_maps[name] = content

    def process_requires_file(self, fname, requirements, req_type, subpkg=None):
        """Process manual subpackage requirements file."""
        content = self.read_conf_file(os.path.join(self.download_path, fname))
        for pkg in content:
            if req_type == 'add':
                requirements.add_requires(pkg, self.os_packages, override=True, subpkg=subpkg)
            else:
                requirements.ban_requires(pkg, subpkg=subpkg)

    def process_provides_file(self, fname, requirements, prov_type, subpkg=None):
        """Process manual subpackage provides file."""
        content = self.read_conf_file(os.path.join(self.download_path, fname))
        for pkg in content:
            if prov_type == 'add':
                requirements.add_provides(pkg, subpkg=subpkg)
            else:
                requirements.ban_provides(pkg, subpkg=subpkg)

    def read_script_file(self, path, track=True):
        """Read RPM script snippet file at path.

        Returns verbatim, except for possibly the first line.

        If the config file does not exist (or is not expected to exist)
        in the package git repo, specify 'track=False'.
        """
        lines = self.read_file(path, track=track)
        if len(lines) > 0 and (lines[0].startswith('#!') or lines[0].startswith('# -*- ')):
            lines = lines[1:]
        # Remove any trailing whitespace and newlines. The newlines are later
        # restored by writer functions.
        return [line.rstrip() for line in lines]

    def setup_patterns(self, path=None):
        """Read each pattern configuration file and assign to the appropriate variable."""
        read_pattern_conf("ignored_commands", self.ignored_commands, list_format=True, path=path)
        read_pattern_conf("failed_commands", self.failed_commands, path=path)
        read_pattern_conf("gems", self.gems, path=path)
        read_pattern_conf("license_hashes", self.license_hashes, path=path)
        read_pattern_conf("license_translations", self.license_translations, path=path)
        read_pattern_conf("license_blacklist", self.license_blacklist, list_format=True, path=path)
        read_pattern_conf("qt_modules", self.qt_modules, path=path)
        read_pattern_conf("cmake_modules", self.cmake_modules, path=path)

    def parse_existing_spec(self, name):
        """Determine the old version, old patch list, old keyid, and cves from old spec file."""
        spec = os.path.join(self.download_path, "{}.spec".format(name))
        if not os.path.exists(spec):
            return

        found_old_version = False
        found_old_patches = False
        ver_regex = r"^Version *: *(.*) *$"
        patch_regex = r"^Patch[0-9]* *: *(.*) *$"

        # If git history exists, read the Version and Patch* spec header fields
        # from the latest commit to take priority over the working copy.
        cmd = ["git", "-C", self.download_path, "grep", "-E", "-h", ver_regex, "HEAD", spec]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            # The first matching line is from the spec header (hopefully)
            line = result.stdout.decode().split("\n")[0]
            m = re.search(ver_regex, line)
            if m:
                self.old_version = m.group(1)
                found_old_version = True

        cmd = ["git", "-C", self.download_path, "grep", "-E", "-h", patch_regex, "HEAD", spec]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            lines = result.stdout.decode().split("\n")
            for line in lines:
                m = re.search(patch_regex, line)
                if m:
                    self.old_patches.append(m.group(1).lower())
                    found_old_patches = True

        with open_auto(spec, "r") as inp:
            for line in inp.readlines():
                line = line.strip().replace("\r", "").replace("\n", "")
                if "Source0 file verified with key" in line:
                    keyidx = line.find('0x') + 2
                    self.old_keyid = line[keyidx:].split()[0] if keyidx > 2 else self.old_keyid
                # As a fallback, read the Version and Patch* header fields from the
                # working copy of the spec, in case a git repo does not exist.
                m = re.search(ver_regex, line)
                if m and not found_old_version:
                    self.old_version = m.group(1)
                    found_old_version = True
                m = re.search(patch_regex, line)
                if m and not found_old_patches:
                    self.old_patches.append(m.group(1).lower())

        # Ignore nopatch
        for patch in self.patches:
            patch = patch.lower()
            if patch not in self.old_patches and patch.endswith(".patch") and patch.startswith("cve-"):
                self.cves.append(patch.upper().split(".PATCH")[0])

    def parse_config_versions(self):
        """Parse the versions configuration file."""
        # Only actually parse it the first time around
        if not self.parsed_versions:
            for line in self.read_conf_file(os.path.join(self.download_path, "versions")):
                # Simply whitespace-separated fields
                fields = line.split()
                version = fields.pop(0)
                if len(fields):
                    url = fields.pop(0)
                else:
                    url = ""
                # Catch and report duplicate URLs in the versions file. Don't stop,
                # but assume only the first one is valid and drop the rest.
                if version in self.parsed_versions and url != self.parsed_versions[version]:
                    print_warning("Already have a URL defined for {}: {}"
                                  .format(version, self.parsed_versions[version]))
                    print_warning("Dropping {}, but you should check my work"
                                  .format(url))
                else:
                    self.parsed_versions[version] = url
                if len(fields):
                    print_warning("Extra fields detected in `versions` file entry:\n{}"
                                  .format(line))
                    print_warning("I'll delete them, but you should check my work")

        # We'll combine what we just parsed from the versions file with any other
        # versions that have already been defined, most likely the version actually
        # provided in the Makefile's URL variable, so we don't drop any.
        for version in self.parsed_versions:
            self.versions[version] = self.parsed_versions[version]

        return self.versions

    def write_default_conf_file(self, name, wrapper, description):
        """Write default configuration file with description to file name."""
        self.config_files.add(name)
        filename = os.path.join(self.download_path, name)
        if os.path.isfile(filename):
            return

        write_out(filename, wrapper.fill(description) + "\n")

    def remove_backport_patch(self, patch_name):
        """Remove backport patch from patch set."""
        if not patch_name.startswith('backport-'):
            return 0
        if patch_name not in self.patches:
            return 0
        series_file = os.path.join(self.download_path, 'series')
        series_content = self.read_file(series_file)
        new_content = []
        for line in series_content:
            if line.strip() == patch_name:
                continue
            new_content.append(line)
        self.write_file(series_file, new_content)
        self.patches.remove(patch_name)
        print_info(f'Removed patch: {patch_name}')
        return 1

    def parse_config_files(self, bump, filemanager, version, requirements):
        """Parse the various configuration files that may exist in the package directory."""
        packages_file = None

        # Require autospec.conf for additional features
        if os.path.exists(self.config_file):
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_file)

            if "autospec" not in config.sections():
                print("Missing autospec section..")
                sys.exit(1)

            self.git_uri = config['autospec'].get('git', None)
            self.license_fetch = config['autospec'].get('license_fetch', None)
            self.license_show = config['autospec'].get('license_show', None)
            packages_file = config['autospec'].get('packages_file', None)
            self.yum_conf = config['autospec'].get('yum_conf', None)
            self.failed_pattern_dir = config['autospec'].get('failed_pattern_dir', None)

            # support reading the local files relative to config_file
            if packages_file and not os.path.isabs(packages_file):
                packages_file = os.path.join(os.path.dirname(self.config_file), packages_file)
            if self.yum_conf and not os.path.isabs(self.yum_conf):
                self.yum_conf = os.path.join(os.path.dirname(self.config_file), self.yum_conf)
            if self.failed_pattern_dir and not os.path.isabs(self.failed_pattern_dir):
                self.failed_pattern_dir = os.path.join(os.path.dirname(self.config_file), self.failed_pattern_dir)

            if not packages_file:
                print("Warning: Set [autospec][packages_file] path to package list file for "
                      "requires validation")
                packages_file = os.path.join(os.path.dirname(self.config_file), "packages")

            self.urlban = config['autospec'].get('urlban', None)

        # Read values from options.conf (and deprecated files) and rewrite as necessary
        self.read_config_opts()

        if not self.git_uri:
            print("Warning: Set [autospec][git] upstream template for remote git URI configuration")
        if not self.license_fetch:
            print("Warning: Set [autospec][license_fetch] uri for license fetch support")
        if not self.license_show:
            print("Warning: Set [autospec][license_show] uri for license link check support")
        if not self.yum_conf:
            print("Warning: Set [autospec][yum_conf] path to yum.conf file for whatrequires validation")
            self.yum_conf = os.path.join(os.path.dirname(self.config_file), "dnf.conf")

        if packages_file:
            self.os_packages = set(self.read_conf_file(packages_file, track=False))
        else:
            self.os_packages = set(self.read_conf_file("~/packages", track=False))

        wrapper = textwrap.TextWrapper()
        wrapper.initial_indent = "# "
        wrapper.subsequent_indent = "# "

        self.write_default_conf_file("buildreq_ban", wrapper,
                                     "This file contains build requirements that get picked up but are "
                                     "undesirable. One entry per line, no whitespace.")
        self.write_default_conf_file("pkgconfig_ban", wrapper,
                                     "This file contains pkgconfig build requirements that get picked up but"
                                     " are undesirable. One entry per line, no whitespace.")
        self.write_default_conf_file("requires_ban", wrapper,
                                     "This file contains runtime requirements that get picked up but are "
                                     "undesirable. One entry per line, no whitespace.")
        self.write_default_conf_file("buildreq_add", wrapper,
                                     "This file contains additional build requirements that did not get "
                                     "picked up automatically. One name per line, no whitespace.")
        self.write_default_conf_file("pkgconfig_add", wrapper,
                                     "This file contains additional pkgconfig build requirements that did "
                                     "not get picked up automatically. One name per line, no whitespace.")
        self.write_default_conf_file("requires_add", wrapper,
                                     "This file contains additional runtime requirements that did not get "
                                     "picked up automatically. One name per line, no whitespace.")
        self.write_default_conf_file("excludes", wrapper,
                                     "This file contains the output files that need %exclude. Full path "
                                     "names, one per line.")

        content = self.read_conf_file(os.path.join(self.download_path, "release"))
        if content and content[0]:
            r = int(content[0])
            if bump:
                r += 1
            self.content.release = str(r)
            print("Release     :", self.content.release)

        content = self.read_conf_file(os.path.join(self.download_path, "extra_sources"))
        for source in content:
            fields = source.split(maxsplit=1)
            print("Adding additional source file: %s" % fields[0])
            self.config_files.add(os.path.basename(fields[0]))
            self.extra_sources.append(fields)

        content = self.read_conf_file(os.path.join(self.download_path, "buildreq_ban"))
        for banned in content:
            print("Banning build requirement: %s." % banned)
            requirements.banned_buildreqs.add(banned)
            requirements.buildreqs.discard(banned)
            requirements.buildreqs_cache.discard(banned)

        content = self.read_conf_file(os.path.join(self.download_path, "pkgconfig_ban"))
        for banned in content:
            banned = "pkgconfig(%s)" % banned
            print("Banning build requirement: %s." % banned)
            requirements.banned_buildreqs.add(banned)
            requirements.buildreqs.discard(banned)
            requirements.buildreqs_cache.discard(banned)

        content = self.read_conf_file(os.path.join(self.download_path, "buildreq_add"))
        for extra in content:
            print("Adding additional build requirement: %s." % extra)
            requirements.add_buildreq(extra)

        cache_file = os.path.join(self.download_path, "buildreq_cache")
        content = self.read_conf_file(cache_file)
        if content and content[0] == version:
            for extra in content[1:]:
                print("Adding additional build (cache) requirement: %s." % extra)
                requirements.add_buildreq(extra)
        else:
            try:
                os.unlink(cache_file)
            except FileNotFoundError:
                pass
            except Exception as e:
                print_warning(f"Unable to remove buildreq_cache file: {e}")

        content = self.read_conf_file(os.path.join(self.download_path, "pkgconfig_add"))
        for extra in content:
            extra = "pkgconfig(%s)" % extra
            print("Adding additional build requirement: %s." % extra)
            requirements.add_buildreq(extra)

        # Handle dynamic configuration files (per subpackage)
        for fname in os.listdir(self.download_path):
            if re.search(r'.+_requires_add$', fname):
                subpkg = fname[:-len("_requires_add")]
                self.process_requires_file(fname, requirements, 'add', subpkg)
            elif re.search(r'.+_requires_ban$', fname):
                subpkg = fname[:-len("_requires_ban")]
                self.process_requires_file(fname, requirements, 'ban', subpkg)
            elif fname == 'requires_add':
                self.process_requires_file(fname, requirements, 'add')
            elif fname == 'requires_ban':
                self.process_requires_file(fname, requirements, 'ban')
            elif fname == 'provides_add':
                self.process_provides_file(fname, requirements, 'add')
            elif fname == 'provides_ban':
                self.process_provides_file(fname, requirements, 'ban')
            elif re.search(r'.+_provides_add$', fname):
                subpkg = fname[:-len("_requires_add")]
                self.process_provides_file(fname, requirements, 'add', subpkg)
            elif re.search(r'.+_provides_ban$', fname):
                subpkg = fname[:-len("_provides_ban")]
                self.process_provides_file(fname, requirements, 'ban', subpkg)
            elif re.search(r'.+_extras$', fname):
                # Prefix all but blessed names with extras-
                name = fname[:-len("_extras")]
                if name not in ('dev', 'tests'):
                    name = f'extras-{name}'
                self.process_extras_file(fname, name, filemanager)
            elif fname == 'extras':
                self.process_extras_file(fname, fname, filemanager)

        content = self.read_conf_file(os.path.join(self.download_path, "excludes"))
        for exclude in content:
            print("%%exclude for: %s." % exclude)
        filemanager.manual_excludes += content
        filemanager.excludes += content

        content = self.read_conf_file(os.path.join(self.download_path, "setuid"))
        for suid in content:
            print("setuid for  : %s." % suid)
        filemanager.setuid += content

        content = self.read_conf_file(os.path.join(self.download_path, "attrs"))
        for line in content:
            attr = line.split()
            filename = attr.pop()
            print("%attr({0},{1},{2}) for: {3}".format(
                attr[0], attr[1], attr[2], filename))
            filemanager.attrs[filename] = attr

        self.patches += self.read_conf_file(os.path.join(self.download_path, "series"))
        pfiles = [("%s/%s" % (self.download_path, x.split(" ")[0])) for x in self.patches]
        cmd = "grep -E \"(\+\+\+|\-\-\-).*((Makefile.am)|(aclocal.m4)|(configure.ac|configure.in))\" %s" % " ".join(pfiles)  # noqa: W605
        if self.patches and call(cmd,
                                 check=False,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL) == 0:
            self.autoreconf = True

        # Parse the version-specific patch lists
        update_security_sensitive = False
        for versionp in self.versions:
            self.verpatches[versionp] = self.read_conf_file(os.path.join(self.download_path, '.'.join(['series', versionp])))
            if any(p.lower().startswith('cve-') for p in self.verpatches[versionp]):
                update_security_sensitive = True

        if any(p.lower().startswith('cve-') for p in self.patches):
            update_security_sensitive = True

        if update_security_sensitive:
            self.config_opts['security_sensitive'] = True
            self.rewrite_config_opts()

        self.pypi_overrides += self.read_conf_file(os.path.join(self.download_path, "pypi_overrides"))

        content = self.read_conf_file(os.path.join(self.download_path, "configure"))
        self.extra_configure = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "configure32"))
        self.extra_configure32 = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "configure64"))
        self.extra_configure64 = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "configure_avx2"))
        self.extra_configure_avx2 = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "configure_avx512"))
        self.extra_configure_avx512 = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "configure_openmpi"))
        self.extra_configure_openmpi = " \\\n".join(content)

        if self.config_opts["keepstatic"]:
            self.disable_static = ""
        if self.config_opts['broken_parallel_build']:
            self.parallel_build = ""

        content = self.read_conf_file(os.path.join(self.download_path, "make_command"))
        if content and content[0]:
            self.make_command = content[0]

        content = self.read_conf_file(os.path.join(self.download_path, "make_args"))
        if content:
            self.extra_make = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "make32_args"))
        if content:
            self.extra32_make = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "make_install_args"))
        if content:
            self.extra_make_install = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "make32_install_args"))
        if content:
            self.extra_make32_install = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "install_macro"))
        if content and content[0]:
            self.install_macro = content[0]

        content = self.read_conf_file(os.path.join(self.download_path, "cmake_args"))
        if content:
            self.extra_cmake = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "cmake_args_openmpi"))
        if content:
            self.extra_cmake_openmpi = " \\\n".join(content)

        content = self.read_conf_file(os.path.join(self.download_path, "cmake_srcdir"))
        if content and content[0]:
            self.cmake_srcdir = content[0]

        content = self.read_conf_file(os.path.join(self.download_path, "subdir"))
        if content and content[0]:
            self.subdir = content[0]

        content = self.read_conf_file(os.path.join(self.download_path, "build_pattern"))
        if content and content[0]:
            self.set_build_pattern(content[0], 20)
            self.autoreconf = False

        content = self.read_script_file(os.path.join(self.download_path, "make_check_command"))
        if content:
            check.tests_config = '\n'.join(content)

        content = self.read_conf_file(os.path.join(self.download_path, self.content.name + ".license"))
        if content and content[0]:
            words = content[0].split()
            for word in words:
                if word.find(":") < 0:
                    if not license.add_license(word, self.license_translations, self.license_blacklist):
                        print_warning("{}: blacklisted license {} ignored.".format(self.content.name + ".license", word))

        content = self.read_conf_file(os.path.join(self.download_path, "golang_libpath"))
        if content and content[0]:
            self.content.golibpath = content[0]
            print("golibpath   : {}".format(self.content.golibpath))

        if self.config_opts['use_clang']:
            self.config_opts['funroll-loops'] = False
            requirements.add_buildreq("llvm")

        if self.config_opts['32bit']:
            requirements.add_buildreq("glibc-libc32")
            requirements.add_buildreq("glibc-dev32")
            requirements.add_buildreq("gcc-dev32")
            requirements.add_buildreq("gcc-libgcc32")
            requirements.add_buildreq("gcc-libstdc++32")

        if self.config_opts['openmpi']:
            requirements.add_buildreq("openmpi-dev")
            requirements.add_buildreq("modules")
            # MPI testsuites generally require "openssh"
            requirements.add_buildreq("openssh")

        self.prep_prepend = self.read_script_file(os.path.join(self.download_path, "prep_prepend"))
        if os.path.isfile(os.path.join(self.download_path, "prep_append")):
            os.rename(os.path.join(self.download_path, "prep_append"), os.path.join(self.download_path, "build_prepend"))
        self.make_prepend = self.read_script_file(os.path.join(self.download_path, "make_prepend"))
        self.build_prepend = self.read_script_file(os.path.join(self.download_path, "build_prepend"))
        self.build_prepend_once = self.read_script_file(os.path.join(self.download_path, "build_prepend_once"))
        self.build_append = self.read_script_file(os.path.join(self.download_path, "build_append"))
        self.install_prepend = self.read_script_file(os.path.join(self.download_path, "install_prepend"))
        if os.path.isfile(os.path.join(self.download_path, "make_install_append")):
            os.rename(os.path.join(self.download_path, "make_install_append"), os.path.join(self.download_path, "install_append"))
        self.install_append = self.read_script_file(os.path.join(self.download_path, "install_append"))
        self.service_restart = self.read_conf_file(os.path.join(self.download_path, "service_restart"))

        if self.config_opts['pgo']:
            self.profile_payload = self.read_script_file(os.path.join(self.download_path, "profile_payload"))

        self.custom_desc = self.read_conf_file(os.path.join(self.download_path, "description"))
        self.custom_summ = self.read_conf_file(os.path.join(self.download_path, "summary"))
