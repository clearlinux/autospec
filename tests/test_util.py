import subprocess
import os
import tempfile
import unittest
import unittest.mock
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
        self.assertEqual(util.translate('dateutil-python'), 'python-dateutil')

    def test_binary_in_path(self):
        """
        Test binary_in_path
        """
        with tempfile.TemporaryDirectory() as tmpd:
            open(os.path.join(tmpd, 'testbin'), 'w').close()
            util.os.environ["PATH"] = tmpd
            self.assertTrue(util.binary_in_path('testbin'))
            self.assertEqual(util.os_paths, [tmpd])

if __name__ == '__main__':
    unittest.main(buffer=True)
