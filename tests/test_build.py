import unittest
import tempfile
import os
from unittest.mock import patch, mock_open, MagicMock
import build
import buildreq
import config
import files
import tarball

class TestBuildpattern(unittest.TestCase):

    def test_simple_pattern_pkgconfig(self):
        """
        Test simple_pattern_pkgconfig with match
        """
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.simple_pattern_pkgconfig('line to test for testpkg.xyz',
                                     r'testpkg.xyz',
                                     'testpkg',
                                     False,
                                     reqs)
        self.assertIn('pkgconfig(testpkg)', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_simple_pattern_pkgconfig_32bit(self):
        """
        Test simple_pattern_pkgconfig with match and 32bit option set
        """
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.simple_pattern_pkgconfig('line to test for testpkg.zyx',
                                     r'testpkg.zyx',
                                     'testpkgz',
                                     True,
                                     reqs)
        self.assertIn('pkgconfig(32testpkgz)', reqs.buildreqs)
        self.assertIn('pkgconfig(testpkgz)', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_simple_pattern_pkgconfig_no_match(self):
        """
        Test simple_pattern_pkgconfig with no match, nothing should be modified
        """
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.simple_pattern_pkgconfig('line to test for somepkg.xyz',
                                     r'testpkg.xyz',
                                     'testpkg',
                                     False,
                                     reqs)
        self.assertEqual(reqs.buildreqs, set())
        self.assertEqual(pkg.must_restart, 0)

    def test_simple_pattern(self):
        """
        Test simple_pattern with match. The main difference between
        simple_pattern and simple_pattern_pkgconfig is the string that is added
        to buildreq.buildreqs.
        """
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.simple_pattern('line to test for testpkg.xyz',
                           r'testpkg.xyz',
                           'testpkg',
                           reqs)
        self.assertIn('testpkg', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_simple_pattern_no_match(self):
        """
        Test simple_pattern with no match, nothing should be modified
        """
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.simple_pattern('line to test for somepkg.xyz',
                           r'testpkg.xyz',
                           'testpkg',
                           reqs)
        self.assertEqual(reqs.buildreqs, set())
        self.assertEqual(pkg.must_restart, 0)

    def test_failed_pattern_no_match(self):
        """
        Test failed_pattern with no match
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: somepkg', conf, reqs, r'(test)', 0)
        self.assertEqual(reqs.buildreqs, set())
        self.assertEqual(pkg.must_restart, 0)

    def test_failed_pattern_no_buildtool(self):
        """
        Test failed_pattern with buildtool unset and initial match, but no
        match in failed_commands.
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg', conf, reqs, r'(test)', 0)
        self.assertEqual(reqs.buildreqs, set())
        self.assertEqual(pkg.must_restart, 0)

    def test_failed_pattern_no_buildtool_match(self):
        """
        Test failed_pattern with buildtool unset and match in failed_commands
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        conf.setup_patterns()
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: lex', conf, reqs, r'(lex)', 0)
        self.assertIn('flex', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_pkgconfig(self):
        """
        Test failed_pattern with buildtool set to pkgconfig
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg.xyz',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='pkgconfig')
        self.assertIn('pkgconfig(testpkg)', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_R(self):
        """
        Test failed_pattern with buildtool set to R
        """
        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg.r',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='R')
        self.assertIn('R-testpkg', reqs.buildreqs)
        self.assertNotIn('R-testpkg', reqs.requires[None])
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_perl(self):
        """
        Test failed_pattern with buildtool set to perl
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg.pl',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='perl')
        self.assertIn('perl(testpkg)', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_pypi(self):
        """
        Test failed_pattern with buildtool set to pypi
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg.py',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='pypi')
        self.assertIn('testpkg-python', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_ruby(self):
        """
        Test failed_pattern with buildtool set to ruby, but no match in
        config.gems, it should just prepend 'rubygem-' to the package name.
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg.rb',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='ruby')
        self.assertIn('rubygem-testpkg', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_ruby_gem_match(self):
        """
        Test failed_pattern with buildtool set to ruby and a match in
        config.gems. In the particular case of test/unit, the result should
        be rubygem-test-unit.
        """
        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: test/unit',
                             conf,
                             reqs,
                             r'(test/unit)',
                             0,  # verbose=0
                             buildtool='ruby')
        self.assertIn('rubygem-test-unit', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_ruby_table(self):
        """
        Test failed_pattern with buildtool set to ruby table and a match in
        config.gems
        """
        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: test/unit',
                             conf,
                             reqs,
                             r'(test/unit)',
                             0,  # verbose=0
                             buildtool='ruby table')
        self.assertIn('rubygem-test-unit', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_ruby_table_no_match(self):
        """
        Test failed_pattern with buildtool set to ruby table but no match in
        config.gems. This should not modify anything.
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='ruby table')
        self.assertEqual(reqs.buildreqs, set())
        self.assertEqual(pkg.must_restart, 0)

    def test_failed_pattern_maven(self):
        """
        Test failed_pattern with buildtool set to maven, but no match in
        config.maven_jars, it should just prepend 'mvn-' to the package name.
        """
        conf = config.Config('')
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: testpkg',
                             conf,
                             reqs,
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='maven')
        self.assertIn('mvn-testpkg', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_failed_pattern_maven_match(self):
        """
        Test failed_pattern with buildtool set to maven with a match in
        config.maven_jars. In the particular case of aether, the corresponding
        maven jar is 'mvn-aether-core'
        """
        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        pkg = build.Build()
        pkg.failed_pattern('line to test for failure: aether',
                             conf,
                             reqs,
                             r'(aether)',
                             0,  # verbose=0
                             buildtool='maven')
        self.assertIn('mvn-aether-core', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_parse_buildroot_log_fail(self):
        """
        Test parse_buildroot_log with a test log indicating failure due to
        missing dependencies ('foobar' and 'foobarbaz')
        """
        def mock_util_call(cmd):
            del cmd

        call_backup = build.util.call
        build.util.call = mock_util_call

        open_name = 'build.util.open_auto'
        content = "line1\nDEBUG util.py:399:  No matching package to install: 'foobar'\nDEBUG util.py:399:  No matching package to install: 'foobarbaz'\nline 4"
        m_open = mock_open(read_data=content)
        pkg = build.Build()

        result = True
        with patch(open_name, m_open, create=True):
            result = pkg.parse_buildroot_log('testname', 1)

        build.util.call = call_backup

        self.assertFalse(result)
        self.assertEqual(pkg.must_restart, 0)

    def test_parse_buildroot_log_pass(self):
        """
        Test parse_buildroot_log with a test log indicating no failures
        """
        def mock_util_call(cmd):
            del cmd

        call_backup = build.util.call
        build.util.call = mock_util_call

        open_name = 'build.util.open_auto'
        content = "line 1\nline 2\nline 3\nline 4"
        m_open = mock_open(read_data=content)
        pkg = build.Build()

        result = True
        with patch(open_name, m_open, create=True):
            result = pkg.parse_buildroot_log('testname', 1)

        build.util.call = call_backup

        self.assertTrue(result)
        self.assertEqual(pkg.must_restart, 0)

    def test_parse_buildroot_log_noop(self):
        """
        Test parse_buildroot_log when parsing should be skipped (i.e. mock
        returned 0)
        """
        def mock_util_call(cmd):
            del cmd

        call_backup = build.util.call
        build.util.call = mock_util_call

        open_name = 'build.util.open_auto'
        content = "line 1\nline 2\nline 3\nline 4"
        m_open = mock_open(read_data=content)
        pkg = build.Build()

        result = True
        with patch(open_name, m_open, create=True):
            result = pkg.parse_buildroot_log('testname', 0)

        build.util.call = call_backup

        self.assertTrue(result)

    def test_parse_build_results_pkgconfig(self):
        """
        Test parse_build_results with a test log indicating failure due to a
        missing qmake package (pkgconfig error)
        """
        def mock_util_call(cmd):
            del cmd

        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        tcontent = tarball.Content("", "", "", [], conf, "/")
        conf.config_opts['32bit'] = True
        call_backup = build.util.call
        build.util.call = mock_util_call
        pkg = build.Build()
        fm = files.FileManager(conf, pkg)

        open_name = 'build.util.open_auto'
        content = 'line 1\nwhich: no qmake\nexiting'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            pkg.parse_build_results('testname', 0, fm, conf, reqs, tcontent)

        build.util.call = call_backup

        self.assertIn('pkgconfig(Qt)', reqs.buildreqs)
        self.assertIn('pkgconfig(32Qt)', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_parse_build_results_simple_pats(self):
        """
        Test parse_build_results with a test log indicating failure due to a
        missing httpd-dev package (simple pat error)
        """
        def mock_util_call(cmd):
            del cmd

        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        tcontent = tarball.Content("", "", "", [], conf, "/")
        call_backup = build.util.call
        build.util.call = mock_util_call
        pkg = build.Build()
        fm = files.FileManager(conf, pkg)

        open_name = 'build.util.open_auto'
        content = 'line 1\nchecking for Apache test module support\nexiting'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            pkg.parse_build_results('testname', 0, fm, conf, reqs, tcontent)

        build.util.call = call_backup

        self.assertIn('httpd-dev', reqs.buildreqs)
        self.assertEqual(pkg.must_restart, 1)

    def test_parse_build_results_failed_pats(self):
        """
        Test parse_build_results with a test log indicating failure due to a
        missing package.
        """
        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        tcontent = tarball.Content("", "", "", [], conf, "/")
        call_backup = build.util.call
        open_auto_backup = build.util.open_auto
        build.util.call = MagicMock(return_value=None)
        pkg = build.Build()
        fm = files.FileManager(conf, pkg)

        with open('tests/builderrors', 'r') as f:
            builderrors = f.readlines()
            for error in builderrors:
                if not error.startswith('#'):
                    input, output = error.strip('\n').split('|')
                    reqs.buildreqs = set()
                    build.util.open_auto = mock_open(read_data=input)
                    pkg.parse_build_results('testname', 0, fm, conf, reqs, tcontent)

                    self.assertIn(output, reqs.buildreqs)
                    self.assertGreater(pkg.must_restart, 0)

        # Restoring functions
        build.util.call = call_backup
        build.util.open_auto = open_auto_backup

    def test_parse_build_results_files(self):
        """
        Test parse_build_results with a test log indicating files are missing
        """
        def mock_util_call(cmd):
            del cmd

        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        tcontent = tarball.Content("", "", "", [], conf, "/")
        call_backup = build.util.call
        build.util.call = mock_util_call
        pkg = build.Build()
        fm = files.FileManager(conf, pkg)

        open_name = 'build.util.open_auto'
        content = 'line 1\n' \
                  'Installed (but unpackaged) file(s) found:\n' \
                  '/usr/testdir/file\n' \
                  '/usr/testdir/file1\n' \
                  '/usr/testdir/file2\n' \
                  'RPM build errors\n' \
                  'errors here\n'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            pkg.parse_build_results('testname', 0, fm, conf, reqs, tcontent)

        build.util.call = call_backup

        self.assertEqual(fm.files,
                         set(['/usr/testdir/file',
                              '/usr/testdir/file1',
                              '/usr/testdir/file2']))
        # one for each file added
        self.assertEqual(pkg.must_restart, 3)

    def test_parse_build_results_banned_files(self):
        """
        Test parse_build_results with a test log indicating banned files are missing
        """
        def mock_util_call(cmd):
            del cmd

        conf = config.Config('')
        conf.setup_patterns()
        reqs = buildreq.Requirements("")
        tcontent = tarball.Content("", "", "", [], conf, "/")
        call_backup = build.util.call
        build.util.call = mock_util_call
        pkg = build.Build()
        fm = files.FileManager(conf, pkg)

        open_name = 'build.util.open_auto'
        content = 'line 1\n' \
                  'Installed (but unpackaged) file(s) found:\n' \
                  '/opt/file\n' \
                  '/usr/etc/file\n' \
                  '/usr/local/file\n' \
                  '/usr/src/file\n' \
                  '/var/file\n' \
                  'RPM build errors\n' \
                  'errors here\n'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            pkg.parse_build_results('testname', 0, fm, conf, reqs, tcontent)

        build.util.call = call_backup

        self.assertEqual(fm.has_banned, True)
        # check no files were added
        self.assertEqual(pkg.must_restart, 0)

    def test_get_mock_cmd_without_consolehelper(self):
        """
        Test get_mock_cmd when /usr/bin/mock doesn't point to consolehelper
        """
        def mock_realpath(path):
            return path

        realpath_backup = build.os.path.realpath

        build.os.path.realpath = mock_realpath

        mock_cmd = build.get_mock_cmd()

        build.os.path.realpath = realpath_backup

        self.assertEqual(mock_cmd, 'sudo /usr/bin/mock')

    def test_get_mock_cmd_with_consolehelper(self):
        """
        Test get_mock_cmd when /usr/bin/mock points to consolehelper
        """
        def mock_realpath(path):
            return '/usr/bin/consolehelper'

        realpath_backup = build.os.path.realpath

        build.os.path.realpath = mock_realpath

        mock_cmd = build.get_mock_cmd()

        build.os.path.realpath = realpath_backup

        self.assertEqual(mock_cmd, '/usr/bin/mock')


if __name__ == '__main__':
    unittest.main(buffer=True)
