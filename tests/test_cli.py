import unittest
from unittest.mock import patch, MagicMock
from muse_drive.cli import _set_windows_drive_label


class TestCli(unittest.TestCase):
    @patch("muse_drive.cli.IS_WINDOWS", True)
    @patch("subprocess.run")
    def test_set_windows_drive_label_executes_thread(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        # Should not throw NameError for threading or anything else
        _set_windows_drive_label("M:", "Muse Drive", host="127.0.0.1", port=18846)


if __name__ == "__main__":
    unittest.main()
