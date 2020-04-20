import copy
import os
import unittest
from unittest.mock import MagicMock, Mock, patch
import build
import config
import files
import tarball


# Stores all test cases for dynamic tests.
# In order to add more tests just add more elements to the lists provided below.

CONTENT_PECL = [
    'package.xml',
    'common-prefix/',
    'common-prefix/md5/',
    'common-prefix/md5/CMakeLists.txt',
    'common-prefix/md5/md5.h',
    'common-prefix/md5/md5hl.c',
    'common-prefix/md5/md5cmp.c',
    'common-prefix/md5/md5.c',
    'common-prefix/md5/Makefile.am',
    'common-prefix/md5/Makefile.in',
    'common-prefix/jerror.c',
    'common-prefix/sharedlib/',
    'common-prefix/sharedlib/CMakeLists.txt',
    'common-prefix/turbojpeg-mapfile',
    'common-prefix/jdpostct.c',
    'common-prefix/turbojpeg-jni.c',
]

CONTENT_PREFIX = [
    'common-prefix/',
    'common-prefix/md5/',
    'common-prefix/md5/CMakeLists.txt',
    'common-prefix/md5/md5.h',
    'common-prefix/md5/md5hl.c',
    'common-prefix/md5/md5cmp.c',
    'common-prefix/md5/md5.c',
    'common-prefix/md5/Makefile.am',
    'common-prefix/md5/Makefile.in',
    'common-prefix/jerror.c',
    'common-prefix/sharedlib/',
    'common-prefix/sharedlib/CMakeLists.txt',
    'common-prefix/turbojpeg-mapfile',
    'common-prefix/jdpostct.c',
    'common-prefix/turbojpeg-jni.c',
]

CONTENT_SUBDIR = [
    'dir1/',
    'dir1/md5/',
    'dir1/md5/CMakeLists.txt',
    'dir1/md5/md5.h',
    'dir1/md5/md5hl.c',
    'dir1/md5/md5cmp.c',
    'dir1/md5/md5.c',
    'dir1/md5/Makefile.am',
    'dir1/md5/Makefile.in',
    'dir2/',
    'dir2/jerror.c',
    'dir2/sharedlib/',
    'dir2/sharedlib/CMakeLists.txt',
    'dir2/turbojpeg-mapfile',
    'dir2/jdpostct.c',
    'dir2/turbojpeg-jni.c',
    'file.c'
]

# Input for tarball.Source class tests.
# Structure: (url, destination, path, fake-content, source_type, prefix, subddir)
SRC_CREATION = [
    ("https://example/src-PECL.tar", "", "/tmp/src-PECL.tar", CONTENT_PECL, "tar", "common-prefix", None),
    ("https://example/src-non-PECL.tar", "", "/tmp/src-non-PECL.tar", CONTENT_PECL, "tar", "", "src-non-PECL"),
    ("https://example/src-prefix.zip", "", "/tmp/src-prefix.zip", CONTENT_PREFIX, "zip", "common-prefix", None),
    ("https://example/src-subdir.zip", "", "/tmp/src-subdir.zip", CONTENT_SUBDIR, "zip", "", "src-subdir"),
    ("https://example/src-prefix.tar", "", "/tmp/src-prefix.tar", CONTENT_PREFIX, "tar", "common-prefix", None),
    ("https://example/src-subdir.tar", "", "/tmp/src-subdir.tar", CONTENT_SUBDIR, "tar", "", "src-subdir"),
    ("https://example/src-no-extractable.tar", ":", "/tmp/src-no-extractable.tar", None, None, None, None),
    ("https://example/go-src/list", "", "/tmp/list", None, "go", "", "list"),
]


class MockSrcFile():
    """Mock class for zipfile and tarfile."""

    def __init__(self, path, mode):
        self.name = path
        self.mode = mode

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, traceback):
        return False

    @classmethod
    def set_content(cls, content):
        # deep copy because the content is modified by Source
        cls.content = copy.deepcopy(content)

    def getnames(self):
        return self.content

    def namelist(self):
        return self.content


def source_test_generator(url, destination, path, content, src_type, prefix, subdir):
    """Create test for tarball.Source class using generator template."""

    @patch('tarball.tarfile.open', MockSrcFile)
    @patch('tarball.zipfile.ZipFile', MockSrcFile)
    @patch('tarball.tarfile.is_tarfile', Mock(return_value=True))
    @patch('tarball.zipfile.is_zipfile', Mock(return_value=True))
    def generator(self):
        """Test template."""
        # Set fake content
        MockSrcFile.set_content(content)
        if os.path.basename(path) in ['src-PECL.tar']:
            src = tarball.Source(url, destination, path, 'phpize')
        else:
            src = tarball.Source(url, destination, path)
        self.assertEqual(src.type, src_type)
        self.assertEqual(src.prefix, prefix, f"fail for: {url}")
        self.assertEqual(src.subdir, subdir)

    return generator


def name_and_version_test_generator(url, name, version, state):
    """Create test for tarball.name_and_version method."""
    def generator(self):
        """Test template."""
        conf = config.Config('/download/path')
        conf.parse_config_versions = Mock(return_value={})
        name_arg = ""
        version_arg = ""
        if state == 1 or state == 3:
            name_arg = f"state.{name}"
        if state == 2 or state == 3:
            version_arg = f"state.{version}"
        content = tarball.Content(url, name_arg, version_arg, [], conf, '/tmp')
        content.config = conf
        pkg = build.Build()
        mgr = files.FileManager(conf, pkg)
        content.name_and_version(mgr)
        name_cmp = name
        version_cmp = version
        if state == 1 or state == 3:
            name_cmp = name_arg
        if state == 2 or state == 3:
            version_cmp = version_arg
        self.assertEqual(name_cmp, content.name)
        self.assertEqual(version_cmp, content.version)
        # redo without args and verify giturl is set correctly
        content.name = ""
        content.version = ""
        content.name_and_version(Mock())
        if "github.com" in url:
            self.assertRegex(content.giturl, r"https://github.com/[^/]+/" + content.repo + ".git")

    return generator


def create_dynamic_tests():
    """Create dynamic tests based on content in lists and packageulrs file."""
    # Create tests for tarball.Source class.
    for url, dest, path, content, src_type, prefix, subdir in SRC_CREATION:
        test_name = 'test_src_{}'.format(url)
        test = source_test_generator(url, dest, path, content, src_type, prefix, subdir)
        setattr(TestTarball, test_name, test)

    # Create tests for tarball.name_and_version method.
    with open('tests/packageurls', 'r') as pkgurls:
        # add count to test if content state is used
        # 0 - no state
        # 1 - name only
        # 2 - version only
        # 3 - name and version
        c = 0
        for urlline in pkgurls.read().split('\n'):
            if not urlline or urlline.startswith('#'):
                continue
            (url, name, version) = urlline.split(',')
            test_name = 'test_name_ver_{}'.format(url)
            test = name_and_version_test_generator(url, name, version, c)
            setattr(TestTarball, test_name, test)
            c = (c + 1) % 4


class TestTarball(unittest.TestCase):
    """Main testing class for tarball.py.

    This class would contain all static tests and dynamic tests for tarball.py
    """

    def setUp(self):
        """Set up default values before start test."""
        # Set strenght to 0 so it can be updated during tests
        conf = config.Config('/download/path')
        self.content = tarball.Content('', '', '', [], conf, '/tmp')
        conf.content = self.content

    @patch('tarball.os.path.isfile', Mock(return_value=True))
    def test_set_gcov(self):
        """Test for tarball.set_gcov method."""
        # Set up input values
        self.content.name = 'test'
        self.content.set_gcov()
        self.assertEqual(self.content.gcov_file, 'test.gcov')

    def test_process_go_archives(self):
        """Test for tarball.process_go_archives method."""
        # Set up input values
        self.content.url = 'https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/list'
        self.content.multi_version = ['v0.3.1', 'v0.3.0', 'v0.2.0']
        go_archives = []
        go_archives_expected = [
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.1.info", ":",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.1.mod", ":",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.1.zip", "",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.0.info", ":",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.0.mod", ":",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.0.zip", "",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.2.0.info", ":",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.2.0.mod", ":",
            "https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.2.0.zip", "",
        ]
        self.content.process_go_archives(go_archives)
        self.assertEqual(go_archives, go_archives_expected)

    def test_process_multiver_archives(self):
        """Test for tarball.process_multiver_archives method."""
        # Set up input values
        main_src = tarball.Source('https://example/src-5.0.tar', ':', '/tmp/src.tar')
        multiver_archives = []
        config_versions = {
            '5.0': 'https://example/src-5.0.tar',
            '4.0': 'https://example/src-4.0.tar',
            '3.5': 'https://example/src-3.5.tar',
            '3.0': 'https://example/src-3.0.tar',
        }
        expected_multiver_archives = [
            'https://example/src-4.0.tar', '',
            'https://example/src-3.5.tar', '',
            'https://example/src-3.0.tar', '',
        ]
        # Set up a return value for parse_config_versions method
        attrs = {'parse_config_versions.return_value': config_versions}
        conf = MagicMock()
        conf.configure_mock(**attrs)
        self.content.config = conf
        self.content.process_multiver_archives(main_src, multiver_archives)
        self.assertEqual(multiver_archives, expected_multiver_archives)

    @patch('tarball.Source.set_prefix', Mock())
    @patch('tarball.Source.extract', Mock())
    def test_extract_sources(self):
        """Test for Content extract_sources method."""
        # Set up input values
        main_src = tarball.Source('https://example1.tar', '', '/tmp')
        arch1_src = tarball.Source('https://example2.tar', '', '/tmp')
        arch2_src = tarball.Source('https://example3.tar', ':', '/tmp')
        arch3_src = tarball.Source('https://example4.tar', '', '/tmp')
        archives_src = [arch1_src, arch2_src, arch3_src]
        self.content.extract_sources(main_src, archives_src)
        # Sources with destination=':' should not be extracted, so method
        # should be called only 3 times.
        self.assertEqual(tarball.Source.extract.call_count, 3)


# Create dynamic tests based on config file
create_dynamic_tests()

if __name__ == '__main__':
    unittest.main(buffer=True)
