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

import build
import buildpattern
import buildreq
import files
import config
import glob
import hashlib
import os
import re
import shutil
import subprocess
import urllib
import urllib.request
import pycurl
from io import BytesIO
from util import call
# from util import golang_name
# from util import golang_libpath

name = ""
rawname = ""
version = ""
release = "1"
url = ""
path = ""
tarball_prefix = ""
gcov_file = ""
golibpath = ""
go_pkgname = ""


def get_sha1sum(filename):
    sh = hashlib.sha1()
    with open(filename, "rb") as f:
        sh.update(f.read())
    return sh.hexdigest()


def really_download(url, destination):
    with open(destination, 'wb') as dfile:
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEDATA, dfile)
        c.setopt(c.FOLLOWLOCATION, True)
        c.perform()
        c.close()


def check_or_get_file(url, tarfile):
    tarball_path = build.download_path + "/" + tarfile
    if not os.path.isfile(tarball_path):
        really_download(url, tarball_path)
    return tarball_path


def build_untar(tarball_path):
    tarball_contents = subprocess.check_output(
        ["tar", "-tf", tarball_path], universal_newlines=True)
    extract_cmd = "tar --directory={0} -xf {1}".format(build.base_path, tarball_path)
    if tarball_contents:
        if tarball_contents.startswith("./\n"):
            # skip first line
            tarball_contents = tarball_contents.partition("\n")[2]

        if tarball_contents.startswith("./"):
            # skip the "./"
            tarball_contents = tarball_contents.partition("/")[2]

        (tarball_prefix, _, _) = tarball_contents.partition("/")

    return extract_cmd, tarball_prefix


def build_unzip(zip_path):
    """Return correct unzip command and the prefix folder name of the contents of zip file

    This function will run the zip file through a content list, parsing that list to get the
    root folder name containing the zip file's contents.

    The output of the unzip -l command has the following format:
    ***snip***
    Archive:  file.zip
    (optional) hash
    Length      Date    Time    Name
    ---------  ---------- -----   ----
            0  01-01-2000 00:00   prefix-dir/sub_dir1/subdir2
    ***snip***
    and this function gets the 'prefix-dir' portion from the start of the unzip -l output.
    """
    contents = subprocess.check_output(["unzip", "-l", zip_path], universal_newlines=True)
    lines = contents.splitlines() if contents else []
    # looking for directory prefix in unzip output as it may differ from default
    if len(lines) > 3:
        # In some cases there is a hash line so we detect this based on the header
        # separator character '-'
        prefix_line = 4 if len(lines) > 4 and lines[3][0] == '-' else 3
        prefix = lines[prefix_line].split("/")[0].split()[-1]
    extract_cmd = "unzip -d {0} {1}".format(build.base_path, zip_path)
    return extract_cmd, prefix


def download_tarball(url_argument, name_argument, archives, target_dir):
    global name
    global version
    global url
    global path
    global tarball_prefix
    global gcov_file
    # go naming
    global golibpath
    global go_pkgname

    tarfile = os.path.basename(url)

    if not target_dir:
        build.download_path = os.getcwd() + "/" + name
    else:
        build.download_path = target_dir
    call("mkdir -p %s" % build.download_path)

    gcov_path = build.download_path + "/" + name + ".gcov"
    if os.path.isfile(gcov_path):
        gcov_file = name + ".gcov"

    tarball_path = check_or_get_file(url, tarfile)
    sha1 = get_sha1sum(tarball_path)
    with open(build.download_path + "/upstream", "w") as file:
        file.write(sha1 + "/" + tarfile + "\n")

    tarball_prefix = name + "-" + version
    if tarfile.lower().endswith('.zip'):
        extract_cmd, tarball_prefix = build_unzip(tarball_path)
    elif tarfile.lower().endswith('.gem'):
        tarball_contents = subprocess.check_output(
            ["gem", "unpack", "--verbose", tarball_path], universal_newlines=True)
        extract_cmd = "gem unpack --target={0} {1}".format(build.base_path, tarball_path)
        if tarball_contents:
            tarball_prefix = tarball_contents.splitlines()[-1].rsplit("/")[-1]
            if tarball_prefix.endswith("'"):
                tarball_prefix = tarball_prefix[:-1]
    else:
        extract_cmd, tarball_prefix = build_untar(tarball_path)

    if version == "":
        version = "1"

    print("\n")

    print("Processing", url_argument)
    print(
        "=============================================================================================")
    print("Name        :", name)
    print("Version     :", version)
    print("Prefix      :", tarball_prefix)

    with open(build.download_path + "/Makefile", "w") as file:
        file.write("PKG_NAME := " + name + "\n")
        file.write("URL := " + url_argument + "\n")
        sep = "ARCHIVES := "
        for archive in archives:
            file.write("{}{}".format(sep, archive))
            sep = " " if sep != " " else " \\\n\t"
        file.write("\n")
        file.write("\n")
        file.write("include ../common/Makefile.common\n")

    shutil.rmtree(build.base_path + name, ignore_errors=True)
    shutil.rmtree(build.base_path + tarball_prefix, ignore_errors=True)
    os.makedirs("{}".format(build.output_path), exist_ok=True)

    call("mkdir -p %s" % build.download_path)
    call(extract_cmd)

    path = build.base_path + tarball_prefix

    for archive, destination in zip(archives[::2], archives[1::2]):
        source_tarball_path = check_or_get_file(archive, os.path.basename(archive))
        if source_tarball_path.lower().endswith('.zip'):
            tarball_contents, source_tarball_prefix = build_unzip(source_tarball_path)
        else:
            extract_cmd, source_tarball_prefix = build_untar(source_tarball_path)
        buildpattern.archive_details[archive + "prefix"] = source_tarball_prefix
        call(extract_cmd)
        tar_files = glob.glob("{0}{1}/*".format(build.base_path, source_tarball_prefix))
        move_cmd = "mv "
        for tar_file in tar_files:
            move_cmd += tar_file + " "
        move_cmd += '{0}/{1}'.format(path, destination)

        mkdir_cmd = "mkdir -p "
        mkdir_cmd += '{0}/{1}'.format(path, destination)

        print("mkdir " + mkdir_cmd)
        call(mkdir_cmd)
        call(move_cmd)

        sha1 = get_sha1sum(source_tarball_path)
        with open(build.download_path + "/upstream", "a") as file:
            file.write(sha1 + "/" + os.path.basename(archive) + "\n")

def name_and_version(url_argument, name_argument):
    global name
    global rawname
    global version
    global url

    url = url_argument
    tarfile = os.path.basename(url)
    # it is important for the more specific patterns to come first
    pattern_options = [
        r"(.*?)[\-_](v*[0-9]+[a-zalpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.orig\.tar",
        r"(.*?)[\-_](v*[0-9]+[alpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.src\.(tgz|tar|zip)",
        r"(.*?)[\-_](v*[0-9]+[alpha\+_sbpfourcesigedsvstableP0-9\.\-\~]*)\.(tgz|tar|zip)",
        r"(.*?)[\-_](v*[0-9]+[\+_spbfourcesigedsvstableP0-9\.\~]*)(-.*?)?\.tar",
    ]
    for pattern in pattern_options:
        p = re.compile(pattern)
        m = p.search(tarfile)
        if m:
            name = m.group(1).strip()
            version = m.group(2).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]
            break

    rawname = name
    # R package
    if url_argument.find("cran.r-project.org") > 0 or url_argument.find("cran.rstudio.com") > 0:
        buildpattern.set_build_pattern("R", 10)
        files.want_dev_split = 0
        buildreq.add_buildreq("clr-R-helpers")
        p = re.compile(r"([A-Za-z0-9]+)_(v*[0-9]+[\+_spbfourcesigedsvstableP0-9\.\~\-]*)\.tar\.gz")
        m = p.search(tarfile)
        if m:
            name = "R-" + m.group(1).strip()
            rawname = m.group(1).strip()
            version = m.group(2).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]

    if url_argument.find("pypi.python.org") > 0:
        buildpattern.set_build_pattern("distutils23", 10)
        url_argument = "http://pypi.debian.net/" + name + "/" + tarfile
    if url_argument.find("pypi.debian.net") > 0:
        buildpattern.set_build_pattern("distutils23", 10)

    if url_argument.find(".cpan.org/CPAN/") > 0:
        buildpattern.set_build_pattern("cpan", 10)
        if name:
            name = "perl-" + name
    if url_argument.find(".metacpan.org/") > 0:
        buildpattern.set_build_pattern("cpan", 10)
        if name:
            name = "perl-" + name

    if "github.com" in url_argument:
        # define regex accepted for valid packages, important for specific
        # patterns to come before general ones
        github_patterns = [r"https://github.com/.*/(.*?)/archive/(.*)-final.tar",
                           r"https://github.com/.*/.*/archive/[0-9a-fA-F]{1,40}\/(.*)\-(.*).tar",
                           r"https://github.com/.*/(.*?)/archive/v?(.*).orig.tar",
                           r"https://github.com/.*/(.*?)/archive/(.*).zip",
                           r"https://github.com/.*/(.*?)/archive/v?(.*).tar"]

        for pattern in github_patterns:
            p = re.compile(pattern)
            m = p.search(url_argument)
            if m:
                name = m.group(1).strip()
                # convert from 7_4_2 to 7.4.2
                version = m.group(2).strip().replace('_', '.')
                # remove release candidate tag
                b = version.find("-rc")
                if b > 0:
                    version = version[:b]
                b = version.find("-")
                # a dash is invalid in the version string
                # check for the version number before and after the dash
                if b > 0:
                    # check the string after the dash, this is most common
                    if version[b + 1:].replace('.', '').isdigit():
                        version = version[b + 1:]
                    # the string after the dash was not a version number, try the
                    # part before the dash.
                    elif version[:b].replace('.', '').isdigit():
                        version = version[:b]
                    # last resort, neither side of the dash looked like a version,
                    # just remove the dash so it is at least a valid version string
                    else:
                        version = version.replace('-', '.')
                break

    if url_argument.find("bitbucket.org") > 0:
        p = re.compile(r"https://bitbucket.org/.*/(.*?)/get/[a-zA-Z_-]*([0-9][0-9_.]*).tar")
        m = p.search(url_argument)
        if m:
            name = m.group(1).strip()
            # convert from 7_4_2 to 7.4.2
            version = m.group(2).strip().replace('_', '.')
        else:
            version = "1"

    # ruby
    if url_argument.find("rubygems.org/") > 0:
        buildpattern.set_build_pattern("ruby", 10)
        p = re.compile(r"(.*?)[\-_](v*[0-9]+[alpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.gem")
        m = p.search(tarfile)
        if m:
            name = "rubygem-" + m.group(1).strip()
            # remove release candidate tag
            b = name.find("-rc")
            if b > 0:
                name = name[:b]
            rawname = m.group(1).strip()
            version = m.group(2).strip()
            b = version.find("-")
            if b >= 0:
                version = version[:b]

    # maven
    if url_argument.find("maven.org") > 0:
        buildpattern.set_build_pattern("maven", 10)

    # override from commandline
    if name_argument and name_argument[0] != name:
        pattern = name_argument[0] + r"[\-]*(.*)\.(tgz|tar|zip)"
        p = re.compile(pattern)
        m = p.search(tarfile)
        if m:
            name = name_argument[0]
            rawname = name
            version = m.group(1).strip()
            b = version.find("-")
            if b >= 0 and version.find("-beta") < 0:
                version = version[:b]
            if version.startswith('.'):
                version = version[1:]
        else:
            name = name_argument[0]

    if not name:
        split = url_argument.split('/')
        if len(split) > 3 and split[-2] in ('archive', 'tarball'):
            name = split[-3]
            version = split[-1]
            if version.startswith('v'):
                version = version[1:]
            # remove extension
            version = '.'.join(version.split('.')[:-1])
            if version.endswith('.tar'):
                version = '.'.join(version.split('.')[:-1])

    b = version.find("-")
    if b >= 0 and version.find("-beta") < 0:
        b = b + 1
        version = version[b:]

    if len(version) > 0 and version[0].lower() in ['v', 'r']:
        version = version[1:]

    # remove package name from beginning of version
    if version.lower().startswith(name.lower()):
        pat = re.compile(re.escape(name), re.IGNORECASE)
        version = pat.sub('', version)
        if version[0] in ['.', '-', '_']:
            version = version[1:]

    assert name != ""

def load_specfile(specfile):
    specfile.tarball_prefix = tarball_prefix
    specfile.gcov_file = gcov_file
    specfile.rawname = rawname
    specfile.golibpath = golibpath
