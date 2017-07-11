import os
import tempfile
import unittest
from unittest.mock import mock_open, patch
import test


def mock_generator(rv=None):
    def mock_f(*args, **kwargs):
        return rv

    return mock_f


class TestTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.open_name = 'test.open'
        test.config.config_opts['skip_tests'] = False
        test.config.config_opts['allow_test_failures'] = False
        test.os.path.isfile = mock_generator(True)

    def setUp(self):
        test.tests_config = ''
        test.tarball.name = ''
        test.buildreq.buildreqs = set()

    def test_check_regression(self):
        """
        Test check_regression
        """
        def mock_parse_log(log):
            return ',120,100,20,0,0'

        parse_log_backup = test.count.parse_log
        test.count.parse_log = mock_parse_log
        m_open = mock_open()
        with patch(self.open_name, m_open, create=True):
            test.check_regression('pkgdir')

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

        parse_log_backup = test.count.parse_log
        test.count.parse_log = mock_parse_log
        m_open = mock_open()
        with patch(self.open_name, m_open, create=True):
            test.check_regression('pkgdir')

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
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['Makefile.in'])
        content = 'check:'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            test.scan_for_tests('pkgdir')

        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config,
                         'make VERBOSE=1 V=1 %{?_smp_mflags} check')

    def test_scan_for_tests_makecheck_am(self):
        """
        Test scan_for_tests with makecheck suite via Makefile.am
        """
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['Makefile.am'])
        content = 'check:'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            test.scan_for_tests('pkgdir')

        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config,
                         'make VERBOSE=1 V=1 %{?_smp_mflags} check')

    def test_scan_for_tests_perlcheck_PL(self):
        """
        Test scan_for_tests with perlcheck suite
        """
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['Makefile.PL'])
        test.scan_for_tests('pkgdir')
        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config, 'make TEST_VERBOSE=1 test')

    def test_scan_for_tests_perlcheck_in(self):
        """
        Test scan_for_tests with perlcheck suite via Makefile.in
        """
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['Makefile.in'])
        content = 'test:'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            test.scan_for_tests('pkgdir')
        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config, 'make TEST_VERBOSE=1 test')

    def test_scan_for_tests_setup(self):
        """
        Test scan_for_tests with setup.py suite
        """
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['setup.py'])
        content = 'test_suite'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            test.scan_for_tests('pkgdir')

        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config,
                         'PYTHONPATH=%{buildroot}/usr/lib/python3.6/site-packages '
                         'python3 setup.py test')

    def test_scan_for_tests_cmake(self):
        """
        Test scan_for_tests with cmake suite
        """
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['CMakeLists.txt'])
        content = 'enable_testing'
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            test.scan_for_tests('pkgdir')

        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config,
                         'pushd clr-build ; make test ; popd')

    def test_scan_for_tests_rakefile(self):
        """
        Test scan_for_tests with rakefile suite
        """
        test.tarball.name = 'rubygem-test'
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['Rakefile'])
        test.scan_for_tests('pkgdir')
        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config,
                         'pushd %{buildroot}%{gem_dir}/gems/' +
                         test.tarball.tarball_prefix +
                         '\nrake --trace test '
                         'TESTOPTS=\"-v\"\npopd')
        self.assertEqual(test.buildreq.buildreqs,
                         set(['rubygem-rake',
                              'rubygem-test-unit',
                              'rubygem-minitest',
                              'ruby']))

    def test_scan_for_tests_rspec(self):
        """
        Test scan_for_tests with rspec suite
        """
        test.tarball.name = 'rubygem-test'
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['spec'])
        test.scan_for_tests('pkgdir')
        test.os.listdir = listdir_backup
        self.assertEqual(test.tests_config,
                         'pushd %{buildroot}%{gem_dir}/gems/' +
                         test.tarball.tarball_prefix +
                         '\nrspec -I.:lib spec/\npopd')
        self.assertEqual(test.buildreq.buildreqs,
                         set(['rubygem-diff-lcs',
                              'rubygem-rspec',
                              'rubygem-devise',
                              'rubygem-rspec-mocks',
                              'rubygem-rspec-support',
                              'rubygem-rspec-core',
                              'rubygem-rspec-expectations']))

    def test_scan_for_tests_rubygem(self):
        """
        Test scan_for_tests with ruby suite
        """
        test.tarball.name = 'rubygem-test'
        with tempfile.TemporaryDirectory() as tmpd:
            # create the test files
            os.mkdir(os.path.join(tmpd, 'test'))
            open(os.path.join(tmpd, 'test', 'test_a.rb'), 'w').close()
            open(os.path.join(tmpd, 'test', 'b_test.rb'), 'w').close()
            test.scan_for_tests(tmpd)

        self.assertEqual(test.tests_config,
                         'pushd %{buildroot}%{gem_dir}/gems/'
                         '\nruby -v -I.:lib:test test*/test_*.rb'
                         '\nruby -v -I.:lib:test test*/*_test.rb'
                         '\npopd')

    def test_scan_for_tests_tox_requires(self):
        """
        Test scan_for_tests with tox.ini in the files list, should add several
        build requirements
        """
        listdir_backup = os.listdir
        test.os.listdir = mock_generator(['tox.ini'])
        test.scan_for_tests('pkgdir')
        test.os.listdir = listdir_backup
        self.assertEqual(test.buildreq.buildreqs,
                         set(['tox',
                              'pytest',
                              'virtualenv',
                              'pluggy',
                              'py-python']))


if __name__ == "__main__":
    unittest.main(buffer=True)
