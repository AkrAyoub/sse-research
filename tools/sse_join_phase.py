#!/usr/bin/env python3
"""R148: role-neutral first-peer vs joining-peer requirements.

No fixed bootstrap IP, enode, ENR, overlay network address, or privileged
owner. Distinguishes STARTING an isolated instance of an existing chain
from CREATING a new genesis and STARTING block production.
"""
from __future__ import annotations
import json
import re

CHAIN_ID = 31340
EL_GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
CL_GENESIS = "0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"

class Refused(ValueError):
    pass

def admission(*, genesis_el, genesis_cl, phase, discovered_peers=0,
              active_local_genesis_validators=0, owner_signing_key_present=False):
    # The network has an immutable original chain identity.  "first peer"
    # never means inventing a different genesis or cloning a signer.
    if genesis_el != EL_GENESIS or genesis_cl != CL_GENESIS:
        raise Refused("original chain31340 genesis identity not verified")
    if phase not in ("first_online_peer", "joining_peer"):
        raise Refused("unknown network phase")
    if type(discovered_peers) is not int or discovered_peers < 0:
        raise Refused("invalid observed peer count")
    if (type(active_local_genesis_validators) is not int
            or active_local_genesis_validators < 0
            or type(owner_signing_key_present) is not bool):
        raise Refused("invalid signing-state observation")
    # A lone honest full node has always been allowed to start in isolation.
    # This is not proof of liveness: finality depends on actual active stake.
    # There is no hardcoded bootstrap peer list and no permission token.
    first = phase == "first_online_peer"
    if not first and discovered_peers == 0:
        return {
            "chainId": CHAIN_ID,
            "phase": phase, "canStartReadOnlyClients": True,
            "chainGenesisRecreated": False, "hardcodedBootnodesRequired": False,
            "nativePeerDiscoveryRequiredForSync": True,
            "nativePeerDiscoveryPresent": False,
            "consensusLiveOrFinalityProven": False,
            "state": "WAITING_FOR_ACTUAL_NATIVE_PEERS_NOT_SYNCHRONIZED",
        }
    return {
        "chainId": CHAIN_ID, "phase": phase,
        "canStartReadOnlyClients": True,
        "chainGenesisRecreated": False,
        "hardcodedBootnodesRequired": False,
        "nativePeerDiscoveryRequiredForSync": not first,
        "nativePeerDiscoveryPresent": discovered_peers > 0,
        "consensusLiveOrFinalityProven": False,
        "locallyAuthorizedExistingGenesisSignerObserved": (
            owner_signing_key_present and active_local_genesis_validators > 0),
        "state": ("FIRST_PEER_WITHOUT_FINALITY_PROOF" if first else
                  "PEERS_VISIBLE_FINALITY_NOT_YET_VERIFIED"),
    }
