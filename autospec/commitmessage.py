#!/bin/true
#
# commitmessage.py - part of autospec
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
# objective
#
# heuristics to find a git commit message
#
#

import os
import re
import shutil
import sys
from subprocess import PIPE, run

import build
import config
import tarball
import util


def scan_for_changes(download_path, directory):
    """Scan for changelogs or news files in the file sources.

    Scan for changelogs or news files in the source code and copy them to download_path as their
    `config.transform`ed name. The file with the transformed name will later be parsed to find the
    commit message.
    """
    found = []
    interests = config.transforms.keys()
    for dirpath, dirnames, files in os.walk(directory, topdown=False):
        hits = [x for x in files if x.lower() in interests and x.lower() not in found]
        for item in hits:
            source = os.path.join(dirpath, item)
            target = os.path.join(download_path, config.transforms[item.lower()])
            try:
                shutil.copy(source, target)
                os.chmod(target, 0o644)
            except Exception as e:
                print("Error copying file: {}".format(e))
                sys.exit(1)
            found.append(item)


def is_header(lines, curindex):
    """Check if the current line is a section header.

    Check if the current line is a section header by looking for a blank line before it or an
    underline/section break (---) after it. Returns True for lines at the beginning or end of the
    file.
    """
    if curindex == 0:
        # treat the start of the file as a header
        # this will not be caught by an IndexError because -1 is a valid index
        return True

    try:
        return (not lines[curindex - 1]) or ('---' in lines[curindex + 1])
    except IndexError:
        # end of file doesn't matter for starting a block and is an obvious end
        # of a block
        return True


def find_in_line(pattern, line):
    """Return True if the pattern is in the line, False otherwise."""
    return bool(re.search(pattern, line))


def process_NEWS(newsfile):
    """Parse the newfile for relevent changes.

    Look for changes and CVE fixes relevant to current version update. This information is returned
    as a tuple: (commitmessage, cves).

    A maximum of 15 lines from the newsfile is returned in the commitmessage.
    If the newsfile information is truncated to 15 lines an additional line is
    added "(NEWS truncated at 15 lines)"
    """
    commitmessage = []
    cves = set()
    start = 0
    stop = 0
    success = False
    start_found = False

    if config.old_version is None or config.old_version == tarball.version:
        # no version update, so no information to search for in newsfile
        return commitmessage, cves

    try:
        with util.open_auto(os.path.join(build.download_path, newsfile)) as f:
            newslines = f.readlines()
    except EnvironmentError:
        return commitmessage, cves

    newslines = [news.rstrip('\n') for news in newslines]

    # these are patterns that define the beginning of a block of information
    # regarding the current version.
    news_start = [r'Version.*{}'.format(tarball.version),
                  r'(v|- )?{}:?'.format(tarball.version),
                  r'{}-{}:?'.format(tarball.name, tarball.version),
                  r'{} 20'.format(tarball.version)]

    # these are patterns that define the end of a block of information
    # regarding the current version.
    news_end = [r'\*\*\* Changes in.*{}'.format(config.old_version),
                r'{}.*201'.format(config.old_version),
                r'Version.*{}'.format(config.old_version),
                r'^Overview of changes leading to {}'.format(config.old_version),
                r'^{}(-| ){}:?'.format(tarball.name, config.old_version),
                r'v?{}:?'.format(config.old_version)]

    for idx, news in enumerate(newslines):
        # only check headers for begin and end patterns
        if is_header(newslines, idx):
            for pat in news_start:
                if find_in_line(pat, news):
                    start = idx
                    start_found = True
                    break
            if start_found:
                for pat in news_end:
                    if find_in_line(pat, news):
                        success = True
                        stop = idx - 1  # stop before this header
                        break
            if start_found and success:
                break

    if not success or stop <= start:
        return commitmessage, cves

    # now search for CVEs
    pat = re.compile(r"(CVE\-[0-9]+\-[0-9]+)")
    for news in newslines[start:stop]:
        match = pat.search(news)
        if match:
            s = match.group(1)
            cves.add(s)

    # compile commitmessage to return
    commitmessage.append("")
    for news in newslines[start:min(start + 15, stop)]:
        commitmessage.append(news)

    if stop > start + 15:
        # append message that news was truncated
        commitmessage.extend(["", "(NEWS truncated at 15 lines)"])

    commitmessage.append("")
    return commitmessage, cves


def process_git(giturl, oldversion, newversion):
    """Check out a git tree and try to turn the git history into a commit message."""
    oldtag = ""
    guessed_oldtag = oldversion
    newtag = ""
    guessed_newtag = newversion

    if len(giturl) < 1:
        return ""
    if oldversion == newversion:
        return ""

    run(["git", "-C", "results", "clone", giturl, tarball.name])
    p = run(["git", "-C", "results/" + tarball.name, "tag"], stdout=PIPE)
    tags = p.stdout.decode('utf-8').split('\n')

    for t in tags:
        i = t.find(oldversion)
        if i != -1:
            guessed_oldtag = t
        if t == oldversion or t == "v" + oldversion:
            oldtag = t
        i = t.find(newversion)
        if i != -1:
            guessed_newtag = t
        if t == newversion or t == "v" + newversion:
            newtag = t

    if oldtag == "":
        oldtag = guessed_oldtag
    if newtag == "":
        newtag = guessed_newtag

    p = run(["git", "-C", "results/" + tarball.name, "log", "--no-merges", oldtag + ".." + newtag], stdout=PIPE)
    fulllog = p.stdout.decode('utf-8').split('\n')
    # 'git shortlog' can accept any 'git log' output over stdin, so make sure
    # it lacks merge commits, too.
    p = run(["git", "-C", "results/" + tarball.name, "shortlog"], input=p.stdout, stdout=PIPE)
    shortlog = p.stdout.decode('utf-8').split('\n')

    if len(fulllog) < 15:
        return fulllog
    else:
        return shortlog


def guess_commit_message(keyinfo):
    """Parse newsfile for a commit message.

    Try and find a sane commit message for the newsfile. The commit message defaults to the
    following for an updated version if no CVEs are fixed:

    <tarball name>: Autospec creation for update from version <old> to version <new>

    If CVEs are fixed:

    <tarball name>: Fix for <cve>

    And if the version does not change:

    <tarball name>: Autospec creation for version <version>

    Additional information is appended to the commitmessage depending on NEWS
    and ChangeLog files and the presence of CVEs. The commitmessage is written
    to a file at <download path>/commitmsg.
    """
    cvestring = ""
    cves = set()
    commitmessage = []
    for cve in config.cves:
        cves.add(cve)
        cvestring += " " + cve

    # default commit messages before we get too smart
    if config.old_version is not None and config.old_version != tarball.version:
        commitmessage.append("{}: Autospec creation for update from version {} to version {}"
                             .format(tarball.name, config.old_version, tarball.version))
        if tarball.giturl != "":
            gitmsg = process_git(tarball.giturl, config.old_version, tarball.version)
            commitmessage.append("")
            commitmessage.extend(gitmsg)
    else:
        if cves:
            commitmessage.append("{}: Fix for {}"
                                 .format(tarball.name, cvestring.strip()))
        else:
            commitmessage.append("{}: Autospec creation for version {}"
                                 .format(tarball.name, tarball.version))
    commitmessage.append("")

    # Only use Changelog if the giturl isn't defined as it is often
    # duplicate content from the git log.
    if tarball.giturl:
        newsfiles = ["NEWS"]
    else:
        newsfiles = ["NEWS", "ChangeLog"]
    for newsfile in newsfiles:
        # parse news files for relevant version updates and cve fixes
        newcommitmessage, newcves = process_NEWS(newsfile)
        commitmessage.extend(newcommitmessage)
        cves.update(newcves)

    if cves:
        # make the package security sensitive if a CVE was patched
        config.config_opts['security_sensitive'] = True
        config.rewrite_config_opts(build.base_path)
        # append CVE fixes to end of commit message
        commitmessage.append("CVEs fixed in this build:")
        commitmessage.extend(sorted(list(cves)))
        commitmessage.append("")

    if keyinfo:
        commitmessage.append("Key imported:\n{}".format(keyinfo))

    util.write_out(os.path.join(build.download_path, "commitmsg"),
                   "\n".join(commitmessage) + "\n")

    print("Guessed commit message:")
    try:
        print("\n".join(commitmessage))
    except Exception:
        print("Can't print")
