#!/bin/true
#
# specdescription.py - part of autospec
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
# create the following parts of the spec file
#
# %description
# Summary
# Group
# %description <subpackage>
#

import os
import license

default_group = "Development/Tools"
default_description = "No detailed description available"
default_description_score = 0
default_summary = "No detailed summary available"
default_summary_score = 0


def clean_license_string(str):

    if str.find("same as") >= 0:
        return ""
    str = str.replace(" (", "(")
    str = str.replace(" v2", "-2")
    str = str.replace(" v3", "-3")
    str = str.replace(" 2", "-2")
    str = str.replace(" 3", "-3")
    str = str.replace(" <", "<")
    str = str.replace(" >", ">")
    str = str.replace("= ", "=")
    str = str.replace("GPL(>=-2)", "GPL-2.0+")

    str = str.replace("Modified", "")
    str = str.replace("OSI", "")
    str = str.replace("Approved", "")
    str = str.replace("Simplified", "")
    str = str.replace("file", "")
    str = str.replace("LICENSE", "")

    return str


#
# Parse any existing RPM specfiles
#

def description_from_spec(specfile):
    global default_description
    global default_summary
    global default_summary_score
    global default_description_score
    specdesc = ""
    phase = 0
    file = open(specfile, "r", encoding="latin-1")
    for line in file.readlines():
        if line.startswith("#"):
            continue

        if line.startswith("%"):
            phase = 0

        if line.startswith("License:") and line.find("Copyright") < 0 and line.find("see ") < 0 and line.find("(") < 0:
            splits = line.split(":")[1:]
            words = ":".join(splits).strip()
            if words in license.license_translations:
                print("Adding license from spec:", words)
                license.add_license(words)
            else:
                words = clean_license_string(words).split()
                for word in words:
                    if word.find(":") < 0 or word.startswith('http'):
                        print("Adding license from spec:", word)
                        license.add_license(word)

        if line.startswith("Summary: ") and default_summary_score < 4:
            default_summary = line[9:]
            default_summary_score = 4

        if phase == 1:
            specdesc = specdesc + line

        if line.endswith("%description\n"):
            phase = 1
    if default_description_score < 4:
        default_description = specdesc
        default_description_score = 4
    file.close()


def description_from_pkginfo(specfile):
    global default_description
    global default_summary
    global default_summary_score
    global default_description_score
    specdesc = ""
    phase = 0
    file = open(specfile, "r", encoding="latin-1")
    for line in file.readlines():
        if line.find(":") and phase == 1:
            phase = 0

        if line.lower().startswith("license:") and line.find("Copyright") < 0 and line.find("see ") < 0:
            splits = line.split(":")[1:]
            words = ":".join(splits).strip()
            if words in license.license_translations:
                print("Adding license from PKG-INFO:", words)
                license.add_license(words)
            else:
                words = clean_license_string(words).split()
                for word in words:
                    if word.find(":") < 0:
                        print("Adding license from PKG-INFO:", word)
                        license.add_license(word)

        if line.startswith("Summary: ") and default_summary_score < 4:
            default_summary = line[9:]
            default_summary_score = 4

        if line.startswith("abstract:") and default_summary_score < 4:
            default_summary = line[9:].strip()
            default_summary_score = 4

        if phase == 1:
            specdesc = specdesc + line

        if line.startswith("Description:"):
            phase = 1
    if default_description_score < 4 and len(specdesc) > 10:
        default_description = specdesc
        default_description_score = 4
    file.close()

#
# Parse pkgconfig files for Description: lines
#


def summary_from_pkgconfig(pkgfile, package):
    global default_summary
    global default_summary_score
    score = 2

    if pkgfile.find(package + ".pc") >= 0:
        score = 3

    file = open(pkgfile, "r")
    for line in file.readlines():
        if line.startswith("Description:") and default_summary_score < score:
            default_summary = line[13:]
            default_summary_score = score
    file.close()


def summary_from_R(pkgfile, package):
    global default_summary
    global default_summary_score
    score = 2

    if pkgfile.find("DESCRIPTION") >= 0:
        score = 3

    file = open(pkgfile, "r", encoding="latin-1")
    for line in file.readlines():
        if line.startswith("Title:") and default_summary_score < score:
            default_summary = line[7:]
            default_summary_score = score
    file.close()


#
# some lines from a readme are just boilerplate and should be skipped
#
def skipline(line):
    if line.find("Copyright") >= 0:
        return 1
    if line.find("Free Software Foundation, Inc.") >= 0:
        return 1
    if line.find("Copying and distribution of") >= 0:
        return 1
    if line.find("are permitted in any") >= 0:
        return 1
    if line.find("notice and this notice") >= 0:
        return 1
    if line.find("README") >= 0:
        return 1
    if line.find("-*-") >= 0:
        return 1

    if line.endswith("introduction"):
        return 1
    return 0


#
# Try to pick the first paragraph or two from the readme file
#
def description_from_readme(readmefile):
    global default_description
    global default_description_score
    state = 0
    desc = ""
    score = 1

    if readmefile.lower().endswith("readme"):
        score = 1.5

    file = open(readmefile, "r", encoding="latin-1")
    for line in file.readlines():
        if state == 1 and len(line) < 2 and len(desc) > 80:
            state = 2
        if state == 0 and len(line) > 2:
            state = 1
        if state == 1:
            if skipline(line) == 0 and len(line) > 2:
                desc = desc + line.strip() + "\n"

    if default_description_score < score:
        default_description = desc
        default_description_score = score
    file.close()

#
# Scan the project directory for things we can use to guess a description
# and summary
#


def scan_for_description(package, dir):
    global default_summary
    for dirpath, dirnames, files in os.walk(dir):
        for name in files:
            if name.lower().endswith(".spec"):
                description_from_spec(os.path.join(dirpath, name))
            if name.lower().endswith("pkg-info"):
                description_from_pkginfo(os.path.join(dirpath, name))
            if name.lower().endswith("meta.yml"):
                description_from_pkginfo(os.path.join(dirpath, name))
            if name.lower().endswith("description"):
                description_from_pkginfo(os.path.join(dirpath, name))
            if name.lower().endswith(".pc"):
                summary_from_pkgconfig(os.path.join(dirpath, name), package)
            if name.startswith("DESCRIPTION"):
                summary_from_R(os.path.join(dirpath, name), package)
            if name.lower().endswith(".pc.in"):
                summary_from_pkgconfig(os.path.join(dirpath, name), package)
            if name.lower().startswith("readme"):
                description_from_readme(os.path.join(dirpath, name))

    print("Summary     :", default_summary.strip())

#  print("Summary: ", default_summary)
#  print("%description")
#  print(default_description)


def write_summary(file):
    global default_summary
    global default_group
    file.write("Summary  : " + default_summary.strip() + "\n")
    file.write("Group    : " + default_group.strip() + "\n")


def write_description(file, package=""):
    global default_description
    if len(package) == 0:
        file.write("\n%description\n" + default_description.strip() + "\n")
    else:
        file.write("\n%description " + package +
                   "\n Subpackage " + package + "\n\n")
