#!/usr/bin/env python3
"""Headless, invite-only genesis-validator Tailscale join on a FRESH Ubuntu VM.

This command is distinct from application-role enrollment and cannot grant a
QBFT validator vote or register an SSE monitor. The node gets a short-lived,
one-time Tailscale key from the dedicated *validator* broker. No Tailscale
OAuth credentials reach this VM. Existing connected devices (VM4704) are
explicitly NOT reauthenticated.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from sse_vm_enroll import safe_broker_url, NoRedirect
from sse_vm_overlay import _check_auth_file, _require_ubuntu_root, _command
from sse_validator_mesh_broker import VALID_IDS

INVITATION=Path("/run/sse/validator.invitation")
AUTH_KEY=Path("/run/sse/validator-once.authkey")
TAG="tag:sse-validator"


class JoinError(ValueError):
    pass


def plan(node_id, broker_origin, invitation_file=INVITATION):
    if type(node_id) is not str or node_id not in VALID_IDS:
        raise JoinError("only validator-1..4 genesis participant IDs allowed")
    if Path(invitation_file)!=INVITATION:
        raise JoinError("invitation must be in fixed root-owned /run/sse path")
    origin=safe_broker_url(broker_origin)
    if not urlsplit(origin).hostname.endswith(".ts.net"):
        raise JoinError("dedicated broker must use pinned Tailscale *.ts.net HTTPS origin")
    return {
        "kind":"SSE_VALIDATOR_HEADLESS_TAILSCALE_PLAN_V1",
        "mode":"DRY_RUN",
        "nodeId":node_id,"brokerOrigin":origin,
        "inviteFile":str(INVITATION),
        "aclTag":TAG,
        "needsOperatorOneTimeInvitation":True,
        "requiresNewUnjoinedUbuntuVM":True,
        "qbftVotingGranted":False,
        "ethereumTransactionsSent":False,
        "tailnetJoined":False,
    }


def read_status(call=_command):
    try:
        raw=call(["tailscale","status","--json"])
        data=json.loads(raw)
    except (ValueError,TypeError):
        raise JoinError("unparseable Tailscale state") from None
    if type(data) is not dict:
        raise JoinError("invalid Tailscale status")
    return data


def already_connected(status):
    if type(status) is not dict:
        raise JoinError("invalid Tailscale state")
    state=status.get("BackendState")
    if state=="Running":
        # Even if offline, never reauth an existing running identity by accident.
        raise JoinError("already joined a tailnet; preserve existing device identity")
    if state not in ("NeedsLogin","Stopped"):
        raise JoinError("tailnet in unexpected transitional state")
    return False


def request_key(origin,node_id,invitation):
    if type(invitation) is not str or not 32<=len(invitation)<=256:
        raise JoinError("invalid one-time invitation")
    body=json.dumps({"node_id":node_id,"invitation":invitation},
                    separators=(",",":")).encode("utf8")
    req=Request(origin+"/v1/mesh/validator",data=body,method="POST",
                headers={"Content-Type":"application/json","Accept":"application/json"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=10) as response:
            if response.status!=200:
                raise JoinError("broker denied validator invitation")
            raw=response.read(4097)
    except OSError:
        raise JoinError("validator broker unavailable; obtain new invitation if consumed") from None
    if len(raw)>4096:
        raise JoinError("unexpected validator response size")
    try:
        result=json.loads(raw)
    except (ValueError,UnicodeError):
        raise JoinError("validator enrollment response invalid") from None
    if (type(result) is not dict or result.get("nodeId")!=node_id
            or result.get("role")!="validator-overlay-only"
            or result.get("qbftVotingGranted") is not False
            or result.get("expiresInSeconds")!=300
            or type(result.get("tailnetAuthKey")) is not str
            or not result["tailnetAuthKey"].startswith("tskey-auth-")
            or len(result["tailnetAuthKey"])>2048):
        raise JoinError("broker response scope mismatch")
    return result["tailnetAuthKey"]


def join(prepared, *, fetch=request_key, call=_command,
         check_file=_check_auth_file, require_root=_require_ubuntu_root):
    if type(prepared) is not dict:
        raise JoinError("invalid immutable join plan")
    expected=plan(prepared.get("nodeId"),prepared.get("brokerOrigin"))
    if prepared!=expected:
        raise JoinError("join plan tampered")
    require_root()
    if shutil.which("tailscale") is None:
        raise JoinError("Tailscale client not installed")
    # Fail closed if VM4704 or any other host already has a device identity.
    already_connected(read_status(call))
    check_file(INVITATION)
    if AUTH_KEY.exists() or AUTH_KEY.is_symlink():
        raise JoinError("stale validator auth key on disk")
    raw_invite=INVITATION.read_text("ascii").strip()
    if not 32<=len(raw_invite)<=256:
        raise JoinError("invalid invitation length")
    key=fetch(expected["brokerOrigin"],expected["nodeId"],raw_invite)
    if type(key) is not str or not key.startswith("tskey-auth-") or len(key)>2048:
        raise JoinError("invalid broker-provisioned auth key")
    fd=os.open(AUTH_KEY,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               (os.O_NOFOLLOW if hasattr(os,"O_NOFOLLOW") else 0),0o600)
    try:
        with os.fdopen(fd,"w",encoding="ascii") as fh:
            fh.write(key+"\n")
        call(["tailscale","up","--auth-key=file:"+str(AUTH_KEY),
              "--hostname=sse-"+expected["nodeId"],
              "--advertise-tags="+TAG,"--accept-routes=false",
              "--accept-dns=true"])
        result=read_status(call)
        if result.get("BackendState")!="Running":
            raise JoinError("tailnet did not reach running state")
        own=result.get("Self")
        if type(own) is not dict or own.get("Online") is not True:
            raise JoinError("tailnet did not verify online device")
        ips=own.get("TailscaleIPs",[])
        stable_id=own.get("StableID") or own.get("ID")
        overlay=[]
        if type(ips) is list:
            for item in ips:
                try:
                    address=ipaddress.IPv4Address(item)
                    if address in ipaddress.ip_network("100.64.0.0/10"):
                        overlay.append(str(address))
                except (ValueError,TypeError):
                    pass
        if (len(overlay)!=1 or type(stable_id) is not str
                or not 2<=len(stable_id)<=128):
            raise JoinError("joined device has no stable Tailscale identity")
        state={"ip":overlay[0],"stableId":stable_id}
    finally:
        AUTH_KEY.unlink(missing_ok=True)
    INVITATION.unlink(missing_ok=True)
    return {
        "kind":"SSE_VALIDATOR_TAILNET_JOINED_V1",
        "nodeId":expected["nodeId"],
        "overlayIPv4":state["ip"],
        "tailscaleStableId":state["stableId"],
        "oneTimeKeyErased":True,
        "invitationErased":True,
        "qbftVotingGranted":False,
        "ethereumTransactionsSent":False,
        "besuProcessStarted":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Headless SSE validator Tailscale join (one-use broker invitation)")
    p.add_argument("--node-id",required=True)
    p.add_argument("--broker-url",required=True)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args(argv)
    try:
        cfg=plan(args.node_id,args.broker_url)
        result=join(cfg) if args.apply else cfg
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (JoinError,OSError,ValueError,TypeError,KeyError) as exc:
        print("SSE_VALIDATOR_JOIN_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
