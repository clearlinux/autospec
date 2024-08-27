import subprocess
import os
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

import util


def mock_gen(rv=None):
    def mock_f(*args, **kwargs):
        return rv

    return mock_f


class TestUtil(unittest.TestCase):

    def test_call(self):
        """
        Test call with default arguments, make sure it passes out the correct
        returncode
        """
        call_backup = subprocess.call
        util.subprocess.call = mock_gen(rv=0)
        self.assertEqual(util.call('some command'), 0)
        util.subprocess.call = call_backup

    def test_call_check(self):
        """
        Test call with check=True (default) and a bad returncode. Should raise a
        CalledProcessError
        """
        call_backup = subprocess.call
        util.subprocess.call = mock_gen(rv=1)
        with self.assertRaises(subprocess.CalledProcessError):
            util.call('some command')

        util.subprocess.call = call_backup

    def test_call_no_check(self):
        """
        Test call with check=False and a bad returncode, should return the
        returncode
        """
        call_backup = subprocess.call
        util.subprocess.call = mock_gen(rv=1)
        self.assertEqual(util.call('some command', check=False), 1)
        util.subprocess.call = call_backup

    def test_translate(self):
        """
        Spot-test the translate function with a package defined in
        translate.dic
        """
        self.assertEqual(util.translate('dateutil-python'), 'pypi-python_dateutil')

    def test_binary_in_path(self):
        """
        Test binary_in_path
        """
        with tempfile.TemporaryDirectory() as tmpd:
            open(os.path.join(tmpd, 'testbin'), 'w').close()
            util.os.environ["PATH"] = tmpd
            self.assertTrue(util.binary_in_path('testbin'))
            self.assertEqual(util.os_paths, [tmpd])

    def test__process_build_log_bad_patch(self):
        """
        Test _process_build_log with a bad patch
        """
        def isfile_mock(_):
            return True
        isfile_backup = util.os.path.isfile
        util.os.path.isfile = isfile_mock
        call_backup = util.call
        util.call = MagicMock()
        open_name = 'util.open_auto'
        content = "Patch #1 (bad.patch):\nHunk #1 FAILED at 1."
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            util._process_build_log('filename')

        util.os.path.isfile = isfile_backup
        mock_call = util.call
        util.call = call_backup
        self.assertTrue(len(mock_call.mock_calls) == 3)



if __name__ == '__main__':
    unittest.main(buffer=True)
