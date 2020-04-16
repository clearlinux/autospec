import unittest
import config


# Input for tarball.detect_build_from_url method tests
# Structure: (url, build_pattern)
BUILD_PAT_URL = [
    ("https://cran.r-project.org/src/contrib/raster_3.0-12.tar.gz", "R"),
    ("http://pypi.debian.net/argparse/argparse-1.4.0.tar.gz", "distutils3"),
    ("https://pypi.python.org/packages/source/T/Tempita/Tempita-0.5.2.tar.gz", "distutils3"),
    ("https://cpan.metacpan.org/authors/id/T/TO/TODDR/IO-Tty-1.14.tar.gz", "cpan"),
    ("http://search.cpan.org/CPAN/authors/id/D/DS/DSKOLL/IO-stringy-2.111.tar.gz", "cpan"),
    ("https://proxy.golang.org/github.com/spf13/pflag/@v/list", "godep"),
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

# Create dynamic tests
create_dynamic_tests()

if __name__ == '__main__':
    unittest.main(buffer=True)
