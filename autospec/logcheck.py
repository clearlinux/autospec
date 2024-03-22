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
import sys

from util import print_fatal, write_out


def log_etc(lines):
    """Return the content of the START/etc ... END/etc section."""
    etc = []
    while True:
        line = next(lines)
        line = line.strip()
        if line == 'END/etc':
            break
        if line.startswith('+'):
            continue
        etc.append(line)
    return etc


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
    iter_lines = iter(lines)
    for line in iter_lines:
        if line.strip() == "START/etc":
            etc = log_etc(iter_lines)
            if etc:
                write_log(pkg_loc, "etc_files", etc)
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
            write_log(pkg_loc, 'configure_misses', misses)
            sys.exit(1)

        print("Configure miss: " + match)
        misses.append("Configure miss: " + match)

    if not misses:
        return

    write_log(pkg_loc, 'configure_misses', misses)


def write_log(pkg_loc, fname, content):
    """Create log file with content."""
    write_out(os.path.join(pkg_loc, fname), '\n'.join(sorted(content)))
