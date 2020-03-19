import unittest

import config
import infile_update_spec
import specfiles


class TestUpdateSpecfile(unittest.TestCase):
    def setUp(self):
        # url, version, name, release
        url = "http://www.testpkg.com/testpkg/pkg-1.0.tar.gz"
        self.specfile = specfiles.Specfile(url, '1.1.1', 'test_pkg', '1', config.Config())

        self.bb_dict = {
            "DEPENDS": "ncurses gettext-native",
            "LICENSE": "new"
        }

    def test_update_summary_if_bb_summary(self):
        """
        Test that if a bitbake file has a summary variable it overwrites
        the specfile - even if there is a description too.
        """
        self.specfile.default_sum = "No detailed summary available"
        self.bb_dict["SUMMARY"] = "Vi IMproved - enhanced vi editor"
        self.bb_dict["DESCRIPTION"] = "Super awesome VIM description"
        infile_update_spec.update_summary(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.default_sum,
                         "Vi IMproved - enhanced vi editor")

    def test_update_summary_if_not_default(self):
        """
        Test that if a bitbake file does NOT have a summary variable, but
        instead has a description variable, that overwrites the specfile"
        """
        self.specfile.default_sum = "No detailed summary available"
        self.bb_dict["DESCRIPTION"] = "Super awesome VIM description"
        infile_update_spec.update_summary(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.default_sum,
                         "Super awesome VIM description")

    def test_update_summary_if_no_bb_summary_or_description(self):
        """
        Test that if a bitbake file has neither a summary or description
        that the default specfile summary is written
        """
        self.specfile.default_sum = "No detailed summary available"
        infile_update_spec.update_summary(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.default_sum,
                         "No detailed summary available")

    def test_update_license_if_not_in_licenses_list(self):
        """
        Test that if a license is scraped from the bb file, and not in the
        licenses specfile list, that it should be added to the list.
        """
        self.specfile.licenses = ['random', 'license']
        infile_update_spec.update_licenses(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.licenses, ['random', 'license', 'new'])

    def test_update_license_if_in_license_list_case(self):
        """
        Test that if a license is already in the specfile licenses list, not
        case sensitive, then it should not be duplicated.
        """
        self.specfile.licenses = ['random', 'New']
        infile_update_spec.update_licenses(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.licenses, ['random', 'New'])

    def test_update_build_deps_append_normal(self):
        """
        Test that if a set if multiple items are scraped from the bb file, and
        they are not already in the specfile, they will be added to the set of
        buildreqs. If the bb depends ends in '-native' that should be removed
        as well.
        """
        self.specfile.buildreqs = {'gmp-dev', 'lua-dev'}
        infile_update_spec.update_build_deps(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.buildreqs, {'gmp-dev', 'lua-dev',
                                                   'ncurses', 'gettext'})

    def test_update_build_deps_append_duplicates(self):
        """
        Test that if a set if multiple items are scraped from the bb file, and
        they are already in the specfile, the resulting set with be the union
        of set 1 and set 2.
        """
        self.specfile.buildreqs = {'gmp-dev', 'ncurses'}
        infile_update_spec.update_build_deps(self.bb_dict, self.specfile)
        self.assertEqual(self.specfile.buildreqs, {'gmp-dev', 'ncurses',
                                                   'gettext'})


if __name__ == '__main__':
    unittest.main(buffer=True)
