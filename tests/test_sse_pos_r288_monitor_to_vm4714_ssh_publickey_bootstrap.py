"""R288: temporary owner-only SSH-key bootstrap and append-only auth tests.

All tests use disposable local fake owner dirs and dummy PUBLIC key bytes;
not a real SSH private key, EOA keystore, Docker daemon or live network.
"""
from pathlib import Path
import base64
import contextlib
import io
import os
import pwd
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r288_monitor_to_vm4714_ssh_publickey_bootstrap as r

BLOB=(b"\x00\x00\x00\x0bssh-ed25519"+
      b"\x00\x00\x00\x20"+bytes(range(32)))
PUB="ssh-ed25519 "+base64.b64encode(BLOB).decode("ascii")


class FakeSshKeygenResult:
    returncode=0


class TestR288OwnerSshTrust(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.uid=os.geteuid()
        app=self.home/".local"/"share"/"sse-v2-app-only"
        app.mkdir(parents=True,mode=0o700)
        app.chmod(0o700)
        self.app=app

    def client_dir(self):
        return self.app/"ssh"

    def client_keypair(self):
        d=self.client_dir()
        d.mkdir(mode=0o700)
        private=d/r.PRIVATE_FILENAME
        public=d/(r.PRIVATE_FILENAME+".pub")
        private.write_bytes(b"TEST_FAKE_PRIVATE_NOT_AN_SSH_KEY")
        private.chmod(0o600)
        public.write_text(PUB+" r288-test\n")
        public.chmod(0o644)
        return private,public

    def authorized(self):
        d=self.home/".ssh"
        d.mkdir(mode=0o700)
        d.chmod(0o700)
        p=d/"authorized_keys"
        return p

    def test_public_ed25519_key_fingerprint_and_strict_structure(self):
        key,fp=r._valid_public_key(PUB)
        self.assertEqual("ssh-ed25519 "+key,PUB)
        self.assertTrue(fp.startswith("SHA256:"))
        self.assertEqual(len(fp),50)

    def test_invalid_public_key_newline_wrong_type_or_blob_rejected(self):
        for pub in (
            "ssh-rsa "+base64.b64encode(BLOB).decode(),
            PUB+"\nssh-ed25519 evil",
            "ssh-ed25519 "+base64.b64encode(b"a"*51).decode(),
            "ssh-ed25519 notbase64",
            PUB+" extra trailing fields \n",
        ):
            with self.subTest(pub=pub[:24]),self.assertRaises(r.Refused):
                r._valid_public_key(pub)

    def test_client_preview_has_no_mutating_effects(self):
        out=r.client_preview(name="ayoubakrvm4711",uid=self.uid,home=self.home)
        self.assertFalse(out["privateIdentityExists"])
        self.assertFalse(out["sshIdentityGenerated"])
        self.assertFalse(self.client_dir().exists())

    def test_owner_client_public_only_reads_public_file(self):
        private,public=self.client_keypair()
        out=r.client_public(name="ayoubakrvm4712",uid=self.uid,home=self.home)
        self.assertEqual(out["publicKey"],PUB)
        self.assertFalse(out["sshPrivateKeyPrintedOrUploaded"])
        self.assertEqual(private.read_bytes(),b"TEST_FAKE_PRIVATE_NOT_AN_SSH_KEY")

    def test_client_create_requires_exact_phrase_before_ssh_keygen(self):
        called=[]
        with self.assertRaisesRegex(r.Refused,"authorization missing"):
            r.client_create(name="ayoubakrvm4713",uid=self.uid,home=self.home,
                confirm="NO",run=lambda *a,**k:called.append(a))
        self.assertFalse(called)
        self.assertFalse(self.client_dir().exists())

    def test_client_create_uses_fixed_local_ssh_keygen_no_private_stdout(self):
        def fake_run(args,**kwargs):
            self.assertEqual(args[0:7],
                ["ssh-keygen","-q","-t","ed25519","-a","16","-N"])
            self.assertEqual(args[7],"")
            self.assertFalse(kwargs["shell"])
            self.assertEqual(kwargs["stdout"],r.subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"],r.subprocess.DEVNULL)
            self.assertEqual(kwargs["stdin"],r.subprocess.DEVNULL)
            self.assertEqual(kwargs["timeout"],30)
            d,private,public=r.ssh_private_paths(self.home)
            private.write_bytes(b"NO_REAL_SECRET_TEST")
            private.chmod(0o600)
            public.write_text(PUB+" fake-monitor")
            public.chmod(0o644)
            return FakeSshKeygenResult()
        result=r.client_create(
            name="ayoubakrvm4711",uid=self.uid,home=self.home,
            confirm="CREATE-ONE-R288-VM4711-VM4714-SSH-ED25519",
            run=fake_run)
        self.assertEqual(result["sourceVm"],"vm4711")
        self.assertTrue(self.client_dir().is_dir())
        self.assertEqual(stat.S_IMODE(self.client_dir().stat().st_mode),0o700)
        self.assertEqual(result["publicKey"],PUB)

    def test_never_overwrite_existing_client_private_file(self):
        private,_=self.client_keypair()
        with self.assertRaisesRegex(r.Refused,"NEVER overwrite"):
            r.client_create(
                name="ayoubakrvm4711",uid=self.uid,home=self.home,
                confirm="CREATE-ONE-R288-VM4711-VM4714-SSH-ED25519",
                run=lambda *a,**k:self.fail("must not regenerate"))
        self.assertEqual(private.read_bytes(),b"TEST_FAKE_PRIVATE_NOT_AN_SSH_KEY")

    def test_provider_preview_no_authorized_keys_modification(self):
        out=r.provider_preview(name="ayoubakrvm4714",uid=self.uid,home=self.home)
        self.assertFalse(out["authorizedKeysExists"])
        self.assertFalse((self.home/".ssh").exists())

    def test_provider_restricted_authorized_keys_exact_one_key_and_ip(self):
        report=r.provider_authorize(
            name="ayoubakrvm4714",uid=self.uid,home=self.home,
            vm="vm4712",pub=PUB,
            confirm="AUTHORIZE-ONE-R288-VM4712-LOOPBACK-8877")
        self.assertTrue(report["addedAuthorizedKeysLine"])
        authorized=self.home/".ssh"/"authorized_keys"
        content=authorized.read_text()
        self.assertTrue(content.startswith(
            'from="10.50.56.19",restrict,port-forwarding,'
            'permitopen="127.0.0.1:8877",command="/usr/bin/true" '))
        self.assertIn(PUB,content)
        self.assertTrue(content.endswith("sse-r288-vm4712\n"))
        self.assertEqual(stat.S_IMODE(authorized.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(authorized.parent.stat().st_mode),0o700)

    def test_provider_authorize_second_identical_is_safe_noop(self):
        kwargs=dict(
            name="ayoubakrvm4714",uid=self.uid,home=self.home,
            vm="vm4711",pub=PUB,
            confirm="AUTHORIZE-ONE-R288-VM4711-LOOPBACK-8877")
        a=r.provider_authorize(**kwargs)
        text=(self.home/".ssh"/"authorized_keys").read_text()
        b=r.provider_authorize(**kwargs)
        self.assertTrue(a["addedAuthorizedKeysLine"])
        self.assertFalse(b["addedAuthorizedKeysLine"])
        self.assertTrue(b["alreadyPresentIdentical"])
        self.assertEqual(text,(self.home/".ssh"/"authorized_keys").read_text())

    def test_provider_append_preserves_previous_authorized_keys(self):
        existing=self.authorized()
        original="# owner original portal key preserved\n"
        existing.write_text(original)
        existing.chmod(0o600)
        r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
            home=self.home,vm="vm4713",pub=PUB,
            confirm="AUTHORIZE-ONE-R288-VM4713-LOOPBACK-8877")
        self.assertTrue(existing.read_text().startswith(original))

    def test_provider_duplicate_public_key_for_different_vm_fails_closed(self):
        r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
            home=self.home,vm="vm4711",pub=PUB,
            confirm="AUTHORIZE-ONE-R288-VM4711-LOOPBACK-8877")
        with self.assertRaisesRegex(r.Refused,"conflicts"):
            r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
                home=self.home,vm="vm4712",pub=PUB,
                confirm="AUTHORIZE-ONE-R288-VM4712-LOOPBACK-8877")

    def test_provider_refuses_symlink_authorized_keys_and_private_dir(self):
        other=self.home/"other"
        other.write_text("keep unchanged\n")
        directory=self.home/".ssh"
        directory.mkdir(mode=0o700)
        (directory/"authorized_keys").symlink_to(other)
        with self.assertRaisesRegex(r.Refused,"symlink"):
            r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
                home=self.home,vm="vm4712",pub=PUB,
                confirm="AUTHORIZE-ONE-R288-VM4712-LOOPBACK-8877")
        self.assertEqual(other.read_text(),"keep unchanged\n")

    def test_provider_refuses_existing_nonprivate_authorized_keys(self):
        p=self.authorized()
        p.write_text("existing nonprivate\n")
        p.chmod(0o644)
        with self.assertRaisesRegex(r.Refused,"mode0600"):
            r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
                home=self.home,vm="vm4713",pub=PUB,
                confirm="AUTHORIZE-ONE-R288-VM4713-LOOPBACK-8877")
        self.assertEqual(p.read_text(),"existing nonprivate\n")

    def test_provider_does_not_rewrite_existing_unterminated_entry(self):
        p=self.authorized()
        p.write_text("original without newline")
        p.chmod(0o600)
        with self.assertRaisesRegex(r.Refused,"lacks newline"):
            r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
                home=self.home,vm="vm4711",pub=PUB,
                confirm="AUTHORIZE-ONE-R288-VM4711-LOOPBACK-8877")
        self.assertEqual(p.read_text(),"original without newline")

    def test_authorization_phrase_rejects_before_creating_dot_ssh(self):
        with self.assertRaisesRegex(r.Refused,"exact one-key"):
            r.provider_authorize(name="ayoubakrvm4714",uid=self.uid,
                home=self.home,vm="vm4711",pub=PUB,confirm="WRONG")
        self.assertFalse((self.home/".ssh").exists())

    def test_reject_wrong_vm_owner_and_unknown_source_vm(self):
        with self.assertRaisesRegex(r.Refused,"only provider"):
            r.provider_authorize(name="ayoubakrvm4711",uid=self.uid,
                home=self.home,vm="vm4711",pub=PUB,confirm="X")
        with self.assertRaisesRegex(r.Refused,"only three"):
            r.restricted_entry("vm4709",PUB)

    def test_main_rejects_missing_mode_and_does_not_start_ssh(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                r.main([])
        self.assertEqual(caught.exception.code,2)


if __name__=="__main__":
    unittest.main()
