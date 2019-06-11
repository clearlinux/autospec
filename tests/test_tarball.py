import subprocess
import unittest
from unittest.mock import patch, Mock, mock_open, call
import build  # needs to be imported before tarball due to dependencies
import tarball
import re


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
        tarball.giturl = ''
        tarball.url = url
        set_multi_version_backup = tarball.set_multi_version
        tarball.config.parse_config_versions = mock_gen(rv=version)
        n, _, v = tarball.name_and_version('', '', FileManager())
        tarball.set_multi_version = set_multi_version_backup
        self.assertEqual(name, n)
        self.assertEqual(version, v)
        if re.match("https?://github.com", url) != None:
            self.assertIsNotNone(tarball.giturl)
            self.assertNotEqual('', tarball.giturl, "giturl should not be empty")
            self.assertIsNotNone(
                    re.match("https://github.com/[^/]+/"+tarball.repo+".git",
                    tarball.giturl), "%s looks incorrect" % tarball.giturl)

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
        set_multi_version_backup = tarball.set_multi_version
        n, _, v = tarball.name_and_version('something', 'else', FileManager())
        tarball.set_multi_version = set_multi_version_backup
        self.assertEqual(v, 'else')
        self.assertEqual(n, 'something')

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
                         ('unzip -qq -d . zip/path', 'prefix-dir'))

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
                         ('unzip -qq -d . zip/path', 'prefix-dir'))

    def test_build_go_unzip(self):
        """
        Test build_go_unzip
        """
        build_unzip_backup = tarball.build_unzip
        tarball.build_unzip = lambda x: (f"unzip {x}", "/foo")
        tarball.multi_version = ["v1.0.0"]
        open_name = 'tarball.open'
        content = "v1.0.0\n"
        go_sources = ["v1.0.0.info", "v1.0.0.mod", "v1.0.0.zip"]
        tarball.buildpattern.sources["godep"] = []
        cmd, prefix = tarball.build_go_unzip("/foo/bar")
        tarball.build_unzip = build_unzip_backup
        self.assertEqual(len(cmd), 1)
        self.assertEqual(cmd[0], "unzip /foo/v1.0.0.zip")
        self.assertEqual(prefix, "/foo")
        self.assertEqual(tarball.buildpattern.sources["godep"], go_sources)
        tarball.buildpattern.sources["godep"] = []

    def test_build_un7z(self):
        """
        Test build_un7z
        """
        check_output_backup = subprocess.check_output
        tarball.subprocess.check_output = mock_gen(rv=UN7Z_OUT)
        tarball.build.base_path = '.'
        self.assertEqual(tarball.build_un7z('zip/path'),
                         ('7z x -o. zip/path', 'src'))

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


UNZIP_OUT = 'longhashstring\n'                             \
            '  Length      Date    Time    Name\n'         \
            '---------  ---------- -----   ----\n'         \
            '        0  04-03-2017 06:27   prefix-dir/\n'  \
            '      668  04-03-2017 06:27   prefix-dir/.gitignore\n'


GEM_OUT = '/path/to/dir/file1\n'                           \
          '/path/to/dir/file2\n'                           \
          '...\n'                                          \
          'Unpacked gem: \'/path/to/gem/test-prefix\''


UN7Z_OUT = '\n'                                                             \
           '7-Zip [64] 16.02 : Copyright (c) 1999-2016 Igor Pavlov : '      \
           '2016-05-21\n'                                                   \
           'p7zip Version 16.02 (locale=en_US.UTF-8,Utf16=on,HugeFiles=on,' \
           '64 bits,4 CPUs Intel(R) Core(TM) i5-6260U CPU @ 1.80GHz (406E3)'\
           ',ASM,AES-NI)\n'                                                 \
           '\n'                                                             \
           'Scanning the drive for archives:\n'                             \
           '1 file, 7933454 bytes (7748 KiB)\n'                             \
           '\n'                                                             \
           'Listing archive: converted_ogg_to_mp3-0.91.7z\n'                \
           '\n'                                                             \
           '--\n'                                                           \
           'Path = converted_ogg_to_mp3-0.91.7z\n'                          \
           'Type = 7z\n'                                                    \
           'Physical Size = 7933454\n'                                      \
           'Headers Size = 1526\n'                                          \
           'Method = LZMA2:23\n'                                            \
           'Solid = +\n'                                                    \
           'Blocks = 1\n'                                                   \
           '\n'                                                             \
           '   Date      Time    Attr         Size   Compressed  Name\n'    \
           '------------------- ----- ------------ ------------  '          \
           '------------------------\n'                                     \
           '2018-05-15 05:50:54 ....A        25095      7931928  '          \
           'src/activities/chronos/resource/sound/1.mp3\n'                  \
           '2018-05-15 05:50:54 ....A        23214               '          \
           'src/activities/chronos/resource/sound/2.mp3\n'                  \
           '2018-05-15 05:50:54 ....A        36589               '          \
           'src/activities/chronos/resource/sound/3.mp3\n'

# Run test_setup to generate tests
test_setup()


if __name__ == '__main__':
    unittest.main(buffer=True)
