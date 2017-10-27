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

import re

# TODO: VAR_append = "" _append same functionality as +=
operators_dict = {
    "=": "{1}",
    "=.": "{1}{0}",
    ".=": "{0}{1}",
    ":=": "{1}",
    "=+": "{1} {0}",
    "+=": "{0} {1}",
    "??=": "{1}",
    "?=": "{1}"
}


def scrape_version(fname, bb_dict):
    # get version from filename if it exists
    try:
        bb_dict['VERSION'] = fname.split('_', 1,)[1].rsplit('.', 1)[0]
    except IndexError:
        print('file has no version: {}')

    return bb_dict


def replace_pv(bb_dict):
    for k, v in bb_dict.items():
        if "${PV}" in v and "VERSION" in bb_dict:
            bb_dict[k] = v.replace("${PV}", bb_dict.get('VERSION'))


def clean_values(value):
    # remove beginning and end quote
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]

    return value


def update_inherit(line, bb_dict):
    if 'inherits' in bb_dict:
        bb_dict['inherits'].append(' '.join(line.split(' ', 1)[1:]))
    else:
        bb_dict['inherits'] = line.split(' ', 1)[1:]


def read_in_command(line, depth, buf):
    for c in line:
        if c == '{':
            depth += 1
        if c == '}' and depth > 0:
            depth -= 1
        if c != "\n":
            buf += c
    return buf, depth


def pattern_match_line(line):

    operators = ["??=", "?=", ":=", "+=",
                 "=+", ".=", "=.", "="]

    for i, e in enumerate(operators):
        operators[i] = '\\' + '\\'.join(e)

    # Split line to be [Key, operator, value] if in operators list
    oper_pattern = r"(^[A-Z]+[_\-${}\[\]A-Za-z0-9]*)\s(" + '|'.join(
        operators) + r")\s(\".*\")"

    return re.compile(oper_pattern).search(line)


def evaluate_expr(op, cur_val, assignment):
    if not cur_val:
        return assignment
    return operators_dict.get(op).format(cur_val, assignment)


def write_to_dict(bb_dict, m):

    if len(m.groups()) == 3:
        key = m.group(1)
        value = clean_values(m.group(3))
        op = m.group(2)

        #
        # ??= is the weakest variable assignment, so if that variable already
        # has an assignment, do not overwrite it. = has the highest precedence
        # and ?= is between the two.
        #
        if key in bb_dict and op == "??=":
            return bb_dict
        elif key in bb_dict and op == "?=":
            if not isinstance(bb_dict[key], list):
                return bb_dict

        if key in bb_dict and isinstance(bb_dict[key], list):
            v = bb_dict[key]
            del [v[1]]
            bb_dict[key] = "".join(v)
        try:
            bb_dict[key] = evaluate_expr(op, bb_dict.get(key), value)
            if op == "??=":
                bb_dict[key] = [bb_dict[key], 1]
        except AttributeError as error:
            print("Missing operation functionality: {}".format(error))
            return None

    return bb_dict


def bb_scraper(bb):

    bb_dict = {}
    todo = []

    bb_dict = scrape_version(bb, bb_dict)

    with open(bb, 'r') as bb_fp:
        cont = None
        for line in bb_fp:
            # do not parse empty strings and comments
            if line.strip() and not line.strip().startswith('#'):
                line = line.strip()

                # If line is a command, create raw string of the command
                # TODO: command could be python code
                if not cont and line.startswith('do_'):
                    cmd_name = line.split('()')[0].strip()
                    cont = ''
                    depth = 0
                    count = 0
                    while 1:
                        count += 1
                        cont, depth = read_in_command(line, depth, cont)
                        if depth == 0:
                            break
                        else:
                            line = next(bb_fp)

                    bb_dict[cmd_name] = cont
                    cont = None
                    continue

                # if line is a continuation, append to single line
                elif not cont and line[-1] == '\\':
                    cont = ""
                    while 1:
                        cont += line
                        line = next(bb_fp).strip('\n')
                        if line[-1] != '\\':
                            cont += line
                            break

                    line = cont
                    cont = None

                if line.startswith('inherit'):
                    update_inherit(line, bb_dict)
                    continue

                match = pattern_match_line(line)
                if match:
                    bb_dict = write_to_dict(bb_dict, match)
                else:
                    todo.append(line)

    # for k, v in bb_dict.items():
    #     print(k)

    replace_pv(bb_dict)
    return bb_dict


def update_summary(bb_dict, specfile):
    k = "default_sum"
    v = "No detailed summary available"

    if hasattr(specfile, k) and getattr(specfile, k) == v:
        for i in ['SUMMARY', 'DESCRIPTION']:
            if i in bb_dict:
                setattr(specfile, k, bb_dict.get(i))
                break


def update_build_deps(bb_dict, specfile):
    deps = set()
    for dep in bb_dict.get('DEPENDS').split():
        dep = re.match(r"(\$\{PYTHON_PN\}\-)?([a-zA-Z0-9\-]+)", dep).group(2)
        if dep.endswith('-native'):
            dep = dep[:-7]
        deps.add(dep)

    spec_deps = getattr(specfile, 'buildreqs')
    setattr(specfile, 'buildreqs', spec_deps.union(deps))


def update_specfile(specfile, bb_dict):

    # update the package summary if one does not exist
    update_summary(bb_dict, specfile)

    # union the current set of buildreqs in the specfile to the bb ones
    update_build_deps(bb_dict, specfile)


def parse_bb(bb, specfile):

    bb_dict = bb_scraper(bb)
    update_specfile(specfile, bb_dict)

    return specfile


def parse_inc(bb, specfile):
    return parse_bb(bb, specfile)
