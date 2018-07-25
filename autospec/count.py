#
# count.py - part of autospec
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
import re
import argparse

testcount = {}
testpass = {}
testfail = {}
testxfail = {}
testskip = {}

total_tests = 0
total_tests = 0
total_pass = 0
total_fail = 0
total_xfail = 0
total_skip = 0

counted_tests = 0
counted_pass = 0
counted_fail = 0
counted_xfail = 0
counted_skip = 0

name = ''


def zero_test_data():
    global total_tests
    global total_pass
    global total_fail
    global total_xfail
    global total_skip
    global counted_tests
    global counted_pass
    global counted_fail
    global counted_xfail
    global counted_skip
    total_tests = 0
    total_pass = 0
    total_fail = 0
    total_xfail = 0
    total_skip = 0
    counted_tests = 0
    counted_pass = 0
    counted_fail = 0
    counted_xfail = 0
    counted_skip = 0


def sanitize_counts():
    global total_tests
    global total_pass
    global total_fail
    global total_xfail
    global total_skip
    global counted_tests
    global counted_pass
    global counted_fail
    global counted_xfail
    global counted_skip
    if total_tests > 0 and total_pass == 0:
        total_pass = total_tests - total_fail - total_skip - total_xfail

    if total_tests < total_pass and total_pass > 0:
        total_tests = total_pass + total_fail + total_skip + total_xfail

    if counted_tests > 0 and counted_pass == 0:
        counted_pass = counted_tests - counted_fail - counted_skip - counted_xfail

    if counted_tests < counted_pass and counted_pass > 0:
        counted_tests = counted_pass + counted_fail + counted_skip + counted_xfail

    if (total_pass + total_fail + total_skip + total_xfail) < total_tests:
        total_pass += total_tests - (total_pass + total_fail + total_skip + total_xfail)

    if (total_pass + total_fail + total_skip + total_xfail) > total_tests:
        total_tests = total_pass + total_fail + total_skip + total_xfail


def collect_output():
    if not testcount.get(name):
        testcount[name] = 0 if not testcount.get(name) else testcount[name]
    if not testpass.get(name):
        testpass[name] = 0
    if not testfail.get(name):
        testfail[name] = 0
    if not testxfail.get(name):
        testxfail[name] = 0
    if not testskip.get(name):
        testskip[name] = 0

    if counted_tests > total_tests:
        testcount[name] += counted_tests
        testpass[name] += counted_pass
        testfail[name] += counted_fail
        testxfail[name] += counted_xfail
        testskip[name] += counted_skip

    else:
        testcount[name] += total_tests
        testpass[name] += total_pass
        testfail[name] += total_fail
        testxfail[name] += total_xfail
        testskip[name] += total_skip

    zero_test_data()


def convert_int(intstr):
    try:
        return int(intstr)
    except ValueError:
        return 0


def parse_meson_test(lines):
    global total_pass
    global total_fail
    global total_skip
    for line in lines:
        line = line.rstrip().split()
        if len(line) != 2:
            continue
        if line[0] == 'OK:':
            total_pass = convert_int(line[1])
        elif line[0] == 'FAIL:':
            total_fail = convert_int(line[1])
        elif line[0] == 'SKIP:':
            total_skip = convert_int(line[1])
        elif line[0] == 'TIMEOUT:':
            # Count timeouts as failures.
            total_fail = convert_int(line[1])


def parse_log(log, pkgname=''):
    global total_tests
    global total_pass
    global total_fail
    global total_xfail
    global total_skip
    global counted_tests
    global counted_pass
    global counted_fail
    global counted_xfail
    global counted_skip
    global name

    name = pkgname
    incheck = False
    with open(log, 'r') as logf:
        lines = logf.readlines()

    zero_lines = ["Executing(%check)",
                  "+ make check",
                  "##### Testing packages."]

    for idx, line in enumerate(lines):
        line = line.rstrip()

        for zline in zero_lines:
            if zline in line:
                if incheck:
                    zero_test_data()
                else:
                    incheck = True

        if "/usr/bin/meson test" in line:
            zero_test_data()
            parse_meson_test(lines[idx:])
            break

        match = re.search(r"CLR-XTEST: Package: (.*)", line)
        if match:
            name = match.group(1)
            sanitize_counts()
            collect_output()

        # ACL package
        # [22] $ rm -Rf d -- ok-
        # 17 commands (17 passed, 0 failed)-
        if re.search(r"\[[0-9]+\].*\-\- ok", line):
            counted_pass += 1
            continue

        match = re.search(r"[0-9]+ commands \(([0-9]+) passed, ([0-9]+) failed\)", line)
        if match:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        # alembic package
        # Ran 678 tests in 5.175s
        # OK (SKIP=15)
        match = re.search("Ran ([0-9]+) tests? in", line)
        if match:
            total_tests += convert_int(match.group(1))
            continue

        match = re.search(r"OK \(SKIP=([0-9]+)\)", line)
        if match:
            total_skip += convert_int(match.group(1))
            continue
        else:
            match = re.search(r"OK \(skipped=([0-9]+)\)", line)
            if match:
                total_skip += convert_int(match.group(1))
                continue

        # anyjson
        # test_implementations.test_default_serialization ... ok
        # note: configure false positive
        if re.search(r"\.\.\. ok$", line) and incheck:
            counted_pass += 1
            continue

        if re.search(r"\.\.\. skipped$", line) and incheck:
            counted_skip += 1
            continue

        # apr
        # testatomic          :  SUCCESS
        if re.search(r":  SUCCESS$", line) and incheck:
            counted_pass += 1
            continue

        # cryptography
        # ================= 76230 passed, 267 skipped in 140.23 seconds ==================
        # ================== 47 passed, 2 error in 10.36 seconds =========================
        # ================ 10 failed, 16 passed, 4 error in 0.16 seconds =================
        # ========================== 43 passed in 2.90 seconds ===========================
        # ======= 28 failed, 281 passed, 13 skipped, 10 warnings in 28.48 seconds ========
        # ===================== 5 failed, 318 passed in 1.06 seconds =====================
        # ============= 1628 passed, 72 skipped, 4 xfailed in 146.26 seconds =============
        # =============== 119 passed, 2 skipped, 54 error in 2.19 seconds ================
        # ========== 1 failed, 74 passed, 10 skipped, 55 error in 2.05 seconds ===========
        # ==================== 68 passed, 1 warnings in 0.12 seconds =====================
        # ================ 3 failed, 250 passed, 3 error in 3.28 seconds =================
        # =============== 1 failed, 407 passed, 10 skipped in 4.71 seconds ===============
        # ========================== 1 skipped in 0.79 seconds ===========================
        # =========================== 3 error in 0.41 seconds ============================
        # ================= 68 passed, 1 pytest-warnings in 0.09 seconds =================
        # ===== 21 failed, 73 passed, 5 skipped, 2 pytest-warnings in 34.81 seconds ======
        match = re.search(r"== ([0-9]+) passed, ([0-9]+) skipped in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_skip += convert_int(match.group(2))
            continue

        match = re.search(r"== ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) xfailed in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_skip += convert_int(match.group(2))
            total_xfail += convert_int(match.group(3))
            continue

        match = re.search(r"== ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) error in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_skip += convert_int(match.group(2))
            total_fail += convert_int(match.group(3))
            continue

        match = re.search(r"== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) error in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            total_fail += convert_int(match.group(4)) + convert_int(match.group(1))
            continue

        match = re.search(r"== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) error in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(2))
            total_fail += convert_int(match.group(3)) + convert_int(match.group(1))
            continue

        match = re.search(r"== ([0-9]+) passed, ([0-9]+) error in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        match = re.search(r"== ([0-9]+) passed, ([0-9]+) warnings in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        match = re.search(r"== ([0-9]+) failed, ([0-9]+) passed in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(2))
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) xfailed in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(2))
            total_fail += convert_int(match.group(1))
            total_xfail += convert_int(match.group(3))
            continue

        match = re.search(r"== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) warnings in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(2))
            total_fail += convert_int(match.group(1)) + convert_int(match.group(4))
            total_skip += convert_int(match.group(3))
            continue

        match = re.search(r"== ([0-9]+) passed in [0-9\.]+ seconds ====", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped in [0-9\.]+ seconds ====", line)
        if match and incheck:
            total_pass += convert_int(match.group(2))
            total_fail += convert_int(match.group(1))
            total_skip += convert_int(match.group(3))
            continue

        match = re.search(r"== ([0-9]+) skipped in [0-9\.]+ seconds ====", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        match = re.search(r"== ([0-9]+) error in [0-9\.]+ seconds ====", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"== ([0-9]+) passed\, [0-9]+ [A-Za-z0-9]+\-warnings? in [0-9\.]+ seconds ====", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # ===== 21 failed, 73 passed, 5 skipped, 2 pytest-warnings in 34.81 seconds ======
        match = re.search(r"== ([0-9]+) failed\, ([0-9]+) passed\, ([0-9]+) skipped\, [0-9]+ [A-Za-z0-9]+\-warnings? in [0-9\.]+ seconds ====", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            total_pass += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            continue

        # swift
        # ========= 1 failed, 1287 passed, 1 warnings, 62 error in 35.77 seconds =========
        match = re.search(r"== ([0-9]+) failed\, ([0-9]+) passed\, ([0-9]+) warnings\, ([0-9]+) error in ", line)
        if match and incheck:
            total_fail += (convert_int(match.group(1)) + convert_int(match.group(3)) + convert_int(match.group(4)))
            total_pass += convert_int(match.group(2))
            continue

        # swift
        # 487 failed, 4114 passed, 32 skipped, 1 pytest-warnings, 34 error in 222.82 seconds
        match = re.search(r"\s*([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped, [0-9]+ [A-Za-z0-9]+\-warnings?, ([0-9]+) error in ", line)
        if match and incheck:
            total_fail += convert_int(match.group(1)) + convert_int(match.group(4))
            total_pass += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            continue

        # tox
        # ======== 199 passed, 38 skipped, 1 xpassed, 1 warnings in 5.76 seconds =========
        match = re.search(r"== ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) xpassed, ([0-9]) warnings in ", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_skip += convert_int(match.group(2))
            total_xfail += convert_int(match.group(3))
            total_fail += convert_int(match.group(4))
            continue

        # augeas
        # TOTAL: 215
        # PASS:  212
        # SKIP:  3
        # XFAIL: 0
        # FAIL:  0
        # XPASS: 0
        # ERROR: 0
        match = re.search(r"# TOTAL: +([0-9]+)", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            continue

        match = re.search(r"# PASS: +([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"# SKIP: +([0-9]+)", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        match = re.search(r"# FAIL: +([0-9]+)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"# XFAIL: +([0-9]+)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            continue

        match = re.search(r"# XPASS: +([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # autoconf
        # 493 tests behaved as expected.
        # 10 tests were skipped.
        # 495: AC_FUNC_STRNLEN                                 ok
        # 344: Erlang                                          skipped (erlang.at:30)
        # 26: autoupdating macros recursively                 expected failure (tools.at:945)
        match = re.search(r"^([0-9]+) tests behaved as expected", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^([0-9]+) tests were skipped", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        match = re.search(r"^[0-9]+\:.*ok$", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^[0-9]+\:.*skipped \(", line)
        if match and incheck:
            counted_skip += 1
            continue

        match = re.search(r"^[0-9]+\:.*expected failure \(", line)
        if match and incheck:
            counted_xfail += 1
            continue

        # bison
        # 470 tests were successful.
        match = re.search(r"^([0-9]+) tests were successful", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # binutils
        # of expected passes            1144
        # of expected failures          57
        # of untested testcases         1
        # of unsupported tests          12
        match = re.search(r"^# of expected passes.*\t([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^# of expected failures.*\t([0-9]+)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            continue

        match = re.search(r"^# of unexpected failures.*\t([0-9]+)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"^# of unsupported tests.*\t([0-9]+)", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        # ccache
        # PASSED: 448 assertions, 88 tests, 10 suites
        match = re.search(r"PASSED: [0-9]+ assertions, ([0-9]+) tests, [0-9]+ suites", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # rubygem-rack
        # 701 tests, 2292 assertions, 0 failures, 0 errors
        match = re.search(r"([0-9]+) tests, [0-9]+ assertions, ([0-9]+) failures, ([0-9])+ errors", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            total_fail += convert_int(match.group(3))
            continue

        # curl
        # TESTDONE: 686 tests out of 686 reported OK: 100%
        match = re.search(r"TESTDONE: ([0-9]+) tests out of ([0-9]+) reported OK: ", line)
        if match and incheck:
            total_tests += convert_int(match.group(2))
            total_pass += convert_int(match.group(1))
            total_fail = convert_int(match.group(2)) - convert_int(match.group(1))
            continue

        # gcc
        # All 4 tests passed
        # PASS: test-strtol-16.
        match = re.search(r"All ([0-9]+) tests passed", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^PASS\: [A-Za-z]+", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^FAIL\: [A-Za-z]+", line)
        if match and incheck:
            counted_fail += 1
            continue

        # gdbm
        # All 22 tests were successful.
        match = re.search(r"All ([0-9]+) tests were successful.", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_pass += convert_int(match.group(1))
            continue

        # glibc
        # 3 FAIL
        # 2182 PASS
        # 1 UNRESOLVED
        # 199 XFAIL
        # 3 XPASS
        match = re.search(r"^\s*([0-9]+) FAIL$", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"^\s*([0-9]+) PASS$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^\s*([0-9]+) XFAIL$", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            continue

        match = re.search(r"^\s*([0-9]+) XPASS$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # libxml2
        # Total 2908 tests, no errors
        # Total: 1171 functions, 291083 tests, 0 errors
        match = re.search(r"Total ([0-9]+) tests, no errors", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"Total: ([0-9]+) functions, ([0-9]+) tests, 0 errors", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # zlib
        # *** zlib shared test OK ***
        match = re.search(r"\*\*\* .* test OK \*\*\*", line)
        if match and incheck:
            counted_pass += 1
            continue

        # e2fsprogs
        # 153 tests succeeded     0 tests failed
        match = re.search(r"([0-9]+) tests succeeded\s*([0-9]+) tests failed", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        # expect
        # all.tcl:        Total   29      Passed  29      Skipped 0       Failed  0
        match = re.search(r".*:\s*Total\s+([0-9]+)\s+Passed\s+([0-9]+)\s+Skipped\s+([0-9]+)\s+Failed\s+([0-9]+)", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_pass += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            total_fail += convert_int(match.group(4))
            continue

        # expat
        # 100%: Checks: 50, Failed: 0
        match = re.search(r"[0-9]+%: Checks: ([0-9]+), Failed: ([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1)) - convert_int(match.group(2))
            total_fail += convert_int(match.group(2))
            continue

        # flex
        # Tests succeeded: 47
        # Tests FAILED: 0
        match = re.search(r"^Tests succeeded: ([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^Tests FAILED: ([0-9]+)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        # this one catches the generic TAP format!
        #  perl-Capture-tiny
        # ok 580 - tee_merged|sys|stderr|short - got STDERR
        match = re.search(r"^ok [0-9]+ \-", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^not ok [0-9]+ \-", line)
        if match and incheck:
            if re.search(r"# TODO known breakage", line):
                counted_xfail += 1
            else:
                counted_fail += 1

            continue

        match = re.search(r"^ok [0-9]+$", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^not ok [0-9]+$", line)
        if match and incheck:
            counted_fail += 1
            continue

        # tcpdump
        #    0 tests failed
        # 154 tests passed
        match = re.search(r"^\s*([0-9]+) tests? failed$", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"^\s*([0-9]+) tests? passed$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # R packages
        # * checking top-level files ... OK
        match = re.search(r"\* .* \.\.\. OK", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"\* .* \.\.\. PASSED\.", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"\* .* \.\.\. SKIPPED", line)
        if match and incheck:
            counted_skip += 1
            continue

        # python
        # 365 tests OK.
        # 22 tests skipped:
        match = re.search(r"^([0-9]+) tests skipped:$", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        match = re.search(r"^([0-9]+) tests OK.$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # jemalloc
        # Test suite summary: pass: 30/33, skip: 3/33, fail: 0/33
        match = re.search(r"Test suite summary: pass: ([0-9]+)\/([0-9]+), skip: ([0-9]+)\/([0-9]+), fail: ([0-9]+)\/([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_tests += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            total_fail += convert_int(match.group(5))
            continue

        # util-linux
        #   All 160 tests PASSED
        match = re.search(r"  All ([0-9]+) tests PASSED$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # nss
        # cert.sh: #101: Import chain-2-serverCA-ec CA -t u,u,u for localhost.localdomain (ext.)  - PASSED
        # Passed:             13036
        # Failed:             6
        # Failed with core:   0
        # Unknown status:     0
        match = re.search(r"^[a-z]+.sh: #[0-9]+: .*  - PASSED$", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^[a-z]+.sh: #[0-9]+: .*  - FAILED$", line)
        if match and incheck:
            counted_fail += 1
            continue

        match = re.search(r"^Passed:\s+([0-9]+)$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^Failed:\s+([0-9]+)$", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"^Failed with core:\s+([0-9]+)$", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        # rsync
        #      34 passed
        #      5 skipped
        match = re.search(r"^\s+([0-9]+) passed$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        match = re.search(r"^\s+([0-9]+) skipped$", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        # mariadb
        # 100% tests passed, 0 tests failed out of 53
        match = re.search(r"tests passed, ([0-9]+) tests failed out of ([0-9]+)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            total_tests += convert_int(match.group(2))
            total_pass += convert_int(match.group(2)) - convert_int(match.group(1))
            continue

        # python-runtime-tests
        # FAILED (KNOWNFAIL=6, SKIP=18, errors=6)
        # FAILED (failures=1)
        # FAILED (failures=1, errors=499, skipped=48)
        # OK (KNOWNFAIL=5, SKIP=15)
        match = re.search(r"FAILED \(KNOWNFAIL=([0-9]+), SKIP=([0-9]+), errors=([0-9]+)\)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            total_skip += convert_int(match.group(2))
            total_fail += convert_int(match.group(3))
            continue

        match = re.search(r"FAILED \(failures=([0-9]+), errors=([0-9]+), skipped=([0-9]+)\)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"FAILED \(failures=([0-9]+), errors=([0-9]+)\)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(2))
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"FAILED \(failures=([0-9]+)\)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"FAILED \(errors=([0-9]+)\)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            continue

        match = re.search(r"OK \(KNOWNFAIL=([0-9]+), SKIP=([0-9]+)\)", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            total_skip += convert_int(match.group(2))
            continue

        # qpid-python
        # Totals: 318 tests, 200 passed, 112 skipped, 0 ignored, 6 failed
        match = re.search(r"Totals: ([0-9]+) tests, ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) ignored, ([0-9]+) failed", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_pass += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            total_xfail += convert_int(match.group(4))
            total_fail += convert_int(match.group(5))
            continue

        # PyYAML
        # TESTS: 2577
        match = re.search(r"^TESTS: ([0-9]+)$", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            continue

        # sudo
        # visudo: 7/7 tests passed; 0/7 tests failed
        # check_symbols: 7 tests run, 0 errors, 100% success rate
        match = re.search(r"[a-z_]+\:\s+([0-9]+)\/[0-9]+ tests passed; ([0-9]+)\/[0-9]+ tests failed", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        match = re.search(r"[a-z_]+\: ([0-9]+) tests run, ([0-9]+) errors", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            total_pass += convert_int(match.group(1)) - convert_int(match.group(2))
            continue

        # R
        # running code in 'reg-examples1.R' ... OK
        # Status: 1 ERROR, 1 WARNING, 4 NOTEs
        # OK: 749 SKIPPED: 4 FAILED: 2
        match = re.search(r"running code in '.*\.R' \.\.. OK", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"Status: ([0-9]+) ERROR, ([0-9]+) WARNING, ([0-9]+) NOTEs", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"OK: ([0-9]+) SKIPPED: ([0-9]+) FAILED: ([0-9]+)", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(3))
            total_skip += convert_int(match.group(2))
            continue

        # onig
        # OK: // 'a'
        match = re.search(r"^OK\: ", line)
        if match and incheck:
            counted_pass += 1
            continue

        # php
        # Number of tests : 13526              9794
        # Tests skipped   : 3732 ( 27.6%) --------
        # Tests warned    :    0 (  0.0%) (  0.0%)
        # Tests failed    :   12 (  0.1%) (  0.1%)
        # Expected fail   :   31 (  0.2%) (  0.3%)
        # Tests passed    : 9751 ( 72.1%) ( 99.6%)
        match = re.search(r"^Number of tests : ([0-9]+)", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            continue

        match = re.search(r"^Tests skipped   :\s+([0-9]+) \(", line)
        if match and incheck:
            total_skip += convert_int(match.group(1))
            continue

        match = re.search(r"^Tests failed    :\s+([0-9]+) \(", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"^Expected fail   :\s+([0-9]+) \(", line)
        if match and incheck:
            total_xfail += convert_int(match.group(1))
            continue

        match = re.search(r"^Tests passed    :\s+([0-9]+) \(", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # rubygem / rake
        # 174 runs, 469 assertions, 0 failures, 0 errors, 0 skips
        match = re.search(r"([0-9]+) runs, ([0-9]+) assertions, ([0-9]+) failures, ([0-9]+) errors, ([0-9]+) skips", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_fail += convert_int(match.group(3))
            total_skip += convert_int(match.group(5))
            continue

        # cryptsetup
        #  [OK]
        if re.search(r" \[OK\]$", line) and incheck:
            counted_pass += 1
            continue

        # lzo
        #  test passed.
        match = re.search(r" test passed.$", line)
        if match and incheck:
            counted_pass += 1
            continue

        # lsof
        # LTnlink ... OK
        # LTnfs ... ERROR!!!
        match = re.search(r"^LT[a-zA-Z0-9]+ \.\.\. OK$", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^LT[a-zA-Z0-9]+ \.\.\. ERROR\!\!\!", line)
        if match and incheck:
            counted_fail += 1
            continue

        # libaio
        # Pass: 11  Fail: 1
        match = re.search(r"^Pass: ([0-9]+)  Fail: ([0-9]+)$", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        # gawk
        match = re.search(r"^ALL TESTS PASSED$", line)
        if match and incheck:
            total_pass += 1
            continue

        # gptfdisk
        # **SUCCESS** ...
        match = re.search(r"^\*\*SUCCESS\*\*", line)
        if match and incheck:
            counted_pass += 1
            continue

        # boost
        # **passed** ...
        # 8 errors detected.
        match = re.search(r"^\*\*passed\*\*", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"([0-9]+) errors? detected\.?", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        match = re.search(r"([0-9]+) failures? detected\.?", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            continue

        # make
        # 534 Tests in 118 Categories Complete ... No Failures
        match = re.search(r"([0-9]+) Tests in ([0-9]+) Categories Complete ... No Failures", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_pass += convert_int(match.group(1))
            continue

        # icu4c ---[OK]
        match = re.search(r"---\[OK\]", line)
        if match and incheck:
            counted_pass += 1
            continue

        # libxslt
        # Pass 1
        match = re.search(r"^Pass [0-9]+$", line)
        if match and incheck:
            counted_pass += 1
            continue

        # bash
        # < Failed 126 of 1378 Unicode tests
        match = re.search(r"^[<,>] Failed ([0-9]+) of ([0-9]+)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            total_tests += convert_int(match.group(2))
            continue

        # crudini
        # Test 95 OK (line 460)
        match = re.search(r"^Test [0-9]+ OK", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"^Test [0-9]+ (?!^OK)[A-Z]+", line)
        if match and incheck:
            counted_fail += 1
            continue

        # discount
        # Reddit-style automatic links ......................... OK
        match = re.search(r"[A-Za-z\-\s]+ \.\.\.+ (OK|GOOD)$", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"[A-Za-z\-\s]+ \.\.\.+ (?!^OK)[A-Z]+$", line)
        if match and incheck:
            counted_fail += 1
            continue

        # libjpeg-turbo
        # JPEG -> RGB Top-Down  2/1 ... Passed.
        # JPEG -> RGB Top-Down  15/8 ... Passed.
        # JPEG -> RGB Top-Down  7/4 ... Passed.
        match = re.search(r"[A-Za-z0-9\ \>\<\/]+ \.\.\. Passed\.", line)
        if match and incheck:
            counted_pass += 1
            continue

        # LVM2
        # valgrind pool awareness ... fail
        # dfa matching ... fail
        # dfa matching ... fail
        # dfa with non-print regex chars ... pass
        # bitset iteration ... pass
        # valgrind pool awareness ... fail
        # dfa matching ... fail
        # dfa matching ... fail
        # dfa with non-print regex chars ... fail
        # bitset iteration ... fail
        match = re.search(r"[a-z\ ]+\ \.\.\.\ pass", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"[a-z\ ]+\ \.\.\.\ fail", line)
        if match and incheck:
            counted_fail += 1
            continue

        # keyring
        #  76 passed, 62 skipped, 50 xfailed, 14 xpassed, 2 warnings, 32 error in 2.13 seconds
        match = re.search(r"([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) xfailed, ([0-9]+) xpassed, ([0-9]+) warnings, ([0-9]+) error in [0-9\.]+ seconds", line)
        if match and incheck:
            total_pass += convert_int(match.group(1)) + convert_int(match.group(4))
            total_skip += convert_int(match.group(2))
            total_xfail += convert_int(match.group(3))
            total_fail += convert_int(match.group(5)) + convert_int(match.group(6))
            continue

        # openblas
        #  Real BLAS Test Program Results
        #  Test of subprogram number  1             SDOT
        #                                     ----- PASS -----
        #  Test of subprogram number  2            SAXPY
        #                                     ----- PASS -----
        #  Test of subprogram number  3            SROTG
        #                                     ----- PASS -----
        match = re.search(r"\ \ +\-\-\-+\ PASS\ \-\-\-+", line)
        if match and incheck:
            counted_pass += 1
            continue

        match = re.search(r"\ \ +\-\-\-+\ FAIL\ \-\-\-+", line)
        if match and incheck:
            counted_fail += 1
            continue

        # rubygem-hashie
        # Finished in 0.07221 seconds (files took 0.28356 seconds to load)
        # 545 examples, 0 failures, 1 pending
        match = re.search(r"([0-9]+) examples?, ([0-9]+) failures?, ([0-9]+) pending", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            continue

        # rubygem-warden
        # Finished in 0.08928 seconds (files took 0.1046 seconds to load)
        # 215 examples, 14 failures
        match = re.search(r"([0-9]+) examples?, ([0-9]+) failures?", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            continue

        # rubygem-ansi
        # Executed 12 tests with 7 passing, 5 errors.
        match = re.search(r"Executed ([0-9]+) tests with ([0-9+]) passing, ([0-9]+) errors\.", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_pass += convert_int(match.group(2))
            total_fail += convert_int(match.group(3))
            continue

        # vim
        # Executed 9 tests
        match = re.search(r"Executed ([0-9]+) tests$", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            continue

        # rubygem-formatador
        #   9 succeeded in 0.00375661 seconds
        match = re.search(r"([0-9]+) succeeded in [0-9]+\.[0-9]+ seconds", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # ./pigz -kf pigz.c ; ./pigz -t pigz.c.gz
        # ./pigz -kfb 32 pigz.c ; ./pigz -t pigz.c.gz
        match = re.search(r".*\.\/pigz.+(\.\/pigz).+", line)
        if match and incheck:
            total_pass += 2
            continue
        elif re.search(r".*\.\/pigz.+", line) and incheck:
            total_pass += 1
            continue

        # netifaces
        # Interface lo:
        # Interface enp2s0:
        match = re.search(r"^Interface [a-zA-Z0-9]+\:", line)
        if match and incheck:
            total_pass += 1
            continue

        # btrfs-progs
        # [TEST]   001-bad-file-extent-bytenr
        # [NOTRUN] Need to validate root privileges
        # test failed for case
        match = re.search(r"    \[TEST\]   .*", line)
        if match and incheck:
            total_pass += 1
            continue

        match = re.search(r"test failed for case.*", line)
        if match and incheck:
            total_fail += 1
            total_pass = max(0, total_pass - 1)
            continue

        match = re.search(r"    \[NOTRUN\] .*", line)
        if match and incheck:
            total_skip += 1
            continue

        # chrpath
        # success: chrpath changed rpath to larger path.
        # error: chrpath unable to change rpath to larger path.
        match = re.search(r"success\: chrpath .*", line)
        if match and incheck:
            total_pass += 1
            continue
        elif re.search(r"error: chrpath .*", line) and incheck:
            total_fail += 1
            continue
        elif re.search(r"warning: chrpath .*", line) and incheck:
            total_fail += 1
            continue

        # yajl
        # 58/58 tests successful
        match = re.search(r"([0-9]+)\/([0-9]+) tests successful", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_tests += convert_int(match.group(2))
            continue

        # xmlsec1
        #     Checking required transforms                            OK
        #     Verify existing signature                             Fail
        #     Checking required transforms                          Skip
        #     Checking required key data                               OK
        match = re.search(r"^    [\w ]+\ +OK$", line)
        if match and incheck:
            total_pass += 1
            continue
        elif re.search(r"^    [\w ]+\ +Fail$", line) and incheck:
            total_fail += 1
            continue
        elif re.search(r"^    [\w ]+\ +Skip$", line) and incheck:
            total_skip += 1
            continue

        # xdg-utils
        # TOTAL: 4 tests failed, 90 of 116 tests passed. (140 attempted)
        match = re.search(r"TOTAL\: ([0-9]+) tests? failed\, ([0-9]+) of [0-9]+ tests? passed\. \(([0-9]+) attempted\)", line)
        if match and incheck:
            total_fail += convert_int(match.group(1))
            total_pass += convert_int(match.group(2))
            total_skip += convert_int(match.group(3)) - (convert_int(match.group(2)) + convert_int(match.group(1)))
            continue

        # slang
        # Testing argv processing ...Ok
        # ./utf8.sl:14:check_sprintf:Test Error
        match = re.search(r"^Testing [\w ]+\.\.\.Ok$", line)
        if match and incheck:
            total_pass += 1
            continue

        match = re.search(r":Test Error", line)
        if match and incheck:
            total_fail += 1
            continue

        # go & golang
        # ok  	golang.org/x/text/encoding/htmlindex	0.002s
        # --- FAIL: TestParents (0.00s)
        # FAIL	golang.org/x/text/internal	0.002s
        # --- PASS: TestApp_Command (0.00s)
        match = re.search(r"^ok\s+[\w_]+[A-Za-z0-9\.\?_\-]*", line)
        if match and incheck:
            total_tests += 1
            total_pass += 1
            continue

        match = re.search(r"(---\s+)?FAIL:?\s*", line)
        if match and incheck:
            total_tests += 1
            total_fail += 1
            continue

        match = re.search(r"---\s+PASS|PASS\s+ ", line)
        if match and incheck:
            total_tests += 1
            total_pass += 1
            continue

        # valgrind
        # == 5 tests, 0 stderr failures, 1 stdout failure, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==
        # == 55 tests, 48 stderr failures, 6 stdout failures, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==
        # == 125 tests, 12 stderr failures, 0 stdout failures, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==
        match = re.search(r"\=\= ([0-9]+) tests?\, ([0-9]+) stderr failures?\, ([0-9]+) stdout failures?\, "
                          "([0-9]+) stderrB failures?\, ([0-9]+) stdoutB failures?\, ([0-9]+) post failures? \=\=", line)
        if match and incheck:
            total_tests += convert_int(match.group(1))
            total_fail += (convert_int(match.group(2)) + convert_int(match.group(3)) + convert_int(match.group(4)) + convert_int(match.group(5)) + convert_int(match.group(6)))
            total_pass += (convert_int(match.group(1)) - (convert_int(match.group(2)) + convert_int(match.group(3)) + convert_int(match.group(4)) + convert_int(match.group(5)) +
                                                          convert_int(match.group(6))))
            continue

        # zsh
        # **************************************
        # 46 successful test scripts, 0 failures, 1 skipped
        # **************************************
        match = re.search(r"([0-9]+) successful test scripts\, ([0-9]+) failures\, ([0-9]+) skipped", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            total_fail += convert_int(match.group(2))
            total_skip += convert_int(match.group(3))
            continue

        # glog
        # Passed 3 tests
        match = re.search(r"Passed ([0-9]+) tests", line)
        if match and incheck:
            total_pass += convert_int(match.group(1))
            continue

        # hdf5
        # Testing h5repack h5repack_szip.h5 -f dset_szip:GZIP=1                  -SKIP-
        # Verifying h5dump output -f GZIP=1 -m 1024                             *FAILED*
        # Testing h5repack --metadata_block_size=8192                            PASSED
        # Verifying h5diff output h5repack_layout.h5 out-meta_long.h5repack_layo PASSED
        match = re.search(r"^Testing .+\ +PASSED$", line)
        if match and incheck:
            total_pass += 1
            continue

        match = re.search(r"^Verifying .+\ +PASSED$", line)
        if match and incheck:
            total_pass += 1
            continue

        match = re.search(r"^Testing .+\ +\-SKIP\-$", line)
        if match and incheck:
            total_skip += 1
            continue

        match = re.search(r"^Verifying .+\ +\-SKIP\-$", line)
        if match and incheck:
            total_skip += 1
            continue

        # libconfig
        # 3 tests; 3 passed, 0 failed
        match = re.search(r"^([0-9]+) tests; ([0-9]+) passed\, ([0-9]+) failed", line)
        if match and incheck:
            total_tests = convert_int(match.group(1))
            total_pass = convert_int(match.group(2))
            total_fail = convert_int(match.group(3))
            continue

        # libogg
        # testing page spill expansion... 0, (0),  granule:0 1, (1),  granule:4103 2, (2),  granule:5127 ok.
        # testing max packet segments... 0, (0),  granule:0 1, (1),  granule:261127 2, (2),  granule:262151 ok.
        # testing very large packets... 0, (0),  granule:0 1, (1),  granule:1031 2, (2), 3, (3),  granule:4103 ok.
        # testing continuation resync in very large packets... 0, 1, 2, (2), 3, (3),  granule:4103 ok.
        # testing zero data page (1 nil packet)... 0, (0),  granule:0 1, (1),  granule:1031 2, (2),  granule:2055 ok.
        # Testing search for capture... ok.
        # Testing recapture... ok.
        match = re.search(r"^[T,t]esting .*\ ok\.$", line)
        if match and incheck:
            counted_pass += 1
            continue

        # libvorbis
        #     vorbis_1ch_q-0.5_44100.ogg : ok
        #     vorbis_2ch_q-0.5_44100.ogg : ok
        #     ...
        #     vorbis_7ch_q-0.5_44100.ogg : ok
        #     vorbis_8ch_q-0.5_44100.ogg : ok
        match = re.search(r"^\ \ \ \ vorbis_.*\.ogg\ \:\ ok$", line)
        if match and incheck:
            counted_pass += 1
            continue

        # pth
        # OK - ALL TESTS SUCCESSFULLY PASSED.
        match = re.search(r"^OK\ \-\ ALL\ TESTS\ SUCCESSFULLY\ PASSED\.$", line)
        if match and incheck:
            counted_pass += 1
            continue

    sanitize_counts()
    collect_output()
    return string_out()


def string_out():
    retstr = ""
    for key in sorted(testcount):
        # key may be an empty string, which is fine since this is handled by
        # the calling module
        retstr += "{},{},{},{},{},{}\n".format(key,
                                               testcount[key],
                                               testpass[key],
                                               testfail[key],
                                               testskip[key],
                                               testxfail[key])

    return retstr.strip()  # strip trailing newline


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('logfile', help="path to log file to parse")
    args = parser.parse_args()
    result = parse_log(args.logfile)
    print(result)
