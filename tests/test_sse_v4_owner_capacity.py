"""Pure capacity planning checks (not live-chain evidence)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_v4_owner_transactions as m
import sse_v4_abi as a

class Capacity(unittest.TestCase):
    def test_registration_scales_bond(self):
        for cap in (1,2,4,64):
            self.assertEqual(m.monitor_intent((0,0,0,0,False),cap,10**15),a.register_monitor(cap,cap*10**15))
    def test_explicit_resize(self):
        pos=(10**15,1,1,1,False)
        with self.assertRaises(RuntimeError): m.monitor_intent(pos,2,10**15)
        self.assertEqual(m.monitor_intent(pos,2,10**15,True),a.update_bond(2,10**15))
        self.assertIsNone(m.monitor_intent(pos,1,10**15))
    def test_no_underreserved_or_exiting(self):
        for pos,cap in (((4*10**15,4,3,1,False),2),((10**15,1,0,1,True),1),((0,0,0,0,False),65)):
            with self.assertRaises(RuntimeError): m.monitor_intent(pos,cap,10**15,True)
    def test_resize_covered(self):
        self.assertEqual(m.monitor_intent((4*10**15,2,1,1,False),4,10**15,True),a.update_bond(4,0))
