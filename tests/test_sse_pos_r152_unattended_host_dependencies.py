"""R152 host provisioning unit coverage — zero package installs or network calls."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r152_unattended_host_dependencies as m

class HostDependencies(unittest.TestCase):
    def test_plan_no_system_change(self):
        with patch.object(m.os,"geteuid",return_value=0):
            result=m.setup()
        self.assertFalse(result["installed"])
        self.assertFalse(result["imagesPulled"])
        self.assertFalse(result["overlayJoined"])

    def test_not_root_refused_before_mutation(self):
        called=[]
        with patch.object(m.os,"geteuid",return_value=1000),self.assertRaises(m.Refused):
            m.setup(execute=True,runner=lambda args,**kwargs:called.append(args))
        self.assertEqual(called,[])

    def test_vendor_key_uses_confirmed_official_upstream_path(self):
        self.assertEqual(
            m.VENDOR_KEY,
            "https://raw.githubusercontent.com/zerotier/ZeroTierOne/master/doc/contact%40zerotier.com.gpg")
        self.assertEqual(
            m.VENDOR_FINGERPRINT,
            "74A5E9C458E1A431F1DA57A71657198823E52A61")

    def test_urls_are_vendor_exact_only(self):
        with self.assertRaises(m.Refused):
            m.fetch_https("http://install.zerotier.com")
        with self.assertRaises(m.Refused):
            m.fetch_https("https://attacker.example/zerotier")

    def test_gpg_refuses_untrusted_release_signing_key(self):
        def runner(argv,**kwargs):
            if "--fingerprint" in argv:
                return "fpr:::::::::DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF:\n"
            return ""
        with self.assertRaises(m.Refused):
            m.verify_official_install_script(b"key",b"signed",runner=runner)

    def test_gpg_requires_only_single_exact_signer(self):
        def runner(argv,**kwargs):
            if "--fingerprint" in argv:
                return ("fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n"
                        "fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n")
            return ""
        with self.assertRaises(m.Refused):
            m.verify_official_install_script(b"key",b"signed",runner=runner)

    def test_exact_signer_verifies_and_returns_only_signed_plaintext(self):
        def runner(argv,**kwargs):
            if "--fingerprint" in argv:
                return "fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n"
            if "--decrypt" in argv:
                path=Path(argv[argv.index("--output")+1])
                path.write_bytes(b"#!/bin/sh\necho vendor-signed\n")
            return ""
        script=m.verify_official_install_script(b"key",b"signed",runner=runner)
        self.assertEqual(script,b"#!/bin/sh\necho vendor-signed\n")

    def test_install_command_bounded_and_actual_client_pins(self):
        calls=[]
        def runner(argv,**kwargs):
            calls.append(argv)
            return ""
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.Path,"exists",return_value=True), \
             patch.object(m.r59,"images") as images, \
             patch.object(m.r59,"overlay_ip",return_value=("ztrb6cq527","fca0::1")):
            result=m.setup(execute=True,runner=runner,fetcher=lambda _:b"never")
        self.assertTrue(result["imagesPulled"])
        self.assertFalse(result["nativeElClP2pVerified"])
        self.assertIn(["zerotier-cli","join",m.NETWORK],calls)
        self.assertIn(["docker","pull",m.r59.BESU_REF],calls)
        self.assertIn(["docker","pull",m.r59.LIGHTHOUSE_REF],calls)
        images.assert_called_once()

    def test_preexisting_vendor_client_is_not_reinstalled(self):
        calls=[]
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.Path,"exists",return_value=True), \
             patch.object(m.r59,"images"), \
             patch.object(m.r59,"overlay_ip",return_value=("ztabcde123","fca0::2")):
            m.setup(execute=True,runner=lambda argv,**kw:calls.append(argv) or "")
        self.assertFalse(any("install.zerotier.com" in " ".join(c) for c in calls))

    def test_actual_overlay_address_required_not_bogus_join_success(self):
        def runner(argv,**kwargs):
            return ""
        with patch.object(m.os,"geteuid",return_value=0), \
             patch.object(m.Path,"exists",return_value=True), \
             patch.object(m.r59,"images"), \
             patch.object(m.r59,"overlay_ip",side_effect=m.r59.R59Refused("not assigned")), \
             patch.object(m.time,"sleep") as sleep:
            with self.assertRaises(m.Refused):
                m.setup(execute=True,runner=runner)
        self.assertEqual(sleep.call_count,11)

if __name__=="__main__":
    unittest.main()
