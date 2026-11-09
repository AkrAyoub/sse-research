"""Gate CLI imports in CI; syntax-only compilation will not catch absent modules."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    'services/monitor-agent/monitor_agent.py',
    'services/monitor-agent/http_probe.py',
    'services/role-agent/agent.py',
    'services/provider-agent/http_service.py',
    'services/provider-agent/compute_http_service.py',
    'services/provider-agent/resource_profile.py',
    'tools/sse_chain_read.py',
    'tools/sse_e2e_local.py',
    'tools/sse_residual_typed_data.py',
)


class EntrypointSmokeTests(unittest.TestCase):
    def test_primary_entrypoints_accept_help_without_starting_services(self):
        for entrypoint in ENTRYPOINTS:
            with self.subTest(entrypoint=entrypoint):
                proc = subprocess.run(
                    [sys.executable, str(ROOT / entrypoint), '--help'],
                    cwd=ROOT, text=True, capture_output=True, timeout=15,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn('usage:', proc.stdout.lower())


if __name__ == '__main__':
    unittest.main()
