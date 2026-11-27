"""R238 per-node status UI real localhost socket and read-only role truth tests."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sse_v2_local_status",
    ROOT/"services"/"node-console"/"v2_status_app.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def observed(node_id,el,bn):
    return {
        "nodeId":node_id,"chainId":31340,"executionBlockNumber":17783,
        "beaconHeadSlot":19394,"finalizedEpoch":602,
        "finalizedRoot":"0x"+"ab"*32,
        "executionNativePeers":2,"beaconNativePeers":2,
        "executionSyncing":False,"beaconSyncing":False,
        "capturedAtUtc":"2026-11-23T16:39:06Z",
    }

CONFIG={
    "nodeId":"vm4707-node","declaredRoles":["observer","provider","validator"],
    "el":"http://127.0.0.1:28545",
    "bn":"http://127.0.0.1:25052",
    "manifest":None,
}

class TestR238RealNodeConsole(unittest.TestCase):
    def test_roles_are_only_declarations_not_wallet_or_activation(self):
        status=mod.node_status(CONFIG,capture=observed)
        self.assertEqual(status["executionAndConsensusLocalObservation"]["finalizedEpoch"],602)
        self.assertFalse(status["stakingValidatorActuallyActiveVerified"])
        self.assertFalse(status["providerPhysicalResourceVerified"])
        self.assertFalse(status["remotePublicHttpsReachabilityVerified"])
        self.assertFalse(status["keysOrWalletsAccessed"])
        self.assertFalse(status["transactionsSignedOrSubmitted"])

    def test_console_refuses_unknown_roles_and_remote_privileged_apis(self):
        with self.assertRaises(mod.Refused):
            mod.approved_options("node-owner",["validator","validator"],
              "http://127.0.0.1:28545","http://127.0.0.1:25052")
        with self.assertRaises(mod.Refused):
            mod.approved_options("node-owner",["admin"],
              "http://127.0.0.1:28545","http://127.0.0.1:25052")
        with self.assertRaises(mod.Refused):
            mod.approved_options("node-owner",["observer"],
              "http://0.0.0.0:28545","http://127.0.0.1:25052")
        with self.assertRaises(mod.Refused):
            mod.approved_options("node-owner",["observer"],
              "http://127.0.0.1:18545","http://127.0.0.1:25052")

    def test_public_html_escapes_all_attacker_text(self):
        sample=mod.node_status(CONFIG,capture=observed)
        sample["nodeId"]="<script>alert(1)</script>"
        html=mod.status_html(sample).decode("utf-8")
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn("Read-only observed original-chain node health.",html)

    def test_real_http_endpoint_is_loopback_only_and_readonly(self):
        server=mod.make_server(CONFIG,0,capture=observed)
        self.assertEqual(server.server_address[0],"127.0.0.1")
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base="http://127.0.0.1:"+str(server.server_port)
        try:
            with urlopen(base+"/v2/status",timeout=4) as response:
                status=json.loads(response.read())
                self.assertIn("default-src 'none'",response.headers[
                    "Content-Security-Policy"])
                self.assertEqual(status["schema"],
                                 "SSE_R238_ROLE_LOCAL_PUBLIC_STATUS_V1")
                self.assertEqual(status["declaredRoles"],CONFIG["declaredRoles"])
            with urlopen(base+"/",timeout=4) as response:
                self.assertIn(b"Finalized epoch",response.read())
            with urlopen(base+"/healthz",timeout=4) as response:
                self.assertFalse(json.loads(response.read())["chainVerifiedByHealthz"])
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base+"/v2/status",data=b"{}",method="POST"),
                        timeout=4)
            self.assertEqual(error.exception.code,405)
            with self.assertRaises(HTTPError) as error:
                urlopen(base+"/v2/lease/1",timeout=4)
            self.assertEqual(error.exception.code,503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=4)

    def test_market_lease_lookup_is_gated_by_explicit_manifest(self):
        conf={**CONFIG,"manifest":Path("/tmp/public-v2-manifest.json")}
        with patch.object(mod,"load_manifest",return_value={"schema":"TEST"}) as load:
            observed_result=mod.lease_status(conf,6,inspect=lambda m,rpc,id:{
                "leaseId":id,"marketV2Finalized":True})
        load.assert_called_once()
        self.assertEqual(observed_result["leaseId"],6)
        with self.assertRaises(mod.Refused):
            mod.lease_status(CONFIG,1)

    def test_source_only_default_never_starts_an_http_server(self):
        import contextlib,io
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            code=mod.main([
                "--node-id","vm4707-node","--roles","observer,monitor",
                "--el","http://127.0.0.1:28545",
                "--bn","http://127.0.0.1:25052"])
        self.assertEqual(code,0)
        result=json.loads(out.getvalue())
        self.assertFalse(result["httpServerStarted"])
        self.assertFalse(result["publicInternetHttpsVerified"])

    def test_application_only_console_uses_real_rpc_interface_without_beacon(self):
        conf=mod.approved_options("node-app",["monitor","provider"],
            "http://127.0.0.1:28545",None,Path("/tmp/manifest.json"))
        def transport(url,method,params):
            self.assertEqual(method,"eth_getBlockByNumber")
            return {"number":"0x7800","timestamp":"0x1000"} if params[0]=="latest" else {"number":"0x7700","timestamp":"0x0800"}
        with patch.object(mod,"load_manifest",return_value={}):
            result=mod.node_status(conf,capture=lambda *a:self.fail("Beacon queried"),
                audit=lambda *a,**kw:{"chainId":31340,"finalizedExecutionHeight":0x7700},
                transport=transport)
        self.assertEqual(result["finalityLagSeconds"],2048)
        self.assertFalse(result["independentLocalConsensusVerified"])
        self.assertFalse(result["roleActivationVerified"])
        self.assertIn(b"Selected roles",mod.status_html(result))
        self.assertIn(b"monitor, provider",mod.status_html(result))

    def test_rpc_only_cannot_claim_native_roles_or_omit_manifest(self):
        for role in ("validator","observer","full_node"):
            with self.assertRaises(mod.Refused):
                mod.approved_options("node-app",[role],"http://127.0.0.1:28545",
                    None,Path("/tmp/manifest.json"))
        with self.assertRaises(mod.Refused):
            mod.approved_options("node-app",["monitor"],"http://127.0.0.1:28545",None)

    def test_status_cache_expiry_and_failure(self):
        now=[0]
        cache=mod.StatusCache(ttl=15,clock=lambda:now[0])
        calls=[]
        def load():
            calls.append(1)
            return {"observed":len(calls)}
        self.assertEqual(cache.read(load),{"observed":1})
        now[0]=14
        self.assertEqual(cache.read(load),{"observed":1})
        now[0]=15
        def fail():
            raise ValueError("RPC unavailable")
        with self.assertRaises(ValueError):
            cache.read(fail)
        self.assertIsNone(cache.value)
        self.assertEqual(cache.read(load),{"observed":2})

    def test_public_mode_restricts_lease_lookups_and_caches_status(self):
        calls=[]
        def capture(*args):
            calls.append(1)
            return observed(*args)
        server=mod.make_server(CONFIG,0,capture=capture,
            inspect=lambda *a:self.fail("lease lookup exposed"),public_readonly=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base="http://127.0.0.1:"+str(server.server_port)
        try:
            for path in ("/","/v2/status","/v2/status?utm_source=chatgpt.com","/?utm_source=chatgpt.com"):
                with urlopen(base+path,timeout=4) as response:
                    self.assertEqual(response.status,200)
            self.assertEqual(len(calls),1)
            with self.assertRaises(HTTPError) as error:
                urlopen(base+"/v2/lease/1?utm_source=chatgpt.com",timeout=4)
            self.assertEqual(error.exception.code,404)
            self.assertEqual(server.request_queue_size,16)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=4)

    def test_monitor_account_reads_only_at_verified_finalized_height(self):
        address="0x"+"ab"*20
        market="0x"+"12"*20
        ledger="0x"+"34"*20
        conf={**CONFIG,"bn":None,"declaredRoles":["monitor"],"monitorAddress":address}
        proof={"finalizedExecutionHeight":42,"contracts":{"market":{"address":market},"ledger":{"address":ledger}}}
        calls=[]
        def query(transport,url,contract,signature,args,height):
            calls.append((contract,signature,height))
            self.assertEqual(args,[int(address,16)])
            values=[1000000000000000,2,1] if signature=="monitors(address)" else [7]
            return "0x"+"".join(format(v,"064x") for v in values)
        def transport(url,method,params):
            self.assertEqual(method,"eth_getBalance")
            self.assertEqual(params,[address,"0x2a"])
            return "0x123"
        with patch.object(mod,"query",side_effect=query):
            account=mod.monitor_account(conf,proof,transport)
        self.assertEqual(account["balanceWei"],"291")
        self.assertEqual(account["bondWei"],"1000000000000000")
        self.assertEqual(account["lockedAssignments"],"2")
        self.assertTrue(account["active"])
        self.assertFalse(account["walletOwnershipVerified"])
        self.assertEqual(account["ledgerWithdrawableWei"],"7")
        self.assertEqual(calls,[(market,"monitors(address)",42),(market,"withdrawable(address)",42),(ledger,"withdrawable(address)",42)])
        self.assertIsNone(mod.monitor_account(CONFIG,{},None))

    def test_monitor_address_configuration_rejects_invalid_scope(self):
        for address in ("bad","0x"+"00"*20,"0x"+"ab"*20):
            with self.assertRaises(mod.Refused):
                mod.make_server({**CONFIG,"monitorAddress":address},0)

    def test_recent_blocks_checks_parent_continuity_and_bounds(self):
        def h(n):
            return "0x"+format(n,"064x")
        calls=[]
        def transport(url,method,params):
            self.assertEqual(method,"eth_getBlockByNumber")
            self.assertFalse(params[1])
            n=20 if params[0]=="finalized" else int(params[0],16)
            calls.append(n)
            return {"number":hex(n),"hash":h(n+1),"parentHash":h(n),
                    "stateRoot":h(100),"transactionsRoot":h(101),"receiptsRoot":h(102),
                    "timestamp":hex(n*12),"gasUsed":"0x5208","gasLimit":"0x100000",
                    "transactions":[h(i+200) for i in range(18)]}
        result=mod.recent_blocks(CONFIG,transport)
        self.assertEqual(calls,[20,20,19,18,17,16,15,14,13])
        self.assertEqual(len(result["blocks"]),8)
        self.assertEqual(result["blocks"][0]["transactionCount"],18)
        self.assertEqual(len(result["blocks"][0]["transactionHashes"]),16)
        self.assertTrue(result["blocks"][0]["transactionHashesTruncated"])
        self.assertFalse(result["localDiskStorageVerified"])
        def broken(url,method,params):
            record=transport(url,method,params)
            if params[0]=="0x13":
                record["hash"]=h(999)
            return record
        with self.assertRaises(mod.Refused):
            mod.recent_blocks(CONFIG,broken)

    def test_market_overview_bounds_finalized_request_reads(self):
        proof={"finalizedExecutionHeight":42,"contracts":{"market":{"address":"0x"+"12"*20}}}
        calls=[]
        def query(transport,url,contract,signature,args,height):
            self.assertEqual(height,42)
            calls.append((signature,args))
            values={"nextRequestId()":[8],"nextLeaseId()":[2],
                    "activeMonitorCount()":[4],"requests(uint256)":[1,2,3,1000,1795620522,0],
                    "bidCount(uint256)":[2]}[signature]
            return "0x"+"".join(format(v,"064x") for v in values)
        with patch.object(mod,"query",side_effect=query):
            result=mod.market_overview(CONFIG,proof,None)
        self.assertEqual(result["requestsCreated"],"7")
        self.assertEqual(result["leasesCreated"],"1")
        self.assertEqual([r["requestId"] for r in result["recentRequests"]],["5","6","7"])
        self.assertEqual(len(calls),9)

    def test_historical_page_and_genesis(self):
        def h(n): return "0x"+format(n,"064x")
        def transport(url,method,params):
            n=20 if params[0]=="finalized" else int(params[0],16)
            return {"number":hex(n),"hash":h(n+1),"parentHash":h(n),
                    "stateRoot":h(100),"transactionsRoot":h(101),"receiptsRoot":h(102),
                    "timestamp":hex(n*12),"gasUsed":"0x0","gasLimit":"0x100000",
                    "transactions":[],"miner":"0x"+"ab"*20}
        self.assertEqual([b["number"] for b in mod.recent_blocks(CONFIG,transport,start=4)["blocks"]],[4,3,2,1,0])
        self.assertEqual(mod.recent_blocks(CONFIG,transport,start=0)["blocks"][0]["feeRecipient"],"0x"+"ab"*20)
        with self.assertRaises(mod.Refused):
            mod.recent_blocks(CONFIG,transport,start=21)

    def test_proposer_requires_matching_execution_hash(self):
        block={"timestamp":1120,"hash":"0x"+"ab"*32}
        def transport(url,**kwargs):
            if url.endswith("/genesis"): return {"genesis_time":"1000"}
            if url.endswith("/blocks/10"):
                return {"message":{"slot":"10","proposer_index":"7","body":{"execution_payload":{"block_hash":block["hash"]}}}}
            if url.endswith("/validators/7"):
                return {"index":"7","validator":{"pubkey":"0x"+"cd"*48}}
            self.fail("unexpected Beacon path")
        result=mod.proposer_identity(CONFIG,block,transport)
        self.assertEqual(result["validatorIndex"],7)
        self.assertTrue(result["executionHashMatched"])
        self.assertIsNone(mod.proposer_identity({**CONFIG,"bn":None},block,transport))
        def wrong(url,**kwargs):
            result=transport(url,**kwargs)
            if url.endswith("/blocks/10"):
                result["message"]["body"]["execution_payload"]["block_hash"]="0x"+"ff"*32
            return result
        with self.assertRaises(mod.Refused):
            mod.proposer_identity(CONFIG,block,wrong)

    def test_explorer_requires_native_role_and_consensus_endpoint(self):
        for roles in (["monitor"],["provider"],["consumer"],["monitor","provider"]):
            conf={**CONFIG,"declaredRoles":roles,"bn":None,"blockExplorer":True}
            self.assertFalse(mod.block_explorer_allowed(conf))
            self.assertFalse(mod.block_explorer_allowed({**conf,"bn":CONFIG["bn"]}))
        for role in ("observer","full_node","validator"):
            conf={**CONFIG,"declaredRoles":[role,"monitor"],"blockExplorer":True}
            self.assertTrue(mod.block_explorer_allowed(conf))
            self.assertFalse(mod.block_explorer_allowed({**conf,"bn":None}))
            self.assertFalse(mod.block_explorer_allowed({**conf,"blockExplorer":False}))

    def test_application_monitor_explorer_routes_denied_even_if_enabled(self):
        conf={**CONFIG,"declaredRoles":["monitor"],"bn":None,"blockExplorer":True}
        server=mod.make_server(conf,0,public_readonly=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base="http://127.0.0.1:"+str(server.server_port)
        try:
            with patch.object(mod,"recent_blocks",side_effect=AssertionError("forbidden block read")):
                for path in ("/blocks/0","/v2/blocks/25339?utm_source=chatgpt.com"):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base+path,timeout=4)
                    self.assertEqual(error.exception.code,404)
                with patch.object(mod,"node_status",return_value={"schema":"test","declaredRoles":["monitor"]}):
                    with urlopen(base+"/v2/status",timeout=4) as response:
                        self.assertNotIn("blockExplorer",json.loads(response.read()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=4)

if __name__=="__main__":
    unittest.main()
