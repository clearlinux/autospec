import license
import unittest
import pycurl
import tempfile
import os
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from unittest.mock import patch, mock_open, MagicMock


class TestLicense(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        license.config.setup_patterns()

    def setUp(self):
        license.licenses = []
        license.config.license_fetch = None

    def test_add_license(self):
        """
        Test add_license from valid string, Apache-2 should be translated to
        Apache-2.0
        """
        self.assertTrue(license.add_license('Apache-2'))
        self.assertIn('Apache-2.0', license.licenses)

    def test_add_license_present(self):
        """
        Test add_license from valid string, but license is already present in
        the licenses list. Should return False and should not modify the
        licenses list. GPL-3 translates to GPL-3.0.
        """
        license.licenses.append('GPL-3.0')
        self.assertFalse(license.add_license('GPL-3'))
        self.assertEqual(['GPL-3.0'], license.licenses)

    def test_add_license_blacklisted(self):
        """
        Test add_license from string in license_blacklist. Should return False
        and should not modify the licenses list.
        """
        # sanity check to make sure the licenses list is empty before the later
        # assertIn() call
        self.assertEqual(license.licenses, [])

        self.assertFalse(license.add_license('License'))
        self.assertNotIn('License', license.licenses)

    def test_license_from_copying_hash(self):
        """
        Test license_from_copying_hash with valid license file
        """
        # Calls out to tarball.get_sha1sum to get the hash of the license
        # we might as well test that is returning what it should because it
        # doesn't call any external resources, it just calculates the hash.
        open_name = 'tarball.open'
        with open('tests/COPYING_TEST', 'rb') as copyingf:
            content = copyingf.read()

        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            license.license_from_copying_hash('copying.txt')

        self.assertIn('GPL-3.0', license.licenses)

    def test_license_from_copying_hash_no_license_show(self):
        """
        Test license_from_copying_hash with invalid hash and no license_show
        set
        """
        # Calls out to tarball.get_sha1sum to get the hash of the license
        # we might as well test that is returning what it should because it
        # doesn't call any external resources, it just calculates the hash.
        open_name = 'tarball.open'
        with open('tests/COPYING_TEST', 'rb') as copyingf:
            content = copyingf.read()

        bkup_hash = license.config.license_hashes[license.tarball.get_sha1sum('tests/COPYING_TEST')]
        # remove the hash from license_hashes
        del(license.config.license_hashes[license.tarball.get_sha1sum('tests/COPYING_TEST')])
        license.config.license_show = "license.show.url"
        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            license.license_from_copying_hash('copying.txt')

        # restore the hash
        license.config.license_hashes[license.tarball.get_sha1sum('tests/COPYING_TEST')] = bkup_hash
        self.assertEquals(license.licenses, [])

    def test_license_from_copying_hash_bad_license(self):
        """
        Test license_from_copying_hash with invalid license file
        """
        # Calls out to tarball.get_sha1sum to get the hash of the license
        # we might as well test that is returning what it should because it
        # doesn't call any external resources, it just calculates the hash.
        open_name = 'tarball.open'
        with open('tests/COPYING_TEST', 'rb') as copyingf:
            # note the replace corrupting the file contents
            content = copyingf.read().replace(b"GNU", b"SNU")

        m_open = mock_open(read_data=content)
        with patch(open_name, m_open, create=True):
            license.license_from_copying_hash('copying.txt')

        self.assertEquals(license.licenses, [])

    @patch('pycurl.Curl')
    def test_license_from_copying_hash_license_server_excep(self, mock_pycurl_curl):
        """
        Test license_from_copying_hash with license server when pycurl raises
        an exception.
        """
        class MockCurl():
            URL = None
            WRITEDATA = None
            POSTFIELDS = None
            FOLLOWLOCATION = 0
            def setopt(_, __, ___):
                pass

            def perform(_):
                raise Exception('Test Exception')

            def close(_):
                pass

        # set the mock curl
        license.pycurl.Curl = MockCurl

        license.config.license_fetch = 'license.server.url'
        with open('tests/COPYING_TEST', 'rb') as copyingf:
            content = copyingf.read()

        # Calls out to tarball.get_sha1sum to get the hash of the license
        # we might as well test that is returning what it should because it
        # doesn't call any external resources, it just calculates the hash.
        # Also patch the open in license.py
        m_open = mock_open(read_data=content)
        with patch('tarball.open', m_open, create=True):
            with patch('license.open', m_open, create=True):
                # let's check that the proper thing is being printed as well
                out = StringIO()
                with redirect_stdout(out):
                    with self.assertRaises(SystemExit):
                        license.license_from_copying_hash('copying.txt')

        self.assertIn('Failed to fetch license from ', out.getvalue())

        # unset the manual mock
        license.pycurl.Curl = pycurl.Curl

    @patch('pycurl.Curl')
    def test_license_from_copying_hash_license_server(self, mock_pycurl_curl):
        """
        Test license_from_copying_hash with license server. This is heavily
        mocked.
        """
        class MockBytesIO(BytesIO):
            """
            Mock class for BytesIO to set returnvalue of BytesIO.getvalue()
            """
            def getvalue(_):
                return 'GPL-3.0'.encode('utf-8')

        # set the mocks
        license.BytesIO = MockBytesIO

        license.config.license_fetch = 'license.server.url'
        with open('tests/COPYING_TEST', 'rb') as copyingf:
            content = copyingf.read()

        # Calls out to tarball.get_sha1sum to get the hash of the license
        # we might as well test that is returning what it should because it
        # doesn't call any external resources, it just calculates the hash.
        # Also patch the open in license.py
        m_open = mock_open(read_data=content)
        with patch('tarball.open', m_open, create=True):
            with patch('license.open', m_open, create=True):
                # let's check that the proper thing is being printed as well
                out = StringIO()
                with redirect_stdout(out):
                    license.license_from_copying_hash('copying.txt')

        self.assertIn('GPL-3.0', license.licenses)
        self.assertIn('License     :  GPL-3.0  (server)', out.getvalue())

        # unset the manual mock
        license.BytesIO = BytesIO

    def test_scan_for_licenses(self):
        """
        Test scan_for_licenses in temporary directory with valid license file
        """
        with open('tests/COPYING_TEST', 'rb') as copyingf:
            content = copyingf.read()

        with tempfile.TemporaryDirectory() as tmpd:
            # create the copying file
            with open(os.path.join(tmpd, 'COPYING'), 'w') as newcopyingf:
                newcopyingf.write(content.decode('utf-8'))
            # create some cruft for testing
            for testf in ['testlib.c', 'testmain.c', 'testheader.h']:
                with open(os.path.join(tmpd, testf), 'w') as newtestf:
                    newtestf.write('test content')
            license.scan_for_licenses(tmpd)

        self.assertIn('GPL-3.0', license.licenses)

    def test_scan_for_licenses_none(self):
        """
        Test scan_for_licenses in temporary directory with no matching files.
        Should not add any licenses, should print a fatal message, should exit
        with a status code of 1.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            # create some cruft for testing
            for testf in ['testlib.c', 'testmain.c', 'testheader.h']:
                with open(os.path.join(tmpd, testf), 'w') as newtestf:
                    newtestf.write('test content')
            # let's check that the proper thing is being printed as well
            out = StringIO()
            with redirect_stdout(out):
                with self.assertRaises(SystemExit) as thread:
                    license.scan_for_licenses(tmpd)

        self.assertEqual(thread.exception.code, 1)
        self.assertIn("Cannot find any license", out.getvalue())
        self.assertEqual(license.licenses, [])

    def test_load_specfile(self):
        """
        Test load_specfile with populated license list. This method is not
        normally tested but there is some logic here.
        """
        class MockSpecfile(object):
            licenses = []

        license.licenses = ['GPL-3.0', 'MIT']
        specfile = MockSpecfile()
        license.load_specfile(specfile)
        self.assertEqual(specfile.licenses, license.licenses)

    def test_load_specfile_none(self):
        """
        Test load_specfile with unpopulated license list. This method is not
        normally tested but there is some logic here.
        """
        class MockSpecfile(object):
            licenses = []

        license.licenses = []
        specfile = MockSpecfile()
        license.load_specfile(specfile)
        self.assertEqual(specfile.licenses, [license.default_license])


if __name__ == '__main__':
    unittest.main(buffer=True)
