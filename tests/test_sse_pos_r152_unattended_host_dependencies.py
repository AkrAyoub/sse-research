"""R152 host provisioning unit coverage — zero package installs or network calls."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r152_unattended_host_dependencies as m

class HostDependencies(unittest.TestCase):
    def test_real_host_prerequisite_failures_have_safe_stages(self):
        import subprocess
        cases=[
            (["apt-get","update","-qq"],"APT_UPDATE"),
            (["apt-get","install","-y","docker.io"],"APT_DOCKER_GNUPG"),
            (["systemctl","enable","--now","zerotier-one"],"ZEROTIER_DAEMON"),
            (["bash","/tmp/vendor.sh"],"ZEROTIER_VENDOR_INSTALL"),
            (["zerotier-cli","join",m.NETWORK],"ZEROTIER_JOIN"),
            (["docker","pull","image@sha256:abc"],"PINNED_CLIENT_IMAGE_PULL"),
        ]
        for argv,stage in cases:
            with (self.subTest(stage=stage),
                  patch.object(m.subprocess,"run",return_value=
                      subprocess.CompletedProcess(argv,42,"SENSITIVE","PRIVATE_TOKEN"))):
                with self.assertRaisesRegex(m.Refused,"R152_"+stage+"_EXIT_42") as failure:
                    m.call(argv)
                self.assertNotIn("SENSITIVE",str(failure.exception))
                self.assertNotIn("PRIVATE_TOKEN",str(failure.exception))


    def test_signed_vendor_fetch_failure_identifies_artifact_without_secrets(self):
        import urllib.error
        for url,stage in (
            (m.VENDOR_KEY,"ZEROTIER_SIGNING_KEY_DOWNLOAD"),
            (m.VENDOR_SCRIPT,"ZEROTIER_SIGNED_INSTALLER_DOWNLOAD"),
        ):
            for error,expected in (
                (urllib.error.HTTPError(url,404,"missing",{},None),"HTTP_404"),
                (urllib.error.URLError("private diagnostic"),"TRANSPORT_UNAVAILABLE"),
            ):
                with (self.subTest(stage=stage,expected=expected),
                      patch.object(m.urllib.request,"urlopen",side_effect=error)):
                    with self.assertRaisesRegex(
                            m.Refused,"R152_"+stage+"_"+expected) as failure:
                        m.fetch_https(url)
                    self.assertNotIn("private diagnostic",str(failure.exception))

    def test_apt_metadata_preflight_is_readonly_and_requires_clearsign(self):
        valid=b"-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n"
        observed=m.verify_vendor_repo_metadata(getter=lambda url:valid)
        self.assertTrue(observed["officialNobleRepoMetadataReachable"])
        self.assertFalse(observed["aptOrServiceStateModified"])
        with self.assertRaisesRegex(m.Refused,"NOT_CLEAR_SIGNED"):
            m.verify_vendor_repo_metadata(getter=lambda url:b"HTML blocked page")
        import urllib.error
        with self.assertRaisesRegex(m.Refused,"METADATA_HTTP_403"):
            m.verify_vendor_repo_metadata(getter=lambda url:(
                (_ for _ in ()).throw(
                    urllib.error.HTTPError(url,403,"blocked",{},None))))

    def test_r177_repo_line_has_actual_newline_not_literal_backslash_n(self):
        self.assertTrue(m.ZEROTIER_APT_LINE.endswith(chr(10)))
        self.assertFalse(m.ZEROTIER_APT_LINE.endswith(chr(92)+"n"))
        self.assertEqual(
            m.ZEROTIER_APT_R175_BAD_LINE,
            m.ZEROTIER_APT_LINE[:-1]+chr(92)+"n")

    def test_r177_only_exact_existing_malformed_repo_line_is_repaired(self):
        import unittest.mock
        calls=[]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            keyring=root/"key.gpg"
            source=root/"zero.list"
            source.write_bytes(m.ZEROTIER_APT_R175_BAD_LINE.encode("ascii"))
            def runner(argv,**kw):
                calls.append(argv)
                if "--fingerprint" in argv:
                    return "pub::::::::::"+chr(10)+"fpr:::::::::"+m.VENDOR_FINGERPRINT+":"+chr(10)
                if "--dearmor" in argv:
                    Path(argv[argv.index("--output")+1]).write_bytes(b"PUBLIC_KEY_FIXTURE")
                return ""
            with (patch.object(m.os,"geteuid",return_value=0),
                  patch.object(m,"verify_vendor_repo_metadata",
                               return_value={"officialNobleRepoMetadataReachable":True}),
                  patch.object(m.Path,"is_file",autospec=True,
                               side_effect=lambda obj:(
                                   True if str(obj)=="/usr/sbin/zerotier-one"
                                   else Path.exists(obj) and not Path.is_dir(obj)))):
                self.assertTrue(m.install_verified_zerotier_apt(
                    runner=runner,fetcher=lambda url:b"PUBLIC_GPG_FIXTURE",
                    keyring=keyring,source=source))
                self.assertEqual(source.read_bytes(),m.ZEROTIER_APT_LINE.encode("ascii"))
                # Idempotent on the already repaired source.
                self.assertTrue(m.install_verified_zerotier_apt(
                    runner=runner,fetcher=lambda url:b"PUBLIC_GPG_FIXTURE",
                    keyring=keyring,source=source))
            self.assertEqual(keyring.read_bytes(),b"PUBLIC_KEY_FIXTURE")
            self.assertTrue(any("zerotier-one" in cmd for cmd in calls))

    def test_r177_refuses_to_rewrite_unrecognized_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"zero.list"
            keyring=root/"key.gpg"
            source.write_text("deb https://untrusted.example invalid main"+chr(10))
            def runner(argv,**kw):
                if "--fingerprint" in argv:
                    return "pub::::::::::"+chr(10)+"fpr:::::::::"+m.VENDOR_FINGERPRINT+":"+chr(10)
                if "--dearmor" in argv:
                    Path(argv[argv.index("--output")+1]).write_bytes(b"PUBLIC_KEY_FIXTURE")
                return ""
            with (patch.object(m.os,"geteuid",return_value=0),
                  patch.object(m,"verify_vendor_repo_metadata",
                               return_value={"officialNobleRepoMetadataReachable":True}),
                  self.assertRaisesRegex(m.Refused,"CONFIG_CONFLICT")):
                m.install_verified_zerotier_apt(
                    runner=runner,fetcher=lambda url:b"PUBLIC_GPG_FIXTURE",
                    keyring=keyring,source=source)
            self.assertEqual(source.read_text(),
                             "deb https://untrusted.example invalid main"+chr(10))

    def test_upstream_noble_repo_is_https_and_scoped_signature(self):
        self.assertEqual(m.ZEROTIER_APT_URL,
                         "https://download.zerotier.com/debian/noble")
        self.assertIn("signed-by=/usr/share/keyrings/sse-zerotier.gpg",
                      m.ZEROTIER_APT_LINE)
        self.assertIn(" noble main",m.ZEROTIER_APT_LINE)
        self.assertNotIn("trusted=yes",m.ZEROTIER_APT_LINE)
        self.assertEqual(m.stage_of(["apt-get","install","-y","zerotier-one"]),
                         "ZEROTIER_SIGNED_APT_INSTALL")

    def test_verified_apt_repo_install_uses_pinned_primary_key_and_apt(self):
        calls=[]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            keyring=root/"keyring.gpg"
            source=root/"zerotier.list"
            def runner(argv,**kw):
                calls.append(argv)
                if "--fingerprint" in argv:
                    return "pub::::::::::\n"+"fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n"
                if "--dearmor" in argv:
                    Path(argv[argv.index("--output")+1]).write_bytes(b"DEARMORED_TEST_FIXTURE")
                return ""
            with (patch.object(m.os,"geteuid",return_value=0),
                  patch.object(m,"verify_vendor_repo_metadata",
                               return_value={"officialNobleRepoMetadataReachable":True}),
                  patch.object(m.Path,"is_file",autospec=True,
                               side_effect=lambda obj:(
                                   True if str(obj)=="/usr/sbin/zerotier-one"
                                   else Path.exists(obj) and not Path.is_dir(obj)))):
                self.assertTrue(m.install_verified_zerotier_apt(
                    runner=runner,fetcher=lambda url:b"PUBLIC_GPG_TEST_FIXTURE",
                    keyring=keyring,source=source))
            self.assertEqual(keyring.read_bytes(),b"DEARMORED_TEST_FIXTURE")
            self.assertEqual(source.read_text(),m.ZEROTIER_APT_LINE)
            self.assertIn(["apt-get","update","-qq"],calls)
            self.assertTrue(any(argv[:2]==["apt-get","install"]
                                and "zerotier-one" in argv for argv in calls))
            self.assertFalse(any("install.zerotier.com" in " ".join(argv)
                                 for argv in calls))

    def test_verified_apt_requires_pinned_primary_key_and_never_writes_on_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            keyring=root/"keyring.gpg"
            source=root/"zt.list"
            def runner(argv,**kw):
                if "--fingerprint" in argv:
                    return "pub::::::::::\nfpr:::::::::DEADBEEF:\n"
                return ""
            with (patch.object(m.os,"geteuid",return_value=0),
                  patch.object(m,"verify_vendor_repo_metadata",
                               return_value={"officialNobleRepoMetadataReachable":True}),
                  self.assertRaises(m.Refused)):
                m.install_verified_zerotier_apt(
                    runner=runner,fetcher=lambda url:b"UNTRUSTED_GPG",
                    keyring=keyring,source=source)
            self.assertFalse(keyring.exists())
            self.assertFalse(source.exists())

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
                return "pub::::::::::\n"+"fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n"
            if "--decrypt" in argv:
                path=Path(argv[argv.index("--output")+1])
                path.write_bytes(b"#!/bin/sh\necho vendor-signed\n")
            return ""
        script=m.verify_official_install_script(b"key",b"signed",runner=runner)
        self.assertEqual(script,b"#!/bin/sh\necho vendor-signed\n")

    def test_legitimate_primary_key_with_subkey_is_accepted(self):
        gpg=("pub::::::::::\n"
             "fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n"
             "sub::::::::::\n"
             "fpr:::::::::1234567890123456789012345678901234567890:\n")
        self.assertTrue(m.verify_primary_vendor_key_fingerprint(gpg))

    def test_two_different_primary_certificates_are_not_accepted(self):
        gpg=("pub::::::::::\n"
             "fpr:::::::::"+m.VENDOR_FINGERPRINT+":\n"
             "pub::::::::::\n"
             "fpr:::::::::1234567890123456789012345678901234567890:\n")
        with self.assertRaises(m.Refused):
            m.verify_primary_vendor_key_fingerprint(gpg)

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
