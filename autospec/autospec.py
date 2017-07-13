#!/usr/bin/python3
#
# autospec.py - part of autospec
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

import argparse
import sys
import os
import re
import types
import tempfile

import build
import buildpattern
import buildreq
import config
import files
import git
import license
import specdescription
import tarball
import test
import commitmessage
import pkg_integrity
import specfiles

from tarball import name
from util import _file_write, print_fatal, binary_in_path
from abireport import examine_abi
from logcheck import logcheck

sys.path.append(os.path.dirname(__file__))


def add_sources(download_path, archives):
    for file in os.listdir(download_path):
        if re.search(".*\.(mount|service|socket|target|timer)$", file):
            buildpattern.sources["unit"].append(file)
    buildpattern.sources["unit"].sort()
    #
    # systemd-tmpfiles uses the configuration files from
    # /usr/lib/tmpfiles.d/ directories to describe the creation,
    # cleaning and removal of volatile and temporary files and
    # directories which usually reside in directories such as
    # /run or /tmp.
    #
    if os.path.exists(os.path.normpath(build.download_path +
                                       "/{0}.tmpfiles".format(tarball.name))):
        buildpattern.sources["tmpfile"].append(
            "{}.tmpfiles".format(tarball.name))
    if tarball.gcov_file:
        buildpattern.sources["gcov"].append(tarball.gcov_file)
    for archive, destination in zip(archives[::2], archives[1::2]):
        buildpattern.sources["archive"].append(archive)
        buildpattern.archive_details[archive + "destination"] = destination


def check_requirements(useGit):
    """ Ensure all requirements are satisfied before continuing """
    required_bins = ["mock", "rpm2cpio", "nm", "objdump", "cpio", "readelf"]

    if useGit:
        required_bins.append("git")

    missing = [x for x in required_bins if not binary_in_path(x)]

    if len(missing) > 0:
        print_fatal("Required programs are not installed: {}".format(", ".join(missing)))
        sys.exit(1)


def load_specfile(specfile):
    """
    Gather all information from static analysis into Specfile instance
    """
    config.load_specfile(specfile)
    tarball.load_specfile(specfile)
    specdescription.load_specfile(specfile)
    license.load_specfile(specfile)
    buildreq.load_specfile(specfile)
    buildpattern.load_specfile(specfile)
    test.load_specfile(specfile)


def main(workingdir):
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--skip-git",
                        action="store_false", dest="git", default=True,
                        help="Don't commit result to git")
    parser.add_argument("-n", "--name", action="store", dest="name", default="",
                        help="Override the package name")
    parser.add_argument("-v", "--version", action="store", dest="version", default="",
                        help="Override the package version")
    parser.add_argument("url",
                        help="tarball URL (e.g."
                             " http://example.com/downloads/mytar.tar.gz)")
    parser.add_argument('-a', "--archives", action="store",
                        dest="archives", default=[], nargs='*',
                        help="tarball URLs for additional source archives and"
                        " a location for the sources to be extacted to (e.g."
                        " http://example.com/downloads/dependency.tar.gz"
                        " /directory/relative/to/extract/root )")
    parser.add_argument("-l", "--license-only",
                        action="store_true", dest="license_only",
                        default=False, help="Only scan for license files")
    parser.add_argument("-b", "--skip-bump", dest="bump",
                        action="store_false", default=True,
                        help="Don't bump release number")
    parser.add_argument("-c", "--config", dest="config", action="store",
                        default="/usr/share/defaults/autospec/autospec.conf",
                        help="Set configuration file to use")
    parser.add_argument("-t", "--target", dest="target", action="store",
                        default=None,
                        help="Target location to create or reuse")
    parser.add_argument("-i", "--integrity", action="store_true",
                        default=False,
                        help="Search for package signature from source URL and attempt to verify package")
    parser.add_argument("--non_interactive", action="store_true",
                        default=False,
                        help="Disable interactive mode for package verification")
    args = parser.parse_args()
    if len(args.archives) % 2 != 0:
        parser.error(argparse.ArgumentTypeError(
                     "-a/--archives requires an even number of arguments"))

    check_requirements(args.git)
    build.setup_workingdir(workingdir)

    #
    # First, download the tarball, extract it and then do a set
    # of static analysis on the content of the tarball.
    #
    filemanager = files.FileManager()
    tarball.process(args.url, args.name, args.version, args.target, args.archives, filemanager)
    _dir = tarball.path

    if args.license_only:
        try:
            with open(os.path.join(build.download_path,
                      tarball.name + ".license"), "r") as dotlic:
                for word in dotlic.read().split():
                    if word.find(":") < 0:
                        license.add_license(word)
        except:
            pass
        license.scan_for_licenses(_dir)
        exit(0)

    config.setup_patterns()
    config.config_file = args.config
    config.parse_config_files(build.download_path, args.bump, filemanager)
    config.parse_existing_spec(build.download_path, tarball.name)

    buildreq.set_build_req()
    buildreq.scan_for_configure(_dir)
    specdescription.scan_for_description(name, _dir)
    license.scan_for_licenses(_dir)
    commitmessage.scan_for_changes(build.download_path, _dir)
    add_sources(build.download_path, args.archives)
    test.scan_for_tests(_dir)

    #
    # Now, we have enough to write out a specfile, and try to build it.
    # We will then analyze the build result and learn information until the
    # package builds
    #
    specfile = specfiles.Specfile(tarball.url, tarball.version, tarball.name, tarball.release)
    filemanager.load_specfile(specfile)
    load_specfile(specfile)

    print("\n")

    if args.integrity == True:
        interactive_mode = not args.non_interactive
        pkg_integrity.check(args.url, build.download_path, interactive=interactive_mode)
        pkg_integrity.load_specfile(specfile)

    specfile.write_spec(build.download_path)
    while 1:
        build.package(filemanager)
        filemanager.load_specfile(specfile)
        specfile.write_spec(build.download_path)
        filemanager.newfiles_printed = 0
        if build.round > 20 or build.must_restart == 0:
            break

    test.check_regression(build.download_path)

    if build.success == 0:
        print_fatal("Build failed, aborting")
        sys.exit(1)
    elif os.path.isfile("README.clear"):
        try:
            print("\nREADME.clear CONTENTS")
            print("*********************")
            with open("README.clear", "r") as readme_f:
                print(readme_f.read())

            print("*********************\n")
        except:
            pass

    examine_abi(build.download_path)

    with open(build.download_path + "/release", "w") as fp:
        fp.write(tarball.release + "\n")

    # record logcheck output
    logcheck(build.download_path)

    commitmessage.guess_commit_message()

    if args.git:
        git.commit_to_git(build.download_path)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as workingdir:
        main(workingdir)
