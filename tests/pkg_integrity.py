import os
import unittest
import tempfile
from autospec.pkg_integrity import (check,
                                    get_verifier,
                                    parse_keyid,
                                    get_keyid,
                                    from_url,
                                    from_disk,
                                    attempt_to_download,
                                    get_signature_url,
                                    GPGVerifier,
                                    GEMShaVerifier,)


ALEMBIC_PKT_URL = "http://pypi.debian.net/alembic/alembic-0.8.8.tar.gz"
XATTR_PKT_URL = "http://pypi.debian.net/xattr/xattr-0.9.1.tar.gz"
NO_SIGN_PKT_URL = "https://pypi.python.org/packages/source/c/crudini/crudini-0.5.tgz"
GEM_PKT = "https://rubygems.org/downloads/hoe-debugging-1.2.1.gem"
NOSIGN_PKT_URL = "http://download.savannah.gnu.org/releases/quagga/quagga-1.1.0.tar.gz"
NOSIGN_SIGN_URL = "http://download.savannah.gnu.org/releases/quagga/quagga-1.1.0.tar.gz.asc"


class TestCheckFn(unittest.TestCase):

    def test_check_no_matching_sign_url(self):
        """ Test a package that does not have simple signature pattern """
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(NOSIGN_PKT_URL))
            attempt_to_download(NOSIGN_PKT_URL, out_file)
            result = check(NOSIGN_PKT_URL, tmpd)
            self.assertEqual(result, None)

    def test_check_matching_sign_url(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(ALEMBIC_PKT_URL))
            attempt_to_download(ALEMBIC_PKT_URL, out_file)
            result = check(ALEMBIC_PKT_URL, tmpd)
            self.assertTrue(result)

    def test_check_with_existing_sign(self):
        """ Download signature for local verification """
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(NOSIGN_PKT_URL))
            attempt_to_download(NOSIGN_PKT_URL, out_file)
            key_file = os.path.join(tmpd, os.path.basename(NOSIGN_PKT_URL))
            attempt_to_download(NOSIGN_SIGN_URL, key_file + '.asc')
            result = check(NOSIGN_PKT_URL, tmpd)
            self.assertTrue(result)


class TestGEMShaVerifier(unittest.TestCase):

    def test_from_url(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(GEM_PKT))
            attempt_to_download(GEM_PKT, out_file)
            result = from_url(GEM_PKT, tmpd)
            self.assertTrue(result)

    def test_non_matchingsha(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(GEM_PKT))
            f = open(out_file, 'wb')
            f.write(b'this is made up data that will force a failure')
            f.close()
            with self.assertRaises(SystemExit) as a:
                from_url(GEM_PKT, tmpd)
            self.assertEqual(a.exception.code, 1)


class TestGPGVerifier(unittest.TestCase):

    def test_from_url(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(ALEMBIC_PKT_URL))
            attempt_to_download(ALEMBIC_PKT_URL, out_file)
            out_file1 = os.path.join(tmpd, os.path.basename(XATTR_PKT_URL))
            attempt_to_download(XATTR_PKT_URL, out_file1)
            result = from_url(ALEMBIC_PKT_URL, tmpd)
            self.assertTrue(result)
            result = from_url(XATTR_PKT_URL, tmpd)
            self.assertTrue(result is None)

    def test_from_disk(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(ALEMBIC_PKT_URL))
            out_key = out_file + '.asc'
            attempt_to_download(ALEMBIC_PKT_URL, out_file)
            attempt_to_download(ALEMBIC_PKT_URL + '.asc', out_key)
            result = from_disk(out_file, out_key)
            self.assertTrue(result)

    def test_non_matchingsig(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(ALEMBIC_PKT_URL))
            f = open(out_file, 'wb')
            f.write(b'made up date that will fail check')
            f.close()
            with self.assertRaises(SystemExit) as a:
                from_url(ALEMBIC_PKT_URL, tmpd)
            self.assertEqual(a.exception.code, 1)

    def test_result_on_non_existent_pkg_path(self):
        result = from_disk('NonExistentPKG.tar.gz', 'NonExistentKey.asc')
        self.assertTrue(result is None)

    def test_result_on_nosign_package(self):
        with tempfile.TemporaryDirectory() as tmpd:
            out_file = os.path.join(tmpd, os.path.basename(NO_SIGN_PKT_URL))
            attempt_to_download(NO_SIGN_PKT_URL, out_file)
            result = from_url(NO_SIGN_PKT_URL, tmpd)
            self.assertTrue(result is None)


class TestUtils(unittest.TestCase):

    def test_get_verifier(self):
        x = get_verifier('file.abcd')
        self.assertEqual(x, None)

        y = get_verifier('xorriso-1.4.6.tar.gz')(package_path='', url='http://ftp.gnu.org/gnu/xorriso/xorriso-1.4.6.tar.gz')
        self.assertTrue(isinstance(y, GPGVerifier))

        z = get_verifier('jeweler-2.1.1.gem')(package_path='', url='https://rubygems.org/downloads/jeweler-2.1.1.gem')
        self.assertTrue(isinstance(z, GEMShaVerifier))

    def test_get_keyid(self):

        def check_algo(algo, k_id):
            with tempfile.NamedTemporaryFile(delete=True) as tmpf:
                tmpf.write(algo)
                tmpf.flush()
                self.assertEqual(parse_keyid(tmpf.name), k_id)
                tmpf.close()

        check_algo(KEY_ALGO17, '8AFAFCD242818A52')
        check_algo(KEY_ALGO1, '330239C1C4DAFEE1')

    def test_get_keyid_none(self):
        false_name = '/false/name'
        self.assertTrue(get_keyid(false_name) is None)

    def test_attempt_to_download(self):
        fakeURL = "https://download.my.url.com/file.tar.gz"
        realURLnoFile = "http://pypi.debian.net/alembic/alembic-0.8.8.non-existent.tar.gz"
        realURL = "http://pypi.debian.net/alembic/alembic-0.8.8.tar.gz"

        tmpf = tempfile.NamedTemporaryFile()
        fname = tmpf.name
        tmpf.close()

        self.assertEqual(attempt_to_download(fakeURL, fname), None)
        self.assertEqual(attempt_to_download(realURLnoFile, fname), 404)
        self.assertEqual(attempt_to_download(realURL, fname), 200)

        os.unlink(fname)

    def test_get_signature_url(self):

        url_from_gnu = "http://ftp.gnu.org/pub/gnu/gperf/gperf-3.0.4.tar.gz"
        url_from_gnu1 = "http://download.savannah.gnu.org/releases/quilt/quilt-0.65.tar.gz"
        url_from_pypi = "http://pypi.debian.net/cmd2/cmd2-0.6.9.tar.gz"
        url_from_pypi1 = "https://pypi.python.org/packages/c6/fe/97319581905de40f1be7015a0ea1bd336a756f6249914b148a17eefa75dc/Cython-0.24.1.tar.gz"

        self.assertEqual(get_signature_url(url_from_gnu)[-4:], '.sig')
        self.assertEqual(get_signature_url(url_from_pypi)[-4:], '.asc')
        self.assertEqual(get_signature_url(url_from_gnu1)[-4:], '.sig')
        self.assertEqual(get_signature_url(url_from_pypi1)[-4:], '.asc')


KEY_ALGO1 = b"""\
-----BEGIN PGP SIGNATURE-----

iQEcBAABAgAGBQJX1yrCAAoJEDMCOcHE2v7hwhcH/AqhJ/vqkCOo09Yh89bYRFyb
O5yEpaRV7vo4qoqXht3fQiR3KC3lSKybtScihbQ0xcTeBzSwGPMKPRpOqXEKRnwY
9Zq8ev72Ixi5yVsKdSKjoeM4smXJdQolKnrKy0chsOMzu7cxk7hwejplIMjycKza
g3HM6jtw6v10JDj6a5SJPkrufj2eIHq1enn2di9q9+yyAJGiuWi3ABfINmL3Y9sa
zODoMBD/B7LCZ1Zv6dG7kaN1XS82crOmXrtgcWslKxfGPkdW9SGQdhCtm6f/Z5/w
29adzXFicobZBFBHVnbQ0iRf39omkNxPOhMYwLVQFprzjOPm/DDHSztZj87jbOM=
=Qe1y
-----END PGP SIGNATURE-----
"""

KEY_ALGO17 = b"""\
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1

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
qA34waak3JSxv16lZC0TqIuD
=cHO/
-----END PGP PUBLIC KEY BLOCK-----
"""


if __name__ == '__main__':
    unittest.main(buffer=True)
