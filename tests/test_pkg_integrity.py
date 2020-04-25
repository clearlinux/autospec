from io import BytesIO
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import config
import download
import pkg_integrity


TESTDIR = os.path.join(os.getcwd(), "tests/testfiles/pkg_integrity")
TESTKEYDIR = os.path.join(TESTDIR, "testkeys")

PACKAGE_URL = "http://pkgconfig.freedesktop.org/releases/pkg-config-0.29.1.tar.gz"
XATTR_PKT_URL = "http://pypi.debian.net/xattr/xattr-0.9.1.tar.gz"
NO_SIGN_PKT_URL = "http://www.ferzkopp.net/Software/SDL_gfx-2.0/SDL_gfx-2.0.25.tar.gz"
GEM_PKT = "https://rubygems.org/downloads/hoe-debugging-1.2.1.gem"
NOSIGN_PKT_URL_BAD = "http://gnu.mirrors.pair.com/savannah/savannah/quagga/bad_quagga-1.1.0.tar.gz"
NOSIGN_PKT_URL = "http://download.savannah.gnu.org/releases/quagga/quagga-1.1.0.tar.gz"
NOSIGN_SIGN_URL = "http://download.savannah.gnu.org/releases/quagga/quagga-1.1.0.tar.gz.asc"
PYPI_MD5_ONLY_PKG = "http://pypi.debian.net/tappy/tappy-0.9.2.tar.gz"
GNOME_SHA256_PKG = "https://download.gnome.org/sources/pygobject/3.24/pygobject-3.24.0.tar.xz"
QT_SHA256_PKG = "https://download.qt.io/official_releases/qt/5.12/5.12.4/submodules/qtspeech-everywhere-src-5.12.4.tar.xz"
KEYID = "EC2392F2EDE74488680DA3CF5F2B4756ED873D23"


def mock_download_do_curl(url, dst=None):
    bad_sigs = ["http://pkgconfig.freedesktop.org/releases/pkg-config-0.29.1.tar.gz.sig",
                "http://www.ferzkopp.net/Software/SDL_gfx-2.0/SDL_gfx-2.0.25.tar.gz.sig",
                "http://www.ferzkopp.net/Software/SDL_gfx-2.0/SDL_gfx-2.0.25.tar.gz.asc",
                "http://www.ferzkopp.net/Software/SDL_gfx-2.0/SDL_gfx-2.0.25.tar.gz.sign"]
    if not dst:
        return BytesIO(b'foobar')
    src = os.path.join(TESTDIR, os.path.basename(url))
    if dst and os.path.isfile(src):
        shutil.copyfile(src, dst)
        return dst
    else:
        return None
    if url in bad_sigs:
        return None


@patch('download.do_curl', mock_download_do_curl)
class TestCheckFn(unittest.TestCase):

    def test_check_matching_sign_url(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            pkey = "023A4420C7EC6914.pkey"
            shutil.copy(os.path.join(TESTKEYDIR, pkey), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)) + ".asc", tmpd)
            result = pkg_integrity.check(PACKAGE_URL, conf)
            self.assertTrue(result)

    def test_check_with_existing_sign(self):
        """ Download signature for local verification """
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "6FE57CA8C1A4AEA6.pkey"), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(NOSIGN_PKT_URL)), tmpd)
            result = pkg_integrity.check(NOSIGN_PKT_URL, conf)
            self.assertTrue(result)


@patch('download.do_curl', mock_download_do_curl)
class TestDomainBasedVerifiers(unittest.TestCase):

    def _mock_pypi_get_info(pkg):
        info = '''
        {
            "info": {
                "author_email": "user@example.com",
                "name": "tappy"
            },
            "releases": {
                "0.9.0": [],
                "0.9.2": [
                    {
                        "filename": "tappy-0.9.2.tar.gz",
                        "md5_digest": "82e7f161746987b4da64c3347a2a2959"
                    }
                ]
            }
        }
        '''
        return json.loads(info)

    def run_test_for_domain(self, Verifier, url):
        with tempfile.TemporaryDirectory() as tmpd:
            filen = os.path.basename(url)
            shutil.copy(os.path.join(TESTDIR, filen), tmpd)
            package_path = os.path.join(tmpd, filen)
            verifier = Verifier(**{'package_path': package_path,
                                   'url': url})
            return verifier.verify()
        return None

    @patch('pkg_integrity.PyPiVerifier.get_info', _mock_pypi_get_info)
    def test_pypi(self):
        result = self.run_test_for_domain(pkg_integrity.PyPiVerifier, PYPI_MD5_ONLY_PKG)
        self.assertTrue(result)

    def _mock_fetch_shasum(url):
        return (
                "100395496483fcea7ba03fc1655c7a770f7f2e12e93be8bda2e31fec42debde0 pygobject-3.24.0.news\n"
                "ae417db3be2a197b403bba6472cfb35a6e642cd802660832acb9c96123f79463  pygobject-3.24.0.changes\n"
                "4e228b1c0f36e810acd971fad1c7030014900d8427c308d63a560f3f1037fa3c pygobject-3.24.0.tar.xz"
                )

    @patch('pkg_integrity.GnomeOrgVerifier.fetch_shasum', _mock_fetch_shasum)
    def test_gnome_org(self):
        result = self.run_test_for_domain(pkg_integrity.GnomeOrgVerifier, GNOME_SHA256_PKG)
        self.assertTrue(result)

    @patch('pkg_integrity.QtIoVerifier.fetch_shasum')
    def test_qt_io(self, test_fetch):
        test_fetch.return_value = "2ff9660fb3f5663c9161f491d1a304db62691720136ae22c145ef6a1c94b90ec  qtspeech-everywhere-src-5.12.4.tar.xz\n"
        result = self.run_test_for_domain(pkg_integrity.QtIoVerifier, QT_SHA256_PKG)
        self.assertTrue(result)


@patch('download.do_curl', mock_download_do_curl)
class TestGEMShaVerifier(unittest.TestCase):

    def _mock_get_gem_info(pkg):
        info = '''
        [
            {
                "number": "2.0.0",
                "sha": "2ac86b58bd2d0b4164c6d82e6d46381c987c47b0eb76428fd6e616370af2cc67"
            },
            {
                "number": "1.2.1",
                "sha": "b391da81ea5efb96d648e69c852e386a269129f543e371c8db64ada80342ac5f"
            }
        ]
        '''
        return json.loads(info)

    @patch('pkg_integrity.GEMShaVerifier.get_rubygems_info', _mock_get_gem_info)
    def test_from_url(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            filen = os.path.basename(GEM_PKT)
            shutil.copy(os.path.join(TESTDIR, filen), tmpd)
            result = pkg_integrity.check(GEM_PKT, conf)
            self.assertTrue(result)

    @patch('pkg_integrity.GEMShaVerifier.get_rubygems_info', _mock_get_gem_info)
    def test_non_matchingsha(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            out_file = os.path.join(tmpd, os.path.basename(GEM_PKT))
            f = open(out_file, 'wb')
            f.write(b'this is made up data that will force a failure')
            f.close()
            with self.assertRaises(SystemExit) as a:
                pkg_integrity.check(GEM_PKT, conf)
            self.assertEqual(a.exception.code, 1)


@patch('download.do_curl', mock_download_do_curl)
class TestGPGVerifier(unittest.TestCase):

    def test_from_url(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "023A4420C7EC6914.pkey"), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)), tmpd)
            result = pkg_integrity.check(PACKAGE_URL, conf)
            self.assertTrue(result)

    def test_invalid_key(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "6FE57CA8C1A4AEA6.pkey"), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(NOSIGN_PKT_URL_BAD)), tmpd)
            with open(os.path.join(tmpd, os.path.basename(NOSIGN_PKT_URL_BAD) + ".asc"), 'w') as ofile:
                ofile.write("Invalid signature")
            result = pkg_integrity.check(NOSIGN_PKT_URL_BAD, conf)
            self.assertIsNone(result)

    def test_key_not_found(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "6FE57CA8C1A4AEA6.pkey"), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(NOSIGN_PKT_URL_BAD)), tmpd)
            result = pkg_integrity.check(NOSIGN_PKT_URL_BAD, conf)
            self.assertIsNone(result)

    def test_from_disk(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "023A4420C7EC6914.pkey"), tmpd)
            out_file = os.path.join(tmpd, os.path.basename(PACKAGE_URL))
            out_key = out_file + ".asc"
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)) + ".asc", tmpd)
            result = pkg_integrity.from_disk(PACKAGE_URL, out_file, out_key, conf)
            self.assertTrue(result)

    def test_non_matchingsig(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "023A4420C7EC6914.pkey"), tmpd)
            out_file = os.path.join(tmpd, os.path.basename(PACKAGE_URL))
            f = open(out_file, 'wb')
            f.write(b'made up date that will fail check')
            f.close()
            with self.assertRaises(SystemExit) as a:
                pkg_integrity.check(PACKAGE_URL, conf)
            self.assertEqual(a.exception.code, 1)

    def test_result_on_non_existent_pkg_path(self):
        conf = config.Config('')
        conf.rewrite_config_opts = unittest.mock.Mock()
        conf.config_opts['verify_required'] = False
        result = pkg_integrity.from_disk('http://nokey.com/package.tar.gz',
                                         'NonExistentPKG.tar.gz',
                                         'NonExistentKey.asc',
                                         conf)
        self.assertIsNone(result)

    def test_result_on_nosign_package(self):
        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTDIR, os.path.basename(NOSIGN_PKT_URL)), tmpd)
            result = pkg_integrity.check(NO_SIGN_PKT_URL, conf)
            self.assertIsNone(result)

    @patch.object(pkg_integrity.GPGCli, 'exec_cmd')
    @patch('pkg_integrity.parse_gpg_packets')
    def test_result_multiple_sig(self, mock_parse, mock_exec):
        """Test verification of first signature of tarball with multiple signatures."""
        def packets_separator(filename, **kwargs):
            if filename.endswith('.pkey'):
                packets = [
                    {
                        'offset': 528,
                        'length': 37,
                        'type': 'user ID',
                        'email': 'user1@example.com',
                    },
                ]
            elif filename.endswith('.asc'):
                packets = [
                    {
                        'offset': 0,
                        'length': 543,
                        'type': 'signature',
                        'keyid': '023A4420C7EC6914',
                    },
                    {
                        'offset': 543,
                        'length': 543,
                        'type': 'signature',
                        'keyid': '12345678DEADCAFE',
                    },
                ]
            return packets
        mock_parse.side_effect = packets_separator

        mock_exec.return_value = (b'', b'', 0)

        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "023A4420C7EC6914.pkey"), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)), tmpd)
            result = pkg_integrity.check(PACKAGE_URL, conf)
            self.assertTrue(result)
            self.assertEqual(mock_parse.call_count, 4)
            self.assertEqual(mock_exec.call_count, 3)
            self.assertEqual(pkg_integrity.EMAIL, "user1@example.com")
            self.assertEqual(pkg_integrity.KEYID, "023A4420C7EC6914")

    @patch.object(pkg_integrity.GPGCli, 'exec_cmd')
    @patch('pkg_integrity.parse_gpg_packets')
    def test_result_multiple_sig_no_separators(self, mock_parse, mock_exec):
        """Test skipping of sig verification in the multiple sig case when packet separators are absent."""
        def packets_no_separator(filename, **kwargs):
            if filename.endswith('.pkey'):
                packets = [
                    {
                        'type': 'user ID',
                        'email': 'user2@example.com',
                    },
                ]
            elif filename.endswith('.asc'):
                packets = [
                    {
                        'type': 'signature',
                        'keyid': '023A4420C7EC6914',
                    },
                    {
                        'type': 'signature',
                        'keyid': 'DEADCAFEC7EC6914',
                    },
                ]
            return packets
        mock_parse.side_effect = packets_no_separator

        mock_exec.return_value = (b'', b'', 0)

        with tempfile.TemporaryDirectory() as tmpd:
            conf = config.Config(tmpd)
            conf.rewrite_config_opts = unittest.mock.Mock()
            conf.config_opts['verify_required'] = False
            shutil.copy(os.path.join(TESTKEYDIR, "023A4420C7EC6914.pkey"), tmpd)
            shutil.copy(os.path.join(TESTDIR, os.path.basename(PACKAGE_URL)), tmpd)
            with self.assertRaises(SystemExit) as msg:
                result = pkg_integrity.check(PACKAGE_URL, conf)
            self.assertEqual(msg.exception.code, 1)
            self.assertEqual(mock_parse.call_count, 4)
            self.assertEqual(mock_exec.call_count, 2)
            self.assertEqual(pkg_integrity.EMAIL, "user2@example.com")
            self.assertEqual(pkg_integrity.KEYID, "023A4420C7EC6914")


class TestInputGetter(unittest.TestCase):

    def test_timput(self):
        ig = pkg_integrity.InputGetter(default='N', timeout=2)
        answer = ig.get_answer()
        self.assertIsNone(answer)
        ig = pkg_integrity.InputGetter(default='Y', timeout=2)
        answer = ig.get_answer()
        self.assertIsNone(answer)


class TestUtils(unittest.TestCase):

    def test_get_verifier(self):
        x = pkg_integrity.get_verifier('file.abcd')
        self.assertEqual(x, None)

        y = pkg_integrity.get_verifier('xorriso-1.4.6.tar.gz')(
                package_path='',
                url='http://ftp.gnu.org/gnu/xorriso/xorriso-1.4.6.tar.gz',
                package_check='http://ftp.gnu.org/gnu/xorriso/xorriso-1.4.6.tar.gz.asc'
                )
        self.assertTrue(isinstance(y, pkg_integrity.GPGVerifier))

        z = pkg_integrity.get_verifier('jeweler-2.1.1.gem')(
                package_path='',
                url='https://rubygems.org/downloads/jeweler-2.1.1.gem'
                )
        self.assertTrue(isinstance(z, pkg_integrity.GEMShaVerifier))

    def test_parse_gpg_packets_for_keyid(self):
        """Test parse_gpg_packets() to retrieve keyid info."""
        def check_packets(algo, key_id, packet_count, packet_with_val):
            with tempfile.NamedTemporaryFile(delete=True) as tmpf:
                tmpf.write(algo)
                tmpf.flush()
                packets = pkg_integrity.parse_gpg_packets(tmpf.name)
                self.assertIsNotNone(packets)
                self.assertEqual(len(packets), packet_count)
                self.assertEqual(packets[packet_with_val]["keyid"], key_id)
                tmpf.close()

        check_packets(KEY_ALGO17, '8AFAFCD242818A52', 6, 1)
        check_packets(KEY_ALGO1, '330239C1C4DAFEE1', 1, 0)

    def test_get_keyid(self):
        """Test get_keyid() to retrieve key ID from GPG key or signature."""
        def check_get_keyid(algo, key_id):
            with tempfile.NamedTemporaryFile(delete=True) as tmpf:
                tmpf.write(algo)
                tmpf.flush()
                result = pkg_integrity.get_keyid(tmpf.name)
                self.assertEqual(result, key_id)
                tmpf.close()

        check_get_keyid(KEY_ALGO17, '8AFAFCD242818A52')
        check_get_keyid(KEY_ALGO1, '330239C1C4DAFEE1')

    def test_get_keyid_none(self):
        """Test get_keyid() when the key name is invalid."""
        false_name = '/false/name'
        self.assertTrue(pkg_integrity.get_keyid(false_name) is None)

    def _mock_download_file(url, dst=None):
        # make return codes match by url to ensure we are using the expected signature type
        if url in ("http://ftp.gnu.org/pub/gnu/gperf/gperf-3.0.4.tar.gz.sig",
                "http://download.savannah.gnu.org/releases/quilt/quilt-0.65.tar.gz.asc",
                "http://download.savannah.gnu.org/releases/freetype/freetype-2.9.tar.bz2.sign",
                "http://pypi.debian.net/cmd2/cmd2-0.6.9.tar.gz.asc",
                "https://pypi.python.org/packages/c6/fe/97319581905de40f1be7015a0ea1bd336a756f6249914b148a17eefa75dc/Cython-0.24.1.tar.gz.asc"):
            return os.path.join(dst, os.path.basename(url))
        return None

    @patch('download.do_curl', _mock_download_file)
    def test_get_signature_url(self):
        url_from_gnu = "http://ftp.gnu.org/pub/gnu/gperf/gperf-3.0.4.tar.gz"
        url_from_gnu1 = "http://download.savannah.gnu.org/releases/quilt/quilt-0.65.tar.gz"
        url_from_gnu2 = "http://download.savannah.gnu.org/releases/freetype/freetype-2.9.tar.bz2"
        url_from_pypi = "http://pypi.debian.net/cmd2/cmd2-0.6.9.tar.gz"
        url_from_pypi1 = "https://pypi.python.org/packages/c6/fe/97319581905de40f1be7015a0ea1bd336a756f6249914b148a17eefa75dc/Cython-0.24.1.tar.gz"

        self.assertEqual(pkg_integrity.get_signature_file(url_from_gnu, '.')[-4:], '.sig')
        self.assertEqual(pkg_integrity.get_signature_file(url_from_pypi, '.')[-4:], '.asc')
        self.assertEqual(pkg_integrity.get_signature_file(url_from_gnu1, '.')[-4:], '.asc')
        self.assertEqual(pkg_integrity.get_signature_file(url_from_gnu2, '.')[-5:], '.sign')
        self.assertEqual(pkg_integrity.get_signature_file(url_from_pypi1, '.')[-4:], '.asc')

    def test_parse_gpg_packets_for_email(self):
        """Test parse_gpg_packets() to retrieve email info."""
        def check_packets(algo, email, packet_count, packet_with_val):
            with tempfile.NamedTemporaryFile(delete=True) as tmpf:
                tmpf.write(algo)
                tmpf.flush()
                packets = pkg_integrity.parse_gpg_packets(tmpf.name)
                self.assertIsNotNone(packets)
                self.assertEqual(len(packets), packet_count)
                if packet_with_val:
                    self.assertEqual(packets[packet_with_val]["email"], email)
                tmpf.close()

        check_packets(KEY_ALGO17, 'kislyuk@gmail.com', 6, 0)
        check_packets(KEY_ALGO1, None, 1, None)

    def test_get_email(self):
        """Test get_email() to retrieve email info from GPG key."""
        def check_get_email(algo, email):
            with tempfile.NamedTemporaryFile(delete=True) as tmpf:
                tmpf.write(algo)
                tmpf.flush()
                result = pkg_integrity.get_email(tmpf.name)
                self.assertEqual(result, email)
                tmpf.close()

        check_get_email(KEY_ALGO17, 'kislyuk@gmail.com')
        check_get_email(KEY_ALGO1, None)

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
