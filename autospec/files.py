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
from collections import OrderedDict
import lang
import re
import tarball
import buildreq
import config
# todo package splits

# per sub-package file list for spec purposes
packages = OrderedDict()
main_requires = OrderedDict()

# global file list to weed out dupes
files = []
files_blacklist = []
excludes = []
extras = []
setuid = []
attrs = {}

newfiles_printed = 0

#
# Do we need ALL include files in a dev package, even if they're not in /usr/include?
# Yes in the general case, but for example for R packages,
# the answer is No.
want_dev_split = 1


def push_main_requires(package):
    global main_requires
    if (package not in main_requires):
        main_requires[package] = set()


def push_package_file(filename, package="main"):
    global packages
    global newfiles_printed

    if (package not in packages):
        packages[package] = set()
    packages[package].add(filename)
    build.must_restart = build.must_restart + 1
    if newfiles_printed == 0:
        print("  New %files content found")
        newfiles_printed = 1


def file_pat_match(filename, pattern, package, replacement="", prefix=""):
    if replacement == "":
        replacement = prefix + filename

    pat = re.compile(pattern)
    match = pat.search(filename)
    if match:
        if filename in excludes:
            push_package_file("%exclude " + filename, package)
            return True
        push_package_file(replacement, package)
        return True
    else:
        return False


def file_is_locale(filename):
    pat = re.compile("^/usr/share/locale/.*/(.*)\.mo")
    match = pat.search(filename)
    if match:
        l = match.group(1)
        lang.add_lang(l)
        return True
    else:
        return False


def push_file(filename):
    global files
    global files_blacklist
    global extras
    global setuid
    global attrs
    for file in files:
        if file == filename:
            return 0

    if filename in files_blacklist:
        return 0
    files.append(filename)

    if file_is_locale(filename):
        return

    # autostart
    part = re.compile("^/usr/lib/systemd/system/.+\.target\.wants/.+")
    if part.search(filename):
        push_package_file(filename, "autostart")
        excludes.append(filename)

    # extras
    if filename in extras:
        push_package_file(filename, "extras")
        excludes.append(filename)

    if filename in setuid:
        fn = "%attr(4755, root, root) " + filename
        push_package_file(fn, "setuid")
        excludes.append(filename)

    if filename in attrs:
        fn = "%s(%s,%s,%s) %s" % (attrs[filename][0], attrs[filename][1], attrs[filename][2],
                                  attrs[filename][3], filename)
        push_package_file(fn, "attr")
        excludes.append(filename)

    if file_pat_match(filename, r"^/usr/share/omf", "main", "/usr/share/omf/*"):
        return

    if file_pat_match(filename, r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib"):
        return
    if file_pat_match(filename, r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib"):
        return
    if file_pat_match(filename, r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib32"):
        return
    if file_pat_match(filename, r"^/usr/lib64/avx2/[a-zA-Z0-9\.\_\-\+]*\.so\.", "lib"):
        return
    if file_pat_match(filename, r"^/usr/lib64/gobject-introspection/", "lib"):
        return
    if file_pat_match(filename, r"^/usr/libexec/", "bin"):
        return
    if file_pat_match(filename, r"^/usr/bin/", "bin"):
        return
    if file_pat_match(filename, r"^/usr/sbin/", "bin"):
        return
    if file_pat_match(filename, r"^/sbin/", "bin"):
        return
    if file_pat_match(filename, r"^/bin/", "bin"):
        return
    if file_pat_match(filename, r"^/bin/", "bin"):
        return

    if file_pat_match(filename, r"^/usr/lib/python.*/", "python", "/usr/lib/python*/*"):
        return
    if file_pat_match(filename, r"^/usr/lib64/python.*/", "python", "/usr/lib64/python*/*"):
        return
    if file_pat_match(filename, r"^/usr/share/gir-[0-9\.]+/[a-zA-Z0-9\.\_\-\+]*\.gir", "dev", "/usr/share/gir-1.0/*.gir"):
        print("HIT GIR\n")
        return
    if file_pat_match(filename, r"^/usr/share/cmake/", "data", "/usr/share/cmake/*"):
        return
    if file_pat_match(filename, r"^/usr/share/cmake-3.1/", "data", "/usr/share/cmake-3.1/*"):
        return
    if file_pat_match(filename, r"^/usr/share/cmake-3.7/", "dev", "/usr/share/cmake-3.7/*"):
        return
    if file_pat_match(filename, r"^/usr/share/cmake-3.6/", "dev", "/usr/share/cmake-3.6/*"):
        return
    if file_pat_match(filename, r"^/usr/share/girepository-1\.0/.*\.typelib\$", "dev", "/usr/share/girepository-1.0/*.typelib"):
        return

    if file_pat_match(filename, r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.hxx", "dev", "/usr/include/*.hxx"):
        return
    if file_pat_match(filename, r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.hpp", "dev", "/usr/include/*.hpp"):
        return
    if file_pat_match(filename, r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.h\+\+", "dev", "/usr/include/*.h\+\+"):
        return
    if file_pat_match(filename, r"^/usr/include/[a-zA-Z0-9\.\_\-\+]*\.h", "dev", "/usr/include/*.h"):
        return
    if file_pat_match(filename, r"^/usr/include/", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib64/girepository-1.0/", "dev"):
        return
    if file_pat_match(filename, r"^/usr/share/cmake/", "dev"):
        return
    if want_dev_split > 0 and file_pat_match(filename, r"^/usr/.*/include/.*\.h$", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.so$", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.so$", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib32/[a-zA-Z0-9\.\_\-\+]*\.so$", "dev32"):
        return
    if file_pat_match(filename, r"^/usr/lib64/avx2/[a-zA-Z0-9\.\_\-\+]*\.so$", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev", "/usr/lib/*.a"):
        return
    if file_pat_match(filename, r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev", "/usr/lib64/*.a"):
        return
    if file_pat_match(filename, r"^/usr/lib64/[a-zA-Z0-9\.\_\-\+]*\.a$", "dev32", "/usr/lib32/*.a"):
        return
    if file_pat_match(filename, r"^/usr/lib/pkgconfig/[a-zA-Z0-9\.\_\-\+]*\.pc$", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib64/pkgconfig/[a-zA-Z0-9\.\_\-\+]*\.pc$", "dev"):
        return
    if file_pat_match(filename, r"^/usr/lib32/pkgconfig/[a-zA-Z0-9\.\_\-\+]*\.pc$", "dev32"):
        return
    if file_pat_match(filename, r"^/usr/share/aclocal/[a-zA-Z0-9\.\_\-\+]*\.ac$", "dev", "/usr/share/aclocal/*.ac"):
        return
    if file_pat_match(filename, r"^/usr/share/aclocal/[a-zA-Z0-9\.\_\-\+]*\.m4$", "dev", "/usr/share/aclocal/*.m4"):
        return
    if file_pat_match(filename, r"^/usr/share/aclocal-1.[0-9]+/[a-zA-Z0-9\.\_\-\+]*\.ac$", "dev", "/usr/share/aclocal-1.*/*.ac"):
        return
    if file_pat_match(filename, r"^/usr/share/aclocal-1.[0-9]+/[a-zA-Z0-9\.\_\-\+]*\.m4$", "dev", "/usr/share/aclocal-1.*/*.m4"):
        return

    if file_pat_match(filename, r"^/usr/share/doc/" + re.escape(tarball.name) + "/", "doc", "%doc /usr/share/doc/" + re.escape(tarball.name) + "/*"):
        return
    if file_pat_match(filename, r"^/usr/share/gtk-doc/html", "doc"):
        return
    if file_pat_match(filename, r"^/usr/share/info/", "doc", "%doc /usr/share/info/*"):
        return

    if file_pat_match(filename, r"^/usr/share/man/man0", "doc", "%doc /usr/share/man/man0/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man1", "doc", "%doc /usr/share/man/man1/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man2", "doc", "%doc /usr/share/man/man2/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man3", "doc", "%doc /usr/share/man/man3/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man4", "doc", "%doc /usr/share/man/man4/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man5", "doc", "%doc /usr/share/man/man5/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man6", "doc", "%doc /usr/share/man/man6/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man7", "doc", "%doc /usr/share/man/man7/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man8", "doc", "%doc /usr/share/man/man8/*"):
        return
    if file_pat_match(filename, r"^/usr/share/man/man9", "doc", "%doc /usr/share/man/man9/*"):
        return

    if file_pat_match(filename, r"^/etc/systemd/system/.*\.wants/", "active-units"):
        return

    # now a set of catch-all rules
    if file_pat_match(filename, r"^/etc/", "config", "", "%config "):
        return
    if file_pat_match(filename, r"^/usr/etc/", "config", "", "%config "):
        return
    if file_pat_match(filename, r"^/lib/systemd", "config"):
        return
    if file_pat_match(filename, r"^/usr/lib/systemd", "config"):
        return
    if file_pat_match(filename, r"^/usr/lib/udev/rules.d", "config"):
        return
    if file_pat_match(filename, r"^/usr/lib/modules-load.d", "config"):
        return
    if file_pat_match(filename, r"^/usr/lib/tmpfiles.d", "config"):
        return
    if file_pat_match(filename, r"^/usr/lib/sysusers.d", "config"):
        return
    if file_pat_match(filename, r"^/usr/lib/sysctl.d", "config"):
        return

    if file_pat_match(filename, r"^/usr/share/", "data"):
        return

    # finally move any dynamically loadable plugins (not
    # perl/python/ruby/etc.. extensions) into lib package
    if file_pat_match(filename, r"^/usr/lib/.*/[a-zA-Z0-9\.\_\-\+]*\.so", "lib"):
        return
    if file_pat_match(filename, r"^/usr/lib64/.*/[a-zA-Z0-9\.\_\-\+]*\.so", "lib"):
        return

# locale data gets picked up via find_lang
    if file_pat_match(filename, r"^/usr/share/locale/", "ignore"):
        return

    if filename in excludes:
        push_package_file("%exclude " + filename)
        return

    push_package_file(filename)


def remove_file(file):
    global files
    global packages
    global files_blacklist
    hit = False

    if file in files:
        files.remove(file)
        print("File no longer present: %s" % file)
        hit = True
    for pkg in packages:
        if file in packages[pkg]:
            packages[pkg].remove(file)
            print("File no longer present in %s: %s" % (pkg, file))
            hit = True
    if hit:
        if file not in files_blacklist:
            files_blacklist.append(file)
        build.must_restart = build.must_restart + 1


def write_files_header(file):
    global files
    global packages

    groups = dict()
    groups["dev"] = "Development"
    groups["bin"] = "Binaries"
    groups["lib"] = "Libraries"
    groups["doc"] = "Documentation"
    groups["data"] = "Data"

    deps = dict()

    deps["dev"] = ["lib", "bin", "data"]
    deps["dev32"] = ["lib32", "bin", "data"]
    deps["bin"] = ["data", "config", "setuid", "attr"]
    deps["lib"] = ["data", "config"]
    deps["lib32"] = ["data", "config"]

    provides = dict()
    provides["dev"] = ["devel"]

    for pkg in sorted(packages):
        if pkg == "ignore":
            continue
        if pkg == "main":
            continue

        file.write("\n%package " + pkg + "\n")
        file.write("Summary: " + pkg +
                   " components for the " + tarball.name + " package.\n")
        if pkg in groups:
            file.write("Group: " + groups[pkg] + "\n")
        else:
            file.write("Group: Default\n")
        for dep in deps.get(pkg, []):
            if dep in packages:
                file.write("Requires: " + tarball.name + "-" + dep + "\n")
        for prov in provides.get(pkg, []):
            file.write("Provides: " + tarball.name + "-" + prov + "\n")
        if pkg == "python":
            if tarball.name != tarball.name.lower():
                file.write("Provides: %s-python\n" % tarball.name.lower())
            for req in sorted(buildreq.pythonreqs):
                if req in buildreq.buildreqs:
                    file.write("Requires: " + req + "\n")
        file.write("\n")
        file.write("%description " + pkg + "\n")
        file.write(pkg + " components for the " + tarball.name + " package.\n")
        file.write("\n")


def write_files(file):
    global files
    global packages

    file.write("\n%files\n")
    file.write("%defattr(-,root,root,-)\n")
    if "main" in packages:
        for filename in sorted(packages["main"]):
            file.write(filename + "\n")

    for pkg in sorted(packages):
        if pkg == "ignore":
            continue
        if pkg == "main":
            continue
        if pkg == "locales":
            continue
        file.write("\n%files " + pkg + "\n")
        file.write("%defattr(-,root,root,-)\n")
        for filename in sorted(packages[pkg]):
            file.write(filename + "\n")


def write_scriplets(file):
    global files
    global packages

    for pkg in sorted(packages):
        if pkg == "ignore":
            continue
        if pkg == "main":
            continue
        if pkg == "locales":
            continue
        for script in ["post", "pre"]:
            content = config.read_conf_file("%s.%s" % (pkg, script))
            if content:
                file.write("\n%{0} {1}\n".format(script, pkg))
                file.writelines(content)


def write_main_subpackage_requires(file):
    global files
    global packages
    global main_requires

    for pkg in packages:
        if pkg == "autostart" and config.config_opts['no_autostart']:
            continue
        if pkg == "ignore":
            continue
        if pkg == "main":
            continue
        if pkg == "dev":
            continue
        if pkg == "active-units":
            continue
        if pkg == "extras":
            continue
        if pkg == "lib32":
            continue
        if pkg == "dev32":
            continue
        file.write("Requires: " + tarball.name + "-" + pkg + "\n")

    for pkg in main_requires:
        file.write("Requires: " + pkg + "\n")
