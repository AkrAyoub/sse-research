"""R92 regression tests for the restricted owner host relay (no Docker use)."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r92_owner_internal_bridge_host_relay as m

class R92RelayTests(unittest.TestCase):
    def test_exact_interfaces_and_no_engine_api(self):
        m.validate()
        self.assertEqual(len(m.FORWARDS), 7)
        self.assertEqual({x[0] for x in m.FORWARDS}, {"tcp", "udp"})
        self.assertEqual({x[1] for x in m.FORWARDS},
                         {"127.0.0.1", "fca0:2328:776e:4750:395b::1"})
        self.assertFalse(any(x[2] == 8551 or x[4] == 8551 for x in m.FORWARDS))
        self.assertEqual(set(x[3] for x in m.FORWARDS), {"172.18.0.2", "172.18.0.3"})
    def test_only_explicit_advertised_p2p_ports(self):
        self.assertEqual(
            {(proto, port) for proto, host, port, _, _ in m.FORWARDS if host == m.OWNER},
            {("tcp", 30404), ("udp", 30404), ("tcp", 9000), ("udp", 9000), ("udp", 9001)}
        )
        self.assertEqual(
            {(proto, port) for proto, host, port, _, _ in m.FORWARDS if host == "127.0.0.1"},
            {("tcp", 18545), ("tcp", 15052)}
        )
    def test_check_mode_does_not_forward(self):
        fake = unittest.mock.MagicMock()
        with patch.object(m, "bind_socket", return_value=fake) as bind, patch.object(
            sys, "argv", ["relay", "--check"]
        ), patch.object(m, "run_tcp") as tcp, patch.object(m, "run_udp") as udp:
            self.assertEqual(m.main(), 0)
        self.assertEqual(bind.call_count, 7)
        self.assertEqual(fake.close.call_count, 7)
        tcp.assert_not_called()
        udp.assert_not_called()

if __name__ == "__main__":
    unittest.main()
