from enum import Enum, auto
import unittest
from unittest.mock import patch, mock_open, call

import pycurl

import download


class MockOpts(Enum):
    URL = auto()
    WRITEDATA = auto()
    POSTFIELDS = auto()
    FOLLOWLOCATION = auto()
    FAILONERROR = auto()
    CONNECTTIMEOUT = auto()
    TIMEOUT = auto()
    LOW_SPEED_LIMIT = auto()
    LOW_SPEED_TIME = auto()


def init_curl_instance(mock_curl):
    instance = mock_curl.return_value
    instance.URL = MockOpts.URL
    instance.FOLLOWLOCATION = MockOpts.FOLLOWLOCATION
    instance.FAILONERROR = MockOpts.FAILONERROR
    instance.WRITEDATA = MockOpts.WRITEDATA
    instance.POSTFIELDS = MockOpts.POSTFIELDS
    return instance


def test_opts(*opts):
    if not opts:
        raise Exception("no curl options specified")
    if len(opts) != 2:
        raise Exception("expected two args to setopt()")
    key, val = opts
    if key == MockOpts.WRITEDATA:
        val.write(b'foobar')


class TestDownload(unittest.TestCase):

    @patch('download.pycurl.Curl')
    def test_download_get_success_no_dest(self, test_curl):
        """
        Test successful GET request when dest is not set.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        data = download.do_curl("foo")
        self.assertEqual(b'foobar', data.getvalue())

    @patch('download.pycurl.Curl')
    def test_download_set_basic(self, test_curl):
        """
        Test curl option settings set by default
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        data = download.do_curl("foo")
        calls = [
            call().setopt(MockOpts.URL, 'foo'),
            call().setopt(MockOpts.FOLLOWLOCATION, True),
            call().setopt(MockOpts.FAILONERROR, True),
        ]
        test_curl.assert_has_calls(calls)

    @patch('download.pycurl.Curl')
    def test_download_set_post(self, test_curl):
        """
        Test setting of POSTFIELDS curl option
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        data = download.do_curl("foo", post='postdata')
        calls = [
            call().setopt(MockOpts.POSTFIELDS, 'postdata'),
        ]
        test_curl.assert_has_calls(calls)

    @patch('download.pycurl.Curl')
    def test_download_get_failure_no_dest(self, test_curl):
        """
        Test failed GET request when dest is not set.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        instance.perform.side_effect = pycurl.error
        data = download.do_curl("foo")
        self.assertIsNone(data)

    @patch('download.sys.exit')
    @patch('download.pycurl.Curl')
    def test_download_get_failure_fatal(self, test_curl, test_exit):
        """
        Test failed GET request when is_fatal is set.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        instance.perform.side_effect = pycurl.error
        data = download.do_curl("foo", is_fatal=True)
        test_exit.assert_called_once_with(1)

    @patch('download.open', new_callable=mock_open)
    @patch('download.pycurl.Curl')
    def test_download_get_success_dest(self, test_curl, test_open):
        """
        Test successful GET request when dest is set.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        data = download.do_curl("foo", "testdest")
        test_open.assert_called_once_with('testdest', 'wb')
        test_open().write.assert_called_once_with(b'foobar')

    @patch('download.os.path.exists')
    @patch('download.open', new_callable=mock_open)
    @patch('download.pycurl.Curl')
    def test_download_get_write_fail_dest(self, test_curl, test_open, test_path):
        """
        Test failure to write to dest after successful GET request.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        test_open.side_effect = IOError
        test_path.return_value = None
        data = download.do_curl("foo", "testdest")
        self.assertIsNone(data)

    @patch('download.sys.exit')
    @patch('download.os.path.exists')
    @patch('download.open')
    @patch('download.pycurl.Curl')
    def test_download_write_fail_fatal(self, test_curl, test_open, test_path, test_exit):
        """
        Test fatal failure to write to dest after successful GET request.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        test_open.side_effect = IOError
        test_path.return_value = None
        data = download.do_curl("foo", "testdest", is_fatal=True)
        test_exit.assert_called_once_with(1)

    @patch('download.os.unlink')
    @patch('download.os.path.exists')
    @patch('download.open')
    @patch('download.pycurl.Curl')
    def test_download_write_fail_remove_dest(self, test_curl, test_open, test_path, test_unlink):
        """
        Test removal of dest following a write failure.
        """
        instance = init_curl_instance(test_curl)
        instance.setopt.side_effect = test_opts
        test_open.side_effect = IOError
        test_path.return_value = True
        data = download.do_curl("foo", "testdest")
        test_path.assert_called_once_with("testdest")
        test_unlink.assert_called_once_with("testdest")


if __name__ == '__main__':
    unittest.main(buffer=True)
