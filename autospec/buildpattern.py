#!/bin/true
#
# buildpattern.py - part of autospec
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
# Deduce and emit the patterns for %build
#

default_pattern = "make"
pattern_strength = 0
sources = {"unit": [], "gcov": [], "tmpfile": [], "archive": [], "destination": [], "godep": []}
source_index = {}
archive_details = {}


def set_build_pattern(pattern, strength):
    """Set the global default pattern and pattern strength."""
    global default_pattern
    global pattern_strength
    if strength <= pattern_strength:
        return
    default_pattern = pattern
    pattern_strength = strength


def load_specfile(specfile):
    """Load specfile object with relevant data."""
    specfile.sources = sources
    specfile.default_pattern = default_pattern
    specfile.archive_details = archive_details
