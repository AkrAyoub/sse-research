#!/usr/bin/env python3
"""R291 owner-consented new-VM-only signed APT ZeroTier transport package.

This is NOT a permissionless enrollment/role whitelist: the lab-only root
package INSTALLER safeguards existing original PoS owners. Any external
operator can independently install ZeroTier and join the same controllerless
ad-hoc public IPv6 network without project-owner account/approval.
Invoked only by checked-in scripts/r291_vm4711_4714_signed_overlay_install.sh
after a local exact-sha clean-checkout gate and explicit human TTY consent.
NO Docker install, original EL/CL/VC, private keys, genesis, SSH trust,
firewall, external listeners, chain transaction, or cloud private route.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import sse_pos_r152_unattended_host_dependencies as vendor
import sse_pos_r291_common_public_overlay_onboarding as overlay

SAFE_OWNERS=frozenset({
    "ayoubakrvm4711","ayoubakrvm4712",
    "ayoubakrvm4713","ayoubakrvm4714"
})


class Refused(ValueError):
    pass


def guarded_root_environment(*,geteuid=os.geteuid,environ=None,os_release=None,
                             machine=platform.machine):
    if environ is None:
        environ=os.environ
    if os_release is None:
        os_release=platform.freedesktop_os_release
    if geteuid()!=0 or environ.get("SUDO_USER") not in SAFE_OWNERS:
        raise Refused("only existing four dedicated non-PoS VM owners through sudo")
    if environ.get("SUDO_UID") in (None,"","0"):
        raise Refused("real nonroot sudo invoking account required")
    release=os_release()
    if (release.get("ID")!="ubuntu" or release.get("VERSION_ID")!="24.04" or
        machine()!="x86_64"):
        raise Refused("verified vendor APT installer only on Ubuntu24.04 x86_64")
    if vendor.NETWORK!=overlay.NETWORK_ID:
        raise Refused("existing original public network differs across source")
    return environ["SUDO_USER"]


def strict_source_revision(expected,*,run=subprocess.run):
    if (type(expected) is not str or len(expected)!=40 or
        any(c not in "0123456789abcdef" for c in expected)):
        raise Refused("require reviewed immutable full SHA")
    for command,exact in (
        (["git","rev-parse","HEAD"],expected+"\n"),
        (["git","status","--porcelain"],""),
    ):
        try:
            p=run(command,capture_output=True,text=True,shell=False,
                  timeout=8,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise Refused("source tree revision could not be verified") from exc
        if p.returncode!=0 or p.stdout!=exact:
            raise Refused("Git checkout changed or not clean; refuse privileged source")
    return True


def signed_package_command(argv,*,timeout=240,run=subprocess.run):
    """Only vetted GPG + apt native client install, no automatic service restarts.

    R152's generic runner sets NEEDRESTART_MODE=a, which is inappropriate
    for VM4714 with an already running compute workload. This package-only
    wrapper overrides it to 'l' (list, never automatic restarts).
    """
    if type(argv) is not list or not argv or any(type(x) is not str for x in argv):
        raise Refused("invalid signed package command")
    if argv[0]=="gpg":
        if argv[1:3] not in (
            ["--batch","--homedir"],["--batch","--yes"]
        ):
            raise Refused("unreviewed GPG command")
    elif argv==["apt-get","update","-qq"]:
        pass
    elif argv==["apt-get","install","-y","-qq",
                 "--no-install-recommends","zerotier-one"]:
        pass
    else:
        raise Refused("only official signed ZeroTier package APT commands allowed")
    env={**os.environ,
         "DEBIAN_FRONTEND":"noninteractive",
         "NEEDRESTART_MODE":"l",
         "APT_LISTCHANGES_FRONTEND":"none",
         "GIT_TERMINAL_PROMPT":"0"}
    try:
        p=run(argv,capture_output=True,text=True,shell=False,
              check=False,timeout=timeout,env=env)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("bounded signed-package helper unavailable") from exc
    if p.returncode!=0:
        raise Refused("signed ZeroTier package operation failed with exit "+str(p.returncode))
    return p.stdout


def install_package_only():
    # Reuse exact R175/R177 signed APT installer, never vendor.setup().
    return vendor.install_verified_zerotier_apt(runner=signed_package_command)


def install(*,sha,root_guard=guarded_root_environment,
            revision_guard=strict_source_revision,which=shutil.which,
            vendor_install=install_package_only,
            vendor_run=vendor.call,zt_installed_fn=None):
    user=root_guard()
    revision_guard(sha)
    overlay.protocol_guard()
    if zt_installed_fn is None:
        zt_installed_fn=lambda:Path("/usr/sbin/zerotier-one").exists()
    if which("zerotier-cli") is not None or zt_installed_fn():
        raise Refused("ZeroTier already present; use read-only status, never reinstall")
    if not all(which(x) for x in ("gpg","apt-get","systemctl")):
        raise Refused("required signed APT/gpg/systemd prerequisites missing")
    if vendor.VENDOR_FINGERPRINT!="74A5E9C458E1A431F1DA57A71657198823E52A61":
        raise Refused("original verified vendor signing key pin changed")
    if vendor.ZEROTIER_APT_URL!="https://download.zerotier.com/debian/noble":
        raise Refused("original signed APT vendor URL changed")
    # The previously VM4709-reviewed R175/R177 exact vendor key, signed
    # noble repository metadata, scoped signed-by, apt Release signature.
    # This helper ONLY installs zerotier-one; never calls vendor.setup()
    # (which would otherwise install Docker/full nodes, pull images).
    vendor_install()
    vendor_run(["systemctl","enable","--now","zerotier-one"],timeout=80)
    return {
        "schema":"SSE_R291_NEW_DEDICATED_VM_SIGNED_APT_ONLY_V1",
        "dedicatedNewLabHost":user,
        "reviewedExactGitSourceCommit":sha,
        "officialGpgFingerprintAndScopedSignedAptRequired":True,
        "vendorZerotierPackageInstalled":True,
        "daemonEnableStartCommandSucceeded":True,
        "publicOverlayNetworkJoinAttempted":False,
        "nativeElClDockerOrValidatorModifiedByThisTool":False,
        "ethereumOrSshKeyRead":False,
        "providerRawHttpExposed":False,
        "nativeTransactionSignedOrSubmitted":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--install-after-owner-consent",action="store_true",required=True)
    p.add_argument("--expected-commit",required=True)
    a=p.parse_args(argv)
    try:
        print(json.dumps(install(sha=a.expected_commit),indent=2,sort_keys=True))
        print("R291_SIGNED_ZEROTIER_ONLY_INSTALL_NO_DOCKER_NO_CHAIN=true")
        return 0
    except (Refused,vendor.Refused,ValueError,TypeError,KeyError,OSError) as exc:
        print("R291_SIGNED_APT_ONLY_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
