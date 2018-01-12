import subprocess
import unittest


class TestGeneral(unittest.TestCase):

    def test_ConfigParser_regressions(self):
        """
        Make sure ConfigParser is always called with the required
        interpolation=None argument
        """
        grep_cmd = ["grep", "-re",
                    "ConfigParser(.*\(^interpolation=None\).*)",
                    "autospec"]
        try:
            output = subprocess.check_output(grep_cmd).decode('utf-8')
        except subprocess.CalledProcessError as e:
            output = e.output.decode('utf-8')

        self.assertEqual(output.strip(), "")


if __name__ == "__main__":
    unittest.main(buffer=True)
