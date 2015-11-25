#!/bin/true
#
# commitmessage.py - part of autospec
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
# objective
#
# heuristics to find a git commit message
#
#

import config
import tarball
import subprocess

commitmessage = []

cves = set()
have_cves = False
cvestring = ""


def new_cve(cve):
    global cvestring
    global have_cves
    global cves

    cves.add(cve)
    have_cves = True
    cvestring += " " + cve


def guess_commit_message():
    global cvestring

    # default commit messages before we get too smart
    if config.old_version != None and config.old_version != tarball.version:
        commitmessage.append("Autospec creation for update from version " +
                             config.old_version + " to version " +
                             tarball.version)
    else:
        if have_cves:
          commitmessage.append("Fix for " + cvestring.strip())
        else:
          commitmessage.append("Autospec creation for version " +
                               tarball.version)
    commitmessage.append("")

    if have_cves:
        commitmessage.append("CVEs fixed in this build:")
        commitmessage.extend(list(cves))
        commitmessage.append("")

    print("Guessed commit message:")
    print(commitmessage)
    with open(build.download_path + "/commitmsg", "w") as file:
      file.writelines(commitmessage)
