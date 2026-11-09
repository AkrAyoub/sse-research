#!/usr/bin/env python3
"""Read-only Ethereum EL/CL snapshot. No keys, signing, deposits or RPC mutation.

Sample: python tools/check_ethereum_network.py \\
  --rpc http://127.0.0.1:8545 --chain-id 32382 \\
  --beacon http://127.0.0.1:5052 --output results/network-check.json

For an independently configured CL use a local private URL. A successful
read does NOT prove permissionless onboarding, validator decentralization,
or that a fresh finality checkpoint occurred.
"""
import argparse,json,sys,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit


def _request(url,body=None):
    obj=urlsplit(url)
    if obj.scheme not in ('http','https') or not obj.hostname or obj.username or obj.password:
        raise ValueError('use http(s) URL without embedded credentials')
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=8) as response:
        if response.status != 200: raise RuntimeError('HTTP status not 200')
        return json.load(response)


def rpc(url,method):
    result=_request(url,{'jsonrpc':'2.0','id':1,'method':method,'params':[]})
    if result.get('error') is not None: raise RuntimeError(f'RPC error: {result["error"]}')
    if 'result' not in result: raise RuntimeError('missing result')
    return result['result']


def inspect(rpc_url,expected_chain,beacon_url=None):
    chain=int(rpc(rpc_url,'eth_chainId'),16)
    height=int(rpc(rpc_url,'eth_blockNumber'),16)
    peers=int(rpc(rpc_url,'net_peerCount'),16)
    result={'kind':'LIVE_READ_ONLY_NETWORK_INSPECTION','timestamp':datetime.now(timezone.utc).isoformat(),
            'ethereum_execution':{'chain_id':chain,'block_number':height,'peer_count':peers},
            'expected_chain_id':expected_chain,'chain_id_matches':chain==expected_chain,
            'fresh_block_production_verified':False,
            'unknown_validators_joined':False,
            'sse_transaction_verified':False}
    if beacon_url:
        base=beacon_url.rstrip('/')
        head=_request(base+'/eth/v1/beacon/headers/head')
        finality=_request(base+'/eth/v1/beacon/states/head/finality_checkpoints')
        result['ethereum_consensus']={
            'head_slot':head.get('data',{}).get('header',{}).get('message',{}).get('slot'),
            'finalized_checkpoint':finality.get('data',{}).get('finalized'),
            'response_received':True}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--rpc',required=True)
    p.add_argument('--beacon')
    p.add_argument('--chain-id',required=True,type=int)
    p.add_argument('--output')
    a=p.parse_args()
    try:
        result=inspect(a.rpc,a.chain_id,a.beacon)
        print(json.dumps(result,indent=2))
        if a.output:
            target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(result,indent=2)+'\n')
        if not result['chain_id_matches']:
            sys.exit('ERROR: execution chain ID does not match expectation')
    except (ValueError,RuntimeError,urllib.error.URLError,TimeoutError,KeyError,TypeError) as e:
        sys.exit(f'ERROR: could not verify network: {e}')
