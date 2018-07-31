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

import os
import re
import ast

import toml

import buildpattern
import util
import config
import subprocess

banned_requires = set()
buildreqs = set()
buildreqs_cache = set()
requires = set()
extra_cmake = set()
verbose = False
cargo_bin = False
banned_buildreqs = set(["llvm-devel",
                        "gcj",
                        "pkgconfig(dnl)",
                        "pkgconfig(hal)",
                        "tslib-0.0",
                        "pkgconfig(parallels-sdk)",
                        "oslo-python",
                        "libxml2No-python"])
autoreconf_reqs = ["gettext-bin",
                   "automake-dev",
                   "automake",
                   "m4",
                   "libtool",
                   "libtool-dev",
                   "pkg-config-dev"]


def add_buildreq(req, cache=False):
    """
    Add req to the global buildreqs set if req is not banned
    """
    global buildreqs
    global buildreqs_cache
    new = True

    req.strip()

    if req in banned_buildreqs:
        return False
    if req in buildreqs:
        new = False
    if verbose and new:
        print("  Adding buildreq:", req)

    buildreqs.add(req)
    if cache and new:
        buildreqs_cache.add(req)
    return new


def add_requires(req, override=False):
    """
    Add req to the global requires set if it is present in buildreqs and
    os_packages and is not banned.
    """
    global requires
    new = True
    req = req.strip()
    if req in requires:
        new = False
    if req in banned_requires:
        return False
    if req not in buildreqs and req not in config.os_packages and not override:
        if req:
            print("requirement '{}' not found is buildreqs or os_packages, skipping".format(req))
        return False
    if new:
        # print("Adding requirement:", req)
        requires.add(req)
    return new


def add_pkgconfig_buildreq(preq, cache=False):
    """
    Format preq as pkgconfig req and add to buildreqs
    """
    if config.config_opts['32bit']:
        req = "pkgconfig(32" + preq + ")"
        add_buildreq(req, cache)
    req = "pkgconfig(" + preq + ")"
    return add_buildreq(req, cache)


def configure_ac_line(line):
    """
    Parse configure_ac line and add appropriate buildreqs
    """
    # print("----\n", line, "\n----")
    # ignore comments
    if line.startswith('#'):
        return

    pat_reqs = [(r"AC_CHECK_FUNC\([tgetent]", ["ncurses-devel"]),
                ("PROG_INTLTOOL", ["intltool"]),
                ("GETTEXT_PACKAGE", ["gettext", "perl(XML::Parser)"]),
                ("AM_GLIB_GNU_GETTEXT", ["gettext", "perl(XML::Parser)"]),
                ("GTK_DOC_CHECK", ["gtk-doc", "gtk-doc-dev", "libxslt-bin", "docbook-xml"]),
                ("AC_PROG_SED", ["sed"]),
                ("AC_PROG_GREP", ["grep"])]

    for pat, reqs in pat_reqs:
        if pat in line:
            for req in reqs:
                add_buildreq(req)

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
                add_pkgconfig_buildreq(req)

    # PKG_CHECK_EXISTS(MODULES, action-if-found, action-if-not-found)
    match = re.search(r"PKG_CHECK_EXISTS\((.*?)\)", line)
    if match:
        L = match.group(1).split(",")
        rqlist = L[0].strip()
        for req in parse_modules_list(rqlist):
            add_pkgconfig_buildreq(req)


def is_number(num_str):
    """
    Return True if num_str can be represented as a number
    """
    try:
        float(num_str)
        return True
    except ValueError:
        return False


def parse_modules_list(modules_string):
    """
    parse the modules_string for the list of modules, stripping out the version
    requirements
    """
    modules = [m.strip('[]') for m in modules_string.split()]
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

        if mod.startswith('$'):
            continue

        if len(mod) >= 2:
            res.append(mod)

    return res


def parse_configure_ac(filename):
    """
    Parse the configure.ac file for build requirements
    """
    buf = ""
    depth = 0
    # print("Configure parse: ", filename)
    buildpattern.set_build_pattern("configure_ac", 1)
    f = open(filename, "r", encoding="latin-1")
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
            configure_ac_line(buf)
            buf = ""

    configure_ac_line(buf)
    f.close()


def parse_cargo_toml(filename):
    """Update build requirements using Cargo.toml

    Set the build requirements for building rust programs using cargo.
    """
    global cargo_bin
    buildpattern.set_build_pattern("cargo", 1)
    add_buildreq("cargo")
    add_buildreq("rustc")
    with open(filename, "r", encoding="latin-1") as ctoml:
        cargo = toml.loads(ctoml.read())
    if cargo.get("bin") or os.path.exists(os.path.join(os.path.dirname(filename), "src/main.rs")):
        cargo_bin = True
    if not cargo.get("dependencies"):
        return
    for cdep in cargo["dependencies"]:
        if add_buildreq(cdep):
            add_requires(cdep)


def set_build_req():
    """
    Add build requirements based on the buildpattern pattern
    """
    if buildpattern.default_pattern == "maven":
        maven_reqs = ["apache-maven",
                      "xmvn",
                      "openjdk-dev",
                      "javapackages-tools",
                      "python3",
                      "six",
                      "lxml",
                      "jdk-plexus-classworlds",
                      "jdk-aether",
                      "jdk-aopalliance",
                      "jdk-atinject",
                      "jdk-cdi-api",
                      "jdk-commons-cli",
                      "jdk-commons-codec",
                      "jdk-commons-io",
                      "jdk-commons-lang",
                      "jdk-commons-lang3",
                      "jdk-commons-logging",
                      "jdk-guice",
                      "jdk-guava",
                      "jdk-httpcomponents-client",
                      "jdk-httpcomponents-core",
                      "jdk-jsoup",
                      "jdk-jsr-305",
                      "jdk-wagon",
                      "jdk-objectweb-asm",
                      "jdk-sisu",
                      "jdk-plexus-containers",
                      "jdk-plexus-interpolation",
                      "jdk-plexus-cipher",
                      "jdk-plexus-sec-dispatcher",
                      "jdk-plexus-utils",
                      "jdk-slf4j"]
        for req in maven_reqs:
            add_buildreq(req)

    if buildpattern.default_pattern == "ruby":
        add_buildreq("ruby")
        add_buildreq("rubygem-rdoc")
    if buildpattern.default_pattern == "cargo":
        add_buildreq("rustc")


def rakefile(filename):
    """
    Scan Rakefile for build requirements
    """
    with open(filename, "r", encoding="latin-1") as f:
        lines = f.readlines()

    pat = re.compile(r"^require '(.*)'$")
    for line in lines:
        match = pat.search(line)
        if match:
            s = match.group(1)
            if s != "rubygems" and s in config.gems:
                print("Rakefile-dep: " + config.gems[s])
                add_buildreq(config.gems[s])
            else:
                print("Rakefile-new: rubygem-" + s)


def qmake_profile(filename):
    """
    Scan .pro file for build requirements
    """
    with open(filename, "r", encoding="latin-1") as f:
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
                pc = config.qt_modules[module]
                add_buildreq('pkgconfig({})'.format(pc))
            except:
                pass


def clean_python_req(req, add_python=True):
    """
    Strip version information from req
    """
    if req.find("#") == 0:
        return ""
    ret = req.rstrip("\n\r").strip()
    i = ret.find(";")
    if i > 0:
        ret = ret[:i]
    i = ret.find("<")
    if i > 0:
        ret = ret[:i]
    i = ret.find("\n")
    if i > 0:
        ret = ret[:i]
    i = ret.find(">")
    if i > 0:
        ret = ret[:i]
    i = ret.find("=")
    if i > 0:
        ret = ret[:i]
    i = ret.find("#")
    if i > 0:
        ret = ret[:i]
    i = ret.find("!")
    if i > 0:
        ret = ret[:i]

    ret = ret.strip()
    # is ret actually a valid (non-empty) string?
    if ret and add_python:
        ret = ret.strip()
    # use the dictionary to translate funky names to our current pgk names
    ret = util.translate(ret)
    return ret


def grab_python_requirements(descfile):
    """
    Add python requirements from requirements.txt file
    """
    with open(descfile, "r", encoding="latin-1") as f:
        lines = f.readlines()

    for line in lines:
        add_requires(clean_python_req(line))


def grab_pip_requirements(pkgname):
    """
    Determine python requirements for pkgname using pip show
    """
    try:
        pipeout = subprocess.check_output(['/usr/bin/pip3', 'show', pkgname])
    except:
        return
    lines = pipeout.decode("utf-8").split('\n')
    for line in lines:
        words = line.split(" ")
        if words[0] == "Requires:":
            for w in words[1:]:
                w2 = w.replace(",", "")
                if len(w2) > 2:
                    print("Suggesting python requirement ", w2)
                    add_requires(w2)


def get_python_build_version_from_classifier(filename):
    """
    Detect if setup should use distutils2 or distutils3 only.

    Uses "Programming Language :: Python :: [2,3] :: Only" classifiers in the
    setup.py file.  Defaults to distutils3 if no such classifiers are found.
    """

    with open(filename) as setup_file:
        data = setup_file.read()

    if "Programming Language :: Python :: 3 :: Only" in data:
        return "distutils3"

    elif "Programming Language :: Python :: 2 :: Only" in data:
        return "distutils2"

    return "distutils3"


def add_setup_py_requires(filename):
    """
    Detect build requirements listed in setup.py in the install_requires and
    setup_requires lists.

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
    with open(filename) as f:
        lines = f.readlines()

    for line in lines:
        if "install_requires" in line or "setup_requires" in line:
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
                        dep = clean_python_req(ast.literal_eval(item), False)
                        add_buildreq(dep)
                        if req:
                            add_requires(dep)

                    except:
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
                    dep = clean_python_req(ast.literal_eval(line), False)
                    add_buildreq(dep)
                    if req:
                        add_requires(dep)

                except:
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
                dep = clean_python_req(dep)
                add_buildreq(dep)
                if req:
                    add_requires(dep)

            except:
                # do not fail, the line contained a variable and had to
                # be skipped
                pass


def parse_catkin_deps(cmakelists_file):
    f = open(cmakelists_file, "r", encoding="latin-1")
    lines = f.readlines()
    pat = re.compile(r"^find_package.*\(.*(catkin)(?: REQUIRED *)?(?:COMPONENTS (?P<comp>.*))?\)$")
    catkin = False

    for line in lines:
        match = pat.search(line)

        if not match:
            continue

        # include catkin's required components
        comp = match.group("comp")
        if comp:
            for curr in comp.split(" "):
                add_pkgconfig_buildreq(curr)

        catkin = True

    # catkin find_package() function will always rely on CMAKE_PREFIX_PATH
    # make sure we keep it consistent with CMAKE_INSTALL_PREFIX otherwise
    # it'll never be able to find its modules
    if catkin:
        for curr in ["catkin", "catkin_pkg", "empy", "googletest"]:
            add_buildreq(curr)

        extra_cmake.add("-DCMAKE_PREFIX_PATH=/usr")
        extra_cmake.add("-DCATKIN_BUILD_BINARY_PACKAGE=ON")
        extra_cmake.add("-DSETUPTOOLS_DEB_LAYOUT=OFF")


def scan_for_configure(dirn):
    """
    Scan the package directory for build files to determine build pattern
    """
    if buildpattern.default_pattern == "distutils":
        add_buildreq("buildreq-distutils")
    elif buildpattern.default_pattern == "distutils23":
        add_buildreq("buildreq-distutils23")
    elif buildpattern.default_pattern == "distutils3":
        add_buildreq("buildreq-distutils3")
    elif buildpattern.default_pattern == "golang":
        add_buildreq("buildreq-golang")
    elif buildpattern.default_pattern == "cmake":
        add_buildreq("buildreq-cmake")
    elif buildpattern.default_pattern == "configure":
        add_buildreq("buildreq-configure")
    elif buildpattern.default_pattern == "qmake":
        add_buildreq("buildreq-qmake")
    elif buildpattern.default_pattern == "cpan":
        add_buildreq("buildreq-cpan")
    elif buildpattern.default_pattern == "scons":
        add_buildreq("buildreq-scons")
    elif buildpattern.default_pattern == "R":
        add_buildreq("buildreq-R")

    count = 0
    for dirpath, _, files in os.walk(dirn):
        default_score = 2 if dirpath == dirn else 1

        if any(f.endswith(".go") for f in files):
            add_buildreq("buildreq-golang")
            buildpattern.set_build_pattern("golang", default_score)

        if "CMakeLists.txt" in files and "configure.ac" not in files:
            add_buildreq("buildreq-cmake")
            buildpattern.set_build_pattern("cmake", default_score)

            srcdir = os.path.abspath(os.path.join(dirn, "clr-build", config.cmake_srcdir or ".."))
            if os.path.samefile(dirpath, srcdir):
                parse_catkin_deps(os.path.join(srcdir, "CMakeLists.txt"))

        if "configure" in files and os.access(dirpath + '/configure', os.X_OK):
            buildpattern.set_build_pattern("configure", default_score)
        elif any(f.endswith(".pro") for f in files):
            add_buildreq("buildreq-qmake")
            buildpattern.set_build_pattern("qmake", default_score)

        if "requires.txt" in files:
            grab_python_requirements(dirpath + '/requires.txt')

        if "setup.py" in files:
            add_buildreq("buildreq-distutils3")
            add_setup_py_requires(dirpath + '/setup.py')
            python_pattern = get_python_build_version_from_classifier(dirpath + '/setup.py')
            buildpattern.set_build_pattern(python_pattern, default_score)

        if "Makefile.PL" in files or "Build.PL" in files:
            buildpattern.set_build_pattern("cpan", default_score)
            add_buildreq("buildreq-cpan")

        if "SConstruct" in files:
            add_buildreq("buildreq-scons")
            buildpattern.set_build_pattern("scons", default_score)

        if "requirements.txt" in files:
            grab_python_requirements(dirpath + '/requirements.txt')

        if "meson.build" in files:
            add_buildreq("buildreq-meson")
            buildpattern.set_build_pattern("meson", default_score)

        for name in files:
            if name.lower() == "cargo.toml" and dirpath == dirn:
                parse_cargo_toml(os.path.join(dirpath, name))
            if name.lower().startswith("configure."):
                parse_configure_ac(os.path.join(dirpath, name))
            if name.lower().startswith("rakefile") and buildpattern.default_pattern == "ruby":
                rakefile(os.path.join(dirpath, name))
            if name.endswith(".pro") and buildpattern.default_pattern == "qmake":
                qmake_profile(os.path.join(dirpath, name))
            if name.lower() == "makefile":
                buildpattern.set_build_pattern("make", default_score)
            if name.lower() == "autogen.sh":
                buildpattern.set_build_pattern("autogen", default_score)
            if name.lower() == "cmakelists.txt":
                buildpattern.set_build_pattern("cmake", default_score)

    can_reconf = os.path.exists(os.path.join(dirn, "configure.ac"))
    if not can_reconf:
        can_reconf = os.path.exists(os.path.join(dirn, "configure.in"))

    if can_reconf and config.autoreconf:
        print("Patches touch configure.*, adding autoreconf stage")
        for breq in autoreconf_reqs:
            add_buildreq(breq)
    else:
        config.autoreconf = False

    print("Buildreqs   : ", end="")
    for lic in sorted(buildreqs):
        if count > 4:
            count = 0
            print("\nBuildreqs   : ", end="")
        count = count + 1
        print(lic + " ", end="")
    print("")


def load_specfile(specfile):
    """
    Load specfile object with necessary buildreq data
    """
    specfile.buildreqs = buildreqs
    specfile.requires = requires
    specfile.cargo_bin = cargo_bin
    specfile.extra_cmake += " " + " ".join(extra_cmake)
