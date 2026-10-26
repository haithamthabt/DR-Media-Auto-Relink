import unittest
import tempfile
from pathlib import Path
from media_auto_relink_core import normalized_parts, workspace_relative, target_from_source, source_looks_like_path

class PathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Workspace"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_windows_path(self):
        self.assertEqual(target_from_source(r"D:\Workspace\Projects\A\VO\v.wav", self.root), self.root / "Projects/A/VO/v.wav")

    def test_posix_path(self):
        self.assertEqual(target_from_source("/old/Workspace/Effects/a.wav", self.root), self.root / "Effects/a.wav")

    def test_cross_project(self):
        self.assertEqual(workspace_relative(r"D:\Workspace\Projects\B\Videos\x.mp4", "Workspace"), ("Projects", "B", "Videos", "x.mp4"))

    def test_missing_anchor(self):
        self.assertIsNone(target_from_source("F:/Other/x.mp4", self.root))

    def test_case_insensitive_anchor(self):
        self.assertEqual(workspace_relative("C:/WORKSPACE/Music/m.wav", "Workspace"), ("Music", "m.wav"))

    def test_traversal_rejected(self):
        self.assertIsNone(target_from_source("C:/Workspace/../secret.mp4", self.root))

    def test_nested_traversal_rejected(self):
        self.assertIsNone(target_from_source("C:/Workspace/Projects/A/../../../escape.wav", self.root))

    def test_source_detection(self):
        for path in ["F:/Studio/x.mp4", r"C:\Studio\x.mp4", "/Volumes/Drive/a.wav", r"\\server\share\a.wav"]:
            self.assertTrue(source_looks_like_path(path), path)

    def test_relative_name_rejected(self):
        self.assertFalse(source_looks_like_path("music.wav"))

    def test_bad_workspace_name(self):
        self.assertIsNone(workspace_relative("C:/Workspace/x.mp4", "Work/space"))

    def test_empty_tail(self):
        self.assertIsNone(workspace_relative("C:/Workspace", "Workspace"))

    def test_unicode_filename(self):
        self.assertEqual(workspace_relative("C:/Workspace/VO/café.wav", "Workspace"), ("VO", "café.wav"))

if __name__ == "__main__":
    unittest.main()
