#!/usr/bin/true
#
# download.py - part of autospec
# Copyright (C) 2018 Intel Corporation
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
import sys
from io import BytesIO

import pycurl
from util import print_fatal


def do_curl(url, dest=None, post=None, is_fatal=False):
    """
    Perform a curl operation for `url`.

    If `post` is set, a POST is performed for `url` with fields taken from the
    specified value. Otherwise a GET is performed for `url`. If `dest` is set,
    the curl response (if successful) is written to the specified path and the
    path is returned. Otherwise a successful response is returned as a BytesIO
    object. If `is_fatal` is `True` (`False` is the default), a GET failure,
    POST failure, or a failure to write to the path specified for `dest`
    results in the program exiting with an error. Otherwise, `None` is returned
    for any of those error conditions.
    """
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    if post:
        c.setopt(c.POSTFIELDS, post)
    c.setopt(c.FOLLOWLOCATION, True)
    c.setopt(c.FAILONERROR, True)
    c.setopt(c.CONNECTTIMEOUT, 10)
    c.setopt(c.TIMEOUT, 600)
    c.setopt(c.LOW_SPEED_LIMIT, 1)
    c.setopt(c.LOW_SPEED_TIME, 10)
    buf = BytesIO()
    c.setopt(c.WRITEDATA, buf)
    try:
        c.perform()
    except pycurl.error as e:
        if is_fatal:
            print_fatal("Unable to fetch {}: {}".format(url, e))
            sys.exit(1)
        return None
    finally:
        c.close()

    # write to dest if specified
    if dest:
        try:
            with open(dest, 'wb') as fp:
                fp.write(buf.getvalue())
        except IOError as e:
            if os.path.exists(dest):
                os.unlink(dest)
            if is_fatal:
                print_fatal("Unable to write to {}: {}".format(dest, e))
                sys.exit(1)
            return None

    if dest:
        return dest
    else:
        return buf
