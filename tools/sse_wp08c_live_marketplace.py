"""WP-08C genuine local marketplace -> chain-bound signed HTTP evidence integration.

This is an isolated *development test*, not distributed cloud operation. It
starts a new Anvil process with a PUBLIC test mnemonic, deploys V1 contracts
from Foundry build artifacts, funds a marketplace lease, activates a selected
committee and epoch, and starts the signed HTTP provider and monitor CLI as
separate processes. It checks the persisted signed raw evidence against the
actual chain-derived committee, and verifies NO votes/payouts are authorized.

Run only after \`forge build\` with Anvil in PATH:
  python tools/sse_wp08c_live_marketplace.py
Do not use these deterministic test keys with real assets or public RPCs.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))
from sse_challenge import keccak256
from sse_chain_read import LocalRPC, inspect_chain
from sse_wp08c_chain_binding import bind_capture_to_chain
from sse_evidence_wire_v1 import EvidenceScope, verify_observation, to_wp07_raw, ObservationKind
from sse_http_signed_delivery_v1 import EvidenceArchive
from typed_evidence import Domain

# Anvil's widely published test mnemonic; never use this wallet on a real chain.
MNEMONIC = 'test test test test test test test test test test test junk'
CHAIN_ID = 31337
CONTRACTS = ('OpenMonitorCommittee', 'SSESettlement', 'OpenResourceBoard')
SCOPED_ERRORS = (ValueError, RuntimeError, OSError, KeyError, AssertionError)


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _word(value: int | str) -> bytes:
    if type(value) is int and 0 <= value < (1 << 256):
        return value.to_bytes(32, 'big')
    if type(value) is str and value.startswith('0x'):
        raw = bytes.fromhex(value[2:])
        if len(raw) in (20, 32):
            return raw.rjust(32, b'\x00')
    raise ValueError('invalid static ABI value')


def _calldata(signature: str, *args: int | str) -> str:
    return '0x' + (keccak256(signature.encode('ascii'))[:4] +
                   b''.join(_word(a) for a in args)).hex()


def _send(rpc: LocalRPC, sender: str, to: str | None, data: str,
          value: int = 0) -> dict:
    call = {'from': sender, 'data': data, 'gas': hex(9_000_000)}
    if to is not None:
        call['to'] = to
    if value:
        call['value'] = hex(value)
    h = rpc.request('eth_sendTransaction', [call])
    if type(h) is not str or len(h) != 66:
        raise AssertionError('Anvil did not return a transaction hash')
    for _ in range(100):
        receipt = rpc.request('eth_getTransactionReceipt', [h])
        if receipt is not None:
            if receipt.get('status') != '0x1':
                raise AssertionError(f'local transaction reverted: {h}')
            return receipt
        time.sleep(0.1)
    raise AssertionError(f'local transaction not mined: {h}')


def _deploy(rpc: LocalRPC, sender: str, contract: str,
            *constructor_args: int | str) -> str:
    path = ROOT / 'out' / f'{contract}.sol' / f'{contract}.json'
    artifact = json.loads(path.read_text(encoding='utf-8'))
    bytecode = artifact['bytecode']['object']
    if type(bytecode) is not str or not bytecode.startswith('0x') or len(bytecode) < 100:
        raise AssertionError(f'invalid Foundry bytecode: {contract}')
    receipt = _send(rpc, sender, None,
                    bytecode + b''.join(_word(a) for a in constructor_args).hex())
    address = receipt.get('contractAddress')
    if type(address) is not str or len(address) != 42:
        raise AssertionError(f'missing deployed contract: {contract}')
    return address.lower()


def _wait_chain(rpc: LocalRPC, anvil: subprocess.Popen) -> list[str]:
    for _ in range(100):
        if anvil.poll() is not None:
            raise RuntimeError(f'Anvil exited early ({anvil.returncode})')
        try:
            if int(rpc.request('eth_chainId', []), 16) != CHAIN_ID:
                raise AssertionError('unexpected chain ID')
            accounts = rpc.request('eth_accounts', [])
            if type(accounts) is list and len(accounts) >= 10:
                return [a.lower() for a in accounts]
        except (ValueError, OSError):
            time.sleep(0.1)
    raise RuntimeError('fresh Anvil failed to start')


def _await_provider(endpoint: str, provider_proc: subprocess.Popen) -> None:
    from urllib.request import urlopen
    for _ in range(80):
        if provider_proc.poll() is not None:
            raise AssertionError('signed provider process exited early')
        try:
            with urlopen(endpoint + '/healthz', timeout=0.5) as response:
                health = json.loads(response.read(2048))
            if response.status == 200 and health.get('experimental') is True:
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError('signed provider did not become available on localhost')


def _terminate(proc: subprocess.Popen | None) -> None:
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _run_cli(args: list[str], env: dict, *, should_succeed: bool) -> str:
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                            text=True, timeout=30, check=False)
    if should_succeed and result.returncode != 0:
        raise AssertionError('capture failed:\n' + result.stderr[-3500:])
    if not should_succeed and result.returncode == 0:
        raise AssertionError('invalid chain-bound capture unexpectedly succeeded')
    return result.stdout


def run(output_dir: Path) -> dict:
    from eth_account import Account
    Account.enable_unaudited_hdwallet_features()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('refusing to replace existing evidence directory')
    output_dir.mkdir(parents=True, exist_ok=True)
    # No system-wide Anvil state, long-lived funded keys, or external RPC calls.
    port = _port()
    rpc = LocalRPC(f'http://127.0.0.1:{port}')
    anvil = None
    provider_proc = None
    tx_hashes: list[str] = []
    try:
        anvil = subprocess.Popen(
            ['anvil', '--silent', '--host', '127.0.0.1', '--port', str(port),
             '--chain-id', str(CHAIN_ID), '--accounts', '10', '--mnemonic', MNEMONIC],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        accounts = _wait_chain(rpc, anvil)
        key_for = {}
        for i, address in enumerate(accounts):
            account = Account.from_mnemonic(
                MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}")
            if account.address.lower() != address:
                raise AssertionError('Anvil account and test mnemonic disagree')
            key_for[address] = bytes(account.key).hex()
        consumer, provider = accounts[:2]
        candidates = accounts[2:7]
        outsider = accounts[7]
        min_bond = 10**9

        pool = _deploy(rpc, consumer, 'OpenMonitorCommittee', consumer,
                       min_bond, 86400, 3600)
        settlement = _deploy(rpc, consumer, 'SSESettlement', pool)
        board = _deploy(rpc, consumer, 'OpenResourceBoard')
        for contract, data in (
            (pool, _calldata('bindSettlement(address)', settlement)),
            (settlement, _calldata('bindResourceBoard(address)', board)),
            (board, _calldata('bindSettlement(address)', settlement)),
        ):
            receipt = _send(rpc, consumer, contract, data)
            tx_hashes.append(receipt['transactionHash'])
        for candidate in candidates:
            receipt = _send(rpc, candidate, pool, _calldata('register()'), min_bond)
            tx_hashes.append(receipt['transactionHash'])

        # Select a loopback port before it is committed to the lease.
        endpoint = f'http://127.0.0.1:{_port()}'
        endpoint_hash = '0x' + keccak256(endpoint.encode('utf-8')).hex()
        profile_hash = '0x' + keccak256(b'wp08c-local-http-profile').hex()
        policy_hash = '0x' + keccak256(b'wp08c-raw-HTTP-policy-lab-only').hex()
        request_hash = '0x' + keccak256(b'wp08c-fresh-real-anvil-epoch').hex()
        block = rpc.request('eth_getBlockByNumber', ['latest', False])
        bidding_close = int(block['timestamp'], 16) + 60
        receipt = _send(rpc, consumer, board,
                        _calldata('requestResource(bytes32,bytes32,uint256,uint64)',
                                  profile_hash, policy_hash, 40, bidding_close))
        tx_hashes.append(receipt['transactionHash'])
        receipt = _send(rpc, provider, board,
                        _calldata('placeBid(uint256,uint256)', 1, 25))
        tx_hashes.append(receipt['transactionHash'])
        timestamp = int(rpc.request('eth_getBlockByNumber',
                                    ['latest', False])['timestamp'], 16)
        rpc.request('evm_increaseTime', [max(0, bidding_close - timestamp + 1)])
        rpc.request('evm_mine', [])

        # The last parameter is a static tuple, so its seven fields are
        # encoded consecutively in the ABI head (no dynamic offset).
        receipt = _send(
            rpc, consumer, board,
            _calldata('chooseBidAndFundLease(uint256,uint256,address,(bytes32,uint256,uint256,uint256,uint64,uint64,uint64))',
                      1, 0, settlement, endpoint_hash, 5, 25, 1, 600, 300, 300),
            value=25)
        tx_hashes.append(receipt['transactionHash'])
        before = inspect_chain(rpc, settlement, 1, 0, endpoint=endpoint)
        lease = before['lease']
        if (before['status'] != 'NO_EPOCH_ADMITTED' or
                lease['marketplaceRequestId'] != 1 or
                lease['slaPolicyHash'] != policy_hash or
                lease['totalEscrow'] != 25 or
                lease['provider'] != provider):
            raise AssertionError('marketplace funding or policy binding failed')

        tx_hashes.append(_send(rpc, provider, settlement,
                               _calldata('acceptLease(uint256)', 1))['transactionHash'])
        tx_hashes.append(_send(
            rpc, consumer, pool, _calldata('fulfillRandomness(uint256,uint256)',
                                          lease['assignmentId'], 0xC0FFEE))['transactionHash'])
        tx_hashes.append(_send(rpc, consumer, settlement,
                               _calldata('finalizeMonitorCommittee(uint256)', 1))['transactionHash'])
        assigned = inspect_chain(rpc, settlement, 1, 0, endpoint=endpoint)['lease']['monitors']
        if len(set(assigned)) != 4 or not set(assigned).issubset(set(candidates)):
            raise AssertionError('unexpected committee selection')
        for monitor in assigned:
            tx_hashes.append(_send(rpc, monitor, settlement,
                                   _calldata('confirmMonitorAssignment(uint256)', 1))['transactionHash'])
        tx_hashes.append(_send(rpc, consumer, settlement,
                               _calldata('admitEpoch(uint256,bytes32)', 1, request_hash))['transactionHash'])

        scope = EvidenceScope(CHAIN_ID, settlement, 1, 0, policy_hash,
                              profile_hash, request_hash)
        bound = bind_capture_to_chain(rpc, scope, endpoint, provider)
        if bound.context.authorized_monitors != frozenset(assigned):
            raise AssertionError('chain-selected monitors were not derived correctly')

        provider_port = int(endpoint.rsplit(':', 1)[1])
        provider_env = {**os.environ, 'SSE_WP08B_PROVIDER_KEY': '0x' + key_for[provider]}
        provider_proc = subprocess.Popen(
            [sys.executable, str(ROOT / 'services/provider-agent/signed_http_service.py'),
             '--port', str(provider_port), '--chain-id', str(CHAIN_ID),
             '--settlement', settlement, '--lease-id', '1', '--epoch-id', '0',
             '--request-hash', request_hash],
            cwd=ROOT, env=provider_env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _await_provider(endpoint, provider_proc)

        archive_path = output_dir / 'evidence.sqlite'
        capture_cli = [
            sys.executable, str(ROOT / 'services/monitor-agent/evidence_capture.py'),
            '--endpoint', endpoint, '--chain-id', str(CHAIN_ID),
            '--settlement', settlement, '--lease-id', '1', '--epoch-id', '0',
            '--sla-policy-hash', policy_hash, '--resource-profile-hash', profile_hash,
            '--request-hash', request_hash, '--provider', provider,
            '--archive', str(archive_path), '--rpc-url', rpc.url,
        ]
        first_monitor = assigned[0]
        good_env = {**os.environ, 'SSE_WP08B_MONITOR_KEY': '0x' + key_for[first_monitor]}
        output = _run_cli(capture_cli, good_env, should_succeed=True)
        if 'Chain-bound context read' not in output:
            raise AssertionError('capture was not executed in the chain-bound mode')
        archive = EvidenceArchive(archive_path)
        if archive.count() != 1:
            raise AssertionError('expected exactly one stored raw observation')
        from contextlib import closing
        with closing(archive._db()) as db:
            evidence_id = db.execute('SELECT evidence_id FROM records').fetchone()[0]
        envelope, raw_bytes = archive.load(
            evidence_id, bound.context, Domain(CHAIN_ID, settlement), provider)
        verified = verify_observation(envelope, bound.context)
        if (verified.signer != first_monitor or
                verified.record.kind != ObservationKind.RESPONSE_SEEN or
                to_wp07_raw(verified).signer != first_monitor or
                not raw_bytes):
            raise AssertionError('stored HTTP response/monitor signatures or raw mapping mismatch')

        bad_env = {**os.environ, 'SSE_WP08B_MONITOR_KEY': '0x' + key_for[outsider]}
        _run_cli(capture_cli, bad_env, should_succeed=False)
        if archive.count() != 1:
            raise AssertionError('unauthorized monitor modified the archive')
        epoch = inspect_chain(rpc, settlement, 1, 0, endpoint=endpoint)['epoch']
        if (epoch['successVotes'] != 0 or epoch['failureVotes'] != 0 or
                epoch['providerCredited'] != 0 or epoch['consumerCredited'] != 0 or
                epoch['unresolvedExposure'] != 25 or epoch['monitoringSealed']):
            raise AssertionError('raw capture unexpectedly authorized a vote or payout')

        summary = {
            'schema': 'sse-wp08c-live-marketplace-v1', 'status': 'PASS',
            'localAnvilOnly': True, 'chainId': CHAIN_ID,
            'usesMarketplaceFundedLease': True, 'marketplaceRequestId': 1,
            'leaseId': 1, 'epochId': 0, 'settlement': settlement,
            'board': board, 'committeePool': pool,
            'selectedMonitors': assigned, 'captureMonitor': first_monitor,
            'provider': provider, 'evidenceId': evidence_id,
            'providerAndMonitorSignaturesVerified': True,
            'authorizationReadFromChainSnapshot': True,
            'independentOperatingSystems': False, 'separateLocalProcesses': True,
            'proofOfFinality': False, 'consumerDeliveryProven': False,
            'qualifiedFactConstructed': False, 'onChainMonitorVotes': 0,
            'servicePayoutsAuthorized': False,
            'localTransactionHashes': tx_hashes,
        }
        (output_dir / 'run.json').write_text(
            json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
        return summary
    finally:
        _terminate(provider_proc)
        _terminate(anvil)


def main() -> int:
    try:
        run(ROOT / '.local' / 'wp08c-live')
        return 0
    except SCOPED_ERRORS as exc:
        print(f'WP08C live integration STOPPED: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
