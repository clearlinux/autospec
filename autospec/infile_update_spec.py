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
import os
from util import print_infile


cmd_mappings = {
    "do_configure": "configure",
    "do_configure_prepend": "configure",
    "do_configure_append": "configure",
    "EXTRA_OECONF": "configure",
    "do_install": "install_append",
    "do_install_append": "install_append",
    "do_install_prepend": "install_prepend"
}


def update_summary(bb_dict, specfile):
    """
    Updates the default summary to the summary or description scraped from
    the bitbake file. The bitbake "SUMMARY" variable is first priority,
    then the "DESCRIPTION" variable. If neither exist, set set it back to the
    specfile value.
    """
    specfile.default_sum = bb_dict.get("SUMMARY") or \
        bb_dict.get("DESCRIPTION") or specfile.default_sum

    if specfile.default_sum == bb_dict.get("SUMMARY") or \
            specfile.default_sum == bb_dict.get("DESCRIPTION"):
        print_infile("Summary updated: {}".format(specfile.default_sum))


def update_licenses(bb_dict, specfile):
    """
    The specfile contains a list of licenses for a package, if the bitbake
    license is not included in that list, add it.
    """
    if "LICENSE" in bb_dict:
        if bb_dict.get("LICENSE").lower() not in [l.lower() for l in specfile.licenses]:
            specfile.licenses.append(bb_dict.get("LICENSE"))
            print_infile("License added: {}".format(bb_dict.get("LICENSE")))


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
            print_infile("Build dependency added: {}".format(dep))


def write_cmd_files(bb_dict, dirname):
    """
    Append "do_" task commands that are scraped from the bitbake file(s). Some
    of these commands have append/prepend. These operations are performed
    prior to being added to the dict. This function appends all commands to
    as comments to their mapped file within the target directory.
    """
    for cmd_name, cmd in bb_dict.items():
        if cmd_name.startswith("do_"):
            filename = os.path.join(dirname, cmd_mappings.get(cmd_name))
            with open(filename, 'a') as cmdfp:
                cmdfp.write("# Infile parser added the following lines:\n")
                cmdfp.write("\n".join(cmd) + "\n")
            print_infile("Suggestions added to the {} file".format(
                cmd_mappings.get(cmd_name)))


def update_specfile(specfile, bb_dict, dirname):

    update_summary(bb_dict, specfile)
    update_licenses(bb_dict, specfile)
    update_build_deps(bb_dict, specfile)
    write_cmd_files(bb_dict, dirname)

    return specfile
