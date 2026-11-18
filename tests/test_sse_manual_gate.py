"""Static safety checks for the manually executed local acceptance wrapper."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


class ManualGateTests(unittest.TestCase):
    def test_uses_local_tools_no_actions(self):
        script = (ROOT / "scripts" / "manual_integrated_gate.sh").read_text()
        self.assertIn("python -m unittest discover -s tests -v", script)
        self.assertIn("forge build", script)
        self.assertIn("forge test -vv", script)
        self.assertNotIn("gh workflow", script)
        self.assertNotIn("cast send", script)
        self.assertNotIn("git reset --hard", script)
        self.assertNotIn("docker compose down", script)


if __name__ == "__main__":
    unittest.main()
