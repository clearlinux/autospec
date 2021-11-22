import unittest
import tempfile
import os
from unittest.mock import MagicMock, mock_open, patch
import json
import io
import buildreq
import config
import pypidata

bak_get_pypi_name = pypidata.get_pypi_name
def get_pypi_name_wrapper(name, miss=None):
    """Ignore missing packags in pypi"""
    return bak_get_pypi_name(name)


class TestBuildreq(unittest.TestCase):

    def setUp(self):
        """
        Test setup method to reset the buildreq module
        """
        self.reqs = buildreq.Requirements("")
        self.reqs.banned_buildreqs.add('bannedreq')

    def test_add_buildreq(self):
        """
        Test add_buildreq with unbanned new req. Follow up by asserting that
        trying to add the same req a second time results in a False return.
        """
        self.assertTrue(self.reqs.add_buildreq('testreq'))
        self.assertIn('testreq', self.reqs.buildreqs)
        self.assertFalse(self.reqs.add_buildreq('testreq'))

    def test_add_buildreq_banned(self):
        """
        Test add_buildreq with banned new req
        """
        self.assertFalse(self.reqs.add_buildreq('bannedreq'))
        self.assertNotIn('bannedreq', self.reqs.buildreqs)

    def test_ban_requires(self):
        """
        Test ban_requires with req already present in requires
        """
        self.reqs.requires[None] = set(['testreq'])
        self.reqs.ban_requires('testreq')
        self.assertNotIn('testreq', self.reqs.requires[None])

    def test_ban_requires_subpkg(self):
        """
        Test ban_requires on a subpkg with req already present in requires
        """
        self.reqs.requires['subpkg'] = set(['testreq'])
        self.reqs.ban_requires('testreq', subpkg='subpkg')
        self.assertNotIn('testreq', self.reqs.requires['subpkg'])

    def test_add_requires(self):
        """
        Test add_requires with unbanned new req already present in
        buildreqs but not yet present in requires
        """
        self.reqs.add_buildreq('testreq')
        self.assertTrue(self.reqs.add_requires('testreq', ['testreq']))
        self.assertIn('testreq', self.reqs.requires[None])

    def test_add_requires_subpkg(self):
        """
        Test add_requires on a subpkg with unbanned new req already present in
        buildreqs but not yet present in requires
        """
        self.reqs.add_buildreq('testreq')
        self.assertTrue(self.reqs.add_requires('testreq', ['testreq'], subpkg='subpkg'))
        self.assertIn('testreq', self.reqs.requires['subpkg'])

    def test_add_requires_not_in_buildreqs(self):
        """
        Test add_requires with unbanned new req not present in buildreqs.
        """
        self.assertFalse(self.reqs.add_requires('testreq', []))
        self.assertNotIn('testreq', self.reqs.requires[None])

    def test_add_pkgconfig_buildreq(self):
        """
        Test add_pkgconfig_buildreq with config_opts['32bit'] set to False
        """
        self.assertTrue(self.reqs.add_pkgconfig_buildreq('testreq', False))
        self.assertIn('pkgconfig(testreq)', self.reqs.buildreqs)

    def test_add_pkgconfig_buildreq_32bit(self):
        """
        Test add_pkgconfig_buildreq with config_opts['32bit'] set to True
        """
        self.assertTrue(self.reqs.add_pkgconfig_buildreq('testreq', True))
        self.assertIn('pkgconfig(testreq)', self.reqs.buildreqs)
        self.assertIn('pkgconfig(32testreq)', self.reqs.buildreqs)

    def test_configure_ac_line(self):
        """
        Test configure_ac_line with standard pattern
        """
        self.reqs.configure_ac_line('AC_CHECK_FUNC\([tgetent])', False)
        self.assertIn('ncurses-devel', self.reqs.buildreqs)

    def test_configure_ac_line_comment(self):
        """
        Test configure_ac_line with commented line
        """
        self.reqs.configure_ac_line('# AC_CHECK_FUNC\([tgetent])', False)
        self.assertEqual(self.reqs.buildreqs, set())

    def test_configure_ac_line_pkg_check_modules(self):
        """
        Test the somewhat complicated logic of configure_ac_line check for the
        PKG_CHECK_MODULES\((.*?)\) line.
        """
        self.reqs.configure_ac_line(
            'PKG_CHECK_MODULES(prefix, '
            '[module > 2 module2 < 2], '
            'action-if-found, action-if-not-found)', False)
        self.assertEqual(self.reqs.buildreqs,
                         set(['pkgconfig(module)', 'pkgconfig(module2)']))

    def test_configure_ac_line_xdt_check_package(self):
        """
        Test configure_ac_line for the XFCE version of PKG_CHECK_MODULES
        """
        self.reqs.configure_ac_line(
            'XDT_CHECK_PACKAGE(prefix, '
            '[module = 2 module2 > 9], '
            'action-if-found, action-if-not-found)', False)
        self.assertEqual(self.reqs.buildreqs,
                         set(['pkgconfig(module)', 'pkgconfig(module2)']))

    def test_configure_ac_line_pkg_check_exists(self):
        """
        Test configure_ac_line for the PKG_CHECK_EXISTS macro
        """
        self.reqs.configure_ac_line('PKG_CHECK_EXISTS([module1 > 1 module2], '
                                   'action-if-found, '
                                   'action-if-not-found)', False)
        self.assertEqual(self.reqs.buildreqs,
                         set(['pkgconfig(module1)', 'pkgconfig(module2)']))

    def test_parse_configure_ac(self):
        """
        Test parse_configure_ac with changing () depths and package
        requirements
        """
        conf = config.Config("")
        open_name = 'buildreq.util.open_auto'
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
            self.reqs.parse_configure_ac(os.path.join(tmpd, 'fname'), conf)

        self.assertEqual(conf.default_pattern, 'configure_ac')
        self.assertEqual(self.reqs.buildreqs,
                         set(['gettext',
                              'perl(XML::Parser)',
                              'pkgconfig(module2)',
                              'pkgconfig(module)',
                              'intltool',
                              'sed']))

    def test_parse_go_mod(self):
        """
        Test parse_go_mod
        """
        open_name = 'buildreq.open'
        content = """module example.com/foo/bar

        require (
        github.com/example/foo v1.0.0
        git.apache.org/skip.git v0.0.0-20180101111111-barf0000000d
        github.com/redirect/bar v2.0.0 // indirect
        "github.com/quote/baz" v0.0.3
        "github.com/qdirect/raz" v1.0.3 // indirect
        )"""
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            result = buildreq.parse_go_mod('filename')
        self.assertEqual(len(result), 4)
        self.assertEqual(len(result[0]), 2)
        self.assertEqual(result[0][0], "github.com/example/foo")
        self.assertEqual(result[0][1], "v1.0.0")
        self.assertEqual(len(result[1]), 2)
        self.assertEqual(result[1][0], "github.com/redirect/bar")
        self.assertEqual(result[1][1], "v2.0.0")
        self.assertEqual(len(result[2]), 2)
        self.assertEqual(result[2][0], "github.com/quote/baz")
        self.assertEqual(result[2][1], "v0.0.3")
        self.assertEqual(len(result[3]), 2)
        self.assertEqual(result[3][0], "github.com/qdirect/raz")
        self.assertEqual(result[3][1], "v1.0.3")

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

        open_name = 'buildreq.util.open_auto'
        content = 'does not matter, let us mock'
        m_open = mock_open(read_data=content)
        conf = config.Config("")
        with patch(open_name, m_open, create=True):
            self.reqs.parse_cargo_toml('filename', conf)

        buildreq.os.path.exists = exists_backup
        buildreq.toml.loads = loads_backup

        self.assertEqual(self.reqs.buildreqs,
                         set(['rustc', 'dep1', 'dep2', 'dep3']))
        self.assertTrue(self.reqs.cargo_bin)
        self.assertEqual(conf.default_pattern, 'cargo')

    def test_set_build_req_maven(self):
        """
        Test set_build_req with default_pattern set to maven.
        This is just a simple test for the inclusion of a single package, in
        case the overall package list changes in the future.
        """
        conf = config.Config("")
        conf.default_pattern = "maven"
        self.reqs.set_build_req(conf)
        self.assertIn('apache-maven', self.reqs.buildreqs)

    def test_set_build_req_ruby(self):
        """
        Test set_build_req with default_pattern set to ruby.
        This is just a simple test for the inclusion of a single package, in
        case the overall package list changes in the future.
        """
        conf = config.Config("")
        conf.default_pattern = "ruby"
        self.reqs.set_build_req(conf)
        self.assertIn('ruby', self.reqs.buildreqs)

    def test_set_build_req_cargo(self):
        """
        Test set_build_req with default_pattern set to cargo.
        This is just a simple test for the inclusion of a single package, in
        case the overall package list changes in the future.
        """
        conf = config.Config("")
        conf.default_pattern = "cargo"
        self.reqs.set_build_req(conf)
        self.assertIn('rustc', self.reqs.buildreqs)

    def test_rakefile(self):
        """
        Test rakefile parsing with both configured gems and unconfigured gems
        """
        conf = config.Config("")
        conf.setup_patterns()
        open_name = 'buildreq.util.open_auto'
        content = "line1\nrequire 'bundler/gem_tasks'\nline3\nrequire 'nope'"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.rakefile('filename', conf.gems)

        self.assertEqual(self.reqs.buildreqs, set(['rubygem-rubygems-tasks']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_clean_python_req(self):
        """
        Test clean_python_req with a common python requirements string
        """
        self.assertEqual(buildreq.clean_python_req('requirement >= 1.1.2'),
                         'requirement')
        self.assertEqual(buildreq.clean_python_req('requirement ; python_version > 1.1.2'),
                         'requirement')
        self.assertEqual(buildreq.clean_python_req('requirement <= 1.1.2'),
                         'requirement')
        self.assertEqual(buildreq.clean_python_req('requirement = 1.1.2'),
                         'requirement')
        self.assertEqual(buildreq.clean_python_req('requirement \n ; rsa>= 1.1.2'),
                         'requirement')
        self.assertEqual(buildreq.clean_python_req('requirement != 1.1.2'),
                         'requirement')
        self.assertEqual(buildreq.clean_python_req('[:python > 2]'),
                         '')
        self.assertEqual(buildreq.clean_python_req('requirement ~= 1.1.2'),
                         'requirement')

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_clean_python_req_comment(self):
        """
        Test clean_python_req with a comment
        """
        self.assertEqual(buildreq.clean_python_req('# hello'), '')

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_clean_python_req_whitespace(self):
        """
        Test clean_python_req with strange whitespaced string
        """
        self.assertEqual(buildreq.clean_python_req('   requirement    < 1.1'),
                        'requirement')

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_grab_python_requirements(self):
        """
        Test grab_python_requirements with a reasonable requirements file
        """
        # buildreqs must include the requires also
        open_name = 'buildreq.util.open_auto'
        content = 'req1 <= 1.2.3\n' \
                  'req2 >= 1.55\n'  \
                  'req7 == 3.3.3\n'
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.grab_python_requirements('filename', [])

        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)', 'pypi(req7)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_grab_python_requirements_strange_file(self):
        """
        Test grab_python_requirements with a poorly written file
        """
        # buildreqs must include the requires also
        open_name = 'buildreq.util.open_auto'
        content = '    req1 <= 1.2.3\n   ' \
                  'req2    >= 1.55   \n'   \
                  '   req7 == 3.3.3\n    '
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.grab_python_requirements('filename', [])

        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)', 'pypi(req7)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires(self):
        """
        Test add_setup_py_requires with a single item in install_requires and
        setup_requires
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=['req1']\n" \
                  "setup_requires=['req2']"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set(['pypi(req1)', 'pypi(req2)']))
        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires_multiline(self):
        """
        Test add_setup_py_requires with a multiline item in install_requires
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=['req1',\n" \
                  "'req2',\n"                   \
                  "'req7']\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set(['pypi(req1)', 'pypi(req2)', 'pypi(req7)']))
        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)', 'pypi(req7)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires_multiline_formatted(self):
        """
        Test add_setup_py_requires with a multiline item in install_requires
        with brackets on their own lines.
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=[\n "  \
                  "'req1',\n"              \
                  "'req2',\n"              \
                  "'req7',\n"              \
                  "]\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set(['pypi(req1)', 'pypi(req2)', 'pypi(req7)']))
        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)', 'pypi(req7)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires_multiline_variable(self):
        """
        Test add_setup_py_requires with multiline item in install_requires that
        contains a non-literal object.
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=[\n" \
                  "reqvar,\n"            \
                  "'req1',\n"            \
                  "'req2'"               \
                  "]\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set(['pypi(req1)', 'pypi(req2)']))
        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires_multiline_install_requires_variable(self):
        """
        Test add_setup_py_requires with multiline item in install_requires that
        contains an extra bit of content that shouldn't be parsed as install_requires.
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=[\n"   \
                  "'req1',\n"              \
                  "'req2'"                 \
                  "] + install_requires\n" \
                  "'bad']\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set(['pypi(req1)', 'pypi(req2)']))
        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires_variable(self):
        """
        Test add_setup_py_requires that contains a non-literal object.
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=[reqname, 'req1', 'req2']\n"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set(['pypi(req1)', 'pypi(req2)']))
        self.assertEqual(self.reqs.requires["python3"], set(['pypi(req1)', 'pypi(req2)']))

    @patch('buildreq.pypidata.get_pypi_name', get_pypi_name_wrapper)
    def test_add_setup_py_requires_single_variable(self):
        """
        Test add_setup_py_requires with a single non-literal object
        """
        open_name = 'buildreq.util.open_auto'
        content = "install_requires=reqname"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            self.reqs.add_setup_py_requires('filename', [])

        self.assertEqual(self.reqs.buildreqs, set())
        self.assertEqual(self.reqs.requires[None], set())

    def test_scan_for_configure(self):
        """
        Test scan_for_configure with a mocked package structure. There is so
        much to test here that uses the same logic, a representative test
        should be sufficient.
        """
        conf = config.Config("")
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, 'subdir'))
            open(os.path.join(tmpd, 'subdir', 'test.go'), 'w').close()
            open(os.path.join(tmpd, 'setup.py'), 'w').close()
            open(os.path.join(tmpd, 'CMakeLists.txt'), 'w').close()
            open(os.path.join(tmpd, 'SConstruct'), 'w').close()
            open(os.path.join(tmpd, 'meson.build'), 'w').close()

            self.reqs.scan_for_configure(tmpd, "", conf)

        self.assertEqual(self.reqs.buildreqs,
                         set(['buildreq-golang', 'buildreq-cmake', 'buildreq-scons', 'buildreq-distutils3', 'buildreq-meson']))

    def test_scan_for_configure_pypi(self):
        """
        Test scan_for_configure when distutils is being used for the build
        pattern to test pypi metadata handling.
        """
        orig_summary = buildreq.specdescription.default_summary
        orig_sscore = buildreq.specdescription.default_summary_score
        orig_pypi_name = buildreq.pypidata.get_pypi_name
        orig_pypi_meta = buildreq.pypidata.get_pypi_metadata
        name = "name"
        requires = ["abc",
                    "def"]
        pypi_requires = set(f"pypi({x})" for x in requires)
        summary = "summary"
        content = json.dumps({"name": name,
                              "summary": summary,
                              "requires": requires})
        buildreq.pypidata.get_pypi_name = MagicMock(return_value=True)
        buildreq.pypidata.get_pypi_metadata = MagicMock(return_value=content)
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            os.mkdir(os.path.join(tmpd, 'subdir'))
            open(os.path.join(tmpd, 'subdir', 'setup.py'), 'w').close()
            self.reqs.scan_for_configure(os.path.join(tmpd, 'subdir'), "", conf)

        ssummary = buildreq.specdescription.default_summary
        buildreq.specdescription.default_summary = orig_summary
        buildreq.specdescription.default_summary_score = orig_sscore
        buildreq.pypidata.get_pypi_name = orig_pypi_name
        buildreq.pypidata.get_pypi_metadata = orig_pypi_meta

        self.assertEqual(self.reqs.pypi_provides, name)
        self.assertEqual(self.reqs.requires['python3'], pypi_requires)
        self.assertEqual(ssummary, summary)

    def test_scan_for_configure_pypi_override(self):
        """
        Test scan_for_configure when distutils is being used for the build
        pattern to test pypi metadata file override handling.
        """
        open_name = 'buildreq.open'
        orig_summary = buildreq.specdescription.default_summary
        orig_sscore = buildreq.specdescription.default_summary_score
        name = "name"
        summary = "summary"
        requires = ["req"]
        pypi_requires = set(f"pypi({x})" for x in requires)
        content = json.dumps({"name": name,
                              "summary": summary,
                              "requires": requires})
        m_open = mock_open(read_data=content)
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            os.mkdir(os.path.join(tmpd, 'subdir'))
            open(os.path.join(tmpd, 'subdir', 'setup.py'), 'w').close()
            open(os.path.join(tmpd, 'pypi.json'), 'w').close()
            with patch(open_name, m_open, create=True):
                self.reqs.scan_for_configure(os.path.join(tmpd, 'subdir'), "", conf)

        ssummary = buildreq.specdescription.default_summary
        buildreq.specdescription.default_summary = orig_summary
        buildreq.specdescription.default_summary_score = orig_sscore

        self.assertEqual(self.reqs.pypi_provides, name)
        self.assertEqual(self.reqs.requires['python3'], pypi_requires)
        self.assertEqual(ssummary, summary)

    def test_parse_cmake_pkg_check_modules(self):
        """
        Test parse_cmake to ensure accurate detection of versioned and
        unversioned pkgconfig modules.
        """
        conf = config.Config("")
        conf.setup_patterns()
        content = 'pkg_check_modules(GLIB gio-unix-2.0>=2.46.0 glib-2.0 REQUIRED)'
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'fname'), 'w') as f:
                f.write(content)
            self.reqs.parse_cmake(os.path.join(tmpd, 'fname'), conf.cmake_modules, False)

        self.assertEqual(self.reqs.buildreqs,
                         set(['pkgconfig(gio-unix-2.0)', 'pkgconfig(glib-2.0)']))

    def test_parse_cmake_pkg_check_modules_whitespace(self):
        """
        Test parse_cmake to ensure accurate handling of versioned
        pkgconfig modules with whitespace.
        """
        conf = config.Config("")
        conf.setup_patterns()
        content = 'pkg_check_modules(GLIB gio-unix-2.0 >= 2.46.0 glib-2.0 REQUIRED)'
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'fname'), 'w') as f:
                f.write(content)
            self.reqs.parse_cmake(os.path.join(tmpd, 'fname'), conf.cmake_modules, False)

        self.assertEqual(self.reqs.buildreqs,
                         set(['pkgconfig(gio-unix-2.0)', 'pkgconfig(glib-2.0)']))

    def test_parse_cmake_pkg_check_modules_in_a_comment(self):
        """
        Test parse_cmake to ensure it ignores pkg_check_modules in comments.
        """
        conf = config.Config("")
        conf.setup_patterns()
        content = '''
# For example, consider the following patch to some CMakeLists.txt.
#     - pkg_check_modules(FOO REQUIRED foo>=1.0)
#     + pkg_check_modules(FOO REQUIRED foo>=2.0)
'''
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'fname'), 'w') as f:
                f.write(content)
            self.reqs.parse_cmake(os.path.join(tmpd, 'fname'), conf.cmake_modules, False)

        self.assertEqual(self.reqs.buildreqs,
                         set([]))

    def test_parse_cmake_pkg_check_modules_variables(self):
        """
        Test parse_cmake to ensure accurate handling of versioned
        pkgconfig modules with variable version strings.
        """
        conf = config.Config("")
        conf.setup_patterns()
        content = 'pkg_check_modules(AVCODEC libavcodec${_avcodec_ver} libavutil$_avutil_ver)'
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'fname'), 'w') as f:
                f.write(content)
            self.reqs.parse_cmake(os.path.join(tmpd, 'fname'), conf.cmake_modules, False)

        self.assertEqual(self.reqs.buildreqs,
                         set(['pkgconfig(libavcodec)', 'pkgconfig(libavutil)']))

    def test_parse_cmake_find_package(self):
        """
        Test parse_cmake to ensure accurate handling of find_package.
        """
        cmake_modules = {
            "valid": "valid",
            "valid_but_commented": "valid_but_commented",
            "different_name": "another_name",
        }
        content = '''
find_package(valid)
#find_package(foo)
  # find_package(valid_but_commented)
find_package(different_name)
'''
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'fname'), 'w') as f:
                f.write(content)
            self.reqs.parse_cmake(os.path.join(tmpd, 'fname'), cmake_modules, False)

        self.assertEqual(self.reqs.buildreqs,
                         set(['valid', 'another_name']))

    def test_r_desc_field_begin(self):
        """Test parsing of the first R description field."""
        lines = [
            "Field1: foo",
            "Field2: bar",
            "Field3: baz",
        ]
        result = buildreq._get_desc_field("Field1", "\n".join(lines))
        self.assertEqual(result, ["foo"])

    def test_r_desc_field_middle(self):
        """Test parsing of an R description field with surrounding fields."""
        lines = [
            "Field1: foo",
            "Field2: bar",
            "Field3: baz",
        ]
        result = buildreq._get_desc_field("Field2", "\n".join(lines))
        self.assertEqual(result, ["bar"])

    def test_r_desc_field_end(self):
        """Test parsing of the last R description field."""
        lines = [
            "Field1: foo",
            "Field2: bar",
            "Field3: baz",
        ]
        result = buildreq._get_desc_field("Field3", "\n".join(lines))
        self.assertEqual(result, ["baz"])

    def test_r_desc_field_middle_multiple_lines(self):
        """Test parsing of a multi-line R description field, with surrounding fields."""
        lines = [
            "Field1: foo",
            "Field2: bar1, bar2,",
            "  bar3, bar4",
            "Field3: baz",
        ]
        result = buildreq._get_desc_field("Field2", "\n".join(lines))
        self.assertEqual(result, ["bar1", "bar2", "bar3", "bar4"])

    def test_r_desc_field_end_multiple_lines(self):
        """Test parsing of the last R description field, consisting of multiple lines."""
        lines = [
            "Field1: foo",
            "Field2: bar",
            "Field3: baz1,",
            "        baz2",
        ]
        result = buildreq._get_desc_field("Field3", "\n".join(lines))
        self.assertEqual(result, ["baz1", "baz2"])

    def test_r_desc_field_middle_one_per_line(self):
        """Test parsing of an R description field with one entry per line."""
        lines = [
            "Field1: foo",
            "Field2:",
            "bar1,",
            "bar2",
            "Field3: baz",
        ]
        result = buildreq._get_desc_field("Field2", "\n".join(lines))
        self.assertEqual(result, ["bar1", "bar2"])

    def test_r_desc_field_trailing_whitespace(self):
        """Test parsing of an R description field with trailing whitespace."""
        lines = [
            "Field1: foo1, foo2    ",
        ]
        result = buildreq._get_desc_field("Field1", "\n".join(lines))
        self.assertEqual(result, ["foo1", "foo2"])

    def test_r_desc_field_trailing_comma(self):
        """Test parsing of an R description field with trailing comma."""
        lines = [
            "Field1: foo1, foo2,",
        ]
        result = buildreq._get_desc_field("Field1", "\n".join(lines))
        self.assertEqual(result, ["foo1", "foo2"])

    def test_r_desc_field_empty(self):
        """Test parsing of an R description field with an empty value."""
        lines = [
            "Field1:",
        ]
        result = buildreq._get_desc_field("Field1", "\n".join(lines))
        self.assertEqual(result, [])

    def test_r_desc_field_missing(self):
        """Test parsing of an R description field that is missing."""
        lines = [
            "Field1: foo, bar",
        ]
        result = buildreq._get_desc_field("Field2", "\n".join(lines))
        self.assertEqual(result, [])

    def test_parse_r_desc_depends(self):
        """Test parsing of R description Depends field."""
        pkgs = ['R-pkg1']
        open_name = 'buildreq.util.open_auto'
        content = 'Depends: pkg1'
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open):
            self.reqs.parse_r_description('filename', pkgs)
        self.assertTrue('R-pkg1' in self.reqs.buildreqs)

    def test_parse_r_desc_imports(self):
        """Test parsing of an R description Imports field."""
        pkgs = ['R-pkg2']
        open_name = 'buildreq.util.open_auto'
        content = 'Imports: pkg2'
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open):
            self.reqs.parse_r_description('filename', pkgs)
        self.assertTrue('R-pkg2' in self.reqs.buildreqs)

    def test_parse_r_desc_linkingto(self):
        """Test parsing of an R description LinkingTo field."""
        pkgs = ['R-pkg3']
        open_name = 'buildreq.util.open_auto'
        content = 'LinkingTo: pkg3'
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open):
            self.reqs.parse_r_description('filename', pkgs)
        self.assertTrue('R-pkg3' in self.reqs.buildreqs)

    def test_parse_r_desc_multiple(self):
        """Test parsing of an R description file that captures multiple fields."""
        pkgs = [
            'R-pkg1',
            'R-pkg2',
            'R-pkg3',
            'R-pkg4',
        ]
        open_name = 'buildreq.util.open_auto'
        content = [
            'Field1: foo',
            'Imports: pkg1, pkg2,',
            '            pkg3   ',
            'LinkingTo: pkg4',
            'FieldFoo: bar',
        ]
        m_open = mock_open(read_data='\n'.join(content))
        with patch(open_name, m_open):
            self.reqs.parse_r_description('filename', pkgs)
        self.assertFalse('R-foo' in self.reqs.buildreqs)
        self.assertFalse('R-bar' in self.reqs.buildreqs)
        self.assertTrue('R-pkg1' in self.reqs.buildreqs)
        self.assertTrue('R-pkg2' in self.reqs.buildreqs)
        self.assertTrue('R-pkg3' in self.reqs.buildreqs)
        self.assertTrue('R-pkg4' in self.reqs.buildreqs)

    def test_parse_r_desc_not_in_os(self):
        """Test parsing of an R description file with some non-OS packages."""
        pkgs = [
            'R-pkg1',
        ]
        open_name = 'buildreq.util.open_auto'
        content = [
            'Imports: pkg1, pkg2',
            'Depends: pkg3',
        ]
        m_open = mock_open(read_data='\n'.join(content))
        with patch(open_name, m_open):
            self.reqs.parse_r_description('filename', pkgs)
        self.assertTrue('R-pkg1' in self.reqs.buildreqs)
        self.assertTrue('R-pkg1' in self.reqs.requires[None])
        # Names absent from the os-packages list are also added, because the
        # DESCRIPTION file is considered authoritative.
        for pkg in ['R-pkg2', 'R-pkg3']:
            self.assertTrue(pkg in self.reqs.buildreqs)
            self.assertTrue(pkg in self.reqs.requires[None])


if __name__ == '__main__':
    unittest.main(buffer=True)
