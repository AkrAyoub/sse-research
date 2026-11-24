"""Check local Docker CPU-worker runtime and independently reproduce its job.

Read-only Docker inspect and localhost HTTP probe. This is LOCAL configuration
observation, NOT remote cloud or trusted-execution attestation.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from compute_workload import compute_result

_CONTAINER = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z')
_IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')


class ComputeError(ValueError):
    pass


def local_endpoint(endpoint: str) -> int:
    u = urlsplit(endpoint)
    try:
        port = u.port
    except ValueError as exc:
        raise ComputeError('invalid endpoint port') from exc
    if (u.scheme != 'http' or u.hostname != '127.0.0.1' or
            not isinstance(port, int) or port <= 0 or port > 65535 or
            u.username is not None or u.password is not None or
            u.path not in ('','/') or u.query or u.fragment or not endpoint.endswith(str(port))):
        raise ComputeError('compute endpoint must be http://127.0.0.1:PORT')
    return port


def require_local_owner_rootless_socket(socket_path: str) -> str:
    """Require exact owner-private rootless UNIX socket; never use remote Docker.

    This opt-in explicitly excludes the existing rootful PoS Docker daemon.
    """
    uid = os.geteuid()
    expected = f"/run/user/{uid}/docker.sock"
    if (uid == 0 or type(socket_path) is not str
            or socket_path != expected):
        raise ComputeError('expected exact nonroot owner Docker socket')
    path = Path(socket_path)
    runtime_dir = path.parent
    if runtime_dir.is_symlink() or not runtime_dir.is_dir():
        raise ComputeError('missing private owner rootless runtime directory')
    d = runtime_dir.stat()
    if d.st_uid != uid or stat.S_IMODE(d.st_mode) != 0o700:
        raise ComputeError('rootless runtime directory not private and owner-controlled')
    if path.is_symlink() or not path.exists():
        raise ComputeError('rootless Docker UNIX socket missing or linked')
    s = path.stat()
    if (not stat.S_ISSOCK(s.st_mode) or s.st_uid != uid
            or not os.access(path, os.R_OK | os.W_OK)):
        raise ComputeError('rootless Docker socket not locally accessible by owner')
    return 'unix://' + socket_path


def inspect_container(profile: dict, endpoint: str, container_name: str,
                      strict_hardening: bool = False, *,
                      docker_socket: str | None = None) -> dict:
    """Read local Docker config; verify exact image/CPU/memory/port.

    strict_hardening=True is mandatory for the new signed marketplace
    provider runtime and adds a deny-by-default isolation configuration.
    Historical WP07 tests continue to use the earlier inspection policy.
    """
    if not isinstance(container_name, str) or not _CONTAINER.fullmatch(container_name):
        raise ComputeError('invalid container name')
    port = local_endpoint(endpoint)
    if profile.get('endpoint') != endpoint:
        raise ComputeError('profile endpoint differs from requested endpoint')
    if not isinstance(profile.get('imageId'), str) or not _IMAGE.fullmatch(profile['imageId']):
        raise ComputeError('profile requires an immutable image ID')
    command = ['docker']
    if docker_socket is not None:
        # An explicitly selected private nonroot daemon. Never inherit
        # Docker's default context or rootful PoS host socket in this mode.
        command += ['--host', require_local_owner_rootless_socket(docker_socket)]
    command += ['container', 'inspect', container_name]
    env = None
    if docker_socket is not None:
        # Docker context/host environment must not override the explicit
        # private Unix socket when other Docker CLIs share this shell.
        env = dict(os.environ)
        env.pop('DOCKER_CONTEXT', None)
        env.pop('DOCKER_HOST', None)
    try:
        p = subprocess.run(command,
                           capture_output=True, text=True, check=False,
                           timeout=8, shell=False, env=env)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise ComputeError('Docker CLI unavailable or timed out; start Docker Desktop') from exc
    if p.returncode != 0:
        raise ComputeError('Docker container not found/running; check docker ps')
    try:
        items = json.loads(p.stdout)
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise ValueError('unexpected JSON')
        d = items[0]
        state, host = d['State'], d['HostConfig']
        if state['Running'] is not True or state.get('Paused') is True or state.get('Restarting') is True:
            raise ComputeError('Docker worker is not in running state')
        if d['Image'].lower() != profile['imageId']:
            raise ComputeError('container image ID does not match committed profile')
        cpu = profile['cpuMilli'] * 1_000_000
        if type(host.get('NanoCpus')) is not int or host['NanoCpus'] != cpu:
            raise ComputeError('Docker NanoCpus does not match committed CPU limit')
        if type(host.get('Memory')) is not int or host['Memory'] != profile['memoryBytes']:
            raise ComputeError('Docker memory cap does not match committed memory limit')
        if host.get('ReadonlyRootfs') is not True:
            raise ComputeError('Docker container must have read-only root filesystem')
        bindings = host.get('PortBindings', {}).get('8877/tcp')
        if (not isinstance(bindings, list) or len(bindings) != 1 or
                bindings[0].get('HostIp') != '127.0.0.1' or bindings[0].get('HostPort') != str(port)):
            raise ComputeError('Docker worker must publish 8877/tcp only on expected localhost port')
        if host.get('NetworkMode') == 'host':
            raise ComputeError('host networking forbidden')
        if host.get('Privileged') is True:
            raise ComputeError('privileged Docker workers forbidden')
        if d.get('Config', {}).get('User') not in ('10001:10001', '10001'):
            raise ComputeError('worker must run as non-root UID 10001')
        if strict_hardening:
            # A local Docker configuration inspection is not a hardware or
            # anti-tamper attestation. It only checks the committed limits.
            if host.get('NetworkMode') != 'bridge':
                raise ComputeError('marketplace worker must use isolated bridge network')
            if host.get('MemorySwap') != profile['memoryBytes']:
                raise ComputeError('worker swap must not exceed agreed memory cap')
            if type(host.get('PidsLimit')) is not int or not 1 <= host['PidsLimit'] <= 64:
                raise ComputeError('worker requires bounded pids limit')
            caps = host.get('CapDrop')
            if type(caps) is not list or [x.lower() for x in caps] != ['all']:
                raise ComputeError('worker requires all Linux capabilities dropped')
            opts = host.get('SecurityOpt')
            if (type(opts) is not list or
                    not any(x in ('no-new-privileges', 'no-new-privileges:true')
                            for x in opts)):
                raise ComputeError('worker must prevent privilege escalation')
            if 'seccomp=builtin' not in opts:
                raise ComputeError('worker requires built-in seccomp syscall filter')
            if any(x in ('seccomp=unconfined', 'apparmor=unconfined',
                         'systempaths=unconfined', 'label=disable') for x in opts):
                raise ComputeError('worker may not disable confinement')
            if (host.get('CapAdd') or host.get('Devices') or
                    host.get('Binds') or host.get('Mounts') or d.get('Mounts')):
                raise ComputeError('worker cannot add capabilities, devices or mounts')
            if any(host.get(k) == 'host' for k in
                   ('NetworkMode','PidMode','IpcMode','UTSMode','UsernsMode','CgroupnsMode')):
                raise ComputeError('worker cannot share host namespaces')
            if set(host.get('PortBindings', {})) != {'8877/tcp'}:
                raise ComputeError('worker cannot expose extra service ports')
            if host.get('AutoRemove') is not True:
                raise ComputeError('worker must clean up after stop')
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, ComputeError):
            raise
        raise ComputeError('malformed Docker inspection record') from exc
    return {'imageId': d['Image'].lower(), 'cpuMilli': profile['cpuMilli'],
            'memoryBytes': profile['memoryBytes'], 'hostPort': port,
            'containerId': d['Id'], 'runtimeReportedRunning': True,
            'localDockerConfigurationInspected': True, 'trustedHardwareAttestation': False,
            'dockerDaemonSelection': ('EXACT_OWNER_ROOTLESS_UNIX_SOCKET'
                                      if docker_socket is not None
                                      else 'LEGACY_DEFAULT_CONTEXT_NOT_ROOTLESS_ATTESTED')}


def run_compute_probe(endpoint: str, lease_id: int, epoch_id: int, request_hash: str) -> dict:
    local_endpoint(endpoint)
    expected = compute_result(lease_id, epoch_id, request_hash)
    req = Request(endpoint.rstrip('/') + '/v1/compute',
                  data=json.dumps({'leaseId': lease_id, 'epochId': epoch_id,
                                   'requestHash': request_hash}).encode('utf-8'),
                  headers={'Content-Type':'application/json'}, method='POST')
    start = time.perf_counter()
    try:
        with urlopen(req, timeout=8) as response:
            if response.status != 200:
                raise ComputeError('compute worker returned unexpected HTTP status')
            data = response.read(4097)
        if len(data) > 4096:
            raise ComputeError('compute response too large')
        parsed = json.loads(data)
    except (OSError, TimeoutError, UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, ComputeError):
            raise
        raise ComputeError('compute worker unavailable or malformed response') from exc
    if parsed != expected:
        raise ComputeError('nonce-bound compute result did not match independently calculated digest')
    return {'schema':'sse-local-compute-observation-v1',
            'leaseId': lease_id, 'epochId': epoch_id, 'requestHash':request_hash.lower(),
            'resultDigest': expected['resultDigest'], 'rounds':expected['rounds'],
            'elapsedSecondsLocal':round(time.perf_counter()-start, 6),
            'workloadResultVerified': True, 'trustedHardwareAttestation':False,
            'independentMonitorHost':False}
