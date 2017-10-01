import subprocess
import unittest
from unittest.mock import patch, Mock, mock_open, call
import build  # needs to be imported before tarball due to dependencies
import tarball


class FileManager():
    want_dev_split = False


def mock_gen(rv=None):
    def mock_f(*args, **kwargs):
        return rv

    return mock_f


def test_generator(url, name, version):
    """
    Generate a test for each line passed in
    """
    @patch('tarball.build')
    def test_packageurl(self, mock_build):
        """
        Test the name and version detection from tarball url
        """
        tarball.name = ''
        tarball.version = ''
        tarball.url = url
        tarball.name_and_version('', '', FileManager())
        self.assertEqual(tarball.name, name)
        self.assertEqual(tarball.version, version)

    return test_packageurl


def test_setup():
    global TestTarballVersionName
    with open('tests/packageurls', 'r') as pkgurls:
        for urlline in pkgurls.read().split('\n'):
            if not urlline or urlline.startswith('#'):
                continue

            tarball.name = ''
            tarball.version = ''
            (url, name, version) = urlline.split(',')
            test_name = 'test_pat_{}'.format(url)
            test = test_generator(url, name, version)
            setattr(TestTarballVersionName, test_name, test)


class TestTarballVersionName(unittest.TestCase):

    def test_version_configuration_override(self):
        """
        Test the version and name override from the command line
        """
        tarball.name_and_version('something', 'else', FileManager())
        self.assertEqual(tarball.version, 'else')
        self.assertEqual(tarball.name, 'something')

    def test_build_untar(self):
        """
        Test build_untar with common tar -tf output
        """
        check_output_backup = subprocess.check_output
        tarball.subprocess.check_output = mock_gen(rv=TAR_OUT)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_untar('tarballpath'),
                         ('tar --directory=. -xf tarballpath',
                          'libjpeg-turbo-1.5.1'))

    def test_build_untar_leading_dot(self):
        """
        Test build_untar with leading dot to tar -tf output
        """
        check_output_backup = subprocess.check_output
        tar_dotted = ''
        for line in TAR_OUT.split():
            tar_dotted += './{}\n'.format(line)
        tarball.subprocess.check_output = mock_gen(rv=tar_dotted)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_untar('tarball/path'),
                         ('tar --directory=. -xf tarball/path',
                          'libjpeg-turbo-1.5.1'))

    def test_build_untar_leading_dot_line(self):
        """
        Test build_untar with leading dot and leading ./ line to tar -tf output
        """
        check_output_backup = subprocess.check_output
        tar_dotted = './\n'
        for line in TAR_OUT.splitlines():
            tar_dotted += './{}\n'.format(line)
        tarball.subprocess.check_output = mock_gen(rv=tar_dotted)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_untar('tarball/path'),
                         ('tar --directory=. -xf tarball/path',
                          'libjpeg-turbo-1.5.1'))

    def test_build_unzip_hash(self):
        """
        Test build_unzip with hash in output
        """
        check_output_backup = subprocess.check_output
        tarball.subprocess.check_output = mock_gen(rv=UNZIP_OUT)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_unzip('zip/path'),
                         ('unzip -d . zip/path', 'prefix-dir'))

    def test_build_unzip_nohash(self):
        """
        Test build_unzip with no hash in output
        """
        check_output_backup = subprocess.check_output
        unzip_nohash = ''
        for line in UNZIP_OUT.splitlines():
            if 'longhashstring' in line:
                continue
            unzip_nohash += line + '\n'

        tarball.subprocess.check_output = mock_gen(rv=unzip_nohash)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_unzip('zip/path'),
                         ('unzip -d . zip/path', 'prefix-dir'))

    def test_build_gem_unpack(self):
        """
        Test build_gem_unpack
        """
        check_output_backup = subprocess.check_output
        tarball.subprocess.check_output = mock_gen(rv=GEM_OUT)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_gem_unpack('gem/path'),
                         ('gem unpack --target=. gem/path', 'test-prefix'))

    def test_find_extract(self):
        """
        Test find_extract with the three supported filetypes
        (*.zip, *.gem, *.tar*)
        """
        build_unzip_backup = tarball.build_unzip
        build_gem_unpack_backup = tarball.build_gem_unpack
        build_untar_backup = tarball.build_untar

        tarball.build_unzip = Mock(return_value=('', ''))
        tarball.build_gem_unpack = Mock(return_value=('', ''))
        tarball.build_untar = Mock(return_value=('', ''))

        tarball.find_extract('path/to/tar', 'test.zip')
        tarball.find_extract('path/to/tar', 'test.gem')
        tarball.find_extract('path/to/tar', 'test.tar.gz')

        tarball.build_unzip.assert_called_once()
        tarball.build_gem_unpack.assert_called_once()
        tarball.build_untar.assert_called_once()

        tarball.build_unzip = build_unzip_backup
        tarball.build_gem_unpack = build_gem_unpack_backup
        tarball.build_untar = build_untar_backup

    def test_write_makefile(self):
        """
        Test write_makefile for correct archive format
        """
        archives = ['archive1', 'dest1', 'archive2', 'dest2']
        build.download_path = '.'
        tarball.name = 'test'
        tarball.url = 'url'
        m_open = mock_open()
        with patch('tarball.open', m_open, create=True):
            tarball.write_makefile(archives)

        exp_calls = [call().write('PKG_NAME := test\n'),
                     call().write('URL := url\n'),
                     call().write('ARCHIVES := archive1'),
                     call().write(' dest1'),
                     call().write(' \\\n\tarchive2'),
                     call().write(' dest2'),
                     call().write('\n'),
                     call().write('\n'),
                     call().write('include ../common/Makefile.common\n')]
        for m_call in exp_calls:
            self.assertIn(m_call, m_open.mock_calls)


TAR_OUT = 'libjpeg-turbo-1.5.1/\n'                         \
          'libjpeg-turbo-1.5.1/md5/\n'                     \
          'libjpeg-turbo-1.5.1/md5/CMakeLists.txt\n'       \
          'libjpeg-turbo-1.5.1/md5/md5.h\n'                \
          'libjpeg-turbo-1.5.1/md5/md5hl.c\n'              \
          'libjpeg-turbo-1.5.1/md5/md5cmp.c\n'             \
          'libjpeg-turbo-1.5.1/md5/md5.c\n'                \
          'libjpeg-turbo-1.5.1/md5/Makefile.am\n'          \
          'libjpeg-turbo-1.5.1/md5/Makefile.in\n'          \
          'libjpeg-turbo-1.5.1/jerror.c\n'                 \
          'libjpeg-turbo-1.5.1/sharedlib/\n'               \
          'libjpeg-turbo-1.5.1/sharedlib/CMakeLists.txt\n' \
          'libjpeg-turbo-1.5.1/turbojpeg-mapfile\n'        \
          'libjpeg-turbo-1.5.1/jdpostct.c\n'               \
          'libjpeg-turbo-1.5.1/turbojpeg-jni.c\n'


UNZIP_OUT = 'Archive:  file.zip\n'                         \
            'longhashstring\n'                             \
            '  Length      Date    Time    Name\n'         \
            '---------  ---------- -----   ----\n'         \
            '        0  04-03-2017 06:27   prefix-dir/\n'  \
            '      668  04-03-2017 06:27   prefix-dir/.gitignore\n'


GEM_OUT = '/path/to/dir/file1\n'                           \
          '/path/to/dir/file2\n'                           \
          '...\n'                                          \
          'Unpacked gem: \'/path/to/gem/test-prefix\''


# Run test_setup to generate tests
test_setup()


if __name__ == '__main__':
    unittest.main(buffer=True)
