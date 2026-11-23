"""R148: first-node bootstrap invariants, not a newly invented genesis."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_join_phase as p

def call(**changes):
    values={"genesis_el":p.EL_GENESIS,"genesis_cl":p.CL_GENESIS,
            "phase":"first_online_peer"}
    values.update(changes)
    return p.admission(**values)

class Phases(unittest.TestCase):
    def test_first_node_with_zero_bootstrap_has_no_fixed_peer(self):
        result=call(discovered_peers=0)
        self.assertTrue(result["canStartReadOnlyClients"])
        self.assertFalse(result["hardcodedBootnodesRequired"])
        self.assertFalse(result["chainGenesisRecreated"])
        self.assertFalse(result["consensusLiveOrFinalityProven"])

    def test_first_nonvalidator_node_not_false_finality(self):
        result=call(active_local_genesis_validators=0)
        self.assertEqual(result["state"],"FIRST_PEER_WITHOUT_FINALITY_PROOF")
        self.assertFalse(result["locallyAuthorizedExistingGenesisSignerObserved"])

    def test_original_authorized_genesis_signer_not_auto_activated(self):
        result=call(active_local_genesis_validators=1,owner_signing_key_present=True)
        self.assertTrue(result["locallyAuthorizedExistingGenesisSignerObserved"])
        self.assertFalse(result["consensusLiveOrFinalityProven"])

    def test_joining_node_without_peers_waits_without_inventing_them(self):
        result=call(phase="joining_peer",discovered_peers=0)
        self.assertEqual(result["state"],"WAITING_FOR_ACTUAL_NATIVE_PEERS_NOT_SYNCHRONIZED")
        self.assertFalse(result["nativePeerDiscoveryPresent"])

    def test_joining_node_with_peers_requires_actual_finality(self):
        result=call(phase="joining_peer",discovered_peers=3)
        self.assertEqual(result["state"],"PEERS_VISIBLE_FINALITY_NOT_YET_VERIFIED")
        self.assertFalse(result["consensusLiveOrFinalityProven"])

    def test_wrong_chain_identity_refused(self):
        for field in ("genesis_el","genesis_cl"):
            with self.subTest(field=field),self.assertRaises(p.Refused):
                call(**{field:"0x"+"bb"*32})

    def test_bad_phase_and_bad_synthetic_peer_counts_refused(self):
        for phase in ("genesis_recreate","administrator", ""):
            with self.assertRaises(p.Refused):
                call(phase=phase)
        for count in (-1,True,"5"):
            with self.assertRaises(p.Refused):
                call(discovered_peers=count)

if __name__=="__main__":
    unittest.main()
