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

import os
import subprocess

import build
import buildpattern
import config
import tarball
from util import call, write_out


def commit_to_git(path):
    """Update package's git tree for autospec managed changes."""
    call("git init", stdout=subprocess.DEVNULL, cwd=path)

    # This config is used for setting the remote URI, so it is optional.
    if config.git_uri:
        try:
            call("git config --get remote.origin.url", cwd=path)
        except subprocess.CalledProcessError:
            upstream_uri = config.git_uri % {'NAME': tarball.name}
            call("git remote add origin %s" % upstream_uri, cwd=path)

    for config_file in config.config_files:
        call("git add %s" % config_file, cwd=path, check=False)
    for unit in buildpattern.sources["unit"]:
        call("git add %s" % unit, cwd=path)
    call("git add Makefile", cwd=path)
    call("git add upstream", cwd=path)
    call("bash -c 'shopt -s failglob; git add *.spec'", cwd=path)
    call("git add %s.tmpfiles" % tarball.name, check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add prep_prepend", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add build_prepend", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add make_prepend", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add install_prepend", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add install_append", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add series", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add -f *.asc'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add -f *.sig'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add -f *.sha256'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add -f *.sign'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add -f *.pkey'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add configure", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add configure32", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add configure64", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add configure_avx2", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add configure_avx512", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add make_check_command", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add *.patch'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("bash -c 'shopt -s failglob; git add *.nopatch'", check=False, stderr=subprocess.DEVNULL, cwd=path)
    for item in config.transforms.values():
        call("git add {}".format(item), check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add release", cwd=path)
    call("git add symbols", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add symbols32", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add used_libs", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add used_libs32", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add testresults", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add profile_payload", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add options.conf", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add configure_misses", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add whatrequires", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add description", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git add attrs", check=False, stderr=subprocess.DEVNULL, cwd=path)

    # remove deprecated config files
    call("git rm make_install_append", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm prep_append", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm use_clang", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm use_lto", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm use_avx2", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm fast-math", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm broken_c++", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm skip_test_suite", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm optimize_size", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm asneeded", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm broken_parallel_build", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm pgo", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm unit_tests_must_pass", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm funroll-loops", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm keepstatic", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm allow_test_failures", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm no_autostart", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm insecure_build", check=False, stderr=subprocess.DEVNULL, cwd=path)
    call("git rm conservative_flags", check=False, stderr=subprocess.DEVNULL, cwd=path)

    # add a gitignore
    ignorelist = [
        ".*~",
        "*~",
        "*.info",
        "*.mod",
        "*.swp",
        ".repo-index",
        "*.log",
        "build.log.round*",
        "*.tar.*",
        "*.tgz",
        "!*.tar.*.*",
        "*.zip",
        "*.jar",
        "*.pom",
        "*.xml",
        "commitmsg",
        "results/",
        "rpms/",
        "for-review.txt",
        ""
    ]
    write_out(os.path.join(path, '.gitignore'), '\n'.join(ignorelist))
    call("git add .gitignore", check=False, stderr=subprocess.DEVNULL, cwd=path)

    if build.success == 0:
        return

    call("git commit -a -F commitmsg ", cwd=path)
    call("rm commitmsg", cwd=path)
