"""R136 read-only onboarding preflight: pure mocked tests, no running-VM actions."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r136_independent_observer_preflight as m

def valid():
    return {"schema": m.SCHEMA, "chainId": 31340,
            "nodeId": "independent-operator-1", "role": "observer",
            "networkId": m.NETWORK_ID, "archiveSha256": m.ARCHIVE_SHA}

class R136Tests(unittest.TestCase):
    def test_manifest_not_tied_to_existing_two_vms(self):
        self.assertEqual(m.validate_manifest(valid())["nodeId"], "independent-operator-1")
        self.assertNotIn("hostIp", valid())

    def test_wrong_identity_role_and_secret_fields_refused(self):
        for k,v in [("chainId", 31339), ("chainId", True),
                    ("role", "validator"), ("networkId", "wrong"),
                    ("archiveSha256", "0" * 64), ("nodeId", "../unsafe")]:
            with self.subTest(field=k):
                obj = valid()
                obj[k] = v
                with self.assertRaises(m.Refused):
                    m.validate_manifest(obj)
        obj = valid()
        obj["privateKey"] = "not-allowed"
        with self.assertRaises(m.Refused):
            m.validate_manifest(obj)

    def test_real_overlay_interface_not_only_advertisement(self):
        ip = "fca0:2328:7777:8888:9999::1"
        networks = [{"nwid": m.NETWORK_ID, "status": "OK", "type": "PUBLIC",
                     "portDeviceName": "ztabcdef12", "assignedAddresses": [ip + "/40"]}]
        links = [{"ifname": "ztabcdef12",
                  "addr_info": [{"local": ip, "prefixlen": 40}]}]
        def run(cmd):
            return json.dumps(networks if cmd[0] == "zerotier-cli" else links)
        self.assertEqual(m.observed_overlay(run), ("ztabcdef12", ip))
        links[0]["addr_info"].clear()
        with self.assertRaises(m.Refused):
            m.observed_overlay(run)
        links[0]["addr_info"].append({"local": ip, "prefixlen": 40})
        networks[0]["type"] = "PRIVATE"
        with self.assertRaises(m.Refused):
            m.observed_overlay(run)

    def test_duplicate_addresses_and_wrong_prefix_refused(self):
        ip = "fca0:2328:7777:8888:9999::1"
        node = {"nwid": m.NETWORK_ID, "status": "OK", "type": "PUBLIC",
                "portDeviceName": "ztabcdef12", "assignedAddresses":
                [ip + "/40", "fca0:2328:7777:8888:9999::2/40"]}
        with self.assertRaises(m.Refused):
            m.observed_overlay(lambda cmd: json.dumps([node]))
        node["assignedAddresses"] = [ip + "/64"]
        with self.assertRaises(m.Refused):
            m.observed_overlay(lambda cmd: json.dumps([node]))

    def test_archive_wrong_bytes_and_symlinks_refused(self):
        with tempfile.TemporaryDirectory() as root:
            p = pathlib.Path(root) / "archive.tar.gz"
            p.write_bytes(b"not original chain")
            with self.assertRaises(m.Refused):
                m.verify_archive(p)
            link = pathlib.Path(root) / "link.tar.gz"
            link.symlink_to(p)
            with self.assertRaises(m.Refused):
                m.verify_archive(link)

    def test_never_claim_live_chain_or_public_permissionless_access(self):
        result = m.report(valid(), 200, "ztabcdef12", "fca0:2328:7777:8888:9999::1")
        for field in ("validatorCreatedOrStarted", "genesisRecreated",
                      "dockerResourcesChanged", "nativeElPeerHandshakeVerified",
                      "nativeClPeerHandshakeVerified", "canonicalChainSyncVerified",
                      "independentPublicInternetReachabilityVerified",
                      "permissionlessOnboardingEndToEndVerified"):
            self.assertFalse(result[field])
        self.assertEqual(result["status"], "PREFLIGHT_ONLY_NOT_DEPLOYED")

if __name__ == "__main__":
    unittest.main()
