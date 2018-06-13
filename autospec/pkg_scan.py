#
# pkg_scan.py - part of autospec
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
import subprocess

import util
import config


def get_whatrequires(pkg):
    """
    Write list of packages that require current package to file
    using dnf repoquery what-requires and --recursive commands
    """

    # clean up dnf cache to avoid 'no more mirrors repo' error
    try:
        subprocess.check_output(['dnf', '--config', config.yum_conf,
                                 '--releasever', 'clear', 'clean', 'all'])
    except subprocess.CalledProcessError as err:
        util.print_warning("Unable to clean dnf repo: {}".format(pkg, err))
        return

    try:
        out = subprocess.check_output(['dnf', 'repoquery',
                                       '--config', config.yum_conf,
                                       '--releasever', 'clear',
                                       '--archlist=src', '--recursive', '--queryformat=%{NAME}',
                                       '--whatrequires', pkg]).decode('utf-8')

    except subprocess.CalledProcessError as err:
        util.print_warning("dnf repoquery whatrequires for {} failed with: {}".format(pkg, err))
        return

    util.write_out('whatrequires', '# This file contains recursive sources that '
                   'require this package\n' + out)
