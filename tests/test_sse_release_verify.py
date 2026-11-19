"""Signed immutable release manifest tests. Requires pinned pycryptodome."""
import base64
import importlib.util
import sys
import time
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sse_release_verify", ROOT/"tools"/"sse_release_verify.py")
r = importlib.util.module_from_spec(spec); sys.modules[spec.name] = r; spec.loader.exec_module(r)
SHA = "a" * 40
ADDR = "0x" + "12" * 20


class ReleaseVerifyTests(unittest.TestCase):
    def setUp(self):
        self.private = ECC.generate(curve="Ed25519")
        self.public = self.private.public_key().export_key(format="PEM")
        self.now = 500000
        self.payload = dict(
            kind="SSE_RELEASE_V1", revision=SHA, chainId=11155111,
            settlement=ADDR, roles=["provider", "monitor", "consumer", "observer"],
            createdAt=self.now - 1, expiresAt=self.now + 3600,
            artifactUrl="https://github.com/AkrAyoub/sse-research/releases/download/v1/sse.tar.gz",
            artifactSha256="f" * 64,
        )

    def signed(self, payload=None):
        payload = self.payload if payload is None else payload
        signature = eddsa.new(self.private, "rfc8032").sign(r.canonical(payload))
        return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}

    def verify(self, env):
        return r.verify_envelope(env, self.public, expected_chain_id=11155111,
                                 settlement=ADDR, required_roles=("provider",),
                                 now=self.now)

    def test_good_release_cryptographically_verified_not_applied(self):
        result = self.verify(self.signed())
        self.assertTrue(result["verified"])
        self.assertFalse(result["softwareApplied"])
        self.assertFalse(result["chainTransactionsSent"])

    def test_tampered_signed_payload_fails(self):
        env = self.signed()
        env["payload"]["revision"] = "b" * 40
        with self.assertRaises(r.ReleaseError):
            self.verify(env)

    def test_wrong_public_key_fails(self):
        other = ECC.generate(curve="Ed25519").public_key().export_key(format="PEM")
        with self.assertRaises(r.ReleaseError):
            r.verify_envelope(self.signed(), other, expected_chain_id=11155111,
                              settlement=ADDR, required_roles=("provider",), now=self.now)

    def test_expired_release_rejected_even_if_signed(self):
        self.payload["expiresAt"] = self.now
        with self.assertRaises(r.ReleaseError):
            self.verify(self.signed())

    def test_wrong_chain_and_contract_rejected_even_if_signed(self):
        self.payload["chainId"] = 31337
        with self.assertRaises(r.ReleaseError):
            self.verify(self.signed())
        self.payload["chainId"] = 11155111
        self.payload["settlement"] = "0x" + "34" * 20
        with self.assertRaises(r.ReleaseError):
            self.verify(self.signed())

    def test_unsupported_roles_rejected(self):
        self.payload["roles"] = ["observer"]
        with self.assertRaises(r.ReleaseError):
            self.verify(self.signed())

    def test_no_http_or_embed_secrets_in_artifact_url(self):
        for url in ("http://downloads.example/artifact", "https://x:y@downloads.example/file",
                    "https://example.org/file?token=secret"):
            self.payload["artifactUrl"] = url
            with self.subTest(url=url), self.assertRaises(r.ReleaseError):
                self.verify(self.signed())

    def test_unsigned_extra_fields_rejected(self):
        self.payload["danger"] = "override"
        with self.assertRaises(r.ReleaseError):
            self.verify(self.signed())

    def test_invalid_signature_length_rejected(self):
        env = self.signed()
        env["signature"] = base64.b64encode(b"short").decode()
        with self.assertRaises(r.ReleaseError):
            self.verify(env)


if __name__ == "__main__":
    unittest.main()
