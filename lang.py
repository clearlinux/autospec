#!/bin/true
#
# lang.py - part of autospec
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
# Parse config files
#

import files


locales = []


def add_lang(lang):
    global locales
    if lang in locales:
        return
    locales.append(lang)
    print("  New locale:", lang)

    if "locales" in files.packages:
        return
    files.packages["locales"] = []


def write_find_lang(file):
    for lang in locales:
        file.write("%find_lang " + lang + "\n")


def write_lang_files(file):
    global locales
    if len(locales) == 0:
        return
    file.write("\n%files locales ")
    for lang in locales:
        file.write("-f " + lang + ".lang ")
    file.write("\n%defattr(-,root,root,-)\n\n")
