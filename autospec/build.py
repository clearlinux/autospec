#!/bin/true
#
# build.py - part of autospec
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
# Actually build the package
#

import buildreq
import files
import getpass
import re
import tarball
import os

import config
import util
import filecmp

success = 0
round = 0
must_restart = 0
base_path = "/tmp/" + getpass.getuser() + "/"
output_path = base_path + "output"
download_path = output_path + "/" + tarball.name
mock_cmd = '/usr/bin/mock'


def simple_pattern_pkgconfig(line, pattern, pkgconfig):
    global must_restart
    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        must_restart += buildreq.add_pkgconfig_buildreq(pkgconfig)


def simple_pattern(line, pattern, req):
    global must_restart
    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        must_restart += buildreq.add_buildreq(req)


def failed_pattern(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            req = config.failed_commands[s]
            if req:
                must_restart += buildreq.add_buildreq(req)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_pkgconfig(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        must_restart += buildreq.add_pkgconfig_buildreq(s)


def failed_pattern_R(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if buildreq.add_buildreq("R-" + s) > 0:
                must_restart += 1
                files.push_main_requires("R-" + s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_perl(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            must_restart += buildreq.add_buildreq('perl(%s)' % s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_pypi(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = util.translate(match.group(1))
        if s == "":
            return
        try:
            must_restart += buildreq.add_buildreq(util.translate('%s-python' % s))
        except:
            if verbose > 0:
                print("Unknown python pattern match: ", pattern, s, line)


def failed_pattern_go(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = util.translate(match.group(1))
        if s == "":
            return
        elif s == match.group(1):
            # the requirement it's also golang libpath format
            # (e.g: github.com/<project>/<repo> so transform into pkg name
            s = util.golang_name(s)
        try:
            must_restart += buildreq.add_buildreq(s)
        except:
            if verbose > 0:
                print("Unknown golang pattern match: ", pattern, s, line)


def failed_pattern_ruby(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if s in config.gems:
                must_restart += buildreq.add_buildreq(config.gems[s])
            else:
                must_restart += buildreq.add_buildreq('rubygem-%s' % s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_ruby_table(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if s in config.gems:
                must_restart += buildreq.add_buildreq(config.gems[s])
            else:
                print("Unknown ruby gem match", s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_maven(line, pattern, verbose=0):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if s in config.maven_jars:
                must_restart += buildreq.add_buildreq(config.maven_jars[s])
            else:
                must_restart += buildreq.add_buildreq('jdk-%s' % s)
        except:
            if verbose > 0:
                print("Unknown maven jar match: ", s)


def parse_build_results(filename, returncode):
    global must_restart
    global success
    buildreq.verbose = 1
    must_restart = 0
    infiles = 0

    # Flush the build-log to disk, before reading it
    util.call("sync")
    file = open(filename, "r", encoding="latin-1")
    for line in file.readlines():
        simple_pattern_pkgconfig(line, r"which: no qmake", "Qt")
        simple_pattern_pkgconfig(line, r"XInput2 extension not found", "xi")
        simple_pattern_pkgconfig(line, r"checking for UDEV\.\.\. no", "udev")
        simple_pattern_pkgconfig(
            line, r"checking for UDEV\.\.\. no", "libudev")
        simple_pattern_pkgconfig(
            line, r"XMLLINT not set and xmllint not found in path", "libxml-2.0")
        simple_pattern_pkgconfig(
            line, r"error\: xml2-config not found", "libxml-2.0")
        simple_pattern_pkgconfig(
            line, r"error: must install xorg-macros", "xorg-macros")
        simple_pattern(
            line, r"Cannot find development files for any supported version of libnl", "libnl-dev")
        simple_pattern(line, r"/<http:\/\/www.cmake.org>", "cmake")
        simple_pattern(line, r"\-\- Boost libraries:", "boost-dev")
        simple_pattern(line, r"XInput2 extension not found", "inputproto")
        simple_pattern(line, r"^WARNING: could not find 'runtest'$", "dejagnu")
        simple_pattern(line, r"^WARNING: could not find 'runtest'$", "expect")
        simple_pattern(line, r"^WARNING: could not find 'runtest'$", "tcl")
        simple_pattern(line, r"VignetteBuilder package required for checking but installed:", "R-knitr")
        simple_pattern(
            line, r"You must have XML::Parser installed", "perl(XML::Parser)")
        simple_pattern(
            line, r"checking for Apache .* module support", "httpd-dev")
        simple_pattern(
            line, r"checking for.*in -ljpeg... no", "libjpeg-turbo-dev")
        simple_pattern(
            line, r"fatal error\: zlib\.h\: No such file or directory", "zlib-dev")
        simple_pattern(line, r"\* tclsh failed", "tcl")
        simple_pattern(
            line, r"\/usr\/include\/python2\.7\/pyconfig.h", "python-dev")
        simple_pattern(
            line, r"checking \"location of ncurses\.h file\"", "ncurses-dev")
        simple_pattern(line, r"Can't exec \"aclocal\"", "automake")
        simple_pattern(line, r"Can't exec \"aclocal\"", "libtool")
        simple_pattern(
            line, r"configure: error: no suitable Python interpreter found", "python-dev")
        simple_pattern(line, r"Checking for header Python.h", "python-dev")
        simple_pattern(
            line, r"configure: error: No curses header-files found", "ncurses-dev")
        simple_pattern(line, r" \/usr\/include\/python2\.6$", "python-dev")
        simple_pattern(line, r"to compile python extensions", "python-dev")
        simple_pattern(line, r"testing autoconf... not found", "autoconf")
        simple_pattern(line, r"configure\: error\: could not find Python headers", "python-dev")
        simple_pattern(line, r"checking for libxml libraries", "libxml2-dev")
        simple_pattern(line, r"configure: error: no suitable Python interpreter found", "python3")
        simple_pattern(line, r"configure: error: pcre-config for libpcre not found", "pcre")
        simple_pattern(line, r"checking for OpenSSL", "openssl-dev")
        simple_pattern(line, r"Package systemd was not found in the pkg-config search path.", "systemd-dev")
        simple_pattern(line, r"Unable to find the requested Boost libraries.", "boost-dev")
        simple_pattern(line, r"libproc not found. Please configure without procps", "procps-ng-dev")
        simple_pattern(line, r"configure: error: glib2", "glib-dev")

# simple_pattern(line, r"Can't locate Test/More.pm", "perl-Test-Simple")

        failed_pattern(line, r"checking for library containing (.*)... no")
        failed_pattern(line, r"checking for (.*?)\.\.\. not_found")
        failed_pattern(line, r"checking for (.*?)\.\.\. not found")
        failed_pattern(line, r"Checking for (.*?)\s>=.*\s*: not found")
        failed_pattern(line, r"Checking for (.*?)\s*: not found")
        failed_pattern(line, r"configure: error: pkg-config missing (.*)")
        failed_pattern(line, r"configure: error: Cannot find (.*)\. Make sure")
        failed_pattern(line, r"checking for (.*?)\.\.\. no")
        failed_pattern(line, r"checking for (.*) support\.\.\. no")
        failed_pattern(line, r"checking (.*?)\.\.\. no")
        failed_pattern(line, r"checking for (.*)... configure: error")
        failed_pattern(line, r"checking for (.*) with pkg-config... no")
        failed_pattern(line, r"Checking for (.*) development files... No")
        failed_pattern(line, r"which\: no ([a-zA-Z\-]*) in \(")
        failed_pattern(line, r"checking for (.*) support\.\.\. no")
        failed_pattern(
            line, r"checking for (.*) in default path\.\.\. not found")
        failed_pattern(line, r" ([a-zA-Z0-9\-]*\.m4) not found")
        failed_pattern(line, r" exec: ([a-zA-Z0-9\-]+): not found")
        failed_pattern(line, r"configure\: error\: Unable to locate (.*)")
        failed_pattern(line, r"No rule to make target `(.*)',")
        failed_pattern(line, r"ImportError\: No module named (.*)")
        failed_pattern(line, r"/usr/bin/python.*\: No module named (.*)")
        failed_pattern(line, r"ImportError\: cannot import name (.*)")
        failed_pattern(line, r"ImportError\: ([a-zA-Z]+) module missing")
        failed_pattern(
            line, r"checking for [a-zA-Z0-9\_\-]+ in (.*?)\.\.\. no")
        failed_pattern(line, r"No library found for -l([a-zA-Z\-])")
        failed_pattern(line, r"\-\- Could NOT find ([a-zA-Z0-9]+)")
        failed_pattern(
            line, r"By not providing \"([a-zA-Z0-9]+).cmake\" in CMAKE_MODULE_PATH this project")
        failed_pattern(
            line, r"CMake Error at cmake\/modules\/([a-zA-Z0-9]+).cmake")
        failed_pattern(line, r"Could NOT find ([a-zA-Z0-9]+)")
        failed_pattern(line, r"  Could not find ([a-zA-Z0-9]+)")
        failed_pattern(line, r"  Did not find ([a-zA-Z0-9]+)")
        failed_pattern(
            line, r"([a-zA-Z\-]+) [0-9\.]+ is required to configure this module; please install it or upgrade your CPAN\/CPANPLUS shell.")
        failed_pattern(line, r"\/bin\/ld: cannot find (-l[a-zA-Z0-9\_]+)")
        failed_pattern(line, r"fatal error\: (.*)\: No such file or directory")
        failed_pattern(line, r"([a-zA-Z0-9\-\_\.]*)\: command not found", 1)
#    failed_pattern(line, r"\: (.*)\: command not found", 1)
        failed_pattern(line, r"-- (.*) not found.", 1)
        failed_pattern(
            line, r"You need ([a-zA-Z0-9\-\_]*) to build this program.", 1)
        failed_pattern(line, r"Cannot find ([a-zA-Z0-9\-_\.]*)", 1)
        failed_pattern(line, r"    ([a-zA-Z]+\:\:[a-zA-Z]+) not installed", 1)
        failed_pattern(line, r"([a-zA-Z\-]*) tool not found or not executable")
        failed_pattern(line, r"([a-zA-Z\-]*) validation tool not found or not executable")
        failed_pattern(line, r"Could not find suitable distribution for Requirement.parse\('([a-zA-Z\-]*)")
        failed_pattern(line, r"unable to execute '([a-zA-Z\-]*)': No such file or directory")
        failed_pattern(line, r"Unable to find '(.*)'")
        failed_pattern(line, r"Downloading https?://.*\.python\.org/packages/.*/.?/([A-Za-z]*)/.*")
        failed_pattern(line, r"configure\: error\: ([a-zA-Z0-9]+) is required to build")
        failed_pattern(line, r".* /usr/bin/([a-zA-Z0-9-_]*).*not found")
        failed_pattern(line, r"warning: failed to load external entity \"(/usr/share/sgml/docbook/xsl-stylesheets)/.*\"")
        failed_pattern(line, r"Warning\: no usable ([a-zA-Z0-9]+) found")
        failed_pattern(line, r"/usr/bin/env\: (.*)\: No such file or directory")
        failed_pattern(line, r"make: ([a-zA-Z0-9].+): Command not found")
        failed_pattern_R(line, r"ERROR: dependencies.*'([a-zA-Z0-9\-]*)' are not available for package '.*'")
        failed_pattern_R(line, r"Package which this enhances but not available for checking: '([a-zA-Z0-9\-]*)'")
        failed_pattern_R(line, r"Unknown packages '([a-zA-Z0-9\-]*)'.* in Rd xrefs")
        failed_pattern_R(line, r"Unknown package '([a-zA-Z0-9\-]*)'.* in Rd xrefs")
        failed_pattern_R(line, r"ERROR: dependencies '([a-zA-Z0-9\-]*)'.* are not available for package '.*'")
        failed_pattern_R(line, r"ERROR: dependencies '.*', '([a-zA-Z0-9\-]*)',.* are not available for package '.*'")
        failed_pattern_R(line, r"ERROR: dependency '([a-zA-Z0-9\-]*)' is not available for package '.*'")
        failed_pattern_R(line, r"there is no package called '([a-zA-Z0-9\-]*)'")
        failed_pattern_perl(line, r"you may need to install the ([a-zA-Z0-9\-:]*) module")
        failed_pattern_perl(line, r"    !  ([a-zA-Z:]+) is not installed")
        failed_pattern_perl(line, r"Warning: prerequisite ([a-zA-Z:]+) [0-9\.]+ not found.")
        failed_pattern_perl(line, r"Can't locate [a-zA-Z\/\.]+ in @INC \(you may need to install the ([a-zA-Z:]+) module\)")
        failed_pattern_pypi(line, r"Download error on https://pypi.python.org/simple/([a-zA-Z0-9\-\._:]+)/")
        failed_pattern_pypi(line, r"No matching distribution found for ([a-zA-Z0-9\-\._]+)")
        failed_pattern_pypi(line, r"ImportError:..*: No module named ([a-zA-Z0-9\-\._]+)")
        failed_pattern_pypi(line, r"ImportError: No module named ([a-zA-Z0-9\-\._]+)")
        failed_pattern_pypi(line, r"ImportError: No module named '([a-zA-Z0-9\-\._]+)'")
        failed_pattern_pkgconfig(line, r"Perhaps you should add the directory containing `([a-zA-Z0-9\-:]*)\.pc'")
        failed_pattern_pkgconfig(line, r"No package '([a-zA-Z0-9\-:]*)' found")
        failed_pattern_pkgconfig(line, r"Package '([a-zA-Z0-9\-:]*)', required by '.*', not found")
        failed_pattern_ruby(line, r"WARNING:  [a-zA-Z\-\_]+ dependency on ([a-zA-Z0-9\-\_:]*) \([<>=~]+ ([0-9.]+).*\) .*")
        failed_pattern_ruby(line, r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-:]*)' \([>=]+ ([0-9.]+).*\), here is why:")
        failed_pattern_ruby(line, r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-\_]*)' \([>=]+ ([0-9.]+).*\) in any repository")
        failed_pattern_ruby(line, r"Could not find '([a-zA-Z0-9\-\_]*)' \([~<>=]+ ([0-9.]+).*\) among [0-9]+ total gem")
        failed_pattern_ruby(line, r"Could not find gem '([a-zA-Z0-9\-\_]+) \([~<>=0-9\.\, ]+\) ruby'")
        failed_pattern_ruby(line, r"Gem::LoadError: Could not find '([a-zA-Z0-9\-\_]*)'")
        failed_pattern_ruby(line, r"[a-zA-Z0-9\-:]* is not installed: cannot load such file -- rdoc/([a-zA-Z0-9\-:]*)")
        failed_pattern_ruby(line, r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:]+)/.*")
        failed_pattern_ruby(line, r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:]+) ")
        failed_pattern_ruby_table(line, r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:\/]+)")
        failed_pattern_ruby_table(line, r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:\/\_]+)")
        failed_pattern_go(line, r".*\.go:.*cannot find package \"(.*)\" in any of:")
        failed_pattern_maven(line, "\[ERROR\] .* Cannot access central \(.*\) in offline mode and the artifact .*:(.*):[pom|jar]+:.* has not been downloaded from it before. .*")
        failed_pattern_maven(line, "\[ERROR\] .* Cannot access central \(.*\) in offline mode and the artifact .*:(.*):[jar|pom]+:.* has not been downloaded from it before.*")
        failed_pattern_maven(line, "\[WARNING\] The POM for .*:(.*):[jar|pom]+:.* is missing, no dependency information available")

        if infiles == 1 and line.find("RPM build errors") >= 0:
            infiles = 2
        if infiles == 1 and line.find("Childreturncodewas") >= 0:
            infiles = 2
        if infiles == 1 and line.find("Child returncode") >= 0:
            infiles = 2
        if infiles == 1 and line.startswith("Building"):
            infiles = 2
        if infiles == 1 and line.startswith("Child return code was"):
            infiles = 2
        if infiles == 1 and line.find("Empty %files file") >= 0:
            infiles = 2

        if line.find("Installed (but unpackaged) file(s) found:") >= 0:
            infiles = 1
        else:
            if infiles == 1 and "not matching the package arch" not in line:
                files.push_file(line.strip())

        if line.startswith("Sorry: TabError: inconsistent use of tabs and spaces in indentation"):
            print(line)
            returncode = 99

        if "File not found: /builddir/build/BUILDROOT/" in line:
            left = "File not found: /builddir/build/BUILDROOT/%s-%s-%s.x86_64/" % (tarball.name, tarball.version, tarball.release)
            missing_file = "/" + line.split(left)[1].strip()
            files.remove_file(missing_file)

        if line.startswith("Executing(%clean") and returncode == 0:
            print("RPM build successful")
            success = 1

    file.close()


def set_mock():
    global mock_cmd
    if filecmp.cmp('/usr/bin/mock', '/usr/sbin/mock'):
        mock_cmd = 'sudo /usr/bin/mock'


def package():
    global round
    round = round + 1
    set_mock()
    print("Building package " + tarball.name + " round", round)
    # call(mock_cmd + " -q -r clear --scrub=cache")
    # call(mock_cmd + " -q -r clear --scrub=all")
    util.call("mkdir -p %s/results" % download_path)
    util.call(mock_cmd + " -r clear --buildsrpm --sources=./ --spec={0}.spec --uniqueext={0} --result=results/ --no-cleanup-after".format(tarball.name),
              logfile="%s/mock_srpm.log" % download_path, cwd=download_path)
    util.call("rm -f results/build.log", cwd=download_path)
    srcrpm = "results/%s-%s-%s.src.rpm" % (tarball.name, tarball.version, tarball.release)
    returncode = util.call(mock_cmd + " -r clear  --result=results/ %s --enable-plugin=ccache  --uniqueext=%s --no-cleanup-after" % (srcrpm, tarball.name),
                           logfile="%s/mock_build.log" % download_path, check=False, cwd=download_path)
    parse_build_results(download_path + "/results/build.log", returncode)
