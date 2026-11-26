"""Exact combinatorial regression tests; no live network measurements."""
import sys
import unittest
from fractions import Fraction
from itertools import combinations
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from sse_pos_r412_monitor_selection_risk import risk,render

class MonitorRiskTests(unittest.TestCase):
    def test_exhaustive_small_populations(self):
        for n in range(4,10):
            for a in range(n+1):
                for k in range(4,n+1):
                    counts=Counter(sum(i<a for i in c) for c in combinations(range(n),k))
                    total=sum(counts.values())
                    expected={i:Fraction(v,total) for i,v in counts.items()}
                    r=risk(n,a,k)
                    self.assertEqual(r["distribution"],expected)
                    b=(k-1)//3
                    q=k-b
                    self.assertEqual(r["assumptionExceeded"],sum(p for i,p in expected.items() if i>b))
                    self.assertEqual(r["attackerQuorum"],sum(p for i,p in expected.items() if i>=q))
                    self.assertEqual(r["honestOnlyQuorumUnavailableIfAdversaryAbstains"],sum(p for i,p in expected.items() if k-i<q))
                    self.assertGreater(2*q-k,b)
                    self.assertLessEqual(q,k-b)

    def test_four_seats(self):
        self.assertEqual(risk(8,2,4)["assumptionExceeded"],Fraction(3,14))
        self.assertEqual(risk(8,2,4)["attackerQuorum"],0)
        self.assertEqual(risk(4,3,4)["attackerQuorum"],1)

    def test_boundary(self):
        for a in (0,10):
            r=risk(10,a,4)
            self.assertEqual(r["assumptionExceeded"],int(a==10))
            self.assertEqual(r["attackerQuorum"],int(a==10))

    def test_invalid(self):
        for args in [(3,0,3),(4,-1,4),(4,5,4),(4,0,5),(True,0,4),(4,0,4.0)]:
            with self.assertRaises(ValueError):
                risk(*args)

    def test_exact_serialization(self):
        self.assertEqual(render(Fraction(1,3)),{"numerator":1,"denominator":3,"probability":1/3})

if __name__=="__main__":
    unittest.main()
