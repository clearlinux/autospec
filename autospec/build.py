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
import sys

import util


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
    s = s.replace(" and usability", "")
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


def check_for_warning_pattern(line):
    """Print warning if a line matches against a warning list."""
    warning_patterns = [
        "march=native"
    ]
    for pat in warning_patterns:
        if pat in line:
            util.print_warning("Build log contains: {}".format(pat))


def get_mock_cmd():
    """Set mock command to use sudo as needed."""
    # Some distributions (e.g. Fedora) use consolehelper to run mock,
    # while others (e.g. Clear Linux) expect the user run it via sudo.
    if os.path.basename(os.path.realpath('/usr/bin/mock')) == 'consolehelper':
        return '/usr/bin/mock'
    return 'sudo /usr/bin/mock'


class Build(object):
    """Manage package builds."""

    def __init__(self):
        """Initialize default build settings."""
        self.success = 0
        self.round = 0
        self.must_restart = 0
        self.file_restart = 0
        self.uniqueext = ''
        self.warned_about = set()
        self.patch_name_line = re.compile(r'^Patch #[0-9]+ \((.*)\):$')
        self.patch_fail_line = re.compile(r'^Skipping patch.$')

    def simple_pattern_pkgconfig(self, line, pattern, pkgconfig, conf32, requirements):
        """Check for pkgconfig patterns and restart build as needed."""
        pat = re.compile(pattern)
        match = pat.search(line)
        if match:
            self.must_restart += requirements.add_pkgconfig_buildreq(pkgconfig, conf32, cache=True)

    def simple_pattern(self, line, pattern, req, requirements):
        """Check for simple patterns and restart the build as needed."""
        pat = re.compile(pattern)
        match = pat.search(line)
        if match:
            self.must_restart += requirements.add_buildreq(req, cache=True)

    def failed_pattern(self, line, config, requirements, pattern, verbose, buildtool=None):
        """Check against failed patterns to restart build as needed."""
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
                    self.must_restart += requirements.add_buildreq(req, cache=True)
            elif buildtool == 'pkgconfig':
                self.must_restart += requirements.add_pkgconfig_buildreq(s, config.config_opts.get('32bit'), cache=True)
            elif buildtool == 'R':
                if requirements.add_buildreq("R-" + s, cache=True) > 0:
                    self.must_restart += 1
            elif buildtool == 'perl':
                s = s.replace('inc::', '')
                self.must_restart += requirements.add_buildreq('perl(%s)' % s, cache=True)
            elif buildtool == 'pypi':
                s = util.translate(s)
                if not s:
                    return
                self.must_restart += requirements.add_buildreq(f"pypi({s.lower().replace('-', '_')})", cache=True)
            elif buildtool == 'catkin':
                self.must_restart += requirements.add_pkgconfig_buildreq(s, config.config_opts.get('32bit'), cache=True)
                self.must_restart += requirements.add_buildreq(s, cache=True)
        except Exception:
            if s.strip() and s not in self.warned_about and s[:2] != '--':
                util.print_warning(f"Unknown pattern match: {s}")
                self.warned_about.add(s)

    def parse_buildroot_log(self, filename, returncode):
        """Handle buildroot log contents."""
        if returncode == 0:
            return True
        self.must_restart = 0
        self.file_restart = 0
        fatals = []
        util.call("sync")
        with util.open_auto(filename, "r") as rootlog:
            loglines = rootlog.readlines()
        missing_pat = re.compile(r"^.*No matching package to install: '(.*)'$")
        for line in loglines:
            match = missing_pat.match(line)
            if match is not None:
                fatals.append(f"Cannot resolve dependency name: {match.group(1)}")
        if fatals:
            util.print_fatal('\n'.join(fatals))
            sys.exit(1)

    def parse_build_results(self, filename, returncode, filemanager, config, requirements, content):
        """Handle build log contents."""
        requirements.verbose = 1
        self.must_restart = 0
        self.file_restart = 0
        infiles = 0
        patch_name = ""

        # Flush the build-log to disk, before reading it
        util.call("sync")
        with util.open_auto(filename, "r") as buildlog:
            loglines = buildlog.readlines()
        for line in loglines:
            if patch_name_match := self.patch_name_line.search(line):
                patch_name = patch_name_match.groups()[0]
            if patch_name:
                if self.patch_fail_line.search(line):
                    self.must_restart += config.remove_backport_patch(patch_name)
            for pat in config.pkgconfig_pats:
                self.simple_pattern_pkgconfig(line, *pat, config.config_opts.get('32bit'), requirements)

            for pat in config.simple_pats:
                self.simple_pattern(line, *pat, requirements)

            for pat in config.failed_pats:
                self.failed_pattern(line, config, requirements, *pat)

            check_for_warning_pattern(line)

            # Search for files to add to the %files section.
            # * infiles == 0 before we reach the files listing
            # * infiles == 1 for the "Installed (but unpackaged) file(s) found" header
            #     and for the entirety of the files listing
            # * infiles == 2 after the files listing has ended
            if infiles == 1:
                for search in ["RPM build errors", "Childreturncodewas",
                               "Child returncode", "Empty %files file"]:
                    if search in line:
                        infiles = 2
                for start in ["Building", "Child return code was"]:
                    if line.startswith(start):
                        infiles = 2

            if infiles == 0 and "Installed (but unpackaged) file(s) found:" in line:
                infiles = 1
            elif infiles == 1 and "not matching the package arch" not in line:
                # exclude blank lines from consideration...
                file = line.strip()
                if file and file[0] == "/":
                    filemanager.push_file(file, content.name)

            if line.startswith("Sorry: TabError: inconsistent use of tabs and spaces in indentation"):
                print(line)
                returncode = 99

            nvr = f"{content.name}-{content.version}-{content.release}"
            match = f"File not found: /builddir/build/BUILDROOT/{nvr}.x86_64/"
            if match in line:
                missing_file = "/" + line.split(match)[1].strip()
                filemanager.remove_file(missing_file)

            if line.startswith("Executing(%clean") and returncode == 0:
                print("RPM build successful")
                self.success = 1

    def package(self, filemanager, mockconfig, mockopts, config, requirements, content, cleanup=False):
        """Run main package build routine."""
        self.round += 1
        self.success = 0
        mock_cmd = get_mock_cmd()
        print("Building package " + content.name + " round", self.round)

        self.uniqueext = content.name

        if cleanup:
            cleanup_flag = "--cleanup-after"
        else:
            cleanup_flag = "--no-cleanup-after"

        print("{} mock chroot at /var/lib/mock/clear-{}".format(content.name, self.uniqueext))

        if self.round == 1:
            shutil.rmtree('{}/results'.format(config.download_path), ignore_errors=True)
            os.makedirs('{}/results'.format(config.download_path))

        cmd_args = [
            mock_cmd,
            f"--root={mockconfig}",
            "--buildsrpm",
            "--sources=./",
            f"--spec={content.name}.spec",
            f"--uniqueext={self.uniqueext}-src",
            "--result=results/",
            cleanup_flag,
            mockopts,
        ]

        util.call(" ".join(cmd_args),
                  logfile=f"{config.download_path}/results/mock_srpm.log",
                  cwd=config.download_path)

        # back up srpm mock logs
        util.call("mv results/root.log results/srpm-root.log", cwd=config.download_path)
        util.call("mv results/build.log results/srpm-build.log", cwd=config.download_path)

        srcrpm = f"results/{content.name}-{content.version}-{content.release}.src.rpm"

        cmd_args = [
            mock_cmd,
            f"--root={mockconfig}",
            "--result=results/",
            srcrpm,
            "--enable-plugin=ccache",
            f"--uniqueext={self.uniqueext}",
            cleanup_flag,
            mockopts,
        ]

        if config.config_opts.get('avoid_rebuild') and not cleanup and self.must_restart == 0 and self.file_restart > 0 and set(filemanager.excludes) == set(filemanager.manual_excludes):
            cmd_args.append("--no-clean")
            cmd_args.append("--short-circuit=binary")

        ret = util.call(" ".join(cmd_args),
                        logfile=f"{config.download_path}/results/mock_build.log",
                        check=False,
                        cwd=config.download_path)

        # sanity check the build log
        if not os.path.exists(config.download_path + "/results/build.log"):
            util.print_fatal("Mock command failed, results log does not exist. User may not have correct permissions.")
            sys.exit(1)

        self.parse_buildroot_log(config.download_path + "/results/root.log", ret)

        self.parse_build_results(config.download_path + "/results/build.log", ret, filemanager, config, requirements, content)
        if filemanager.has_banned:
            util.print_fatal("Content in banned paths found, aborting build")
            sys.exit(1)
