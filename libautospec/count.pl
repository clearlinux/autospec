#!/usr/bin/perl
#
# count.pl - part of autospec
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

my %testcount;
my %testpass;
my %testfail;
my %testxfail;
my %testskip;
my $pkg_has_test = 0;

my $total_tests;
my $total_pass;
my $total_fail;
my $total_xfail;
my $total_skip;

my $counted_tests;
my $counted_pass;
my $counted_fail;
my $counted_xfail;
my $counted_skip;

my $name, $v, $r;


sub parse_log
{
    my ($fn) = @_;
    my $incheck = 0;

    open(my $log, "<", "$fn") or return 0;
    while (<$log>) {
        my $line = $_;
        chomp($line);

        if ($line =~ /Executing\(%check\)/) {
            if ($incheck == 1) {
                $total_tests = 0;
                $total_pass = 0;
                $total_fail = 0;
                $total_xfail = 0;
                $total_skip = 0;
                $counted_tests = 0;
                $counted_pass = 0;
                $counted_fail = 0;
                $counted_xfail = 0;
                $counted_skip = 0;
            }
            else {
                $incheck = 1;
            }
        }
        if ($line =~ /\+ make check/) {
            if ($incheck == 1) {
                $total_tests = 0;
                $total_pass = 0;
                $total_fail = 0;
                $total_xfail = 0;
                $total_skip = 0;
                $counted_tests = 0;
                $counted_pass = 0;
                $counted_fail = 0;
                $counted_xfail = 0;
                $counted_skip = 0;
            }
            else {
                $incheck = 1;
            }
        }
        if ($line =~ /##### Testing packages\./) {
            if ($incheck == 1) {
                $total_tests = 0;
                $total_pass = 0;
                $total_fail = 0;
                $total_xfail = 0;
                $total_skip = 0;
                $counted_tests = 0;
                $counted_pass = 0;
                $counted_fail = 0;
                $counted_xfail = 0;
                $counted_skip = 0;
            }
            else {
                $incheck = 1;
            }
        }
        if ($line =~ /CLR-XTEST: Package: (.*)/) {
            my $n = $1;
            sanitize_counts();
            collect_output();
            $name = $n;
        }

# ACL package
# [22] $ rm -Rf d -- ok-
# 17 commands (17 passed, 0 failed)-
        if ($line =~ /\[[0-9]+\].*\-\- ok/) {
            $counted_pass++;
            next;
        }
        if ($line =~ /[0-9]+ commands \(([0-9]+) passed, ([0-9]+) failed\)/) {
            $total_pass += $1;
            $total_fail += $2;
            next;
        }

# alembic package
#Ran 678 tests in 5.175s
#OK (SKIP=15)
        if ($line =~ /Ran ([0-9]+) tests? in/) {
            $total_tests += $1;
            next;
        }
        if ($line =~ /OK \(SKIP=([0-9]+)\)/) {
            $total_skip += $1;
            next;
        } elsif ($line =~ /OK \(skipped=([0-9]+)\)/) {
            $total_skip += $1;
            next;
        }

# anyjson
# test_implementations.test_default_serialization ... ok
# note: configure false positive
        if ($line =~ /\.\.\. ok$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /\.\.\. skipped$/ and $incheck == 1) {
            $counted_skip++;
            next;
        }

# apr
# testatomic          :  SUCCESS
        if ($line =~ /\:  SUCCESS$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

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
        if ($line =~ /== ([0-9]+) passed, ([0-9]+) skipped in / and $incheck == 1) {
            $total_pass += $1;
            $total_skip += $2;
            next;
        }
        if ($line =~ /== ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) xfailed in / and $incheck == 1) {
            $total_pass += $1;
            $total_skip += $2;
            $total_xfail += $3;
            next;
        }
        if ($line =~ /== ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) error in / and $incheck == 1) {
            $total_pass += $1;
            $total_skip += $2;
            $total_fail += $3;
            next;
        }
        if ($line =~ /== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) error in / and $incheck == 1) {
            $total_pass += $2;
            $total_skip += $3;
            $total_fail += $4 + $1;
            next;
        }
        if ($line =~ /== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) error in / and $incheck == 1) {
            $total_pass += $2;
            $total_fail += $3 + $1;
            next;
        }
        if ($line =~ /== ([0-9]+) passed, ([0-9]+) error in / and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            next;
        }
        if ($line =~ /== ([0-9]+) passed, ([0-9]+) warnings in / and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            next;
        }
        if ($line =~ /== ([0-9]+) failed, ([0-9]+) passed in / and $incheck == 1) {
            $total_pass += $2;
            $total_fail += $1;
            next;
        }
        if ($line =~ /== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) xfailed in / and $incheck == 1) {
            $total_pass += $2;
            $total_fail += $1;
            $total_xfail += $3;
            next;
        }
        if ($line =~ /== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) warnings in / and $incheck == 1) {
            $total_pass += $2;
            $total_fail += ($1+$4);
            $total_skip += $3;
            next;
        }
        if ($line =~ /== ([0-9]+) passed in [0-9\.]+ seconds ====/ and $incheck == 1) {
            $total_pass += $1;
            $total_skip += $2;
            next;
        }
        if ($line =~ /== ([0-9]+) failed, ([0-9]+) passed, ([0-9]+) skipped in [0-9\.]+ seconds ====/ and $incheck == 1) {
            $total_pass += $2;
            $total_fail += $1;
            $total_skip += $3;
            next;
        }
        if ($line =~ /== ([0-9]+) skipped in [0-9\.]+ seconds ====/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }
        if ($line =~ /== ([0-9]+) error in [0-9\.]+ seconds ====/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /== ([0-9]+) passed\, [0-9]+ [A-Za-z0-9]+\-warnings? in [0-9\.]+ seconds ====/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
# ===== 21 failed, 73 passed, 5 skipped, 2 pytest-warnings in 34.81 seconds ======
        if ($line =~ /== ([0-9]+) failed\, ([0-9]+) passed\, ([0-9]+) skipped\, [0-9]+ [A-Za-z0-9]+\-warnings? in [0-9\.]+ seconds ====/ and $incheck == 1) {
            $total_fail += $1;
            $total_pass += $2;
            $total_skip += $3;
            next;
        }

# swift
# ========= 1 failed, 1287 passed, 1 warnings, 62 error in 35.77 seconds =========
        if ($line =~ /== ([0-9]+) failed\, ([0-9]+) passed\, ([0-9]+) warnings\, ([0-9]+) error in / and $incheck == 1) {
            $total_fail += ($1 + $3 + $4);
            $total_pass += $2;
            next;
        }
# swift
# 487 failed, 4114 passed, 32 skipped, 1 pytest-warnings, 34 error in 222.82 seconds
        if ($line =~ /\ ([0-9]+) failed\, ([0-9]+) passed\, ([0-9]+) skipped\, [0-9]+ [A-Za-z0-9]+\-warnings?\, ([0-9]+) error in / and $incheck == 1) {
            $total_fail += $1 + $4;
            $total_pass += $2;
            $total_skip += $3;
            next;
        }

# tox
# ======== 199 passed, 38 skipped, 1 xpassed, 1 warnings in 5.76 seconds =========
        if ($line =~/== ([0-9]+) passed\, ([0-9]+) skipped\, ([0-9]+) xpassed\, ([0-9]) warnings in / and $incheck == 1) {
            $total_pass += $1;
            $total_skip += $2;
            $total_xfail += $3;
            $total_fail += $4;
            next;
        }

# augeas
# TOTAL: 215
# PASS:  212
# SKIP:  3
# XFAIL: 0
# FAIL:  0
# XPASS: 0
# ERROR: 0
        if ($line =~ /# TOTAL: +([0-9]+)/ and $incheck == 1) {
            $total_tests += $1;
            next;
        }
        if ($line =~ /# PASS: +([0-9]+)/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /# SKIP: +([0-9]+)/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }
        if ($line =~ /# FAIL: +([0-9]+)/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /# XFAIL: +([0-9]+)/ and $incheck == 1) {
            $total_xfail += $1;
            next;
        }
        if ($line =~ /# XPASS: +([0-9]+)/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# autoconf
# 493 tests behaved as expected.
# 10 tests were skipped.
# 495: AC_FUNC_STRNLEN                                 ok
# 344: Erlang                                          skipped (erlang.at:30)
# 26: autoupdating macros recursively                 expected failure (tools.at:945)
        if ($line =~ /^([0-9]+) tests behaved as expected/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /^([0-9]+) tests were skipped/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }
        if ($line =~ /^[0-9]+\:.*ok$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /^[0-9]+\:.*skipped \(/ and $incheck == 1) {
            $counted_skip++;
            next;
        }
        if ($line =~ /^[0-9]+\:.*expected failure \(/ and $incheck == 1) {
            $counted_xfail++;
            next;
        }

# bison
# 470 tests were successful.
        if ($line =~ /^([0-9]+) tests were successful/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# binutils
# of expected passes            1144
# of expected failures          57
# of untested testcases         1
# of unsupported tests          12
        if ($line =~ /^# of expected passes.*\t([0-9]+)/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /^# of expected failures.*\t([0-9]+)/ and $incheck == 1) {
            $total_xfail += $1;
            next;
        }
        if ($line =~ /^# of unexpected failures.*\t([0-9]+)/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /^# of unsupported tests.*\t([0-9]+)/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }

# ccache
# PASSED: 448 assertions, 88 tests, 10 suites
        if ($line =~ /PASSED: [0-9]+ assertions, ([0-9]+) tests, [0-9]+ suites/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# rubygem-rack
# 701 tests, 2292 assertions, 0 failures, 0 errors
        if ($line =~ /([0-9]+) tests, [0-9]+ assertions, ([0-9]+) failures, ([0-9])+ errors/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            $total_fail += $3;
            next;
        }

# curl
# TESTDONE: 686 tests out of 686 reported OK: 100%
        if ($line =~ /TESTDONE: ([0-9]+) tests out of ([0-9]+) reported OK: / and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $2;
            $total_fail = $2-$1;
            next;
        }

# gcc
# All 4 tests passed
# PASS: test-strtol-16.
        if ($line =~ /All ([0-9]+) tests passed/ and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $1;
            next;
        }
        if ($line =~/^PASS\: [A-Za-z]+/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~/^FAIL\: [A-Za-z]+/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# gdbm
# All 22 tests were successful.
        if ($line =~ /All ([0-9]+) tests were successful./ and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $1;
            next;
        }

# glibc
# 3 FAIL
# 2182 PASS
# 1 UNRESOLVED
# 199 XFAIL
# 3 XPASS
        if ($line =~ /^\s*([0-9]+) FAIL$/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /^\s*([0-9]+) PASS$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /^\s*([0-9]+) XFAIL$/ and $incheck == 1) {
            $total_xfail += $1;
            next;
        }
        if ($line =~ /^\s*([0-9]+) XPASS$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# libxml2
# Total 2908 tests, no errors
# Total: 1171 functions, 291083 tests, 0 errors
        if ($line =~ /Total ([0-9]+) tests, no errors/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /Total: ([0-9]+) functions, ([0-9]+) tests, 0 errors/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# zlib
# *** zlib shared test OK ***
        if (line =~ /\*\*\* .* test OK \*\*\*/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# e2fsprogs
# 153 tests succeeded     0 tests failed
        if ($line =~ /([0-9]+) tests succeeded\s*([0-9]+) tests failed/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            next;
        }

# expect
# all.tcl:        Total   29      Passed  29      Skipped 0       Failed  0
        if ($line =~ /.*:\s*Total\s+([0-9]+)\s+Passed\s+([0-9]+)\s+Skipped\s+([0-9]+)\s+Failed\s+([0-9]+)/ and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $2;
            $total_skip += $3;
            $total_fail += $4;
            next;
        }

# expat
# 100%: Checks: 50, Failed: 0
        if ($line =~ /100%: Checks: ([0-9]+), Failed: ([0-9]+)/ and $incheck == 1) {
            $total_pass += $1 - $2;
            $total_fail += $2;
            next;
        }

# flex
#Tests succeeded: 47
#Tests FAILED: 0
        if ($line =~/^Tests succeeded: ([0-9]+)/ and $incheck == 1 and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~/^Tests FAILED: ([0-9]+)/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }

# this one catches the generic TAP format!
#  perl-Capture-tiny
# ok 580 - tee_merged|sys|stderr|short - got STDERR
        if ($line =~ /^ok [0-9]+ \-/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /^not ok [0-9]+ \-/ and $incheck == 1) {
            if ($line =~ /# TODO known breakage/) {
                $counted_xfail++;
            } else {
                $counted_fail++;
            }
            next;
        }
        if ($line =~ /^ok [0-9]+$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /^not ok [0-9]+$/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# tcpdump
#    0 tests failed
# 154 tests passed
        if ($line =~ /^\s?+([0-9]+) tests? failed$/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /^\s?+([0-9]+) tests? passed$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# R packages
# * checking top-level files ... OK
        if ($line =~ /\* .* \.\.\. OK/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /\* .* \.\.\. PASSED\./ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /\* .* \.\.\. SKIPPED/ and $incheck == 1) {
            $counted_skip++;
            next;
        }

# python
# 365 tests OK.
# 22 tests skipped:
        if ($line =~ /^([0-9]+) tests skipped:$/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }
        if ($line =~ /^([0-9]+) tests OK.$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

#jemalloc
# Test suite summary: pass: 30/33, skip: 3/33, fail: 0/33
        if ($line =~ /Test suite summary: pass: ([0-9]+)\/([0-9]+), skip: ([0-9]+)\/([0-9]+), fail: ([0-9]+)\/([0-9]+)/ and $incheck == 1) {
            $total_pass += $1;
            $total_tests += $2;
            $total_skip += $3;
            $total_fail += $5;
            next;
        }

# util-linux
#   All 160 tests PASSED
        if ($line =~ /  All ([0-9]+) tests PASSED$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# onig
# OK: // 'a'
        if ($line =~ /^OK\: / and $incheck == 1) {
            $counted_pass++;
            next;
        }

# nss
# cert.sh: #101: Import chain-2-serverCA-ec CA -t u,u,u for localhost.localdomain (ext.)  - PASSED
# Passed:             13036
# Failed:             6
# Failed with core:   0
# Unknown status:     0
        if ($line =~ /^[a-z]+.sh: #[0-9]+: .*  - PASSED$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /^[a-z]+.sh: #[0-9]+: .*  - FAILED$/ and $incheck == 1) {
            $counted_fail++;
            next;
        }
        if ($line =~ /^Passed:\s+([0-9]+)$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /^Failed:\s+([0-9]+)$/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /^Failed with core:\s+([0-9]+)$/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }

# rsync
#      34 passed
#      5 skipped
        if ($line =~ /^\s+([0-9]+) passed$/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
        if ($line =~ /^\s+([0-9]+) skipped$/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }

# mariadb
# 100% tests passed, 0 tests failed out of 53
        if ($line =~ /tests passed, ([0-9]+) tests failed out of ([0-9]+)/ and $incheck == 1) {
            $total_fail += $1;
            $total_tests += $2;
            $total_pass += $2 - $1;
            next;
        }

# python-runtime-tests
# FAILED (KNOWNFAIL=6, SKIP=18, errors=6)
# FAILED (failures=1)
# FAILED (failures=1, errors=499, skipped=48)
# OK (KNOWNFAIL=5, SKIP=15)
        if ($line =~ /FAILED \(KNOWNFAIL=([0-9]+), SKIP=([0-9]+), errors=([0-9]+)\)/ and $incheck == 1) {
            $total_xfail += $1;
            $total_skip += $2;
            $total_fail += $3;
            next;
        }
        if ($line =~ /FAILED \(failures=([0-9]+), errors=([0-9]+), skipped=([0-9]+)\)/ and $incheck == 1) {
            $total_xfail += $2;
            $total_skip += $3;
            $total_fail += $1;
            next;
        }
        if ($line =~ /FAILED \(failures=([0-9]+), errors=([0-9]+)\)/ and $incheck == 1) {
            $total_xfail += $2;
            $total_fail += $1;
            next;
        }
        if ($line =~ /FAILED \(failures=([0-9]+)\)/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /FAILED \(errors=([0-9]+)\)/ and $incheck == 1) {
            $total_xfail += $1;
            next;
        }
        if ($line =~ /OK \(KNOWNFAIL=([0-9]+), SKIP=([0-9]+)\)/ and $incheck == 1) {
            $total_xfail += $1;
            $total_skip += $2;
            next;
        }

# qpid-python
# Totals: 318 tests, 200 passed, 112 skipped, 0 ignored, 6 failed
        if ($line =~ /Totals: ([0-9]+) tests, ([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) ignored, ([0-9]+) failed/ and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $2;
            $total_skip += $3;
            $total_xfail += $4;
            $total_fail += $5;
            next;
        }

# PyYAML
# TESTS: 2577
        if ($line =~ /^TESTS: ([0-9]+)$/ and $incheck == 1) {
            $total_tests += $1;
            next;
        }

# sudo
# visudo: 7/7 tests passed; 0/7 tests failed
# check_symbols: 7 tests run, 0 errors, 100% success rate
        if ($line =~ /[a-z_]+\:\s+([0-9]+)\/[0-9]+ tests passed; ([0-9]+)\/[0-9]+ tests failed/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            next;
        }
        if ($line =~ /[a-z_]+\: ([0-9]+) tests run, ([0-9]+) errors/ and $incheck == 1) {
             $total_tests += $1;
             $total_fail += $2;
             $total_pass += $1 - $2;
             next;
        }

# R
# running code in 'reg-examples1.R' ... OK
# Status: 1 ERROR, 1 WARNING, 4 NOTEs
# OK: 749 SKIPPED: 4 FAILED: 2
        if ($line =~ /running code in '.*\.R' \.\.. OK/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /Status: ([0-9]+) ERROR, ([0-9]+) WARNING, ([0-9]+) NOTEs/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /OK: ([0-9]+) SKIPPED: ([0-9]+) FAILED: ([0-9]+)/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $3;
            $total_skip += $2;
            next;
        }

# php
# Number of tests : 13526              9794
# Tests skipped   : 3732 ( 27.6%) --------
# Tests warned    :    0 (  0.0%) (  0.0%)
# Tests failed    :   12 (  0.1%) (  0.1%)
# Expected fail   :   31 (  0.2%) (  0.3%)
# Tests passed    : 9751 ( 72.1%) ( 99.6%)
        if ($line =~ /^Number of tests : ([0-9]+)/ and $incheck == 1) {
            $total_tests += $1;
            next;
        }
        if ($line =~ /^Tests skipped   :\s+([0-9]+) \(/ and $incheck == 1) {
            $total_skip += $1;
            next;
        }
        if ($line =~ /^Tests failed    :\s+([0-9]+) \(/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~ /^Expected fail   :\s+([0-9]+) \(/ and $incheck == 1) {
            $total_xfail += $1;
            next;
        }
        if ($line =~ /^Tests passed    :\s+([0-9]+) \(/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# rubygem / rake
# 174 runs, 469 assertions, 0 failures, 0 errors, 0 skips
        if ($line =~ /([0-9]+) runs, ([0-9]+) assertions, ([0-9]+) failures, ([0-9]+) errors, ([0-9]+) skips/ and $incheck == 1) {
            $total_tests += $1;
            $total_fail += $3;
            $total_skip += $5;
            next;
        }

# cryptsetup
#  [OK]
        if ($incheck == 1 && $line =~ / \[OK\]$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# lzo
#  test passed.
        if ($line =~ / test passed.$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# lsof
# LTnlink ... OK
# LTnfs ... ERROR!!!
        if ($line =~ /^LT[a-zA-Z0-9]+ \.\.\. OK$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /^LT[a-zA-Z0-9]+ \.\.\. ERROR\!\!\!/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# libaio
# Pass: 11  Fail: 1
        if ($line =~ /^Pass: ([0-9]+)  Fail: ([0-9]+)$/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $1;
            next;
        }

# gawk
        if ($line =~ /^ALL TESTS PASSED$/ and $incheck == 1) {
            $total_pass++;
            next;
        }

# gptfdisk
# **SUCCESS** ...
        if ($line =~ /^\*\*SUCCESS\*\*/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# boost
# **passed** ...
# 8 errors detected.
        if ($line =~ /^\*\*passed\*\*/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~/([0-9]+) errors? detected\.?/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }
        if ($line =~/([0-9]+) failures? detected\.?/ and $incheck == 1) {
            $total_fail += $1;
            next;
        }

# make
# 534 Tests in 118 Categories Complete ... No Failures
        if ($line =~ /([0-9]+) Tests in ([0-9]+) Categories Complete ... No Failures/ and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $1;
            next;
        }

# icu4c ---[OK]
        if ($line =~ /---\[OK\]/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# libxslt
# Pass 1
        if ($line =~ /^Pass [0-9]+$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# apr-util
# :  SUCCESS
        if ($line =~ /:  SUCCESS$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# bash
# < Failed 126 of 1378 Unicode tests
        if ($line =~ /^[<,>] Failed ([0-9]+) of ([0-9]+)/ and $incheck == 1) {
            $total_fail+=$1;
            $total_tests+=$2;
            next;
        }

# crudini
# Test 95 OK (line 460)
        if ($line =~ /^Test [0-9]+ OK/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /^Test [0-9]+ [A-Z!O][A-Z!K]/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# discount
# Reddit-style automatic links ......................... OK
        if ($line =~ /[a-z\-]+ \.\.\.+ (OK|GOOD)$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /[a-z\-]+ \.\.\.+ [A-Z!O][A-Z!K]$/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# libjpeg-turbo
# JPEG -> RGB Top-Down  2/1 ... Passed.
# JPEG -> RGB Top-Down  15/8 ... Passed.
# JPEG -> RGB Top-Down  7/4 ... Passed.
        if ($line =~ /[A-Za-z0-9\ \>\<\/]+ \.\.\. Passed\./ and $incheck == 1) {
            $counted_pass++;
            next;
        }

# *** zlib test OK ***
# *** zlib 64-bit test OK ***
        if ($line =~ /\*\*\* zlib .*test OK \*\*\*/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /\*\*\* zlib .*test [A-Z!O][A-Z!K] \*\*\*/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

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
        if ($line =~ /[a-z\ ]+\ \.\.\.\ pass/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /[a-z\ ]+\ \.\.\.\ fail/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# keyring
#  76 passed, 62 skipped, 50 xfailed, 14 xpassed, 2 warnings, 32 error in 2.13 seconds
        if ($line =~ /([0-9]+) passed, ([0-9]+) skipped, ([0-9]+) xfailed, ([0-9]+) xpassed, ([0-9]+) warnings, ([0-9]+) error in [0-9\.]+ seconds/ and $incheck == 1) {
            $total_pass += $1 + $4;
            $total_skipp += $2;
            $total_xfail += $3;
            $total_fail =+ $5 + $6;
            next;
        }

# openblas
#  Real BLAS Test Program Results
#  Test of subprogram number  1             SDOT
#                                     ----- PASS -----
#  Test of subprogram number  2            SAXPY
#                                     ----- PASS -----
#  Test of subprogram number  3            SROTG
#                                     ----- PASS -----
        if ($line =~ /\ \ +\-\-\-+\ PASS\ \-\-\-+/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
        if ($line =~ /\ \ +\-\-\-+\ FAIL\ \-\-\-+/ and $incheck == 1) {
            $counted_fail++;
            next;
        }

# rubygem-hashie
# Finished in 0.07221 seconds (files took 0.28356 seconds to load)
# 545 examples, 0 failures, 1 pending
        if ($line =~ /([0-9]+) examples?, ([0-9]+) failures?, ([0-9]+) pending/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            $total_skip += $3;
            next;
        }

# rubygem-warden
# Finished in 0.08928 seconds (files took 0.1046 seconds to load)
# 215 examples, 14 failures
        if ($line =~ /([0-9]+) examples?, ([0-9]+) failures?/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            next;
        }

# rubygem-ansi
# Executed 12 tests with 7 passing, 5 errors.
        if ($line =~ /Executed ([0-9]+) tests with ([0-9+]) passing, ([0-9]+) errors\./ and $incheck == 1) {
            $total_tests += $1;
            $total_pass += $2;
            $total_fail += $3;
            next;
        }

# rubygem-formatador
#   9 succeeded in 0.00375661 seconds
        if ($line =~ /([0-9]+) succeeded in [0-9]+\.[0-9]+ seconds/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }

# ./pigz -kf pigz.c ; ./pigz -t pigz.c.gz
# ./pigz -kfb 32 pigz.c ; ./pigz -t pigz.c.gz
        if ($line =~ /.*\.\/pigz.+(\.\/pigz).+/ and $incheck == 1) {
            $total_pass += 2;
            next;
        } elsif ($line =~ /.*\.\/pigz.+/ and $incheck == 1) {
            $total_pass++;
            next;
        }

# netifaces
# Interface lo:
# Interface enp2s0:
        if ($line =~ /^Interface [a-zA-Z0-9]+\:/ and $incheck == 1) {
            $total_pass++;
            next;
        }

# btrfs-progs
# [TEST]   001-bad-file-extent-bytenr
# [NOTRUN] Need to validate root privileges
# test failed for case
        if ($line =~ /    \[TEST\]   .*/ and $incheck == 1) {
            $total_pass++;
            next;
        }
        if ($line =~ /test failed for case.*/ and $incheck == 1) {
            $total_fail++;
            $total_pass--;
            next;
        }
        if ($line =~ /    \[NOTRUN\] .*/ and $incheck == 1) {
            $total_skip++;
            next;
        }

# chrpath
# success: chrpath changed rpath to larger path.
# error: chrpath unable to change rpath to larger path.
        if ($line =~ /success\: chrpath .*/ and $incheck == 1) {
            $total_pass++;
            next;
        } elsif ($line =~ /error: chrpath .*/ and $incheck == 1) {
            $total_fail++;
            next;
        } elsif ($line =~ /warning: chrpath .*/ and $incheck == 1) {
            $total_fail++;
            next;
        }

# yajl
# 58/58 tests successful
        if ($line =~/([0-9]+)\/([0-9]+) tests successful/ and $incheck == 1) {
            $total_pass += $1;
            $total_tests += $2;
            next;
        }

# xmlsec1
#     Checking required transforms                            OK
#     Verify existing signature                             Fail
#     Checking required transforms                          Skip
#     Checking required key data                               OK
        if ($line =~ /^    [\w ]+\ +OK$/ and $incheck == 1) {
            $total_pass++;
            next;
        } elsif ($line =~ /^    [\w ]+\ +Fail$/ and $incheck == 1) {
            $total_fail++;
            next;
        } elsif ($line =~ /^    [\w ]+\ +Skip$/ and $incheck == 1) {
            $total_skip++;
            next;
        }

# xdg-utils
# TOTAL: 4 tests failed, 90 of 116 tests passed. (140 attempted)
        if ($line =~/TOTAL\: ([0-9]+) tests? failed\, ([0-9]+) of [0-9]+ tests? passed\. \(([0-9]+) attempted\)/ and $incheck == 1) {
            $total_fail += $1;
            $total_pass += $2;
            $total_skip += $3 - ($2 + $1);
            next;
        }

# slang
# Testing argv processing ...Ok
# ./utf8.sl:14:check_sprintf:Test Error
        if ($line =~/^Testing [\w ]+\.\.\.Ok$/ and $incheck == 1) {
            $total_pass++;
            next;
        }
        if ($line =~/^\.\/[A-Za-z0-9\.\<\>\:\ ]+\:Test Error$/ and $incheck == 1) {
            $total_fail++;
            next;
        }

#go & golang
#ok  	golang.org/x/text/encoding/htmlindex	0.002s  	
#--- FAIL: TestParents (0.00s)
#FAIL	golang.org/x/text/internal	0.002s
#--- PASS: TestApp_Command (0.00s)
#if ($line =~/^ok\s+[\w_]+[0-9A-Za-z\._\/]*\s+[0-9]+\.[0-9]+s$/ and $incheck == 1) {
        if ($line =~/^ok\s+[\w_]+[A-Za-z0-9\.\?_\-]*/ and $incheck == 1) {
            $total_tests++;
            $total_pass++;
            next;
        }
        if ($line =~/---\s+FAIL:|FAIL\s+ / and $incheck == 1) {
            $total_tests++;
            $total_fail++;
            next;
        }
        if ($line =~/---\s+PASS|PASS\s+ / and $incheck == 1) {
            $total_tests++;
            $total_pass++;
            next;
        }

# valgrind
# == 5 tests, 0 stderr failures, 1 stdout failure, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==
# == 55 tests, 48 stderr failures, 6 stdout failures, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==
# == 125 tests, 12 stderr failures, 0 stdout failures, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==
#if ($line =~/\=\= ([0-9]+) tests/ and $incheck == 1) {
        if ($line =~/\=\= ([0-9]+) tests?\, ([0-9]+) stderr failures?\, ([0-9]+) stdout failures?\, ([0-9]+) stderrB failures?\, ([0-9]+) stdoutB failures?\, ([0-9]+) post failures? \=\=/ and $incheck == 1) {
            $total_tests += $1;
            $total_fail += ($2 + $3 + $4 + $5 + $6);
            $total_pass += ($1 - ($2 + $3 + $4 + $5 + $6));
            next;
        }
# zsh
# **************************************
# 46 successful test scripts, 0 failures, 1 skipped
# **************************************
        if ($line =~/([0-9]+) successful test scripts\, ([0-9]+) failures\, ([0-9]+) skipped/ and $incheck == 1) {
            $total_pass += $1;
            $total_fail += $2;
            $total_skip += $3;
            next;
        }
# glog
# Passed 3 tests
        if ($line =~/Passed ([0-9]+) tests/ and $incheck == 1) {
            $total_pass += $1;
            next;
        }
# hdf5
# Testing h5repack h5repack_szip.h5 -f dset_szip:GZIP=1                  -SKIP-
# Verifying h5dump output -f GZIP=1 -m 1024                             *FAILED*
# Testing h5repack --metadata_block_size=8192                            PASSED
# Verifying h5diff output h5repack_layout.h5 out-meta_long.h5repack_layo PASSED
        if ($line =~/^Testing .+\ +PASSED$/ and $incheck == 1) {
            $total_pass ++;
            next;
        }
        if ($line =~/^Verifying .+\ +PASSED$/ and $incheck == 1) {
            $total_pass ++;
            next;
        }
        if ($line =~/^Testing .+\ +\-SKIP\-$/ and $incheck == 1) {
            $total_skip ++;
            next;
        }
        if ($line =~/^Verifying .+\ +\-SKIP\-$/ and $incheck == 1) {
            $total_skip ++;
            next;
        }
        if ($line =~/^Testing .+\ +\*FAILED\*$/ and $incheck == 1) {
            $total_fail ++;
            next;
        }
        if ($line =~/^Verifying .+\ +\*FAILED\*$/ and $incheck == 1) {
            $total_fail ++;
            next;
        }
# libconfig
# 3 tests; 3 passed, 0 failed
        if ($line =~/^([0-9]+) tests; ([0-9]+) passed\, ([0-9]+) failed/ and $incheck == 1) {
            $total_tests = $1;
            $total_pass = $2;
            $total_fail = $3;
            next;
        }
# libogg
# testing page spill expansion... 0, (0),  granule:0 1, (1),  granule:4103 2, (2),  granule:5127 ok.
# testing max packet segments... 0, (0),  granule:0 1, (1),  granule:261127 2, (2),  granule:262151 ok.
# testing very large packets... 0, (0),  granule:0 1, (1),  granule:1031 2, (2), 3, (3),  granule:4103 ok.
# testing continuation resync in very large packets... 0, 1, 2, (2), 3, (3),  granule:4103 ok.
# testing zero data page (1 nil packet)... 0, (0),  granule:0 1, (1),  granule:1031 2, (2),  granule:2055 ok.
# Testing search for capture... ok.
# Testing recapture... ok.
        if ($line =~/^[T,t]esting .*\ ok\.$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
# libvorbis
#     vorbis_1ch_q-0.5_44100.ogg : ok
#     vorbis_2ch_q-0.5_44100.ogg : ok
#     ...
#     vorbis_7ch_q-0.5_44100.ogg : ok
#     vorbis_8ch_q-0.5_44100.ogg : ok
        if ($line =~/^\ \ \ \ vorbis_.*\.ogg\ \:\ ok$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
# pth
# OK - ALL TESTS SUCCESSFULLY PASSED.
        if ($line =~/^OK\ \-\ ALL\ TESTS\ SUCCESSFULLY\ PASSED\.$/ and $incheck == 1) {
            $counted_pass++;
            next;
        }
    } 
    close($log);
}

sub sanitize_counts
{
    if ($total_tests > 0 && $total_pass == 0) {
        $total_pass = $total_tests - $total_fail - $total_skip - $total_xfail;
    }
    if ($total_tests < $total_pass && $total_pass > 0) {
        $total_tests = $total_pass + $total_fail + $total_skip + $total_xfail;
    }
    if ($counted_tests > 0 && $counted_pass == 0) {
        $counted_pass = $counted_tests - $counted_fail - $counted_skip - $counted_xfail;
    }
    if ($counted_tests < $counted_pass && $counted_pass > 0) {
        $counted_tests = $counted_pass + $counted_fail + $counted_skip + $counted_xfail;
    }
    if (($total_pass + $total_fail + $total_skip + $total_xfail) < $total_tests) {
        $total_pass+=$total_tests-($total_pass + $total_fail + $total_skip + $total_xfail);
    }
    if (($total_pass + $total_fail + $total_skip + $total_xfail) > $total_tests) {
        $total_tests = ($total_pass + $total_fail + $total_skip + $total_xfail)
    }
}

sub collect_output
{
    if ($counted_tests > $total_tests) {
        $testcount{$name} += $counted_tests;
        $testpass{$name} += $counted_pass;
        $testfail{$name} += $counted_fail;
        $testxfail{$name} += $counted_xfail;
        $testskip{$name} += $counted_skip;
        if ($counted_tests > 0) {
            $pkg_has_tests++;
        }
    } else {
        $testcount{$name} += $total_tests;
        $testpass{$name} += $total_pass;
        $testfail{$name} += $total_fail;
        $testxfail{$name} += $total_xfail;
        $testskip{$name} += $total_skip;
        if ($total_tests > 0) {
            $pkg_has_tests++;
        }
    }

    $total_tests = 0;
    $total_pass = 0;
    $total_fail = 0;
    $total_xfail = 0;
    $total_skip = 0;

    $counted_tests = 0;
    $counted_pass = 0;
    $counted_fail = 0;
    $counted_xfail = 0;
    $counted_skip = 0;
}

sub print_output
{
    $count = keys %testcount;
    if ($count > 1) {
        foreach my $key (sort(keys(%testcount))) {
            if ($key) {
                print $key;
                print ",$testcount{$key},$testpass{$key},$testfail{$key},$testskip{$key},$testxfail{$key}";
                print "\n";
            }
        }
    } else {
        foreach my $key (sort(keys(%testcount))) {
            print ",$testcount{$key},$testpass{$key},$testfail{$key},$testskip{$key},$testxfail{$key}";
            print "\n";
        }
    }
}

$total_tests = 0;
$total_pass = 0;
$total_fail = 0;
$total_xfail = 0;
$total_skip = 0;

$counted_tests = 0;
$counted_pass = 0;
$counted_fail = 0;
$counted_xfail = 0;
$counted_skip = 0;

parse_log($ARGV[0]);
sanitize_counts();
collect_output();
print_output();
