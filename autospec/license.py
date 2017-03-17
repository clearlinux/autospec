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
import re
import tarball
import pycurl
import urllib
import config
from io import BytesIO

from util import print_fatal, print_warning

default_license = "TO BE DETERMINED"

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

license_blacklist = [
    "and",
    "BSD",
    "3BSD",
    "LGPL",
    "GPL",
    "ASL",
    "2.0",
    "advertising",
    "LGPL+BSD",
    "UN",
    "GNU",
    "new",
    "none",
    "License",
    "license",
    "Standard",
    "PIL",
    "Software",
    "|",
    "+",
    "UNKNOWN",
    "unknown",
    "BSD-like",
    "or",
    "Modified",
    "3-clause",
    "Unlimited",
    "BSD_3_clause",
    "BSD(3",
    "clause)",
    "GFDL",
    "MPL",
    "Muddy-MIT",
    "LGPL/MIT",
    "License,",
    "Lucent",
    "Public",
    "LICENCE",
    "-",
    "See",
    "details",
    "for",
    "Version-2.0",
    "exceptions",
    "http://nmap.org/man/man-legal.html",
    "with",
    "style",
    "Foundation",
    "~",
    "open_source",
    "BSDish",
    "EPL",
    "Artistic",
    "(specified",
    "using",
    "classifiers)",
    "APL-2.0",
    "dual",
    ".git",
    ".mit",
    "GPL/BSD",
    "GPLv2.1",
    "version-2",
    "public",
    "domain",
    "Commercial",
    "ndg/httpsclient/LICENCE",
    "License-2.0",
    "BSD-style",
    "Licences",
    "New",
    "License(==-2.0)",
    "1.0",
    "Version"
]


def add_license(lic):
    """
    Add license from license string lic after checking for duplication or
    presence in the blacklist.
    """
    global licenses
    lic = lic.strip()

    # Translate the license if a translation exists
    real_lic = license_translations.get(lic, lic)
    # Return False if not adding to licenses
    if real_lic in licenses or real_lic in license_blacklist:
        return False

    licenses.append(real_lic)
    return True


def license_from_copying_content(copying):
    """
    Scan the copying file for strings indicating which license it represents.
    Add that license to the licenses list using add_license(lic)
    """
    with open(copying, 'r', encoding="latin-1") as content_file:
        content = content_file.read()

    cp_content_map = {"Version 2, June 1991": "GPL-2.0",
                      "Version 3, 29 June 2007": "GPL-3.0",
                      "Version 2.1, February 1999": "LGPL-2.1",
                      "Source Code is licensed under MIT license": "MIT",
                      "Version 2.0, January 2004": "Apache-2.0"}
    for cp_str, lic in cp_content_map.items():
        if cp_str in content:
            add_license(lic)


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
        page = response.decode('utf-8').strip()
        if page:
            print("License     : ", page, " (server) (", hash_sum, ")")
            add_license(page)
            return

    if hash_sum in config.license_hashes:
        add_license(config.license_hashes[hash_sum])
    else:
        if not config.license_show:
            return
        print_warning("Unknown license {0} with hash {1}".format(copying, hash_sum))
        hash_url = config.license_show % {'HASH': hash_sum}
        print_warning("Visit {0} to enter".format(hash_url))


def license_from_doc(doc):
    """ Scan for documentation license in the given file """
    with open(doc, 'r', encoding="latin-1") as content_file:
        content = content_file.read()

    doc_content_map = {
        "GNU Free Documentation License, Version 1.3": "GFDL-1.3",
        "GNU Free Documentation License, Version 1.2": "GFDL-1.2",
        "GNU Free Documentation License, Version 1.1": "GFDL-1.1",
        "(The MIT License)": "MIT"
    }

    for doc_str, lic in doc_content_map.items():
        if doc_str in content:
            add_license(lic)


def scan_for_licenses(srcdir):
    """
    Scan the project directory for things we can use to guess a description
    and summary
    """
    targets = ["copyright",
               "copyright.txt",
               "apache-2.0",
               "libcurllicense",
               "gpl.txt",
               "gplv2.txt",
               "notice",
               "copyrights",
               "about_bsd.txt"]
    # look for files that start with copying or licen[cs]e (spelling errors)
    # or end with licen[cs]e
    target_pat = re.compile(r"^((copying)|(licen[cs]e))|(licen[cs]e)$")
    for dirpath, dirnames, files in os.walk(srcdir):
        for name in files:
            if name.lower() in targets or target_pat.search(name.lower()):
                license_from_copying_hash(os.path.join(dirpath, name))
                license_from_copying_content(os.path.join(dirpath, name))
            else:
                if "." not in name:
                    continue
                ext = name.split(".")[-1].lower()
                if ext in ("man", "texi", "rdoc"):
                    license_from_doc(os.path.join(dirpath, name))

    if not licenses:
        print_fatal(" Cannot find any license or {}.license file!\n".format(tarball.name))
        sys.exit(1)

    print("Licenses    : ", " ".join(sorted(licenses)))


def load_specfile(specfile):
    specfile.licenses = licenses if licenses else [default_license]
