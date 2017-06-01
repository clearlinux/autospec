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
import tarball
import config
import subprocess

banned_requires = set()
buildreqs = set()
requires = set()
banned_buildreqs = set(
    ["llvm-devel", "gcj", "pkgconfig(dnl)", "pkgconfig(hal)", "tslib-0.0", "pkgconfig(parallels-sdk)", "oslo-python", "libxml2No-python"])
verbose = False
cargo_bin = False

autoreconf_reqs = ["gettext-bin", "automake-dev", "automake", "m4", "libtool", "libtool-dev", "pkg-config-dev"]


def add_buildreq(req):
    global buildreqs
    new = True

    req.strip()

    if req in banned_buildreqs:
        return False
    if req in buildreqs:
        new = False
    if verbose and new:
        print("  Adding buildreq:", req)

    buildreqs.add(req)
    return new


def add_requires(req):
    global requires
    new = True

    req.strip()

    if req in requires:
        new = False
    if req in banned_requires:
        return False
    if req not in buildreqs and req not in config.os_packages:
        if len(req) > 0:
            print("requirement '{}' not found is buildreqs or os_packages, skipping".format(req))
        return False
    if new:
        # print("Adding requirement:", req)
        requires.add(req)
    return new


def add_pkgconfig_buildreq(preq):
    if config.config_opts['32bit']:
        req = "pkgconfig(32" + preq + ")"
        add_buildreq(req)
    req = "pkgconfig(" + preq + ")"
    return add_buildreq(req)


def configure_ac_line(line):
    # print("----\n", line, "\n----")
    # ignore comments
    if line.startswith('#'):
        return

    if line.find("AC_CHECK_FUNC\([tgetent]") >= 0:
        add_buildreq("ncurses-devel")
    if line.find("PROG_INTLTOOL") >= 0:
        add_buildreq("intltool")
    if line.find("GETTEXT_PACKAGE") >= 0:
        add_buildreq("gettext")
        add_buildreq("perl(XML::Parser)")
    if line.find("AM_GLIB_GNU_GETTEXT") >= 0:
        add_buildreq("gettext")
        add_buildreq("perl(XML::Parser)")
    if line.find("GTK_DOC_CHECK") >= 0:
        add_buildreq("gtk-doc")
        add_buildreq("gtk-doc-dev")
        add_buildreq("libxslt-bin")
        add_buildreq("docbook-xml")
    if line.find("AC_PROG_SED") >= 0:
        add_buildreq("sed")
    if line.find("AC_PROG_GREP") >= 0:
        add_buildreq("grep")

    line = line.strip()

    # print("--", line, "--")
    # XFCE uses an equivalent to PKG_CHECK_MODULES, handle them both the same
    for style in [r"PKG_CHECK_MODULES\((.*?)\)", r"XDT_CHECK_PACKAGE\((.*?)\)"]:
        pattern = re.compile(style)
        match = pattern.search(line)
        L = []
        if match:
            L = match.group(1).split(",")
        if len(L) > 1:
            rqlist = L[1].strip()
            f = rqlist.find(">")
            if f >= 0:
                rqlist = rqlist[:f]
            f = rqlist.find("<")
            if f >= 0:
                rqlist = rqlist[:f]

            L2 = rqlist.split(" ")
            for rq in L2:
                if len(rq) < 2:
                    continue
                # remove [] if any
                if rq[0] == "[":
                    rq = rq[1:]
                f = rq.find("]")
                if f >= 0:
                    rq = rq[:f]
                f = rq.find(">")
                if f >= 0:
                    rq = rq[:f]
                f = rq.find("<")
                if f >= 0:
                    rq = rq[:f]
                f = rq.find("=")
                if f >= 0:
                    rq = rq[:f]
                rq = rq.strip()
                if len(rq) > 0 and rq[0] != "$":
                    add_pkgconfig_buildreq(rq)

    pattern = re.compile(r"PKG_CHECK_EXISTS\((.*?)\)")
    match = pattern.search(line)
    if match:
        L = match.group(1).split(",")
        # print("---", match.group(1).strip(), "---")
        rqlist = L[0].strip()
        L2 = rqlist.split(" ")
        for rq in L2:
            # remove [] if any
            if rq[0] == "[":
                rq = rq[1:]
            f = rq.find("]")
            if f >= 0:
                rq = rq[:f]
            f = rq.find(">")
            if f >= 0:
                rq = rq[:f]
            f = rq.find("<")
            if f >= 0:
                rq = rq[:f]
            f = rq.find("=")
            if f >= 0:
                rq = rq[:f]
            rq = rq.strip()
            # print("=== ", rq, "===")
            if len(rq) > 0 and rq[0] != "$":
                add_pkgconfig_buildreq(rq)
                break

    pass


def parse_configure_ac(filename):
    buffer = ""
    depth = 0
    # print("Configure parse: ", filename)
    buildpattern.set_build_pattern("configure_ac", 1)
    file = open(filename, "r", encoding="latin-1")
    while 1:
        c = file.read(1)
        if len(c) == 0:
            break
        if c == "(":
            depth = depth + 1
        if c == ")" and depth > 0:
            depth = depth - 1
        if c != "\n":
            buffer = buffer + c
        if c == "\n" and depth == 0:
            configure_ac_line(buffer)
            buffer = ""

    configure_ac_line(buffer)
    file.close()


def parse_cargo_toml(filename):
    """Update build requirements using Cargo.toml

    Set the build requirements for building rust programs using cargo.
    """
    global cargo_bin
    buildpattern.set_build_pattern("cargo", 1)
    add_buildreq("rustc")
    with open(filename, "r", encoding="latin-1") as ctoml:
        cargo = toml.loads(ctoml.read())
    if cargo.get("bin") or os.path.exists(os.path.join(os.path.dirname(filename), "src/main.rs")):
        cargo_bin = True
    if not cargo.get("dependencies"):
        return
    for bdep in cargo["dependencies"]:
        add_buildreq(bdep)


def set_build_req():
    if buildpattern.default_pattern == "maven":
        add_buildreq("apache-maven")
        add_buildreq("xmvn")
        add_buildreq("openjdk-dev")
        add_buildreq("javapackages-tools")
        add_buildreq("python3")
        add_buildreq("six")
        add_buildreq("lxml")
        add_buildreq("jdk-plexus-classworlds")
        add_buildreq("jdk-aether")
        add_buildreq("jdk-aopalliance")
        add_buildreq("jdk-atinject")
        add_buildreq("jdk-cdi-api")
        add_buildreq("jdk-commons-cli")
        add_buildreq("jdk-commons-codec")
        add_buildreq("jdk-commons-io")
        add_buildreq("jdk-commons-lang")
        add_buildreq("jdk-commons-lang3")
        add_buildreq("jdk-commons-logging")
        add_buildreq("jdk-guice")
        add_buildreq("jdk-guava")
        add_buildreq("jdk-httpcomponents-client")
        add_buildreq("jdk-httpcomponents-core")
        add_buildreq("jdk-jsoup")
        add_buildreq("jdk-jsr-305")
        add_buildreq("jdk-wagon")
        add_buildreq("jdk-objectweb-asm")
        add_buildreq("jdk-sisu")
        add_buildreq("jdk-plexus-containers")
        add_buildreq("jdk-plexus-interpolation")
        add_buildreq("jdk-plexus-cipher")
        add_buildreq("jdk-plexus-sec-dispatcher")
        add_buildreq("jdk-plexus-utils")
        add_buildreq("jdk-slf4j")
    if buildpattern.default_pattern == "ruby":
        add_buildreq("ruby")
        add_buildreq("rubygem-rdoc")
    if buildpattern.default_pattern == "cargo":
        add_buildreq("rustc")


def Rakefile(filename):
    file = open(filename, "r", encoding="latin-1")
    lines = file.readlines()
    for line in lines:
        pat = re.compile(r"^require '(.*)'$")
        match = pat.search(line)
        if match:
            s = match.group(1)
            if s != "rubygems" and s in config.gems:
                print("Rakefile-dep: " + config.gems[s])
                add_buildreq(config.gems[s])
            else:
                print("Rakefile-new: rubygem-" + s)


def clean_python_req(str, add_python=True):
    if str.find("#") == 0:
        return ""
    ret = str.rstrip("\n\r").strip()
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
    file = open(descfile, "r", encoding="latin-1")
    for line in file.readlines():
        add_requires(clean_python_req(line))


def grab_pip_requirements(pkgname):
    try:
        pipeout = subprocess.check_output(['/usr/bin/pip3', 'show', pkgname])
    except:
        return
    lines = pipeout.decode("utf-8").split('\n')
    for line in lines:
        words = line.split(" ")
        if words[0] == "Requires:":
            for w in words[1:]:
                w2 = w.replace(",","")
                if len(w2) > 2:
                    print("Suggesting python requirement ", w2)
                    add_requires(w2)


def setup_py_python3(filename):
    try:
        with open(filename) as FILE:
            if ":: Python :: 3" in "".join(FILE.readlines()):
                return 1
    except:
        return 0
    return 0


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

    Does not evaluate lists of variables.
    """
    py_dep_string = None
    try:
        with open(filename) as FILE:
            for line in FILE.readlines():
                if "install_requires" in line or "setup_requires" in line:
                    req = False
                    if "install_requires" in line:
                        req = True
                    # find the value for *_requires
                    line = line.split("=", 1)[1].strip()
                    # check for end bracket on this line
                    end_bracket = line.find("]")
                    # easy, one-line case
                    if line.startswith("[") and end_bracket > 0:
                        line = line[:end_bracket + 1]
                        # eval the string and add requirements
                        for dep in ast.literal_eval(line):
                            print(dep)
                            dep = clean_python_req(dep, False)
                            add_buildreq(dep)
                            if req:
                                add_requires(dep)
                        continue
                    # more complicated, multi-line list.
                    # this sets the py_dep_string with the current line, which
                    # is the beginning of a multi-line list. py_dep_string
                    # acts as a flag to the below conditional
                    # `if py_dep_string`.
                    elif line.startswith("["):
                        py_dep_string = line
                    # if the line doesn't start with '[' it is the case where
                    # there is a single dependency as a string
                    else:
                        start_quote = line[0]
                        # end_quote remains -1 if start_quote is not a quote or
                        # there is no end quote on this line
                        end_quote = -1
                        if start_quote is "'":
                            end_quote = line[1:].find("'")
                            # account for first character
                            end_quote += 1
                        elif start_quote is '"':
                            end_quote = line[1:].find('"')
                            # account for first character
                            end_quote += 1

                        # at this point, end_quote is only > 0 if there was a
                        # matching start quote
                        if end_quote > 0:
                            line = line[:end_quote + 1]
                            for dep in ast.literal_eval(line):
                                print(dep)
                                dep = clean_python_req(dep, False)
                                add_buildreq(py_deps)
                                if req:
                                    add_requires(py_deps)
                            continue

                # if py_dep_string was set above when a multi-line list was
                # detected, add the stripped line to the string.
                # when the end of the list is detected (line ends with ']'),
                # the string-list is literal_evaled into a list of strings.
                if py_dep_string:
                    # py_dep_string is a copy of the line when it is set,
                    # only append line when line has been incremented
                    if py_dep_string is not line:
                        py_dep_string += line.strip(" \n")
                    # look for the end of the list
                    end_bracket = py_dep_string.find("]")
                    if end_bracket > 0:
                        # eval the string and add requirements
                        for dep in ast.literal_eval(py_dep_string[:end_bracket + 1]):
                            dep = clean_python_req(dep, False)
                            add_buildreq(dep)
                            if req:
                                add_requires(dep)
                        continue

    except:
        # this except clause will be invoked in the case the install_requires
        # list contains variables instead of strings as well as the normal
        # error case
        pass


def scan_for_configure(package, dir, autospecdir):
    global default_summary
    count = 0
    for dirpath, dirnames, files in os.walk(dir):
        default_score = 2
        if dirpath != dir:
            default_score = 1

        if any(file.endswith(".go") for file in files):
            add_buildreq("go")
            buildpattern.set_build_pattern("golang", default_score)

        if "CMakeLists.txt" in files and "configure.ac" not in files:
            add_buildreq("cmake")
            buildpattern.set_build_pattern("cmake", default_score)

        if "configure" in files and os.access(dirpath + '/configure', os.X_OK):
            buildpattern.set_build_pattern("configure", default_score)

        if "requires.txt" in files:
                grab_python_requirements(dirpath + '/requires.txt')

        if "setup.py" in files:
            add_buildreq("python-dev")
            add_buildreq("python3-dev")
            add_buildreq("setuptools")
            add_buildreq("pbr")
            add_buildreq("pip")
            add_setup_py_requires(dirpath + '/setup.py')
            buildpattern.set_build_pattern("distutils23", default_score)

        if "Makefile.PL" in files or "Build.PL" in files:
            buildpattern.set_build_pattern("cpan", default_score)
        if "SConstruct" in files:
            add_buildreq("scons")
            add_buildreq("python-dev")
            buildpattern.set_build_pattern("scons", default_score)

        if "requirements.txt" in files:
                grab_python_requirements(dirpath + '/requirements.txt')

        for name in files:
            if name.lower() =="cargo.toml":
                parse_cargo_toml(os.path.join(dirpath, name))
            if name.lower().startswith("configure."):
                parse_configure_ac(os.path.join(dirpath, name))
            if name.lower().startswith("rakefile") and buildpattern.default_pattern == "ruby":
                Rakefile(os.path.join(dirpath, name))
            if name.lower() == "makefile":
                buildpattern.set_build_pattern("make", default_score)
            if name.lower() == "autogen.sh":
                buildpattern.set_build_pattern("autogen", default_score)
            if name.lower() == "cmakelists.txt":
                buildpattern.set_build_pattern("cmake", default_score)

    can_reconf = os.path.exists(os.path.join(dir, "configure.ac"))
    if not can_reconf:
        can_reconf = os.path.exists(os.path.join(dir, "configure.in"))

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
    specfile.buildreqs = buildreqs
    specfile.requires = requires
    specfile.cargo_bin = cargo_bin
