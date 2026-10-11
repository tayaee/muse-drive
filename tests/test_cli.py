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

    @patch("muse_drive.cli.IS_WINDOWS", True)
    def test_default_target_windows(self):
        from muse_drive.cli import _default_target
        self.assertEqual(_default_target(), "M:")

    @patch("muse_drive.cli.IS_WINDOWS", False)
    def test_default_target_linux(self):
        from pathlib import Path
        from muse_drive.cli import _default_target
        self.assertEqual(_default_target(), str(Path.home() / "muse-workspace"))


if __name__ == "__main__":
    unittest.main()
