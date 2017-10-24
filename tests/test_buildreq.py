import unittest
import tempfile
import os
from unittest.mock import mock_open, patch
from libautospec import buildreq


class TestBuildreq(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        """
        Class setup method to configure necessary modules
        """
        buildreq.banned_buildreqs.add('bannedreq')
        buildreq.config.setup_patterns()

    def setUp(self):
        """
        Test setup method to reset the buildreq module
        """
        buildreq.banned_requires = set()
        buildreq.buildreqs = set()
        buildreq.requires = set()
        buildreq.verbose = False
        buildreq.cargo_bin = False
        buildreq.config.config_opts['32bit'] = False
        buildreq.config.os_packages = set()
        buildreq.buildpattern.pattern_strength = 0

    def test_add_buildreq(self):
        """
        Test add_buildreq with unbanned new req. Follow up by asserting that
        trying to add the same req a second time results in a False return.
        """
        self.assertTrue(buildreq.add_buildreq('testreq'))
        self.assertIn('testreq', buildreq.buildreqs)
        self.assertFalse(buildreq.add_buildreq('testreq'))

    def test_add_buildreq_banned(self):
        """
        Test add_buildreq with banned new req
        """
        self.assertFalse(buildreq.add_buildreq('bannedreq'))
        self.assertNotIn('bannedreq', buildreq.buildreqs)

    def test_add_requires(self):
        """
        Test add_requires with unbanned new req already present in
        buildreqs but not yet present in requires
        """
        buildreq.add_buildreq('testreq')
        self.assertTrue(buildreq.add_requires('testreq'))
        self.assertIn('testreq', buildreq.requires)

    def test_add_requires_not_in_buildreqs(self):
        """
        Test add_requires with unbanned new req not present in buildreqs.
        """
        self.assertFalse(buildreq.add_requires('testreq'))
        self.assertNotIn('testreq', buildreq.requires)

    def test_add_pkgconfig_buildreq(self):
        """
        Test add_pkgconfig_buildreq with config_opts['32bit'] set to False
        """
        self.assertTrue(buildreq.add_pkgconfig_buildreq('testreq'))
        self.assertIn('pkgconfig(testreq)', buildreq.buildreqs)

    def test_add_pkgconfig_buildreq_32bit(self):
        """
        Test add_pkgconfig_buildreq with config_opts['32bit'] set to True
        """
        buildreq.config.config_opts['32bit'] = True
        self.assertTrue(buildreq.add_pkgconfig_buildreq('testreq'))
        self.assertIn('pkgconfig(testreq)', buildreq.buildreqs)
        self.assertIn('pkgconfig(32testreq)', buildreq.buildreqs)

    def test_configure_ac_line(self):
        """
        Test configure_ac_line with standard pattern
        """
        buildreq.configure_ac_line('AC_CHECK_FUNC\([tgetent])')
        self.assertIn('ncurses-devel', buildreq.buildreqs)

    def test_configure_ac_line_comment(self):
        """
        Test configure_ac_line with commented line
        """
        buildreq.configure_ac_line('# AC_CHECK_FUNC\([tgetent])')
        self.assertEqual(buildreq.buildreqs, set())

    def test_configure_ac_line_pkg_check_modules(self):
        """
        Test the somewhat complicated logic of configure_ac_line check for the
        PKG_CHECK_MODULES\((.*?)\) line.
        """
        buildreq.configure_ac_line(
            'PKG_CHECK_MODULES(prefix, '
            '[module > 2 module2 < 2], '
            'action-if-found, action-if-not-found)')
        self.assertEqual(buildreq.buildreqs,
                         set(['pkgconfig(module)', 'pkgconfig(module2)']))

    def test_configure_ac_line_xdt_check_package(self):
        """
        Test configure_ac_line for the XFCE version of PKG_CHECK_MODULES
        """
        buildreq.configure_ac_line(
            'XDT_CHECK_PACKAGE(prefix, '
            '[module = 2 module2 > 9], '
            'action-if-found, action-if-not-found)')
        self.assertEqual(buildreq.buildreqs,
                         set(['pkgconfig(module)', 'pkgconfig(module2)']))

    def test_configure_ac_line_pkg_check_exists(self):
        """
        Test configure_ac_line for the PKG_CHECK_EXISTS macro
        """
        buildreq.configure_ac_line('PKG_CHECK_EXISTS([module1 > 1 module2], '
                                   'action-if-found, '
                                   'action-if-not-found)')
        self.assertEqual(buildreq.buildreqs,
                         set(['pkgconfig(module1)', 'pkgconfig(module2)']))

    def test_parse_configure_ac(self):
        """
        Test parse_configure_ac with changing () depths and package
        requirements
        """
        open_name = 'libautospec.buildreq.open'
        content = 'AC_CHECK_FUNC([tgetent])\n'                   \
                  'XDT_CHECK_PACKAGE(prefix, '                   \
                  '[module = 2 module2 > 9], '                   \
                  'action-if-found, action-if-not-found)\n'      \
                  'next two lines should be read in batch ( \n'  \
                  'PROG_INTLTOOL\n'                              \
                  'AC_PROG_SED)\n'                               \
                  'GETTEXT_PACKAGE'
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'fname'), 'w') as f:
                f.write(content)
            buildreq.parse_configure_ac(os.path.join(tmpd, 'fname'))

        self.assertEqual(buildreq.buildpattern.default_pattern, 'configure_ac')
        self.assertEqual(buildreq.buildreqs,
                         set(['gettext',
                              'perl(XML::Parser)',
                              'pkgconfig(module2)',
                              'pkgconfig(module)',
                              'intltool',
                              'sed']))

    def test_parse_cargo_toml(self):
        """
        Test parse_cargo_toml
        """
        def mock_loads(loadstr):
            return {'dependencies': ['dep1', 'dep2', 'dep3'], 'bin': True}

        def mock_exists(path):
            return True

        exists_backup = buildreq.os.path.exists
        loads_backup = buildreq.toml.loads

        buildreq.os.path.exists = mock_exists
        buildreq.toml.loads = mock_loads

        open_name = 'libautospec.buildreq.open'
        content = 'does not matter, let us mock'
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.parse_cargo_toml('filename')

        buildreq.os.path.exists = exists_backup
        buildreq.toml.loads = loads_backup

        self.assertEqual(buildreq.buildreqs,
                         set(['rustc', 'dep1', 'dep2', 'dep3']))
        self.assertTrue(buildreq.cargo_bin)
        self.assertEqual(buildreq.buildpattern.default_pattern, 'cargo')

    def test_set_build_req_maven(self):
        """
        Test set_build_req with buildpattern.default_pattern set to maven.
        This is just a simple test for the inclusion of a single package, in
        case the overall package list changes in the future.
        """
        buildreq.buildpattern.default_pattern = 'maven'
        buildreq.set_build_req()
        self.assertIn('apache-maven', buildreq.buildreqs)

    def test_set_build_req_ruby(self):
        """
        Test set_build_req with buildpattern.default_pattern set to ruby.
        This is just a simple test for the inclusion of a single package, in
        case the overall package list changes in the future.
        """
        buildreq.buildpattern.default_pattern = 'ruby'
        buildreq.set_build_req()
        self.assertIn('ruby', buildreq.buildreqs)

    def test_set_build_req_cargo(self):
        """
        Test set_build_req with buildpattern.default_pattern set to cargo.
        This is just a simple test for the inclusion of a single package, in
        case the overall package list changes in the future.
        """
        buildreq.buildpattern.default_pattern = 'cargo'
        buildreq.set_build_req()
        self.assertIn('rustc', buildreq.buildreqs)

    def test_rakefile(self):
        """
        Test rakefile parsing with both configured gems and unconfigured gems
        """
        open_name = 'libautospec.buildreq.open'
        content = "line1\nrequire 'bundler/gem_tasks'\nline3\nrequire 'nope'"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.rakefile('filename')

        self.assertEqual(buildreq.buildreqs, set(['rubygem-rubygems-tasks']))

    def test_clean_python_req(self):
        """
        Test clean_python_req with a common python requirements string
        """
        self.assertEqual(buildreq.clean_python_req('requirement >= 1.1.2'),
                         'requirement')

    def test_clean_python_req_comment(self):
        """
        Test clean_python_req with a comment
        """
        self.assertEqual(buildreq.clean_python_req('# hello'), '')

    def test_clean_python_req_whitespace(self):
        """
        Test clean_python_req with strange whitespaced string
        """
        self.assertEqual(buildreq.clean_python_req('   requirement    < 1.1'),
                         'requirement')

    def test_grab_python_requirements(self):
        """
        Test grab_python_requirements with a reasonable requirements file
        """
        # buildreqs must include the requires also
        buildreq.buildreqs = set(['req1', 'req2', 'req7'])
        open_name = 'libautospec.buildreq.open'
        content = 'req1 <= 1.2.3\n' \
                  'req2 >= 1.55\n'  \
                  'req7 == 3.3.3\n'
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.grab_python_requirements('filename')

        self.assertEqual(buildreq.requires, set(['req1', 'req2', 'req7']))

    def test_grab_python_requirements_strange_file(self):
        """
        Test grab_python_requirements with a poorly written file
        """
        # buildreqs must include the requires also
        buildreq.buildreqs = set(['req1', 'req2', 'req7'])
        open_name = 'libautospec.buildreq.open'
        content = '    req1 <= 1.2.3\n   ' \
                  'req2    >= 1.55   \n'   \
                  '   req7 == 3.3.3\n    '
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.grab_python_requirements('filename')

        self.assertEqual(buildreq.requires, set(['req1', 'req2', 'req7']))

    def test_add_setup_py_requires(self):
        """
        Test add_setup_py_requires with a single item in install_requires and
        setup_requires
        """
        open_name = 'libautospec.buildreq.open'
        content = "install_requires=['req1']\n" \
                  "setup_requires=['req2']"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.add_setup_py_requires('filename')

        self.assertEqual(buildreq.buildreqs, set(['req1', 'req2']))
        self.assertEqual(buildreq.requires, set(['req1']))

    def test_add_setup_py_requires_multiline(self):
        """
        Test add_setup_py_requires with a multiline item in install_requires
        """
        open_name = 'libautospec.buildreq.open'
        content = "install_requires=['req1',\n" \
                  "'req2',\n"                   \
                  "'req3']\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.add_setup_py_requires('filename')

        self.assertEqual(buildreq.buildreqs, set(['req1', 'req2', 'req3']))
        self.assertEqual(buildreq.requires, set(['req1', 'req2', 'req3']))

    def test_add_setup_py_requires_multiline_formatted(self):
        """
        Test add_setup_py_requires with a multiline item in install_requires
        with brackets on their own lines.
        """
        open_name = 'libautospec.buildreq.open'
        content = "install_requires=[\n "  \
                  "'req1',\n"              \
                  "'req2',\n"              \
                  "'req3',\n"              \
                  "]\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.add_setup_py_requires('filename')

        self.assertEqual(buildreq.buildreqs, set(['req1', 'req2', 'req3']))
        self.assertEqual(buildreq.requires, set(['req1', 'req2', 'req3']))

    def test_add_setup_py_requires_multiline_variable(self):
        """
        Test add_setup_py_requires with multiline item in install_requires that
        contains a non-literal object.
        """
        open_name = 'libautospec.buildreq.open'
        content = "install_requires=[\n" \
                  "reqvar,\n"            \
                  "'req1',\n"            \
                  "'req2'"               \
                  "]\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.add_setup_py_requires('filename')

        self.assertEqual(buildreq.buildreqs, set(['req1', 'req2']))
        self.assertEqual(buildreq.requires, set(['req1', 'req2']))

    def test_add_setup_py_requires_variable(self):
        """
        Test add_setup_py_requires that contains a non-literal object.
        """
        open_name = 'libautospec.buildreq.open'
        content = "install_requires=[reqname, 'req1', 'req2']\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.add_setup_py_requires('filename')

        self.assertEqual(buildreq.buildreqs, set(['req1', 'req2']))
        self.assertEqual(buildreq.requires, set(['req1', 'req2']))

    def test_add_setup_py_requires_single_variable(self):
        """
        Test add_setup_py_requires with a single non-literal object
        """
        open_name = 'libautospec.buildreq.open'
        content = "install_requires=reqname"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            buildreq.add_setup_py_requires('filename')

        self.assertEqual(buildreq.buildreqs, set())
        self.assertEqual(buildreq.requires, set())

    def test_scan_for_configure(self):
        """
        Test scan_for_configure with a mocked package structure. There is so
        much to test here that uses the same logic, a representative test
        should be sufficient.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, 'subdir'))
            open(os.path.join(tmpd, 'subdir', 'test.go'), 'w').close()
            open(os.path.join(tmpd, 'CMakeLists.txt'), 'w').close()
            open(os.path.join(tmpd, 'SConstruct'), 'w').close()

            buildreq.scan_for_configure(tmpd)

        self.assertEqual(buildreq.buildreqs,
                         set(['go', 'cmake', 'scons', 'python-dev']))


if __name__ == '__main__':
    unittest.main(buffer=True)
