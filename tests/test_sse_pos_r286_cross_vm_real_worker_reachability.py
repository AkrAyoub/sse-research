"""R286 CPU/protected worker and monitor private TCP path, MOCKED only."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r286_cross_vm_real_worker_reachability as m


class FakeSocket:
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


class TestR286ActualFourVmReadOnlyCrossHostPreflight(unittest.TestCase):
    def test_plan_no_network_no_docker_and_no_cpu(self):
        for owner in m.HOSTS:
            with self.subTest(owner=owner):
                out=m.observe(
                    user=owner,probe=False,
                    connect=lambda *args,**kwargs: (_ for _ in ()).throw(
                        AssertionError("unexpected TCP on plan")),
                    docker_inspect=lambda *args,**kwargs: (_ for _ in ()).throw(
                        AssertionError("unexpected Docker on plan")),
                    compute_probe=lambda *args,**kwargs: (_ for _ in ()).throw(
                        AssertionError("unexpected CPU on plan")))
                self.assertFalse(out["probeRequested"])
                self.assertFalse(out["realExternalPortReachabilityChecked"])
                self.assertFalse(out["networkListenerStarted"])
                self.assertFalse(out["dockerChanged"])
                self.assertFalse(out["nativeChainTransactionSent"])

    def test_monitor_remote_tcp_probe_fixed_22_and_8877_only(self):
        calls=[]
        def connect(where,timeout):
            calls.append((where,timeout))
            return FakeSocket()
        out=m.observe(user="ayoubakrvm4711",probe=True,
                      connect=connect,docker_inspect=lambda *a,**k:
                      self.fail("monitor must not access provider Docker"))
        self.assertEqual(calls,[
            ((m.PROVIDER_IPV4,22),2.0),
            ((m.PROVIDER_IPV4,8877),2.0)
        ])
        self.assertEqual([r["tcpStatus"] for r in out["actualNetworkProbes"]],
                         ["TCP_HANDSHAKE_SUCCEEDED"]*2)
        self.assertFalse(out["actualWorkerDockerConfigReaudited"])
        self.assertFalse(out["remoteLeaseOrSlaVerified"])

    def test_monitor_connect_refused_is_observation_not_sla_failure(self):
        def denied(where,timeout):
            raise ConnectionRefusedError("real port refused")
        out=m.observe(user="ayoubakrvm4712",probe=True,connect=denied)
        self.assertEqual([r["tcpStatus"] for r in out["actualNetworkProbes"]],
                         ["TCP_REFUSED","TCP_REFUSED"])
        self.assertFalse(out["remoteLeaseOrSlaVerified"])
        self.assertFalse(out["nativeChainTransactionSent"])

    def test_tcp_probe_restricts_network_destinations(self):
        for addr,port in (("8.8.8.8",22),(m.PROVIDER_IPV4,80),
                          ("127.0.0.1",8877)):
            with self.subTest(addr=addr,port=port),self.assertRaises(m.Refused):
                m.tcp_probe(addr,port,connect=lambda *a,**k:
                            self.fail("unexpected TCP network access"))

    def test_vm4714_reads_exact_worker_image_and_runs_fresh_real_challenge_mock(self):
        challenge="a1"*32
        calls=[]
        def ins(profile,endpoint,name,**opts):
            calls.append(("inspect",profile,endpoint,name,opts))
            return {
                "containerId":m.WORKER_ID,"imageId":m.IMAGE_ID,
                "runtimeReportedRunning":True,
                "localDockerConfigurationInspected":True
            }
        def probe(endpoint,lease,epoch,request):
            calls.append(("probe",endpoint,lease,epoch,request))
            return {"workloadResultVerified":True,"rounds":8192,
                    "requestHash":request,
                    "resultDigest":"sha256:"+"ff"*32,
                    "elapsedSecondsLocal":0.003}
        out=m.observe(user="ayoubakrvm4714",probe=True,
            connect=lambda addr,timeout:FakeSocket(),
            docker_inspect=ins,compute_probe=probe,
            random_bytes=lambda n:challenge)
        self.assertTrue(out["actualWorkerDockerConfigReaudited"])
        self.assertTrue(out["actualLocalCpuChallengeIndependentlyVerified"])
        self.assertEqual(calls[0][0],"inspect")
        self.assertEqual(calls[0][4],{
            "strict_hardening":True,
            "dedicated_vm4714_sudo_docker":True
        })
        self.assertEqual(calls[1],(
            "probe",m.WORKER_ENDPOINT,1,0,"0x"+challenge))
        self.assertEqual(out["localProbe"]["rounds"],8192)
        self.assertFalse(out["remoteLeaseOrSlaVerified"])

    def test_vm4714_wrong_actual_docker_id_refuses_before_cpu(self):
        def bad(*args,**kwargs):
            return {"containerId":"bad","imageId":m.IMAGE_ID,
                    "runtimeReportedRunning":True,
                    "localDockerConfigurationInspected":True}
        with self.assertRaisesRegex(m.Refused,"worker ID"):
            m.observe(user="ayoubakrvm4714",probe=True,
                connect=lambda addr,timeout:FakeSocket(),
                docker_inspect=bad,compute_probe=lambda *a:
                self.fail("must not compute before verified container"))

    def test_vm4714_missing_real_cpu_result_refuses(self):
        with self.assertRaisesRegex(m.Refused,"CPU recomputation"):
            m.observe(user="ayoubakrvm4714",probe=True,
                connect=lambda addr,timeout:FakeSocket(),
                docker_inspect=lambda *a,**k:{
                    "containerId":m.WORKER_ID,"imageId":m.IMAGE_ID,
                    "runtimeReportedRunning":True,
                    "localDockerConfigurationInspected":True},
                compute_probe=lambda *a:{
                    "workloadResultVerified":False,
                    "rounds":8192,"requestHash":"0x"+"aa"*32},
                random_bytes=lambda n:"aa"*32)

    def test_vm_user_gate_refuses_root_and_unknown(self):
        with self.assertRaisesRegex(m.Refused,"nonroot"):
            m.identify(geteuid=lambda:0,getname=lambda n:"root")
        with self.assertRaisesRegex(m.Refused,"four previously"):
            m.identify(geteuid=lambda:1234,getname=lambda n:"not-the-VM")

    def test_probe_requires_operator_opt_in(self):
        import contextlib,io
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main([]),2)


if __name__=="__main__":
    unittest.main()
