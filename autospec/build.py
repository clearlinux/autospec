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
import grp
import shutil

import config
import util

success = 0
round = 0
must_restart = 0
base_path = None
output_path = None
download_path = None
mock_cmd = '/usr/bin/mock'

def setup_workingdir(workingdir):
    global base_path
    global output_path
    global download_path
    base_path = workingdir
    output_path = os.path.join(base_path, "output")
    download_path = os.path.join(output_path, tarball.name)

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


def failed_pattern(line, pattern, verbose, buildtool=None):
    global must_restart

    pat = re.compile(pattern)
    match = pat.search(line)
    if not match:
        return
    s = match.group(1)
    try:
        if not buildtool:
            req = config.failed_commands[s]
            if req:
                must_restart += buildreq.add_buildreq(req)
        elif buildtool == 'pkgconfig':
            must_restart += buildreq.add_pkgconfig_buildreq(s)
        elif buildtool == 'R':
            if buildreq.add_buildreq("R-" + s) > 0:
                must_restart += 1
                buildreq.add_requires("R-" + s)
        elif buildtool == 'perl':
            must_restart += buildreq.add_buildreq('perl(%s)' % s)
        elif buildtool == 'pypi':
            s = util.translate(s)
            if not s:
                return
            must_restart += buildreq.add_buildreq(util.translate('%s-python' % s))
        elif buildtool == 'ruby':
            if s in config.gems:
                must_restart += buildreq.add_buildreq(config.gems[s])
            else:
                must_restart += buildreq.add_buildreq('rubygem-%s' % s)
        elif buildtool == 'ruby table':
            if s in config.gems:
                must_restart += buildreq.add_buildreq(config.gems[s])
            else:
                print("Unknown ruby gem match", s)
        elif buildtool == 'maven':
            if s in config.maven_jars:
                must_restart += buildreq.add_buildreq(config.maven_jars[s])
            else:
                must_restart += buildreq.add_buildreq('jdk-%s' % s)
    except:
        if verbose > 0:
            print("Unknown pattern match: ", s)


def parse_build_results(filename, returncode, filemanager):
    global must_restart
    global success
    buildreq.verbose = 1
    must_restart = 0
    infiles = 0

    # Flush the build-log to disk, before reading it
    util.call("sync")
    with open(filename, "r", encoding="latin-1") as buildlog:
        loglines = buildlog.readlines()

    for line in loglines:
        for pat in config.pkgconfig_pats:
            simple_pattern_pkgconfig(line, *pat)

        for pat in config.simple_pats:
            simple_pattern(line, *pat)

        for pat in config.failed_pats:
            failed_pattern(line, *pat)

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
            filemanager.push_file(line.strip())

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


def set_mock():
    global mock_cmd
    # get group list of current user
    user_grps = [grp.getgrgid(g).gr_name for g in os.getgroups()]
    if os.path.exists('/usr/bin/mock'):
       if 'mock' not in user_grps:
           mock_cmd = 'sudo /usr/bin/mock'


def package(filemanager):
    global round
    round = round + 1
    set_mock()
    print("Building package " + tarball.name + " round", round)
    # call(mock_cmd + " -q -r clear --scrub=cache")
    # call(mock_cmd + " -q -r clear --scrub=all")
    shutil.rmtree('{}/results'.format(download_path), ignore_errors=True)
    os.makedirs('{}/results'.format(download_path))
    util.call(mock_cmd + " -r clear --buildsrpm --sources=./ --spec={0}.spec --uniqueext={0} --result=results/ --no-cleanup-after".format(tarball.name),
              logfile="%s/mock_srpm.log" % download_path, cwd=download_path)
    util.call("rm -f results/build.log", cwd=download_path)
    srcrpm = "results/%s-%s-%s.src.rpm" % (tarball.name, tarball.version, tarball.release)
    returncode = util.call(mock_cmd + " -r clear  --result=results/ %s --enable-plugin=ccache  --uniqueext=%s --no-cleanup-after" % (srcrpm, tarball.name),
                           logfile="%s/mock_build.log" % download_path, check=False, cwd=download_path)
    # sanity check the build log
    if not os.path.exists(download_path + "/results/build.log"):
        util.print_fatal("Mock command failed, results log does not exist. User may not have correct permissions.")
        exit(1)

    parse_build_results(download_path + "/results/build.log", returncode, filemanager)
