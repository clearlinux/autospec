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
import os
import re
import subprocess

import buildpattern
import config
import toml
import util

banned_requires = set(["futures"])
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
                        "libxml2No-python",
                        "futures"])
autoreconf_reqs = ["gettext-bin",
                   "automake-dev",
                   "automake",
                   "m4",
                   "libtool",
                   "libtool-dev",
                   "pkg-config-dev"]


def add_buildreq(req, cache=False):
    """Add req to the global buildreqs set if req is not banned."""
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
    """Add req to the global requires set if it is present in buildreqs and os_packages and is not banned."""
    global buildreqs
    global requires
    new = True
    req = req.strip()
    if req in requires:
        new = False
    if req in banned_requires:
        return False

    # Try dashes instead of underscores as some ecosystems are inconsistent in their naming
    req2 = req.replace("_", "-")
    if req not in buildreqs and req2 in config.os_packages and req2 not in requires and req2 not in banned_requires:
        # Since this is done for python add a buildreq just in case (might not be correct though)
        buildreqs.add(req2)
        requires.add(req2)
        return True

    # Try reversing the case of the first letter as some ecosystems are inconsistent in their naming
    if len(req) > 1:
        if req[0].isupper():
            req2 = req[0].lower() + req[1:]
        else:
            req2 = req[0].upper() + req[1:]
    if req not in buildreqs and req2 in config.os_packages and req2 not in requires and req2 not in banned_requires:
        # Since this is done for python add a buildreq just in case (might not be correct though)
        buildreqs.add(req2)
        requires.add(req2)
        return True

    if req not in buildreqs and req not in config.os_packages and not override:
        if req:
            print("requirement '{}' not found in buildreqs or os_packages, skipping".format(req))
        return False
    if new:
        # print("Adding requirement:", req)
        requires.add(req)
    return new


def add_pkgconfig_buildreq(preq, cache=False):
    """Format preq as pkgconfig req and add to buildreqs."""
    if config.config_opts['32bit']:
        req = "pkgconfig(32" + preq + ")"
        add_buildreq(req, cache)
    req = "pkgconfig(" + preq + ")"
    return add_buildreq(req, cache)


def configure_ac_line(line):
    """Parse configure_ac line and add appropriate buildreqs."""
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


def parse_go_mod(path):
    """Parse go.mod file for build requirements.

    File content looks as follows:

    module example.com/foo/bar

    require (
        github.com/BurntSushi/toml v0.3.1
        git.apache.org/thrift.git v0.0.0-20180902110319-2566ecd5d999
        github.com/inconshreveable/mousetrap v1.0.0 // indirect
        "github.com/spf13/cobra" v0.0.3
        github.com/spf13/pflag v1.0.3 // indirect
    )

    Need to handle all require lines including //indirect.
    Skip requires that use .git for now. May need to be handled
    differently.
    """
    reqs = []
    with open(path, "r") as gfile:
        dep_start = False
        for line in gfile.readlines():
            # Ideally the mod file is generated and the format is
            # always correct but add a few defenses just in case
            line = line.strip()
            if line.startswith("//"):
                # Skip comments
                continue
            if dep_start:
                # End of the require section
                if line.startswith(")"):
                    break
                req = line.split()[:2]
                req[0] = req[0].replace('"', '')
                if req[0].endswith(".git"):
                    continue
                reqs.append(req)
                continue
            if line.startswith("require ("):
                dep_start = True
    return reqs


def parse_modules_list(modules_string, is_cmake=False):
    """Parse the modules_string for the list of modules, stripping out the version requirements."""
    if is_cmake:
        modules = [m for m in re.split(r'\s*([><]?=|\${?[^}]*}?)\s*', modules_string)]
        modules = filter(None, modules)
    else:
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

        if is_version(mod):
            continue

        if mod.startswith('$'):
            continue

        if len(mod) >= 2:
            res.append(mod)

    return res


def parse_configure_ac(filename):
    """Parse the configure.ac file for build requirements."""
    buf = ""
    depth = 0
    # print("Configure parse: ", filename)
    buildpattern.set_build_pattern("configure_ac", 1)
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
            configure_ac_line(buf)
            buf = ""

    configure_ac_line(buf)
    f.close()


def parse_cargo_toml(filename):
    """Update build requirements using Cargo.toml.

    Set the build requirements for building rust programs using cargo.
    """
    global cargo_bin
    buildpattern.set_build_pattern("cargo", 1)
    add_buildreq("rustc")
    with util.open_auto(filename, "r") as ctoml:
        cargo = toml.loads(ctoml.read())
    if cargo.get("bin") or os.path.exists(os.path.join(os.path.dirname(filename), "src/main.rs")):
        cargo_bin = True
    if not cargo.get("dependencies"):
        return
    for cdep in cargo["dependencies"]:
        if add_buildreq(cdep):
            add_requires(cdep)


def _get_desc_field(field, desc):
    """Get a given field in an R DESCRIPTION file.

    Internal helper to read the value for the given field in an R package
    DESCRIPTION file. Returns a list representing the value; if value contained
    commas, the string is split on the commas and surrounding whitespace to
    create the list.
    """
    val = []
    # Values may span multiple lines...
    pat = re.compile(r"^" + field + r": *(.*?)(?=\n\w+:)", re.MULTILINE | re.DOTALL)
    match = pat.search(desc)
    if match:
        joined = match.group(1).replace("\n", " ")
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


def parse_r_description(filename):
    """Update build/runtime requirements according to the R package description."""
    deps = []
    with util.open_auto(filename, "r") as desc:
        content = desc.read()
        deps = _get_desc_field("Depends", content)
        deps.extend(_get_desc_field("Imports", content))
    r_provides = _get_r_provides()
    for dep in deps:
        if dep == 'R':
            continue
        if dep in r_provides:
            continue
        pkg = 'R-' + dep
        if pkg in config.os_packages:
            add_buildreq(pkg)
            add_requires(pkg)
        else:
            print("CRAN package '{}' not found in os_packages, skipping".format(pkg))


def set_build_req():
    """Add build requirements based on the buildpattern pattern."""
    if buildpattern.default_pattern == "maven":
        maven_reqs = ["apache-maven",
                      "openjdk-dev",
                      "mvn-aether-core",
                      "mvn-aopalliance",
                      "mvn-cdi-api",
                      "mvn-commons-cli",
                      "mvn-commons-codec",
                      "mvn-commons-io",
                      "mvn-commons-lang",
                      "mvn-commons-lang3",
                      "mvn-commons-logging",
                      "mvn-guice",
                      "mvn-guava",
                      "mvn-httpcomponents-client",
                      "mvn-httpcomponents-core",
                      "mvn-jsoup",
                      "mvn-jsr305",
                      "mvn-wagon",
                      "mvn-sisu",
                      "mvn-plexus-cipher",
                      "mvn-plexus-classworlds",
                      "mvn-plexus-containers",
                      "mvn-plexus-interpolation",
                      "mvn-sonatype-plexus-sec-dispatcher",
                      "mvn-plexus-utils",
                      "mvn-slf4j"]
        for req in maven_reqs:
            add_buildreq(req)

    if buildpattern.default_pattern == "ruby":
        add_buildreq("ruby")
        add_buildreq("rubygem-rdoc")
    if buildpattern.default_pattern == "cargo":
        add_buildreq("rustc")


def rakefile(filename):
    """Scan Rakefile for build requirements."""
    with util.open_auto(filename, "r") as f:
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


def parse_cmake(filename):
    """Scan a .cmake or CMakeLists.txt file for what's it's actually looking for."""
    findpackage = re.compile(r"^[^#]*find_package\((\w+)\b.*\)", re.I)
    pkgconfig = re.compile(r"^[^#]*pkg_check_modules\s*\(\w+ (.*)\)", re.I)
    pkg_search_modifiers = {'REQUIRED', 'QUIET', 'NO_CMAKE_PATH',
                            'NO_CMAKE_ENVIRONMENT_PATH', 'IMPORTED_TARGET'}
    extractword = re.compile(r'(?:"([^"]+)"|(\S+))(.*)')

    with util.open_auto(filename, "r") as f:
        lines = f.readlines()
    for line in lines:
        match = findpackage.search(line)
        if match:
            module = match.group(1)
            try:
                pkg = config.cmake_modules[module]
                add_buildreq(pkg)
            except Exception:
                pass

        match = pkgconfig.search(line)
        if match:
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
                    add_pkgconfig_buildreq(m)


def qmake_profile(filename):
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
                pc = config.qt_modules[module]
                add_buildreq('pkgconfig({})'.format(pc))
            except Exception:
                pass


def clean_python_req(req, add_python=True):
    """Strip version information from req."""
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
    """Add python requirements from requirements.txt file."""
    if "/demo/" in descfile:
        return
    if "/doc/" in descfile:
        return
    if "/docs/" in descfile:
        return
    if "/example/" in descfile:
        return
    if "/test/" in descfile:
        return
    if "/tests/" in descfile:
        return

    with util.open_auto(descfile, "r") as f:
        lines = f.readlines()

    for line in lines:
        # don't add the test section
        if clean_python_req(line) == '[test]':
            break
        if clean_python_req(line) == '[testing]':
            break
        if clean_python_req(line) == '[dev]':
            break
        if clean_python_req(line) == '[doc]':
            break
        if clean_python_req(line) == '[docs]':
            break
        if 'pytest' in line:
            continue
        if clean_python_req(line) == 'mock':
            continue
        add_requires(clean_python_req(line))


def grab_pip_requirements(pkgname):
    """Determine python requirements for pkgname using pip show."""
    try:
        pipeout = subprocess.check_output(['/usr/bin/pip3', 'show', pkgname])
    except Exception:
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
    """Detect if setup should use distutils2 or distutils3 only.

    Uses "Programming Language :: Python :: [2,3] :: Only" classifiers in the
    setup.py file.  Defaults to distutils3 if no such classifiers are found.
    """
    with util.open_auto(filename) as setup_file:
        data = setup_file.read()

    if "Programming Language :: Python :: 3 :: Only" in data:
        return "distutils3"

    elif "Programming Language :: Python :: 2 :: Only" in data:
        return "distutils2"

    return "distutils3"


def add_setup_py_requires(filename):
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
                    dep = clean_python_req(ast.literal_eval(line), False)
                    add_buildreq(dep)
                    if req:
                        add_requires(dep)

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
                dep = clean_python_req(dep)
                add_buildreq(dep)
                if req:
                    add_requires(dep)

            except Exception:
                # do not fail, the line contained a variable and had to
                # be skipped
                pass


def parse_catkin_deps(cmakelists_file):
    """Determine requirements for catkin packages."""
    f = util.open_auto(cmakelists_file, "r")
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


def is_qmake_pro(f):
    """Test if file extension is pro and not hidden."""
    return f.endswith(".pro") and not f.startswith(".")


def scan_for_configure(dirn):
    """Scan the package directory for build files to determine build pattern."""
    if buildpattern.default_pattern == "distutils":
        add_buildreq("buildreq-distutils")
    elif buildpattern.default_pattern == "distutils36":
        add_buildreq("buildreq-distutils36")
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
        parse_r_description(os.path.join(dirn, "DESCRIPTION"))
    elif buildpattern.default_pattern == "phpize":
        add_buildreq("buildreq-php")

    count = 0
    for dirpath, _, files in os.walk(dirn):
        default_score = 2 if dirpath == dirn else 1

        if any(f.endswith(".go") for f in files):
            add_buildreq("buildreq-golang")
            buildpattern.set_build_pattern("golang", default_score)

        if "go.mod" in files and dirpath == dirn:
            if "Makefile" not in files:
                # Go packages usually have make build systems so far
                # so only use go directly if we can't find a Makefile
                buildpattern.set_build_pattern("golang", default_score)
            add_buildreq("buildreq-golang")
            config.set_gopath = False
            mod_path = os.path.join(dirpath, "go.mod")
            reqs = parse_go_mod(mod_path)
            for req in reqs:
                # req[0] is a SCM url segment in the form, repo/XXX/dependency-name
                # req[1] is the version of the dependency
                pkg = "go-" + req[0].replace("/", "-")
                add_buildreq(pkg)
                if buildpattern.default_pattern == "godep":
                    add_requires(pkg)

        if "CMakeLists.txt" in files and "configure.ac" not in files:
            add_buildreq("buildreq-cmake")
            buildpattern.set_build_pattern("cmake", default_score)

            srcdir = os.path.abspath(os.path.join(dirn, "clr-build", config.cmake_srcdir or ".."))
            if os.path.samefile(dirpath, srcdir):
                parse_catkin_deps(os.path.join(srcdir, "CMakeLists.txt"))

        if "configure" in files and os.access(dirpath + '/configure', os.X_OK):
            buildpattern.set_build_pattern("configure", default_score)
        elif any(is_qmake_pro(f) for f in files):
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

        if "config.m4" in files:
            add_buildreq("buildreq-php")
            buildpattern.set_build_pattern("phpize", 1)

        if "build.xml" in files:
            add_buildreq("apache-ant")
            add_buildreq("buildreq-mvn")
            buildpattern.set_build_pattern("ant", default_score)

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
            if (name.lower() == "cmakelists.txt" or name.endswith(".cmake")) \
               and buildpattern.default_pattern == "cmake":
                parse_cmake(os.path.join(dirpath, name))

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
    """Load specfile object with necessary buildreq data."""
    specfile.buildreqs = buildreqs
    specfile.requires = requires
    specfile.cargo_bin = cargo_bin
    specfile.extra_cmake += " " + " ".join(extra_cmake)
