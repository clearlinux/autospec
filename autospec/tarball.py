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

import configparser
import glob
import hashlib
import os
import re
import shutil
import subprocess
from collections import OrderedDict

import build
import buildpattern
import buildreq
import config
import download
from util import call, print_fatal, write_out

name = ""
rawname = ""
version = ""
multi_version = OrderedDict()
release = "1"
url = ""
path = ""
tarball_prefix = ""
gcov_file = ""
archives = []
giturl = ""
domain = ""
prefixes = dict()


def get_go_artifacts(url, target, ver):
    """Get artifacts required to be a go proxy alternative."""
    for name in [f"{ver}.{x}" for x in ["info", "mod", "zip"]]:
        path = os.path.join(target, name)
        if not os.path.exists(path):
            download.do_curl(os.path.join(url, name),
                             dest=path,
                             is_fatal=True)
        sha1 = get_sha1sum(path)
        write_upstream(sha1, name, mode="a")


def process_go_dependency(url, target):
    """Handle go dependency files."""
    base_url = os.path.dirname(url)
    # Unlink the upstream file to avoid appending existing go artifacts
    try:
        os.unlink(os.path.join(build.download_path, "upstream"))
    except FileNotFoundError:
        pass
    for ver in list(multi_version.keys()):
        get_go_artifacts(base_url, target, ver)


def get_contents(filename):
    """Get contents of filename (tar file)."""
    with open(filename, "rb") as f:
        return f.read()
    return None


def get_sha1sum(filename):
    """Get sha1 sum of filename (tar file)."""
    sh = hashlib.sha1()
    sh.update(get_contents(filename))
    return sh.hexdigest()


def check_or_get_file(upstream_url, tarfile, mode="w"):
    """Download tarball from url unless it is present locally."""
    tarball_path = build.download_path + "/" + tarfile
    # check if url signifies a go dependency, which needs special handling
    if tarfile == "list":
        process_go_dependency(upstream_url, build.download_path)
    elif not os.path.isfile(tarball_path):
        download.do_curl(upstream_url, dest=tarball_path, is_fatal=True)
        write_upstream(get_sha1sum(tarball_path), tarfile, mode)
    else:
        write_upstream(get_sha1sum(tarball_path), tarfile, mode)
    return tarball_path


def build_untar(tarball_path):
    """Determine extract command and tarball prefix from tar -tf output."""
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
    """Return correct unzip command and the prefix folder name of the contents of zip file.

    This function will run the zip file through a content list, parsing that list to get the
    root folder name containing the zip file's contents.

    The output of the unzip -q -l command has the following format:
    ***snip***
    (optional) hash
    Length      Date    Time    Name
    ---------  ---------- -----   ----
            0  01-01-2000 00:00   prefix-dir/sub_dir1/subdir2
    ***snip***
    and this function gets the 'prefix-dir' portion from the start of the unzip -l output.
    """
    prefix = None
    zipfile = os.path.basename(zip_path)
    contents = subprocess.check_output(["unzip", "-q", "-l", zip_path], universal_newlines=True)
    lines = contents.splitlines() if contents else []
    # looking for directory prefix in unzip output as it may differ from default

    # First, find the end of the info header
    # It starts with -----
    while len(lines):
        line = lines.pop(0)
        if line[0] == '-':
            break

    # Similarly, strip the footer, if it exists
    if any(line.startswith('-') for line in lines):
        while len(lines):
            line = lines.pop()
            if line[0] == '-':
                break

    # Are there any files left?
    if len(lines) < 1:
        print_fatal("Zip file doesn't appear to have any content")
        exit(1)

    # Look for a common directory prefix
    for line in lines:
        fields = re.split(r'\s+', line, maxsplit=4)
        filename = fields.pop()
        if prefix is None:
            prefix = os.path.dirname(filename)
        common = list()
        for pair in zip(re.split(r'/', prefix), re.split(r'/', filename)):
            if pair[0] == pair[1]:
                common.append(pair[0])
            else:
                break
        prefix = '/'.join(common)

    # If we didn't find a common prefix, make a dir, based on the zip filename
    if not prefix:
        subdir = os.path.splitext(zipfile)[0]
        extract_cmd = "unzip -qq -d {0} {1}".format(
            os.path.join(build.base_path, subdir), zip_path)
    else:
        extract_cmd = "unzip -qq -d {0} {1}".format(build.base_path, zip_path)

    return extract_cmd, prefix


def build_un7z(zip_path):
    """Return correct 7z command and the prefix folder name of the contents of 7z file.

    This function will run the 7z file through a content list, parsing that list to get the
    root folder name containing the 7z file's contents.

    The output of the 7z l command has the following format:
    ***snip***
    7-Zip [64] 16.02 : Copyright (c) 1999-2016 Igor Pavlov : 2016-05-21
    p7zip Version 16.02 (locale=en_US.UTF-8,Utf16=on,HugeFiles=on,64 bits,4 CPUs Intel(R) Core(TM) i5-6260U CPU @ 1.80GHz (406E3),ASM,AES-NI)

    Scanning the drive for archives:
    1 file, 7933454 bytes (7748 KiB)

    Listing archive: foo.7z

    --
    Path = foo.7z
    Type = 7z
    Physical Size = 7933454
    Headers Size = 1526
    Method = LZMA2:23
    Solid = +
    Blocks = 1

    Date         Time    Attr         Size   Compressed  Name
    ------------------- ----- ------------ ------------  ------------------------
    2018-05-15 05:50:54 ....A        25095      7931928  prefix-dir/sub_dir1/subdir2
    ***snip***

    and this function gets the 'prefix-dir' portion from the start of the unzip -l output.
    """
    prefix = ""
    contents = subprocess.check_output(["7z", "l", zip_path], universal_newlines=True)
    lines = contents.splitlines() if contents else []
    # looking for directory prefix in unzip output as it may differ from default
    past_header = False
    for line in lines:
        if past_header:
            # This should be an archive entry; use it
            prefix = line.split("/")[0].split()[-1]
            break
        if line.startswith('----------'):
            # This is the header line; next line should be an archive entry
            past_header = True

    if not past_header:
        print_fatal("Zip file doesn't appear to have any content")
        exit(1)

    if not prefix:
        print_fatal("Malformed zipfile, unable to determine zipfile prefix")
        exit(1)

    extract_cmd = "7z x -o{0} {1}".format(build.base_path, zip_path)
    return extract_cmd, prefix


def build_gem_unpack(tarball_path):
    """Create gem unpack command.

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


def build_go_unzip(tarball_path):
    """Create go unzip command(s)."""
    base_path = os.path.dirname(tarball_path)
    full_extract = []
    prefix = ""
    base_url = os.path.dirname(url)
    for ver in multi_version:
        source_info = os.path.join(base_url, f"{ver}.info")
        source_mod = os.path.join(base_url, f"{ver}.mod")
        source_zip = os.path.join(base_url, f"{ver}.zip")
        extract_cmd, prefix = build_unzip(os.path.join(base_path, f"{ver}.zip"))
        buildpattern.sources["godep"] += [source_info, source_mod, source_zip]
        full_extract.append(extract_cmd)

    return full_extract, prefix


def print_header():
    """Print header for autospec run."""
    print("\n")
    print("Processing", url)
    print("=" * 105)
    print("Name        :", name)
    print("Version     :", version)
    print("Prefix      :", tarball_prefix)


def create_download_path(target_dir):
    """Create download path.

    priority for target directory:
    - target_dir set from args
    - current directory if options.conf['package'] exists and
      any of the options match what has been detected.
    - curdir/name

    Also set giturl from the config (needs config refactor).
    """
    global giturl
    global domain

    target = os.path.join(os.getcwd(), name)
    if os.path.exists(os.path.join(os.getcwd(), 'options.conf')):
        config_f = configparser.ConfigParser(interpolation=None)
        config_f.read('options.conf')
        if "package" in config_f.sections():
            if (config_f["package"].get("name") == name or config_f["package"].get("url") == url or config_f["package"].get("archives") == " ".join(archives)):
                target = os.getcwd()
            if "giturl" in config_f["package"]:
                giturl = config_f["package"].get("giturl")
            if "domain" in config_f["package"]:
                domain = config_f["package"].get("domain")

    if target_dir:
        target = target_dir

    build.download_path = target
    call("mkdir -p {}".format(build.download_path))
    return target


def convert_version(ver_str, name):
    """Remove disallowed characters from the version."""
    # banned substrings. It is better to remove these here instead of filtering
    # them out with expensive regular expressions
    banned_subs = ["x86.64", "source", "src", "all", "bin", "release", "rh",
                   "ga", ".ce", "lcms", "onig", "linux", "gc", "sdk", "orig",
                   "jurko"]

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


def detect_build_from_url(url):
    """Detect build patterns and build requirements from the patterns detected in the url."""
    # R package
    if "cran.r-project.org" in url or "cran.rstudio.com" in url:
        buildpattern.set_build_pattern("R", 10)

    # python
    if "pypi.python.org" in url or "pypi.debian.net" in url:
        buildpattern.set_build_pattern("distutils3", 10)

    # cpan
    if ".cpan.org/" in url or ".metacpan.org/" in url:
        buildpattern.set_build_pattern("cpan", 10)

    # ruby
    if "rubygems.org/" in url:
        buildpattern.set_build_pattern("ruby", 10)

    # maven
    if ".maven." in url:
        buildpattern.set_build_pattern("maven", 10)

    # rust crate
    if "crates.io" in url:
        buildpattern.set_build_pattern("cargo", 10)

    # go dependency
    if "proxy.golang.org" in url:
        buildpattern.set_build_pattern("godep", 10)


def set_multi_version(ver):
    """Add ver to multi_version set and return latest version."""
    global multi_version

    multi_version = config.parse_config_versions(build.download_path)

    if ver:
        # Some build patterns put multiple versions in the same package.
        # For those patterns add to the multi_version list
        if buildpattern.default_pattern in ["godep"]:
            multi_version[ver] = ""
        else:
            multi_version = {ver: ""}
    elif not multi_version:
        # Fall back to ensure a version is always set
        # (otherwise the last known version will be used)
        multi_version[1] = ""
    latest = sorted(multi_version.keys())[-1]
    return latest


def name_and_version(name_arg, version_arg, filemanager):
    """Parse the url for the package name and version."""
    global rawname
    global url
    global giturl
    global repo

    tarfile = os.path.basename(url)

    # If both name and version overrides are set via commandline, set the name
    # and version variables to the overrides and bail. If only one override is
    # set, continue to auto detect both name and version since the URL parsing
    # handles both. In this case, wait until the end to perform the override of
    # the one that was set. An extra conditional, that version_arg is a string
    # is added to enable a package to have multiple versions at the same time
    # for some language ecosystems.
    if name_arg and version_arg:
        # rawname == name in this case
        name = name_arg
        rawname = name_arg
        version = set_multi_version(version_arg)
        return name, rawname, convert_version(version, name)

    name = name_arg
    rawname = name_arg
    version = ""
    # it is important for the more specific patterns to come first
    pattern_options = [
        # handle font packages with names ending in -nnndpi
        r"(.*-[0-9]+dpi)[-_]([0-9]+[a-zA-Z0-9\+_\.\-\~]*)\.(tgz|tar|zip)",
        r"(.*?)[-_][vs]?([0-9]+[a-zA-Z0-9\+_\.\-\~]*)\.(tgz|tar|zip)",
    ]
    for pattern in pattern_options:
        m = re.search(pattern, tarfile)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2), name)
            break

    # R package
    if "cran.r-project.org" in url or "cran.rstudio.com" in url:
        filemanager.want_dev_split = False
        m = re.search(r"([A-Za-z0-9.]+)_(v*[0-9]+[a-zA-Z0-9\+_\.\~\-]*)\.tar\.gz",
                      tarfile)
        if m:
            name = "R-" + m.group(1).strip()
            rawname = m.group(1).strip()
            version = convert_version(m.group(2), name)

    if ".cpan.org/" in url or ".metacpan.org/" in url and name:
        name = "perl-" + name

    if "github.com" in url:
        # define regex accepted for valid packages, important for specific
        # patterns to come before general ones
        github_patterns = [r"https?://github.com/(.*)/(.*?)/archive/[v|r]?.*/(.*).tar",
                           r"https?://github.com/(.*)/(.*?)/archive/[-a-zA-Z_]*-(.*).tar",
                           r"https?://github.com/(.*)/(.*?)/archive/[vVrR]?(.*).tar",
                           r"https?://github.com/(.*)/.*-downloads/releases/download/.*?/(.*)-(.*).tar",
                           r"https?://github.com/(.*)/(.*?)/releases/download/(.*)/",
                           r"https?://github.com/(.*)/(.*?)/files/.*?/(.*).tar"]

        for pattern in github_patterns:
            m = re.search(pattern, url)
            if m:
                repo = m.group(2).strip()
                if repo not in name:
                    # Only take the repo name as the package name if it's more descriptive
                    name = repo
                elif name != repo:
                    name = re.sub(r"release-", '', name)
                    name = re.sub(r"\d*$", '', name)
                rawname = name
                version = m.group(3).replace(name, '')
                if "archive" not in pattern:
                    version = re.sub(r"^[-_.a-zA-Z]+", "", version)
                version = convert_version(version, name)
                if not giturl:
                    giturl = "https://github.com/" + m.group(1).strip() + "/" + repo + ".git"
                break

    if "gnome.org" in url:
        buildreq.add_buildreq("buildreq-gnome")

    if "kde.org" in url or "https://github.com/KDE" in url:
        buildreq.add_buildreq("buildreq-kde")

    # SQLite tarballs use 7 digit versions, e.g 3290000 = 3.29.0, 3081002 = 3.8.10.2
    if "sqlite.org" in url:
        major = version[0]
        minor = version[1:3].lstrip("0").zfill(1)
        patch = version[3:5].lstrip("0").zfill(1)
        build = version[5:7].lstrip("0")
        version = major + "." + minor + "." + patch + "." + build
        version = version.strip(".")

    # construct github giturl from gnome projects
    if not giturl and "download.gnome.org" in url:
        giturl = "https://github.com/GNOME/{}.git".format(name)

    if "mirrors.kernel.org" in url:
        m = re.search(r".*/sourceware/(.*?)/releases/(.*?).tgz", url)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2), name)

    if "sourceforge.net" in url:
        scf_pats = [r"projects/.*/files/(.*?)/(.*?)/[^-]*(-src)?.tar.gz",
                    r"downloads.sourceforge.net/.*/([a-zA-Z]+)([-0-9\.]*)(-src)?.tar.gz"]
        for pat in scf_pats:
            m = re.search(pat, url)
            if m:
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)
                break

    if "bitbucket.org" in url:
        bitbucket_pats = [r"/.*/(.*?)/.*/.*v([-\.0-9a-zA-Z_]*?).(tar|zip)",
                          r"/.*/(.*?)/.*/([-\.0-9a-zA-Z_]*?).(tar|zip)"]
        for pat in bitbucket_pats:
            m = re.search(pat, url)
            version = 1
            if m:
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)
                break

    # ruby
    if "rubygems.org/" in url:
        m = re.search(r"(.*?)[\-_](v*[0-9]+[a-zA-Z0-9\+_\.\-\~]*)\.gem", tarfile)
        if m:
            name = "rubygem-" + m.group(1).strip()
            # remove release candidate tag from the package name
            # https://rubygems.org/downloads/ruby-rc4-0.1.5.gem
            b = name.find("-rc")
            if b > 0:
                name = name[:b]
            rawname = m.group(1).strip()
            version = convert_version(m.group(2), name)

    # maven
    if ".maven." in url:
        maven_pats = [r"maven.org/maven2/[a-zA-Z\-\_]+/([a-zA-Z\-\_])+/([a-zA-Z-\_\d.]+)/[a-zA-Z-\_\d.]*\.(?:pom|jar)",
                      r"maven.apache.org/maven2/[a-zA-Z\-\_]+/([a-zA-Z\-\_])+/([\d.]+)/[a-z-\_.\d]*\.(?:pom|jar)",
                      r"maven.org/maven2/(?:[a-zA-Z-\_.\d/]+)/([a-zA-Z-\_.\d]*)/([a-zA-Z\d\.\_\-]+)/(?:[a-zA-Z-\_.\d]*)\.(?:pom|jar)"]
        for pat in maven_pats:
            m = re.search(pat, url)
            if m:
                name = m.group(1).strip()
                version = convert_version(m.group(2), name)
                break

    # rust crate
    if "crates.io" in url:
        m = re.search(r"/crates.io/api/v[0-9]+/crates/(.*)/(.*)/download.*\.crate", url)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2), name)

    if "gitlab.com" in url:
        # https://gitlab.com/leanlabsio/kanban/-/archive/1.7.1/kanban-1.7.1.tar.gz
        m = re.search(r"gitlab\.com/.*/(.*)/-/archive/(.*)/", url)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2), name)

    if "git.sr.ht" in url:
        # https://git.sr.ht/~sircmpwn/scdoc/archive/1.9.4.tar.gz
        m = re.search(r"git\.sr\.ht/.*/(.*)/archive/(.*).tar.gz", url)
        if m:
            name = m.group(1).strip()
            version = convert_version(m.group(2), name)

    # override name and version from commandline
    name = name_arg if name_arg else name
    version = version_arg if version_arg else version
    version = set_multi_version(version)
    return name, rawname, convert_version(version, name)


def set_gcov():
    """Set the gcov file name."""
    global gcov_file
    gcov_path = os.path.join(build.download_path, name + ".gcov")
    if os.path.isfile(gcov_path):
        gcov_file = name + ".gcov"


def write_upstream(sha, tarfile, mode="w"):
    """Write the upstream hash to the upstream file."""
    write_out(os.path.join(build.download_path, "upstream"),
              os.path.join(sha, tarfile) + "\n", mode=mode)


def find_extract(tar_path, tarfile):
    """Determine the extract command and tarball_prefix."""
    tar_prefix = "{}-{}".format(name, version)
    if tarfile.lower().endswith('.zip'):
        extract_cmd, tar_prefix = build_unzip(tar_path)
    elif tarfile.lower().endswith('.gem'):
        extract_cmd, tar_prefix = build_gem_unpack(tar_path)
    elif tarfile.lower().endswith('.jar'):
        extract_cmd, tar_prefix = build_unzip(tar_path)
    elif tarfile == "list":
        extract_cmd, tar_prefix = build_go_unzip(tar_path)
    else:
        extract_cmd, tar_prefix = build_untar(tar_path)

    return extract_cmd, tar_prefix


def prepare_and_extract(extract_cmd):
    """Prepare the directory and extract the tarball."""
    shutil.rmtree(os.path.join(build.base_path, name), ignore_errors=True)
    shutil.rmtree(os.path.join(build.base_path, tarball_prefix), ignore_errors=True)
    os.makedirs("{}".format(build.base_path), exist_ok=True)
    call("mkdir -p %s" % build.download_path)
    if isinstance(extract_cmd, list) and buildpattern.default_pattern in ["godep"]:
        for cmd in extract_cmd:
            call(cmd)
    else:
        call(extract_cmd)


def process_archives(archives):
    """Download and process archives."""
    for archive, destination in zip(archives[::2], archives[1::2]):
        source_tarball_path = check_or_get_file(archive, os.path.basename(archive), mode="a")

        if destination.startswith(':'):
            continue

        if source_tarball_path.lower().endswith('.zip'):
            extract_cmd, source_tarball_prefix = build_unzip(source_tarball_path)
        elif source_tarball_path.lower().endswith('.7z'):
            extract_cmd, source_tarball_prefix = build_un7z(source_tarball_path)
        else:
            extract_cmd, source_tarball_prefix = build_untar(source_tarball_path)
        buildpattern.archive_details[archive + "prefix"] = source_tarball_prefix
        call(extract_cmd)
        tar_path = os.path.join(build.base_path, source_tarball_prefix)
        if source_tarball_prefix:
            prefixes[archive] = source_tarball_prefix
        else:
            fake_prefix = os.path.splitext(os.path.basename(source_tarball_path))[0]
            tar_path = os.path.join(build.base_path, fake_prefix)
        tar_files = glob.glob("{}/*".format(tar_path))
        if tar_path == path:
            print("Archive {} already unpacked in main path {}; ignoring destination"
                  .format(archive, path))
        else:
            move_cmd = "mv "
            for tar_file in tar_files:
                move_cmd += '"{}"'.format(tar_file) + " "
            move_cmd += '"{0}/{1}"'.format(path, destination)

            mkdir_cmd = "mkdir -p "
            mkdir_cmd += '"{0}/{1}"'.format(path, destination)

            call(mkdir_cmd)
            call(move_cmd)


def process(url_arg, name_arg, ver_arg, target, archives_arg, filemanager):
    """Download and process the tarball at url_arg."""
    global url
    global name
    global version
    global path
    global tarball_prefix
    global archives
    global prefixes
    url = url_arg
    name = name_arg
    version = ver_arg
    archives = archives_arg
    tarfile = os.path.basename(url_arg)
    # determine build pattern and build requirements from url
    detect_build_from_url(url)
    # Create the download path for content and set build.download_path
    create_download_path(target)
    # determine name and version of package
    name, rawname, version = name_and_version(name_arg, ver_arg, filemanager)
    # Store the top-level version
    config.versions[version] = url
    # set gcov file information, must be done after name is set since the gcov
    # name is created by adding ".gcov" to the package name (if a gcov file
    # exists)
    set_gcov()
    # download the tarball to tar_path
    tar_path = check_or_get_file(url, tarfile)
    # determine extract command and tarball prefix for the tarfile
    extract_cmd, tarball_prefix = find_extract(tar_path, tarfile)
    # Store the detected prefix associated with this file
    prefixes[url] = tarball_prefix
    # set global path with tarball_prefix
    path = os.path.join(build.base_path, tarball_prefix)
    # Now that the metadata has been collected print the header
    print_header()
    # write out the Makefile with the name, url, and archives we found
    # prepare directory and extract tarball
    prepare_and_extract(extract_cmd)
    # locate or download archives and move them into the right spot
    process_archives(archives_arg)
    # process any additional versions
    urls = config.parse_config_versions(build.download_path)
    if len(urls) <= 1:
        # This is a single version package
        return
    for extraver in urls:
        extraurl = urls[extraver]
        if not extraurl:
            # Nothing to do here
            continue
        if extraurl == url:
            # This is the same as the SOURCE0 package, which we already handled
            continue
        buildpattern.sources["version"].append(extraurl)
        name, rawname, extraver = name_and_version(name_arg, extraver, filemanager)
        # Make sure we don't stick to a single version
        set_multi_version(None)
        tarfile = os.path.basename(extraurl)
        tar_path = check_or_get_file(extraurl, tarfile, mode="a")
        extract_cmd, tarball_prefix = find_extract(tar_path, tarfile)
        prefixes[extraurl] = tarball_prefix
        prepare_and_extract(extract_cmd)


def load_specfile(specfile):
    """Load the specfile object with the tarball_prefix, gcov_file, and rawname."""
    specfile.tarball_prefix = tarball_prefix
    specfile.prefixes = prefixes
    specfile.gcov_file = gcov_file
    specfile.rawname = rawname
