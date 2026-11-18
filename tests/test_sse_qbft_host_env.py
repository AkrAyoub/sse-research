"""Signed QBFT lab startup config: four genesis keys and peer signatures."""
import hashlib
import json
import os
from unittest.mock import patch
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from Crypto.PublicKey import ECC
from sse_network_peers import sign,SCHEMA,PeerCatalogError
from sse_qbft_validator_identity import node_key_record
from sse_qbft_lab_config import genesis
from sse_qbft_host_env import generate,EnvError,write_once

SOURCE_SHA="a"*40
GEN_HASH="0x"+"cd"*32
IMG="hyperledger/besu:26.11.1@sha256:"+"4"*64

class SignedQbftHostEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        if os.name == "nt":
            # Production host paths MUST remain POSIX-only. Unit tests on
            # Windows model safe Linux host-volume paths without weakening
            # sse_qbft_host_env.safe_path() for actual deployments.
            temporary_path=patch("sse_qbft_host_env.safe_path",
                                 side_effect=lambda value: "/tmp/sse-qbft-unit/"+value.name)
            temporary_path.start()
            self.addCleanup(temporary_path.stop)
        self.records=[node_key_record(i.to_bytes(32,"big"),f"validator-{i}",
                        f"100.101.102.{i+100}") for i in range(1,5)]
        self.genesis=self.base/"genesis.json"
        self.genesis.write_text(json.dumps(
            genesis([r["validatorAddress"] for r in self.records],
                    reward_wei=0),sort_keys=True)+"\n")
        self.genesha=hashlib.sha256(self.genesis.read_bytes()).hexdigest()
        self.signer=ECC.generate(curve="Ed25519")
        self.pub=self.signer.public_key().export_key(format="PEM")
        self.payload={
            "schema":SCHEMA,"chainId":31338,"genesisHash":GEN_HASH,
            "revision":SOURCE_SHA,"issuedAt":100,"expiresAt":9000,
            "nodes":[{"nodeId":r["nodeId"],"role":"validator","enode":r["enode"]}
                     for r in self.records],
        }
        self.catalog=sign(self.payload,self.signer.export_key(format="PEM"),
                          chain_id=31338,genesis_hash=GEN_HASH,now=101)
        self.kw=dict(node_id="validator-1",local_public=self.records[0],
                     catalog=self.catalog,public_pem=self.pub,
                     source_sha=SOURCE_SHA,genesis_path=self.genesis,
                     genesis_sha256=self.genesha,genesis_block_hash=GEN_HASH,
                     image=IMG,data_path=self.base/"data",key_path=self.base/"node.key",
                     user_id=1000,group_id=1000,now=200)

    def test_signed_catalog_produces_enodes_not_filename(self):
        env,report=generate(**self.kw)
        self.assertIn("BESU_BOOTNODES_LIST=enode://",env)
        self.assertNotIn("BESU_BOOTNODES=/etc/",env)
        self.assertEqual(env.count("enode://"),3)
        self.assertNotIn(self.records[0]["enode"],env)
        self.assertEqual(report["initialBootnodeCount"],3)
        self.assertEqual(report["consensusMode"],"PERMISSIONED_QBFT_RESEARCH")
        self.assertFalse(report["permissionlessValidatorMembership"])
        self.assertTrue(report["sourceCatalogSignatureVerified"])
        self.assertFalse(report["nodeStarted"])
        self.assertFalse(report["ethereumTransactionsSent"])
        self.assertEqual(report["envSha256"],hashlib.sha256(env.encode()).hexdigest())

    def test_signed_catalog_tamper_rejected(self):
        altered=json.loads(json.dumps(self.catalog))
        altered["payload"]["nodes"][1]["enode"]=self.records[0]["enode"]
        with self.assertRaises((PeerCatalogError,EnvError)):
            generate(**{**self.kw,"catalog":altered})
        with self.assertRaises((PeerCatalogError,EnvError)):
            generate(**{**self.kw,"public_pem":ECC.generate(curve="Ed25519").public_key().export_key(format="PEM")})

    def test_wrong_key_genesis_revision_refused(self):
        variants=[
            {"local_public":self.records[1]},
            {"source_sha":"b"*40},
            {"genesis_block_hash":"0x"+"ab"*32},
            {"genesis_sha256":"0"*64},
            {"image":"hyperledger/besu:latest"},
            {"key_path":self.base/"data"},
        ]
        for v in variants:
            with self.subTest(case=v),self.assertRaises((EnvError,PeerCatalogError,ValueError)):
                generate(**{**self.kw,**v})

    def test_signed_genesis_key_mismatch(self):
        different=self.base/"bad.json"
        different.write_text(json.dumps(genesis([r["validatorAddress"]
                             for r in self.records[:3]]+
                             ["0x"+"77"*20],reward_wei=0))+"\n")
        digest=hashlib.sha256(different.read_bytes()).hexdigest()
        with self.assertRaises(EnvError):
            generate(**{**self.kw,"genesis_path":different,
                        "genesis_sha256":digest})

    def test_env_file_once(self):
        private=self.base/"private"
        private.mkdir(mode=0o700)
        env,_=generate(**self.kw)
        path=private/".env"
        write_once(path,env)
        self.assertTrue(path.is_file())
        with self.assertRaises(EnvError):
            write_once(path,env)

    def test_compose_security_and_real_enode_arg(self):
        text=(ROOT/"infra"/"qbft-multivm"/"compose.yaml").read_text()
        self.assertIn("/tmp:rw,exec,nosuid,nodev",text)
        self.assertIn("BESU_BOOTNODES_LIST:",text)
        self.assertNotIn("--bootnodes=/etc/sse/bootnodes.txt",text)
        self.assertIn("--rpc-http-host=127.0.0.1",text)
        self.assertIn("read_only: true",text)
        self.assertIn("no-new-privileges:true",text)
        self.assertIn("cap_drop: [ALL]",text)

if __name__=="__main__":
    unittest.main()
