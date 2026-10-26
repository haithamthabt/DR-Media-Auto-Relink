import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_auto_relink_core import workspace_relative, target_from_source


class PathMappingTests(unittest.TestCase):
    def test_windows_to_mac(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Studio Workspace"
            root.mkdir()
            result = target_from_source(
                r"D:\Studio Workspace\Projects\Project A\VO\intro.wav", root
            )
            self.assertEqual(result, root / "Projects" / "Project A" / "VO" / "intro.wav")

    def test_cross_project(self):
        self.assertEqual(
            workspace_relative(r"D:\Workspace\Projects\Project B\Videos\clip.mp4", "Workspace"),
            ("Projects", "Project B", "Videos", "clip.mp4"),
        )

    def test_shared_effects(self):
        self.assertEqual(
            workspace_relative(r"E:\Workspace\Effects\hit.wav", "Workspace"),
            ("Effects", "hit.wav"),
        )

    def test_missing_anchor(self):
        self.assertIsNone(workspace_relative(r"D:\Other\clip.mov", "Workspace"))

    def test_traversal_rejected(self):
        self.assertIsNone(workspace_relative(r"D:\Workspace\..\secret.wav", "Workspace"))

    def test_case_insensitive_anchor(self):
        self.assertEqual(
            workspace_relative(r"D:\WORKSPACE\Audio\voice.wav", "Workspace"),
            ("Audio", "voice.wav"),
        )


if __name__ == "__main__":
    unittest.main()
