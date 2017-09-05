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
    using repoquery what-requires and --recursive commands
    """

    # clean up yum cache to avoid 'no more mirrors repo' error
    subprocess.check_output(['yum', '--config', config.yum_conf,
                             'clean', 'all'])

    try:
        out = subprocess.check_output(['repoquery', '--config', config.yum_conf,
                                       '--archlist=src', '--recursive',
                                       '--whatrequires', pkg]).decode('utf-8')

    except subprocess.CalledProcessError as err:
        util.print_warning("repoquery whatrequires for {} failed with: {}".format(pkg, err))
        return

    if 'filesystem' in out:
        util.print_warning("Package contains filesystem as a whatrequires.\n" +
                           "BE CAREFUL building {}; may require full OS rebuild.\n".format(pkg))

    util.write_out('whatrequires',
            "# This file contains recursive sources that require this package\n" + \
            out)
