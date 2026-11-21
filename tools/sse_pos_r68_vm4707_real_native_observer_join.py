#!/usr/bin/env python3
"""R68: one-command REAL non-signing VM4707 observer join, public bootstraps.

Public bootstrap identities are copied verbatim from R67 ACTUAL VM4706
read-only RPC + Beacon REST report after R65 owner migration 2026-11-21.
These are public node locators, never keys. No signer or simulated peer.
Read-only --plan first; --apply uses genuine R59 explicit user approval.
"""
from __future__ import annotations
import argparse
import json
import sys
import sse_pos_r59_native_ipv6_observer as r59

SOURCE_R67_GIT_SHA="25b317dcd43c0558a5a3c5811c5c8fc11dd19fc3"
SOURCE_CHAIN_ID=31340
SOURCE_OWNER_IPV6="fca0:2328:776e:4750:395b::1"
SOURCE_OBSERVED_FINALIZED_EPOCH=122
SOURCE_OBSERVED_FINALIZED_ROOT="0x6310aca4e76388f48323370de92019a9b7689ad4e742de698a2eb019486b7888"
SOURCE_EXECUTION_ENODE_V6="enode://25e1b943beafb981df59b037e19f4d9068ccf538777a4995931a2c31bb72a8b4f35255d8985dc42b0c15870fa76082efa5b3832e28f842e28777ede29a88dcbb@[fca0:2328:776e:4750:395b::1]:30404"
SOURCE_BEACON_ENR="enr:-NS4QINvGJM8jw3NULEdwhfpLeC7eylSPitzMevA7-r7bO41KGBbBTxKhDTccww8LE_4eKcXp1AYvRDQJpWWzGronAUOh2F0dG5ldHOIADAAAAAAAACEZXRoMpAqIL-xo0AABv__________gmlkgnY0g2lwNpD8oCMod25HUDlbAAAAAAABhXF1aWM2giMpiXNlY3AyNTZrMaED3Dl0SImVQ7LWs5wsQy9oisn9PP2CxN4druC6feLPQQyIc3luY25ldHMPhHRjcDaCIyiEdWRwNoIjKA"

def check_source_seed()->None:
    if not r59.bootnodes(SOURCE_EXECUTION_ENODE_V6,SOURCE_BEACON_ENR):
        raise r59.R59Refused("original public native EL+CL bootstrap records absent")
    if SOURCE_OWNER_IPV6 not in SOURCE_EXECUTION_ENODE_V6:
        raise r59.R59Refused("original source execution overlay IPv6 changed")

def main()->int:
    ap=argparse.ArgumentParser(description="Original chain31340 real VM4707 non-signing EL+CL join")
    x=ap.add_mutually_exclusive_group(required=True)
    x.add_argument("--plan",action="store_true")
    x.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    try:
        check_source_seed()
        if args.plan:
            status=r59.preflight(SOURCE_EXECUTION_ENODE_V6,SOURCE_BEACON_ENR)
            status["mode"]="readonly_r68_real_source_bootstrap_verified"
        else:
            status=r59.apply(SOURCE_EXECUTION_ENODE_V6,SOURCE_BEACON_ENR)
        status["actualR67SourceGitSha"]=SOURCE_R67_GIT_SHA
        status["originalObservedFinalizedEpochBeforeObserverLaunch"]=SOURCE_OBSERVED_FINALIZED_EPOCH
        status["originalObservedFinalizedRootBeforeObserverLaunch"]=SOURCE_OBSERVED_FINALIZED_ROOT
        status["ownerActualNativePeerStatusBeforeObserverLaunch"]="EL_0_CL_0"
        status["originalRealSourceBootstrapIdentityPairsPassedToR59"]=True
        status["liveOutsideProviderNativeP2pAndRootAgreementStillUnverified"]=True
        print(json.dumps(status,sort_keys=True,indent=2))
        return 0
    except (r59.R59Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R68_NON_SIGNING_REAL_OBSERVER_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
