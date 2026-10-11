import unittest
from unittest.mock import MagicMock
from muse_drive.dav_provider import _clean_dav_path, MuseDAVProvider, MuseDirectoryResource, MuseFileResource


class TestDavProvider(unittest.TestCase):
    def test_clean_dav_path(self):
        self.assertEqual(_clean_dav_path("/"), "")
        self.assertEqual(_clean_dav_path(""), "")
        self.assertEqual(_clean_dav_path("/DavWWWRoot"), "")
        self.assertEqual(_clean_dav_path("/DavWWWRoot/"), "")
        self.assertEqual(_clean_dav_path("DavWWWRoot"), "")
        self.assertEqual(_clean_dav_path("/DavWWWRoot/folder1"), "folder1")
        self.assertEqual(_clean_dav_path("/DavWWWRoot/folder1/file.txt"), "folder1/file.txt")
        self.assertEqual(_clean_dav_path("/folder1/file.txt"), "folder1/file.txt")

    def test_dav_provider_davwwwroot_resolution(self):
        mock_client = MagicMock()
        mock_client.list_dir.return_value = [
            {"name": "test_folder", "type": "directory"},
            {"name": "notes.txt", "type": "file", "size": 123},
        ]
        mock_client.stat.side_effect = lambda path: (
            {"name": "test_folder", "type": "directory"} if path == "test_folder"
            else {"name": "notes.txt", "type": "file", "size": 123} if path == "notes.txt"
            else None
        )

        provider = MuseDAVProvider(mock_client)
        environ = {"wsgidav.provider": provider}

        # 1. Root and DavWWWRoot root
        root_res = provider.get_resource_inst("/", environ)
        self.assertIsInstance(root_res, MuseDirectoryResource)
        self.assertEqual(root_res.rel_path, "")

        dav_root_res = provider.get_resource_inst("/DavWWWRoot", environ)
        self.assertIsInstance(dav_root_res, MuseDirectoryResource)
        self.assertEqual(dav_root_res.rel_path, "")

        # 2. List members of /DavWWWRoot
        members = dav_root_res.get_member_list()
        self.assertEqual(len(members), 2)
        names = [m.name for m in members]
        self.assertIn("test_folder", names)
        self.assertIn("notes.txt", names)

        # 3. Access member via DavWWWRoot path
        file_res = provider.get_resource_inst("/DavWWWRoot/notes.txt", environ)
        self.assertIsInstance(file_res, MuseFileResource)
        self.assertEqual(file_res.rel_path, "notes.txt")
        self.assertEqual(file_res.get_content_length(), 123)


if __name__ == "__main__":
    unittest.main()
