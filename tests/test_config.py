import unittest
import config


# Input for tarball.detect_build_from_url method tests
# Structure: (url, build_pattern)
BUILD_PAT_URL = [
    ("https://cran.r-project.org/src/contrib/raster_3.0-12.tar.gz", "R"),
    ("https://ftp.osuosl.org/pub/cran/src/contrib/hexbin_1.28.5.tar.gz", "R"),
    ("http://pypi.debian.net/argparse/argparse-1.4.0.tar.gz", "distutils3"),
    ("https://pypi.python.org/packages/source/T/Tempita/Tempita-0.5.2.tar.gz", "distutils3"),
    ("https://cpan.metacpan.org/authors/id/T/TO/TODDR/IO-Tty-1.14.tar.gz", "cpan"),
    ("http://search.cpan.org/CPAN/authors/id/D/DS/DSKOLL/IO-stringy-2.111.tar.gz", "cpan"),
    ("https://pecl.php.net//get/lua-2.0.6.tgz", "phpize"),
]


def detect_build_test_generator(url, build_pattern):
    """Create test for tarball.detect_build_from_url method."""
    def generator(self):
        """Test template."""
        conf = config.Config("")
        conf.detect_build_from_url(url)
        self.assertEqual(build_pattern, conf.default_pattern)

    return generator


def create_dynamic_tests():
    # Create tests for config.detect_build_from_url method.
    for url, build_pattern in BUILD_PAT_URL:
        test_name = 'test_pat_{}'.format(url)
        test = detect_build_test_generator(url, build_pattern)
        setattr(TestConfig, test_name, test)


class TestConfig(unittest.TestCase):

    def test_set_build_pattern(self):
        """
        Test set_build_pattern with sufficient pattern strength
        """
        conf = config.Config("")
        conf.set_build_pattern("configure_ac", 1)
        self.assertEqual(conf.default_pattern, "configure_ac")
        self.assertEqual(conf.pattern_strength, 1)

    def test_set_build_pattern_low_strength(self):
        """
        Test set_build_pattern with low pattern strength, nothing in the module
        should change
        """
        conf = config.Config("")
        conf.pattern_strength = 2
        conf.set_build_pattern("configure_ac", 1)
        self.assertEqual(conf.default_pattern, "make")
        self.assertEqual(conf.pattern_strength, 2)

    def test_validate_extras_content_bad_glob(self):
        """
        Test validate_extras_content with more than one glob in a directory
        """
        conf = config.Config("")
        lines = ['/bad*path*/file']
        new_lines = conf.validate_extras_content(lines, 'bad_glob')
        self.assertEqual(len(new_lines), 0)

    def test_validate_extras_content_good_single_glob(self):
        """
        Test validate_extras_content with a single glob in a directory
        """
        conf = config.Config("")
        lines = ['/good*/file']
        new_lines = conf.validate_extras_content(lines, 'good_single_glob')
        self.assertEqual(new_lines, [lines[0].split('/')])

    def test_validate_extras_content_good_multi_glob(self):
        """
        Test validate_extras_content with a multiple valid globs
        """
        conf = config.Config("")
        lines = ['/path1', '/good*/glob*/file', '/path3']
        new_lines = conf.validate_extras_content(lines, 'good_multi_glob')
        self.assertEqual(new_lines, ['/path1', lines[1].split('/'), '/path3'])

# Create dynamic tests
create_dynamic_tests()

if __name__ == '__main__':
    unittest.main(buffer=True)
