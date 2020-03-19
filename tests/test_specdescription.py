import unittest
from unittest.mock import mock_open, patch
import config
import specdescription


class TestSpecdescription(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.open_name = 'specdescription.util.open_auto'

    def setUp(self):
        specdescription.default_description = "No detailed description available"
        specdescription.default_description_score = 0
        specdescription.default_summary = "No detailed summary available"
        specdescription.default_summary_score = 0
        specdescription.license.licenses = []

    def test_clean_license_string(self):
        """
        Test clean_license_string with a list of license strings
        """
        lics = [("ZPL-2.1", "ZPL-2.1"),
                ("Apache-2.0", "Apache-2.0"),
                ("GPL-2.0+", "GPL-2.0+"),
                ("GPL v2", "GPL-2"),
                ("GPL (>= 2)", "GPL-2.0+"),
                ("BSD 2-Clause Simplified", "BSD-2-Clause ")]

        for lic, exp in lics:
            self.assertEqual(specdescription.clean_license_string(lic), exp)

    def test_description_from_spec(self):
        """
        Test description_from_spec with summary and description present in
        spec file
        """
        content = "# this is a specfile\n"          \
                "License: GPL v2\n"                 \
                "Summary: This is a test package\n" \
                "\n"                                \
                "%description\n"                    \
                "Here is the description section\n" \
                "Look it continues until the\n"     \
                "line that begins with '%'\n"       \
                "\n"                                \
                "%donewithdesc\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.description_from_spec("filename", {}, [])

        self.assertEqual(specdescription.default_description,
                         "Here is the description section\n"
                         "Look it continues until the\n"
                         "line that begins with '%'\n\n")
        self.assertEqual(specdescription.default_summary,
                         "This is a test package\n")
        self.assertEqual(specdescription.default_description_score, 4)
        self.assertEqual(specdescription.default_summary_score, 4)
        self.assertEqual(specdescription.license.licenses, ["GPL-2"])

    def test_description_from_spec_no_info(self):
        """
        Test description_from_spec with no license, summary or description in
        spec file
        """
        content = "# this is a specfile without much in it\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.description_from_spec("filename", {}, [])

        self.assertEqual(specdescription.default_description,
                         "No detailed description available")
        self.assertEqual(specdescription.default_summary,
                         "No detailed summary available")
        self.assertEqual(specdescription.default_description_score, 0)
        self.assertEqual(specdescription.default_summary_score, 0)
        self.assertEqual(specdescription.license.licenses, [])

    def test_description_from_pkginfo(self):
        """
        Test description_from_pkginfo with information in pkg-info file
        """
        content = "# this is a package info file\n"  \
                "License: GPL v2\n"                  \
                "abstract: This is a test package\n" \
                "\n"                                 \
                "Description:\n"                     \
                "Here is the description section\n"  \
                "Look it continues until the\n"      \
                "line that contains a colon.\n"      \
                "\n"                                 \
                "donewithdesc:\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.description_from_pkginfo("filename", {}, [])

        self.assertEqual(specdescription.default_description,
                         "Here is the description section\n"
                         "Look it continues until the\n"
                         "line that contains a colon.\n\n")
        self.assertEqual(specdescription.default_summary,
                         "This is a test package")
        self.assertEqual(specdescription.default_description_score, 4)
        self.assertEqual(specdescription.default_summary_score, 4)
        self.assertEqual(specdescription.license.licenses, ["GPL-2"])

    def test_description_from_pkginfo_no_info(self):
        """
        Test description_from_pkginfo with no information in the pkginfo file
        """
        content = "# this is a pkginfo file without much in it\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.description_from_pkginfo("filename", {}, [])

        self.assertEqual(specdescription.default_description,
                         "No detailed description available")
        self.assertEqual(specdescription.default_summary,
                         "No detailed summary available")
        self.assertEqual(specdescription.default_description_score, 0)
        self.assertEqual(specdescription.default_summary_score, 0)
        self.assertEqual(specdescription.license.licenses, [])

    def test_summary_from_pkgconfig(self):
        """
        Test summary_from_pkgconfig with a summary present in the file. The
        file is named <package>.pc, increasing the summary score
        """
        content = "# this is a pkgconfig file\n" \
                  "Description: this is a test package\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.summary_from_pkgconfig("testpkg.pc", "testpkg")

        self.assertEqual(specdescription.default_summary,
                         "this is a test package\n")
        self.assertEqual(specdescription.default_summary_score, 3)

    def test_summary_from_pkgconfig_misnamed_file(self):
        """
        Test summary_from_pkgconfig with a summary present in the file. The
        file is named pkg.pc, which does not increase the summary score to 3
        """
        content = "# this is a pkgconfig file\n" \
                  "Description: this is a test package\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.summary_from_pkgconfig("pkg.pc", "testpkg")

        self.assertEqual(specdescription.default_summary,
                         "this is a test package\n")
        self.assertEqual(specdescription.default_summary_score, 2)

    def test_summary_from_pkgconfig_no_info(self):
        """
        Test summary_from_pkgconfig with no summary in the file.
        """
        content = "# this is a pkgconfig file without a description\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.summary_from_pkgconfig("pkg.pc", "testpkg")

        self.assertEqual(specdescription.default_summary,
                         "No detailed summary available")
        self.assertEqual(specdescription.default_summary_score, 0)

    def test_summary_from_R(self):
        """
        Test summary_from_R with DESCRIPTION file
        """
        content = "# this is a pkgconfig file\n" \
                  "Title: this is a test package\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.summary_from_R("DESCRIPTION")

        self.assertEqual(specdescription.default_summary,
                         "this is a test package\n")
        self.assertEqual(specdescription.default_summary_score, 3)

    def test_summary_from_R_no_info(self):
        """
        Test summary_from_R with no summary in the file
        """
        content = "# this is a DESCRIPTION file without a description\n"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.summary_from_pkgconfig("DESCRIPTION", "testpkg")

        self.assertEqual(specdescription.default_summary,
                         "No detailed summary available")
        self.assertEqual(specdescription.default_summary_score, 0)

    def test_skipline(self):
        """
        Test skipline for a list of lines
        """
        skips = ["Copyright",
                 "Free Software Foundation, Inc.",
                 "Copying and distribution of",
                 "are permitted in any",
                 "notice and this notice",
                 "README",
                 "-*-",
                 "blabla introduction"]

        for skip in skips:
            self.assertTrue(specdescription.skipline(skip))

        self.assertFalse(specdescription.skipline('nothing to skip here'))

    def test_description_from_readme(self):
        """
        Test description_from_readme with greater than 80 characters and a file
        name README, increasing the score
        """
        content = "This is a readme blah blah blah blah test test test\n" \
                  "this is the package but it is just a test package\n"   \
                  "ok?\n\n"                                               \
                  "This is a new paragraph, shouldn't be included"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.description_from_readme("README")

        self.assertEqual(specdescription.default_description,
                         "This is a readme blah blah blah blah test test test\n"
                         "this is the package but it is just a test package\n"
                         "ok?\n")
        self.assertEqual(specdescription.default_description_score, 1.5)

    def test_description_from_readme_with_skiplines(self):
        """
        Test description_from_readme with a skipline.
        """
        content = "This is a readme blah blah blah blah test test test\n"  \
                  "this is the package Copying and distribution of this\n" \
                  "ok? More characters needed to get over 80\n\n"          \
                  "This is a new paragraph, shouldn't be included"
        m_open = mock_open(read_data=content)
        with patch(self.open_name, m_open, create=True):
            specdescription.description_from_readme("Readme.md")

        self.assertEqual(specdescription.default_description,
                         "This is a readme blah blah blah blah test test test\n"
                         "ok? More characters needed to get over 80\n")
        self.assertEqual(specdescription.default_description_score, 1)


if __name__ == '__main__':
    unittest.main(buffer=True)
