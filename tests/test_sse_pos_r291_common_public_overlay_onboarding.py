"""R291 source-only guarded open-join transport tests; no real sudo/network."""
from pathlib import Path
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r291_common_public_overlay_onboarding as m


ADDRESS="fca0:2328:77b8:6578:a55::1/40"
INTERFACE="ztrb6cq527"


def runner(*,installed=True,online=True,joined=True,healthy=True,
           public=True,addr=ADDRESS,iface=INTERFACE,joins=None):
    commands=[]
    join_count=[0]
    def call(argv,**kwargs):
        commands.append(argv)
        if kwargs["shell"] is not False:
            raise AssertionError("shell command forbidden")
        if argv[:5]==["sudo","-n","zerotier-cli","-j","info"]:
            return subprocess.CompletedProcess(argv,0,
                json.dumps({"online":online}),"")
        if argv[:5]==["sudo","-n","zerotier-cli","-j","listnetworks"]:
            present=joined or join_count[0]>0
            payload=([{
                "nwid":m.NETWORK_ID,
                "type":"PUBLIC" if public else "PRIVATE",
                "status":"OK" if healthy else "REQUESTING_CONFIGURATION",
                "assignedAddresses":[addr] if addr else [],
                "portDeviceName":iface,
            }] if present else [])
            return subprocess.CompletedProcess(argv,0,json.dumps(payload),"")
        if argv==["sudo","-n","zerotier-cli","join",m.NETWORK_ID]:
            join_count[0]+=1
            return subprocess.CompletedProcess(argv,0,"200 join OK","")
        raise AssertionError("unreviewed sudo or networking command "+repr(argv))
    return (call,commands,
            lambda x:"/usr/sbin/zerotier-cli" if installed else None,
            join_count)


class FakeTty:
    def __init__(self,value):
        self.value=value
    def isatty(self):
        return self.value


class TestR291RealOpenControllerlessTransportPolicies(unittest.TestCase):
    def test_open_adhoc_id_covers_native_p2p_and_observation(self):
        p=m.protocol_guard()
        self.assertEqual(p["publicControllerlessZeroTierNetworkId"],
                         "ff2328775f000000")
        self.assertEqual(p["destinationPortMaximum"],30559)
        self.assertTrue(p["networkControllerInvitationRequired"] is False)
        self.assertTrue(p["originalNativeLighthouseP2pPortsIncluded"])
        self.assertTrue(p["originalNativeBesuP2pPortsIncluded"])
        self.assertTrue(p["futureAuthenticatedProviderPort29080Included"])

    def test_same_public_ipv6_overlay_ready_does_not_claim_native_peer(self):
        run,commands,which,_=runner()
        report=m.status(run=run,which=which)
        self.assertTrue(report["actualOpenOverlayReadyForCrossHostTransport"])
        self.assertEqual(report["assignedActual6planeIpv6"],
                         "fca0:2328:77b8:6578:a55::1")
        self.assertEqual(report["actualOverlayInterface"],INTERFACE)
        self.assertFalse(report["nativeBesuLighthousePeerHandshakeVerified"])
        self.assertFalse(report["physicalIndependentInternetIspVerified"])
        self.assertFalse(report["providerSignedHttpsEndpointVerified"])
        self.assertFalse(report["private10Dot50InfrastructureAddressUsedForDataPlane"])
        self.assertEqual(len(commands),2)

    def test_uninstalled_zero_tier_is_no_mutating_command(self):
        run,commands,which,_=runner(installed=False)
        result=m.status(run=run,which=which)
        self.assertFalse(result["zerotierClientInstalled"])
        self.assertFalse(result["actualOpenOverlayReadyForCrossHostTransport"])
        self.assertEqual(commands,[])

    def test_not_online_is_not_ready(self):
        run,_,which,_=runner(online=False)
        result=m.status(run=run,which=which)
        self.assertFalse(result["daemonReportsOnline"])
        self.assertFalse(result["actualOpenOverlayReadyForCrossHostTransport"])

    def test_nonpublic_overlay_and_unhealthy_refuse_readiness(self):
        for opts in ({"public":False},{"healthy":False},
                     {"addr":None},{"iface":"unexpected0"}):
            with self.subTest(opts=opts):
                run,_,which,_=runner(**opts)
                result=m.status(run=run,which=which)
                self.assertFalse(result["actualOpenOverlayReadyForCrossHostTransport"])

    def test_private_ipv4_cannot_be_overlay_address(self):
        run,_,which,_=runner(addr="10.50.56.22/24")
        report=m.status(run=run,which=which)
        self.assertFalse(report["actualOpenOverlayReadyForCrossHostTransport"])
        self.assertIsNone(report["assignedActual6planeIpv6"])

    def test_different_controllerless_network_refused_without_unsafe_join(self):
        run,commands,which,_=runner(joined=False)
        def swapped(argv,**kwargs):
            result=run(argv,**kwargs)
            if argv[-1]=="listnetworks":
                result.stdout=json.dumps([{"nwid":"ff99999999999999",
                                           "type":"PUBLIC","status":"OK"}])
            return result
        report=m.status(run=swapped,which=which)
        self.assertFalse(report["networkIsJoined"])
        self.assertFalse(report["actualOpenOverlayReadyForCrossHostTransport"])
        self.assertEqual(len(commands),2)

    def test_join_without_zero_tier_refuses_before_any_sudo_mutation(self):
        run,commands,which,_=runner(installed=False)
        with self.assertRaisesRegex(m.Refused,"client absent"):
            m.join(run=run,which=which,
                   owner_guard=lambda:"unrelated-external-operator")
        self.assertEqual(commands,[])

    def test_join_noninteractive_refuses_before_any_network_change(self):
        run,commands,which,_=runner(joined=False)
        with self.assertRaisesRegex(m.Refused,"operator terminal"):
            m.join(run=run,which=which,
                   stdin=FakeTty(False),stderr=FakeTty(True),
                   owner_guard=lambda:"new-independent-user")
        self.assertEqual(len(commands),2)
        self.assertFalse(any("join" in c for c in commands))

    def test_offline_daemon_refuses_join_before_local_tty_or_write(self):
        run,commands,which,join_count=runner(joined=False,online=False)
        with self.assertRaisesRegex(m.Refused,"daemon is not online"):
            m.join(run=run,which=which,
                   stdin=FakeTty(True),stderr=FakeTty(True),
                   input_fn=lambda p:self.fail("offline daemon must not ask consent"),
                   owner_guard=lambda:"outside-operator")
        self.assertEqual(join_count[0],0)
        self.assertEqual(len(commands),2)

    def test_exact_local_tty_consent_required(self):
        run,commands,which,_=runner(joined=False)
        with self.assertRaisesRegex(m.Refused,"exact independent"):
            m.join(run=run,which=which,
                   stdin=FakeTty(True),stderr=FakeTty(True),
                   input_fn=lambda p:"NOT-AUTHORIZED",
                   owner_guard=lambda:"arbitrary-operator")
        self.assertEqual(len(commands),2)

    def test_join_calls_only_fixed_public_network_then_real_readback(self):
        run,commands,which,join_count=runner(joined=False)
        result=m.join(run=run,which=which,
                      stdin=FakeTty(True),stderr=FakeTty(True),
                      input_fn=lambda p:"JOIN-EXISTING-OPEN-SSE31340-ZEROTIER",
                      owner_guard=lambda:"new-operator-from-another-ISP")
        self.assertTrue(result["joinCommandSent"])
        self.assertTrue(result["actualOpenOverlayReadyForCrossHostTransport"])
        self.assertEqual(join_count[0],1)
        self.assertIn(["sudo","-n","zerotier-cli","join",m.NETWORK_ID],commands)
        self.assertEqual(len(commands),5)
        self.assertTrue(result["participantRoleOrVmAllowlistControlsOverlayAdmission"] is False)

    def test_already_joined_has_no_second_join(self):
        run,commands,which,join_count=runner()
        result=m.join(run=run,which=which,
                      owner_guard=lambda:"external-user")
        self.assertEqual(result["joinAction"],"ALREADY_JOINED_READONLY")
        self.assertFalse(result["joinCommandSent"])
        self.assertEqual(join_count[0],0)

    def test_unhealthy_existing_membership_requires_diagnosis_not_rejoin(self):
        run,commands,which,join_count=runner(healthy=False)
        with self.assertRaisesRegex(m.Refused,"existing network not healthy"):
            m.join(run=run,which=which,
                   owner_guard=lambda:"external-user")
        self.assertEqual(join_count[0],0)

    def test_original_native_p2p_owner_is_protected(self):
        with self.assertRaisesRegex(m.Refused,"original live"):
            m._operator_guard(uid_fn=lambda:1001,
                              user_fn=lambda x:"ayoubakrvm4706",
                              os_name=lambda:"Linux",
                              arch=lambda:"x86_64")
        with self.assertRaisesRegex(m.Refused,"nonroot"):
            m._operator_guard(uid_fn=lambda:0,
                              user_fn=lambda x:"root",
                              os_name=lambda:"Linux",
                              arch=lambda:"x86_64")

    def test_signer_material_guard_refuses_before_join(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/".local/share/sse-r27-bls-operator-private"
            p.parent.mkdir(parents=True)
            p.touch()
            with self.assertRaisesRegex(m.Refused,"signing material"):
                m._operator_guard(uid_fn=lambda:1001,
                                  user_fn=lambda x:"external-user",
                                  os_name=lambda:"Linux",
                                  arch=lambda:"x86_64",
                                  home_fn=lambda:Path(td))

    def test_status_malformed_cli_json_is_safe_unavailable(self):
        run,commands,which,_=runner()
        def malformed(argv,**kwargs):
            p=run(argv,**kwargs)
            if argv[-1]=="listnetworks":
                p.stdout="not-json"
            return p
        report=m.status(run=malformed,which=which)
        self.assertFalse(report["readOnlyZeroTierCliAccessible"])
        self.assertFalse(report["actualOpenOverlayReadyForCrossHostTransport"])

    def test_cli_requires_opt_in_and_source_no_private_network_literals(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                m.main([])
        self.assertEqual(exc.exception.code,2)
        source=(ROOT/"tools/sse_pos_r291_common_public_overlay_onboarding.py").read_text()
        self.assertNotIn("10.50.56.",source)
        self.assertNotIn("ssh-keygen",source)
        self.assertNotIn("authorized_keys",source)


if __name__=="__main__":
    unittest.main()
