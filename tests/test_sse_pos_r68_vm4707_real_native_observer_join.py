"""R68 non-signing original chain31340 real public bootstrap role tests.

These tests mock all R59 host actions. NO real Docker, overlay, chain or signer.
"""
import pathlib
import sys
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r68_vm4707_real_native_observer_join as m

class R68RealVM4707JoinTests(unittest.TestCase):
    def test_source_public_owner_bootstrap_matches_actual_r67_report(self):
        self.assertEqual(m.SOURCE_R67_GIT_SHA,"25b317dcd43c0558a5a3c5811c5c8fc11dd19fc3")
        self.assertEqual(m.SOURCE_CHAIN_ID,31340)
        self.assertEqual(m.SOURCE_OWNER_IPV6,"fca0:2328:776e:4750:395b::1")
        self.assertTrue(m.SOURCE_EXECUTION_ENODE_V6.endswith("@[fca0:2328:776e:4750:395b::1]:30404"))
        self.assertEqual(m.SOURCE_OBSERVED_FINALIZED_EPOCH,122)
        self.assertEqual(m.SOURCE_OBSERVED_FINALIZED_ROOT,
            "0x6310aca4e76388f48323370de92019a9b7689ad4e742de698a2eb019486b7888")
        self.assertTrue(m.SOURCE_BEACON_ENR.startswith("enr:-NS4QINvGJM8"))

    def test_real_source_enode_and_beacon_enr_are_both_valid(self):
        m.check_source_seed()
        self.assertTrue(m.r59.ENODE6.fullmatch(m.SOURCE_EXECUTION_ENODE_V6))
        self.assertTrue(m.r59.ENR.fullmatch(m.SOURCE_BEACON_ENR))

    def test_beacon_enr_from_real_owner_advertises_verified_source_ipv6(self):
        import sse_pos_r67_post_migration_native_bootstrap_audit as r67
        enr=r67.parse_enr_fields(m.SOURCE_BEACON_ENR)
        record=r67.validate_enr_host(enr,m.SOURCE_OWNER_IPV6)
        self.assertTrue(record["beaconEnrIp6VerifiedAsActualOwnerOpenOverlay"])

    def test_only_readonly_preflight_called_by_r68_plan(self):
        with patch.object(sys,"argv",["program","--plan"]),patch.object(
                m.r59,"preflight",return_value={"mode":"read_only"}) as check,patch.object(
                m.r59,"apply") as mutate:
            self.assertEqual(m.main(),0)
        check.assert_called_once_with(m.SOURCE_EXECUTION_ENODE_V6,m.SOURCE_BEACON_ENR)
        mutate.assert_not_called()

    def test_apply_passes_exact_real_source_ids_to_one_time_R59_installer(self):
        with patch.object(sys,"argv",["program","--apply"]),patch.object(
                m.r59,"apply",return_value={"mode":"real"}) as apply:
            self.assertEqual(m.main(),0)
        apply.assert_called_once_with(m.SOURCE_EXECUTION_ENODE_V6,m.SOURCE_BEACON_ENR)

    def test_no_default_apply_and_no_synthetic_peer_claim(self):
        with patch.object(sys,"argv",["program"]):
            with self.assertRaises(SystemExit):
                m.main()
        src=(ROOT/"tools/sse_pos_r68_vm4707_real_native_observer_join.py").read_text()
        self.assertIn("liveOutsideProviderNativeP2pAndRootAgreementStillUnverified",src)
        self.assertNotIn("docker(",src)
        self.assertNotIn("secrets.token_hex",src)
        self.assertNotIn("validator create",src)

if __name__=="__main__":
    unittest.main()
