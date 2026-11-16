"""Local node inventory and deployment planning API."""

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from propose_node import build_proposal
from validate_inventory import validate
from plan_deploy import plan
from settlement_scenarios import report as settlement_report
from sse_chain_observer import Observer, ObserverError, read_config
from sse_chain_read import ChainReadError, inspect_chain
from sse_settlement_explain import SettlementExplainError, explain_inspection

app = FastAPI(title='SSE Control Plane', docs_url=None, redoc_url=None)
STATIC = Path(__file__).parent / 'static'


class Enrollment(BaseModel):
    node_id: str
    private_ip: str
    roles: list[str] = Field(min_length=1)
    ethereum_client: str = 'none'
    ssh_user: str = 'ubuntu'
    environment: Literal['staging', 'production'] = 'staging'


class PlanRequest(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=100)


def _authorize(header: str | None, write: bool = False) -> str:
    """Authenticate an administrator or read-only request."""
    admin = os.environ.get('SSE_CONTROL_TOKEN', '')
    read = os.environ.get('SSE_READ_TOKEN', '')
    if not admin or len(admin) < 16:
        raise HTTPException(503, 'control plane disabled: set a strong SSE_CONTROL_TOKEN')
    if not header or not header.startswith('Bearer '):
        raise HTTPException(401, 'authentication required')
    supplied = header[7:]
    if secrets.compare_digest(supplied, admin):
        return 'administrator'
    if not write and read and len(read) >= 16 and secrets.compare_digest(supplied, read):
        return 'observer'
    raise HTTPException(401, 'authentication required')


def _proposals_dir() -> Path:
    root = Path(os.environ.get('SSE_PROPOSALS_DIR', str(ROOT/'infra/inventory/proposals')))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def _inventory_path() -> Path:
    return Path(os.environ.get('SSE_INVENTORY_PATH', str(ROOT/'infra/inventory/nodes.json')))


def _audit(event: str, node_id: str, role: str):
    record = {'time': datetime.now(timezone.utc).isoformat(),
              'event': event, 'node_id': node_id, 'actor_role': role,
              'effect': 'proposal-only'}
    path = _proposals_dir() / 'audit.jsonl'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, separators=(',', ':')) + '\n')


def _proposal_file(node_id: str) -> Path:
    from validate_inventory import NAME
    if not NAME.fullmatch(node_id):
        raise HTTPException(422, 'invalid node ID')
    return _proposals_dir() / (node_id + '.json')


@app.get('/')
def index():
    return FileResponse(STATIC/'index.html', headers={'Cache-Control': 'no-store'})


@app.get('/dashboard.js')
def dashboard_js():
    return FileResponse(STATIC/'dashboard.js', media_type='application/javascript', headers={'Cache-Control': 'no-store'})


@app.get('/healthz')
def healthz():
    return {'service': 'sse-control-plane',
            'status': 'local', 'remote_execution': False,
            'blockchain_deployed': False, 'validator_activation': False}


@app.get('/v1/nodes')
def nodes(authorization: str | None = Header(None)):
    _authorize(authorization)
    try:
        path = _inventory_path()
        payload = json.loads(path.read_text()) if path.exists() else {'environment': 'staging', 'nodes': []}
        validate(payload)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, 'inventory unavailable or invalid') from exc
    return payload


@app.get('/v1/proposals')
def list_proposals(authorization: str | None = Header(None)):
    _authorize(authorization)
    result = []
    for file in sorted(_proposals_dir().glob('*.json')):
        if file.is_symlink():
            continue
        try:
            proposal = json.loads(file.read_text())
            validate(proposal)
            result.extend(proposal['nodes'])
        except (ValueError, OSError, KeyError, TypeError):
            continue
    return {'proposals': result, 'remote_execution': False}


@app.post('/v1/enrollment-proposals', status_code=202)
def propose(data: Enrollment, authorization: str | None = Header(None)):
    role = _authorize(authorization, write=True)
    try:
        proposal = build_proposal(data.node_id, data.private_ip, data.roles,
                                  data.ethereum_client, data.ssh_user, data.environment)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    target = _proposal_file(data.node_id)
    if any(n['node_id'] == data.node_id or n['address'] == data.private_ip
           for n in list_proposals(authorization)['proposals']):
        raise HTTPException(409, 'node ID or address already proposed')
    try:
        existing = json.loads(_inventory_path().read_text())
        validate(existing)
        if any(n['node_id'] == data.node_id or n['address'] == data.private_ip
               for n in existing['nodes']):
            raise HTTPException(409, 'node ID or address already in inventory')
    except FileNotFoundError:
        pass
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise HTTPException(409, 'proposal already exists') from None
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(proposal, out, indent=2)
        out.write('\n')
    _audit('proposed', data.node_id, role)
    return {'node_id': data.node_id, 'status': 'pending',
            'connected': False, 'role_activated': False}


@app.post('/v1/proposals/{node_id}/approve')
def approve(node_id: str, authorization: str | None = Header(None)):
    role = _authorize(authorization, write=True)
    target = _proposal_file(node_id)
    if target.is_symlink():
        raise HTTPException(409, 'unsafe proposal location')
    try:
        proposal = json.loads(target.read_text())
        validate(proposal)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(404, 'valid proposal not found') from exc
    node = proposal['nodes'][0]
    if node['node_id'] != node_id or node['status'] != 'pending':
        raise HTTPException(409, 'proposal is not pending')
    node['status'] = 'approved'
    temp = _proposals_dir() / (node_id + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(proposal, out, indent=2)
        out.write('\n')
    os.replace(temp, target)
    _audit('approved-for-manual-review', node_id, role)
    return {'node_id': node_id, 'status': 'approved', 'connected': False,
            'role_activated': False, 'needs_machine_identity_check': True}


@app.post('/v1/deployment-plans')
def deployment_plan(data: PlanRequest, authorization: str | None = Header(None)):
    _authorize(authorization, write=True)
    for path in data.paths:
        if not path or path.startswith('/') or '..' in Path(path).parts or '\\' in path:
            raise HTTPException(422, 'paths must be repository-relative')
    result = plan(data.paths)
    return {**result, 'executed': False, 'chain_deployment': False}


@app.get('/v1/audit')
def audit(authorization: str | None = Header(None)):
    _authorize(authorization)
    path = _proposals_dir()/'audit.jsonl'
    if not path.exists():
        return {'events': []}
    return {'events': [json.loads(line) for line in path.read_text().splitlines()[-100:]]}


@app.get('/v1/settlement-scenarios')
def settlement_scenarios(authorization: str | None = Header(None)):
    _authorize(authorization)
    return settlement_report()


# R8 observer: independently hosted, authenticated, read-only EVM RPC surface.
# These endpoints cannot submit transactions or send commands to SSE nodes.
def _chain_observer():
    try:
        return Observer(read_config())
    except ObserverError:
        raise HTTPException(status_code=503, detail="chain observer not configured") from None


def _observed(call):
    try:
        return call()
    except ObserverError:
        raise HTTPException(status_code=502, detail="chain observer RPC unavailable or inconsistent") from None


@app.get("/v1/chain/overview")
def chain_overview(authorization: str | None = Header(None)):
    _authorize(authorization)
    observer = _chain_observer()
    return _observed(observer.overview)


@app.get("/v1/chain/blocks")
def chain_blocks(limit: int = Query(default=10, ge=1, le=20),
                 authorization: str | None = Header(None)):
    _authorize(authorization)
    observer = _chain_observer()
    return _observed(lambda: observer.blocks(limit))


@app.get("/v1/chain/transactions/{tx_hash}")
def chain_transaction(tx_hash: str,
                      authorization: str | None = Header(None)):
    _authorize(authorization)
    observer = _chain_observer()
    return _observed(lambda: observer.transaction(tx_hash))


@app.get("/v1/chain/events")
def chain_events(start_block: int = Query(ge=0),
                 end_block: int = Query(ge=0),
                 authorization: str | None = Header(None)):
    _authorize(authorization)
    observer = _chain_observer()
    return _observed(lambda: observer.events(start_block, end_block))


@app.get("/v1/chain/leases/{lease_id}/epochs/{epoch_id}")
def inspect_sse_lease_epoch(lease_id: int, epoch_id: int,
                            authorization: str | None = Header(None)):
    """Read chain-pinned lease/epoch and derive conditional SSE payout bounds.

    The configured settlement MUST be explicitly allowlisted. Never use a
    user-supplied contract address, user-controlled RPC, or an unpinned view.
    """
    _authorize(authorization)
    if lease_id < 1 or epoch_id < 0:
        raise HTTPException(status_code=422, detail="invalid lease or epoch index")
    observer = _chain_observer()
    settlement = os.environ.get("SSE_OBSERVER_SETTLEMENT_ADDRESS", "").lower()
    if settlement not in observer.config["contracts"]:
        raise HTTPException(status_code=503, detail="settlement inspector not configured")
    class ReadOnlyChainAdapter:
        def request(self, method, params):
            return observer.rpc(method, params)
    try:
        snapshot = inspect_chain(
            ReadOnlyChainAdapter(), settlement, lease_id, epoch_id,
            expected_chain_id=observer.config["chain_id"],
            pin_block_hash=True,
        )
        explanation = explain_inspection(snapshot)
    except (ChainReadError, SettlementExplainError, ObserverError, OSError, ValueError):
        raise HTTPException(status_code=502,
                            detail="SSE lease inspection unavailable or inconsistent") from None
    return {"inspection": snapshot, "explanation": explanation,
            "readOnly": True, "participantActionsAvailable": False}
