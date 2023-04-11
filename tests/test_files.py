import unittest
import config
import files
import tempfile
import os
from unittest.mock import call, MagicMock
import build
from files import FileManager


def mock_return(retval):
    """
    Simple mock method to set return value of a function
    """
    def mock_fn(_):
        return retval

    return mock_fn


class TestFiles(unittest.TestCase):

    def setUp(self):
        conf = config.Config("")
        pkg = build.Build()
        self.fm = FileManager(conf, pkg)

    def test_banned_path(self):
        """
        Test banned paths are detected
        """
        bad_paths = ["/etc/one",
                     "/opt/two",
                     "/V3/opt/two",
                     "/V4/opt/two",
                     "/usr/etc/three",
                     "/usr/local/four",
                     "/usr/src/five",
                     "/var/six"]
        for path in bad_paths:
            self.assertTrue(FileManager.banned_path(path))

    def test_push_package_file(self):
        """
        Test push_package_file with no package name specified (package name
        should default to 'main'
        """
        self.assertFalse(self.fm.newfiles_printed)
        self.fm.push_package_file('test-fn')
        self.assertEqual(self.fm.packages['main'], set(['test-fn']))
        self.assertTrue(self.fm.newfiles_printed)

    def test_push_package_file_banned(self):
        """
        Test push_package_file with banned filename'
        """
        self.assertFalse(self.fm.newfiles_printed)
        self.fm.push_package_file('/etc/test-fn')
        self.fm.push_package_file('/V3/etc/test-fn')
        self.fm.push_package_file('/V4/etc/test-fn')
        self.assertTrue(self.fm.has_banned)
        self.assertFalse(self.fm.newfiles_printed)

    def test_push_package_file_dev(self):
        """
        Test push_package_file with dev package specified
        """
        self.fm.push_package_file('test-fn', 'dev')
        self.assertEqual(self.fm.packages['dev'], set(['test-fn']))
        self.assertTrue(self.fm.newfiles_printed)

    def test_compat_exclude_keep_file(self):
        """
        Test compat_exclude with a file that shouldn't be excluded.
        """
        self.fm.config.config_opts['compat'] = True
        self.assertFalse(self.fm.compat_exclude('/usr/lib64/libfoo.so.1'))

    def test_compat_exclude_exclude_file(self):
        """
        Test compat_exclude with a file that should be excluded.
        """
        self.fm.config.config_opts['compat'] = True
        self.assertTrue(self.fm.compat_exclude('/usr/lib64/libfoo.so'))
        self.assertTrue(self.fm.compat_exclude('/V3/usr/lib64/libfoo.so'))
        self.assertTrue(self.fm.compat_exclude('/V4/usr/lib64/libfoo.so'))

    def test_compat_exclude_not_compat_mode(self):
        """
        Test compat_exclude with a file that should be excluded but isn't
        because the package isn't being run in compat mode.
        """
        self.fm.config.config_opts['compat'] = False
        self.assertFalse(self.fm.compat_exclude('/usr/lib64/libfoo.so'))
        self.assertFalse(self.fm.compat_exclude('/V3/usr/lib64/libfoo.so'))
        self.assertFalse(self.fm.compat_exclude('/V4/usr/lib64/libfoo.so'))

    def test_file_pat_match(self):
        """
        Test file_pat_match with good match and no replacement or prefix
        specified.
        """
        self.fm.push_package_file = MagicMock()
        self.assertTrue(self.fm.file_pat_match('/test-fn', r'^/test-fn', 'main'))
        self.fm.push_package_file.assert_called_with('/test-fn', 'main')
        self.assertTrue(self.fm.file_pat_match('/V3/test-fn', r'^/test-fn', 'main'))
        self.fm.push_package_file.assert_called_with('/V3/test-fn', 'main')
        self.assertTrue(self.fm.file_pat_match('/V4/test-fn', r'^/test-fn', 'main'))
        self.fm.push_package_file.assert_called_with('/V4/test-fn', 'main')

    def test_file_pat_match_exclude(self):
        """
        Test file_pat_match with good match and filename in excludes list.
        """
        self.fm.push_package_file = MagicMock()
        self.fm.excludes.append('/test-fn')
        self.assertTrue(self.fm.file_pat_match('/test-fn', r'^/test-fn', 'main'))
        self.assertTrue(self.fm.file_pat_match('/V3/test-fn', r'^/test-fn', 'main'))
        self.assertTrue(self.fm.file_pat_match('/V4/test-fn', r'^/test-fn', 'main'))
        self.fm.push_package_file.assert_not_called()

    def test_file_pat_match_replacement(self):
        """
        Test file_pat_match with replacement provided
        """
        self.fm.push_package_file = MagicMock()
        self.assertTrue(self.fm.file_pat_match('/test-fn', r'^/test-fn', 'main', '/testfn'))
        self.fm.push_package_file.assert_called_with('/testfn', 'main')
        self.assertTrue(self.fm.file_pat_match('/V3/test-fn', r'/test-fn', 'main', '/testfn'))
        self.fm.push_package_file.assert_called_with('/V3/testfn', 'main')
        self.assertTrue(self.fm.file_pat_match('/V4/test-fn', r'/test-fn', 'main', '/testfn'))
        self.fm.push_package_file.assert_called_with('/V4/testfn', 'main')

    def test_file_pat_match_replacement_no_glob(self):
        """
        Test file_pat_match with replacement provided but no glob set
        """
        self.fm.push_package_file = MagicMock()
        self.fm.config.config_opts['no_glob'] = True
        self.assertTrue(self.fm.file_pat_match('/test-fn', r'^/test-fn', 'main', '/testfn'))
        self.fm.push_package_file.assert_called_with('/test-fn', 'main')
        self.assertTrue(self.fm.file_pat_match('/V3/test-fn', r'^/test-fn', 'main', '/testfn'))
        self.fm.push_package_file.assert_called_with('/V3/test-fn', 'main')
        self.assertTrue(self.fm.file_pat_match('/V4/test-fn', r'^/test-fn', 'main', '/testfn'))
        self.fm.push_package_file.assert_called_with('/V4/test-fn', 'main')

    def test_file_pat_match_no_match(self):
        """
        Test file_pat_match with no match
        """
        self.fm.push_package_file = MagicMock()
        self.assertFalse(self.fm.file_pat_match('test-fn', r'testfn', 'main'))
        self.fm.push_package_file.assert_not_called()

    def test_file_is_locale(self):
        """
        Test file_is_locale with locale filename not present in locale list
        """
        self.assertEqual(self.fm.locales, [])
        self.assertTrue(self.fm.file_is_locale('/usr/share/locale/a/loc.mo'))
        self.assertEqual(self.fm.locales, ['loc'])

    def test_file_is_locale_non_locale(self):
        """
        Test file_is_locale with non-locale filename
        """
        self.assertFalse(self.fm.file_is_locale('test-fn'))
        self.assertEqual(self.fm.locales, [])

    def test_file_is_locale_present(self):
        """
        Test file_is_locale with locale present in locale list
        """
        self.fm.locales.append('loc')
        self.assertEqual(self.fm.locales, ['loc'])
        self.assertTrue(self.fm.file_is_locale('/usr/share/locale/a/loc.mo'))
        self.assertEqual(self.fm.locales, ['loc'])

    def test_push_file_autostart(self):
        """
        Test push_file to autostart package, this excludes the file.
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        autostart = '/usr/lib/systemd/system/some.target.wants/some'
        self.fm.push_file(autostart, '')
        calls = [call(autostart, 'autostart'), call('%exclude ' + autostart, 'services')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_file_custom_extras(self):
        """
        Test push_file to a custom extras package
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.file_maps = {'foobar-extras': {'files': ["/foobar"]}}
        self.fm.push_file('/foobar', '')
        calls = [call('/foobar', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V3/foobar', '')
        calls = [call('/V3/foobar', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V4/foobar', '')
        calls = [call('/V4/foobar', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_package_file_glob_empty(self):
        """
        Test push_file with glob extras empty match
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.file_maps = {'foobar-extras': {'files': [['', 'leftglob*rightglob']]}}
        self.fm.push_file('/leftglobrightglob', '')
        calls = [call('/leftglob*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V3/leftglobrightglob', '')
        calls = [call('/V3/leftglob*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V4/leftglobrightglob', '')
        calls = [call('/V4/leftglob*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_package_file_glob_left_match(self):
        """
        Test push_file with glob extras left content matching
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.file_maps = {'foobar-extras': {'files': [['', 'leftglob*']]}}
        self.fm.push_file('/leftglobrightglob', '')
        calls = [call('/leftglob*', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V3/leftglobrightglob', '')
        calls = [call('/V3/leftglob*', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V4/leftglobrightglob', '')
        calls = [call('/V4/leftglob*', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_package_file_glob_right_match(self):
        """
        Test push_file with glob extras right content matching
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.file_maps = {'foobar-extras': {'files': [['', '*rightglob']]}}
        self.fm.push_file('/leftglobrightglob', '')
        calls = [call('/*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V3/leftglobrightglob', '')
        calls = [call('/V3/*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V4/leftglobrightglob', '')
        calls = [call('/V4/*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_package_file_glob_leftright_match(self):
        """
        Test push_file with glob extras leftright content matching
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.file_maps = {'foobar-extras': {'files': [['', 'leftglob*rightglob']]}}
        self.fm.push_file('/leftglobstuffrightglob', '')
        calls = [call('/leftglob*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V3/leftglobstuffrightglob', '')
        calls = [call('/V3/leftglob*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V4/leftglobstuffrightglob', '')
        calls = [call('/V4/leftglob*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_package_file_glob_multi_match(self):
        """
        Test push_file with multiple globs extras content matching
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.file_maps = {'foobar-extras': {'files': [['', 'leftglob*', '*rightglob']]}}
        self.fm.push_file('/leftglobstuff/stuffrightglob', '')
        calls = [call('/leftglob*/*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V3/leftglobstuff/stuffrightglob', '')
        calls = [call('/V3/leftglob*/*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)
        self.fm.push_file('/V4/leftglobstuff/stuffrightglob', '')
        calls = [call('/V4/leftglob*/*rightglob', 'foobar-extras')]
        self.fm.push_package_file.assert_has_calls(calls)

    def test_push_file_setuid(self):
        """
        Test push_file with fname in setuid list
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.setuid.append('test')
        self.fm.push_file('test', '')
        calls = [call('%attr(4755, root, root) test', 'setuid')]
        self.fm.push_package_file.assert_has_calls(calls)


    def test_push_file_match(self):
        """
        Test push_file with match in pattern list
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.push_file('/usr/bin/test', '')
        self.fm.push_package_file.assert_called_once_with('/usr/bin/test', 'bin')
        self.fm.push_file('/V3/usr/bin/test', '')
        self.fm.push_package_file.assert_has_calls([call('/V3/usr/bin/test', 'bin')])
        self.fm.push_file('/V4/usr/bin/test', '')
        self.fm.push_package_file.assert_has_calls([call('/V4/usr/bin/test', 'bin')])

    def test_push_file_match_pkg_name_dependency(self):
        """
        Test push_file with match in the list on the single item that is
        dependent on the pkg_name.
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.push_file('/usr/share/doc/testball/', 'testball')
        self.fm.push_package_file.assert_called_once_with('/usr/share/doc/testball/*', 'doc')
        self.fm.push_file('/V3/usr/share/doc/testball/', 'testball')
        self.fm.push_package_file.assert_has_calls([call('/V3/usr/share/doc/testball/*', 'doc')])
        self.fm.push_file('/V4/usr/share/doc/testball/', 'testball')
        self.fm.push_package_file.assert_has_calls([call('/V4/usr/share/doc/testball/*', 'doc')])

    def test_push_file_no_match(self):
        """
        Test push_file with no pattern match on the file name. Should just push
        the unmodified filename once.
        """
        self.fm.file_is_locale = MagicMock(return_value=False)
        self.fm.push_package_file = MagicMock()
        self.fm.push_file('doesntmatcha thing', '')
        self.fm.push_package_file.assert_called_once_with('doesntmatcha thing')

    def test_remove_file(self):
        """
        Test remove_file with filename in files list and main package
        """
        self.fm.files.add('test')
        self.fm.packages['main'] = ['test']
        self.assertIn('test', self.fm.files)
        self.assertNotIn('test', self.fm.files_blacklist)
        self.assertIn('test', self.fm.packages['main'])
        self.fm.remove_file('test')
        self.assertNotIn('test', self.fm.files)
        self.assertNotIn('test', self.fm.packages['main'])
        self.assertIn('test', self.fm.files_blacklist)

    def test_remove_file_not_present(self):
        """
        Test remove_file with filename not in files list.
        """
        self.assertNotIn('test', self.fm.files)
        self.assertNotIn('test', self.fm.files_blacklist)
        self.fm.remove_file('test')
        self.assertNotIn('test', self.fm.files)
        self.assertNotIn('test', self.fm.files_blacklist)

    def test_clean_directories(self):
        """
        Test clean_directories with a directory in the list
        """
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, "directory"))
            with open(os.path.join(tmpd, "file1"), "w") as f:
                f.write(" ")

            with open(os.path.join(tmpd, "file2"), "w") as f:
                f.write(" ")

            self.fm.packages["main"] = set()
            self.fm.packages["main"].add("/directory")
            self.fm.packages["main"].add("/file1")
            self.fm.packages["main"].add("/file2")
            self.fm.clean_directories(tmpd)
            self.assertEqual(self.fm.packages["main"], set(["/file1", "/file2"]))


    def test_clean_directories_with_dir(self):
        """
        Test clean_directories with a %dir directory in the list. This should
        remain.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, "directory"))
            with open(os.path.join(tmpd, "file1"), "w") as f:
                f.write(" ")

            with open(os.path.join(tmpd, "file2"), "w") as f:
                f.write(" ")

            self.fm.packages["main"] = set()
            self.fm.packages["main"].add("%dir /directory")
            self.fm.packages["main"].add("/file1")
            self.fm.packages["main"].add("/file2")
            self.fm.clean_directories(tmpd)
            self.assertEqual(self.fm.packages["main"],
                             set(["%dir /directory", "/file1", "/file2"]))


    def test_clean_directories_with_symlink_to_dir(self):
        """
        Test clean_directories with a symlink to a directory in the list. The
        symlink should remain, but the directory should be cleaned.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            dirname = os.path.join(tmpd, "directory")
            linkname = os.path.join(tmpd, "symlink")
            os.mkdir(dirname)
            os.symlink(dirname, linkname)
            self.fm.packages["main"] = set()
            self.fm.packages["main"].add("/directory")
            self.fm.packages["main"].add("/symlink")
            self.fm.clean_directories(tmpd)
            self.assertEqual(self.fm.packages["main"],
                             set(["/symlink"]))


    def test_clean_directories_with_symlink_to_explicit_dir(self):
        """
        Test clean_directories with a symlink to a %dir directory in the list.
        The symlink and directory should both remain.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            dirname = os.path.join(tmpd, "directory")
            linkname = os.path.join(tmpd, "symlink")
            os.mkdir(dirname)
            os.symlink(dirname, linkname)
            self.fm.packages["main"] = set()
            self.fm.packages["main"].add("%dir /directory")
            self.fm.packages["main"].add("/symlink")
            self.fm.clean_directories(tmpd)
            self.assertEqual(self.fm.packages["main"],
                             set(["%dir /directory", "/symlink"]))


    def test_clean_directories_with_doc(self):
        """
        Test clean_directories with a %doc directive in the list. This should
        remain.
        """
        with tempfile.TemporaryDirectory() as tmpd:
            os.mkdir(os.path.join(tmpd, "directory"))
            with open(os.path.join(tmpd, "file1"), "w") as f:
                f.write(" ")

            with open(os.path.join(tmpd, "file2"), "w") as f:
                f.write(" ")

            self.fm.packages["main"] = set()
            self.fm.packages["main"].add("%doc /directory")
            self.fm.packages["main"].add("/file1")
            self.fm.packages["main"].add("/file2")
            self.fm.clean_directories(tmpd)
            self.assertEqual(self.fm.packages["main"],
                             set(["%doc /directory", "/file1", "/file2"]))


if __name__ == '__main__':
    unittest.main(buffer=True)
