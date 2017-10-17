import unittest
import tempfile
import os
from unittest.mock import patch, mock_open
import build
import files


class TestBuildpattern(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        """
        Class setup method to configure necessary modules
        """
        build.config.setup_patterns()

    def setUp(self):
        """
        Test setup method to reset the buildpattern module
        """
        build.success = 0
        build.round = 0
        build.must_restart = 0
        build.base_path = None
        build.output_path = None
        build.download_path = None
        build.mock_cmd = '/usr/bin/mock'
        build.buildreq.buildreqs = set()
        build.config.config_opts['32bit'] = False

    def test_setup_workingdir(self):
        """
        Test that setup_workingdir sets the correct directory patterns
        """
        build.tarball.name = "testtarball"
        build.setup_workingdir("test_directory")
        self.assertEqual(build.base_path, "test_directory")
        self.assertEqual(build.output_path, "test_directory/output")
        self.assertEqual(build.download_path,
                         "test_directory/output/testtarball")

    def test_simple_pattern_pkgconfig(self):
        """
        Test simple_pattern_pkgconfig with match
        """
        build.buildreq.config.config_opts['32bit'] = False
        build.simple_pattern_pkgconfig('line to test for testpkg.xyz',
                                       r'testpkg.xyz',
                                       'testpkg')
        self.assertIn('pkgconfig(testpkg)', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_simple_pattern_pkgconfig_32bit(self):
        """
        Test simple_pattern_pkgconfig with match and 32bit option set
        """
        build.buildreq.config.config_opts['32bit'] = True
        build.simple_pattern_pkgconfig('line to test for testpkg.zyx',
                                       r'testpkg.zyx',
                                       'testpkgz')
        self.assertIn('pkgconfig(32testpkgz)', build.buildreq.buildreqs)
        self.assertIn('pkgconfig(testpkgz)', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_simple_pattern_pkgconfig_no_match(self):
        """
        Test simple_pattern_pkgconfig with no match, nothing should be modified
        """
        build.simple_pattern_pkgconfig('line to test for somepkg.xyz',
                                       r'testpkg.xyz',
                                       'testpkg')
        self.assertEqual(build.buildreq.buildreqs, set())
        self.assertEqual(build.must_restart, 0)

    def test_simple_pattern(self):
        """
        Test simple_pattern with match. The main difference between
        simple_pattern and simple_pattern_pkgconfig is the string that is added
        to buildreq.buildreqs.
        """
        build.simple_pattern('line to test for testpkg.xyz',
                             r'testpkg.xyz',
                             'testpkg')
        self.assertIn('testpkg', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_simple_pattern_no_match(self):
        """
        Test simple_pattern with no match, nothing should be modified
        """
        build.simple_pattern('line to test for somepkg.xyz',
                             r'testpkg.xyz',
                             'testpkg')
        self.assertEqual(build.buildreq.buildreqs, set())
        self.assertEqual(build.must_restart, 0)

    def test_failed_pattern_no_match(self):
        """
        Test failed_pattern with no match
        """
        build.failed_pattern('line to test for failure: somepkg', r'(test)', 0)
        self.assertEqual(build.buildreq.buildreqs, set())
        self.assertEqual(build.must_restart, 0)

    def test_failed_pattern_no_buildtool(self):
        """
        Test failed_pattern with buildtool unset and initial match, but no
        match in failed_commands.
        """
        build.failed_pattern('line to test for failure: testpkg', r'(test)', 0)
        self.assertEqual(build.buildreq.buildreqs, set())
        self.assertEqual(build.must_restart, 0)

    def test_failed_pattern_no_buildtool_match(self):
        """
        Test failed_pattern with buildtool unset and match in failed_commands
        """
        build.failed_pattern('line to test for failure: lex', r'(lex)', 0)
        self.assertIn('flex', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_pkgconfig(self):
        """
        Test failed_pattern with buildtool set to pkgconfig
        """
        build.buildreq.config.config_opts['32bit'] = False
        build.failed_pattern('line to test for failure: testpkg.xyz',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='pkgconfig')
        self.assertIn('pkgconfig(testpkg)', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_R(self):
        """
        Test failed_pattern with buildtool set to R
        """
        build.failed_pattern('line to test for failure: testpkg.r',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='R')
        self.assertIn('R-testpkg', build.buildreq.buildreqs)
        self.assertIn('R-testpkg', build.buildreq.requires)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_perl(self):
        """
        Test failed_pattern with buildtool set to perl
        """
        build.failed_pattern('line to test for failure: testpkg.pl',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='perl')
        self.assertIn('perl(testpkg)', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_pypi(self):
        """
        Test failed_pattern with buildtool set to pypi
        """
        build.failed_pattern('line to test for failure: testpkg.py',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='pypi')
        self.assertIn('testpkg-python', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_ruby(self):
        """
        Test failed_pattern with buildtool set to ruby, but no match in
        config.gems, it should just prepend 'rubygem-' to the package name.
        """
        build.failed_pattern('line to test for failure: testpkg.rb',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='ruby')
        self.assertIn('rubygem-testpkg', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_ruby_gem_match(self):
        """
        Test failed_pattern with buildtool set to ruby and a match in
        config.gems. In the particular case of test/unit, the result should
        be rubygem-test-unit.
        """
        build.failed_pattern('line to test for failure: test/unit',
                             r'(test/unit)',
                             0,  # verbose=0
                             buildtool='ruby')
        self.assertIn('rubygem-test-unit', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_ruby_table(self):
        """
        Test failed_pattern with buildtool set to ruby table and a match in
        config.gems
        """
        build.failed_pattern('line to test for failure: test/unit',
                             r'(test/unit)',
                             0,  # verbose=0
                             buildtool='ruby table')
        self.assertIn('rubygem-test-unit', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_ruby_table_no_match(self):
        """
        Test failed_pattern with buildtool set to ruby table but no match in
        config.gems. This should not modify anything.
        """
        build.failed_pattern('line to test for failure: testpkg',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='ruby table')
        self.assertEqual(build.buildreq.buildreqs, set())
        self.assertEqual(build.must_restart, 0)

    def test_failed_pattern_maven(self):
        """
        Test failed_pattern with buildtool set to maven, but no match in
        config.maven_jars, it should just prepend 'jdk-' to the package name.
        """
        build.failed_pattern('line to test for failure: testpkg',
                             r'(testpkg)',
                             0,  # verbose=0
                             buildtool='maven')
        self.assertIn('jdk-testpkg', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_failed_pattern_maven_match(self):
        """
        Test failed_pattern with buildtool set to maven with a match in
        config.maven_jars. In the particular case of apache, the corresponding
        maven jar is 'jdk-apache-parent'
        """
        build.failed_pattern('line to test for failure: apache',
                             r'(apache)',
                             0,  # verbose=0
                             buildtool='maven')
        self.assertIn('jdk-apache-parent', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_parse_build_resultsi_pkgconfig(self):
        """
        Test parse_build_results with a test log indicating failure due to a
        missing qmake package (pkgconfig error)
        """
        def mock_util_call(cmd):
            del cmd

        build.config.setup_patterns()
        build.config.config_opts['32bit'] = True
        call_backup = build.util.call
        build.util.call = mock_util_call
        fm = files.FileManager()

        open_name = 'build.open'
        content = 'line 1\nwhich: no qmake\nexiting'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            build.parse_build_results('testname', 0, fm)

        build.util.call = call_backup

        self.assertIn('pkgconfig(Qt)', build.buildreq.buildreqs)
        self.assertIn('pkgconfig(32Qt)', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_parse_build_results_simple_pats(self):
        """
        Test parse_build_results with a test log indicating failure due to a
        missing httpd-dev package (simple pat error)
        """
        def mock_util_call(cmd):
            del cmd

        build.config.setup_patterns()
        call_backup = build.util.call
        build.util.call = mock_util_call
        fm = files.FileManager()

        open_name = 'build.open'
        content = 'line 1\nchecking for Apache test module support\nexiting'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            build.parse_build_results('testname', 0, fm)

        build.util.call = call_backup

        self.assertIn('httpd-dev', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_parse_build_results_failed_pats(self):
        """
        Test parse_build_results with a test log indicating failure due to a
        missing testpkg (failed pat error). The specific error is a python
        ImportError.
        """
        def mock_util_call(cmd):
            del cmd

        build.config.setup_patterns()
        call_backup = build.util.call
        build.util.call = mock_util_call
        fm = files.FileManager()

        open_name = 'build.open'
        content = 'line 1\nImportError: No module named testpkg\nexiting'
        m_open = mock_open(read_data=content)

        with patch(open_name, m_open, create=True):
            build.parse_build_results('testname', 0, fm)

        build.util.call = call_backup

        self.assertIn('testpkg-python', build.buildreq.buildreqs)
        self.assertEqual(build.must_restart, 1)

    def test_set_mock_without_consolehelper(self):
        """
        Test set_mock when /usr/bin/mock doesn't point to consolehelper
        """
        def mock_realpath(path):
            return path

        realpath_backup = build.os.path.realpath

        build.os.path.realpath = mock_realpath

        build.set_mock()

        build.os.path.realpath = realpath_backup

        self.assertEqual(build.mock_cmd, 'sudo /usr/bin/mock')

    def test_set_mock_with_consolehelper(self):
        """
        Test set_mock when /usr/bin/mock points to consolehelper
        """
        def mock_realpath(path):
            return '/usr/bin/consolehelper'

        realpath_backup = build.os.path.realpath

        build.os.path.realpath = mock_realpath

        build.set_mock()

        build.os.path.realpath = realpath_backup

        self.assertEqual(build.mock_cmd, '/usr/bin/mock')

    def test_get_uniqueext_first(self):
        """
        Test get_uniqueext() with no collisions
        """
        with tempfile.TemporaryDirectory() as tmpd:
            self.assertEqual(build.get_uniqueext(tmpd, "test", "pkg"), "pkg")

    def test_get_uniqueext_second(self):
        """
        Test get_uniqueext() with one collision
        """
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, "test-pkg"))
            self.assertEqual(build.get_uniqueext(tmpd, "test", "pkg"), "pkg-1")

    def test_get_uniqueext_third(self):
        """
        Test get_uniqueext() with two collisions
        """
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, "test-pkg"))
            os.mkdir(os.path.join(tmpd, "test-pkg-1"))
            self.assertEqual(build.get_uniqueext(tmpd, "test", "pkg"), "pkg-2")



if __name__ == '__main__':
    unittest.main(buffer=True)
