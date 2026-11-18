"""Offline test of four-host public report audit and node clone detection."""
import base64
import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_validator_identity import node_key_record
from sse_qbft_fleet_evidence import (
    FleetError, audit, ssh_public_fingerprint, validate_public_report
)

NOW=1795000000
REV="a"*40


def fake_ssh_pub(i:int):
    wire=(11).to_bytes(4,"big")+b"ssh-ed25519"+(32).to_bytes(4,"big")+bytes([i])*32
    return "ssh-ed25519 "+base64.b64encode(wire).decode()+" test-host"


def fixture(i:int):
    public=node_key_record(i.to_bytes(32,"big"),f"validator-{i}",
                           f"100.101.102.{i+100}")
    return {
        "schema":"SSE_QBFT_HOST_REPORT_V1",
        "nodeId":public["nodeId"], "gitCommit":REV,
        "collectedAt":NOW-120,
        "hostName":f"cloud-node-{i}",
        "sshEd25519Fingerprint":ssh_public_fingerprint(fake_ssh_pub(i)),
        "tailscaleStableId":f"n-test-{i}",
        "tailscaleDnsName":f"validator-{i}.tail123.ts.net.",
        "overlayIPv4":public["overlayIPv4"],
        "validatorPublic":public,
        "privateKeysIncluded":False,
        "operatorIdentityIndependenceProved":False,
        "networkStarted":False,
    }


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.reports=[fixture(i) for i in range(1,5)]

    def test_independent_four_public_identities_accept(self):
        report=audit(self.reports,revision=REV,now=NOW)
        self.assertEqual(report["uniqueValidatorKeys"],4)
        self.assertEqual(report["uniqueOverlayAddresses"],4)
        self.assertEqual(report["uniqueTailscaleDeviceIDs"],4)
        self.assertEqual(report["uniqueSSHHostKeys"],4)
        self.assertTrue(report["hostNamesAllDistinct"])
        self.assertFalse(report["physicalIndependenceCryptographicallyProved"])
        self.assertFalse(report["transactionsSent"])

    def test_duplicate_portal_hostname_not_identity(self):
        self.reports[3]["hostName"]=self.reports[0]["hostName"]
        report=audit(self.reports,revision=REV,now=NOW)
        self.assertFalse(report["hostNamesAllDistinct"])
        self.assertEqual(report["uniqueSSHHostKeys"],4)

    def test_cloned_ssh_key_rejected(self):
        self.reports[1]["sshEd25519Fingerprint"]=self.reports[0]["sshEd25519Fingerprint"]
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)

    def test_cloned_tailscale_device_rejected(self):
        self.reports[1]["tailscaleStableId"]=self.reports[0]["tailscaleStableId"]
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)

    def test_duplicate_p2p_key_and_ip_rejected(self):
        self.reports[2]["validatorPublic"]=copy.deepcopy(self.reports[0]["validatorPublic"])
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)

    def test_stale_future_and_different_revision_rejected(self):
        self.reports[1]["collectedAt"]=NOW-14401
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)
        self.reports[1]["collectedAt"]=NOW+100
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)
        self.reports[1]["collectedAt"]=NOW-120
        self.reports[1]["gitCommit"]="b"*40
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)

    def test_manipulated_address_and_enode_rejected(self):
        self.reports[2]["validatorPublic"]["validatorAddress"]="0x"+"ab"*20
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)
        self.reports[2]=fixture(3)
        self.reports[2]["validatorPublic"]["enode"]="enode://"+"ee"*64+"@100.101.102.103:30303"
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)

    def test_rejects_hidden_privates_and_wrong_schema(self):
        self.reports[0]["validatorPublic"]["privateKeyIncluded"]=True
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)
        self.reports[0]=fixture(1)
        self.reports[0]["validatorPublic"]["newField"]="hidden"
        with self.assertRaises(FleetError):
            audit(self.reports,revision=REV,now=NOW)

    def test_ssh_fp_uses_openssh_wire_digest(self):
        value=ssh_public_fingerprint(fake_ssh_pub(1))
        self.assertTrue(value.startswith("SHA256:"))
        self.assertEqual(len(value),50)
        with self.assertRaises(FleetError):
            ssh_public_fingerprint("ssh-rsa blah")
        with self.assertRaises(FleetError):
            ssh_public_fingerprint("ssh-ed25519 NOT_BASE64***")


if __name__=="__main__":
    unittest.main()
