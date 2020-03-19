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
import re

import license
import util

default_description = "No detailed description available"
default_description_score = 0
default_summary = "No detailed summary available"
default_summary_score = 0


def clean_license_string(lic):
    """Clean up license string by replacing substrings."""
    if lic.find("same as") >= 0:
        return ""

    reps = [(" (", "("),
            (" v2", "-2"),
            (" v3", "-3"),
            (" 2", "-2"),
            (" 3", "-3"),
            (" <", "<"),
            (" >", ">"),
            ("= ", "="),
            ("GPL(>=-2)", "GPL-2.0+"),
            ("Modified", ""),
            ("OSI", ""),
            ("Approved", ""),
            ("Simplified", ""),
            ("file", ""),
            ("LICENSE", "")]

    for sub, rep in reps:
        lic = lic.replace(sub, rep)

    return lic


def assign_summary(summary, score):
    """Assign summary to default_summary if score is greater than default_summary_score."""
    global default_summary
    global default_summary_score
    if score > default_summary_score:
        default_summary = summary
        default_summary_score = score


def assign_description(description, score):
    """Assign description to default_description if score is greater than default_description_score."""
    global default_description
    global default_description_score
    if score > default_description_score:
        default_description = description
        default_description_score = score


def description_from_spec(specfile, translations, blacklist):
    """Parse any existing RPM specfiles."""
    try:
        with util.open_auto(specfile, 'r') as specfd:
            lines = specfd.readlines()
    except FileNotFoundError:
        return

    specdesc = ""
    section = False
    for line in lines:
        if line.startswith("#"):
            continue

        if line.startswith("%"):
            section = False

        excludes = ["Copyright", "see ", "("]
        if line.startswith("License:") and not any(e in line for e in excludes):
            splits = line.split(":")[1:]
            words = ":".join(splits).strip()
            if words in translations:
                print("Adding license from spec:", words)
                license.add_license(words, translations, blacklist)
            else:
                words = clean_license_string(words).split()
                for word in words:
                    if ":" not in word and not word.startswith("@"):
                        print("Adding license from spec:", word)
                        license.add_license(word, translations, blacklist)

        if line.startswith("Summary: "):
            assign_summary(line[9:], 4)

        specdesc += line if section else ""
        # Check for %description after assigning the line to specdesc so the
        # %description string is not included
        if line.endswith("%description\n"):
            section = True

    if len(specdesc) > 10:
        assign_description(specdesc, 4)


def description_from_pkginfo(pkginfo, translations, blacklist):
    """Parse existing package info files."""
    try:
        with util.open_auto(pkginfo, 'r') as pkgfd:
            lines = pkgfd.readlines()
    except FileNotFoundError:
        return

    pkginfo = ""
    section = False
    for line in lines:
        if ":" in line and section:
            section = False

        excludes = ["Copyright", "see "]
        if line.lower().startswith("license:") and not any(e in line for e in excludes):
            splits = line.split(":")[1:]
            words = ":".join(splits).strip()
            if words in translations:
                print("Adding license from PKG-INFO:", words)
                license.add_license(words, translations, blacklist)
            else:
                words = clean_license_string(words).split()
                for word in words:
                    if ":" not in word:
                        print("Adding license from PKG-INFO:", word)
                        license.add_license(word, translations, blacklist)

        for sub in ["Summary: ", "abstract: "]:
            if line.startswith(sub):
                assign_summary(line[len(sub):].strip(), 4)

        pkginfo += line if section else ""
        if line.startswith("Description:"):
            section = True

    if len(pkginfo) > 10:
        assign_description(pkginfo, 4)


def summary_from_pkgconfig(pkgfile, package):
    """Parse pkgconfig files for Description: lines."""
    try:
        with util.open_auto(pkgfile, "r") as pkgfd:
            lines = pkgfd.readlines()
    except FileNotFoundError:
        return

    score = 3 if package + ".pc" in pkgfile else 2
    for line in lines:
        if line.startswith("Description:"):
            assign_summary(line[13:], score)
            # Score will not increase, stop trying
            break


def summary_from_R(pkgfile):
    """Parse DESCRIPTION file for Title: lines."""
    try:
        with util.open_auto(pkgfile, "r") as pkgfd:
            lines = pkgfd.readlines()
    except FileNotFoundError:
        return

    for line in lines:
        if line.startswith("Title:"):
            assign_summary(line[7:], 3)
            # Score will not increase, stop trying
            break


def skipline(line):
    """Skip boilerplate readme lines."""
    if line.endswith("introduction"):
        return True

    skips = ["Copyright",
             "Free Software Foundation, Inc.",
             "Copying and distribution of",
             "are permitted in any",
             "notice and this notice",
             "README",
             "-*-"]
    return any(s in line for s in skips)


def description_from_readme(readmefile):
    """Try to pick the first paragraph or two from the readme file."""
    try:
        with util.open_auto(readmefile, "r") as readmefd:
            lines = readmefd.readlines()
    except FileNotFoundError:
        return

    section = False
    desc = ""
    for line in lines:
        if section and len(line) < 2 and len(desc) > 80:
            # If we are in a section and encounter a new line, break as long as
            # we already have a description > 80 characters.
            break
        if not section and len(line) > 2:
            # Found the first paragraph hopefully
            section = True
        if section:
            # Copy all non-empty lines into the description
            if skipline(line) == 0 and len(line) > 2:
                desc = desc + line.strip() + "\n"

    score = 1.5 if readmefile.lower().endswith("readme") else 1
    assign_description(desc, score)


def scan_for_description(package, dirn, translations, blacklist):
    """Scan the project directory for things we can use to guess a description and summary."""
    test_pat = re.compile(r"tests?")
    dirpath_seen = ""
    for dirpath, dirnames, files in os.walk(dirn):
        if dirpath_seen != dirpath:
            dirpath_seen = dirpath
            dirnames[:] = [d for d in dirnames if not re.match(test_pat, d)]
        for name in files:
            if name.lower().endswith(".pdf"):
                continue
            if name.lower().endswith(".spec"):
                description_from_spec(os.path.join(dirpath, name), translations, blacklist)
            if name.lower().endswith("pkg-info"):
                description_from_pkginfo(os.path.join(dirpath, name), translations, blacklist)
            if name.lower().endswith("meta.yml"):
                description_from_pkginfo(os.path.join(dirpath, name), translations, blacklist)
            if name.lower().endswith("description"):
                description_from_pkginfo(os.path.join(dirpath, name), translations, blacklist)
            if name.lower().endswith(".pc"):
                summary_from_pkgconfig(os.path.join(dirpath, name), package)
            if name.startswith("DESCRIPTION"):
                summary_from_R(os.path.join(dirpath, name))
            if name.lower().endswith(".pc.in"):
                summary_from_pkgconfig(os.path.join(dirpath, name), package)
            if name.lower().startswith("readme"):
                description_from_readme(os.path.join(dirpath, name))

    print("Summary     :", default_summary.strip())


def load_specfile(specfile, description, summary):
    """Load specfile with parse results."""
    if description:
        specfile.default_desc = "\n".join(description)
    else:
        specfile.default_desc = default_description
    if summary:
        specfile.default_sum = summary[0]
    else:
        specfile.default_sum = default_summary
