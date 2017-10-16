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

import glob
import hashlib
import os
import re
import shutil
import subprocess
import pycurl
import configparser

import build
import buildpattern
import buildreq
from util import call, print_fatal, write_out

name = ""
rawname = ""
version = ""
release = "1"
url = ""
path = ""
tarball_prefix = ""
gcov_file = ""
archives = []


def get_sha1sum(filename):
    """
    Get sha1 sum of filename (tar file)
    """
    sh = hashlib.sha1()
    with open(filename, "rb") as f:
        sh.update(f.read())
    return sh.hexdigest()


def really_download(upstream_url, destination):
    """
    Ok, really download the tarball from url
    """
    with open(destination, 'wb') as dfile:
        c = pycurl.Curl()
        c.setopt(c.URL, upstream_url)
        c.setopt(c.WRITEDATA, dfile)
        c.setopt(c.FOLLOWLOCATION, True)
        try:
            c.perform()
        except pycurl.error:
            print_fatal("unable to download {}".format(upstream_url))
            exit(1)
        finally:
            c.close()


def check_or_get_file(upstream_url, tarfile):
    """
    Download tarball from url unless it is present locally
    """
    tarball_path = build.download_path + "/" + tarfile
    if not os.path.isfile(tarball_path):
        really_download(upstream_url, tarball_path)
    return tarball_path


def build_untar(tarball_path):
    """
    Determine extract command and tarball prefix from tar -tf output
    """
    tar_prefix = ""
    try:
        tarball_contents = subprocess.check_output(
            ["tar", "-tf", tarball_path], universal_newlines=True).split("\n")
    except subprocess.CalledProcessError as cpe:
        file_type = subprocess.check_output(["file", tarball_path]).decode("utf-8").strip()
        print_fatal("tarball inspection failed, unable to determine tarball contents:\n"
                    "{}\n{}\n".format(file_type, cpe))
        exit(1)

    extract_cmd = "tar --directory={0} -xf {1}".format(build.base_path, tarball_path)
    for line in tarball_contents:
        # sometimes a leading ./ is prepended to the line, this is not the prefix
        line = line.lstrip("./")
        # skip this line, it does not contain the prefix or is not a directory
        if not line or "/" not in line:
            continue

        tar_prefix = line.split("/")[0]
        if tar_prefix:
            break

    if not tar_prefix:
        print_fatal("malformed tarball, unable to determine tarball prefix")
        exit(1)

    return extract_cmd, tar_prefix


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


def build_gem_unpack(tarball_path):
    """
    gem unpack --verbose
    /path/to/dir/file1
    /path/to/dir/file2
    ...
    Unpacked gem: '/path/to/gem/tarball_prefix'
    """
    tar_prefix = ''
    tarball_contents = subprocess.check_output(
        ["gem", "unpack", "--verbose", tarball_path], universal_newlines=True)
    extract_cmd = "gem unpack --target={0} {1}".format(build.base_path, tarball_path)
    if tarball_contents:
        tar_prefix = tarball_contents.splitlines()[-1].rsplit("/")[-1]
        if tar_prefix.endswith("'"):
            tar_prefix = tar_prefix[:-1]

    return extract_cmd, tar_prefix


def print_header():
    """
    Print header for autospec run
    """
    print("\n")
    print("Processing", url)
    print("=" * 105)
    print("Name        :", name)
    print("Version     :", version)
    print("Prefix      :", tarball_prefix)


def download_tarball(target_dir):
    """
    Download tarball at url (global) to target_dir

    priority for target directory:
    - target_dir set from args
    - current directory if options.conf['package'] exists and
      any of the options match what has been detected.
    - curdir/name
    """
    tarfile = os.path.basename(url)
    target = os.path.join(os.getcwd(), name)
    if os.path.exists(os.path.join(os.getcwd(), 'options.conf')):
        config_f = configparser.ConfigParser()
        config_f.read('options.conf')
        if "package" in config_f.sections():
            if (config_f["package"].get("name") == name or
                    config_f["package"].get("url") == url or
                    config_f["package"].get("archives") == " ".join(archives)):
                target = os.getcwd()

    if target_dir:
        target = target_dir

    build.download_path = target
    call("mkdir -p {}".format(build.download_path))

    # locate the tarball locally or download
    return check_or_get_file(url, tarfile)


def convert_version(ver_str):
    """
    Remove disallowed characters from the version
    """
    suffix = ''
    # remove architecture string
    ver_str = ver_str.replace('x86_64', '')
    ver_str = ver_str.replace(name, '')
    ver_str = ver_str.strip().replace('-', '.').replace('_', '.')
    ver_str_pat = r'[0-9\.]+(beta|pre|b|alpha|sdist)([\.0-9]*)$'
    match = re.search(ver_str_pat, ver_str)
    # it is important the first group matches, not just the second
    if match and match.group(1):
        # match.group(2) is an empty string if it was not matched
        suffix = match.group(1) + match.group(2)
        ver_str = re.sub(r'{}$'.format(suffix), '', ver_str)
    ver_str = ''.join(c for c in ver_str if c.isdigit() or c == '.')
    return '{}.{}'.format(ver_str.strip('.'), suffix) if suffix else ver_str.strip('.')


def name_and_version(name_arg, version_arg, filemanager):
    """
    Parse the url for the package name and version
    """
    global name
    global rawname
    global version
    global url

    tarfile = os.path.basename(url)

    # If both name and version overrides are set via commandline, set the name
    # and version variables to the overrides and bail. If only one override is
    # set, continue to auto detect both name and version since the URL parsing
    # handles both. In this case, wait until the end to perform the override of
    # the one that was set.
    if name_arg and version_arg:
        # rawname == name in this case
        name = name_arg
        rawname = name
        version = version_arg
        return

    # it is important for the more specific patterns to come first
    pattern_options = [
        r"(.*?)[\-_](v*[0-9]+[a-zalpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.orig\.tar",
        r"(.*?)[\-_](v*[0-9]+[alpha\+_spbfourcesigedsvstableP0-9\.\-\~]*)\.src\.(tgz|tar|zip)",
        # handle font packages with names ending in -nnndpi
        r"(.*-[0-9]+dpi)[\-_](v*[0-9]+[alpha\+_sbpfourcesigedsvstableP0-9\.\-\~]*)\.(tgz|tar|zip)",
        r"(.*?)[\-_](v*[0-9]+[alpha\+_sbpfourcesigedsvstableP0-9\.\-\~]*)\.(tgz|tar|zip)",
        r"(.*?)[\-_](v*[0-9]+[\+_spbfourcesigedsvstableP0-9\.\~]*)(-.*?)?\.tar",
    ]
    for pattern in pattern_options:
        p = re.compile(pattern)
        m = p.search(tarfile)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2))
            break

    rawname = name
    # R package
    if url.find("cran.r-project.org") > 0 or url.find("cran.rstudio.com") > 0:
        buildpattern.set_build_pattern("R", 10)
        filemanager.want_dev_split = False
        buildreq.add_buildreq("clr-R-helpers")
        p = re.compile(r"([A-Za-z0-9.]+)_(v*[0-9]+[\+_spbfourcesigedsvstableP0-9\.\~\-]*)\.tar\.gz")
        m = p.search(tarfile)
        if m:
            name = "R-" + m.group(1).strip()
            rawname = m.group(1).strip()
            version = m.group(2).strip().replace('-', '.')

    if url.find("pypi.python.org") > 0:
        buildpattern.set_build_pattern("distutils23", 10)
        url = "http://pypi.debian.net/" + name + "/" + tarfile
        buildreq.add_buildreq("python3-dev")
        buildreq.add_buildreq("python-dev")

    if url.find("pypi.debian.net") > 0:
        buildpattern.set_build_pattern("distutils23", 10)
        buildreq.add_buildreq("python3-dev")
        buildreq.add_buildreq("python-dev")

    if url.find(".cpan.org/CPAN/") > 0:
        buildpattern.set_build_pattern("cpan", 10)
        if name:
            name = "perl-" + name
    if url.find(".metacpan.org/") > 0:
        buildpattern.set_build_pattern("cpan", 10)
        if name:
            name = "perl-" + name

    if "github.com" in url:
        # define regex accepted for valid packages, important for specific
        # patterns to come before general ones
        github_patterns = [r"https?://github.com/.*/(.*?)/archive/(.*)-final.tar",
                           r"https?://github.com/.*/.*/archive/[0-9a-fA-F]{1,40}\/(.*)\-(.*).tar",
                           r"https?://github.com/.*/(.*?)/archive/v?(.*).orig.tar",
                           r"https?://github.com/.*/(.*?)/archive/(.*).zip",
                           r"https?://github.com/.*/(.*?)/archive/v?(.*).tar",
                           r"https?://github.com/.*/(.*?)/releases/download/v.*/(.*).tar"]

        for pattern in github_patterns:
            p = re.compile(pattern)
            m = p.search(url)
            if m:
                name = m.group(1).strip()
                rawname = name
                version = convert_version(m.group(2))
                break

    if url.find("bitbucket.org") > 0:
        p = re.compile(r"https?://bitbucket.org/.*/(.*?)/.*/([.0-9a-zA-Z_-]*?).tar")
        m = p.search(url)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2))
        else:
            version = "1"

    # ruby
    if url.find("rubygems.org/") > 0:
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
    if url.find("maven.org") > 0:
        buildpattern.set_build_pattern("maven", 10)

    if not name:
        split = url.split('/')
        if len(split) > 3 and split[-2] in ('archive', 'tarball'):
            name = split[-3]
            version = split[-1]
            version = version.lstrip('v')
            # remove extension
            version = version.rsplit('.', 1)[0]
            if version.endswith('.tar'):
                version = version.replace('.tar', '')

    # override name and version from commandline
    name = name_arg if name_arg else name
    version = version_arg if version_arg else version

    # sanity check to make sure we aren't using an empty version
    if version == "":
        version = "1"


def set_gcov():
    """
    Set the gcov file name
    """
    global gcov_file
    gcov_path = os.path.join(build.download_path, name + ".gcov")
    if os.path.isfile(gcov_path):
        gcov_file = name + ".gcov"


def write_upstream(sha, tarfile, mode="w"):
    """
    Write the upstream hash to the upstream file
    """
    write_out(os.path.join(build.download_path, "upstream"),
              os.path.join(sha, tarfile) + "\n", mode=mode)


def find_extract(tar_path, tarfile):
    """
    Determine the extract command and tarball_prefix
    """
    tar_prefix = "{}-{}".format(name, version)
    if tarfile.lower().endswith('.zip'):
        extract_cmd, tar_prefix = build_unzip(tar_path)
    elif tarfile.lower().endswith('.gem'):
        extract_cmd, tar_prefix = build_gem_unpack(tar_path)
    else:
        extract_cmd, tar_prefix = build_untar(tar_path)

    return extract_cmd, tar_prefix


def write_makefile(archives):
    """
    Write the new makefile with url, name, and archives
    """
    with open(build.download_path + "/Makefile", "w") as f:
        f.write("PKG_NAME := " + name + "\n")
        f.write("URL := " + url + "\n")
        sep = "ARCHIVES := "
        for archive in archives:
            f.write("{}{}".format(sep, archive))
            sep = " " if sep != " " else " \\\n\t"
        f.write("\n")
        f.write("\n")
        f.write("include ../common/Makefile.common\n")


def prepare_and_extract(extract_cmd):
    """
    Prepare the directory and extract the tarball
    """
    shutil.rmtree(os.path.join(build.base_path, name), ignore_errors=True)
    shutil.rmtree(os.path.join(build.base_path, tarball_prefix), ignore_errors=True)
    os.makedirs("{}".format(build.output_path), exist_ok=True)
    call("mkdir -p %s" % build.download_path)
    call(extract_cmd)


def process_archives(archives):
    """
    Download and process archives
    """
    for archive, destination in zip(archives[::2], archives[1::2]):
        source_tarball_path = check_or_get_file(archive, os.path.basename(archive))
        if source_tarball_path.lower().endswith('.zip'):
            extract_cmd, source_tarball_prefix = build_unzip(source_tarball_path)
        else:
            extract_cmd, source_tarball_prefix = build_untar(source_tarball_path)
        buildpattern.archive_details[archive + "prefix"] = source_tarball_prefix
        call(extract_cmd)
        tar_path = os.path.join(build.base_path, source_tarball_prefix)
        tar_files = glob.glob("{}/*".format(tar_path))
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
        write_upstream(sha1, os.path.basename(archive), mode="a")


def process(url_arg, name_arg, ver_arg, target, archives_arg, filemanager):
    """
    Download and process the tarball at url_arg
    """
    global url
    global name
    global version
    global path
    global tarball_prefix
    global archives
    url = url_arg
    name = name_arg
    version = ver_arg
    archives = archives_arg
    tarfile = os.path.basename(url_arg)
    # determine name and version of package
    name_and_version(name_arg, ver_arg, filemanager)
    # set gcov file information, must be done after name is set since the gcov
    # name is created by adding ".gcov" to the package name (if a gcov file
    # exists)
    set_gcov()
    # download the tarball to tar_path
    tar_path = download_tarball(target)
    # write the sha of the upstream tarfile to the "upstream" file
    write_upstream(get_sha1sum(tar_path), tarfile)
    # determine extract command and tarball prefix for the tarfile
    extract_cmd, tarball_prefix = find_extract(tar_path, tarfile)
    # set global path with tarball_prefix
    path = os.path.join(build.base_path, tarball_prefix)
    # Now that the metadata has been collected print the header
    print_header()
    # write out the Makefile with the name, url, and archives we found
    # DEPRECATED, this will be removed in a future version
    write_makefile(archives_arg)
    # prepare directory and extract tarball
    prepare_and_extract(extract_cmd)
    # locate or download archives and move them into the right spot
    process_archives(archives_arg)


def load_specfile(specfile):
    """
    Load the specfile object with the tarball_prefix, gcov_file, and rawname
    """
    specfile.tarball_prefix = tarball_prefix
    specfile.gcov_file = gcov_file
    specfile.rawname = rawname
