#!/bin/true
#
# util.py - part of autospec
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

import hashlib
import os
import re
import shlex
import subprocess
import sys

dictionary_filename = os.path.dirname(__file__) + "/translate.dic"
dictionary = [line.strip() for line in open(dictionary_filename, 'r')]
os_paths = None
ERROR_FILE = 'pumpAutospec'
ERROR_ENV = 'AUTOSPEC_UPDATE'


def _log_error(error):
    write_out(ERROR_FILE, f"{error}\n", mode='a')


def _commit_result():
    if not os.path.isfile(ERROR_FILE):
        return
    call(f"git add {ERROR_FILE}", check=False, stderr=subprocess.DEVNULL)
    call(f"git commit {ERROR_FILE} -m 'Notes update'", check=False, stderr=subprocess.DEVNULL)
    call("git push", check=False, stderr=subprocess.DEVNULL)


def _process_line(line, prev_line, current_patch, reported_patches, error):
    if m := re.match('^Patch #[0-9]+ .(?P<patch>.*).:', line):
        current_patch[0] = m.group('patch')

    if m := re.match('Hunk #[0-9]+ FAILED at [0-9]+', line):
        if current_patch[0] not in reported_patches:
            _log_error("Patch " + current_patch[0] + " does not apply")
            reported_patches[current_patch[0]] = True
            return True

    if m := re.match(".*can't find file to patch at input line ", line):
        if current_patch[0] not in reported_patches:
            _log_error("Patch " + current_patch[0] + " does not apply")
            reported_patches[current_patch[0]] = True
            return True

    if m := re.match('.*meson.build:[0-9]+:[0-9]+: ERROR: Unknown options: "(?P<option>.*)"', line):
        _log_error("Unknown meson option: " + m.group('option'))
        return True

    if m := re.match('Error: package ‘(?P<module>.*)’ .* was found, but', line):
        _log_error("R package " + m.group('module') + " not found")
        return True

    if m := re.match('.*CMake Error at .*/CMake', prev_line):
        if m := re.match('(?P<module>.*) not found', line):
            _log_error("CMake module " + m.group('module') + "not found")
            return True

    if m := re.match(r'go: download.*connect: connection refused', line):
        _log_error("Go online update")
        return True

    if 'Updating crates.io index' in line:
        _log_error("Rust crates.io online update")
        return True

    if "error: '__builtin_ctzs' needs isa option -mbmi" in line:
        _log_error(" error: '__builtin_ctzs' needs isa option -mbmi")
        return True

    if "error:" in line and 'Bad exit status from' not in line:
        m = re.match('.*error:(?P<error>.*)', line)
        if m and not error:
            _log_error("Compiler: " + m.group('error'))
            return True

    if m := re.match(r'Could NOT find (?P<package>.*) .missing', line):
        _log_error("CMake module " + m.group('package') + " not found")
        return True
    if m := re.match(r'Could not find a package configuration file provided by (?P<package>.*) with', line):
        _log_error("CMake module " + m.group('package') + " not found")
        return True
    # Unable to find program 'gperf'
    if m := re.match(r"Failed to find program ‘(?P<module>.*)’", line):
        _log_error("Failed to find " + m.group('module'))
        return True
    if m := re.match(r"Failed to find ‘(?P<module>.*)’", line):
        _log_error("Failed to find " + m.group('module'))
        return True

    return False


def _process_build_log(filename):
    with open_auto(filename, "r") as lfile:
        lines = lfile.readlines()

    prev_line = ''
    current_patch = ['']
    reported_patches = {}
    error = False
    for line in lines:
        if _process_line(line, prev_line, current_patch, reported_patches, error):
            error = True
        prev_line = line

    if error:
        _commit_result()


def call(command, logfile=None, check=True, **kwargs):
    """Subprocess.call convenience wrapper."""
    returncode = 1
    full_args = {
        "args": shlex.split(command),
        "universal_newlines": True,
    }
    full_args.update(kwargs)

    if logfile:
        full_args["stdout"] = open(logfile, "w")
        full_args["stderr"] = subprocess.STDOUT
        returncode = subprocess.call(**full_args)
        full_args["stdout"].close()
    else:
        returncode = subprocess.call(**full_args)

    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, full_args["args"], None)

    return returncode


def _file_write(self, s):
    s = s.strip()
    if not s.endswith("\n"):
        s += "\n"
    self.write(s)


def translate(package):
    """Convert terms to their alternate definition."""
    global dictionary
    for item in dictionary:
        if item.startswith(package + "="):
            return item.split("=")[1]
    return package


def do_regex(patterns, re_str):
    """Find a match in multiple patterns."""
    for p in patterns:
        match = re.search(p, re_str)
        if match:
            return match


def get_contents(filename):
    """Get contents of filename."""
    with open(filename, "rb") as f:
        return f.read()
    return None


def get_sha1sum(filename):
    """Get sha1 sum of filename."""
    sh = hashlib.sha1()
    sh.update(get_contents(filename))
    return sh.hexdigest()


def _supports_color():
    # FIXME: check terminfo instead
    return sys.stdout.isatty()


def _print_message(message, level, color=None):
    prefix = level
    if color and _supports_color():
        # FIXME: use terminfo instead
        if color == 'red':
            params = '31;1'
        elif color == 'green':
            params = '32;1'
        elif color == 'yellow':
            params = '33;1'
        elif color == 'blue':
            params = '34;1'
        prefix = f'\033[{params}m{level}\033[0m'
    print(f'[{prefix}] {message}')


def print_error(message):
    """Print error, color coded for TTYs."""
    _print_message(message, 'ERROR', 'red')


def print_build_failed():
    """Print final fatal error, color coded for TTYs."""
    _print_message('Build failed, aborting', 'FATAL', 'red')
    try:
        if os.environ.get(ERROR_ENV):
            _process_build_log('results/build.log')
    except Exception:
        pass


def print_fatal(message):
    """Print fatal error, color coded for TTYs."""
    _print_message(message, 'FATAL', 'red')
    if os.environ.get(ERROR_ENV):
        write_out(ERROR_FILE, f"{message}\n", mode='a')
        _commit_result()


def print_warning(message):
    """Print warning, color coded for TTYs."""
    _print_message(message, 'WARNING', 'red')


def print_info(message):
    """Print informational message, color coded for TTYs."""
    _print_message(message, 'INFO', 'yellow')


def print_success(message):
    """Print success message, color coded for TTYs."""
    _print_message(message, 'SUCCESS', 'green')


def binary_in_path(binary):
    """Determine if the given binary exists in the provided filesystem paths."""
    global os_paths
    if not os_paths:
        os_paths = os.getenv("PATH", default="/usr/bin:/bin").split(os.pathsep)

    for path in os_paths:
        if os.path.exists(os.path.join(path, binary)):
            return True
    return False


def write_out(filename, content, mode="w"):
    """File.write convenience wrapper."""
    with open_auto(filename, mode) as require_f:
        require_f.write(content)


def open_auto(*args, **kwargs):
    """Open a file with UTF-8 encoding.

    Open file with UTF-8 encoding and "surrogate" escape characters that are
    not valid UTF-8 to avoid data corruption.
    """
    # 'encoding' and 'errors' are fourth and fifth positional arguments, so
    # restrict the args tuple to (file, mode, buffering) at most
    assert len(args) <= 3
    assert 'encoding' not in kwargs
    assert 'errors' not in kwargs
    return open(*args, encoding="utf-8", errors="surrogateescape", **kwargs)


def globlike_match(filename, match_name):
    """Compare the filename to the match_name in a way that simulates the shell glob '*'."""
    fsplit = filename.split('/')
    if len(fsplit) != len(match_name):
        return False
    match = True
    for fpart, mpart in zip(fsplit, match_name):
        if fpart != mpart:
            if '*' not in mpart:
                match = False
                break
            if len(mpart) > len(fpart) + 1:
                match = False
                break
            mpl, mpr = mpart.split('*')
            try:
                if fpart.index(mpl) != 0:
                    match = False
                    break
                if fpart.rindex(mpr) != len(fpart) - len(mpr):
                    match = False
                    break
            except ValueError:
                match = False
                break
    return match
