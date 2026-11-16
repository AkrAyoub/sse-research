"""Fail-closed local role manifest and monitor counterparty conflict checks.

One Ubuntu VM may own multiple application roles. This policy prevents a
configured local consumer/provider wallet from simultaneously witnessing
its own funded lease using that VM's monitor wallet. Wallet/address checks
are NOT proof that two distinct VMs have independent operators: operator
identity, Sybil resistance and topology attestation remain open research.
"""
from __future__ import annotations

import re

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
NODE = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
APPLICATION = frozenset(("consumer", "provider", "monitor", "observer"))


class RolePolicyError(ValueError):
    pass


def role_manifest(manifest):
    if type(manifest) is not dict or set(manifest) != {"schema","nodeId","roles","wallets"}:
        raise RolePolicyError("invalid node role manifest schema")
    if manifest["schema"] != "sse-node-roles-v1" or (
            type(manifest["nodeId"]) is not str or not NODE.fullmatch(manifest["nodeId"])):
        raise RolePolicyError("unrecognized node roles or node ID")
    roles, wallets = manifest["roles"], manifest["wallets"]
    if (type(roles) is not list or not roles or
            any(type(r) is not str or r not in APPLICATION for r in roles) or
            len(roles) != len(set(roles)) or type(wallets) is not dict or
            set(wallets) != (set(roles) - {"observer"})):
        raise RolePolicyError("node roles and owned application wallets disagree")
    for r, address in wallets.items():
        if type(address) is not str or not ADDRESS.fullmatch(address) or int(address,16)==0:
            raise RolePolicyError("missing or invalid node role wallet")
    owned = [x.lower() for x in wallets.values()]
    if len(owned) != len(set(owned)):
        raise RolePolicyError("each locally operated role must use its own wallet")
    return {"schema":"sse-node-roles-v1","nodeId":manifest["nodeId"],
            "roles":list(roles),"wallets":{r:v.lower() for r,v in wallets.items()}}


def authorize_selected_monitor(manifest, chain_snapshot, monitor_signer):
    node = role_manifest(manifest)
    if "monitor" not in node["roles"]:
        raise RolePolicyError("node has not configured a monitor role")
    if (type(monitor_signer) is not str or not ADDRESS.fullmatch(monitor_signer) or
            monitor_signer.lower() != node["wallets"]["monitor"]):
        raise RolePolicyError("monitor signer is not this node's monitor wallet")
    if (type(chain_snapshot) is not dict or
            chain_snapshot.get("schema") != "sse-onchain-inspection-v1" or
            chain_snapshot.get("blockHashPinned") is not True or
            chain_snapshot.get("domainSeparatorMatches") is not True):
        raise RolePolicyError("monitor requires a pinned chain inspection")
    lease = chain_snapshot.get("lease")
    epoch = chain_snapshot.get("epoch")
    if type(lease) is not dict or type(epoch) is not dict or epoch.get("exists") is not True:
        raise RolePolicyError("monitor requires admitted chain epoch")
    if lease.get("stateName") != "Active":
        raise RolePolicyError("monitor requires active lease")
    consumer, provider = lease.get("consumer"), lease.get("provider")
    if any(type(x) is not str or not ADDRESS.fullmatch(x) for x in (consumer, provider)):
        raise RolePolicyError("invalid lease counterparties")
    counterparties = {consumer.lower(), provider.lower()}
    if (monitor_signer.lower() in counterparties or
            counterparties.intersection(node["wallets"].values())):
        raise RolePolicyError("node may not witness its own consumer/provider lease")
    selected = lease.get("monitors")
    if (type(selected) is not list or len(selected) != 4 or
            any(type(x) is not str or not ADDRESS.fullmatch(x) for x in selected) or
            len({x.lower() for x in selected}) != 4 or
            monitor_signer.lower() not in {x.lower() for x in selected} or
            lease.get("monitorConfirmations") != 4):
        raise RolePolicyError("node monitor not in confirmed elected committee")
    if epoch.get("monitoringSealed") is not False or epoch.get("evidenceClosed") is not False:
        raise RolePolicyError("monitoring/evidence window no longer open")
    return {"nodeId":node["nodeId"],"monitor":monitor_signer.lower(),
            "selectedForLease":True,"localConflictChecked":True,
            "operatorIndependenceVerified":False,"voteAuthorized":False,
            "physicalSlaVerified":False}
