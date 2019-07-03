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

import os
import re
import shutil
import subprocess

import buildreq
import config
import tarball
import util

success = 0
round = 0
must_restart = 0
base_path = None
download_path = None
uniqueext = ''
warned_about = set()


def setup_workingdir(workingdir):
    """Create directory for expanding tar file."""
    global base_path
    global download_path
    base_path = workingdir
    download_path = os.path.join(base_path, tarball.name)


def simple_pattern_pkgconfig(line, pattern, pkgconfig):
    """Check for pkgconfig patterns and restart build as needed."""
    global must_restart
    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        must_restart += buildreq.add_pkgconfig_buildreq(pkgconfig, cache=True)


def simple_pattern(line, pattern, req):
    """Check for simple patterns and restart the build as needed."""
    global must_restart
    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        must_restart += buildreq.add_buildreq(req, cache=True)


def cleanup_req(s: str) -> str:
    """Strip unhelpful strings from requirements."""
    if "is wanted" in s:
        s = ""
    if "should be defined" in s:
        s = ""
    if "are broken" in s:
        s = ""
    if "is broken" in s:
        s = ""
    if s[0:4] == 'for ':
        s = s[4:]
    s = s.replace(" works as expected", "")
    s = s.replace(" usability", "")
    s = s.replace(" argument", "")
    s = s.replace(" environment variable", "")
    s = s.replace(" environment var", "")
    s = s.replace(" presence", "")
    s = s.replace(" support", "")
    s = s.replace(" implementation is broken", "")
    s = s.replace(" is broken", "")
    s = s.replace(" files can be found", "")
    s = s.replace(" can be found", "")
    s = s.replace(" is declared", "")
    s = s.replace("whether to build ", "")
    s = s.replace("whether ", "")
    s = s.replace("library containing ", "")
    s = s.replace("x86_64-generic-linux-gnu-", "")
    s = s.replace("i686-generic-linux-gnu-", "")
    s = s.replace("'", "")
    s = s.strip()
    return s


def failed_pattern(line, pattern, verbose, buildtool=None):
    """Check against failed patterns to restart build as needed."""
    global must_restart
    global warned_about

    pat = re.compile(pattern)
    match = pat.search(line)
    if not match:
        return
    s = match.group(1)
    # standard configure cleanups
    s = cleanup_req(s)

    if s in config.ignored_commands:
        return

    try:
        if not buildtool:
            req = config.failed_commands[s]
            if req:
                must_restart += buildreq.add_buildreq(req, cache=True)
        elif buildtool == 'pkgconfig':
            must_restart += buildreq.add_pkgconfig_buildreq(s, cache=True)
        elif buildtool == 'R':
            if buildreq.add_buildreq("R-" + s, cache=True) > 0:
                must_restart += 1
                buildreq.add_requires("R-" + s)
        elif buildtool == 'perl':
            s = s.replace('inc::', '')
            must_restart += buildreq.add_buildreq('perl(%s)' % s, cache=True)
        elif buildtool == 'pypi':
            s = util.translate(s)
            if not s:
                return
            must_restart += buildreq.add_buildreq(util.translate('%s-python' % s), cache=True)
        elif buildtool == 'ruby':
            if s in config.gems:
                must_restart += buildreq.add_buildreq(config.gems[s], cache=True)
            else:
                must_restart += buildreq.add_buildreq('rubygem-%s' % s, cache=True)
        elif buildtool == 'ruby table':
            if s in config.gems:
                must_restart += buildreq.add_buildreq(config.gems[s], cache=True)
            else:
                print("Unknown ruby gem match", s)
        elif buildtool == 'maven':
            if s in config.maven_jars:
                must_restart += buildreq.add_buildreq(config.maven_jars[s], cache=True)
            else:
                must_restart += buildreq.add_buildreq('mvn-%s' % s, cache=True)
        elif buildtool == 'catkin':
            must_restart += buildreq.add_pkgconfig_buildreq(s, cache=True)
            must_restart += buildreq.add_buildreq(s, cache=True)

    except Exception:
        if s not in warned_about and s[:2] != '--':
            print("Unknown pattern match: ", s)
            warned_about.add(s)


def parse_buildroot_log(filename, returncode):
    """Handle buildroot log contents."""
    if returncode == 0:
        return True
    global must_restart
    must_restart = 0
    is_clean = True
    util.call("sync")
    with util.open_auto(filename, "r") as rootlog:
        loglines = rootlog.readlines()

    missing_pat = re.compile(r"^.*No matching package to install: '(.*)'$")
    for line in loglines:
        match = missing_pat.match(line)
        if match is not None:
            util.print_fatal("Cannot resolve dependency name: {}".format(match.group(1)))
            is_clean = False

    return is_clean


def check_for_warning_pattern(line):
    """Print warning if a line matches against a warning list."""
    warning_patterns = [
        "march=native"
    ]
    for pat in warning_patterns:
        if pat in line:
            util.print_warning("Build log contains: {}".format(pat))


def parse_build_results(filename, returncode, filemanager):
    """Handle build log contents."""
    global must_restart
    global success
    buildreq.verbose = 1
    must_restart = 0
    infiles = 0

    # Flush the build-log to disk, before reading it
    util.call("sync")
    with util.open_auto(filename, "r") as buildlog:
        loglines = buildlog.readlines()

    for line in loglines:
        for pat in config.pkgconfig_pats:
            simple_pattern_pkgconfig(line, *pat)

        for pat in config.simple_pats:
            simple_pattern(line, *pat)

        for pat in config.failed_pats:
            failed_pattern(line, *pat)

        check_for_warning_pattern(line)

        # search for files to add to the %files section
        # track with infiles. If infiles == 1 we found the header
        # "Installed (but unpackaged) file(s) found" in the build log
        # This tells us to look in the next line. Increment infiles if we don't
        # find a file in the next line.
        if infiles == 1:
            for search in ["RPM build errors", "Childreturncodewas",
                           "Child returncode", "Empty %files file"]:
                if search in line:
                    infiles = 2
            for start in ["Building", "Child return code was"]:
                if line.startswith(start):
                    infiles = 2

        if "Installed (but unpackaged) file(s) found:" in line:
            infiles = 1
        elif infiles == 1 and "not matching the package arch" not in line:
            # exclude blank lines from consideration...
            file = line.strip()
            if file:
                filemanager.push_file(file)

        if line.startswith("Sorry: TabError: inconsistent use of tabs and spaces in indentation"):
            print(line)
            returncode = 99

        if "File not found: /builddir/build/BUILDROOT/" in line:
            left = "File not found: /builddir/build/BUILDROOT/%s-%s-%s.x86_64/" % (tarball.name, tarball.version, tarball.release)
            missing_file = "/" + line.split(left)[1].strip()
            filemanager.remove_file(missing_file)

        if line.startswith("Executing(%clean") and returncode == 0:
            print("RPM build successful")
            success = 1


def reserve_path(path):
    """Try to pre-populate directory at path."""
    try:
        subprocess.check_output(['sudo', 'mkdir', path], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        out = err.output.decode('utf-8')
        return "File exists" not in out

    return True


def get_uniqueext(dirn, dist, name):
    """Find a unique name to create mock chroot without reusing an old one."""
    # Default to tarball name
    resultsdir = os.path.join(dirn, "{}-{}".format(dist, name))
    if reserve_path(resultsdir):
        return name

    # Find a unique extension by checking if it exists in /var/lib/mock
    # Increment the pathname until an unused path is found
    resultsdir += "-1"
    seq = 1
    while not reserve_path(resultsdir):
        seq += 1
        resultsdir = resultsdir.replace("-{}".format(seq - 1), "-{}".format(seq))

    return "{}-{}".format(name, seq)


def get_mock_cmd():
    """Set mock command to use sudo as needed."""
    # Some distributions (e.g. Fedora) use consolehelper to run mock,
    # while others (e.g. Clear Linux) expect the user run it via sudo.
    if os.path.basename(os.path.realpath('/usr/bin/mock')) == 'consolehelper':
        return '/usr/bin/mock'
    return 'sudo /usr/bin/mock'


def package(filemanager, mockconfig, mockopts, cleanup=False):
    """Run main package build routine."""
    global round
    global uniqueext
    global success
    round = round + 1
    success = 0
    mock_cmd = get_mock_cmd()
    print("Building package " + tarball.name + " round", round)

    # determine uniqueext only once
    if cleanup:
        uniqueext = uniqueext or get_uniqueext("/var/lib/mock", "clear", tarball.name)
        cleanup_flag = "--cleanup-after"
    else:
        uniqueext = tarball.name
        cleanup_flag = "--no-cleanup-after"

    print("{} mock chroot at /var/lib/mock/clear-{}".format(tarball.name, uniqueext))

    if round == 1:
        shutil.rmtree('{}/results'.format(download_path), ignore_errors=True)
        os.makedirs('{}/results'.format(download_path))

    util.call("{} -r {} --buildsrpm --sources=./ --spec={}.spec "
              "--uniqueext={} --result=results/ {} {}"
              .format(mock_cmd, mockconfig, tarball.name, uniqueext, cleanup_flag,
                      mockopts),
              logfile="%s/results/mock_srpm.log" % download_path, cwd=download_path)

    # back up srpm mock logs
    util.call("mv results/root.log results/srpm-root.log", cwd=download_path)
    util.call("mv results/build.log results/srpm-build.log", cwd=download_path)

    srcrpm = "results/%s-%s-%s.src.rpm" % (tarball.name, tarball.version, tarball.release)
    returncode = util.call("{} -r {} --result=results/ {} "
                           "--enable-plugin=ccache  --uniqueext={} {}"
                           .format(mock_cmd, mockconfig, srcrpm, uniqueext, cleanup_flag),
                           logfile="%s/results/mock_build.log" % download_path, check=False, cwd=download_path)
    # sanity check the build log
    if not os.path.exists(download_path + "/results/build.log"):
        util.print_fatal("Mock command failed, results log does not exist. User may not have correct permissions.")
        exit(1)

    is_clean = parse_buildroot_log(download_path + "/results/root.log", returncode)
    if is_clean:
        parse_build_results(download_path + "/results/build.log", returncode, filemanager)
