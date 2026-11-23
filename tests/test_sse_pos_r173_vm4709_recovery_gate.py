"""R173 read-only recovery gate unit tests: no apt, git, Docker mutations."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r173_vm4709_recovery_gate as m

class R173Tests(unittest.TestCase):
    def test_read_only_rejects_unrecognized_genesis_or_selected_role(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            state=base/"selection.json"
            release=base/"releases"/m.EXPECTED_SOURCE
            release.mkdir(parents=True)
            archive=release/"original-chain31340.tar.gz"
            archive.write_bytes(b"wrong and definitely not the original genesis")
            state.write_text(json.dumps({
                "sourceCommit":m.EXPECTED_SOURCE,
                "selectedRoles":["observer"],"network":"chain31340",
                "chainGenesisRecreated":False,"publicSourceDownloaded":True,
                "roleSelectionRecorded":True,"nodeId":"node-test-a"}))
            state.chmod(0o600)
            with self.assertRaisesRegex(m.Refused,"checksum"):
                m.diagnose(root=base/"releases",state=state,
                           runner=lambda args:self.fail("unexpected subprocess"))
            data=json.loads(state.read_text())
            data["selectedRoles"]=["validator"]
            state.write_text(json.dumps(data))
            with self.assertRaisesRegex(m.Refused,"unexpected saved"):
                m.diagnose(root=base/"releases",state=state,
                           runner=lambda args:self.fail("unexpected subprocess"))

    def test_immutable_archive_and_no_sse_clients_reports_safe_state(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            state=base/"selection.json"
            release=base/"releases"/m.EXPECTED_SOURCE
            release.mkdir(parents=True)
            archive=release/"original-chain31340.tar.gz"
            blob=b"TEST-ONLY-BYTES"
            archive.write_bytes(blob)
            state.write_text(json.dumps({
                "sourceCommit":m.EXPECTED_SOURCE,
                "selectedRoles":["observer"],"network":"chain31340",
                "chainGenesisRecreated":False,"publicSourceDownloaded":True,
                "roleSelectionRecorded":True,"nodeId":"node-test-a"}))
            state.chmod(0o600)
            called=[]
            def runner(args):
                called.append(args)
                if args[:2]==["docker","ps"]:
                    return (0,"other-preexisting-container\n")
                if args[:2]==["systemctl","is-active"]:
                    return (0,"active") if args[-1]=="docker" else (3,"inactive")
                return None
            previous=m.EXPECTED_GENESIS
            try:
                m.EXPECTED_GENESIS=hashlib.sha256(blob).hexdigest()
                observed=m.diagnose(root=base/"releases",state=state,runner=runner)
            finally:
                m.EXPECTED_GENESIS=previous
            self.assertTrue(observed["publicOriginalArchiveSha256Verified"])
            self.assertTrue(observed["dockerActive"])
            self.assertFalse(observed["zerotier_oneActive"])
            self.assertFalse(observed["safeToRerunR147Installer"])
            self.assertTrue(observed["existingReleaseMustBePreserved"])
            self.assertTrue(all(args[0] in ("docker","systemctl","zerotier-cli")
                                for args in called))

    def test_existing_chain_containers_refuse_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            state=base/"selection.json"
            release=base/"releases"/m.EXPECTED_SOURCE
            release.mkdir(parents=True)
            blob=b"TEST-ONLY-BYTES"
            (release/"original-chain31340.tar.gz").write_bytes(blob)
            state.write_text(json.dumps({
                "sourceCommit":m.EXPECTED_SOURCE,
                "selectedRoles":["observer"],"network":"chain31340",
                "chainGenesisRecreated":False,"publicSourceDownloaded":True,
                "roleSelectionRecorded":True,"nodeId":"node-test-a"}))
            state.chmod(0o600)
            previous=m.EXPECTED_GENESIS
            try:
                m.EXPECTED_GENESIS=hashlib.sha256(blob).hexdigest()
                with self.assertRaisesRegex(m.Refused,"existing SSE Docker"):
                    m.diagnose(root=base/"releases",state=state,
                               runner=lambda args:(0,"sse31340-r137-node-test-a-el"))
            finally:
                m.EXPECTED_GENESIS=previous

if __name__=="__main__":
    unittest.main()
