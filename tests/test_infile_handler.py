import unittest

import infile_handler


class TestInputReader(unittest.TestCase):
    def test_sort_files_with_inc_and_bb(self):
        """
        Test that the sort_files key to the sorted function, returns the
        correct order when multiple bb files and an inc file are passed.
        The correct output should be the .inc file first, and then the .bb
        files.
        """
        files = ['catkin-runtime_0.6.19.bb', 'catkin.inc', 'catkin_0.6.19.bb']
        sorted_files = sorted(files, key=infile_handler.sort_files)

        expect = ['catkin.inc', 'catkin-runtime_0.6.19.bb', 'catkin_0.6.19.bb']
        self.assertEqual(expect, sorted_files)

    def test_parse_ext_bb(self):
        path = "cython_7.8.1.bb"

        ext = infile_handler.parse_ext(path)
        expect = "bb"

        self.assertEqual(expect, ext)

    def test_parse_ext_inc(self):
        path = "cython.inc"

        ext = infile_handler.parse_ext(path)
        expect = "inc"

        self.assertEqual(expect, ext)

    def test_parse_ext_none(self):
        path = "cython.deb"

        ext = infile_handler.parse_ext(path)
        expect = None

        self.assertEqual(expect, ext)


if __name__ == '__main__':
    unittest.main(buffer=True)
