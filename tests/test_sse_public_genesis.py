"""R149 pure public artifact release tests; no network, sudo or new genesis."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_public_genesis as m

def release():
    return {
        "schema":m.SCHEMA,"chainId":31340,
        "executionGenesisHash":m.EL_GENESIS,
        "beaconGenesisValidatorsRoot":m.CL_GENESIS,
        "originalGenesisArchiveSha256":m.ARCHIVE_SHA,
        "originalGenesisArchiveSources":[],
        "replaceablePeerDirectorySources":[],
        "currentPublicReleaseStatus":"BLOCKED_UNPUBLISHED_ORIGINAL_GENESIS_AND_DISCOVERY",
        "noFixedBootstrapPeerOrIp":True,
        "noMemberAllowlist":True,
        "noAutomaticGenesisRecreation":True,
    }

class PublicArtifactTests(unittest.TestCase):
    def test_repository_release_explicitly_blocked_without_mirrors(self):
        path=Path(__file__).resolve().parents[1]/"release/chain31340-public-release.json"
        obj=m.read_manifest(path)
        self.assertEqual(obj["chainId"],31340)
        self.assertFalse(obj["originalGenesisArchiveSources"])
        self.assertFalse(obj["replaceablePeerDirectorySources"])

    def test_missing_public_artifact_does_not_create_fake_genesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"original-genesis.tar.gz"
            with self.assertRaisesRegex(m.Refused,"NOT_YET_PUBLICLY_RELEASED"):
                m.acquire(release(),dest)
            self.assertFalse(dest.exists())

    def test_wrong_genesis_or_chain_refused(self):
        for field in ("chainId","executionGenesisHash",
                      "beaconGenesisValidatorsRoot","originalGenesisArchiveSha256"):
            bad=release()
            bad[field]="invented"
            with self.subTest(field=field),self.assertRaises(m.Refused):
                m.manifest(bad)

    def test_extra_privileged_admission_fields_refused(self):
        bad=release()
        bad["permissionedAddresses"]=["0x123"]
        with self.assertRaises(m.Refused):
            m.manifest(bad)

    def test_mirrors_are_replaceable_public_dns_not_fixed_ips(self):
        for url in ("http://mirror.example.org/a.tar.gz",
                    "https://127.0.0.1/a.tar.gz",
                    "https://u:p@mirror.example.org/a.tar.gz",
                    "https://localhost/a.tar.gz",
                    "https://mirror.example.org"):
            with self.subTest(url=url),self.assertRaises(m.Refused):
                m.verify_url(url)
        self.assertEqual(m.verify_url("https://mirror.example.org/a.tar.gz"),
                         "https://mirror.example.org/a.tar.gz")

    def test_public_source_list_unique_and_bounded(self):
        obj=release()
        obj["originalGenesisArchiveSources"]=["https://a.example.org/archive"]*2
        with self.assertRaises(m.Refused):
            m.manifest(obj)

    def test_valid_byte_for_byte_artifact_install_is_create_only(self):
        data=b"ONLY-UNIT-TEST-NOT-REAL-GENESIS"
        obj=release()
        obj["originalGenesisArchiveSources"]=["https://mirror.example.org/genesis.tar.gz"]
        obj["currentPublicReleaseStatus"]="PUBLIC_GENESIS_MIRRORED_NATIVE_DISCOVERY_PENDING"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,"ARCHIVE_SHA",hashlib.sha256(data).hexdigest()):
            # Release manifest is intentionally pinned to the real hash; update
            # only the pure fixture here to simulate a verified byte stream.
            obj["originalGenesisArchiveSha256"]=m.ARCHIVE_SHA
            target=Path(tmp)/"original-archive"
            result=m.acquire(obj,target,lambda _:data)
            self.assertTrue(result["sha256Verified"])
            self.assertEqual(target.read_bytes(),data)
            with self.assertRaises(m.Refused):
                m.acquire(obj,target,lambda _:data)

    def test_wrong_downloaded_bytes_do_not_create_output(self):
        obj=release()
        obj["originalGenesisArchiveSources"]=["https://mirror.example.org/genesis.tar.gz"]
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"original-archive"
            with self.assertRaises(m.Refused):
                m.acquire(obj,target,lambda _:b"not the original genesis")
            self.assertFalse(target.exists())

if __name__=="__main__":
    unittest.main()
