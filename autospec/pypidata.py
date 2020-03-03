#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile


def pip_search(name):
    """Run a pip search for name and return True if found."""
    with tempfile.TemporaryFile() as tfile:
        proc = subprocess.run(["pip", "search", name], stdout=tfile.fileno(),
                              stderr=subprocess.DEVNULL)
        if proc.returncode:
            return False
        tfile.seek(0)
        data = tfile.read().decode('utf-8', errors='surrogateescape').splitlines()
        for line in data:
            if line.lower().startswith(f"{name} "):
                return True
    return False


def get_pypi_name(name):
    """Try and verify the pypi name for a given package name."""
    # normalize the name for matching as pypi is case insensitve for search
    name = name.lower()
    # Common case is the name and the pypi name match
    if pip_search(name):
        return name
    # Maybe we have a python- prefix
    prefix = "python-"
    if name.startswith(prefix):
        name = name[len(prefix):]
        if pip_search(name):
            return name
    # Some cases where search fails (Sphinx)
    # Just try the name we were given
    return name


def get_pypi_metadata(name):
    """Get metadata for a pypi package."""
    show = []
    # Create virtenv to do the pip install (needed for pip show)
    with tempfile.TemporaryDirectory() as tdir:
        proc = subprocess.run(["virtualenv", tdir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return ""
        proc = subprocess.run(f"source bin/activate && pip install {name}", cwd=tdir, shell=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return ""
        with tempfile.TemporaryFile() as tfile:
            proc = subprocess.run(f"source bin/activate &> /dev/null && pip show {name}",
                                  cwd=tdir, shell=True,
                                  stdout=tfile.fileno(), stderr=subprocess.DEVNULL)
            if proc.returncode != 0:
                return ""
            tfile.seek(0)
            show = tfile.read().decode('utf-8', errors='surrogateescape').splitlines()
    # Parse pip show for relevent information
    metadata = {}
    for line in show:
        if line.startswith("Name: "):
            # 'Name: pypi-name'
            metadata["name"] = line.split()[1]
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
