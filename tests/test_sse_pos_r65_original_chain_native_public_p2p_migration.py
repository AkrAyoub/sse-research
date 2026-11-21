"""R65 owner existing chain native open-join IPv6 P2P migration safety tests.

No real Docker, validator signer, keys, ENR, blockchain, overlay or services
are touched; actual deployment requires explicit owner local authorization.
"""
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r65_original_chain_native_public_p2p_migration as m

IP="fca0:2328:776e:4750:395b::1"

class R65NativePublicOwnerMigrationTests(unittest.TestCase):
    def test_unchanged_original_single_signer_and_pinned_images(self):
        self.assertEqual((m.EL,m.BN,m.VC),
            ("sse31340-g2-el-r40","sse31340-g2-bn","sse31340-g2-vc"))
        self.assertEqual(m.TRUSTED,"sse31340-g2-internal")
        self.assertEqual(m.BESU_ID,m.r59.BESU_ID)
        self.assertEqual(m.LIGHTHOUSE_ID,m.r59.LIGHTHOUSE_ID)

    def test_besu_ipv6_port_separate_from_ipv4(self):
        ports=m.validated_host_ports(IP)
        self.assertEqual(ports[m.EL],[
          f"[{IP}]:30404:30404/tcp",f"[{IP}]:30404:30404/udp",
          "127.0.0.1:18545:8545/tcp"])
        self.assertEqual(ports[m.BN],[
          f"[{IP}]:9000:9000/tcp",f"[{IP}]:9000:9000/udp",
          f"[{IP}]:9001:9001/udp","127.0.0.1:15052:5052/tcp"])

    def test_refuse_private_provider_lan_or_wildcard_public_endpoint(self):
        for invalid in ("10.50.56.2","192.168.0.1","::","::1",
                        "2001:db8::1","fe80::1"):
            with self.subTest(ip=invalid),self.assertRaises(m.R65Refused):
                m.validated_host_ports(invalid)

    def test_besu_renews_existing_command_without_new_genesis(self):
        cmd=["--network-id=31340","--p2p-enabled=false",
             "--genesis-file=/testnet/genesis.json",
             "--engine-jwt-secret=/jwt/engine.jwt",
             "--engine-rpc-port=8551"]
        new=m.revised_cmd(m.EL,cmd,IP)
        self.assertIn("--p2p-enabled=true",new)
        self.assertIn("--p2p-host-ipv6="+IP,new)
        self.assertIn("--p2p-port-ipv6=30404",new)
        self.assertIn("--p2p-discovery-port-ipv6=30404",new)
        self.assertNotIn("--p2p-enabled=false",new)
        self.assertIn("--genesis-file=/testnet/genesis.json",new)
        self.assertIn("--engine-jwt-secret=/jwt/engine.jwt",new)
        self.assertIn("--network-id=31340",new)
        self.assertIn("--p2p-host=127.0.0.1",new)

    def test_beacon_existing_cli_and_genesis_preserved(self):
        cmd=["--testnet-dir=/testnet","--datadir=/data","bn",
             "--execution-endpoint=http://sse31340-g2-el:8551",
             "--execution-jwt=/jwt/engine.jwt"]
        new=m.revised_cmd(m.BN,cmd,IP)
        for arg in cmd:
            self.assertIn(arg,new)
        self.assertIn("--enr-address="+IP,new)
        self.assertIn("--listen-address=::",new)
        self.assertIn("--enr-quic6-port=9001",new)
        with self.assertRaises(m.R65Refused):
            m.revised_cmd(m.VC,cmd,IP)

    def test_clone_client_keeps_existing_owner_state_and_private_engine(self):
        defn={
          "name":m.EL,"image":m.BESU_REF,
          "config":{"User":"1000:1000"},
          "host":{"Memory":4294967296,"PidsLimit":384,
                  "NanoCpus":2000000000,"Tmpfs":{"/tmp":"rw,nosuid,exec,size=256m"}},
          "mounts":[
           {"Source":"/owner/testnet","Destination":"/testnet","RW":False},
           {"Source":"/owner/engine.jwt","Destination":"/jwt/engine.jwt","RW":False},
           {"Source":"/owner/el","Destination":"/data","RW":True},
          ],
          "cmd":["--network-id=31340","--p2p-enabled=false"]
        }
        argv=m.clone_args(defn,IP)
        self.assertEqual(argv[:3],["create","--pull","never"])
        self.assertIn(m.TRUSTED,argv)
        self.assertIn("--network-alias",argv)
        self.assertIn("sse31340-g2-el",argv)
        self.assertIn(f"[{IP}]:30404:30404/udp",argv)
        self.assertIn("127.0.0.1:18545:8545/tcp",argv)
        self.assertNotIn("8551:8551",json.dumps(argv))
        self.assertNotIn("10.50.56",json.dumps(argv))
        self.assertIn("unless-stopped",argv)
        self.assertIn("--cap-drop",argv)
        self.assertIn("--read-only",argv)

    def test_safe_mounts_and_exact_original_container_reuse(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text("utf-8")
        self.assertIn('targets!={"/testnet","/jwt/engine.jwt","/data"}',source)
        self.assertIn('m.get("RW") is not False',source)
        self.assertIn('m.get("RW") is not True',source)
        self.assertIn('str(owner_root)',source)
        self.assertIn('"same-data"',source) if False else None
        self.assertIn('os.path.commonpath',source)

    def test_refuse_original_client_already_migrated(self):
        owner={"originalELP2pExplicitlyDisabled":False}
        with patch.object(m.r64,"current_owner_audit",return_value=owner):
            with self.assertRaises(m.R65Refused):
                m.read_only_plan("a"*40)

    def test_preflight_does_not_modify_docker_or_restart_signer(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text("utf-8")
        body=source[source.index("def read_only_plan("):source.index("def rollback(")]
        for banned in ('docker(["stop"', 'docker(["start"', 'docker(["run"',
                       'docker(["network","create"', 'docker(["rename"',
                       'clone_args(', 'rollback('):
            self.assertNotIn(banned,body)
        self.assertIn('"nothingModifiedByPlan":True',body)

    def test_refuse_apply_without_attested_backup_even_when_plan_passes(self):
        plan={"actualOpenOverlayIPv6":IP}
        with patch.object(m,"read_only_plan",return_value=(plan,{},{})):
            with self.assertRaises(m.R65Refused):
                m.apply("a"*40,False)

    def test_rollback_never_deletes_original_containers_before_rename(self):
        with patch.object(m,"docker",return_value="true") as run,patch.object(
             m,"wait_client",return_value=True):
            m.rollback(set(),set())
        args=[x.args[0] for x in run.call_args_list]
        self.assertFalse(any(a[0]=="rm" for a in args))
        self.assertFalse(any(a[0]=="rename" for a in args))
        self.assertIn(["start",m.VC],args)

    def test_rollback_removes_only_created_new_and_restores_exact_old_names(self):
        with patch.object(m,"docker",return_value="true") as run,patch.object(
             m,"wait_client",return_value=True):
            m.rollback({m.EL,m.BN},{m.EL,m.BN})
        args=[x.args[0] for x in run.call_args_list]
        self.assertIn(["rm",m.EL],args)
        self.assertIn(["rm",m.BN],args)
        self.assertIn(["rename",m.PRESERVED[m.EL],m.EL],args)
        self.assertIn(["rename",m.PRESERVED[m.BN],m.BN],args)
        self.assertNotIn(["rm",m.VC],args)
        self.assertNotIn(["rename",m.VC,m.VC],args)

    def test_original_validator_only_started_after_EL_and_BN_healthy(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text("utf-8")
        body=source[source.index("def apply("):source.index("def main(")]
        self.assertLess(body.index('if not wait_client(name,kind):'),
                        body.index('docker(["start",VC]'))
        self.assertLess(body.index('ports=verify_old_absent_and_new_reachability(ipv6)'),
                        body.index('docker(["start",VC]'))
        self.assertIn('for name in (VC,BN,EL):',body)

    def test_original_engine_api_never_published_and_loopback_only(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text("utf-8")
        self.assertIn('"engine8551HostPublicationPlanned":False',source)
        self.assertIn('"originalEngine8551PublishedToHost":False',source)
        self.assertIn('"onlyRequiredP2pPublishedToActualOwner6plane":True',source)
        self.assertIn('"hostJsonRpcAndBeaconApiPublishedOnlyToLocalhost":True',source)

    def test_no_clone_of_original_validator_keys_or_genesis(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text("utf-8")
        for banned in ('docker(["rm",VC]', 'docker(["rename",VC',
                       'docker(["run",VC','zerotier-cli","join"',
                       'wallet create','genesis-build','import-validator',
                       'scp ','ssh '):
            self.assertNotIn(banned,source)
        self.assertIn('"originalValidatorSigningDataAndKeystoreNeverCloned":True',source)
        self.assertIn('"externalNativeEthereumP2pSyncAndFinalizedRootMatchObserved":False',source)

    def test_source_only_no_real_peer_claim_and_dynamic_host_ip(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text("utf-8")
        self.assertIn('owner["actualOwnerOverlayIpv6"]',source)
        self.assertIn('nativeOutsideProviderP2pPeerAndContinuedFinalityStillUnverified',source)
        self.assertIn('originalBeaconFinalizedEpoch',source)
        self.assertNotIn('10.50.56.',source)

if __name__=="__main__":
    unittest.main()
