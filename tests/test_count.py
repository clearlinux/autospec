import unittest
from unittest.mock import mock_open, patch
import count

pats = [
    # acl
    ('[22] $ rm -Rf d -- ok-',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('17 commands (17 passed, 1 failed)-',
     [18, 17, 1, 0, 0, 0, 0, 0, 0, 0]),
    # alembic
    ('Ran 678 tests in 5.175s',
     [678, 678, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('OK (SKIP=15)',
     [15, 0, 0, 0, 15, 0, 0, 0, 0, 0]),
    ('OK (skipped=16)',
     [16, 0, 0, 0, 16, 0, 0, 0, 0, 0]),
    # anyjson
    ('test_implementations.test_default_serialization ... ok',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('test_implementations.test_default_serialization ... skipped',
     [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    # apr
    ('testatomic          :  SUCCESS',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # cryptography
    ('================= 76230 passed, 267 skipped in 140.23 seconds ==================',
     [76497, 76230, 0, 0, 267, 0, 0, 0, 0, 0]),
    ('================== 47 passed, 2 error in 10.36 seconds =========================',
     [49, 47, 2, 0, 0, 0, 0, 0, 0, 0]),
    ('================ 10 failed, 16 passed, 4 error in 0.16 seconds =================',
     [30, 16, 14, 0, 0, 0, 0, 0, 0, 0]),
    ('========================== 43 passed in 2.90 seconds ===========================',
     [43, 43, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('======= 28 failed, 281 passed, 13 skipped, 10 warnings in 28.48 seconds ========',
     [332, 281, 38, 0, 13, 0, 0, 0, 0, 0]),
    ('===================== 5 failed, 318 passed in 1.06 seconds =====================',
     [323, 318, 5, 0, 0, 0, 0, 0, 0, 0]),
    ('===================== 5 failed, 9 passed, 7 xfailed in 1.06 seconds ============',
     [21, 9, 5, 7, 0, 0, 0, 0, 0, 0]),
    ('============= 1628 passed, 72 skipped, 4 xfailed in 146.26 seconds =============',
     [1704, 1628, 0, 4, 72, 0, 0, 0, 0, 0]),
    ('=============== 119 passed, 2 skipped, 54 error in 2.19 seconds ================',
     [175, 119, 54, 0, 2, 0, 0, 0, 0, 0]),
    ('========== 1 failed, 74 passed, 10 skipped, 55 error in 2.05 seconds ===========',
     [140, 74, 56, 0, 10, 0, 0, 0, 0, 0]),
    ('==================== 68 passed, 1 warnings in 0.12 seconds =====================',
     [69, 68, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('================ 3 failed, 250 passed, 3 error in 3.28 seconds =================',
     [256, 250, 6, 0, 0, 0, 0, 0, 0, 0]),
    ('=============== 1 failed, 407 passed, 10 skipped in 4.71 seconds ===============',
     [418, 407, 1, 0, 10, 0, 0, 0, 0, 0]),
    ('========================== 1 skipped in 0.79 seconds ===========================',
     [1, 0, 0, 0, 1, 0, 0, 0, 0, 0]),
    ('=========================== 3 error in 0.41 seconds ============================',
     [3, 0, 3, 0, 0, 0, 0, 0, 0, 0]),
    ('================= 68 passed, 1 pytest-warnings in 0.09 seconds =================',
     [68, 68, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('===== 21 failed, 73 passed, 5 skipped, 2 pytest-warnings in 34.81 seconds ======',
     [99, 73, 21, 0, 5, 0, 0, 0, 0, 0]),
    # swift
    ('========= 1 failed, 1287 passed, 1 warnings, 62 error in 35.77 seconds =========',
     [1351, 1287, 64, 0, 0, 0, 0, 0, 0, 0]),
    (' 487 failed, 4114 passed, 32 skipped, 1 pytest-warnings, 34 error in 222.82 seconds',
     [4667, 4114, 521, 0, 32, 0, 0, 0, 0, 0]),
    # tox
    ('======== 199 passed, 38 skipped, 1 xpassed, 1 warnings in 5.76 seconds =========',
     [239, 199, 1, 1, 38, 0, 0, 0, 0, 0]),
    # augeas
    ('# TOTAL: 215\n'
     '# PASS:  212\n'
     '# SKIP:  3\n'
     '# XFAIL: 0\n'
     '# FAIL:  0\n'
     '# XPASS: 0\n'
     '# ERROR: 0',
     [215, 212, 0, 0, 3, 0, 0, 0, 0, 0]),
    # autoconf
    ('493 tests behaved as expected\n'
     '10 tests were skipped.\n'
     '495: AC_FUNC_STRNLEN                                 ok\n'
     '344: Erlang                                          skipped (erlang.at:30)\n'
     '26: autoupdating macros recursively                 expected failure (tools.at:945)',
    [503, 493, 0, 0, 10, 3, 1, 0, 1, 1]),
    # bison
    ('470 tests were successful',
    [470, 470, 0, 0, 0, 0, 0, 0, 0, 0]),
    # binutils
    ('# of expected passes\t1144\n'
     '# of expected failures\t57\n'
     '# of untested testcases\t1\n'
     '# of unsupported tests\t12\n'
     '# of unexpected failures\t1\n',
     [1214, 1144, 1, 57, 12, 0, 0, 0, 0, 0]),
    # ccache
    ('PASSED: 448 assertions, 88 tests, 10 suites',
     [88, 88, 0, 0, 0, 0, 0, 0, 0, 0]),
    # rubygem-rack
    ('701 tests, 2292 assertions, 0 failures, 0 errors',
     [701, 701, 0, 0, 0, 0, 0, 0, 0, 0]),
    # curl
    ('TESTDONE: 680 tests out of 686 reported OK: 99%',
     [686, 680, 6, 0, 0, 0, 0, 0, 0, 0]),
    # gcc
    ('All 4 tests passed\n'
     'PASS: test-strtol-16\n'
     'FAIL: test-strtol-32',
     [4, 4, 0, 0, 0, 2, 1, 1, 0, 0]),
    # gdbm
    ('All 22 tests were successful.',
     [22, 22, 0, 0, 0, 0, 0, 0, 0, 0]),
    # glibc
    ('3 FAIL\n'
     '2182 PASS\n'
     '1 UNRESOLVED\n'
     '199 XFAIL\n'
     '3 XPASS',
     [2387, 2185, 3, 199, 0, 0, 0, 0, 0, 0]),
    # libxml2
    ('Total 2908 tests, no errors',
     [2908, 2908, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('Total: 1171 functions, 291083 tests, 0 errors',
     [1171, 1171, 0, 0, 0, 0, 0, 0, 0, 0]),
    # zlib
    ('*** zlib shared test OK ***',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # e2fsprogs
    ('153 tests succeeded     1 tests failed',
     [154, 153, 1, 0, 0, 0, 0, 0, 0, 0]),
    # expect
    ('all.tcl:     Total   41     Passed   29     Skipped   2     Failed   10',
     [41, 29, 10, 0, 2, 0, 0, 0, 0, 0]),
    # expat
    ('50%: Checks: 50, Failed: 25',
     [50, 25, 25, 0, 0, 0, 0, 0, 0, 0]),
    # flex
    ('Tests succeeded: 47\n'
     'Tests FAILED: 3',
     [50, 47, 3, 0, 0, 0, 0, 0, 0, 0]),
    # TAP and perl-Capture-tiny
    ('ok 580 - tee_merged|sys|stderr|short = got STDERR',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('not ok 580 - tee_merged|sys|stderr|short = got STDERR',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    ('not ok 580 - tee_merged|sys|stderr|short = got STDERR  # TODO known breakage',
     [0, 0, 0, 0, 0, 0, 0, 0, 1, 0]),
    ('ok 9',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('not ok 9',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    # tcpdump
    ('    1 test failed\n'
     ' 154 tests passed',
     [155, 154, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('    2 tests failed\n'
     ' 154 tests passed',
     [156, 154, 2, 0, 0, 0, 0, 0, 0, 0]),
    # R packages
    ('* checking top-level files ... OK',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('* checking top-level files ... PASSED.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('* checking top-level files ... SKIPPED',
     [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    # python
    ('365 tests OK.\n'
     '22 tests skipped:',
     [387, 365, 0, 0, 22, 0, 0, 0, 0, 0]),
    # jemalloc
    ('Test suite summary: pass: 30/33, skip: 3/33, fail: 0/33',
     [33, 30, 0, 0, 3, 0, 0, 0, 0, 0]),
    # util-linux
    ('  All 160 tests PASSED',
     [160, 160, 0, 0, 0, 0, 0, 0, 0, 0]),
    # onig
    ("OK: // 'a'",
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # nss
    ('cert.sh: #101: Import chain-2-serverCA-ec CA -t u,u,u for localhost.localdomain (ext.)  - PASSED\n'
     'Passed:             13036\n'
     'Failed:             6\n'
     'Failed with core:   0\n'
     'Unknown status:     0',
     [13042, 13036, 6, 0, 0, 1, 1, 0, 0, 0]),
    # nss
    ('cert.sh: #101: Import chain-2-serverCA-ec CA -t u,u,u for localhost.localdomain (ext.)  - FAILED\n'
     'Passed:             13036\n'
     'Failed:             6\n'
     'Failed with core:   0\n'
     'Unknown status:     0',
     [13042, 13036, 6, 0, 0, 0, 0, 1, 0, 0]),
    # rsync
    ('     34 passed\n'
     '     5 skipped',
     [39, 34, 0, 0, 5, 0, 0, 0, 0, 0]),
    # mariadb
    ('50% tests passed, 20 tests failed out of 40',
     [40, 20, 20, 0, 0, 0, 0, 0, 0, 0]),
    # python-runtime-tests
    ('FAILED (KNOWNFAIL=6, SKIP=18, errors=6)',
     [30, 0, 6, 6, 18, 0, 0, 0, 0, 0]),
    ('FAILED (failures=1, errors=499, skipped=48)',
     [548, 0, 1, 499, 48, 0, 0, 0, 0, 0]),
    ('FAILED (failures=1, errors=499)',
     [500, 0, 1, 499, 0, 0, 0, 0, 0, 0]),
    ('FAILED (failures=1)',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('FAILED (errors=1)',
     [1, 0, 0, 1, 0, 0, 0, 0, 0, 0]),
    ('OK (KNOWNFAIL=5, SKIP=15)',
     [20, 0, 0, 5, 15, 0, 0, 0, 0, 0]),
    # qpid-python
    ('Totals: 318 tests, 200 passed, 112 skipped, 0 ignored, 6 failed',
     [318, 200, 6, 0, 112, 0, 0, 0, 0, 0]),
    # PyYAML
    ('TESTS: 2577',
     [2577, 2577, 0, 0, 0, 0, 0, 0, 0, 0]),
    # sudo
    ('visudo: 7/7 tests passed; 0/7 tests failed',
     [7, 7, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('check_symbols: 7 tests run, 0 errors, 100% success rate',
     [7, 7, 0, 0, 0, 0, 0, 0, 0, 0]),
    # R
    ("running code in 'reg-examples1.R' ... OK",
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('Status: 1 ERROR, 1 WARNING, 4 NOTEs',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('OK: 749 SKIPPED: 4 FAILED: 2',
     [755, 749, 2, 0, 4, 0, 0, 0, 0, 0]),
    # php
    ('Number of tests : 13526              9794\n'
     'Tests skipped   : 3732 ( 27.6%) --------\n'
     'Tests warned    :    0 (  0.0%) (  0.0%)\n'
     'Tests failed    :   12 (  0.1%) (  0.1%)\n'
     'Expected fail   :   31 (  0.2%) (  0.3%)\n'
     'Tests passed    : 9751 ( 72.1%) ( 99.6%)',
     [13526, 9751, 12, 31, 3732, 0, 0, 0, 0, 0]),
    # rubygem/rake
    ('174 runs, 469 assertions, 0 failures, 0 errors, 0 skips',
     [174, 174, 0, 0, 0, 0, 0, 0, 0, 0]),
    # cryptsetup
    (' [OK]',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # lzo
    (' test passed.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # lsof
    ('LTnlink ... OK',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('LTnfs ... ERROR!!!',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    # libaio
    ('Pass: 11  Fail: 1',
     [12, 11, 1, 0, 0, 0, 0, 0, 0, 0]),
    # gawk
    ('ALL TESTS PASSED',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    # gptfdisk
    ('**SUCCESS**',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # boost
    ('**passed** ...',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('8 errors detected.',
     [8, 0, 8, 0, 0, 0, 0, 0, 0, 0]),
    ('8 failures detected.',
     [8, 0, 8, 0, 0, 0, 0, 0, 0, 0]),
    # make
    ('534 Tests in 118 Categories Complete ... No Failures',
     [534, 534, 0, 0, 0, 0, 0, 0, 0, 0]),
    # icu4c
    ('---[OK]',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # libxslt
    ('Pass 1',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # apr-util
    (':  SUCCESS',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # bash
    ('< Failed 126 of 1378 Unicode tests',
     [1378, 1252, 126, 0, 0, 0, 0, 0, 0, 0]),
    # crudini
    ('Test 95 OK (line 460)',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('Test 95 BAD',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    # discount
    ('Reddit-style automatic links ............................... OK',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('Reddit-style automatic links .............................. BAD',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    # libjpeg-turbo
    ('JPEG -> RGP Top-Down 2/1 ... Passed.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # zlib
    ('*** zlib test OK ***',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('*** zlib 64-bit test OK ***',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # LVM2
    ('valgrind pool awareness ... fail',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    ('dfa with non-print regex chars ... pass',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # keyring
    ('76 passed, 62 skipped, 50 xfailed, 14 xpassed, 2 warnings, 32 error in 2.13 seconds',
     [236, 90, 34, 50, 62, 0, 0, 0, 0, 0]),
    # openblas
    ('  ----- PASS -----',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('  ----- FAIL -----',
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]),
    # rubygem-hashie
    ('545 examples, 0 failures, 1 pending',
     [546, 545, 0, 0, 1, 0, 0, 0, 0, 0]),
    # rubygem-warden
    ('215 examples, 14 failures',
     [229, 215, 14, 0, 0, 0, 0, 0, 0, 0]),
    # rubygem-ansi
    ('Executed 12 tests with 7 passing, 5 errors.',
     [12, 7, 5, 0, 0, 0, 0, 0, 0, 0]),
    # vim
    ('Executed 12 tests',
     [12, 12, 0, 0, 0, 0, 0, 0, 0, 0]),
    # rubygem-formatador
    ('  9 succeeded in 0.00375661 seconds',
     [9, 9, 0, 0, 0, 0, 0, 0, 0, 0]),
    # pigz
    ('./pigz -kf pigz.c ; ./pigz -t pigz.c.gz',
     [2, 2, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('./pigz -kfb 32 pigz.c',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    # netifaces
    ('Interface lo:',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    # btrfs-progs
    ('    [TEST]    001-bad-file-extent-bytenr',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('    [NOTRUN]  Need to validate root privileges',
     [1, 0, 0, 0, 1, 0, 0, 0, 0, 0]),
    ('test failed for case',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    # chrpath
    ('success: chrpath changed rpath to larger path.',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('error: chrpath unable to change rpath to larger path.',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('warning: chrpath does not have root permissions',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    # yajl
    ('58/58 tests successful',
     [58, 58, 0, 0, 0, 0, 0, 0, 0, 0]),
    # xmlsec1
    ('    Checking required transforms                            OK',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('    Verify existing signature                             Fail',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('    Checking required transforms                          Skip',
     [1, 0, 0, 0, 1, 0, 0, 0, 0, 0]),
    # xdg-utils
    ('TOTAL: 4 tests failed, 90 of 116 tests passed. (140 attempted)',
    [140, 90, 4, 0, 46, 0, 0, 0, 0, 0]),
    # slang
    ('Testing argv processing ...Ok',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('./utf8.sl:14:check_sprintf:Test Error',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    # go & golang
    ('ok    golang.org/x/text/encoding/htmlindex    0.002s',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('--- FAIL: TestParents (0.00s)',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('FAIL	golang.org/x/text/internal	0.002s',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('--- PASS: TestApp_Command (0.00s)',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    # valgrind
    ('== 5 tests, 0 stderr failures, 1 stdout failure, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==',
     [5, 4, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('== 55 tests, 48 stderr failures, 6 stdout failures, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==',
     [55, 1, 54, 0, 0, 0, 0, 0, 0, 0]),
    ('== 125 tests, 12 stderr failures, 0 stdout failures, 0 stderrB failures, 0 stdoutB failures, 0 post failures ==',
     [125, 113, 12, 0, 0, 0, 0, 0, 0, 0]),
    # zsh
    ('46 successful test scripts, 0 failures, 1 skipped',
     [47, 46, 0, 0, 1, 0, 0, 0, 0, 0]),
    # glog
    ('Passed 3 tests',
     [3, 3, 0, 0, 0, 0, 0, 0, 0, 0]),
    # hdf5
    ('Testing h5repack h5repack_szip.h5 -f dset_szip:GZIP=1                  -SKIP-',
     [1, 0, 0, 0, 1, 0, 0, 0, 0, 0]),
    ('Verifying h5repack h5repack_szip.h5 -f dset_szip:GZIP=1                -SKIP-',
     [1, 0, 0, 0, 1, 0, 0, 0, 0, 0]),
    ('Verifying h5dump output -f GZIP=1 -m 1024                             *FAILED*',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('Testing h5dump output -f GZIP=1 -m 1024                               *FAILED*',
     [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    ('Testing h5repack --metadata_block_size=8192                            PASSED',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    ('Verifying h5diff output h5repack_layout.h5 out-meta_long.h5repack_layo PASSED',
     [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    # libconfig
    ('3 tests; 3 passed, 0 failed',
     [3, 3, 0, 0, 0, 0, 0, 0, 0, 0]),
    # libogg
    ('testing page spill expansion... 0, (0),  granule:0 1, (1),  granule:4103 2, (2),  granule:5127 ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('testing max packet segments... 0, (0),  granule:0 1, (1),  granule:261127 2, (2),  granule:262151 ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('testing very large packets... 0, (0),  granule:0 1, (1),  granule:1031 2, (2), 3, (3),  granule:4103 ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('testing continuation resync in very large packets... 0, 1, 2, (2), 3, (3),  granule:4103 ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('testing zero data page (1 nil packet)... 0, (0),  granule:0 1, (1),  granule:1031 2, (2),  granule:2055 ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('Testing search for capture... ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('Testing recapture... ok.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # libvorbis
    ('    vorbis_1ch_q-0.5_44100.ogg : ok',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('    vorbis_2ch_q-0.5_44100.ogg : ok',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('    vorbis_7ch_q-0.5_44100.ogg : ok',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    ('    vorbis_8ch_q-0.5_44100.ogg : ok',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # pth
    ('OK - ALL TESTS SUCCESSFULLY PASSED.',
     [0, 0, 0, 0, 0, 1, 1, 0, 0, 0]),
    # casync (uses meson / ninja)
    ("ninja: Entering directory `builddir'\n"
     '[0/1] /usr/bin/python3 -u /usr/bin/meson test --no-rebuild --print-errorlogs\n'
     ' 1/16 test-script.sh                          OK      21.20 s \n'
     ' 2/16 test-script-sha256.sh                   OK      23.13 s \n'
     ' 3/16 test-script-gzip.sh                     OK      20.91 s \n'
     ' 4/16 test-script-xz.sh                       OK      29.97 s \n'
     ' 5/16 test-nbd.sh                             OK       0.91 s \n'
     ' 6/16 test-fuse.sh                            OK       1.25 s \n'
     ' 7/16 test-cachunk                            OK       0.02 s \n'
     ' 8/16 test-cachunker                          OK       0.70 s \n'
     ' 9/16 test-cachunker-histogram                OK       2.04 s \n'
     '10/16 test-cadigest                           OK      10.01 s \n'
     '11/16 test-caencoder                          OK       0.05 s \n'
     '12/16 test-camakebst                          OK       3.21 s \n'
     '13/16 test-caorigin                           OK       0.00 s \n'
     '14/16 test-casync                             OK       0.74 s \n'
     '15/16 test-cautil                             OK       0.00 s \n'
     '16/16 test-util                               OK       0.01 s \n'
     '\n'
     'OK:        16\n'
     'FAIL:       0\n'
     'SKIP:       0\n'
     'TIMEOUT:    0\n',
     [16, 16, 0, 0, 0, 0, 0, 0, 0, 0]),
    # gstreamer (uses meson / ninja)
    ('+ meson test -C builddir\n'
     "ninja: Entering directory `builddir'\n"
     'ninja: no work to do.\n'
     '1/6 gst_gst                                  OK       0.40 s\n'
     '2/6 gst_gstabi                               FAIL     0.35 s\n'
     '3/6 pipelines_stress                         OK       10.49 s\n'
     '4/6 generic_sinks                            EXPECTEDFAIL 4.12 s\n'
     '5/6 gst_gstcpp                               OK       0.37 s\n'
     '6/6 libs_gstlibscpp                          OK       0.03 s\n'
     'Ok:                   4\n'
     'Expected Fail:        1\n'
     'Fail:                 1\n'
     'Unexpected Pass:      0\n'
     'Skipped:              0\n'
     'Timeout:              0\n',
     [6, 4, 1, 1, 0, 0, 0, 0, 0, 0]),
]

backup_zero_test_data = count.zero_test_data

def mock_zero_test_data():
    pass


class TestCount(unittest.TestCase):

    def setUp(self):
        count.zero_test_data()


def test_generator(line, expected):
    """
    Generate a test for each line passed in
    """
    def test_parse_log(self):
        """
        test parse_log
        expected = [total_tests,
                    total_pass,
                    total_fail,
                    total_xfail,
                    total_skip,
                    counted_tests,
                    counted_pass,
                    counted_fail,
                    counted_xfail,
                    counted_skip]
        """
        content = '+ make check\n' + line
        m_open = mock_open(read_data=content)
        with patch('count.util.open_auto', m_open, create=True):
            count.zero_test_data = mock_zero_test_data
            count.parse_log('log')
            count.zero_test_data = backup_zero_test_data

        actual = [count.total_tests,
                  count.total_pass,
                  count.total_fail,
                  count.total_xfail,
                  count.total_skip,
                  count.counted_tests,
                  count.counted_pass,
                  count.counted_fail,
                  count.counted_xfail,
                  count.counted_skip]

        self.assertEqual(actual, expected)

    return test_parse_log


def test_setup():
    for i, pat in enumerate(pats):
        test_name = 'test_pat{}'.format(pat[0])
        test = test_generator(pat[0], pat[1])
        setattr(TestCount, test_name, test)


# Run test_setup() to generate tests
test_setup()


if __name__ == "__main__":
    unittest.main(buffer=True)
