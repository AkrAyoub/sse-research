"""R287 source-only safety: no actual SSH, network, Docker, transactions."""
import base64
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r287_three_vm_authenticated_temporary_compute_ssh_probe as m
from compute_workload import compute_result

PUBLIC_B64=base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519"+b"\x00\x00\x00\x20"+bytes(range(32))).decode()
EXPECTED=m.parse_public("ssh-ed25519 "+PUBLIC_B64)[0]


class FakeHttpResponse:
    status=200
    def __init__(self,doc):
        self.body=json.dumps(doc).encode()
        self.headers={"Content-Length":str(len(self.body))}
    def read(self,n):
        return self.body[:n]
    def __enter__(self):
        return self
    def __exit__(self,*a):
        return False


class FakeHttpOpener:
    def __init__(self,*,wrong=False):
        self.urls=[]
        self.wrong=wrong
    def open(self,request,timeout):
        self.urls.append((request.full_url,request.method,timeout))
        if request.method=="GET":
            return FakeHttpResponse({
                "ok":True,"localComputeWorker":True,
                "onChainAuthenticated":False
            })
        req=json.loads(request.data)
        doc=compute_result(req["leaseId"],req["epochId"],req["requestHash"])
        if self.wrong:
            doc["rounds"]=999
        return FakeHttpResponse(doc)


class FakeSocket:
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


class FakeSshProcess:
    def __init__(self):
        self.exited=False
        self.terminated=False
    def poll(self):
        return 0 if self.exited else None
    def terminate(self):
        self.terminated=True
        self.exited=True
    def wait(self,timeout):
        return 0
    def kill(self):
        self.exited=True


class TestR287PinnedTemporarySshPreleaseWorker(unittest.TestCase):
    def test_read_only_provider_host_key_public_fingerprint_only(self):
        data=m.provider_public_hostkey(
            read=lambda:"ssh-ed25519 "+PUBLIC_B64+" server-label")
        self.assertEqual(data["ed25519HostPublicKeyFingerprint"],EXPECTED)
        self.assertFalse(data["privateSshSigningKeyRead"])
        self.assertFalse(data["sshHostOrAuthorizedKeysChanged"])

    def test_untrusted_ssh_scan_requires_equal_out_of_band_fingerprint(self):
        calls=[]
        def runner(cmd,**kwargs):
            calls.append((cmd,kwargs))
            return subprocess.CompletedProcess(
                cmd,0,"# comment\n"+
                m.HOST+" ssh-ed25519 "+PUBLIC_B64+"\n","")
        self.assertEqual(m.scanned_public_hostkey(EXPECTED,run=runner),PUBLIC_B64)
        self.assertEqual(calls[0][0],[
            "ssh-keyscan","-T","4","-p","22","-t","ed25519",m.HOST
        ])
        self.assertFalse(calls[0][1]["shell"])
        with self.assertRaisesRegex(m.Refused,"DOES NOT MATCH"):
            m.scanned_public_hostkey("SHA256:"+"A"*43,run=runner)

    def test_scan_rejects_multiple_or_unknown_ssh_keys(self):
        def runner(cmd,**kwargs):
            return subprocess.CompletedProcess(
                cmd,0,m.HOST+" ssh-ed25519 "+PUBLIC_B64+"\n"+
                "otherserver ssh-ed25519 "+PUBLIC_B64+"\n","")
        with self.assertRaisesRegex(m.Refused,"unknown SSH"):
            m.scanned_public_hostkey(EXPECTED,run=runner)

    def test_invalid_host_fingerprint_rejected_without_network(self):
        with self.assertRaisesRegex(m.Refused,"EXACT"):
            m.scanned_public_hostkey("trust-on-first-use",run=lambda *a,**k:
                self.fail("must never scan without out-of-band pin"))

    def test_strict_ssh_never_uses_portal_proxy_or_unverified_host_keys(self):
        with tempfile.TemporaryDirectory() as td:
            f=m.authorize_known_host(td,PUBLIC_B64)
            self.assertEqual(f.stat().st_mode & 0o777,0o600)
            self.assertEqual(f.read_text(),
                             m.HOST+" ssh-ed25519 "+PUBLIC_B64+"\n")
            args=m.strict_ssh_args(f)
            for expected in (
                "StrictHostKeyChecking=yes","PasswordAuthentication=no",
                "KbdInteractiveAuthentication=no","BatchMode=yes",
                "ProxyCommand=none","ForwardAgent=no","ControlMaster=no",
                "UserKnownHostsFile="+str(f),"ExitOnForwardFailure=yes"
            ):
                self.assertIn(expected,args)
            self.assertEqual(args[0:3],["ssh","-F","/dev/null"])

    def test_pinned_monitor_preflight_no_tunnel_or_worker_compute(self):
        invoked=[]
        def scan(cmd,**kwargs):
            invoked.append(("keyscan",cmd))
            return subprocess.CompletedProcess(
                cmd,0,m.HOST+" ssh-ed25519 "+PUBLIC_B64+"\n","")
        def auth(cmd,**kwargs):
            invoked.append(("ssh_auth",cmd))
            self.assertEqual(cmd[-2:],[m.TARGET,"true"])
            return subprocess.CompletedProcess(cmd,0,"","")
        out=m.observe(user="ayoubakrvm4711",mode="--preflight",
                      fingerprint=EXPECTED,scan_run=scan,ssh_run=auth,
                      tunnel=lambda *_:self.fail("no tunnel in preflight"))
        self.assertTrue(out["sshNoninteractivePublicKeyLoginVerified"])
        self.assertFalse(out["fullSshTunnelAndRealRemoteCpuTestRequested"])
        self.assertFalse(out["newAuthorizedKeysOrKnownHostsPersisted"])
        self.assertFalse(out["paidFinalizedV2LeaseOrSlaVerified"])
        self.assertEqual([x[0] for x in invoked],["keyscan","ssh_auth"])

    def test_missing_client_ssh_auth_does_not_start_tunnel(self):
        def scan(cmd,**kwargs):
            return subprocess.CompletedProcess(
                cmd,0,m.HOST+" ssh-ed25519 "+PUBLIC_B64+"\n","")
        def denied(cmd,**kwargs):
            return subprocess.CompletedProcess(cmd,255,"","permission denied")
        result=m.observe(user="ayoubakrvm4712",mode="--probe",
                         fingerprint=EXPECTED,scan_run=scan,ssh_run=denied,
                         tunnel=lambda *_:self.fail("no tunnel without SSH auth"))
        self.assertFalse(result["sshNoninteractivePublicKeyLoginVerified"])
        self.assertEqual(result["nextAction"],
                         "REVIEW_PUBLIC_KEY_LOGIN_WITHOUT_CHANGING_FIREWALL_OR_KEYS")
        self.assertFalse(result["monitorEip712VoteSignedOrBroadcast"])

    def test_real_remote_http_cpu_expected_payload_checked_independently_mock(self):
        http=FakeHttpOpener()
        out=m.worker_probe(21877,opener=http,random_hex=lambda n:"ab"*32)
        self.assertTrue(out["realRemoteCpuResultVerified"])
        self.assertEqual(out["rounds"],8192)
        self.assertEqual(len(http.urls),2)
        self.assertEqual(http.urls[0][0],
                         "http://127.0.0.1:21877/healthz")
        self.assertEqual(http.urls[1][0],
                         "http://127.0.0.1:21877/v1/compute")
        self.assertFalse(out["providerResponseEip712SignatureVerified"])
        self.assertFalse(out["onChainLeaseOrSlaVerified"])

    def test_wrong_remote_cpu_digest_or_rounds_is_hard_refusal(self):
        with self.assertRaisesRegex(m.Refused,"REAL CPU result"):
            m.worker_probe(21877,opener=FakeHttpOpener(wrong=True),
                           random_hex=lambda n:"ab"*32)

    def test_short_lived_ssh_tunnel_terminated_after_one_cpu_job(self):
        process=FakeSshProcess()
        launches=[]
        def popen(command,**kwargs):
            launches.append((command,kwargs))
            return process
        result=m.temporary_tunnel(["ssh","-F","/dev/null"],
            popen=popen,connect=lambda addr,timeout:FakeSocket(),
            port_picker=lambda:21877,
            probe=lambda port:{"verified":True},sleep=lambda s:self.fail("no wait"))
        self.assertTrue(result["verified"])
        self.assertTrue(process.terminated)
        self.assertIn("127.0.0.1:21877:127.0.0.1:8877",launches[0][0])
        self.assertEqual(launches[0][0][-1],m.TARGET)
        self.assertEqual(launches[0][1]["stdin"],subprocess.DEVNULL)
        self.assertEqual(launches[0][1]["stdout"],subprocess.DEVNULL)
        self.assertTrue(result["temporarySshForwardListenerBoundOnlyMonitorLoopback"])

    def test_tunnel_cleans_up_ssh_even_if_remote_cpu_mismatches(self):
        proc=FakeSshProcess()
        with self.assertRaisesRegex(m.Refused,"worker invalid"):
            m.temporary_tunnel(["ssh"],popen=lambda *a,**k:proc,
                connect=lambda *a,**k:FakeSocket(),
                port_picker=lambda:21878,
                probe=lambda p:(_ for _ in ()).throw(m.Refused("worker invalid")))
        self.assertTrue(proc.terminated)

    def test_only_existing_owner_pinned_private_identity_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"key"
            p.write_text("FAKE_KEY_NEVER_A_REAL_SECRET")
            p.chmod(0o600)
            self.assertEqual(m._identity(str(p),p.stat().st_uid),str(p))
            self.assertIn("IdentitiesOnly=yes",m.strict_ssh_args(
                Path(td)/"known_hosts",identity=str(p)))
            p.chmod(0o644)
            with self.assertRaisesRegex(m.Refused,"0400/0600"):
                m._identity(str(p),p.stat().st_uid)
            p.chmod(0o600)
            link=Path(td)/"link"
            link.symlink_to(p)
            with self.assertRaisesRegex(m.Refused,"non-symlink"):
                m._identity(str(link),p.stat().st_uid)

    def test_only_actual_vm_owners_accepted(self):
        with self.assertRaisesRegex(m.Refused,"nonroot"):
            m.owner(uid_fn=lambda:0,name_fn=lambda uid:"root")
        with self.assertRaisesRegex(m.Refused,"four actually observed"):
            m.owner(uid_fn=lambda:1001,name_fn=lambda uid:"unknownuser")
        with self.assertRaisesRegex(m.Refused,"only provider"):
            m.observe(user="ayoubakrvm4711",mode="--provider-hostkey")
        with self.assertRaisesRegex(m.Refused,"only VM4711"):
            m.observe(user="ayoubakrvm4714",mode="--probe",
                      fingerprint=EXPECTED)

    def test_cli_no_implicit_ssh_probe(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                m.main([])
        self.assertEqual(caught.exception.code,2)


if __name__=="__main__":
    unittest.main()
