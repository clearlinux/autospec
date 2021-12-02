#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile

import download


def pip_env():
    """Generate a copy of os.environ appropriate for pip."""
    env = os.environ.copy()
    env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
    return env


def pkg_search(name):
    """Query the pypi json API for name and return True if found."""
    query = f"https://pypi.org/pypi/{name}/json/"
    resp = download.do_curl(query)
    if resp is not None:
        return True
    else:
        return False


def get_pypi_name(name, miss=False):
    """Try and verify the pypi name for a given package name."""
    # normalize the name for matching as pypi is case insensitve for search
    name = name.lower().replace('-', '_')
    # Common case is the name and the pypi name match
    if pkg_search(name):
        return name
    # Maybe we have a prefix
    for prefix in ["pypi_", "python_"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            if pkg_search(name):
                return name
    # Some cases where search fails (Sphinx)
    # Just try the name we were given
    if miss:
        return ""
    return name


def get_pypi_metadata(name):
    """Get metadata for a pypi package."""
    show = []
    # Create virtenv to do the pip install (needed for pip show)
    with tempfile.TemporaryDirectory() as tdir:
        proc = subprocess.run(["virtualenv", "--no-periodic-update", tdir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return ""
        proc = subprocess.run(f"source bin/activate && pip install {name}", cwd=tdir, shell=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              env=pip_env())
        if proc.returncode != 0:
            return ""
        with tempfile.TemporaryFile() as tfile:
            proc = subprocess.run(f"source bin/activate &> /dev/null && pip show {name}",
                                  cwd=tdir, shell=True,
                                  stdout=tfile.fileno(), stderr=subprocess.DEVNULL,
                                  env=pip_env())
            if proc.returncode != 0:
                return ""
            tfile.seek(0)
            show = tfile.read().decode('utf-8', errors='surrogateescape').splitlines()
    # Parse pip show for relevent information
    metadata = {}
    for line in show:
        if line.startswith("Name: "):
            # 'Name: pypi-name'
            # normalize names -> lowercase and dash to underscore
            metadata["name"] = line.split()[1].lower().replace('-', '_')
        elif line.startswith("Summary: "):
            # 'Summary: <description of the package>'
            try:
                metadata["summary"] = line.split(maxsplit=1)[1]
            except IndexError:
                # No Summary (haven't seen this case before though)
                metadata["summary"] = ""
        elif line.startswith("Requires: "):
            # 'Requires: dep1, dep2
            # normalize names -> lowercase and dash to underscore
            try:
                reqs = [item.strip().lower().replace('-', '_') for item in line.split(maxsplit=1)[1].split(",")]
            except IndexError:
                # No Requires
                reqs = []
            metadata["requires"] = reqs

    return json.dumps(metadata)


def main():
    """Standalone pypi metadata query entry point."""
    pkg_name = sys.argv[1]
    pypi_name = get_pypi_name(pkg_name)
    if not pypi_name:
        print(f"Couldn't find {pkg_name} in pypi")
        sys.exit(1)
    pypi_metadata = get_pypi_metadata(pypi_name)
    print(pypi_metadata)


if __name__ == '__main__':
    main()
