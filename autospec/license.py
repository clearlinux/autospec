#!/bin/true
#
# license.py - part of autospec
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
# Deduce the upstream version from the package content
# based on both license file pattern matching and
# exact matches on hashes of the COPYING file
#

import sys
import os
import tarball
import pycurl
import urllib
import config
from io import BytesIO

from util import print_fatal, print_warning

default_license = "TO BE DETERMINED"

LICENSE_HASH_FILE = "common/licenses"

licenses = []

license_translations = {
    "GPL-2.0": "GPL-2.0",
    "GPLv2": "GPL-2.0",
    "GPLV2": "GPL-2.0",
    "GPLV3": "GPL-3.0",
    "GPL-2": "GPL-2.0",
    "GPL-2+": "GPL-2.0+",
    "GPL-2.0+": "GPL-2.0+",
    "GPLv2+": "GPL-2.0+",
    "GPL(>=2)": "GPL-2.0+",
    "GPL(>=-2)": "GPL-2.0+",
    "LGPL(>=2)": "LGPL-2.0+",
    "LGPL(>=-2)": "LGPL-2.0+",
    "LGPLv2": "LGPL-2.0",
    "LGPLv2.1": "LGPL-2.1",
    "LGPLv2+": "LGPL-2.1+",
    "LGPL-2.0+": "LGPL-2.0+",
    "LGPL-2.1": "LGPL-2.1",
    "LGPLv2.1": "LGPL-2.1",
    "LGPL-2.1+": "LGPL-2.1+",
    "LGPLv2.1+": "LGPL-2.1+",
    "LGPLv3+": "LGPL-3.0+",
    "LGPLv3": "LGPL-3.0",
    "GPL(>=-2.0)": "GPL-2.0+",
    "GPL-3.0": "GPL-3.0",
    "GPLv3": "GPL-3.0",
    "gplv3": "GPL-3.0",
    "GPL-3": "GPL-3.0",
    "GPL-3+": "GPL-3.0",
    "LGPL-3": "LGPL-3.0",
    "zlib": "Zlib",
    "ZLIB": "Zlib",
    "zlib/libpng": "zlib-acknowledgement",
    "Boost": "BSL-1.0",
    "GPL-3.0+": "GPL-3.0+",
    "GPLv3+": "GPL-3.0+",
    "GPL3": "GPL-3.0",
    "GPL(>=3)": "GPL-3.0+",
    "http://opensource.org/licenses/MIT": "MIT",
    "mit": "MIT",
    "http://www.apache.org/licenses/LICENSE-2.0": "Apache-2.0",
    "Apache License, Version 2.0": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "APL2.0": "Apache-2.0",
    "APL2": "Apache-2.0",
    "ASL 2.0": "Apache-2.0",
    "ASL-2.0": "Apache-2.0",
    "APL-2.0": "Apache-2.0",
    "ASL-2": "Apache-2.0",
    "Apache2.0": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "Apache": "Apache-2.0",
    "apache": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "artistic_2": "Artistic-2.0",
    "MPLv1.1": "MPL-1.1",
    "MPL-2": "MPL-2.0",
    "MPL2": "MPL-2.0",
    "MPLv2.0": "MPL-2.0",
    "MPLv2.0,": "MPL-2.0",
    "ZPL 2.1": "ZPL-2.1",
    "ZPL": "ZPL-2.0",
    "http://creativecommons.org/licenses/BSD/": "BSD-2-Clause",
    "BSD_3_clause": "BSD-3-Clause",
    "perl": "Artistic-1.0-Perl",
    "PSF": "Python-2.0",
    "Python": "Python-2.0",
    "BSD_2_clause": "BSD-2-Clause",
    "Expat": "MIT",
    "w3c": "W3C",
    "VIM": "Vim",
    "CC0": "CC0-1.0"
}

license_blacklist = {
    "and": True,
    "BSD": True,
    "3BSD": True,
    "LGPL": True,
    "GPL": True,
    "ASL": True,
    "2.0": True,
    "advertising": True,
    "LGPL+BSD": True,
    "UN": True,
    "GNU": True,
    "new": True,
    "none": True,
    "License": True,
    "License": True,
    "license": True,
    "Standard": True,
    "PIL": True,
    "Software": True,
    "|": True,
    "+": True,
    "UNKNOWN": True,
    "unknown": True,
    "BSD-like": True,
    "or": True,
    "Modified": True,
    "3-clause": True,
    "Unlimited": True,
    "BSD_3_clause": True,
    "BSD(3": True,
    "clause)": True,
    "GFDL": True,
    "MPL": True,
    "Muddy-MIT": True,
    "LGPL/MIT": True,
    "License,": True,
    "Lucent": True,
    "Public": True,
    "LICENCE": True,
    "-": True,
    "See": True,
    "details": True,
    "for": True,
    "Version-2.0": True,
    "exceptions": True,
    "http://nmap.org/man/man-legal.html": True,
    "with": True,
    "style": True,
    "Foundation": True,
    "~": True,
    "open_source": True,
    "BSDish": True,
    "EPL": True,
    "Artistic": True,
    "(specified": True,
    "using": True,
    "classifiers)": True,
    "APL-2.0": True,
    "dual": True,
    ".git": True,
    ".mit": True,
    "GPL/BSD": True,
    "GPLv2.1": True,
    "version-2": True,
    "public": True,
    "domain": True,
    "Commercial": True,
    "ndg/httpsclient/LICENCE": True,
    "License-2.0": True,
    "BSD-style": True,
    "Licences": True,
    "New": True,
    "License(==-2.0)": True,
}


def add_license(lic):
    global licenses
    lic = lic.strip()

    # Bail if the license isn't one we recognize, is a blacklisted word or has already been added
    if lic in licenses:
        return False
    if lic in license_blacklist:
        return False
    if lic not in license_translations:
        licenses.append(lic)
        return True
    if license_translations[lic] in licenses:
        return False

    licenses.append(license_translations[lic])
    return True


def license_from_copying_content(copying):
    with open(copying, 'r', encoding="latin-1") as content_file:
        content = content_file.read()
    if content.find("Version 2, June 1991") >= 0:
        add_license("GPL-2.0")
    if content.find("Version 3, 29 June 2007") >= 0:
        add_license("GPL-3.0")
    if content.find("Version 2.1, February 1999") >= 0:
        add_license("LGPL-2.1")
    if content.find("Source Code is licensed under MIT license") >= 0:
        add_license("MIT")
    if content.find("Version 2.0, January 2004") >= 0:
        add_license("Apache-2.0")


def license_from_copying_hash(copying):
    """Add licenses based on the hash of the copying file"""
    licenses_list = []
    hash_sum = tarball.get_sha1sum(copying)

    licenses_dict = dict()

    if config.license_fetch:
        with open(copying, "r", encoding="latin-1") as myfile:
            data = myfile.read()
            values = {'hash': hash_sum, 'text': data, 'package': tarball.name}
            data = urllib.parse.urlencode(values)
            data = data.encode('utf-8')

            buffer = BytesIO()
            c = pycurl.Curl()
            c.setopt(c.URL, config.license_fetch)
            c.setopt(c.WRITEDATA, buffer)
            c.setopt(c.POSTFIELDS, data)
            c.perform()
            c.close()

            response = buffer.getvalue()
            the_page = response.decode('utf-8')

            if len(the_page.strip()) > 0:
                print("License     : ", the_page.strip(), " (server) (", hash_sum, ")")
                add_license(the_page.strip())
                return
    else:
        if os.path.exists(LICENSE_HASH_FILE):
            with open(LICENSE_HASH_FILE, "r") as file:
                licenses_list = file.readlines()
        licenses_dict = dict(license.split(" | ") for license in licenses_list)

    if hash_sum in licenses_dict:
        add_license(licenses_dict[hash_sum])
    else:
        if not config.license_show:
            return
        print_warning("Unknown license {0} with hash {1}".format(copying, hash_sum))
        hashUrl = config.license_show % {'HASH': hash_sum}
        print_warning("Visit {0} to enter".format(hashUrl))


def license_from_doc(doc):
    """ Scan for documentation license in the given file """
    with open(doc, 'r', encoding="latin-1") as content_file:
        content = content_file.read()
    if content.find("GNU Free Documentation License, Version 1.3") >= 0:
        add_license("GFDL-1.3")
    elif content.find("GNU Free Documentation License, Version 1.2") >= 0:
        add_license("GFDL-1.2")
    elif content.find("GNU Free Documentation License, Version 1.1") >= 0:
        add_license("GFDL-1.1")
    elif content.find("(The MIT License)") >= 0:
        add_license("MIT")


#
# Scan the project directory for things we can use to guess a description
# and summary
#

def scan_for_licenses(package, dir):
    for dirpath, dirnames, files in os.walk(dir):
        for name in files:
            if (name.lower() in ("copyright", "copyright.txt", "apache-2.0", "libcurllicense", "gpl.txt", "gplv2.txt", "notice", "copyrights", "about_bsd.txt") or
               name.lower().startswith("copying") or name.lower().startswith("license") or name.lower().endswith("license") or name.lower().startswith("licence") or name.lower().endswith("licence")):
                license_from_copying_hash(os.path.join(dirpath, name))
                license_from_copying_content(os.path.join(dirpath, name))
            else:
                if "." not in name:
                    continue
                ext = name.split(".")[-1].lower()
                if ext in ("man", "texi", "rdoc"):
                    license_from_doc(os.path.join(dirpath, name))

    if len(licenses) == 0:
        print_fatal(" Cannot find any license or " + tarball.name + ".license file!\n")
        sys.exit(1)
    else:
        print("Licenses    : ", " ".join(sorted(licenses)))


def load_specfile(specfile):
    lics = licenses if licenses else [default_license]
    specfile.licenses = lics
