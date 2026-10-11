import unittest
from unittest.mock import MagicMock
from pathlib import Path
from muse_drive.client import MuseWorkspaceClient


class TestWorkspaceClient(unittest.TestCase):
    def test_list_dir_caching_and_stat_prepopulation(self):
        client = MuseWorkspaceClient(cookies_path=Path("/tmp/fake_cookies.txt"))
        mock_gateway = MagicMock()
        client._get_client = MagicMock(return_value=mock_gateway)

        mock_gateway.call_json.return_value = {
            "entries": [
                {"name": "file1.txt", "type": "file", "size": 100},
                {"name": "subfolder", "type": "dir", "size": 0},
            ]
        }

        # 1. First call to list_dir fetches from gateway
        res = client.list_dir("")
        self.assertEqual(len(res), 2)
        mock_gateway.call_json.assert_called_once_with("fs.list", body={"path": "workspace"})

        # 2. Subsequent stat on file1.txt should hit pre-populated cache without calling gateway again
        mock_gateway.call_json.reset_mock()
        stat_res = client.stat("file1.txt")
        self.assertIsNotNone(stat_res)
        self.assertEqual(stat_res.get("size"), 100)
        mock_gateway.call_json.assert_not_called()

        # 3. Subsequent list_dir should hit cache
        res2 = client.list_dir("")
        self.assertEqual(len(res2), 2)
        mock_gateway.call_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
