#!/bin/true
#
# util.py - part of autospec
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
import re
import shlex
import subprocess

dictionary_filename = os.path.dirname(__file__) + "/translate.dic"
dictionary = [line.strip() for line in open(dictionary_filename, 'r')]
os_paths = None


def call(command, logfile=None, check=True, **kwargs):
    returncode = 1
    full_args = {
        "args": shlex.split(command),
        "universal_newlines": True,
    }
    full_args.update(kwargs)

    if logfile:
        full_args["stdout"] = open(logfile, "w")
        full_args["stderr"] = subprocess.STDOUT
        returncode = subprocess.call(**full_args)
        full_args["stdout"].close()
    else:
        returncode = subprocess.call(**full_args)

    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, full_args["args"], None)

    return returncode


def _file_write(self, s):
    s = s.strip()
    if not s.endswith("\n"):
        s += "\n"
    self.write(s)


def translate(package):
    global dictionary
    for item in dictionary:
        if item.startswith(package + "="):
            return item.split("=")[1]
    return package


def golang_name(some_str):
    """ get the golang-somesite-project-repo format pkg name"""
    ret = some_str
    pattern = re.compile(r".*(github)\.com/([0-9a-zA-Z_-]+)/([0-9a-zA-Z_-]+)/?")
    match = pattern.search(some_str)
    if match:
        domain = match.group(1).strip()
        project = match.group(2).strip()
        repo = match.group(3).strip()
        ret = "golang-" + domain + "-" + project + "-" + repo
    return ret


def golang_libpath(some_str):
    """ get the import path for golang"""
    ret = ""
    pattern = re.compile(r".*(github\.com/[0-9a-zA-Z_\-]+/[0-9a-zA-Z_\-]+).*")
    match = pattern.search(some_str)
    if match:
        ret = match.group(1).strip()
    return ret


def print_fatal(message):
    print("[\033[1m\033[91mFATAL\033[0m] {}".format(message))


def print_warning(message):
    print("[\033[31;1mWARNING\033[0m] {}".format(message))


def binary_in_path(binary):
    """ Determine if the given binary exists in the provided filesystem paths """
    global os_paths
    if not os_paths:
        os_paths = os.getenv("PATH", default="/usr/bin:/bin").split(os.pathsep)

    for path in os_paths:
        if os.path.exists(os.path.join(path, binary)):
            return True
    return False
