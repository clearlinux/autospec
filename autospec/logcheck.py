#!/usr/bin/python3
#
# logcheck.py - part of autospec
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

import os
import re

from util import print_fatal, write_out


def logcheck(pkg_loc):
    """Try to discover configuration options that were automatically switched off."""
    log = os.path.join(pkg_loc, 'results', 'build.log')
    if not os.path.exists(log):
        print('build log is missing, unable to perform logcheck.')
        return

    whitelist = []
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(file_dir, 'configure_whitelist')
    with open(file_path, "r") as whitelistf:
        for line in whitelistf:
            if line.startswith("#"):
                continue
            whitelist.append(line.rstrip())

    blacklist = []
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(file_dir, 'configure_blacklist')
    with open(file_path, "r") as blacklistf:
        for line in blacklistf:
            if line.startswith("#"):
                continue
            blacklist.append(line.rstrip())

    with open(log, 'r') as logf:
        lines = logf.readlines()

    pat = re.compile(r"^checking (?:for )?(.*?)\.\.\. no")
    misses = []
    for line in lines:
        match = None
        m = pat.search(line)
        if m:
            match = m.group(1)

        if "none required" in line:
            match = None

        if "warning: format not a string literal" in line:
            match = line

        if not match or match in whitelist:
            continue

        if match in blacklist:
            print_fatal("Blacklisted configure-miss is forbidden: " + match)
            misses.append("Blacklisted configure-miss is forbidden: " + match)
            write_misses(pkg_loc, misses)
            exit(1)

        print("Configure miss: " + match)
        misses.append("Configure miss: " + match)

    if not misses:
        return

    write_misses(pkg_loc, misses)


def write_misses(pkg_loc, misses):
    """Create configure_misses file with automatically disabled configuration options."""
    write_out(os.path.join(pkg_loc, 'configure_misses'), '\n'.join(sorted(misses)))
