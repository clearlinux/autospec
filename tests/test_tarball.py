import unittest
import unittest.mock
import build  # needs to be imported before tarball due to dependencies
import tarball


class TestTarballVersionName(unittest.TestCase):

    @unittest.mock.patch('tarball.build')
    def test_packageurls(self, mock_build):
        """
        Test the name and version detection from tarball url

        Reads in file packageurls and assumes each line to be of the format
        <url>,<expected name>,<expected version>

        Does not use self.assertEquals but appends to a list so all failures
        are reported instead of just the first one.
        """
        class FileManager():
            want_dev_split = False

        errors = []
        with open('tests/packageurls', 'r') as pkgurls:
            for urlline in pkgurls.read().split('\n'):
                if not urlline or urlline.startswith('#'):
                    continue

                tarball.name = ''
                tarball.version = ''
                (url, name, version) = urlline.split(',')
                tarball.name_and_version(url, '', '', FileManager())
                if tarball.name != name:
                    errors.append("name: '{}' != '{}' for url: {}"
                                  .format(tarball.name, name, url))

                if tarball.version != version:
                    errors.append("version: '{}' != '{}' for url: {}"
                                  .format(tarball.version, version, url))

                exp_rawname = tarball.name.replace('R-', '')
                if 'cran' in urlline and tarball.rawname != exp_rawname:
                    errors.append("rawname: '{}' != '{}' for url: {}"
                                  .format(tarball.rawname, exp_rawname, url))
        if errors:
            # raising an AssertionError signifies to unittest this is a failure
            # instead of an error. This prints a pretty list of all failures
            # that occurred.
            raise AssertionError('\n{}'.format('\n'.join(errors)))

    def test_version_configuration_override(self):
        """
        Test the version and name override from the command line
        """
        class FileManager():
            want_dev_split = False

        tarball.name_and_version('something', 'else', 'entirely', FileManager())
        self.assertEqual(tarball.version, 'entirely')
        self.assertEqual(tarball.name, 'else')

if __name__ == '__main__':
    unittest.main(buffer=True)
