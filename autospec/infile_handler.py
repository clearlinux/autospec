#!/usr/bin/true
#
# infile_parser.py - part of autospec
# Copyright (C) 2017 Intel Corporation
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

import os
import re
import tempfile
from urllib.request import urlretrieve

import infile_bb_parser

import requests

import util


# filetypes and their parse order (lower parsed first)
parsable_filetypes = {'.inc': 1, '.bb': 2}


def parse_ext(path):
    """
    Check if a file can be parsed based on its extension.

    Gets the extension of a file and determines if the filetype can be handled
    by the infile_parser. If so, it returns the extension. If not, it returns
    nothing, which will cause the file_handler to return and infile parsing
    will NOT be used on that file.
    """
    ext = os.path.splitext(path)[1]
    if ext not in parsable_filetypes:
        util.print_warning("Cannot parse infile \"{}\" type. From input: {}."
                           " \nContinuing with the execution of "
                           "autospec".format(ext, path))
        return None

    return ext.lstrip('.')


def check_url_content(url):
    """
    Check that the url to the infile file is raw or in plaintext.

    This function checks the header content-type for a request to the infile
    url. If it is html it converts eith a github url to point to the raw file,
    a git url to point to the plaintext file, or returns None with a statement
    that the file must be in plaintext or raw.
    """
    if "text/html" in requests.head(url).headers['content-type']:
        if re.match(r'^(http)s?://github.com(.*)', url):
            url = url.replace("github", "raw.githubusercontent").replace("blob/", "")
        elif 'git' in url and "/tree/" in url:
            url = url.replace("/tree/", "/plain/", 1)
        else:
            util.print_fatal("infile url has an html content-type, "
                             "please use plaintext.")
            return None

    return url


def sort_files(x):
    """Sorts files depending on their priority in the parsable_filetypes dict."""
    return parsable_filetypes.get(os.path.splitext(x)[1])


def parse_infile(bb_fp, output_dict, parse_type):
    """Scrape and parse the infile file returning the dictionary of collected data based on its type."""
    if parse_type == "bb":
        return infile_bb_parser.bb_scraper(bb_fp, output_dict)
    elif parse_type == "inc":
        return infile_bb_parser.bb_scraper(bb_fp, output_dict)


def file_handler(indata, output_dict):
    """
    File or url parsing frontend.

    This function determines whether the input is a file or a url. If it is a
    url it checks that it is in the correct format (plaintext), downloads the
    url to a temporary file and passes the file handler to be scraped.
    If the input is a file, then it opens the file and passes the handler to
    be scraped.

    The type of parsing bitbake, inc, deb, etc is based on the file extension.
    """
    # If ext is not parsable, return from using infile parser on that file.
    parse_type = parse_ext(indata)
    if not parse_type:
        return

    if output_dict.get('filename'):
        output_dict['filename'].append(indata)
    else:
        output_dict['filename'] = [indata]

    if not os.path.isfile(indata):
        # check that input is plain or raw text and not html
        indata = check_url_content(indata)
        with tempfile.NamedTemporaryFile() as tmpfile:
            try:
                tmp, _ = urlretrieve(indata, tmpfile.name)
                with open(tmp, 'r') as bb_fp:
                    output_dict = parse_infile(bb_fp, output_dict, parse_type)
            except Exception as e:
                util.print_warning("Infile was unable to be parsed with the "
                                   "error: \"{}\". \nContinuing with the "
                                   "execution of autospec.".format(e))
    else:
        with open(indata, 'r') as bb_fp:
            output_dict = parse_infile(bb_fp, output_dict, parse_type)
    return output_dict


def infile_reader(indata, name):
    """
    Parse an infile.

    The infile parser can take 3 different inputs:
      A url to a file
      A directory with multiple files or urls
      A path or filename

    Each file in the directory should scraped to the same dictionary instance.
    """
    output_dict = {"NAME": name}

    if os.path.isdir(indata):
        files = [f for f in os.listdir(indata) if os.path.isfile(
            os.path.join(indata, f)) and not f.startswith('.')]
        for f in sorted(files, key=sort_files):
            output_dict = file_handler(os.path.join(indata, f), output_dict)
    else:
        output_dict = file_handler(indata, output_dict)

    return output_dict
