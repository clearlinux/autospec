import unittest
from libautospec import buildpattern


class TestBuildpattern(unittest.TestCase):

    def setUp(self):
        """
        Test setup method to reset the buildpattern module
        """
        buildpattern.default_pattern = "make"
        buildpattern.pattern_strength = 0
        buildpattern.sources = {
            "unit": [],
            "gcov": [],
            "tmpfile": [],
            "archive": []
        }
        buildpattern.source_index = {}
        buildpattern.archive_details = {}

    def test_set_build_pattern(self):
        """
        Test set_build_pattern with sufficient pattern strength
        """
        buildpattern.set_build_pattern("configure_ac", 1)
        self.assertEqual(buildpattern.default_pattern, "configure_ac")
        self.assertEqual(buildpattern.pattern_strength, 1)

    def test_set_build_pattern_low_strength(self):
        """
        Test set_build_pattern with low pattern strength, nothing in the module
        should change
        """
        buildpattern.pattern_strength = 2
        buildpattern.set_build_pattern("configure_ac", 1)
        self.assertEqual(buildpattern.default_pattern, "make")
        self.assertEqual(buildpattern.pattern_strength, 2)



if __name__ == '__main__':
    unittest.main(buffer=True)
