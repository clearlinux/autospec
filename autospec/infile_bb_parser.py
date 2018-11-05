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


def scrape_version(bb_dict):
    """
    Get the package version from the bb filename.

    Return None if filename doesn't exist, or there is no version
    within the filename. Otherwise, return the version.
    """
    try:
        return bb_dict.get('filename')[-1].split('_', 1,)[1].rsplit('.', 1)[0]
    except Exception:
        return None


def replace_bb_variable_names(bb_dict):
    """
    Replace bitbake variable name with values.

    Bitbake files use various variable names defined by a string
    surrounded by ${}.
    Variables able for replacement:
        - ${PV} with version
        - ${ROS_SPN} with name, or actual value if defined in .bb
    """
    def replace_var(bb_dict, val):
        if bb_dict.get("VERSION"):
            val = val.replace("${PV}", bb_dict.get('VERSION'))

        if "ROS_SPN" in bb_dict:
            val = val.replace("${ROS_SPN}", bb_dict.get("ROS_SPN"))
        elif "NAME" in bb_dict:
            val = val.replace("${ROS_SPN}", bb_dict.get('NAME'))

        return val

    for k, v in bb_dict.items():
        if isinstance(v, list):
            for i, j in enumerate(v):
                v[i] = replace_var(bb_dict, j)
        elif isinstance(v, str):
            v = replace_var(bb_dict, v)

        bb_dict[k] = v


def get_src_url(bb_dict):
    """Return the tarball url of the package source from the bb file."""
    if bb_dict.get('SRC_URI'):
        bb_dict["URL"] = bb_dict.get("SRC_URI").split('\\')[0].split(';')[0]


def clean_values(value):
    """Remove quotations and line continuations from values."""
    # remove beginning and end quote
    value = value.strip('"')

    # remove line continuations
    value = value.replace("\\", "")

    return value


def read_in_command(line, depth):
    """
    Determine if a line is a part of a command.

    If it returns a depth of 0, then the command has been read completely
    from the file.
    """
    for c in line:
        if c == '{':
            depth += 1
        if c == '}' and depth > 0:
            depth -= 1
        if c != "\n":
            continue
    return depth


def pattern_match_regex():
    """
    Build regex patterns for a defined set of operators.

    Compile the regular expression to determine the operation being used by
    the line to perform the correct task on the variable.

    Returns the match object from searching a string
    for the correct pattern as: [key, operator, value].
    """
    # escape operators for regex handling
    operators = ["\\??\\=", "\\?\\=", "\\:\\=",
                 "\\+\\=", "\\=\\+", "\\.\\=",
                 "\\=\\.", "\\="]

    # Split line to be [Key, operator, value] if in operators list
    oper_pattern = r"(^[A-Z]+[_\-${}\[\]A-Za-z0-9]*)\s(" + '|'.join(
        operators) + r")\s(\".*\")"

    return re.compile(oper_pattern)


def evaluate_expr(op, cur_val, assignment):
    """
    Get values based on operation and context for a given expression.

    Using the operators_dict. get the correct value from the expression. This
    function returns the syntactically correct value for the bb_dict key. For
    example, if the op is "=", and the assignment is "value", the return will
    be "value". However, if the op is "+=" and the cur_value is "first", and
    the assignment is "second" this function will return the appending of
    second to first: "first second".

    :param op: The operation (The key from the operators_dict)
    :param cur_val: The current value of the key within in the bb_dict
    :param assignment: The new value from the line that will be assigned to the
    bb_dict key.
    """
    if not cur_val:
        return assignment
    return operators_dict.get(op).format(cur_val, assignment)


def write_to_dict(bb_dict, m):
    """
    Update bb_dict based on bitbake input file.

    Store the correct information to the bb_dict that is correctly parsed from
    the bitbake file. This function uses the "evaluate_expr" function heavily
    to ensure that the values are correctly parsed.
    """
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

    return bb_dict


def bb_scraper(bb_fp, bb_dict):
    """Scrapes data from a filepointer (to a bitbake or .inc file) and stores the values in a dictionary."""
    bb_dict["VERSION"] = scrape_version(bb_dict)
    bb_dict["inherits"] = []

    # compile the regex once, prior to the line parsing for faster searching
    line_regex = pattern_match_regex()

    for line in bb_fp:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # If line is a command, create array of command lines
        # TODO: command could be python code
        if line.startswith('do_'):
            cmd_name = line.split('()')[0].strip()
            cmd = []
            depth = 0
            while 1:
                depth = read_in_command(line, depth)
                if line:
                    cmd.append("# " + line)

                if depth == 0:
                    break
                else:
                    line = next(bb_fp).strip()

            # Remove the 'do_command {' and '}' from the list, so that
            # the dict value is a list of the commands.
            if cmd[0].startswith("# " + cmd_name) and cmd[-1] == '# }':
                cmd = cmd[1:-1]

            # Some bitbake files have tasks with prepend or append operations.
            # Perform the logic to store all tasks with the same 'core' command
            # name in the dictionary.
            if not bb_dict.get(cmd_name):
                bb_dict[cmd_name] = cmd
            elif cmd_name.rsplit('_') == 'prepend':
                cmd.extend(bb_dict.get(cmd_name))
                bb_dict[cmd_name] = cmd
            else:
                bb_dict.get(cmd_name).extend(cmd)

            continue

        # If a line continuation, create a string that can easily be split
        # by '\' for src_uri and other variables.
        elif line[-1] == '\\':
            lines = []
            while 1:
                lines.append(line)
                line = next(bb_fp).strip()
                if line[-1] != '\\':
                    lines.append(line)
                    break

            line = " ".join(lines)

        if line.startswith('inherit'):
            bb_dict['inherits'].append(line.split(maxsplit=1)[1])
            continue

        match = line_regex.search(line)
        if match:
            bb_dict = write_to_dict(bb_dict, match)

    get_src_url(bb_dict)
    replace_bb_variable_names(bb_dict)

    return bb_dict
