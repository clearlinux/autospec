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

import re

import build
import config
import tarball

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


def process_NEWS(file):
    global commitmessage
    news = []
    start = 0
    stop = 0
    success = 0

    if config.old_version is None or config.old_version == tarball.version:
        return

    try:
        with open(build.download_path + "/" + file, encoding="latin-1") as f:
            news = f.readlines()
    except EnvironmentError:
        return

    stop = len(news)
    if stop <= start:
        return

    i = start
    while i < stop:
        news[i] = news[i].strip('\n')
        i = i + 1

    i = start + 1
    while i < stop - 1:
        if news[i] == config.old_version and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i] == "Overview of changes leading to " + config.old_version and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i] == config.old_version + ":" and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i] == tarball.version + ":" and news[i - 1] == "":
            start = i
        if news[i] == tarball.name + "-" + config.old_version + ":" and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i] == tarball.name + "-" + tarball.version + ":" and news[i - 1] == "":
            start = i
        if news[i] == "- " + config.old_version + ":" and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i] == "- " + tarball.version + ":" and news[i - 1] == "":
            start = i
        if news[i].find(config.old_version) >= 0 and news[i].find("*** Changes in ") >= 0 and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i].find(config.old_version) >= 0 and news[i].find("201") >= 0 and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i].lower().find(tarball.name + " " + config.old_version) >= 0 and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i].find(config.old_version) >= 0 and news[i].find("Version ") >= 0 and news[i - 1] == "":
            stop = i - 1
            success = 1
        if news[i].find(tarball.version) >= 0 and news[i].find("Version ") >= 0 and news[i - 1] == "":
            start = i

        if news[i].find(config.old_version + ":") == 0:
            stop = i - 1
            success = 1
        if news[i] == config.old_version and news[i + 1].find("---") >= 0:
            stop = i - 1
            success = 1
        if news[i] == tarball.version and news[i + 1].find("---") >= 0:
            start = i

        i = i + 1

    if success == 0:
        return

    # now search for CVEs
    i = start
    pat = re.compile("(CVE\-[0-9]+\-[0-9]+)")
    while i < stop and i < start:
        match = pat.search(news[i])
        if match:
                s = match.group(1)
                new_cve(s)
        i = i + 1

    commitmessage.append("")
    i = start
    while i < stop and i < start + 15:
        commitmessage.append(news[i])
        i = i + 1
    commitmessage.append("")


def guess_commit_message():
    global cvestring

    # default commit messages before we get too smart
    if config.old_version is not None and config.old_version != tarball.version:
        commitmessage.append(tarball.name + ": Autospec creation for update from version " +
                             config.old_version + " to version " +
                             tarball.version)
    else:
        if have_cves:
            commitmessage.append(tarball.name + ": Fix for " + cvestring.strip())
        else:
            commitmessage.append(tarball.name + ": Autospec creation for version " +
                                 tarball.version)
    commitmessage.append("")

    if have_cves:
        commitmessage.append("CVEs fixed in this build:")
        commitmessage.extend(list(cves))
        commitmessage.append("")

    process_NEWS("NEWS")
    process_NEWS("ChangeLog")

    print("Guessed commit message:")
    with open(build.download_path + "/commitmsg", "w", encoding="latin-1") as file:
        file.write("\n".join(commitmessage) + "\n")
    try:
        print(commitmessage)
    except:
        print("Can't print")
