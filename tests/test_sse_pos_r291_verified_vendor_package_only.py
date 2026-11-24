"""R291 signed package-only root helper; fully mocked NO real apt, sudo or Docker."""
from pathlib import Path
import contextlib
import io
import os
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r291_verified_vendor_package_only as m


SHA="e"*40


def safe_root():
    return "ayoubakrvm4714"


def which(command):
    if command=="zerotier-cli":
        return None
    if command in ("gpg","apt-get","systemctl"):
        return "/usr/bin/"+command
    return None


class TestR291ExistingVendorSignedAptOnly(unittest.TestCase):
    def test_only_new_nonpos_sudo_owner_permitted(self):
        for args in (
            dict(geteuid=lambda:1001,environ={"SUDO_USER":"ayoubakrvm4714","SUDO_UID":"1001"}),
            dict(geteuid=lambda:0,environ={"SUDO_USER":"ayoubakrvm4706","SUDO_UID":"1001"}),
            dict(geteuid=lambda:0,environ={"SUDO_USER":"ayoubakrvm4714","SUDO_UID":"0"}),
        ):
            with self.subTest(args=args),self.assertRaises(m.Refused):
                m.guarded_root_environment(
                    **args,os_release=lambda:{"ID":"ubuntu","VERSION_ID":"24.04"},
                    machine=lambda:"x86_64")

    def test_exact_ubuntu_2404_amd64_only(self):
        for release,arch in (
            ({"ID":"ubuntu","VERSION_ID":"22.04"},"x86_64"),
            ({"ID":"debian","VERSION_ID":"12"},"x86_64"),
            ({"ID":"ubuntu","VERSION_ID":"24.04"},"aarch64"),
        ):
            with self.subTest(release=release,arch=arch),self.assertRaises(m.Refused):
                m.guarded_root_environment(
                    geteuid=lambda:0,
                    environ={"SUDO_USER":"ayoubakrvm4714","SUDO_UID":"1001"},
                    os_release=lambda:release,machine=lambda:arch)
        self.assertEqual(m.guarded_root_environment(
            geteuid=lambda:0,
            environ={"SUDO_USER":"ayoubakrvm4714","SUDO_UID":"1001"},
            os_release=lambda:{"ID":"ubuntu","VERSION_ID":"24.04"},
            machine=lambda:"x86_64"),"ayoubakrvm4714")

    def test_invalid_git_revision_refuses_before_any_git_process(self):
        with self.assertRaisesRegex(m.Refused,"full SHA"):
            m.strict_source_revision("main",run=lambda *_args,**_kw:
                                     self.fail("no git expected"))

    def test_exact_reviewed_sha_and_clean_checkout_required(self):
        actions=[]
        def git(argv,**kwargs):
            actions.append(argv)
            return subprocess.CompletedProcess(argv,0,
                   SHA+"\n" if argv==["git","rev-parse","HEAD"] else "","")
        self.assertTrue(m.strict_source_revision(SHA,run=git))
        self.assertEqual(actions,[
            ["git","rev-parse","HEAD"],["git","status","--porcelain"]
        ])

    def test_dirty_checkout_refuses_privileged_package(self):
        def git(argv,**kwargs):
            return subprocess.CompletedProcess(argv,0,
                SHA+"\n" if argv[1]=="rev-parse" else " M tools/abc\n","")
        with self.assertRaisesRegex(m.Refused,"not clean"):
            m.strict_source_revision(SHA,run=git)

    def test_package_only_calls_old_verified_vendor_then_systemd_and_no_join(self):
        calls=[]
        report=m.install(
            sha=SHA,root_guard=safe_root,
            revision_guard=lambda s:calls.append(("revision",s)),
            which=which,zt_installed_fn=lambda:False,
            vendor_install=lambda:calls.append(("signed_vendor_apt",)),
            vendor_run=lambda argv,timeout: calls.append(("service",argv,timeout)))
        self.assertEqual(calls,[
            ("revision",SHA),
            ("signed_vendor_apt",),
            ("service",["systemctl","enable","--now","zerotier-one"],80)
        ])
        self.assertTrue(report["vendorZerotierPackageInstalled"])
        self.assertFalse(report["publicOverlayNetworkJoinAttempted"])
        self.assertFalse(report["nativeElClDockerOrValidatorModifiedByThisTool"])
        self.assertFalse(report["nativeTransactionSignedOrSubmitted"])

    def test_already_installed_refused_no_new_apt(self):
        with self.assertRaisesRegex(m.Refused,"already present"):
            m.install(
                sha=SHA,root_guard=safe_root,revision_guard=lambda x:True,
                which=lambda name: "/usr/bin/zerotier-cli" if name=="zerotier-cli"
                        else which(name),
                zt_installed_fn=lambda:False,
                vendor_install=lambda:self.fail("must never apt"))
        with self.assertRaisesRegex(m.Refused,"already present"):
            m.install(
                sha=SHA,root_guard=safe_root,revision_guard=lambda x:True,
                which=which,zt_installed_fn=lambda:True,
                vendor_install=lambda:self.fail("must never apt"))

    def test_missing_signed_apt_prerequisites_fails_closed(self):
        with self.assertRaisesRegex(m.Refused,"prerequisites"):
            m.install(sha=SHA,root_guard=safe_root,
                revision_guard=lambda x:True,
                which=lambda name:None,zt_installed_fn=lambda:False,
                vendor_install=lambda:self.fail("must never apt"))

    def test_source_only_checked_wrapper_mentions_no_docker_mutation(self):
        body=(ROOT/"scripts/r291_vm4711_4714_signed_overlay_install.sh").read_text()
        self.assertIn("sudo -n /usr/bin/python3 -B",body)
        self.assertIn("INSTALL-ONE-R291-SIGNED-ZEROTIER-ONLY",body)
        self.assertIn("git status --porcelain",body)
        self.assertNotIn("docker run",body)
        self.assertNotIn("docker stop",body)
        self.assertNotIn("ssh-keygen",body)
        self.assertNotIn("10.50.56.",body)

    def test_signed_package_only_never_auto_restarts_other_vm_services(self):
        observed=[]
        def fake_run(argv,**kwargs):
            observed.append((argv,kwargs))
            return subprocess.CompletedProcess(argv,0,"OK","")
        result=m.signed_package_command(
            ["apt-get","install","-y","-qq",
             "--no-install-recommends","zerotier-one"],run=fake_run)
        self.assertEqual(result,"OK")
        self.assertEqual(observed[0][1]["env"]["NEEDRESTART_MODE"],"l")
        self.assertEqual(observed[0][1]["env"]["DEBIAN_FRONTEND"],"noninteractive")
        self.assertFalse(observed[0][1]["shell"])

    def test_signed_package_runner_rejects_docker_or_unreviewed_apt(self):
        for argv in (
            ["docker","restart","sse-compute-vm4714"],
            ["apt-get","install","-y","docker.io"],
            ["systemctl","restart","docker"],
            ["bash","https://install.zerotier.com"],
        ):
            with self.subTest(argv=argv),self.assertRaisesRegex(
                m.Refused,"only official signed ZeroTier"):
                m.signed_package_command(argv,run=lambda *args,**kwargs:
                    self.fail("unreviewed command must not execute"))

    def test_cli_requires_install_mode_and_explicit_revision(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                m.main([])
        self.assertEqual(exc.exception.code,2)


if __name__=="__main__":
    unittest.main()
