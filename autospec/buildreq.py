#!/bin/true
#
# buildreq.py - part of autospec
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
# Deduce and manage build requirements
#

import ast
import configparser
import json
import os
import re
import tomllib

import pypidata
import specdescription
import util


def is_qmake_pro(f):
    """Test if file extension is pro and not hidden."""
    return f.endswith(".pro") and not f.startswith(".")


def old_python_module(req):
    """Check if the req is only for old python versions."""
    # Format for the line is expected to be:
    #  'module_name >= x.y.z; python_version<"x.y"'
    for block in req.split(';'):
        if 'python_version' in block:
            loc = block.find('python_version')
            if '<' in block[loc:]:
                return True
    return False


def clean_python_req(req):
    """Strip version information from req."""
    if not req:
        return ""
    if req[0] == "#":
        return ""
    ret = req.rstrip("\n\r").strip()
    i = ret.find(";")
    if i >= 0:
        if old_python_module(ret):
            return ""
        else:
            ret = ret[:i]
    i = ret.find("<")
    if i >= 0:
        ret = ret[:i]
    i = ret.find("\n")
    if i >= 0:
        ret = ret[:i]
    i = ret.find(">")
    if i >= 0:
        ret = ret[:i]
    i = ret.find("=")
    if i >= 0:
        ret = ret[:i]
    i = ret.find("#")
    if i >= 0:
        ret = ret[:i]
    i = ret.find("!")
    if i >= 0:
        ret = ret[:i]
    i = ret.find("[")
    if i >= 0:
        ret = ret[:i]
    i = ret.find("~")
    if i >= 0:
        ret = ret[:i]
    i = ret.find(" ")
    if i >= 0:
        ret = ret[:i]

    ret = ret.strip()
    # use the dictionary to translate funky names to our current pgk names
    ret = util.translate(ret)
    if ret:
        # normalize to pypi name
        ret = pypidata.get_pypi_name(ret, miss=True)
        if ret and ret[0] == '_':
            # These tend to be leftover junk
            # ignore them
            ret = ""
    return ret


def python_req_in_filtered_path(path):
    """Return True if the python requirement file is in a path we don't want to look at."""
    if "/demo/" in path:
        return True
    if "/doc/" in path:
        return True
    if "/docs/" in path:
        return True
    if "/example/" in path:
        return True
    if "/test/" in path:
        return True
    if "/tests/" in path:
        return True
    if "/plugin/" in path:
        return True
    if "/plugins/" in path:
        return True

    return False


def is_number(num_str):
    """Return True if num_str can be represented as a number."""
    try:
        float(num_str)
        return True
    except ValueError:
        return False


def is_version(num_str):
    """Return True if num_str looks like a version number."""
    if re.search(r'^\d+(\.\d+)*$', num_str):
        return True

    return False


def parse_modules_list(modules_string, is_cmake=False):
    """Parse the modules_string for the list of modules, stripping out the version requirements."""
    if is_cmake:
        modules = [m for m in re.split(r'\s*([><]?=|\${?[^}]*}?)\s*', modules_string)]
        modules = filter(None, modules)
    else:
        modules = [m.strip('[]').strip('"') for m in modules_string.split()]
    res = []
    next_is_ver = False
    for mod in modules:
        if next_is_ver:
            next_is_ver = False
            continue

        if any(s in mod for s in ['<', '>', '=']):
            next_is_ver = True
            continue

        if is_number(mod):
            continue

        if is_version(mod):
            continue

        if mod.startswith('$'):
            continue

        if len(mod) >= 2:
            res.append(mod)

    return res


def _get_desc_field(field, desc):
    """Get a field value from an R package DESCRIPTION file.

    Internal helper to read the value for the given field in an R package
    DESCRIPTION file. Returns a list representing the value: one or more
    package names.

    The value is a comma-separated list of package names and, optionally, their
    version constraints. The entire value is split on the commas and
    surrounding whitespace to convert it to a list of package names, also
    skipping any declared version constraints.

    Consider a field with a value consisting of four package names, one with a
    version constraint, and three without. The field and value may take one of
    the following forms, or variants thereof:

      (a) all on a single line:

          FIELD: PKG1, PKG2 (VERSION CONSTRAINT), PKG3, PKG4

      (b) split across multiple lines with field name and some package names
          declared on the first line:

          FIELD: PKG1, PKG2 (VERSION CONSTRAINT),
                PKG3, PKG4

      (c) split across multiple lines, with the field name on the first
          line, and one package name per line on the remaining lines:

          FIELD:
              PKG1,
              PKG2 (VERSION CONSTRAINT),
              PKG3,
              PKG4
    """
    val = []
    # Note that fields may appear on any line, and values may span multiple
    # lines. The end of the match is captured by either a lookahead assertion
    # for the "next" field in the file, or \Z, which matches EOF in this case.
    pat = re.compile(r"^" + field + r":(.*?)((?=\n\S+:)|\Z)", re.MULTILINE | re.DOTALL)
    match = pat.search(desc)
    if match:
        joined = match.group(1).replace("\n", " ").strip(' ,')
        if joined:
            val = re.split(r"\s*,\s*", joined)
            # Also omit any version constraints
            # For example, translate "stringr (>= 1.2.0)" -> "stringr"
            val = [re.split(r'\s*\(', v)[0] for v in val]
    return val


# FIXME: this list should be autodetected
def _get_r_provides():
    """Set of packages provided by R, serving as blacklist for CRAN deps."""
    provides = [
        "KernSmooth",
        "MASS",
        "Matrix",
        "base",
        "boot",
        "class",
        "cluster",
        "codetools",
        "compiler",
        "datasets",
        "foreign",
        "grDevices",
        "graphics",
        "grid",
        "lattice",
        "methods",
        "mgcv",
        "nlme",
        "nnet",
        "parallel",
        "rpart",
        "spatial",
        "splines",
        "stats",
        "stats4",
        "survival",
        "tcltk",
        "tools",
        "translations",
        "utils",
    ]
    return set(provides)


class Requirements(object):
    """Handle package build and runtime requiremnts."""

    def __init__(self, url):
        """Initialize Default requirements settings."""
        self.banned_anywhere_requires = set(["futures",
                                             "configparser",
                                             "typing",
                                             "ipaddress",
                                             "pypi-nose",
                                             "pypi(nose)"])
        self.banned_requires = {None: set()}
        self.buildreqs = set()
        self.buildreqs_cache = set()
        self.requires = {None: set(), "pypi": set()}
        self.banned_provides = {None: set()}
        self.provides = {None: set(), "pypi": set()}
        self.extra_cmake = set()
        self.extra_cmake_openmpi = set()
        self.verbose = False
        self.pypi_provides = None
        self.banned_buildreqs = set(["llvm-devel",
                                     "gcj",
                                     "pkgconfig(dnl)",
                                     "pkgconfig(hal)",
                                     "tslib-0.0",
                                     "pkgconfig(parallels-sdk)",
                                     "oslo-python",
                                     "libxml2No-python",
                                     "futures",
                                     "configparser",
                                     "setuptools_scm[toml]",
                                     "typing",
                                     "ipaddress",
                                     "pypi-nose",
                                     "pypi(setuptools_scm_git_archive)",
                                     "pypi(setuptools_changelog_shortener)",
                                     "pypi(nose)"])
        self.autoreconf_reqs = ["gettext-bin",
                                "automake-dev",
                                "automake",
                                "m4",
                                "libtool",
                                "libtool-dev",
                                "pkg-config-dev"]
        if "gnome.org" in url:
            self.add_buildreq("buildreq-gnome")
        if "kde.org" in url or "https://github.com/KDE" in url:
            self.add_buildreq("buildreq-kde")

    def add_buildreq(self, req, cache=False):
        """Add req to the global buildreqs set if req is not banned."""
        new = True
        if not req:
            return False
        req.strip()
        if req in self.banned_buildreqs:
            return False
        if req in self.buildreqs:
            new = False
        if self.verbose and new:
            print("  Adding buildreq:", req)

        self.buildreqs.add(req)
        if cache and new:
            self.buildreqs_cache.add(req)
        return new

    def ban_requires(self, ban, subpkg=None):
        """Add ban to the banned set (and remove it from requires if it was added)."""
        ban = ban.strip()
        if (requires := self.requires.get(subpkg)) is None:
            requires = self.requires[subpkg] = set()
        if (banned_requires := self.banned_requires.get(subpkg)) is None:
            banned_requires = self.banned_requires[subpkg] = set()
        requires.discard(ban)
        banned_requires.add(ban)

    def add_requires(self, req, packages, override=False, subpkg=None):
        """Add req to the requires set if it is present in buildreqs and packages and is not banned."""
        new = True
        req = req.strip()
        if (requires := self.requires.get(subpkg)) is None:
            requires = self.requires[subpkg] = set()
        if req in requires:
            new = False
        if (banned_requires := self.banned_requires.get(subpkg)) is None:
            banned_requires = self.banned_requires[subpkg] = set()
        if req in banned_requires:
            return False
        if req in self.banned_anywhere_requires:
            return False

        if req not in self.buildreqs and req not in packages and not override:
            if req:
                print("requirement '{}' not found in buildreqs or os_packages, skipping".format(req))
            return False
        if new:
            # print("Adding requirement:", req)
            requires.add(req)
        return new

    def ban_provides(self, ban, subpkg=None):
        """Add ban to the banned set (and remove it from provides if it was added)."""
        ban = ban.strip()
        if (provides := self.provides.get(subpkg)) is None:
            provides = self.provides[subpkg] = set()
        if (banned_provides := self.banned_provides.get(subpkg)) is None:
            banned_provides = self.banned_provides[subpkg] = set()
        provides.discard(ban)
        banned_provides.add(ban)

    def add_provides(self, prov, subpkg=None):
        """Add prov to the provides set if it is not banned."""
        new = True
        prov = prov.strip()
        if (provides := self.provides.get(subpkg)) is None:
            provides = self.provides[subpkg] = set()
        if prov in provides:
            new = False
        if (banned_provides := self.banned_provides.get(subpkg)) is None:
            banned_provides = self.banned_provides[subpkg] = set()
        if prov in banned_provides:
            return False
        if new:
            provides.add(prov)
        return new

    def add_pkgconfig_buildreq(self, preq, conf32, cache=False):
        """Format preq as pkgconfig req and add to buildreqs."""
        if conf32:
            req = "pkgconfig(32" + preq + ")"
            self.add_buildreq(req, cache)
        req = "pkgconfig(" + preq + ")"
        return self.add_buildreq(req, cache)

    def configure_ac_line(self, line, conf32):
        """Parse configure_ac line and add appropriate buildreqs."""
        # print("----\n", line, "\n----")
        # ignore comments
        if line.startswith('#'):
            return

        pat_reqs = [(r"AC_CHECK_FUNC([tgetent]", ["ncurses-devel"]),
                    ("PROG_INTLTOOL", ["intltool"]),
                    ("GETTEXT_PACKAGE", ["gettext", "perl(XML::Parser)"]),
                    ("AM_GLIB_GNU_GETTEXT", ["gettext", "perl(XML::Parser)"]),
                    ("GTK_DOC_CHECK", ["gtk-doc", "gtk-doc-dev", "libxslt-bin", "docbook-xml"]),
                    ("AC_PROG_SED", ["sed"]),
                    ("AC_PROG_GREP", ["grep"])]

        for pat, reqs in pat_reqs:
            if pat in line:
                for req in reqs:
                    self.add_buildreq(req)

        line = line.strip()

        # XFCE uses an equivalent to PKG_CHECK_MODULES, handle them both the same
        for style in [r"PKG_CHECK_MODULES\((.*?)\)", r"XDT_CHECK_PACKAGE\((.*?)\)"]:
            match = re.search(style, line)
            L = []
            if match:
                L = match.group(1).split(",")
            if len(L) > 1:
                rqlist = L[1].strip()
                for req in parse_modules_list(rqlist):
                    self.add_pkgconfig_buildreq(req, conf32)

        # PKG_CHECK_EXISTS(MODULES, action-if-found, action-if-not-found)
        match = re.search(r"PKG_CHECK_EXISTS\((.*?)\)", line)
        if match:
            L = match.group(1).split(",")
            rqlist = L[0].strip()
            for req in parse_modules_list(rqlist):
                self.add_pkgconfig_buildreq(req, conf32)

    def parse_configure_ac(self, filename, config):
        """Parse the configure.ac file for build requirements."""
        buf = ""
        depth = 0
        # print("Configure parse: ", filename)
        f = util.open_auto(filename, "r")
        while 1:
            c = f.read(1)
            if not c:
                break
            if c == "(":
                depth += 1
            if c == ")" and depth > 0:
                depth -= 1
            if c != "\n":
                buf += c
            if c == "\n" and depth == 0:
                self.configure_ac_line(buf, config.config_opts.get('32bit'))
                buf = ""
        self.configure_ac_line(buf, config.config_opts.get('32bit'))
        f.close()

    def parse_r_description(self, filename, packages):
        """Update build/runtime requirements according to the R package description."""
        deps = []
        with util.open_auto(filename, "r") as desc:
            content = desc.read()
            deps = _get_desc_field("Depends", content)
            deps.extend(_get_desc_field("Imports", content))
            deps.extend(_get_desc_field("LinkingTo", content))
        r_provides = _get_r_provides()
        for dep in deps:
            if dep == 'R':
                continue
            if dep in r_provides:
                continue
            pkg = 'R-' + dep
            self.add_buildreq(pkg)
            self.add_requires(pkg, packages)

    def set_build_req(self, config):
        """Add build requirements based on the build pattern."""

    def findpackage_parse_lines(self, fp_line, line_iter, cmake_modules):
        """Parse find_package multiline segment of the line_iter."""
        qt6module = re.compile(r"^[^#]*find_package\(\s*\bQt6.*", re.I)
        kf6module = re.compile(r"^[^#]*find_package\(\s*\bKF6.*", re.I)
        ns = ''
        if qt6module.search(fp_line):
            ns = 'qt6'
        elif kf6module.search(fp_line):
            ns = 'kf6'
        while True:
            ln = next(line_iter).strip()
            if not ln:
                continue
            modules = ln.strip(')').split(' ')
            for module in modules:
                if module:
                    if pkg := cmake_modules.get(f"{ns}.{module}"):
                        self.add_buildreq(pkg)
            if ')' in ln:
                break

    def parse_cmake(self, filename, cmake_modules, conf32):
        """Scan a .cmake or CMakeLists.txt file for what's it's actually looking for."""
        findpackage = re.compile(r"^[^#]*find_package\((\w+)\b.*\)", re.I)
        findpackage_multiline = re.compile(r"^[^#]*find_package\((\w+)\b.*", re.I)
        pkgconfig = re.compile(r"^[^#]*pkg_check_modules\s*\([\w\-]+ (.*)\)", re.I)
        pkg_search_modifiers = {'REQUIRED', 'QUIET', 'NO_CMAKE_PATH',
                                'NO_CMAKE_ENVIRONMENT_PATH', 'IMPORTED_TARGET'}
        extractword = re.compile(r'(?:"([^"]+)"|(\S+))(.*)')

        with util.open_auto(filename, "r") as f:
            lines = iter(f.readlines())
        for line in lines:
            if match := findpackage.search(line):
                module = match.group(1)
                if pkgs := cmake_modules.get(module):
                    # Some of the entries in cmake_modules list multiple packages, space-separated, so we need to split.
                    # Otherwise, anything in buildreq_ban would have to match the entire string, not just a single package name.
                    # For example: Png2Ico, extra-cmake-modules png2ico
                    # buildreq_ban would have to contain "extra-cmake-modules png2ico" to match, instead of just "png2ico"
                    for pkg in pkgs.split():
                        self.add_buildreq(pkg)
            elif findpackage_multiline.search(line):
                self.findpackage_parse_lines(line, lines, cmake_modules)

            if match := pkgconfig.search(line):
                rest = match.group(1)
                while rest:
                    wordmatch = extractword.search(rest)
                    if not wordmatch:
                        break
                    rest = wordmatch.group(3)
                    if wordmatch.group(2) in pkg_search_modifiers:
                        continue
                    # Only one of the two groups can match at a time
                    module = wordmatch.group(1)
                    if not module:
                        module = wordmatch.group(2)
                    # We have a match, so strip out any version info
                    for m in parse_modules_list(module, is_cmake=True):
                        self.add_pkgconfig_buildreq(m, conf32)

    def qmake_profile(self, filename, qt_modules):
        """Scan .pro file for build requirements."""
        with util.open_auto(filename, "r") as f:
            lines = f.readlines()

        pat = re.compile(r"(QT|QT_PRIVATE|QT_FOR_CONFIG).*=\s*(.*)\s*")
        for line in lines:
            match = pat.search(line)
            if not match:
                continue
            s = match.group(2)
            for module in s.split():
                module = re.sub('-private$', '', module)
                try:
                    pc = qt_modules[module]
                    self.add_buildreq('pkgconfig({})'.format(pc))
                except Exception:
                    pass

    def grab_python_requirements(self, descfile, packages):
        """Add python requirements from requirements.txt file."""
        with util.open_auto(descfile, "r") as f:
            lines = f.readlines()

        for line in lines:
            if '[' in line:
                break
            clean_line = clean_python_req(line)
            if 'pytest' in line:
                continue
            if clean_line:
                if self.add_buildreq(f"pypi({clean_line})"):
                    self.add_requires(f"pypi({clean_line})", packages, override=True, subpkg="python3")

    def add_pyproject_requires(self, filename):
        """Detect build requirements listed in pyproject.toml in the build-system's requires lists."""
        with util.open_auto(filename) as pfile:
            pyproject = tomllib.loads(pfile.read())
        if not (buildsys := pyproject.get("build-system")):
            return

        if not (requires := buildsys.get("requires")):
            return

        for require in requires:
            if dep := clean_python_req(require):
                self.add_buildreq(f"pypi({dep})")

    def add_setup_cfg_requires(self, filename, packages):
        """Detect install requirements listed in setup.cfg in the build-system's requires lists."""
        setup_f = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        setup_f.read(filename)
        if 'options' in setup_f.sections() and (install_reqs := setup_f['options'].get('install_requires')):
            for req in install_reqs.splitlines():
                if dep := clean_python_req(req):
                    req = f"pypi({dep})"
                    self.add_buildreq(req)
                    self.add_requires(req, packages, subpkg="python3")

    def add_setup_py_requires(self, filename, packages):
        """Detect build requirements listed in setup.py in the install_requires and setup_requires lists.

        Handles the following patterns:
        install_requires='one'
        install_requires=['one', 'two', 'three']
        install_requires=['one',
                          'two',
                          'three']
        setup_requires=[
            'one>=2.1',   # >=2.1 is removed
            'two',
            'three'
        ]
        setuptools.setup(
            setup_requires=['one', 'two'],
        ...)
        setuptools.setup(setup_requires=['one', 'two'], ...)

        Does not evaluate variables for security purposes
        """
        multiline = False
        with util.open_auto(filename) as f:
            lines = f.readlines()

        for line in lines:
            if not multiline and ("install_requires" in line or "setup_requires" in line):
                req = "install_requires" in line
                # find the value for *_requires
                line = line.split("=", 1)
                if len(line) == 2:
                    line = line[1].strip()
                else:
                    # skip because this could be a conditionally extended list
                    # we only want to automatically detect the core packages
                    continue

                # easy, one-line case
                if line.startswith("[") and "]" in line:
                    # remove the leading [ and split off everthing after the ]
                    line = line[1:].split("]")[0]
                    for item in line.split(','):
                        item = item.strip()
                        try:
                            # eval the string and add requirements
                            if dep := clean_python_req(ast.literal_eval(item)):
                                dep = f"pypi({dep})"
                                if self.add_buildreq(dep) and req:
                                    self.add_requires(dep, packages, subpkg="python3")

                        except Exception:
                            # do not fail, the line contained a variable and
                            # had to be skipped
                            pass

                    continue

                # more complicated, multi-line list.
                # this sets the py_dep_string with the current line, which
                # is the beginning of a multi-line list.
                elif line.startswith("["):
                    multiline = True
                    line = line.lstrip("[")

                # if the line doesn't start with '[' it is the case where
                # there is (should be) a single dependency as a string
                else:
                    line = line.strip()
                    try:
                        if dep := clean_python_req(ast.literal_eval(line)):
                            dep = f"pypi({dep})"
                            if self.add_buildreq(dep) and req:
                                self.add_requires(dep, packages, subpkg="python3")

                    except Exception:
                        # Do not fail, just keep looking
                        pass

                    continue

            # if multiline was set above when a multi-line list was
            # detected, for each line until the end bracket is found attempt to
            # add the line as a buildreq
            if multiline:
                # if end bracket found, reset the flag
                if "]" in line:
                    multiline = False
                    line = line.split("]")[0]

                try:
                    dep = ast.literal_eval(line.split('#')[0].strip(' ,\n'))
                    if dep := clean_python_req(dep):
                        dep = f"pypi({dep})"
                        if self.add_buildreq(dep) and req:
                            self.add_requires(dep, packages, subpkg="python3")

                except Exception:
                    # do not fail, the line contained a variable and had to
                    # be skipped
                    pass

    def get_data_from_pypi(self, name, config):
        """Use pypi for getting package requires and metadata."""
        # First look for a local override
        pypi_json = ""
        pypi_file = os.path.join(config.download_path, "pypi.json")
        if os.path.isfile(pypi_file):
            with open(pypi_file, "r") as pfile:
                pypi_json = pfile.read()
        else:
            # Try and grab the pypi details for the package
            if config.alias:
                name = config.alias
            pypi_name = pypidata.get_pypi_name(name)
            pypi_json = pypidata.get_pypi_metadata(pypi_name)
        if pypi_json:
            try:
                package_pypi = json.loads(pypi_json)
            except json.JSONDecodeError:
                package_pypi = {}
            if package_pypi.get("name"):
                self.pypi_provides = package_pypi["name"]
            if package_pypi.get("requires"):
                for pkg in package_pypi["requires"]:
                    self.add_requires(f"pypi({pkg})", config.os_packages, override=True, subpkg="python3")
            if package_pypi.get("license"):
                # The license field is freeform, might be worth looking at though
                print(f"Pypi says the license is: {package_pypi['license']}")
            if package_pypi.get("summary"):
                specdescription.assign_summary(package_pypi["summary"], 4)

    def setup_autoreconf(self, config, spath):
        """Configure for autoreconf (or not)."""
        can_reconf = os.path.exists(os.path.join(spath, "configure.ac"))
        if not can_reconf:
            can_reconf = os.path.exists(os.path.join(spath, "configure.in"))
        if can_reconf and config.autoreconf:
            print("Patches touch configure.*, adding autoreconf stage")
            for breq in self.autoreconf_reqs:
                self.add_buildreq(breq)
        else:
            config.autoreconf = False

    def scan_for_configure(self, dirn, tname, config):
        """Scan the package directory for build files to determine build pattern."""
        count = 0
        pyproject_path = ""
        requirements_path = ""
        setup_path = ""
        configure_ac_files = []
        qmake_profiles = []
        cmake_files = []

        if config.config_opts['use_ninja']:
            self.add_buildreq('ninja')

        for dirpath, _, files in os.walk(dirn):
            default_score = 2 if dirpath == dirn else 1

            if "Cargo.toml" in files and 'Makefile' not in files:
                config.set_build_pattern('cargo', default_score)

            if "CMakeLists.txt" in files and "configure.ac" not in files:
                config.set_build_pattern("cmake", default_score)

            if "configure" in files and os.access(dirpath + '/configure', os.X_OK):
                config.set_build_pattern("configure", default_score)
            elif any(is_qmake_pro(f) for f in files):
                config.set_build_pattern("qmake", default_score)

            if "pyproject.toml" in files and not pyproject_path:
                req_path = os.path.join(dirpath, "pyproject.toml")
                if "setup.cfg" in files:
                    s_path = os.path.join(dirpath, 'setup.cfg')
                    if not python_req_in_filtered_path(s_path):
                        setup_path = s_path
                if not python_req_in_filtered_path(req_path):
                    pyproject_path = req_path
                    config.set_build_pattern("pyproject", default_score)
            elif "setup.py" in files and not setup_path:
                s_path = os.path.join(dirpath, "setup.py")
                if not python_req_in_filtered_path(s_path):
                    setup_path = s_path
                    config.set_build_pattern("distutils3", default_score)

            if "requires.txt" in files and not pyproject_path:
                req_path = os.path.join(dirpath, "requires.txt")
                if not python_req_in_filtered_path(req_path):
                    requirements_path = req_path

            if "requirements.txt" in files and not requirements_path:
                req_path = os.path.join(dirpath, "requirements.txt")
                if not python_req_in_filtered_path(req_path):
                    requirements_path = req_path

            if "Makefile.PL" in files or "Build.PL" in files:
                config.set_build_pattern("cpan", default_score)

            if "SConstruct" in files:
                config.set_build_pattern("scons", default_score)

            if "meson.build" in files:
                config.set_build_pattern("meson", default_score)

            for name in files:
                if name.lower().startswith("configure."):
                    config.set_build_pattern("configure_ac", 1)
                    configure_ac_files.append(os.path.join(dirpath, name))
                if name.endswith(".pro") and config.default_pattern == "qmake":
                    qmake_profiles.append(os.path.join(dirpath, name))
                if name.lower() == "makefile":
                    config.set_build_pattern("make", default_score)
                if name.lower() == "autogen.sh":
                    config.set_build_pattern("autogen", default_score)
                if name.lower() == "cmakelists.txt":
                    config.set_build_pattern("cmake", default_score)
                if (name.lower() == "cmakelists.txt" or name.endswith(".cmake")) \
                   and config.default_pattern == "cmake":
                    cmake_files.append(os.path.join(dirpath, name))

        if config.default_pattern in ('distutils3', 'pyproject'):
            if pyproject_path:
                self.add_pyproject_requires(pyproject_path)
            if setup_path:
                self.add_setup_py_requires(setup_path, config.os_packages)
            if requirements_path:
                self.grab_python_requirements(requirements_path, config.os_packages)
            self.get_data_from_pypi(tname, config)
            self.add_buildreq("buildreq-distutils3")
        elif config.default_pattern == "cmake":
            self.add_buildreq("buildreq-cmake")
            for cfile in cmake_files:
                self.parse_cmake(cfile, config.cmake_modules, config.config_opts.get('32bit'))
        elif config.default_pattern == "configure":
            for cfile in configure_ac_files:
                self.parse_configure_ac(cfile, config)
            self.add_buildreq("buildreq-configure")
        elif config.default_pattern in ("autogen", "configure_ac"):
            for cfile in configure_ac_files:
                self.parse_configure_ac(cfile, config)
            self.setup_autoreconf(config, dirn)
        elif config.default_pattern == "qmake":
            self.add_buildreq("buildreq-qmake")
            for qfile in qmake_profiles:
                self.qmake_profile(qfile, config.qt_modules)
        elif config.default_pattern == "cpan":
            self.add_buildreq("buildreq-cpan")
        elif config.default_pattern == "cargo":
            self.add_buildreq("rustc")
        elif config.default_pattern == "scons":
            self.add_buildreq("buildreq-scons")
        elif config.default_pattern == "meson":
            self.add_buildreq("buildreq-meson")
        elif config.default_pattern == "R":
            self.add_buildreq("buildreq-R")
            self.parse_r_description(os.path.join(dirn, "DESCRIPTION"), config.os_packages)
        elif config.default_pattern == "phpize":
            self.add_buildreq("buildreq-php")
        elif config.default_pattern == "nginx":
            self.add_buildreq("buildreq-nginx")

        print("Buildreqs   : ", end="")
        for lic in sorted(self.buildreqs):
            if count > 4:
                count = 0
                print("\nBuildreqs   : ", end="")
            count = count + 1
            print(lic + " ", end="")
        print("")
