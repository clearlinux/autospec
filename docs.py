#!/bin/true
#
# docs.py - part of autospec
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

import os
import shutil
import sys

transforms = {
    'changelog': 'ChangeLog',
    'changes.rst': 'ChangeLog',
    'changes.txt': 'ChangeLog',
    'news': 'NEWS'
}
interests = transforms.keys()


def scan_for_changes(download_path, dir):
    found = []
    for dirpath, dirnames, files in os.walk(dir):

        hits = [x for x in files if x.lower() in interests and x.lower() not in found]
        for item in hits:
            source = os.path.join(dirpath, item)
            target = os.path.join(download_path, transforms[item.lower()])
            try:
                shutil.copy(source, target)
            except Exception as e:
                print("Error copying file: %s", e)
                sys.exit(1)
            found.append(item)
