"""Read-only VM gate: pin image/genesis and reject accidental legacy chain."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_vm_preflight import (parse_image,parse_tailscale_status,
                                  parse_genesis,PreflightError,assess)
from sse_qbft_lab_config import genesis

ADDRS=["0x"+f"{i:02x}"*20 for i in range(1,5)]
IMAGE="hyperledger/besu:26.8.0@sha256:"+"a"*64


class PreflightTests(unittest.TestCase):
    def test_immutable_baseline_and_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"genesis.json"
            path.write_text(json.dumps(genesis(ADDRS)),encoding="utf-8")
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            doc=parse_genesis(path,digest)
            self.assertEqual(doc["chainId"],31338)
            self.assertEqual(doc["blockGasLimit"],15000000)
            with self.assertRaises(PreflightError):
                parse_genesis(path,"0"*64)
    def test_rejects_wrong_genesis_or_unpinned_image(self):
        for value in ("hyperledger/besu:latest","hyperledger/besu:26.8.0",
                      "other/besu:26.8.0@sha256:"+"a"*64,
                      "hyperledger/besu:26.8.0@sha256:banana"):
            with self.subTest(value=value), self.assertRaises(PreflightError):
                parse_image(value)
        self.assertEqual(parse_image(IMAGE), IMAGE)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"genesis.json"
            value=genesis(ADDRS)
            value["config"]["chainId"]=31337
            path.write_text(json.dumps(value),encoding="utf-8")
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(PreflightError):
                parse_genesis(path,digest)
    def test_overlay_identity_must_be_online_and_own_ip(self):
        good=json.dumps({"BackendState":"Running","Self":{
            "Online":True,"TailscaleIPs":["100.101.102.103"]}})
        self.assertEqual(parse_tailscale_status(good,"100.101.102.103")["tailscaleOnline"],True)
        for ip in ("100.101.102.104","10.50.56.14","127.0.0.1"):
            with self.subTest(ip=ip),self.assertRaises(PreflightError):
                parse_tailscale_status(good,ip)
        with self.assertRaises(PreflightError):
            parse_tailscale_status(good.replace("Running","Stopped"),"100.101.102.103")
    def test_wrong_revision_fails_before_any_host_probing(self):
        with self.assertRaises(PreflightError):
            assess(source_revision="a"*40,current_revision="b"*40,
                   image=IMAGE,genesis=Path("/unused"),
                   genesis_sha256="a"*64,
                   private_dir=Path("/unused"),public_file=Path("/unused"),
                   tailscale_status="",run=lambda a: AssertionError("should not call"),
                   listening=lambda *a: AssertionError("should not call"))

if __name__=="__main__":
    unittest.main()
