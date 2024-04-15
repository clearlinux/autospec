#!/usr/bin/true
#
# tarball.py - part of autospec
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

import bz2
import configparser
import os
import re
import sys
import tarfile
import zipfile

import download
from util import call, do_regex, get_sha1sum, print_fatal, write_out


class Source():
    """Holds data and methods for source code or archives management."""

    def __init__(self, url, destination, path, pattern=None):
        """Set default values for source file."""
        self.url = url
        self.destination = destination
        self.path = path
        self.pattern = pattern
        self.type = None
        self.prefix = None
        self.subdir = None

        # Extra  compressed archives
        if not self.destination.startswith(':'):
            self.set_type()
            self.set_prefix()

    def set_type(self):
        """Determine compression type."""
        if self.url.lower().endswith(('.zip', 'jar')):
            self.type = 'zip'
        elif self.url.lower().endswith(('.bz2')) and not self.url.lower().endswith(('.tar.bz2')):
            self.type = 'bz2'
        else:
            self.type = 'tar'

    def set_prefix(self):
        """Determine the prefix and subdir if no prefix."""
        prefix_method = getattr(self, 'set_{}_prefix'.format(self.type))
        prefix_method()
        # When there is no prefix, create subdir
        if not self.prefix:
            self.subdir = os.path.splitext(os.path.basename(self.path))[0]

    def set_tar_prefix(self):
        """Determine prefix folder name of tar file."""
        if tarfile.is_tarfile(self.path):
            with tarfile.open(self.path, 'r') as content:
                lines = content.getnames()
                # When tarball is not empty
                if len(lines) == 0:
                    print_fatal("Tar file doesn't appear to have any content")
                    sys.exit(1)
                elif len(lines) > 1:
                    if 'package.xml' in lines and self.pattern in ['phpize']:
                        lines.remove('package.xml')
                    self.prefix = os.path.commonpath(lines)
        else:
            print_fatal("Not a valid tar file.")
            sys.exit(1)

    def set_bz2_prefix(self):
        """No prefix for plain bz2 archives."""

    def set_zip_prefix(self):
        """Determine prefix folder name of zip file."""
        if zipfile.is_zipfile(self.path):
            with zipfile.ZipFile(self.path, 'r') as content:
                lines = content.namelist()
                # When zipfile is not empty
                if len(lines) > 0:
                    self.prefix = os.path.commonpath(lines)
                else:
                    print_fatal("Zip file doesn't appear to have any content")
                    sys.exit(1)
        else:
            print_fatal("Not a valid zip file.")
            sys.exit(1)

    def extract(self, base_path):
        """Prepare extraction path and call specific extraction method."""
        if not self.prefix:
            extraction_path = os.path.join(base_path, self.subdir)
        else:
            extraction_path = base_path

        extract_method = getattr(self, 'extract_{}'.format(self.type))
        extract_method(extraction_path)

    def extract_tar(self, extraction_path):
        """Extract tar in path."""
        with tarfile.open(self.path) as content:
            content.extractall(path=extraction_path)

    def extract_bz2(self, extraction_path):
        """Extract plain bz2 file in path."""
        with bz2.BZ2File(self.path, 'rb') as content:
            data = content.read()
            newfile = self.path.rsplit('/', 1)[1]
            newfile = newfile.rsplit('.bz2', 1)[0]
            with open(os.path.join(extraction_path), mode='wb') as f:
                f.write(data)

    def extract_zip(self, extraction_path):
        """Extract zip in path."""
        with zipfile.ZipFile(self.path, 'r') as content:
            content.extractall(path=extraction_path)


def convert_version(ver_str, name):
    """Remove disallowed characters from the version."""
    # banned substrings. It is better to remove these here instead of filtering
    # them out with expensive regular expressions
    banned_subs = ["x86.64", "source", "src", "all", "bin", "release", "rh",
                   "ga", ".ce", "lcms", "onig", "linux", "gc", "sdk", "orig",
                   "jurko", "%2f", "%2F", "%20", "x265"]

    # package names may be modified in the version string by adding "lib" for
    # example. Remove these from the name before trying to remove the name from
    # the version
    name_mods = ["lib", "core", "pom", "opa-"]

    # enforce lower-case strings to make them easier to standardize
    ver_str = ver_str.lower()
    # remove the package name from the version string
    ver_str = ver_str.replace(name.lower(), '')
    # handle modified name substrings in the version string
    for mod in name_mods:
        ver_str = ver_str.replace(name.replace(mod, ""), "")

    # replace illegal characters
    ver_str = ver_str.strip().replace('-', '.').replace('_', '.')

    # remove banned substrings
    for sub in banned_subs:
        ver_str = ver_str.replace(sub, "")

    # remove consecutive '.' characters
    while ".." in ver_str:
        ver_str = ver_str.replace("..", ".")

    return ver_str.strip(".")


class Content():
    """Detect static information about the project."""

    def __init__(self, url, name, version, archives, config, base_path):
        """Initialize Default content settings."""
        self.name = name
        self.rawname = ""
        self.version = version
        self.release = "1"
        self.url = url
        self.path = ""
        self.tarball_prefix = ""
        self.gcov_file = ""
        self.archives = archives
        self.giturl = ""
        self.repo = ""
        self.domain = ""
        self.prefixes = dict()
        self.config = config
        self.base_path = base_path
        self.autogenerated_tarball = None

    def write_upstream(self, sha, tarfile, mode="w"):
        """Write the upstream hash to the upstream file."""
        write_out(os.path.join(self.config.download_path, "upstream"),
                  os.path.join(sha, tarfile) + "\n", mode=mode)

    def extract_sources(self, main_src, archives_src):
        """Extract sources."""
        full_list_src = [main_src] + archives_src
        for src in full_list_src:
            if src.destination != ':':
                src.extract(self.base_path)

    def check_or_get_file(self, upstream_url, tarfile, mode="w"):
        """Download tarball from url unless it is present locally."""
        tarball_path = self.config.download_path + "/" + tarfile
        if not os.path.isfile(tarball_path):
            download.do_curl(upstream_url, dest=tarball_path, is_fatal=True)
            self.write_upstream(get_sha1sum(tarball_path), tarfile, mode)
        else:
            self.write_upstream(get_sha1sum(tarball_path), tarfile, mode)
        return tarball_path

    def process_main_source(self, url):
        """Download and get important information from main source code."""
        src_path = self.check_or_get_file(url, os.path.basename(url))
        main_src = Source(url, '', src_path, self.config.default_pattern)
        return main_src

    def process_autogenerated_source(self, url):
        """Download any autogenerated source tarball for comparison."""
        autogenerated_src = None
        if url:
            src_path = self.check_or_get_file(url, os.path.basename(url))
            autogenerated_src = Source(url, '../autogenerated-tmp', src_path, self.config.default_pattern)
        return autogenerated_src

    def print_header(self):
        """Print header for autospec run."""
        print("\n")
        print("Processing", self.url)
        print("=" * 105)
        print("Name        :", self.name)
        print("Version     :", self.version)
        print("Prefix      :", self.tarball_prefix)

    def set_giturl_and_domain(self):
        """Set giturl and domain from the config (needs config refactor)."""
        options_path = os.path.join(self.config.download_path, 'options.conf')
        if os.path.exists(options_path):
            config_f = configparser.ConfigParser(interpolation=None)
            config_f.read(options_path)
            if "package" in config_f.sections():
                if "giturl" in config_f["package"]:
                    self.giturl = config_f["package"].get("giturl")
                if "domain" in config_f["package"]:
                    self.domain = config_f["package"].get("domain")

    def name_and_version(self, filemanager):
        """Parse the url for the package name and version."""
        tarfile = os.path.basename(self.url)

        # If both name and version overrides are set via commandline, set the name
        # and version variables to the overrides and bail. If only one override is
        # set, continue to auto detect both name and version since the URL parsing
        # handles both. In this case, wait until the end to perform the override of
        # the one that was set. An extra conditional, that version_arg is a string
        # is added to enable a package to have multiple versions at the same time
        # for some language ecosystems.
        if self.name and self.version:
            # rawname == name in this case
            self.rawname = self.name
            self.version = convert_version(self.version, self.name)
            return

        name = self.name
        self.rawname = self.name
        version = ""
        # it is important for the more specific patterns to come first
        pattern_options = [
            # handle font packages with names ending in -nnndpi
            r"(.*-[0-9]+dpi)[-_]([0-9]+[a-zA-Z0-9\+_\.\-\~]*)\.(tgz|tar|zip)",
            r"(.*?)[-_][vs]?([0-9]+[a-zA-Z0-9\+_\.\-\~]*)\.(tgz|tar|zip)",
        ]
        match = do_regex(pattern_options, tarfile)
        if match:
            name = match.group(1).strip()
            version = convert_version(match.group(2), name)

        # R package
        if "cran.r-project.org" in self.url or "cran.rstudio.com" in self.url and name:
            filemanager.want_dev_split = False
            self.rawname = name
            name = "R-" + name

        if ".cpan.org/" in self.url or ".metacpan.org/" in self.url and name:
            name = "perl-" + name

        if "github.com" in self.url:
            # define regex accepted for valid packages, important for specific
            # patterns to come before general ones
            github_patterns = [r"https?://github.com/(.*)/(.*?)/archive/refs/tags/[vVrR]?(.*)\.tar",
                               r"https?://github.com/(.*)/(.*?)/archive/[v|r]?.*/(.*).tar",
                               r"https?://github.com/(.*)/(.*?)/archive/[-a-zA-Z_]*-(.*).tar",
                               r"https?://github.com/(.*)/(.*?)/archive/[vVrR]?(.*).tar",
                               r"https?://github.com/(.*)/.*-downloads/releases/download/.*?/(.*)-(.*).tar",
                               r"https?://github.com/(.*)/(.*?)/releases/download/(.*)/",
                               r"https?://github.com/(.*)/(.*?)/files/.*?/(.*).tar"]

            match = do_regex(github_patterns, self.url)
            if match:
                self.repo = match.group(2).strip()
                if self.repo not in name:
                    # Only take the repo name as the package name if it's more descriptive
                    name = self.repo
                elif name != self.repo:
                    name = re.sub(r"release-", '', name)
                    name = re.sub(r"\d*$", '', name)
                self.rawname = name
                # Identify the auto-generated tarball URL for comparison
                if "/releases/download/" in self.url:
                    self.autogenerated_tarball = "https://github.com/" + match.group(1).strip() + "/" + self.repo + "/archive/refs/tags/" + match.group(3).strip() + ".tar.gz"
                version = match.group(3).replace(name, '')
                if "/archive/" not in self.url:
                    version = re.sub(r"^[-_.a-zA-Z]+", "", version)
                version = convert_version(version, name)
                if not self.giturl:
                    self.giturl = "https://github.com/" + match.group(1).strip() + "/" + self.repo + ".git"

        # SQLite tarballs use 7 digit versions, e.g 3290000 = 3.29.0, 3081002 = 3.8.10.2
        if "sqlite.org" in self.url:
            major = version[0]
            minor = version[1:3].lstrip("0").zfill(1)
            patch = version[3:5].lstrip("0").zfill(1)
            build = version[5:7].lstrip("0")
            version = major + "." + minor + "." + patch + "." + build
            version = version.strip(".")

        # Construct gitlab giturl for GNOME projects, and update previous giturls
        # that pointed to the GitHub mirror.
        if "download.gnome.org" in self.url:
            if not self.giturl or "github.com/GNOME" in self.giturl or "git.gnome.org" in self.giturl:
                self.giturl = "https://gitlab.gnome.org/GNOME/{}".format(name)

        if "mirrors.kernel.org" in self.url:
            m = re.search(r".*/sourceware/(.*?)/releases/(.*?).tgz", self.url)
            if m:
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)

        if "sourceforge.net" in self.url:
            scf_pats = [r"projects/.*/files/(.*?)/(.*?)/[^-]*(-src)?.tar.gz",
                        r"downloads.sourceforge.net/.*/([a-zA-Z]+)([-0-9\.]*)(-src)?.tar.gz"]
            match = do_regex(scf_pats, self.url)
            if match:
                name = match.group(1).strip()
                version = convert_version(match.group(2), name)

        if "bitbucket.org" in self.url:
            bitbucket_pats = [r"/.*/(.*?)/.*/.*v([-\.0-9a-zA-Z_]*?).(tar|zip)",
                              r"/.*/(.*?)/.*/([-\.0-9a-zA-Z_]*?).(tar|zip)"]

            match = do_regex(bitbucket_pats, self.url)
            if match:
                name = match.group(1).strip()
                version = convert_version(match.group(2), name)

        if "gitlab.com" in self.url:
            # https://gitlab.com/leanlabsio/kanban/-/archive/1.7.1/kanban-1.7.1.tar.gz
            m = re.search(r"gitlab\.com/.*/(.*)/-/archive/(?:VERSION_|[vVrR])?(.*)/", self.url)
            if m:
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)

        if "git.sr.ht" in self.url:
            # https://git.sr.ht/~sircmpwn/scdoc/archive/1.9.4.tar.gz
            m = re.search(r"git\.sr\.ht/.*/(.*)/archive/(.*).tar.gz", self.url)
            if m:
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)

        if "pigeonhole.dovecot.org" in self.url:
            # https://pigeonhole.dovecot.org/releases/2.3/dovecot-2.3-pigeonhole-0.5.20.tar.gz
            if m := re.search(r"pigeonhole\.dovecot\.org/releases/.*/dovecot-[\d\.]+-(\w+)-([\d\.]+)\.[^\d]", self.url):
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)

        if ".ezix.org" in self.url:
            # https://www.ezix.org/software/files/lshw-B.02.19.2.tar.gz
            if m := re.search(r"(\w+)-[A-Z]\.(\d+(?:\.\d+)+)", self.url):
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)

        if self.name and not version:
            # In cases where we have a name but no version
            # use what is after the name.
            # https://invisible-mirror.net/archives/lynx/tarballs/lynx2.8.9rel.1.tar.gz
            postname = tarfile.split(self.name)[-1]
            no_extension = os.path.splitext(postname)[0]
            if no_extension.endswith('.tar'):
                no_extension = os.path.splitext(no_extension)[0]
            version = convert_version(no_extension, self.name)

        # override name and version from commandline
        self.name = self.name if self.name else name
        self.version = self.version if self.version else version

    def set_gcov(self):
        """Set the gcov file name."""
        gcov_path = os.path.join(self.config.download_path, self.name + ".gcov")
        if os.path.isfile(gcov_path):
            self.gcov_file = self.name + ".gcov"

    def process_archives(self):
        """Process extra sources needed by package."""
        src_objects = []

        full_archives = self.archives
        # Download and extract full list
        for arch_url, destination in zip(full_archives[::2], full_archives[1::2]):
            src_path = self.check_or_get_file(arch_url, os.path.basename(arch_url), mode="a")
            # Create source object and extract archive
            archive = Source(arch_url, destination, src_path, self.config.default_pattern)
            # Add archive prefix to list
            self.config.archive_details[arch_url + "prefix"] = archive.prefix
            self.prefixes[arch_url] = archive.prefix
            # Add archive to list
            src_objects.append(archive)

        return src_objects

    def process(self, filemanager):
        """Download and process the tarball."""
        # determine build pattern and build requirements from url
        self.set_giturl_and_domain()
        # determine name and version of package
        self.name_and_version(filemanager)
        # set gcov file information, must be done after name is set since the gcov
        # name is created by adding ".gcov" to the package name (if a gcov file
        # exists)
        self.set_gcov()
        # Download and process main source
        main_src = self.process_main_source(self.url)
        # Store the detected prefix associated with this file
        self.prefixes[self.url] = main_src.prefix
        self.tarball_prefix = main_src.prefix
        # set global path with tarball_prefix
        self.path = os.path.join(self.base_path, self.tarball_prefix)
        # Now that the metadata has been collected print the header
        self.print_header()
        # Download and process extra sources: archives
        archives_src = self.process_archives()
        # Extract all sources
        self.extract_sources(main_src, archives_src)
        # Download and process any auto-generated source-tree archive for comparison
        autogenerated_src = self.process_autogenerated_source(self.autogenerated_tarball)
        # Extract autogenerated source for comparison
        if autogenerated_src:
            autogenerated_src.extract(os.path.join(self.base_path, 'autogenerated-tmp'))
            # Move the autogenerated source to a non-version-named directory for consistent diffs
            call(f"mv autogenerated-tmp/{autogenerated_src.prefix} autogenerated", check=True, cwd=self.base_path)
            call(f"diff -u -r ../autogenerated ./",
                 logfile="archive.diff", check=False, cwd=os.path.join(self.base_path, main_src.prefix))
