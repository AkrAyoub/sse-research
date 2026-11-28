"""Installer policy defaults and preparation plan (unit tests only)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sse_v4_app_install as app

class Defaults(unittest.TestCase):
    def test_caps(self):
        self.assertEqual(app.default_caps(),{"maxFeePerGasWei":1000000,"maxPriorityFeePerGasWei":1000,"maxGasPerTx":3000000,"dailyGasWeiBudget":1000000000000000})
        caps=app.default_caps(); caps["maxGasPerTx"]=1
        self.assertEqual(app.default_caps()["maxGasPerTx"],3000000)
    def test_no_signer_or_provider_enable(self):
        p=app.plan_actions(["provider","monitor"],False,"http://127.0.0.1:28545")
        self.assertFalse(p["activationClaimed"])
        enable=dict(p["actions"])["enable"]
        self.assertNotIn("sse-v4-agent.service",enable)
        self.assertNotIn("sse-v4-provider-outputs.service",enable)
        self.assertIn("sse-v4-console.service",enable)
if __name__=="__main__": unittest.main()
