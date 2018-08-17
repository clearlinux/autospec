#!/bin/true
#
# files.py - part of autospec
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
# %files section management
#

import build
import tarball
import config
import re
import os
import util
import sys
from collections import OrderedDict
# todo package splits


class FileManager(object):
    """
    Files class handles spec file %files section management
    """
    def __init__(self):
        self.packages = OrderedDict()  # per sub-package file list for spec purposes
        self.files = []  # global file list to weed out dupes
        self.files_blacklist = set()
        self.excludes = []
        self.extras = []
        self.dev_extras = []
        self.setuid = []
        self.attrs = []
        self.locales = []
        self.newfiles_printed = False
        # Do we need ALL include files in a dev package, even if they're not in
        # /usr/include?  Yes in the general case, but for example for R
        # packages, the answer is No.
        self.want_dev_split = True


    def compile_patterns(self):
        def make_pattern(file, package="main"):
            if file.startswith("/") or file.startswith('%'):
                return (re.compile(re.escape(file)), package)
            if file.startswith("^"):
                return (re.compile(file), package)
            util.print_fatal("Line in {} pattern must be absolute or start with ^: {}"
                             .format(package, file))
            sys.exit(1)

        # Prepare compiled patterns
        self.patterns = []

        # Start with the rules for manual config
        for file in self.excludes:
            self.patterns.append((make_pattern(file, "excludes")[0], "main", "%exclude "))
        for file in self.extras:
            self.patterns.append(make_pattern(file, "extras"))
        for file in self.dev_extras:
            self.patterns.append(make_pattern(file, "dev"))
        for file in self.setuid:
            self.patterns.append((*make_pattern(file, "setuid"), "%attr(4755, root, root) "))
        for line in self.attrs:
            attr = re.split(r'\(|\)|,', line)
            attr = [a.strip() for a in attr]
            file = attr.pop()
            prefix = "{0}({1}) ".format(attr[0], ','.join(attr[1:3]))
            self.patterns.append((re.compile(re.escape(file)), "attrs", prefix))

        # if configured to do so, add .so files to the lib package instead of
        # the dev package. THis is useful for packages with a plugin
        # architecture like elfutils and mesa.
        so_dest = 'lib' if config.config_opts.get('so_to_lib') else 'dev'
        patterns = [
            # Patterns for matching files, format is a tuple as follows:
            # (<raw pattern>, <package>, <optional prefix>)
            # order matters!
            (r"^/usr/share/doc/.*/.*COPYING.*", "license"),
            (r"^/usr/share/doc/.*/.*COPYRIGHT.*", "license"),
            (r"^/usr/share/doc/.*/.*GPL.*", "license"),
            (r"^/usr/share/doc/.*/.*MIT.*", "license"),
            (r"^/usr/share/doc/.*/.*LICENSE.*", "license"),
            (r"^/usr/share/doc/.*/.*license.*", "license"),
            (r"^/usr/share/man/man2", "dev"),
            (r"^/usr/share/man/man3", "dev"),
            (r"^/usr/share/man/", "man"),
            (r"^/usr/share/omf", "main"),
            (r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib"),
            (r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib"),
            (r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib32"),
            (r"^/usr/lib64/lib(asm|dw|elf)-[0-9.]+\.so", "lib"),
            (r"^/usr/lib32/lib(asm|dw|elf)-[0-9.]+\.so", "lib32"),
            (r"^/usr/lib64/haswell/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib"),
            (r"^/usr/lib64/gobject-introspection/", "lib"),
            (r"^/usr/libexec/", "bin"),
            (r"^/usr/bin/", "bin"),
            (r"^/usr/sbin/", "bin"),
            (r"^/sbin/", "bin"),
            (r"^/bin/", "bin"),
            (r"^/usr/lib/python3.*/", "python3"),
            (r"^/usr/lib/python2.*/", "legacypython"),
            (r"^/usr/lib64/python.*/", "python"),
            (r"^/usr/share/gir-[0-9\.]+/[a-zA-Z0-9\.\_\-\+]*\.gir", "data"),
            (r"^/usr/share/girepository-1\.0/.*\.typelib\$", "data"),
            (r"^/usr/share/cmake/", "data"),
            (r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.hxx", "dev"),
            (r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.hpp", "dev"),
            (r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.h\+\+", "dev"),
            (r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.h", "dev"),
            (r"^/usr/include/", "dev"),
            (r"^/usr/lib64/girepository-1.0/", "data"),
            (r"^/usr/share/cmake/", "dev"),
            (r"^/usr/lib/cmake/", "dev"),
            (r"^/usr/lib64/cmake/", "dev"),
            (r"^/usr/lib32/cmake/", "dev32"),
            (r"^/usr/lib/qt5/mkspecs/", "dev"),
            (r"^/usr/lib64/qt5/mkspecs/", "dev"),
            (r"^/usr/lib32/qt5/mkspecs/", "dev32"),
            (r"^/usr/lib/qt5/", "lib"),
            (r"^/usr/lib64/qt5/", "lib"),
            (r"^/usr/lib32/qt5/", "lib32"),
            (r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.so$", so_dest),
            (r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.so$", so_dest),
            (r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.so$", so_dest + '32'),
            (r"^/usr/lib64/haswell/[a-zA-Z0-9\.\_\-\+]*\.so$", so_dest),
            (r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev"),
            (r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev"),
            (r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev32"),
            (r"^/usr/lib/haswell/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev"),
            (r"^/usr/lib64/haswell/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev"),
            (r"^/usr/lib32/haswell/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev32"),
            (r"^/usr/lib/pkgconfig/[a-zA-Z0-9\.\_\-\+]*\.pc$", "dev"),
            (r"^/usr/lib64/pkgconfig/[a-zA-Z0-9\.\_\-\+]*\.pc$", "dev"),
            (r"^/usr/lib32/pkgconfig/[a-zA-Z0-9\.\_\-\+]*\.pc$", "dev32"),
            (r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.la$", "dev"),
            (r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.la$", "dev"),
            (r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.la$", "dev32"),
            (r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.prl$", "dev"),
            (r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.prl$", "dev"),
            (r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.prl$", "dev32"),
            (r"^/usr/share/aclocal/[a-zA-Z0-9\.\_\-\+]*\.ac$", "dev"),
            (r"^/usr/share/aclocal/[a-zA-Z0-9\.\_\-\+]*\.m4$", "dev"),
            (r"^/usr/share/aclocal-1.[0-9]+/[a-zA-Z0-9\.\_\-\+]*\.ac$", "dev"),
            (r"^/usr/share/aclocal-1.[0-9]+/[a-zA-Z0-9\.\_\-\+]*\.m4$", "dev"),
            (r"^/usr/share/doc/" + re.escape(tarball.name) + "/", "doc", "%doc "),
            (r"^/usr/share/doc/", "doc"),
            (r"^/usr/share/gtk-doc/html", "doc"),
            (r"^/usr/share/help", "doc"),
            (r"^/usr/share/info/", "doc", "%doc "),
            (r"^/etc/systemd/system/.*\.wants/", "active-units"),
            # now a set of catch-all rules
            (r"^/etc/", "config", "%config "),
            (r"^/usr/etc/", "config", "%config "),
            (r"^/lib/systemd", "config"),
            (r"^/usr/lib/systemd", "config"),
            (r"^/usr/lib/udev/rules.d", "config"),
            (r"^/usr/lib/modules-load.d", "config"),
            (r"^/usr/lib/tmpfiles.d", "config"),
            (r"^/usr/lib/sysusers.d", "config"),
            (r"^/usr/lib/sysctl.d", "config"),
            (r"^/usr/share/", "data"),
            # finally move any dynamically loadable plugins (not
            # perl/python/ruby/etc.. extensions) into lib package
            (r"^/usr/lib/.*/[a-zA-Z0-9\.\_\-\+]*\.so", "lib"),
            (r"^/usr/lib64/.*/[a-zA-Z0-9\.\_\-\+]*\.so", "lib"),
            (r"^/usr/lib32/.*/[a-zA-Z0-9\.\_\-\+]*\.so", "lib32"),
            # locale data gets picked up via file_is_locale
            (r"^/usr/share/locale/", "ignore")]

        for p in patterns:
            self.patterns.append((re.compile(p[0]), ) + p[1:])


    def push_package_file(self, filename, package="main"):
        """
        Add found %file and indicate to build module that we must restart the
        build.
        """
        if package not in self.packages:
            self.packages[package] = set()

        self.packages[package].add(filename)
        build.must_restart += 1
        if not self.newfiles_printed:
            print("  New %files content found")
            self.newfiles_printed = True

    def compat_exclude(self, filename):
        """
        Exclude non-library files if the package is for compatability.
        """
        if not config.config_opts.get("compat"):
            return False

        patterns = [
            re.compile(r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.so\."),
            re.compile(r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.so\."),
            re.compile(r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.so\."),
            re.compile(r"^/usr/lib64/lib(asm|dw|elf)-[0-9.]+\.so"),
            re.compile(r"^/usr/lib32/lib(asm|dw|elf)-[0-9.]+\.so"),
            re.compile(r"^/usr/lib64/haswell/[a-zA-Z0-9\.\_\-\+]*\.so\.")]

        exclude = True
        for pat in patterns:
            if pat.search(filename):
                exclude = False
                break

        return exclude

    def file_pat_match(self, filename, pat, package, prefix=""):
        """
        Search for pattern in filename, if pattern matches push package file.
        If that file is also in the excludes list, prepend "%exclude " before
        pushing the filename.
        Returns True if a file was pushed, False otherwise.
        """
        replacement = prefix + filename

        match = pat.search(filename)
        if match:
            if filename in self.excludes or self.compat_exclude(filename):
                self.push_package_file("%exclude " + filename, package)
                return True

            self.push_package_file(replacement, package)
            return True
        else:
            return False

    def file_is_locale(self, filename):
        """
        If a file is a locale, appends to self.locales and returns True,
        returns False otherwise
        """
        pat = re.compile(r"^/usr/share/locale/.*/(.*)\.mo")
        match = pat.search(filename)
        if match:
            lang = match.group(1)
            if lang not in self.locales:
                self.locales.append(lang)
                print("  New locale:", lang)
                if "locales" not in self.packages:
                    self.packages["locales"] = set()

            return True
        else:
            return False

    def _clean_dirs(self, root, files):
        """
        Do the work to remove the directories from the files list
        """
        res = set()
        removed = False

        directive_re = re.compile("(%\w+(\([^\)]*\))?\s+)(.*)")
        for f in files:
            # skip the files with directives at the beginning, including %doc
            # and %dir directives.
            # autospec does not currently support adding empty directories to
            # the file list by prefixing "%dir". Regardless, skip these entries
            # because if they exist at this point it is intentional (i.e.
            # support was added).
            if directive_re.match(f):
                res.add(f)
                continue

            path = os.path.join(root, f.lstrip("/"))
            if os.path.isdir(path) and not os.path.islink(path):
                util.print_warning("Removing directory {} from file list".format(f))
                self.files_blacklist.add(f)
                removed = True
            else:
                res.add(f)

        return (res, removed)

    def clean_directories(self, root):
        """
        Remove directories from file list
        """
        removed = False
        for pkg in self.packages:
            self.packages[pkg], _rem = self._clean_dirs(root, self.packages[pkg])
            if _rem:
                removed = True

        return removed

    def push_file(self, filename):
        """
        Perform a number of checks against the filename and push the filename
        if appropriate.
        """
        if filename in self.files or filename in self.files_blacklist:
            return

        self.files.append(filename)
        if self.file_is_locale(filename):
            return

        # autostart
        part = re.compile(r"^/usr/lib/systemd/system/.+\.target\.wants/.+")
        if part.search(filename) and 'update-triggers.target.wants' not in filename:
            self.push_package_file(filename, "autostart")
            self.push_package_file("%exclude " + filename)

        if filename in self.attrs:
            newfn = "{0}({1}) {2}".format(self.attrs[filename][0],
                                          ','.join(self.attrs[filename][1:3]),
                                          filename)
            self.push_package_file(newfn, "attr")
            self.push_package_file("%exclude " + filename)
            return

        if self.want_dev_split and self.file_pat_match(filename, re.compile(r"^/usr/.*/include/.*\.h$"), "dev"):
            return

        for pat_args in self.patterns:
            if self.file_pat_match(filename, *pat_args):
                return

        # Everything else goes to the main package
        self.push_package_file(filename)

    def remove_file(self, filename):
        """
        Remove filename from local file list
        """
        hit = False

        if filename in self.files:
            self.files.remove(filename)
            print("File no longer present: {}".format(filename))
            hit = True
        for pkg in self.packages:
            if filename in self.packages[pkg]:
                self.packages[pkg].remove(filename)
                print("File no longer present in {}: {}".format(pkg, filename))
                hit = True
        if hit:
            self.files_blacklist.add(filename)
            build.must_restart += 1

    def load_specfile(self, specfile):
        """
        Load a specfile instance with relevant information to be written to the
        spec file.
        """
        specfile.packages = self.packages
        specfile.excludes = self.excludes
        specfile.locales = self.locales
