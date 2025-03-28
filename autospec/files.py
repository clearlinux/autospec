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

import os
import re
from collections import OrderedDict

import util


class FileManager(object):
    """Class to handle spec file %files section management."""

    def __init__(self, config, package):
        """Set defaults for FileManager."""
        self.config = config
        self.package = package
        self.packages = OrderedDict()  # per sub-package file list for spec purposes
        self.files = set()  # global file set to weed out dupes
        self.files_blacklist = set()
        self.excludes = []
        self.manual_excludes = []
        self.file_maps = {}  # Filename-to-package mapping
        self.setuid = []
        self.attrs = {}
        self.locales = []
        self.newfiles_printed = False
        # Do we need ALL include files in a dev package, even if they're not in
        # /usr/include?  Yes in the general case, but for example for R
        # packages, the answer is No.
        self.want_dev_split = True
        self.has_banned = False

    @staticmethod
    def banned_path(path):
        """Check if the path is either banned or in a banned subdirectory."""
        banned_paths = [r"/etc.*",
                        r"/opt.*",
                        r"/usr/local.*",
                        r"/usr/etc.*",
                        r"/usr/src.*",
                        r"/var.*"]
        for bpath in banned_paths:
            if re.search(r"^(/V3|/V4|/VA)?" + bpath, path):
                return True
        return False

    def push_package_file(self, filename, package="main"):
        """Add found %file and indicate to build module that we must restart the build."""
        if package not in self.packages:
            self.packages[package] = set()

        if FileManager.banned_path(filename):
            util.print_warning(f"  Content {filename} found in banned path, skipping")
            self.has_banned = True
            return

        # prepend the %attr macro if file defined in 'attrs' control file
        if filename in self.attrs:
            mod = self.attrs[filename][0]
            u = self.attrs[filename][1]
            g = self.attrs[filename][2]
            filename = "%attr({0},{1},{2}) {3}".format(mod, u, g, filename)
        self.packages[package].add(filename)
        self.package.file_restart += 1
        if not self.newfiles_printed:
            print("  New %files content found")
            self.newfiles_printed = True

    def compat_exclude(self, filename):
        """Exclude non-library files if the package is for compatability."""
        if not self.config.config_opts.get("compat"):
            return False

        patterns = [
            r"/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.so\.",
            r"/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.so\.",
            r"/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.so\.",
            r"/usr/lib64/lib(asm|dw|elf)-[0-9.]+\.so",
            r"/usr/lib32/lib(asm|dw|elf)-[0-9.]+\.so",
            r"/usr/lib64/haswell/[a-zA-Z0-9\.\_\-\+]*\.so\.",
            r"/usr/share/package-licenses/"]

        exclude = True
        for pat in patterns:
            pat = re.compile(r"^(/V3|/V4|/VA)?" + pat)
            if pat.search(filename):
                exclude = False
                break

        return exclude

    def file_pat_match(self, filename, pattern, package, replacement=""):
        """Search for pattern in filename.

        Attempt to find pattern in filename, if pattern matches push package file.
        If that file is also in the excludes list, don't push the file.
        Returns True if a file was pushed, False otherwise.
        """
        if not replacement or self.config.config_opts.get("no_glob"):
            replacement = filename

        # compat files should always be excluded
        if self.compat_exclude(filename):
            self.excludes.append(filename)
            return True

        # All patterns at this time and should always be prefixed by '^'
        # but just in case add the following to strip just the '^'
        pattern = pattern if not pattern.startswith('^') else pattern[1:]
        pat = re.compile(r"^(/V3|/V4|/VA)?" + pattern)
        match = pat.search(filename)
        if match:
            if len(match.groups()) > 0 and match.groups()[0] in ['/V3', '/V4', '/VA']:
                norm_filename = filename.removeprefix(match.groups()[0])
                if replacement != filename:
                    replacement = match.groups()[0] + replacement
            else:
                norm_filename = filename
            if norm_filename in self.excludes:
                return True

            self.push_package_file(replacement, package)
            return True

        return False

    def file_is_locale(self, filename):
        """If a file is a locale, appends to self.locales and returns True, returns False otherwise."""
        pat = re.compile(r"^/usr/share/locale/.*/(.*)\.mo")
        match = pat.search(filename)
        if match:
            lang = match.group(1)
            if lang not in self.locales:
                self.locales.append(lang)
                print("  New locale:", lang)
                self.package.must_restart += 1
                if "locales" not in self.packages:
                    self.packages["locales"] = set()

            return True
        else:
            return False

    def _clean_dirs(self, root, files):
        """Do the work to remove the directories from the files list."""
        res = set()
        removed = False

        directive_re = re.compile(r"(%\w+(\([^\)]*\))?\s+)(.*)")
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
        """Remove directories from file list."""
        removed = False
        for pkg in self.packages:
            self.packages[pkg], _rem = self._clean_dirs(root, self.packages[pkg])
            if _rem:
                removed = True

        return removed

    def push_file(self, filename, pkg_name):
        """Perform a number of checks against the filename and push the filename if appropriate."""
        if filename in self.files or filename in self.files_blacklist:
            return

        self.files.add(filename)
        if self.file_is_locale(filename):
            return

        # Explicit file packaging
        for k, v in self.file_maps.items():
            for match_name in v['files']:
                match = re.search(r"^/(V3|V4|VA)", filename)
                norm_filename = filename if not match else filename.removeprefix(match.group())
                if isinstance(match_name, str):
                    if norm_filename == match_name:
                        self.push_package_file(filename, k)
                        return
                elif len('/'.join(match_name)) <= (len(norm_filename) + 1):
                    # the match name may be 1 longer due to a glob
                    # being able to match an empty string
                    if util.globlike_match(norm_filename, match_name):
                        path_prefix = '/' if not match else match.group()
                        self.push_package_file(os.path.join(path_prefix, *match_name), k)
                        return

        if filename in self.setuid:
            if filename in self.attrs:
                mod = self.attrs[filename][0]
                u = self.attrs[filename][1]
                g = self.attrs[filename][2]
                newfn = "%attr({0},{1},{2}) {3}".format(mod, u, g, filename)
            else:
                newfn = "%attr(4755, root, root) " + filename
            self.push_package_file(newfn, "setuid")
            return

        # autostart
        part = re.compile(r"^/usr/lib/systemd/system/.+\.target\.wants/.+")
        if part.search(filename) and 'update-triggers.target.wants' not in filename:
            if filename not in self.excludes:
                self.push_package_file(filename, "autostart")
                self.push_package_file("%exclude " + filename, "services")
                return

        if self.want_dev_split and self.file_pat_match(filename, r"^/usr/.*/include/.*\.h$", "dev"):
            return

        # Exclude Windows executables and DLLs unless otherwise configured
        # Can't just skip them because they could be swept up in a python lib wildcard, for example
        if re.search(r"[^/]+\.(exe|dll)$", filename):
            if self.config.config_opts.get('allow_exe'):
                util.print_warning("Allowing {} because allow_exe is true".format(filename))
            else:
                util.print_warning("Blocking {} because allow_exe is false".format(filename))
                self.excludes.append(filename)
                return

        # if configured to do so, add .so files to the lib package instead of
        # the dev package. THis is useful for packages with a plugin
        # architecture like elfutils and mesa.
        so_dest = 'lib' if self.config.config_opts.get('so_to_lib') else 'dev'
        so_dest_ompi = 'openmpi' if self.config.config_opts.get('so_to_lib') else 'dev'

        patterns = [
            # Patterns for matching files, format is a tuple as follows:
            # (<raw pattern>, <package>, <optional replacement>, <optional prefix>)
            # order matters, first match wins!
            (r"^/usr/share/package-licenses/.{1,}/.{1,}", "license"),
            (r"^/usr/share/man/man2", "dev"),
            (r"^/usr/share/man/man3", "dev"),
            (r"^/usr/share/man/", "man"),
            (r"^/usr/share/pkgconfig/32.*\.pc$", "dev32"),
            (r"^/usr/share/pkgconfig/", "dev"),
            (r"^/usr/share/info/", "info"),
            (r"^/usr/share/abi/", "abi"),
            (r"^/usr/share/qt5/examples/", "examples"),
            (r"^/usr/share/qt6/examples/", "examples"),
            (r"^/usr/share/omf", "main", "/usr/share/omf/*"),
            (r"^/usr/share/installed-tests/", "tests"),
            (r"^/usr/libexec/installed-tests/", "tests"),
            (r"^/usr/lib/rustlib/x86_64-unknown-linux-gnu/lib/[a-zA-Z0-9._+-]+\.rlib", "lib", "/usr/lib/rustlib/x86_64-unknown-linux-gnu/lib/*.rlib"),
            (r"^/usr/lib/rustlib/x86_64-unknown-linux-gnu/analysis/[a-zA-Z0-9._+-]+\.json", "lib", "/usr/lib/rustlib/x86_64-unknown-linux-gnu/analysis/*.json"),
            (r"^/usr/share/clear/optimized-elf/bin", "bin", "/usr/share/clear/optimized-elf/bin*"),
            (r"^/usr/share/clear/optimized-elf/exec", "libexec", "/usr/share/clear/optimized-elf/exec*"),
            (r"^/usr/share/clear/optimized-elf/lib", "lib", "/usr/share/clear/optimized-elf/lib*"),
            (r"^/usr/share/clear/optimized-elf/other", "lib", "/usr/share/clear/optimized-elf/other*"),
            (r"^/usr/share/clear/optimized-elf/test", "tests", "/usr/share/clear/optimized-elf/test*"),
            (r"^/usr/share/clear/optimized-elf/", "lib"),
            (r"^/usr/share/clear/filemap/", "filemap"),
            (r"^/usr/lib64/openmpi/bin/", "openmpi"),
            (r"^/usr/lib64/openmpi/share", "openmpi"),
            (r"^/usr/lib64/openmpi/include/", "dev"),
            (r"^/usr/lib64/openmpi/lib/[a-zA-Z0-9._+-]*\.so$", so_dest_ompi),
            (r"^/usr/lib64/openmpi/lib/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib64/openmpi/lib/[a-zA-Z0-9._+-]*\.so\.", "openmpi"),
            (r"^/usr/lib64/openmpi/lib/python3.*/", "openmpi"),
            (r"^/usr/lib64/openmpi/lib/", "dev"),
            (r"^/usr/lib/[a-zA-Z0-9._+-]*\.so\.", "plugins"),
            (r"^/usr/lib64/[a-zA-Z0-9._+-]*\.so\.", "lib"),
            (r"^/usr/lib32/[a-zA-Z0-9._+-]*\.so\.", "lib32"),
            (r"^/usr/lib64/lib(asm|dw|elf)-[0-9.]+\.so", "lib"),
            (r"^/usr/lib64/libkdeinit5", "lib"),
            (r"^/usr/lib32/lib(asm|dw|elf)-[0-9.]+\.so", "lib32"),
            (r"^/usr/lib64/haswell/[a-zA-Z0-9._+-]*\.so\.", "lib"),
            (r"^/usr/lib64/gobject-introspection/", "lib"),
            (r"^/usr/libexec/", "libexec"),
            (r"^/usr/bin/", "bin"),
            (r"^/usr/sbin/", "bin"),
            (r"^/sbin/", "bin"),
            (r"^/bin/", "bin"),
            (r"^/usr/lib/python3.*/", "python3", "/usr/lib/python3*/*"),
            (r"^/usr/share/gir-[0-9\.]+/[a-zA-Z0-9._+-]*\.gir", "data", "/usr/share/gir-1.0/*.gir"),
            (r"^/usr/share/cmake/", "data", "/usr/share/cmake/*"),
            (r"^/usr/share/cmake-3.1/", "data", "/usr/share/cmake-3.1/*"),
            (r"^/usr/share/cmake-3.7/", "data", "/usr/share/cmake-3.7/*"),
            (r"^/usr/share/cmake-3.8/", "data", "/usr/share/cmake-3.8/*"),
            (r"^/usr/share/cmake-3.6/", "data", "/usr/share/cmake-3.6/*"),
            (r"^/usr/share/girepository-1\.0/.*\.typelib\$", "data", "/usr/share/girepository-1.0/*.typelib"),
            (r"^/usr/include/", "dev"),
            (r"^/usr/lib64/girepository-1.0/", "data"),
            (r"^/usr/share/cmake/", "dev"),
            (r"^/usr/lib/cmake/", "dev"),
            (r"^/usr/lib64/cmake/", "dev"),
            (r"^/usr/lib32/cmake/", "dev32"),
            (r"^/usr/lib/qt5/mkspecs/", "dev"),
            (r"^/usr/lib/qt6/mkspecs/", "dev"),
            (r"^/usr/lib64/qt5/mkspecs/", "dev"),
            (r"^/usr/lib32/qt5/mkspecs/", "dev32"),
            (r"^/usr/lib64/qt6/mkspecs/", "dev"),
            (r"^/usr/lib32/qt6/mkspecs/", "dev32"),
            (r"^/usr/lib/qt5/", "lib"),
            (r"^/usr/lib/qt6/", "lib"),
            (r"^/usr/lib64/qt5/", "lib"),
            (r"^/usr/lib32/qt5/", "lib32"),
            (r"^/usr/lib64/qt6/", "lib"),
            (r"^/usr/lib32/qt6/", "lib32"),
            (r"^/usr/lib/[a-zA-Z0-9._+-]*\.so$", so_dest),
            (r"^/usr/lib64/libkdeinit5_[a-zA-Z0-9._+-]*\.so$", "lib"),
            (r"^/usr/lib32/libkdeinit5_[a-zA-Z0-9._+-]*\.so$", "lib32"),
            (r"^/usr/lib64/[a-zA-Z0-9._+-]*\.so$", so_dest),
            (r"^/usr/lib32/[a-zA-Z0-9._+-]*\.so$", so_dest + '32'),
            (r"^/usr/lib64/glibc-hwcaps/x86-64-v[0-9]+/[a-zA-Z0-9._+-]*\.so$", so_dest),
            (r"^/usr/lib64/haswell/avx512_1/[a-zA-Z0-9._+-]*\.so$", so_dest),
            (r"^/usr/lib64/haswell/[a-zA-Z0-9._+-]*\.so$", so_dest),
            (r"^/usr/lib64/haswell/avx512_1/[a-zA-Z0-9._+-]*\.so$", so_dest),
            (r"^/usr/lib/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib64/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib32/[a-zA-Z0-9._+-]*\.a$", "staticdev32"),
            (r"^/usr/lib/haswell/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib64/glibc-hwcaps/x86-64-v[0-9]+/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib64/haswell/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib64/haswell/avx512_1/[a-zA-Z0-9._+-]*\.a$", "staticdev"),
            (r"^/usr/lib32/haswell/[a-zA-Z0-9._+-]*\.a$", "staticdev32"),
            (r"^/usr/lib/pkgconfig/[a-zA-Z0-9._+-]*\.pc$", "dev"),
            (r"^/usr/lib64/pkgconfig/[a-zA-Z0-9._+-]*\.pc$", "dev"),
            (r"^/usr/lib32/pkgconfig/[a-zA-Z0-9._+-]*\.pc$", "dev32"),
            (r"^/usr/lib64/glibc-hwcaps/x86-64-v[0-9]+/[a-zA-Z0-9._+-]*\.pc$", "dev"),
            (r"^/usr/lib64/haswell/pkgconfig/[a-zA-Z0-9._+-]*\.pc$", "dev"),
            (r"^/usr/lib64/haswell/avx512_1/pkgconfig/[a-zA-Z0-9._+-]*\.pc$", "dev"),
            (r"^/usr/lib/[a-zA-Z0-9._+-]*\.la$", "dev"),
            (r"^/usr/lib64/[a-zA-Z0-9._+-]*\.la$", "dev"),
            (r"^/usr/lib32/[a-zA-Z0-9._+-]*\.la$", "dev32"),
            (r"^/usr/lib/[a-zA-Z0-9._+-]*\.prl$", "dev"),
            (r"^/usr/lib64/[a-zA-Z0-9._+-]*\.prl$", "dev"),
            (r"^/usr/lib32/[a-zA-Z0-9._+-]*\.prl$", "dev32"),
            (r"^/usr/share/aclocal/[a-zA-Z0-9._+-]*\.ac$", "dev", "/usr/share/aclocal/*.ac"),
            (r"^/usr/share/aclocal/[a-zA-Z0-9._+-]*\.m4$", "dev", "/usr/share/aclocal/*.m4"),
            (r"^/usr/share/aclocal-1.[0-9]+/[a-zA-Z0-9._+-]*\.ac$", "dev", "/usr/share/aclocal-1.*/*.ac"),
            (r"^/usr/share/aclocal-1.[0-9]+/[a-zA-Z0-9._+-]*\.m4$", "dev", "/usr/share/aclocal-1.*/*.m4"),
            (r"^/usr/share/doc/" + re.escape(pkg_name) + "/", "doc", "/usr/share/doc/" + re.escape(pkg_name) + "/*"),
            (r"^/usr/share/doc/", "doc"),
            (r"^/usr/share/gtk-doc/html", "doc"),
            (r"^/usr/share/help", "doc"),
            (r"^/usr/share/info/", "doc", "/usr/share/info/*"),
            # now a set of catch-all rules
            (r"^/lib/systemd/system/", "services"),
            (r"^/lib/systemd/user/", "services"),
            (r"^/usr/lib/systemd/system/", "services"),
            (r"^/usr/lib/systemd/user/", "services"),
            (r"^/usr/lib/udev/hwdb.d", "config"),
            (r"^/usr/lib/udev/rules.d", "config"),
            (r"^/usr/lib/modules-load.d", "config"),
            (r"^/usr/lib/tmpfiles.d", "config"),
            (r"^/usr/lib/sysusers.d", "config"),
            (r"^/usr/lib/sysctl.d", "config"),
            (r"^/usr/share/", "data"),
            (r"^/usr/lib/perl5/", "perl", "/usr/lib/perl5/*"),
            # finally move any dynamically loadable plugins (not
            # perl/python/etc.. extensions) into lib package
            (r"^/usr/lib/.*/[a-zA-Z0-9._+-]*\.so", "lib"),
            (r"^/usr/lib64/.*/[a-zA-Z0-9._+-]*\.so", "lib"),
            (r"^/usr/lib32/.*/[a-zA-Z0-9._+-]*\.so", "lib32"),
            # locale data gets picked up via file_is_locale
            (r"^/usr/share/locale/", "ignore")]

        for pat_args in patterns:
            if self.file_pat_match(filename, *pat_args):
                return

        if filename in self.excludes:
            return

        self.push_package_file(filename)

    def remove_file(self, filename):
        """Remove filename from local file list."""
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
            self.package.must_restart += 1

    def load_specfile(self, specfile):
        """Load a specfile instance with relevant information to be written to the spec file."""
        specfile.packages = self.packages
        specfile.excludes = self.excludes
        specfile.locales = self.locales
        specfile.file_maps = self.file_maps
        specfile.setuid = self.setuid
