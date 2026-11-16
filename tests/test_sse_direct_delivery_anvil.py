"""Opt-in actual-chain, real signed consumer -> winning-provider HTTP exchange.

This test starts Anvil ONLY on localhost. It uses separate consumer,
two bidding provider accounts, five bonded monitor EOAs and real Foundry
contract bytecode. No remote VM, Tailscale or public ETH. It is skipped by
default and uses Anvil's PUBLIC development-only mnemonic.

A chain-backed signed off-chain result is NOT proof of Docker resource delivery
or independent monitor truth. The V1 provider response contract signature
authenticates only the V1 challenge responseHash, not compute output bytes.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))
sys.path.insert(0,str(ROOT/"services"/"provider-agent"))

from eth_account import Account
from sse_challenge import keccak256
from sse_chain_read import inspect_chain
from sse_node_marketplace import RPC, execute, make_plan
from sse_sla_manifest import proposed_policy, policy_hash, compare_to_lease
from sse_resource_profile_v2 import make_profile, resource_hash, compare_policy
from sse_direct_delivery import (ExchangeError, prepare_request, authenticate_request,
                                 submit_work_request, validate_response,
                                 verify_receipt, post_json)
from compute_workload import compute_result
from direct_work_service import make_server
from sse_direct_journal import DirectJournal
from sse_docker_sla_runner import docker_launch_argv, make_docker_runner
from test_sse_node_marketplace_anvil import (
    AVAILABLE, ENABLE, CHAIN, MNEMONIC, _data, _deploy, _unlocked,
    _address_words, _loopback_port
)

@unittest.skipUnless(ENABLE, "explicit loopback Anvil integration opt-in required")
@unittest.skipUnless(AVAILABLE, "Anvil binary and Foundry artifacts required")
class ChainBackedDirectDelivery(unittest.TestCase):
    def test_two_provider_bids_selected_provider_delivers_signed_compute(self):
        Account.enable_unaudited_hdwallet_features()
        use_docker=os.environ.get("SSE_DIRECT_ANVIL_USE_DOCKER") == "1"
        docker_image=os.environ.get("SSE_DOCKER_WORKER_IMAGE", "")
        if use_docker:
            # Check local Docker and immutable image BEFORE deploying any
            # temporary Anvil chain or touching the Docker daemon.
            from test_sse_docker_sla_live import require_local_docker_engine
            require_local_docker_engine(docker_image)
        port=_loopback_port()
        process=subprocess.Popen(
            ["anvil","--silent","--host","127.0.0.1",
             "--port",str(port),"--chain-id",str(CHAIN),
             "--accounts","10","--mnemonic",MNEMONIC],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        server=None
        worker=None
        private_journal_dir=None
        docker_container_id=None
        try:
            rpc=RPC("http://127.0.0.1:"+str(port))
            for _ in range(100):
                if process.poll() is not None:
                    self.fail("isolated Anvil process exited")
                try:
                    if int(rpc.request("eth_chainId",[]),16)==CHAIN:
                        break
                except (OSError,ValueError):
                    pass
                time.sleep(.1)
            else:
                self.fail("temporary Anvil startup failed")
            wallets=[Account.from_mnemonic(
                MNEMONIC,account_path=f"m/44'/60'/0'/0/{i}") for i in range(8)]
            consumer,losing_provider,winner=wallets[:3]
            monitors=wallets[3:8]
            self.assertEqual([x.address.lower() for x in wallets],
                             [x.lower() for x in rpc.request("eth_accounts",[])][:8])
            bond=10**9
            pool=_deploy(rpc,consumer.address,"OpenMonitorCommittee",
                         consumer.address,bond,86400,3600)
            settlement=_deploy(rpc,consumer.address,"SSESettlement",pool)
            board=_deploy(rpc,consumer.address,"OpenResourceBoard")
            for to,calldata in (
                (pool,_data("bindSettlement(address)",settlement)),
                (settlement,_data("bindResourceBoard(address)",board)),
                (board,_data("bindSettlement(address)",settlement)),
            ):
                _unlocked(rpc,consumer.address,to,calldata)
            contracts={"chain_id":CHAIN,"board":board,
                       "settlement":settlement,"pool":pool}
            submitted=[]
            def transact(action,role,values,account):
                plan=make_plan(action,role,params=values,**contracts)
                result=execute(rpc,plan,account,max_total_wei=10**18,
                               selected_bid_fee=values.get("selectedEpochFeeWei"))
                self.assertEqual(result["status"],"MINED_UNFINALIZED",result)
                submitted.append(result["transactionHash"])
                return result
            for monitor in monitors:
                transact("monitor-register","monitor",{"bondWei":bond},monitor)

            # Endpoint is committed BEFORE bids; test only uses loopback HTTP.
            service_port=_loopback_port()
            endpoint="http://127.0.0.1:"+str(service_port)
            profile=make_profile("deterministic_compute",endpoint,
                                 image_digest=(docker_image if use_docker else
                                               "sha256:"+"a1"*32),
                                 cpu_milli=500,memory_bytes=512*2**20)
            profile_digest=resource_hash(profile)
            policy=proposed_policy(service_kind="deterministic_compute",
                chain_id=CHAIN,settlement=settlement,
                resource_profile_hash=profile_digest)
            self.assertTrue(compare_policy(profile,policy))
            policy_digest=policy_hash(policy)
            head=rpc.request("eth_getBlockByNumber",["latest",False])
            close=int(head["timestamp"],16)+60
            transact("request","consumer",{
                "profileHash":profile_digest,"policyHash":policy_digest,
                "maxEpochFeeWei":45,"biddingClose":close
            },consumer)
            transact("bid","provider",{"requestId":1,"epochFeeWei":31},losing_provider)
            transact("bid","provider",{"requestId":1,"epochFeeWei":25},winner)
            self.assertEqual(int(rpc.request("eth_call",[
                {"to":board,"data":_data("bidCount(uint256)",1)},"latest"]),16),2)
            now=int(rpc.request("eth_getBlockByNumber",["latest",False])["timestamp"],16)
            rpc.request("evm_increaseTime",[max(0,close-now+1)])
            rpc.request("evm_mine",[])
            transact("fund","consumer",{
                "requestId":1,"bidIndex":1,"selectedEpochFeeWei":25,
                "endpointHash":"0x"+keccak256(endpoint.encode("ascii")).hex(),
                "reservationFeeWei":0,"exposureBudgetWei":25,"maxEpochs":1,
                "responsePeriodSeconds":600,"monitorGraceSeconds":300,
                "evidenceWindowSeconds":300,
            },consumer)
            offered=inspect_chain(rpc,settlement,1,0,expected_chain_id=CHAIN)
            self.assertEqual(offered["lease"]["marketplaceRequestId"],1)
            self.assertEqual(offered["lease"]["provider"],winner.address.lower())
            self.assertEqual(offered["lease"]["consumer"],consumer.address.lower())
            self.assertNotEqual(winner.address.lower(),losing_provider.address.lower())
            self.assertEqual(offered["lease"]["slaPolicyHash"],policy_digest)
            self.assertEqual(offered["lease"]["resourceProfileHash"],profile_digest)
            self.assertEqual(offered["lease"]["reservationFee"],0)
            self.assertEqual(offered["lease"]["totalEscrow"],25)
            transact("accept","provider",{"leaseId":1},winner)
            assignment=offered["lease"]["assignmentId"]
            # Existing lab-only source-controlled entropy is not unbiased VRF.
            _unlocked(rpc,consumer.address,pool,
                      _data("fulfillRandomness(uint256,uint256)",assignment,123456))
            _unlocked(rpc,consumer.address,settlement,
                      _data("finalizeMonitorCommittee(uint256)",1))
            result=rpc.request("eth_call",[
                {"to":pool,"data":_data("getCommittee(uint256)",assignment)},"latest"])
            selected=_address_words(result)
            self.assertEqual(len(set(selected)),4)
            known={x.address.lower():x for x in monitors}
            for member in selected:
                transact("monitor-confirm","monitor",{"leaseId":1},known[member])
            challenge="0x"+keccak256(b"SSE_REAL_MARKETPLACE_COMPUTE_EPOCH_1").hex()
            transact("admit-epoch","consumer",
                     {"leaseId":1,"requestHash":challenge},consumer)

            def inspected(lease_id,epoch_id):
                return inspect_chain(rpc,settlement,lease_id,epoch_id,
                                     expected_chain_id=CHAIN,pin_block_hash=True)
            active=inspected(1,0)
            self.assertEqual(active["lease"]["stateName"],"Active")
            self.assertEqual(active["epoch"]["requestHash"],challenge)
            compare_to_lease(policy,active,endpoint=endpoint)
            self.assertEqual(active["lease"]["marketplaceRequestId"],1)
            self.assertEqual(active["lease"]["monitors"],selected)

            nonce="0x"+keccak256(b"UNIQUE_WORK_ORDER_ON_REAL_LEASE").hex()
            order=prepare_request(active,policy,endpoint,consumer,nonce)
            with self.assertRaises(ExchangeError):
                authenticate_request(order,active,policy,endpoint,losing_provider)
            with self.assertRaises(ExchangeError):
                prepare_request(active,policy,endpoint,losing_provider,nonce)

            private_journal_dir=tempfile.TemporaryDirectory()
            journal=DirectJournal(Path(private_journal_dir.name)/"provider-evidence.sqlite")
            compute_runner=None
            if use_docker:
                docker_port=_loopback_port()
                docker_endpoint="http://127.0.0.1:"+str(docker_port)
                docker_name="sse-compute-"+secrets.token_hex(5)
                command=docker_launch_argv(profile,policy,docker_endpoint,docker_name)
                started=subprocess.run(command,capture_output=True,text=True,
                                       timeout=45,check=False)
                self.assertEqual(started.returncode,0,started.stderr)
                docker_container_id=started.stdout.strip()
                self.assertRegex(docker_container_id,r"^[0-9a-f]{64}$")
                from urllib.request import urlopen
                for _ in range(100):
                    try:
                        with urlopen(docker_endpoint+"/healthz",timeout=.5) as health:
                            if health.status==200:
                                break
                    except (OSError,TimeoutError):
                        pass
                    time.sleep(.2)
                else:
                    self.fail("real Docker worker did not expose loopback service")
                compute_runner=make_docker_runner(
                    profile,policy,docker_endpoint,docker_name)
            server=make_server(service_port,winner,policy,endpoint,inspected,
                               journal=journal,compute_runner=compute_runner)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            exchange=submit_work_request(endpoint,active,policy,consumer,nonce)
            self.assertTrue(exchange["receiptAcceptedByProvider"])
            self.assertEqual(journal.counts(),{"RECEIVED":1})
            self.assertFalse(exchange["onChainSettlementSubmitted"])
            self.assertFalse(exchange["physicalDeadlineCertified"])
            response=exchange["response"]
            self.assertEqual(response["result"],
                             compute_result(1,0,challenge))
            self.assertEqual(
                validate_response(response,exchange["request"],active,policy,endpoint)["provider"],
                winner.address.lower())
            receipt=verify_receipt(exchange["receipt"],response,active,policy,endpoint)
            self.assertTrue(receipt["validSignature"])
            self.assertFalse(receipt["physicalDeadlineCertified"])
            with self.assertRaises(ExchangeError):
                post_json(endpoint,exchange["request"])
            observed=inspected(1,0)
            self.assertFalse(observed["epoch"]["responseAuthenticated"])
            self.assertEqual(observed["epoch"]["successVotes"],0)
            self.assertEqual(observed["epoch"]["failureVotes"],0)

            # The provider also signed the exact Solidity V1 challenge response.
            # The consumer can relay it on-chain without handling provider key.
            from eth_abi import encode
            v1sig=bytes.fromhex(response["providerV1Signature"][2:])
            calldata="0x"+(
                keccak256(b"submitProviderResponse(uint256,uint256,bytes)")[:4]+
                encode(["uint256","uint256","bytes"],[1,0,v1sig])
            ).hex()
            _unlocked(rpc,consumer.address,settlement,calldata)
            acknowledged=inspected(1,0)
            self.assertTrue(acknowledged["epoch"]["responseAuthenticated"])
            self.assertFalse(acknowledged["epoch"]["acknowledged"])
            self.assertEqual(acknowledged["epoch"]["successVotes"],0)
            self.assertEqual(acknowledged["epoch"]["failureVotes"],0)
            # The chain authenticates provider response, not compute validity.
            self.assertFalse(acknowledged["computeProvisioningVerified"])
            self.assertFalse(acknowledged["deadlineTimelinessCertified"])
            self.assertGreaterEqual(len(submitted),5+1+2+1+1+4+1)
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            if worker is not None:
                worker.join(timeout=5)
            if private_journal_dir is not None:
                private_journal_dir.cleanup()
            if docker_container_id is not None:
                subprocess.run(["docker","stop",docker_container_id],
                               capture_output=True,text=True,timeout=20,
                               check=False)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__=="__main__":
    unittest.main()
