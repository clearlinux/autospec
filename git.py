#!/bin/true
#
# git.py - part of autospec
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
# Commit to git
#

import subprocess

import build
import buildpattern
import tarball
import test
import docs
from util import call
import config


def commit_to_git(path):

    if not config.git_uri:
        return

    call("git init", stdout=subprocess.DEVNULL, cwd=path)

    try:
        call("git config --get remote.origin.url", cwd=path)
    except subprocess.CalledProcessError:
        upstream_uri = config.git_uri % {'NAME': tarball.name}
        call("git remote add origin %s" % upstream_uri, cwd=path)

    for config_file in config.config_files:
        call("git add %s" % config_file, cwd=path)
    for unit in buildpattern.sources["unit"]:
        call("git add %s" % unit, cwd=path)
    call("git add Makefile", cwd=path)
    call("git add upstream", cwd=path)
    call("git add *.spec", cwd=path)
    if test.unit_pass_written:
        call("git add unit_tests_must_pass", cwd=path)
    call("git add %s.tmpfiles" % tarball.name, check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add make_install_append", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add funroll-loops", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add series", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add make_check_command", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add keepstatic", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add *.patch", check=False, stderr=subprocess.DEVNULL, cwd=path)
    for item in docs.transforms.values():
        call("git add {}".format(item), check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add release", cwd=path)

    if build.success == 0:
        return

    if config.old_version != None and config.old_version != tarball.version:
        call("git commit -a -m \"Autospec creation for version update from " + config.old_version + " to " + tarball.version + "\"", cwd=path)
    else:
        call("git commit -a -m \"Autospec creation for version " + tarball.version + "\"", cwd=path)
