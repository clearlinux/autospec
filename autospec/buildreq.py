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

import buildpattern
import patches
import util
import tarball

buildreqs = set()
pythonreqs = set()
banned_buildreqs = set(
    ["llvm-devel", "gcj", "pkgconfig(dnl)", "pkgconfig(hal)", "tslib-0.0", "pkgconfig(parallels-sdk)", "oslo-python"])
verbose = False

autoreconf_reqs = ["gettext-bin", "automake-dev", "automake", "m4", "libtool", "libtool-dev", "pkg-config-dev"]


def add_buildreq(req):
    global verbose
    new = True
    if req in banned_buildreqs:
        return False
    if req in buildreqs:
        new = False
    if verbose and new:
        print("  Adding buildreq:", req)

    buildreqs.add(req)
    return new


def add_pythonreq(req):
    global verbose
    new = True

    if req in pythonreqs:
        new = False
    if new:
        print("Adding python requirement:", req)
        pythonreqs.add(req)
    return new


def add_pkgconfig_buildreq(preq):
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
    for style in [r"PKG_CHECK_MODULES\((.*)\)", r"XDT_CHECK_PACKAGE\((.*)\)"]:
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

    pattern = re.compile(r"PKG_CHECK_EXISTS\((.*)\)")
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

gems = {"hoe": "rubygem-hoe",
        "rspec/core/rake_task": "rubygem-rspec-core",
        "bundler/gem_tasks": "rubygem-rubygems-tasks",
        "bundler/setup": "rubygem-bundler",
        "echoe": "rubygem-echoe",
        "sass": "rubygem-sass",
        "redcarpet": "rubygem-redcarpet",
        "action_view/helpers/sanitize_helper": "rubygem-actionview",
        "appraisal/file": "rubygem-appraisal",
        "benchmark/ips": "rubygem-benchmark-ips",
        "builder": "rubygem-builder",
        "bundler": "rubygem-bundler",
        "gem_hadar": "rubygem-gem_hadar",
        "gherkin/rubify": "rubygem-gherkin",
        "guard/compat/test/helper": "rubygem-guard-compat",
        "html/pipeline": "rubygem-html-pipeline",
        "minitest/autorun": "rubygem-minitest",
        "minitest/unit": "rubygem-minitest",
        "mocha/setup": "rubygem-mocha",
        "nokogiri/diff": "rubygem-nokogiri-diff",
        "pdf/reader": "rubygem-pdf-reader",
        "pry": "rubygem-pry",
        "rake/extensiontask": "rubygem-rake-compiler",
        "rack/test": "rubygem-rack-test",
        "rack/utils": "rubygem-rack",
        "rspec/core": "rubygem-rspec-core",
        "rspec/its": "rubygem-rspec-its",
        "rspec/mocks": "rubygem-rspec-mocks",
        "test/unit": "rubygem-test-unit",
        }


def Rakefile(filename):
    global gems
    file = open(filename, "r", encoding="latin-1")
    lines = file.readlines()
    for line in lines:
        pat = re.compile(r"^require '(.*)'$")
        match = pat.search(line)
        if match:
            s = match.group(1)
            if s != "rubygems" and s in gems:
                print("Rakefile-dep: " + gems[s])
                add_buildreq(gems[s])
            else:
                print("Rakefile-new: rubygem-" + s)


def clean_python_req(str):
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
    # is ret actually a valid (non-empty) string?
    if ret:
        ret = ret.strip() + "-python"
    # use the dictionary to translate funky names to our current pgk names
    ret = util.translate(ret)
    return ret


def grab_python_requirements(descfile):
    file = open(descfile, "r", encoding="latin-1")
    for line in file.readlines():
        add_pythonreq(clean_python_req(line))


def setup_py_python3(filename):
    try:
        with open(filename) as FILE:
            if ":: Python :: 3" in "".join(FILE.readlines()):
                return 1
    except:
        return 0
    return 0


def scan_for_configure(package, dir, autospecdir):
    global default_summary
    count = 0
    for dirpath, dirnames, files in os.walk(dir):
        default_score = 2
        if dirpath != dir:
            default_score = 1

        if any( file.endswith(".go") for file in files):
            add_buildreq("go")
            tarball.name = tarball.go_pkgname
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
            add_buildreq("setuptools")
            add_buildreq("pbr")
            add_buildreq("pip")
            if setup_py_python3(dirpath + '/setup.py') or setup_py_python3(dirpath + '/PKG-INFO'):
                add_buildreq("python3-dev")
                buildpattern.set_build_pattern("distutils23", default_score)
                # force override the pypi rule
                if buildpattern.default_pattern == 'distutils' and buildpattern.pattern_strengh <= 10:
                    buildpattern.default_pattern = 'distutils23'
            else:
                # check for adding python3 support in patches
                try:
                    with open(autospecdir + '/series', 'r') as series:
                        for patchname in series:
                            if setup_py_python3(autospecdir + '/' + patchname.strip()):
                                add_buildreq("python3-dev")
                                buildpattern.set_build_pattern("distutils23", default_score)
                                # force override the pypi rule
                                if buildpattern.default_pattern == 'distutils' and buildpattern.pattern_strengh <= 10:
                                    buildpattern.default_pattern = 'distutils23'
                except:
                    pass
                buildpattern.set_build_pattern("distutils", default_score)

        if "Makefile.PL" in files or "Build.PL" in files:
            buildpattern.set_build_pattern("cpan", default_score)
        if "SConstruct" in files:
            add_buildreq("scons")
            add_buildreq("python-dev")
            buildpattern.set_build_pattern("scons", default_score)

        if "requirements.txt" in files:
                grab_python_requirements(dirpath + '/requirements.txt')

        for name in files:
            if name.lower().startswith("configure."):
                parse_configure_ac(os.path.join(dirpath, name))
            if name.lower().startswith("rakefile"):
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

    if can_reconf and patches.autoreconf:
        print("Patches touch configure.*, adding autoreconf stage")
        for breq in autoreconf_reqs:
            add_buildreq(breq)
    else:
        patches.autoreconf = False

    print("Buildreqs   : ", end="")
    for lic in sorted(buildreqs):
        if count > 4:
            count = 0
            print("\nBuildreqs   : ", end="")
        count = count + 1
        print(lic + " ", end="")
    print("")


def write_buildreq(file):
    if len(buildreqs) > 0:
        for lic in sorted(buildreqs):
            file.write("BuildRequires : " + lic + "\n")
