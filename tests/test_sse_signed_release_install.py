"""Release archive escape, publisher signature, and isolated staging tests (offline)."""
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa
import base64
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_signed_release_install import safe_extract, install, InstallerError
from sse_release_verify import canonical

NOW=1795000000
CHAIN=31338
SETTLEMENT="0x" + "12" * 20
KEY=ECC.generate(curve="Ed25519")
PUB=KEY.public_key().export_key(format="PEM")


def archive(files):
    buff=io.BytesIO()
    with tarfile.open(fileobj=buff,mode="w:gz") as tar:
        for name,contents in files.items():
            info=tarfile.TarInfo(name)
            info.size=len(contents)
            tar.addfile(info,io.BytesIO(contents))
    return buff.getvalue()


def envelope(content):
    payload={
      "kind":"SSE_RELEASE_V1","revision":"a"*40,
      "chainId":CHAIN,"settlement":SETTLEMENT,"roles":["provider"],
      "createdAt":NOW-10,"expiresAt":NOW+100,
      "artifactUrl":"https://releases.example.org/sse.tar.gz",
      "artifactSha256":hashlib.sha256(content).hexdigest()
    }
    sig=eddsa.new(KEY,"rfc8032").sign(canonical(payload))
    return {"payload":payload,"signature":base64.b64encode(sig).decode()}


class SignedBundleTests(unittest.TestCase):
    def test_extract_good_github_source_archive(self):
        data=archive({"sse-research/contracts/SSESettlement.sol":b"contract SSESettlement {}"})
        with tempfile.TemporaryDirectory() as d:
            archive_file=Path(d)/"source.tar.gz"
            archive_file.write_bytes(data)
            repo=safe_extract(archive_file,Path(d))
            self.assertTrue((repo/"contracts/SSESettlement.sol").is_file())

    def test_reject_path_escape_and_symlink(self):
        entries={"sse-research/../outside.txt":b"not safe"}
        data=archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"bad.tar.gz"; path.write_bytes(data)
            with self.assertRaises(InstallerError):
                safe_extract(path, Path(d))

    def test_install_approved_snapshot_to_new_target_only(self):
        data=archive({"sse-research/contracts/SSESettlement.sol":b"pragma solidity ^0.8.24;"})
        signed=envelope(data)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def mock_download(url,digest,target):
                target.write_bytes(data)
                return len(data)
            output=root/"install"
            result=install(signed,PUB,expected_chain_id=CHAIN,
                           settlement=SETTLEMENT,roles=("provider",),
                           target=output, now=NOW,download=mock_download)
            self.assertTrue(result["publisherSignatureVerified"])
            self.assertFalse(result["ethereumTransactionsSent"])
            with self.assertRaises(InstallerError):
                install(signed,PUB,expected_chain_id=CHAIN,
                        settlement=SETTLEMENT,roles=("provider",),
                        target=output,now=NOW,download=mock_download)

    def test_tamper_signed_manifest_fails(self):
        data=archive({"sse-research/contracts/SSESettlement.sol":b"x"})
        signed=envelope(data)
        signed["payload"]["chainId"]=31337
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            install(signed,PUB,expected_chain_id=CHAIN,settlement=SETTLEMENT,
                    roles=("provider",),target=Path(d)/"install",now=NOW,
                    download=lambda *a: AssertionError("must not be called"))


if __name__=="__main__":
    unittest.main()
