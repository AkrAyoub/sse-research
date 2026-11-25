#!/usr/bin/env python3
"""R234: V2-only provider-side real Docker compute plus PUBLIC pre-signed reply.

NEVER loads or exports wallet private keys, never signs a message, never
starts/stops Docker, never submits an EVM transaction. --serve explicitly
starts an IPv4 LOOPBACK-ONLY HTTP service; an owner-operated authenticated
TLS reverse proxy is required for outside access. Every accepted request
checks real Docker configuration and executes the running CPU worker before
serving its previously authenticated EIP-712 reply; deterministic output is
not hardware attestation. The source-only dry-run does not invoke Docker.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))

from compute_workload import compute_result
from sse_compute_docker import (
    ComputeError,inspect_container,local_endpoint,run_compute_probe,
)
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,
)
from sse_pos_r229_v2_finalized_lease_snapshot import (
    Refused as SnapshotRefused,inspect as inspect_lease,
)
from sse_pos_r231_v2_compute_wire import (
    Refused as WireRefused,payload_from_result,validate_signed_reply,
)
from sse_pos_r233_public_v2_compute_terms import (
    Refused as TermsRefused,validate_profile,validate_policy,
    resource_hash,policy_hash,
)

MAX_HTTP_BODY=1024
NAME=re.compile(r"sse-compute-[a-z0-9][a-z0-9-]{0,45}\Z")


class Refused(ValueError):
    pass


def unique_pairs(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:
            raise Refused("duplicate JSON provider request field")
        obj[key]=value
    return obj


def load_public_json(path,maxbytes=8192):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=maxbytes:
        raise Refused("bounded, regular, non-symlink public input required")
    return json.loads(path.read_text("utf-8"),object_pairs_hook=unique_pairs)


def verify_config(profile,policy,signed_payload,snapshot,*,allow_canonical=False):
    validate_policy(policy,profile)
    provisional=(snapshot.get("schema")=="SSE_R350_CANONICAL_V2_LEASE_READONLY_V1" and
                 snapshot.get("finalizedAuthorization") is False and
                 snapshot.get("reorganizationPossible") is True)
    if ((snapshot.get("schema")!="SSE_R229_FINALIZED_V2_LEASE_READONLY_V1" and
         not (allow_canonical is True and provisional)) or
        snapshot.get("deploymentRuntimeAndWiringAttested") is not True or
        snapshot.get("chainId")!=31340):
        raise Refused("R206/R229 original-chain finalized attestation absent")
    lease=snapshot["lease"]
    ep=snapshot["epoch"]
    if (ep is None or ep["market"]["exists"] is not True or
        ep["ledger"]["exists"] is not True or
        lease["phase"]!=4 or lease["providerAccepted"] is not True or
        snapshot["committee"]["ready"] is not True or
        ep["ledger"].get("monitoringSealed") is True or ep["market"].get("resolved") is True):
        raise Refused("not active finalized paid provider compute epoch")
    if (lease["profileHash"]!=resource_hash(profile) or
        lease["policyHash"]!=policy_hash(policy,profile) or
        policy["market"].lower()!=snapshot["market"].lower()):
        raise Refused("profile/policy not committed in actual funded lease")
    from sse_challenge import keccak256
    if lease["endpointHash"]!="0x"+keccak256(profile["origin"].encode("ascii")).hex():
        raise Refused("public TLS provider endpoint origin not lease-committed")
    check=validate_signed_reply(signed_payload,snapshot,allow_canonical=True) if provisional else validate_signed_reply(signed_payload,snapshot)
    if check["providerPublicSignatureVerified"] is not True:
        raise Refused("provider pre-signed V2 payload cannot be authenticated")
    return {
        "schema":"SSE_R234_V2_DOCKER_PROVIDER_READONLY_PLAN_V1",
        "leaseId":snapshot["leaseId"],"epochId":snapshot["epochId"],
        "requestHash":ep["market"]["requestHash"],
        "provider":lease["provider"],
        "publicOrigin":profile["origin"],
        "signedResponseHash":check["responseHash"],
        "sourceManifestAndActualLeaseAttested":True,
        "leaseStateFinalized":not provisional,
        "localDockerInspectedOrStarted":False,
        "externalProviderHttpServerStarted":False,
        "transactionSignedOrSubmitted":False,
        "independentPhysicalComputeProved":False,
    }


def make_docker_executor(profile,endpoint,container_name,*,rootless_docker=False,dedicated_vm4714_sudo_docker=False):
    if rootless_docker and dedicated_vm4714_sudo_docker:
        raise Refused("Docker inspection modes are mutually exclusive")
    if dedicated_vm4714_sudo_docker and (os.geteuid()==0 or container_name!="sse-compute-vm4714" or endpoint!="http://127.0.0.1:8877"):
        raise Refused("dedicated inspection requires exact nonroot local worker")
    validate_profile(profile)
    local_endpoint(endpoint)
    if type(container_name) is not str or not NAME.fullmatch(container_name):
        raise Refused("unapproved local Docker worker name")
    local_profile={
        "endpoint":endpoint,"imageId":profile["dockerImageId"],
        "cpuMilli":profile["cpuMilli"],"memoryBytes":profile["memoryBytes"]
    }
    def compute(lease_id,epoch_id,request_hash):
        inspection_options={"strict_hardening":True}
        if rootless_docker:
            if os.geteuid()==0:
                raise Refused("rootless worker inspection forbids root process")
            inspection_options["docker_socket"]=f"/run/user/{os.geteuid()}/docker.sock"
        if dedicated_vm4714_sudo_docker:
            inspection_options["dedicated_vm4714_sudo_docker"]=True
        verified=inspect_container(local_profile,endpoint,container_name,
                                   **inspection_options)
        if verified["runtimeReportedRunning"] is not True:
            raise Refused("real Docker worker not running")
        result=run_compute_probe(endpoint,lease_id,epoch_id,request_hash)
        expected=compute_result(lease_id,epoch_id,request_hash)
        if (result["workloadResultVerified"] is not True or
            result["resultDigest"]!=expected["resultDigest"] or
            result["rounds"]!=expected["rounds"]):
            raise Refused("real worker did not return authenticated CPU result")
        return expected
    return compute


def make_server(port,context,signed_payload,profile,executor,*,authorize_request=None):
    if type(port) is not int or not (port==0 or 1024<=port<=65535):
        raise Refused("provider port must be unprivileged; 0 is test-only auto-bind")
    if type(executor).__name__ not in ("function","method"):
        raise Refused("actual Docker compute function required")
    expected={
        "leaseId":context["leaseId"],"epochId":context["epochId"],
        "requestHash":context["requestHash"]
    }
    response_json=json.dumps(signed_payload,sort_keys=True,separators=(",",":"),
                             ensure_ascii=True,allow_nan=False).encode("ascii")

    class Handler(BaseHTTPRequestHandler):
        def respond(self,status,payload):
            raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("ascii")
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path!="/healthz":
                return self.respond(404,{"error":"not found"})
            return self.respond(200,{
                "service":"SSE_V2_LOCAL_DOCKER_PROVIDER",
                "providerSignaturePreverified":True,
                "dockerInspectedForThisHealthCheck":False,
                "sourceNodeOrSlaVerified":False,
            })

        def do_POST(self):
            if self.path!="/v2/challenge":
                return self.respond(404,{"error":"not found"})
            try:
                size=self.headers.get("Content-Length","")
                if not size.isdecimal() or not 1<=int(size)<=MAX_HTTP_BODY:
                    raise Refused("invalid request size")
                self.connection.settimeout(8)
                raw=self.rfile.read(int(size))
                data=json.loads(raw.decode("utf-8"),
                                object_pairs_hook=unique_pairs)
                if type(data) is not dict or data!=expected or any(
                    type(data[k]) is not type(expected[k]) for k in expected
                ):
                    raise Refused("not the pinned on-chain challenge")
                # On EVERY request, real Docker inspect + actual CPU endpoint
                # must succeed before releasing a pre-signed public payload.
                if authorize_request is not None:
                    authorize_request()
                result=executor(expected["leaseId"],expected["epochId"],
                                expected["requestHash"])
                bound=payload_from_result(
                    expected["leaseId"],expected["epochId"],
                    expected["requestHash"],profile_hash,policy_hash_value,result)
                if any(signed_payload[k]!=bound[k] for k in bound):
                    raise Refused("real worker output not equal to signed payload")
                if authorize_request is not None:
                    authorize_request()
            except (Refused,ComputeError,WireRefused,ValueError,TypeError,
                    OSError,OverflowError,KeyError):
                return self.respond(503,{"error":"provider cannot verify Docker work"})
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json)

        def log_message(self,*args):
            return

    # These profile/policy hashes were already independently matched to
    # R229 finalized state by verify_config before the caller starts server.
    profile_hash=context["profileHash"]
    policy_hash_value=context["policyHash"]
    return HTTPServer(("127.0.0.1",port),Handler)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--lease-id",required=True,type=int)
    p.add_argument("--epoch-id",required=True,type=int)
    p.add_argument("--profile",required=True,type=Path)
    p.add_argument("--policy",required=True,type=Path)
    p.add_argument("--signed-reply",required=True,type=Path,
                   help="public pre-signed V2 JSON reply; NEVER a private key")
    p.add_argument("--worker-endpoint",default="http://127.0.0.1:8877")
    p.add_argument("--container",help="actual Docker worker name for --serve")
    p.add_argument("--port",type=int,default=8879)
    p.add_argument("--serve",action="store_true",
                   help="explicitly serve local HTTP after real Docker policy check")
    modes=p.add_mutually_exclusive_group()
    modes.add_argument("--rootless-docker",action="store_true",
                   help="use ONLY private /run/user/<uid>/docker.sock for per-request Docker inspect; no privileged daemon fallback")
    modes.add_argument("--dedicated-vm4714-sudo-docker",action="store_true",
                       help="explicit existing nonroot VM4714 local strict inspect only; no socket permission changes")
    p.add_argument("--canonical-confirmations",type=int,help="explicit provisional provider startup; reorg risk remains")
    a=p.parse_args(argv)
    try:
        profile=load_public_json(a.profile)
        policy=load_public_json(a.policy)
        signed=load_public_json(a.signed_reply)
        manifest=load_manifest(a.manifest)
        from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical,block_identity
        provisional=a.canonical_confirmations is not None
        snapshot=inspect_canonical(manifest,a.rpc,a.lease_id,a.epoch_id,confirmations=a.canonical_confirmations) if provisional else inspect_lease(manifest,a.rpc,a.lease_id,a.epoch_id)
        report=verify_config(profile,policy,signed,snapshot,allow_canonical=provisional)
        if not a.serve:
            print(json.dumps(report,sort_keys=True,indent=2))
            return 0
        if not a.container or not 1024<=a.port<=65535:
            raise Refused("--serve requires actual Docker worker and explicit unprivileged port")
        executor=make_docker_executor(profile,a.worker_endpoint,a.container,
                                      rootless_docker=a.rootless_docker,
                                      dedicated_vm4714_sudo_docker=a.dedicated_vm4714_sudo_docker)
        context={
            **report,"profileHash":snapshot["lease"]["profileHash"],
            "policyHash":snapshot["lease"]["policyHash"],
        }
        from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical
        from sse_pos_r206_adaptive_v2_deployment_audit import rpc
        import time
        def authorize_request():
            if provisional:
                height=snapshot["observedExecutionHeight"]
                if block_identity(rpc(a.rpc,"eth_getBlockByNumber",[hex(height),False]))!=(height,snapshot["observedExecutionHash"]):
                    raise Refused("provider startup anchor reorganized; restart with reviewed state")
            state=inspect_canonical(manifest,a.rpc,a.lease_id,a.epoch_id)
            ep=state["epoch"]["ledger"]
            if (state["lease"]["phase"]!=4 or not state["lease"]["providerAccepted"]
                or not state["committee"]["ready"] or not ep["exists"]
                or ep["monitoringSealed"] or state["epoch"]["market"]["resolved"]
                or ep["requestHash"]!=context["requestHash"]
                or state["lease"]["provider"]!=context["provider"]
                or state["lease"]["profileHash"]!=context["profileHash"]
                or state["lease"]["policyHash"]!=context["policyHash"]
                or state["lease"]["endpointHash"]!=snapshot["lease"]["endpointHash"]
                or (ep["responseAuthenticated"] and ep["responseHash"]!=context["signedResponseHash"])):
                raise Refused("provider epoch no longer authorized")
            block=rpc(a.rpc,"eth_getBlockByNumber",[hex(state["observedExecutionHeight"]),False])
            if (block["hash"].lower()!=state["observedExecutionHash"]
                or max(time.time(),int(block["timestamp"],16))>=ep["monitoringClose"]):
                raise Refused("provider epoch anchor changed or deadline passed")
        authorize_request()
        server=make_server(a.port,context,signed,profile,executor,authorize_request=authorize_request)
        print("R234_V2_PROVIDER_LOOPBACK_HTTP_READY=true",flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    except (Refused,AuditRefused,SnapshotRefused,WireRefused,TermsRefused,
            ComputeError,ValueError,TypeError,KeyError,OSError) as exc:
        print("R234_V2_PROVIDER_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
