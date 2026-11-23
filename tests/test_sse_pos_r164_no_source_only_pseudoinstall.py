"""R164 regression: no pseudo-install or new-chain fallback when public genesis missing."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sse_install as m

COMMIT="ca3a9e1ef747f56f99220f5b1bafa7f0a06e9969"

class R164FailClosedTests(unittest.TestCase):
    def test_market_only_roles_refused_before_any_package_mutation(self):
        for roles in (["consumer"],["provider"],["monitor"],
                      ["provider","consumer","monitor"]):
            with self.subTest(roles=roles), \
                 tempfile.TemporaryDirectory() as tmp, \
                 patch.object(m.os,"geteuid",return_value=0), \
                 patch.object(m,"guard_existing"), \
                 patch.object(m,"command") as runner:
                root=Path(tmp)/"sse/releases"
                state=Path(tmp)/"sse/selection.json"
                with self.assertRaisesRegex(
                        m.Refused,"MARKETPLACE_ROLE_INSTALLER_NOT_YET_IMPLEMENTED"):
                    m.install_source(COMMIT,m.build_plan(COMMIT,roles,"node-fresh-a"),
                                     root=root,state=state)
                runner.assert_not_called()
                self.assertFalse(root.exists())
                self.assertFalse(state.exists())

    def test_lack_of_public_genesis_must_not_leave_installed_selection(self):
        # Executing source acquisition on a verified fresh host with NO
        # release URL may install signed OS packages, but MUST NOT mark
        # its source as successfully activated or create local selection.
        import inspect
        text=inspect.getsource(m.install_source)
        self.assertIn("PUBLIC_ORIGINAL_GENESIS_NOT_YET_AVAILABLE",text)
        self.assertLess(text.index("PUBLIC_ORIGINAL_GENESIS_NOT_YET_AVAILABLE"),
                        text.index('state.parent.mkdir('))

    def test_original_chains_and_live_services_still_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"home/user/.local/share/sse-r27-bls-operator-private").mkdir(
                parents=True)
            with self.assertRaises(m.Refused):
                m.guard_existing(root)

if __name__=="__main__":
    unittest.main()
