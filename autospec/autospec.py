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
import configparser
import os
import re
import sys
import tempfile

from abireport import examine_abi
import build
import buildpattern
import buildreq
import check
import commitmessage
import config
import files
import git
import infile_handler
import infile_update_spec
import license
from logcheck import logcheck
import pkg_integrity
import pkg_scan
import specdescription
import specfiles
import tarball
from util import binary_in_path, print_fatal, print_infile, write_out

sys.path.append(os.path.dirname(__file__))


def add_sources(download_path, archives):
    """Add archives to buildpattern sources and archive_details."""
    for srcf in os.listdir(download_path):
        if re.search(r".*\.(mount|service|socket|target|timer|path)$", srcf):
            buildpattern.sources["unit"].append(srcf)
    buildpattern.sources["unit"].sort()
    #
    # systemd-tmpfiles uses the configuration files from
    # /usr/lib/tmpfiles.d/ directories to describe the creation,
    # cleaning and removal of volatile and temporary files and
    # directories which usually reside in directories such as
    # /run or /tmp.
    #
    if os.path.exists(os.path.normpath(
            build.download_path + "/{0}.tmpfiles".format(tarball.name))):
        buildpattern.sources["tmpfile"].append(
            "{}.tmpfiles".format(tarball.name))
    if tarball.gcov_file:
        buildpattern.sources["gcov"].append(tarball.gcov_file)
    buildpattern.sources["archive"] = archives[::2]
    buildpattern.sources["destination"] = archives[1::2]
    for archive, destination in zip(archives[::2], archives[1::2]):
        buildpattern.archive_details[archive + "destination"] = destination


def check_requirements(use_git):
    """Ensure all requirements are satisfied before continuing."""
    required_bins = ["mock", "rpm2cpio", "nm", "objdump", "cpio", "readelf"]

    if use_git:
        required_bins.append("git")

    missing = [x for x in required_bins if not binary_in_path(x)]

    if missing:
        print_fatal("Required programs are not installed: {}".format(", ".join(missing)))
        sys.exit(1)


def load_specfile(specfile):
    """Gather all information from static analysis into Specfile instance."""
    config.load_specfile(specfile)
    tarball.load_specfile(specfile)
    specdescription.load_specfile(specfile)
    license.load_specfile(specfile)
    buildreq.load_specfile(specfile)
    buildpattern.load_specfile(specfile)
    check.load_specfile(specfile)


def read_old_metadata():
    """Handle options.conf providing package, url and archives."""
    if not os.path.exists(os.path.join(os.getcwd(), 'options.conf')):
        return None, None, []

    config_f = configparser.ConfigParser(interpolation=None)
    config_f.read('options.conf')
    if "package" not in config_f.sections():
        return None, None, []

    archives = config_f["package"].get("archives")
    archives = archives.split() if archives else []
    print("ARCHIVES {}".format(archives))

    return (config_f["package"].get("name"),
            config_f["package"].get("url"),
            archives)


def save_mock_logs(path, iteration):
    """Save Mock build logs to <path>/results/round<iteration>-*.log."""
    basedir = os.path.join(path, "results")
    loglist = ["build", "root", "srpm-build", "srpm-root", "mock_srpm", "mock_build"]
    for l in loglist:
        src = "{}/{}.log".format(basedir, l)
        dest = "{}/round{}-{}.log".format(basedir, iteration, l)
        os.rename(src, dest)


def write_prep(workingdir):
    """Write metadata to the local workingdir when --prep-only is used."""
    if config.urlban:
        used_url = re.sub(config.urlban, "localhost", tarball.url)
    else:
        used_url = tarball.url

    print()
    print("Exiting after prep due to --prep-only flag")
    print()
    print("Results under ./workingdir")
    print("Source  (./workingdir/{})".format(tarball.tarball_prefix))
    print("Name    (./workingdir/name)    :", tarball.name)
    print("Version (./workingdir/version) :", tarball.version)
    print("URL     (./workingdir/source0) :", used_url)
    write_out(os.path.join(workingdir, "name"), tarball.name)
    write_out(os.path.join(workingdir, "version"), tarball.version)
    write_out(os.path.join(workingdir, "source0"), used_url)


def main():
    """Entry point for autospec."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--skip-git",
                        action="store_false", dest="git", default=True,
                        help="Don't commit result to git")
    parser.add_argument("-n", "--name", action="store", dest="name", default="",
                        help="Override the package name")
    parser.add_argument("-v", "--version", action="store", dest="version", default="",
                        help="Override the package version")
    parser.add_argument("url", default="", nargs="?",
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
                        help="Search for package signature from source URL and "
                             "attempt to verify package")
    parser.add_argument("-p", "--prep-only", action="store_true",
                        default=False,
                        help="Only perform preparatory work on package")
    parser.add_argument("--non_interactive", action="store_true",
                        default=False,
                        help="Disable interactive mode for package verification")
    parser.add_argument("-C", "--cleanup", dest="cleanup", action="store_true",
                        default=False,
                        help="Clean up mock chroot after building the package")
    parser.add_argument("--infile", action="store", dest="infile", default="",
                        help="type of input file for .specfile creation")
    parser.add_argument("-m", "--mock-config", action="store", default="clear",
                        help="Value to pass with Mock's -r option. Defaults to "
                             "\"clear\", meaning that Mock will use "
                             "/etc/mock/clear.cfg.")
    parser.add_argument("-o", "--mock-opts", action="store", default="",
                        help="Arbitrary options to pass down to mock when "
                        "building a package.")

    args = parser.parse_args()

    name, url, archives = read_old_metadata()
    name = args.name or name
    url = args.url or url
    archives = args.archives or archives
    infile_dict = {}

    if args.infile:
        infile_dict = infile_handler.infile_reader(args.infile, name)
        if not url:
            try:
                url = infile_dict.get('URL')
            except Exception:
                pass
            else:
                print_infile("Source url found: {}".format(url))

        if infile_dict.get("LICENSE"):
            license.add_license(infile_dict.get("LICENSE"))
            print_infile("License added: {}".format(infile_dict.get("LICENSE")))

    if not url:
        parser.error(argparse.ArgumentTypeError(
            "the url argument or options.conf['package']['url'] is required"))

    if len(archives) % 2 != 0:
        parser.error(argparse.ArgumentTypeError(
            "-a/--archives or options.conf['package']['archives'] requires an "
            "even number of arguments"))

    if args.prep_only:
        package(args, url, name, archives, "./workingdir", infile_dict)
    else:
        with tempfile.TemporaryDirectory() as workingdir:
            package(args, url, name, archives, workingdir, infile_dict)


def package(args, url, name, archives, workingdir, infile_dict):
    """Entry point for building a package with autospec."""
    check_requirements(args.git)
    build.setup_workingdir(workingdir)

    #
    # First, download the tarball, extract it and then do a set
    # of static analysis on the content of the tarball.
    #
    filemanager = files.FileManager()
    tarball.process(url, name, args.version, args.target, archives, filemanager)
    config.create_versions(build.download_path, tarball.multi_version)
    _dir = tarball.path

    if args.license_only:
        try:
            with open(os.path.join(build.download_path,
                                   tarball.name + ".license"), "r") as dotlic:
                for word in dotlic.read().split():
                    if ":" not in word:
                        license.add_license(word)
        except Exception:
            pass
        license.scan_for_licenses(_dir)
        exit(0)

    config.setup_patterns()
    config.config_file = args.config
    config.parse_config_files(build.download_path, args.bump, filemanager, tarball.version)
    config.setup_patterns(config.failed_pattern_dir)
    config.parse_existing_spec(build.download_path, tarball.name)

    if args.prep_only:
        write_prep(workingdir)
        exit(0)

    buildreq.set_build_req()
    buildreq.scan_for_configure(_dir)
    specdescription.scan_for_description(tarball.name, _dir)
    license.scan_for_licenses(_dir)
    commitmessage.scan_for_changes(build.download_path, _dir)
    add_sources(build.download_path, archives)
    check.scan_for_tests(_dir)

    #
    # Now, we have enough to write out a specfile, and try to build it.
    # We will then analyze the build result and learn information until the
    # package builds
    #
    specfile = specfiles.Specfile(tarball.url, tarball.version, tarball.name, tarball.release)
    filemanager.load_specfile(specfile)
    load_specfile(specfile)

    #
    # If infile is passed, parse it and overwrite the specfile configurations
    # with the newly found values.
    #
    if args.infile:
        specfile = infile_update_spec.update_specfile(specfile, infile_dict, args.target)
    print("\n")

    if args.integrity:
        interactive_mode = not args.non_interactive
        pkg_integrity.check(url, build.download_path, interactive=interactive_mode)
        pkg_integrity.load_specfile(specfile)

    specfile.write_spec(build.download_path)
    while 1:
        build.package(filemanager, args.mock_config, args.mock_opts, args.cleanup)
        filemanager.load_specfile(specfile)
        specfile.write_spec(build.download_path)
        filemanager.newfiles_printed = 0
        mock_chroot = "/var/lib/mock/clear-{}/root/builddir/build/BUILDROOT/" \
                      "{}-{}-{}.x86_64".format(build.uniqueext,
                                               tarball.name,
                                               tarball.version,
                                               tarball.release)
        if filemanager.clean_directories(mock_chroot):
            # directories added to the blacklist, need to re-run
            build.must_restart += 1

        if build.round > 20 or build.must_restart == 0:
            break

        save_mock_logs(build.download_path, build.round)

    check.check_regression(build.download_path)

    if build.success == 0:
        config.create_buildreq_cache(build.download_path, tarball.version)
        print_fatal("Build failed, aborting")
        sys.exit(1)
    elif os.path.isfile("README.clear"):
        try:
            print("\nREADME.clear CONTENTS")
            print("*********************")
            with open("README.clear", "r") as readme_f:
                print(readme_f.read())

            print("*********************\n")
        except Exception:
            pass

    examine_abi(build.download_path)
    if os.path.exists("/var/lib/rpm"):
        pkg_scan.get_whatrequires(tarball.name)

    write_out(build.download_path + "/release", tarball.release + "\n")

    # record logcheck output
    logcheck(build.download_path)

    commitmessage.guess_commit_message(pkg_integrity.IMPORTED)
    config.create_buildreq_cache(build.download_path, tarball.version)

    if args.git:
        git.commit_to_git(build.download_path)
    else:
        print("To commit your changes, git add the relevant files and "
              "run 'git commit -F commitmsg'")


if __name__ == '__main__':
    main()
