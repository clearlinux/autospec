import subprocess
import unittest
from unittest.mock import patch, Mock, mock_open, call
import build  # needs to be imported before tarball due to dependencies
import tarball
import re


src_content = None

class FileManager():
    want_dev_split = False


class MockSrcFile:
    def __init__(self, path, mode):
        self.name = path
        self.mode = mode
        self.content = src_content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, traceback):
        return False

    def getnames(self):
        return self.content


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
        Test build_untar using an array to test multiple cases.
        Case 1: Existent tar, with content and common dir.
        Case 2: Non existent tar.
        Case 3: Existent tar, but empty.
        Case 4: Existent tar, with content and non common dir.
        Case 5: Existent tar, with content, common dir with leading dot (./)
        Case 6: Existent tar, with content, one element only with (./)
        Case 7: Existent tar, with one single file
        """

        tests = (
                ({'is_tar': True, 'content':['dir/','dir/file1']}, ('tar --directory=. -xf path/tar_file-v1.tar', 'dir')),
                ({'is_tar': False, 'content':[]}, (False, False)),
                ({'is_tar': True, 'content':[]}, (False, False)),
                ({'is_tar': True, 'content':['dir/','dir1/file1']}, ('tar --directory=. --one-top-level=tar_file-v1 -xf path/tar_file-v1.tar', '')),
                ({'is_tar': True, 'content':['./dir/','./dir/file1']}, ('tar --directory=. -xf path/tar_file-v1.tar', 'dir')),
                ({'is_tar': True, 'content':['./','./dir/','./dir1/file1']}, ('tar --directory=. --one-top-level=tar_file-v1 -xf path/tar_file-v1.tar', '')),
                ({'is_tar': True, 'content':['file1']}, ('tar --directory=. --one-top-level=tar_file-v1 -xf path/tar_file-v1.tar', None)),
                )
        global src_content

        for input, expected in tests:
            try:
                tarball.print_fatal = mock_gen(rv=None)
                tarball.tarfile.is_tarfile = mock_gen(rv=input['is_tar'])
                src_content = input['content']
                tarball.build.base_path = '.'
                tarball.tarfile.open = MockSrcFile
                actual = tarball.build_untar('path/tar_file-v1.tar')
            except:
                actual = (False, False)
            finally:
                self.assertEqual(actual, expected)

    def test_build_unzip(self):
        """
        Test build_unzip using an array to test multiple cases.
        Case 1: Existent zip, with content and common dir.
        Case 2: Non existen zip.
        Case 3: Existent zip, but empty.
        Case 4: Existent zip, with content and non common dir.
        """

        class MockZipFile:
            def __init__(self, path, mode):
                self.name = path
                self.mode = mode
                self.content = zip_content

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, traceback):
                return False

            def namelist(self):
                return self.content

        tests = (
                ({'is_zip':True, 'content':['dir/','dir/file1']}, ('unzip -qq -d . path/zip_file-v1.zip', 'dir')),
                ({'is_zip':False, 'content':[]}, (False, False)),
                ({'is_zip':True, 'content':[]}, (False, False)),
                ({'is_zip':True, 'content':['dir/','dir1/file1', ]}, ('unzip -qq -d ./zip_file-v1 path/zip_file-v1.zip', '')),
                )

        for input, expected in tests:
            try:
                tarball.print_fatal = mock_gen(rv=None)
                tarball.zipfile.is_zipfile = mock_gen(rv=input['is_zip'])
                zip_content = input['content']
                tarball.build.base_path = '.'
                tarball.zipfile.ZipFile = MockZipFile
                actual = tarball.build_unzip('path/zip_file-v1.zip')
            except:
                actual = (False, False)
            finally:
                self.assertEqual(actual, expected)

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

    def test_find_extract(self):
        """
        Test find_extract with the three supported filetypes
        (*.zip, *.tar*)
        """
        build_unzip_backup = tarball.build_unzip
        build_untar_backup = tarball.build_untar

        tarball.build_unzip = Mock(return_value=('', ''))
        tarball.build_untar = Mock(return_value=('', ''))

        tarball.find_extract('path/to/tar', 'test.zip')
        tarball.find_extract('path/to/tar', 'test.tar.gz')

        tarball.build_unzip.assert_called_once()
        tarball.build_untar.assert_called_once()

        tarball.build_unzip = build_unzip_backup
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


# Run test_setup to generate tests
test_setup()


if __name__ == '__main__':
    unittest.main(buffer=True)
