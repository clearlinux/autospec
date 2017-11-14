#!/usr/bin/true
#
# infile_parser.py - part of autospec
# Copyright (C) 2017 Intel Corporation
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

import re

def update_summary(bb_dict, specfile):
    """
    Updates the default summary to the summary or description scraped from
    the bitbake file. The bitbake "SUMMARY" variable is first priority,
    then the "DESCRIPTION" variable. If neither exist, set set it back to the
    specfile value.
    """
    specfile.default_sum = bb_dict.get("SUMMARY") or \
        bb_dict.get("DESCRIPTION") or specfile.default_sum


def update_licenses(bb_dict, specfile):
    """
    The specfile contains a list of licenses for a package, if the bitbake
    license is not included in that list, add it.
    """
    if "LICENSE" in bb_dict:
        if bb_dict.get("LICENSE").lower() not in [l.lower() for l in specfile.licenses]:
            specfile.licenses.append(bb_dict.get("LICENSE"))


def update_build_deps(bb_dict, specfile):
    """
    Add build dependencies to the buildreq set, if the bb_dict scraped build
    time dependencies.
    """
    if bb_dict.get('DEPENDS'):
        for dep in bb_dict.get('DEPENDS').split():
            dep = re.match(r"(\$\{PYTHON_PN\}\-)?([a-zA-Z0-9\-]+)", dep).group(2)
            if dep.endswith('-native'):
                dep = dep[:-7]

            specfile.buildreqs.add(dep)


def update_specfile(specfile, bb_dict):

    update_summary(bb_dict, specfile)
    update_licenses(bb_dict, specfile)
    update_build_deps(bb_dict, specfile)

    return specfile
