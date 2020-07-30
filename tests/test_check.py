import os
import tempfile
import unittest
from unittest.mock import mock_open, patch

import buildreq
import check
import config
import tarball

def mock_generator(rv=None):
    def mock_f(*args, **kwargs):
        return rv

    return mock_f


class TestTest(unittest.TestCase):
    backup_isfile = check.os.path.isfile

    @classmethod
    def setUpClass(self):
        self.open_name = 'check.util.open_auto'
        check.os.path.isfile = mock_generator(True)

    @classmethod
    def tearDownClass(self):
        check.os.path.isfile = self.backup_isfile

    def setUp(self):
        check.tests_config = ''

    def test_check_regression(self):
        """
        Test check_regression
        """
        def mock_parse_log(log):
            return ',120,100,20,0,0'

        parse_log_backup = check.count.parse_log
        check.count.parse_log = mock_parse_log
        m_open = mock_open()
        open_name = 'util.open'
        with patch(open_name, m_open, create=True):
            check.check_regression('pkgdir', False)

        check.count.parse_log = parse_log_backup

        exp_call = unittest.mock.call().write('Total : 120\n'
                                              'Pass : 100\n'
                                              'Fail : 20\n'
                                              'Skip : 0\n'
                                              'XFail : 0\n')
        self.assertIn(exp_call, m_open.mock_calls)

    def test_check_regression_multi(self):
        """
        Test check_regression with multiple results
        """
        def mock_parse_log(log):
            return 'test-a,120,100,20,0,0\ntest-b,10,5,3,2,1'

        parse_log_backup = check.count.parse_log
        check.count.parse_log = mock_parse_log
        m_open = mock_open()
        open_name = 'util.open'
        with patch(open_name, m_open, create=True):
            check.check_regression('pkgdir', False)

        check.count.parse_log = parse_log_backup

        exp_call = unittest.mock.call().write('Package : test-a\n'
                                              'Total : 120\n'
                                              'Pass : 100\n'
                                              'Fail : 20\n'
                                              'Skip : 0\n'
                                              'XFail : 0\n'
                                              'Package : test-b\n'
                                              'Total : 10\n'
                                              'Pass : 5\n'
                                              'Fail : 3\n'
                                              'Skip : 2\n'
                                              'XFail : 1\n')
        self.assertIn(exp_call, m_open.mock_calls)

    def test_scan_for_tests_makecheck_in(self):
        """
        Test scan_for_tests with makecheck suite
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['Makefile.in'])
        content = 'check:'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            conf.default_pattern = "configure"
            check.scan_for_tests('pkgdir', conf, reqs, tcontent)

        check.os.listdir = listdir_backup
        self.assertEqual(check.tests_config,
                         'make %{?_smp_mflags} check')

    def test_scan_for_tests_makecheck_am(self):
        """
        Test scan_for_tests with makecheck suite via Makefile.am
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['Makefile.am'])
        m_open = mock_open()
        with patch(self.open_name, m_open, create=True):
            conf.default_pattern = "configure_ac"
            check.scan_for_tests('pkgdir', conf, reqs, tcontent)

        check.os.listdir = listdir_backup
        self.assertEqual(check.tests_config,
                         'make %{?_smp_mflags} check')

    def test_scan_for_tests_perlcheck_PL(self):
        """
        Test scan_for_tests with perlcheck suite
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['Makefile.PL'])
        conf.default_pattern = "cpan"
        check.scan_for_tests('pkgdir', conf, reqs, tcontent)
        check.os.listdir = listdir_backup
        self.assertEqual(check.tests_config, 'make TEST_VERBOSE=1 test')

    def test_scan_for_tests_perlcheck_in(self):
        """
        Test scan_for_tests with perlcheck suite via Makefile.in
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['Makefile.in'])
        content = 'test:'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            conf.default_pattern = "cpan"
            check.scan_for_tests('pkgdir', conf, reqs, tcontent)

        check.os.listdir = listdir_backup
        self.assertEqual(check.tests_config, 'make TEST_VERBOSE=1 test')

    def test_scan_for_tests_setup(self):
        """
        Test scan_for_tests with setup.py suite
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['setup.py'])
        content = 'test_suite'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            conf.default_pattern = "distutils3"
            check.scan_for_tests('pkgdir', conf, reqs, tcontent)

        check.os.listdir = listdir_backup
        self.assertEqual(check.tests_config,
                         'PYTHONPATH=%{buildroot}$(python -c "import sys; print(sys.path[-1])") '
                         'python setup.py test')

    def test_scan_for_tests_cmake(self):
        """
        Test scan_for_tests with cmake suite
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['CMakeLists.txt'])
        content = 'enable_testing'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            conf.default_pattern = "cmake"
            check.scan_for_tests('pkgdir', conf, reqs, tcontent)

        check.os.listdir = listdir_backup
        self.assertEqual(check.tests_config,
                         'cd clr-build; make test')

    def test_scan_for_tests_tox_requires(self):
        """
        Test scan_for_tests with tox.ini in the files list, should add several
        build requirements
        """
        reqs = buildreq.Requirements("")
        conf = config.Config("")
        tcontent = tarball.Content("", "", "", [], conf, "")
        listdir_backup = os.listdir
        check.os.listdir = mock_generator(['tox.ini'])
        check.scan_for_tests('pkgdir', conf, reqs, tcontent)
        check.os.listdir = listdir_backup
        self.assertEqual(reqs.buildreqs,
                         set(['tox',
                              'pytest',
                              'virtualenv',
                              'pluggy',
                              'py-python']))


if __name__ == "__main__":
    unittest.main(buffer=True)
