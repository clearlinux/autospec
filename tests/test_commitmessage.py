import unittest
import unittest.mock as mock
import os
import tempfile
import build
import commitmessage
import config
import tarball


class TestCommitmessage(unittest.TestCase):

    def setUp(self):
        self.workingdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.workingdir.cleanup()

    def test_is_header(self):
        """
        Test is_header function with list of lines. First and last line, line
        followed by a line containing '---', and lines after a blank '' line
        should be recognized as headers. Last line recognized as header because
        it is a relevant ending point.
        """
        lines = ['line1',  # True
                 'line2',  # False
                 '',       # False
                 'line4',  # True
                 'line5',  # True
                 '---',    # False
                 'line7',  # False
                 'line8']  # True
        for idx, line in enumerate(lines):
            print(line, idx)
            if idx in [0, 3, 4, 7]:
                self.assertTrue(commitmessage.is_header(lines, idx))
            else:
                self.assertFalse(commitmessage.is_header(lines, idx))

    def test_find_in_line(self):
        """
        Trivially tests commitmessage.find_in_line(). Just makes sure results
        evaluate to the correct bool.
        """
        self.assertTrue(commitmessage.find_in_line(r'Version', 'AVersionInThisLine'))
        self.assertFalse(commitmessage.find_in_line(r'z', 'the quick brown fox jumps over the lady dog'))

    def test_process_NEWS(self):
        """
        Test process_NEWS() function with valid newsfile provided
        """
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'NEWS'), 'w') as newsfile:
                newsfile.write(GOOD_NEWS)
            # commitmessage returned will have an empty string as first and
            # last items
            expected_msg = [""] + GOOD_NEWS.split('\n')[3:13]
            expected_cvs = set()
            self.assertEqual(commitmessage.process_NEWS('NEWS', '0.0.0', '', '0.0.1', tmpd),
                             (expected_msg, expected_cvs))

    def test_process_NEWS_bad_news(self):
        """
        Test process_NEWS() function with irrelevant newsfile provided
        """
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'NEWS'), 'w') as newsfile:
                # make GOOD_NEWS irrelevant by replacing current version
                newsfile.write(GOOD_NEWS.replace('0.0.1', '0.0.0'))
            self.assertEqual(commitmessage.process_NEWS('NEWS', '0.0.0', '', '0.0.1', tmpd), ([], set()))

    def test_process_NEWS_good_cves(self):
        """
        Test process_NEWS() function with valid newsfile and CVEs
        """
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'NEWS'), 'w') as newsfile:
                # give GOOD_NEWS some CVEs
                newsfile.write(GOOD_NEWS.replace('change2.1', 'CVE-2-1')
                                        .replace('change2.2', 'CVE-2-2'))
            # commitmessage returned will have an empty string as first and
            # last items.
            # replace change2.* strings with CVE strings
            expected_msg = [""] + GOOD_NEWS.replace('change2.1', 'CVE-2-1')\
                                           .replace('change2.2', 'CVE-2-2')\
                                           .split('\n')[3:13]
            expected_cvs = set(['CVE-2-1', 'CVE-2-2'])
            self.assertEqual(commitmessage.process_NEWS('NEWS', '0.0.0', '', '0.0.1', tmpd),
                             (expected_msg, expected_cvs))

    def test_process_NEWS_long(self):
        """
        Test process_NEWS() function with valid newsfile provided, but relevant
        block is longer than 15 lines, causing it to be truncated.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            long_news = GOOD_NEWS.replace('text explaining change2.2',
                                          '1\n2\n3\n4\n5\n6\n7\n8\n9\n')
            with open(os.path.join(tmpd, 'NEWS'), 'w') as newsfile:
                newsfile.write(long_news)
            # commitmessage returned will have an empty string as first and
            # last items, extend the expected message with extra lines and
            # truncate message.
            expected_msg = [""] + GOOD_NEWS.split('\n')[3:11]
            expected_msg.extend(['1', '2', '3', '4', '5', '6', '7', '',
                                 '(NEWS truncated at 15 lines)', ''])
            expected_cvs = set()
            self.assertEqual(commitmessage.process_NEWS('NEWS', '0.0.0', '', '0.0.1', tmpd),
                             (expected_msg, expected_cvs))

    def test_guess_commit_message(self):
        """
        Test guess_commit_message() with mocked internal functions and both
        commitmessage information and cves available from newsfile.
        """
        conf = config.Config("")
        conf.old_version = "0.0.0"
        tcontent = tarball.Content("", "testball", "0.0.1", [], conf, self.workingdir.name)
        conf.content = tcontent
        process_NEWS_backup = commitmessage.process_NEWS

        def mock_process_NEWS(newsfile, old_version, name, version, download_path):
            return (['', 'commit', 'message', 'with', 'cves', ''],
                    set(['cve1', 'cve2']))

        commitmessage.process_NEWS = mock_process_NEWS
        open_name = 'util.open_auto'
        with mock.patch(open_name, create=True) as mock_open:
            mock_open.return_value = mock.MagicMock()
            conf.rewrite_config_opts = mock.Mock()
            commitmessage.guess_commit_message("", conf, tcontent)
            # reset mocks before asserting so a failure doesn't cascade to
            # other tests
            commitmessage.process_NEWS = process_NEWS_backup
            fh = mock_open.return_value.__enter__.return_value
            fh.write.assert_called_with(
                'testball: Autospec creation for update from version 0.0.0 to '
                'version 0.0.1\n\n\ncommit\nmessage\nwith\ncves\n\n\ncommit\n'
                'message\nwith\ncves\n\nCVEs fixed in this build:\ncve1\ncve2'
                '\n\n')

    def test_guess_commit_message_cve_config(self):
        """
        Test guess_commit_message() with mocked internal functions and both
        commitmessage information and cves available from newsfile. A cve is
        also available from config, which changes the first line of the commmit
        message.
        """
        conf = config.Config("")
        tcontent = tarball.Content("", "testball", "0.0.1", [], conf, self.workingdir.name)
        conf.content = tcontent
        process_NEWS_backup = commitmessage.process_NEWS

        def mock_process_NEWS(newsfile, old_version, name, version, download_path):
            return (['', 'commit', 'message', 'with', 'cves', ''],
                    set(['cve1', 'cve2']))

        commitmessage.process_NEWS = mock_process_NEWS
        conf.cves = set(['CVE-1234-5678'])
        conf.old_version = None  # Allow cve title to be set
        open_name = 'util.open_auto'
        with mock.patch(open_name, create=True) as mock_open:
            mock_open.return_value = mock.MagicMock()
            conf.rewrite_config_opts = mock.Mock()
            commitmessage.guess_commit_message("", conf, tcontent)
            # reset mocks before asserting so a failure doesn't cascade to
            # other tests
            commitmessage.process_NEWS = process_NEWS_backup
            fh = mock_open.return_value.__enter__.return_value
            fh.write.assert_called_with(
                'testball: Fix for CVE-1234-5678\n\n\ncommit\nmessage\nwith\n'
                'cves\n\n\ncommit\nmessage\nwith\ncves\n\nCVEs fixed in this '
                'build:\nCVE-1234-5678\ncve1\ncve2\n\n')

    def test_guess_commit_message_imported_key(self):
        """
        Test guess_commit_message() with mocked internal functions and both
        commitmessage information and cves available from newsfile. A cve is
        also available from config, which changes the first line of the commmit
        message. Additionally there is imported key info that will be displayed
        at the end of the message.
        """
        conf = config.Config("")
        tcontent = tarball.Content("", "testball", "0.0.1", [], conf, self.workingdir.name)
        conf.content = tcontent
        process_NEWS_backup = commitmessage.process_NEWS

        def mock_process_NEWS(newsfile, old_version, name, version, download_path):
            return (['', 'commit', 'message', 'with', 'cves', ''],
                    set(['cve1', 'cve2']))

        commitmessage.process_NEWS = mock_process_NEWS
        conf.cves = set(['CVE-1234-5678'])
        conf.old_version = None  # Allow cve title to be set
        open_name = 'util.open_auto'
        with mock.patch(open_name, create=True) as mock_open:
            mock_open.return_value = mock.MagicMock()
            conf.rewrite_config_opts = mock.Mock()
            commitmessage.guess_commit_message("keyinfo content", conf, tcontent)
            # reset mocks before asserting so a failure doesn't cascade to
            # other tests
            commitmessage.process_NEWS = process_NEWS_backup
            fh = mock_open.return_value.__enter__.return_value
            fh.write.assert_called_with(
                'testball: Fix for CVE-1234-5678\n\n\ncommit\nmessage\nwith\n'
                'cves\n\n\ncommit\nmessage\nwith\ncves\n\nCVEs fixed in this '
                'build:\nCVE-1234-5678\ncve1\ncve2\n\nKey imported:\nkeyinfo '
                'content\n')

    def test_scan_for_changes(self):
        """
        Tests scan_for_changes using temporary directories
        """
        conf = config.Config("")
        with tempfile.TemporaryDirectory() as tmpd:
            with open(os.path.join(tmpd, 'changelog.txt'), 'w') as newsfile:
                newsfile.write('new changelog file')

            with tempfile.TemporaryDirectory() as tmpd1:
                commitmessage.scan_for_changes(tmpd1, tmpd, conf.transforms)
                self.assertTrue(os.path.isfile(tmpd1 + '/ChangeLog'))


GOOD_NEWS = """
GOOD NEWS -- History of user-visible changes.

* Version 0.0.1

change1.1
change1.2

change2.1
text explaining change2.1
change2.2
text explaining change2.2

* Version 0.0.0

This better not show up
"""


if __name__ == '__main__':
    unittest.main(buffer=True)
