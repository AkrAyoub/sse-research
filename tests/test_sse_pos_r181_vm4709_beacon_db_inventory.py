"""R181 read-only bounded Beacon inventory regression tests."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r181_vm4709_beacon_db_inventory as m

class BeaconInventoryTests(unittest.TestCase):
    def test_nested_real_file_metadata_only_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)/"beacon"
            root.mkdir()
            child=root/"beacon"
            child.mkdir()
            (child/"store.db").write_bytes(b"PRIVATE_STATE_DO_NOT_EXPOSE")
            with patch.object(m,"ROOT",root):
                report=m.inventory(root)
            self.assertEqual(report["regularFiles"],1)
            self.assertEqual(report["entryCount"],2)
            self.assertFalse(report["beaconDataAppearsEmpty"])
            self.assertFalse(report["stateModified"])
            self.assertFalse(report["jwtOrBeaconFileContentsRead"])
            self.assertNotIn("PRIVATE_STATE_DO_NOT_EXPOSE",str(report))

    def test_symlink_not_traversed(self):
        with tempfile.TemporaryDirectory() as td:
            base=pathlib.Path(td)
            root=base/"beacon"
            root.mkdir()
            outside=base/"outside"
            outside.mkdir()
            (outside/"secret").write_text("DO_NOT_READ")
            (root/"link").symlink_to(outside,target_is_directory=True)
            with patch.object(m,"ROOT",root):
                report=m.inventory(root)
            self.assertEqual(report["symlinksNotFollowed"],1)
            self.assertEqual(report["regularFiles"],0)

    def test_wrong_root_refused(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(m.Refused,"unexpected"):
                m.inventory(pathlib.Path(td))

if __name__=="__main__":
    unittest.main()
