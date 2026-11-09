"""SSE local Anvil integration demo: HTTP -> EIP-712 -> quorum -> escrow settlement.

Requires B1 reader and existing HTTP service/probe, no additional dependencies.
**DEVELOPMENT ONLY**: uses unlocked Anvil accounts, advances simulated chain time,
uses three probes from one localhost host, and does NOT provision cloud compute.

From project root, with Anvil and provider HTTP server running:
  python tools/sse_e2e_local.py --settlement "$NEW_SSE" --execute --fast-forward
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))
sys.path.insert(0, str(ROOT / 'services' / 'provider-agent'))
from sse_challenge import keccak256, bytes32
from sse_chain_read import (LocalRPC, ChainReadError, inspect_chain, _function_call,
                            _domain_separator, _words, _address, ZERO_ADDR)
from http_probe import observe
from resource_profile import load_profile, profile_hash, verify_lease_profile
from sse_compute_docker import inspect_container, run_compute_probe, ComputeError

CHAIN_ID = 31337
EXPECTED_SETTLEMENT = '0x0dcd1bf9a1b36ce34237eeafef220932846bcd82'
DEFAULT_CONSUMER = '0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266'
DEFAULT_PROVIDER = '0x70997970c51812dc3a010c7d01b50e0d17dc79c8'
ADDR = re.compile(r'0x[0-9a-fA-F]{40}\Z')
HASH = re.compile(r'0x[0-9a-fA-F]{64}\Z')
TXHASH = re.compile(r'0x[0-9a-fA-F]{64}\Z')


class DemoError(Exception):
    pass


def word(value: int | str) -> bytes:
    if type(value) is int and 0 <= value < 2**256:
        return value.to_bytes(32, 'big')
    if isinstance(value, str) and ADDR.fullmatch(value):
        return int(value, 16).to_bytes(32, 'big')
    if isinstance(value, str) and HASH.fullmatch(value):
        return bytes.fromhex(value[2:])
    raise DemoError('invalid value for ABI word')


def encode_static(signature: str, *values: int | str) -> str:
    return '0x' + (_selector(signature) + b''.join(word(v) for v in values)).hex()


def _selector(signature: str) -> bytes:
    return keccak256(signature.encode('ascii'))[:4]


def encode_last_bytes(signature: str, values: tuple, payload: str) -> str:
    """ABI function with fixed head values and one final dynamic bytes argument."""
    if not isinstance(payload, str) or not payload.startswith('0x'):
        raise DemoError('signature must be hexadecimal')
    try:
        raw = bytes.fromhex(payload[2:])
    except ValueError as exc:
        raise DemoError('signature must be hexadecimal') from exc
    if len(raw) != 65:
        raise DemoError('expected 65-byte Ethereum signature')
    num_head_words = len(values) + 1
    tail = word(len(raw)) + raw + b'\0' * ((-len(raw)) % 32)
    encoded = _selector(signature) + b''.join(word(v) for v in values) + word(32 * num_head_words) + tail
    return '0x' + encoded.hex()


def one_address(rpc, contract: str, signature: str) -> str:
    data = rpc.request('eth_call', [{'to': contract, 'data': _function_call(signature)}, 'latest'])
    return '0x' + _words(data, 1)[0][-40:]


def one_uint(rpc, contract: str, signature: str) -> int:
    data = rpc.request('eth_call', [{'to': contract, 'data': _function_call(signature)}, 'latest'])
    return int(_words(data, 1)[0], 16)


def latest_timestamp(rpc) -> int:
    block = rpc.request('eth_getBlockByNumber', ['latest', False])
    if not isinstance(block, dict) or not isinstance(block.get('timestamp'), str):
        raise DemoError('missing latest block timestamp')
    return int(block['timestamp'], 16)


def tx(rpc, sender: str, to: str, data: str, value: int = 0) -> str:
    """Send unlocked-local-Anvil transaction; require a successfully mined receipt."""
    if not (ADDR.fullmatch(sender) and ADDR.fullmatch(to)) or not isinstance(data, str):
        raise DemoError('bad transaction sender/recipient/data')
    params = {'from': sender, 'to': to, 'data': data, 'gas': hex(6000000)}
    if value:
        params['value'] = hex(value)
    transaction = rpc.request('eth_sendTransaction', [params])
    if not isinstance(transaction, str) or not TXHASH.fullmatch(transaction):
        raise DemoError('RPC did not return a 32-byte transaction hash')
    for _ in range(30):
        receipt = rpc.request('eth_getTransactionReceipt', [transaction])
        if receipt is not None:
            if not isinstance(receipt, dict) or receipt.get('status') != '0x1':
                raise DemoError('transaction reverted, hash=' + transaction)
            return transaction
        time.sleep(0.1)
    raise DemoError('transaction not mined; hash=' + transaction)


def eip712(primary_type: str, address: str, request: dict, chain_id: int, contract: str) -> dict:
    fields = {
        'ProviderResponse': [('leaseId','uint256'), ('epochId','uint256'),
                             ('requestHash','bytes32'), ('responseHash','bytes32')],
        'MonitorVote': [('leaseId','uint256'), ('epochId','uint256'),
                        ('requestHash','bytes32'), ('outcome','uint8'),
                        ('responseHash','bytes32'), ('evidenceHash','bytes32')],
    }
    if primary_type not in fields:
        raise DemoError('invalid EIP-712 type')
    expected = {key for key, _ in fields[primary_type]}
    if set(request) != expected:
        raise DemoError('wrong EIP-712 message field names')
    return {
        'types': {
            'EIP712Domain': [{'name':'name','type':'string'}, {'name':'version','type':'string'},
                             {'name':'chainId','type':'uint256'},
                             {'name':'verifyingContract','type':'address'}],
            primary_type: [{'name':name,'type':kind} for name,kind in fields[primary_type]],
        },
        'primaryType': primary_type,
        'domain': {'name':'SSESettlement','version':'1', 'chainId':chain_id,
                   'verifyingContract':contract},
        'message': request,
    }


def sign(rpc, signer: str, data: dict) -> str:
    """Anvil-only EIP-712 signing. Try standard v4 JSON string, then object form."""
    err = None
    for value in (json.dumps(data, separators=(',', ':')), data):
        try:
            signature = rpc.request('eth_signTypedData_v4', [signer, value])
            if isinstance(signature, str) and signature.startswith('0x') and len(bytes.fromhex(signature[2:])) == 65:
                return signature
            raise DemoError('RPC returned an invalid EIP-712 signature')
        except (ChainReadError, ValueError) as exc:
            err = exc
    raise DemoError('Anvil cannot sign typed data for '+ signer + ': '+ str(err))


def quick_health(endpoint: str):
    # Endpoint is validated via the pre-existing observe() and B1 reader;
    # the actual preflight uses the exact loopback root URL.
    from urllib.parse import urlsplit
    u = urlsplit(endpoint)
    if u.scheme != 'http' or u.hostname != '127.0.0.1' or u.port is None or u.path not in ('','/') or u.query or u.fragment or u.username is not None or u.password is not None:
        raise DemoError('provider must use loopback endpoint http://127.0.0.1:PORT')
    try:
        with urlopen(endpoint.rstrip('/')+'/healthz', timeout=2.5) as response:
            info = json.loads(response.read(2049))
            if response.status != 200 or info.get('ok') is not True or info.get('service') != 'sse-local-challenge':
                raise DemoError('not the expected local SSE provider service')
    except OSError as exc:
        raise DemoError('provider service not reachable; start http_service.py first') from exc


def fast_forward(rpc, target: int) -> None:
    before = latest_timestamp(rpc)
    if target > before:
        rpc.request('evm_increaseTime', [target - before])
        rpc.request('evm_mine', [])
    if latest_timestamp(rpc) < target:
        raise DemoError('Anvil time advance failed')


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run(rpc, settlement: str, endpoint: str, out_dir: Path, do_execute: bool,
        do_fast_forward: bool, compute_profile_path: str | None = None,
        docker_container: str | None = None) -> dict:
    if (compute_profile_path is None) != (docker_container is None):
        raise DemoError('provide both --compute-profile and --docker-container, or neither')
    compute_profile = load_profile(compute_profile_path) if compute_profile_path else None
    settlement = _address(settlement)
    if settlement != EXPECTED_SETTLEMENT:
        raise DemoError('wrong settlement for this specific known Anvil deployment')
    old = inspect_chain(rpc, settlement, 1, 0, expected_chain_id=CHAIN_ID)
    oldlease = old['lease']
    if oldlease['consumer'] != DEFAULT_CONSUMER or oldlease['provider'] != DEFAULT_PROVIDER:
        raise DemoError('unknown Anvil identities for the known deployment')
    if oldlease['stateName'] != 'Closed' or oldlease['maxEpochs'] != 1:
        raise DemoError('unexpected baseline lease; refusing to modify chain')
    if old['epoch']['outcomeName'] != 'Failure' or not old['epoch']['evidenceClosed']:
        raise DemoError('old epoch is not the known completed failure scenario')
    pool = one_address(rpc, settlement, 'committeePool()')
    randomness_source = one_address(rpc, pool, 'randomnessSource()')
    accounts = rpc.request('eth_accounts', [])
    if not isinstance(accounts, list):
        raise DemoError('Anvil unlocked accounts not exposed')
    available = {v.lower() for v in accounts}
    must_have = {oldlease['consumer'], oldlease['provider'], randomness_source, *oldlease['monitors']}
    if not must_have.issubset(available) or ZERO_ADDR in must_have:
        raise DemoError('expected unlocked Anvil consumer/provider/monitors/randomness account unavailable')
    if one_uint(rpc, pool, 'candidateCount()') < 4:
        raise DemoError('not enough registered monitor candidates')
    quick_health(endpoint)
    local_container = None
    if compute_profile is not None:
        # Perform all possible checks BEFORE sending a transaction.
        local_container = inspect_container(compute_profile, endpoint, docker_container)
        run_compute_probe(endpoint, 1, 0, '0x' + secrets.token_bytes(32).hex())
    summary = {
        'schema':'sse-local-full-cycle-v1', 'chainId':CHAIN_ID, 'settlement':settlement,
        'committeePool':pool, 'endpoint':endpoint, 'mode':'LOCAL_ANVIL_ONLY',
        'usesArtificialChainTime':do_fast_forward, 'computeProvisioningVerified':False,
        'independentMonitorHosts':False, 'clockAttested':False,
        'providerHttpSignatureVerified':False,
        'usesDirectLeaseCreationNotMarketplace':True,
        'localDockerConfigurationInspected': local_container is not None,
        'localComputeWorkloadVerified':False,
        'remoteCloudProvisioningVerified':False,
        'containerInspect': local_container,
        'transactions':{}, 'evidenceFiles':[], 'evidenceCommitments':{}, 'status':'PREFLIGHT_OK',
    }
    if not do_execute:
        return summary

    consumer = oldlease['consumer']; provider = oldlease['provider']
    # The direct lease path tests the settlement workflow, not marketplace bid selection.
    # Three horizons are long enough for local manual debugging; then time is advanced.
    endpoint_hash = '0x' + keccak256(endpoint.encode('utf8')).hex()
    profile_commitment = profile_hash(compute_profile) if compute_profile is not None else oldlease['resourceProfileHash']
    fee, reserve, exposure, response_period, grace, evidence_period = 25, 5, 25, 600, 300, 300
    lease_id = one_uint(rpc, settlement, 'nextLeaseId()')
    record_path = out_dir / ('lease-' + str(lease_id)) / 'run.json'
    def record(label: str, txid: str | None = None):
        if txid is not None:
            summary['transactions'][label] = txid
        summary['status'] = label
        save_json(record_path, summary)
        print('  ->', label, flush=True)

    record('STARTED')
    record('CREATED', tx(rpc, consumer, settlement,
        encode_static('createLease(address,bytes32,bytes32,uint256,uint256,uint256,uint256,uint64,uint64,uint64)',
                      provider, endpoint_hash, profile_commitment, fee, reserve, exposure, 1,
                      response_period, grace, evidence_period), value=fee))
    lease = inspect_chain(rpc, settlement, lease_id, 0, endpoint=endpoint)['lease']
    if lease['stateName'] != 'Offered' or lease['assignmentId'] == 0 or lease['provider'] != provider:
        raise DemoError('new lease not in Offered state')
    if compute_profile is not None:
        verify_lease_profile(compute_profile, lease, endpoint)
        summary['committedResourceProfileHash'] = profile_commitment
    summary['leaseId'] = lease_id
    record('ACCEPTED', tx(rpc, provider, settlement,
        encode_static('acceptLease(uint256)', lease_id)))
    record('RANDOMNESS_FULFILLED', tx(rpc, randomness_source, pool,
        encode_static('fulfillRandomness(uint256,uint256)', lease['assignmentId'], secrets.randbits(192))))
    record('COMMITTEE_ASSIGNED', tx(rpc, consumer, settlement,
        encode_static('finalizeMonitorCommittee(uint256)', lease_id)))
    lease = inspect_chain(rpc, settlement, lease_id, 0, endpoint=endpoint)['lease']
    monitors = lease['monitors']
    if len(set(monitors)) != 4 or not set(monitors).issubset(available):
        raise DemoError('unexpected or unavailable selected committee')
    summary['monitors'] = monitors
    for idx, monitor in enumerate(monitors):
        record('CONFIRM_'+str(idx+1), tx(rpc, monitor, settlement,
            encode_static('confirmMonitorAssignment(uint256)', lease_id)))
    request_hash = '0x' + keccak256(b'SSE LIVE E2E / ' + secrets.token_bytes(32)).hex()
    record('EPOCH_ADMITTED', tx(rpc, consumer, settlement,
        encode_static('admitEpoch(uint256,bytes32)', lease_id, request_hash)))
    view = inspect_chain(rpc, settlement, lease_id, 0, endpoint=endpoint)
    epoch = view['epoch']
    if epoch is None or epoch['requestHash'] != request_hash or view['lease']['stateName'] != 'Active':
        raise DemoError('new active epoch mismatch')
    summary['requestHash'] = request_hash
    summary['responseHash'] = epoch['responseHash']
    summary['responseDeadline'] = epoch['responseDeadline']
    summary['monitoringClose'] = epoch['monitoringClose']
    summary['evidenceClose'] = epoch['evidenceClose']
    record('EPOCH_CHAIN_BOUND')
    if compute_profile is not None:
        # The job is tied to the real requestHash of this *new* epoch.
        inspected = inspect_container(compute_profile, endpoint, docker_container)
        if inspected['containerId'] != local_container['containerId']:
            raise DemoError('Docker worker replaced since preflight')
        compute_obs = run_compute_probe(endpoint, lease_id, 0, request_hash)
        save_json(record_path.parent / 'provider_compute_observation.json', compute_obs)
        summary['localComputeWorkloadVerified'] = True
        summary['providerComputeObservation'] = compute_obs
        record('REAL_LOCAL_COMPUTE_OBSERVED')
    if latest_timestamp(rpc) >= epoch['responseDeadline']:
        raise DemoError('response deadline already reached before challenge')
    # Genuine HTTP interaction. The current existing provider is unsigned.
    preliminary = observe(endpoint, lease_id, 0, request_hash, duration=3.0)
    if preliminary['outcome'] != 'SUCCESS_OBSERVED':
        raise DemoError('provider HTTP challenge failed; no success vote will be produced')
    save_json(record_path.parent / 'provider_http_observation.json', preliminary)
    record('HTTP_PROBED')
    if latest_timestamp(rpc) >= epoch['responseDeadline']:
        raise DemoError('chain deadline reached before response attestation')
    provider_message = {'leaseId':lease_id,'epochId':0,'requestHash':request_hash,
                        'responseHash':epoch['responseHash']}
    provider_sig = sign(rpc, provider, eip712('ProviderResponse', provider, provider_message, CHAIN_ID, settlement))
    record('PROVIDER_RESPONSE_AUTHENTICATED', tx(rpc, consumer, settlement,
        encode_last_bytes('submitProviderResponse(uint256,uint256,bytes)',
                          (lease_id,0),provider_sig)))
    view = inspect_chain(rpc, settlement, lease_id, 0, endpoint=endpoint)
    if not view['epoch']['responseAuthenticated']:
        raise DemoError('provider signature not authenticated by contract')
    summary['providerResponseAuthenticatedOnChain'] = True
    record('RESPONSE_VERIFIED_ON_CHAIN')
    # Each selected monitor independently signs its own typed-data vote (but
    # all probes run on the same physical localhost, not independent hosts).
    for i, monitor in enumerate(monitors[:3]):
        if latest_timestamp(rpc) >= epoch['monitoringClose']:
            raise DemoError('monitoring window closed before votes')
        obs = observe(endpoint, lease_id, 0, request_hash, duration=3.0)
        compute_obs_monitor = None
        if compute_profile is not None:
            inspected = inspect_container(compute_profile, endpoint, docker_container)
            if inspected['containerId'] != local_container['containerId']:
                raise DemoError('Docker worker changed during monitoring')
            compute_obs_monitor = run_compute_probe(endpoint, lease_id, 0, request_hash)
        if obs['outcome'] != 'SUCCESS_OBSERVED':
            raise DemoError('monitor HTTP probe did not observe success')
        evidence = {
            'schema':'sse-raw-monitor-evidence-v1', 'monitor':monitor,
            'chainId': CHAIN_ID, 'settlement':settlement, 'leaseId':lease_id, 'epochId':0,
            'requestHash':request_hash, 'responseHash':epoch['responseHash'],
            'responseDeadline':epoch['responseDeadline'], 'monitoringClose':epoch['monitoringClose'],
            'chainResponseAuthenticated':True, 'observation':obs,
            'clockAttested':False, 'computeProvisioningVerified':False,
            'independentMonitorHost':False,
            'localDockerConfigurationInspected':compute_profile is not None,
            'localComputeObservation':compute_obs_monitor,
        }
        data = json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()
        evidence_hash = '0x' + keccak256(data).hex()
        evidence_path = record_path.parent / ('monitor_'+str(i+1)+'_evidence.json')
        save_json(evidence_path, evidence)
        summary['evidenceFiles'].append(str(evidence_path))
        summary['evidenceCommitments'][monitor] = evidence_hash
        vote_message = {'leaseId':lease_id,'epochId':0,'requestHash':request_hash,
                        'outcome':1,'responseHash':epoch['responseHash'],'evidenceHash':evidence_hash}
        sig = sign(rpc, monitor, eip712('MonitorVote', monitor, vote_message, CHAIN_ID, settlement))
        record('VOTE_'+str(i+1), tx(rpc, consumer, settlement,
            encode_last_bytes('submitMonitorVote(uint256,uint256,uint8,bytes32,bytes)',
                              (lease_id, 0, 1, evidence_hash), sig)))
    view = inspect_chain(rpc, settlement, lease_id, 0, endpoint=endpoint)
    if view['epoch']['successVotes'] != 3 or view['epoch']['failureVotes'] != 0:
        raise DemoError('quorum was not recorded on chain')
    summary['quorumReached'] = True
    record('QUORUM_REACHED')
    if do_fast_forward:
        fast_forward(rpc, epoch['monitoringClose'] + 1)
    elif latest_timestamp(rpc) <= epoch['monitoringClose']:
        raise DemoError('monitoring not closed; rerun with --fast-forward for local demonstration')
    record('MONITORING_SEALED', tx(rpc, consumer, settlement,
        encode_static('sealMonitoring(uint256,uint256)', lease_id, 0)))
    record('EPOCH_SETTLED', tx(rpc, consumer, settlement,
        encode_static('settleEpoch(uint256,uint256)', lease_id, 0)))
    if do_fast_forward:
        fast_forward(rpc, epoch['evidenceClose'] + 1)
    elif latest_timestamp(rpc) <= epoch['evidenceClose']:
        raise DemoError('evidence still open; rerun with --fast-forward')
    record('EVIDENCE_CLOSED', tx(rpc, consumer, settlement,
        encode_static('closeEpochEvidence(uint256,uint256)', lease_id, 0)))
    record('LEASE_CLOSED', tx(rpc, consumer, settlement,
        encode_static('closeLease(uint256)', lease_id)))
    record('BONDS_RELEASED', tx(rpc, consumer, settlement,
        encode_static('releaseCommitteeAfterEvidence(uint256)', lease_id)))
    final = inspect_chain(rpc, settlement, lease_id, 0, endpoint=endpoint)
    ep = final['epoch']
    if (ep['outcomeName'] != 'Success' or ep['providerCredited'] != fee or
        ep['consumerCredited'] != 0 or ep['unresolvedExposure'] != 0 or
        not ep['evidenceClosed'] or final['lease']['stateName'] != 'Closed'):
        raise DemoError('final accounting assertion failed')
    summary['finalEpoch'] = ep
    summary['finalLeaseState'] = final['lease']['stateName']
    summary['status'] = 'SUCCESS_COMPLETE'
    save_json(record_path, summary)
    print('  -> SUCCESS_COMPLETE; provider credited', ep['providerCredited'], 'wei', flush=True)
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rpc-url', default='http://127.0.0.1:8545')
    p.add_argument('--settlement', required=True)
    p.add_argument('--endpoint', default='http://127.0.0.1:8877')
    p.add_argument('--out-dir', default='.local/sse-e2e-runs')
    p.add_argument('--compute-profile', help='Canonical compute profile JSON tied to Docker container')
    p.add_argument('--docker-container', help='Existing nonprivileged local Docker worker container name')
    p.add_argument('--execute', action='store_true', help='Explicitly authorize local Anvil state changes')
    p.add_argument('--fast-forward', action='store_true', help='Use simulated chain time to close epochs instantly')
    args = p.parse_args()
    try:
        result = run(LocalRPC(args.rpc_url), args.settlement, args.endpoint,
                     Path(args.out_dir), args.execute, args.fast_forward,
                     args.compute_profile, args.docker_container)
        print(json.dumps({'status':result['status'], 'leaseId': result.get('leaseId'),
                          'quorumReached': result.get('quorumReached',False),
                          'finalEpoch':result.get('finalEpoch'),
                          'evidenceFiles':result['evidenceFiles'],
                          'localComputeWorkloadVerified':result.get('localComputeWorkloadVerified',False),
                          'committedResourceProfileHash':result.get('committedResourceProfileHash'),
                          'remoteCloudProvisioningVerified':False},indent=2))
        if not args.execute:
            print('Preflight only. Add --execute --fast-forward to complete the local scenario.')
        return 0
    except (DemoError, ComputeError, ChainReadError, OSError, ValueError, KeyError) as exc:
        print('SSE local demo STOPPED: '+str(exc),file=sys.stderr)
        print('Any transactions already mined are NOT rolled back. Inspect .local/sse-e2e-runs for progress.',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
