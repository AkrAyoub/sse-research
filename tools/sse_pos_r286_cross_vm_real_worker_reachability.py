#!/usr/bin/env python3
"""R286: real VM4711–4714 one-shot nonmutating worker/SSH reachability gates.

ACTUAL TCP probes are explicit --probe. Provider 4714 also re-inspects
already-built one exact Docker worker and executes ONE real local SHA256 job.
Nothing here opens an external listener, sends chain TX, reads wallet keys,
configures SSH/firewall, modifies Docker, or declares a paid SLA.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import secrets
import socket
import sys
import time

from sse_compute_docker import inspect_container, run_compute_probe

HOSTS={
    "ayoubakrvm4711":"VM4711_MONITOR",
    "ayoubakrvm4712":"VM4712_MONITOR",
    "ayoubakrvm4713":"VM4713_MONITOR",
    "ayoubakrvm4714":"VM4714_PROVIDER",
}
PROVIDER_IPV4="10.50.56.22"
WORKER_ENDPOINT="http://127.0.0.1:8877"
WORKER_NAME="sse-compute-vm4714"
WORKER_ID="59b9086543110acd2ef44da7fddeb100ab0341204de3dac595093803985f535b"
IMAGE_ID="sha256:848cde736008713d2f72e8de20cc669326abc678e41f644d3d63480ce77bd20d"


class Refused(ValueError):
    pass


def identify(*,geteuid=os.geteuid,getname=None):
    uid=geteuid()
    if getname is None:
        getname=lambda n:pwd.getpwuid(n).pw_name
    if uid==0:
        raise Refused("nonroot owner account required")
    user=getname(uid)
    if user not in HOSTS:
        raise Refused("only four previously owner-inventoried VMs accepted")
    return user


def tcp_probe(ip:str,port:int,*,connect=socket.create_connection):
    """One real TCP connect; may return refused, timeout, or blocked."""
    if ip!=PROVIDER_IPV4 or port not in (22,8877):
        raise Refused("probe address/port not in fixed approved private allowlist")
    start=time.monotonic_ns()
    try:
        connection=connect((ip,port),timeout=2.0)
        with connection:
            status="TCP_HANDSHAKE_SUCCEEDED"
    except ConnectionRefusedError:
        status="TCP_REFUSED"
    except TimeoutError:
        status="TCP_TIMEOUT"
    except OSError:
        status="TCP_ERROR_OR_FILTERED"
    elapsed=max(0,(time.monotonic_ns()-start)//1_000_000)
    return {"destinationPrivateIpv4":ip,"destinationPort":port,
            "tcpStatus":status,"elapsedMs":elapsed}


def observe(*,user=None,probe=False,connect=socket.create_connection,
            docker_inspect=inspect_container,compute_probe=run_compute_probe,
            random_bytes=secrets.token_hex):
    if user is None:
        user=identify()
    if user not in HOSTS:
        raise Refused("unrecognized previous real VM account")
    result={
        "schema":"SSE_R286_ACTUAL_VM4711_4714_PRIVATE_CROSS_VM_CPU_REACHABILITY_V1",
        "observedHostRole":HOSTS[user],
        "observedOwnerAccount":user,
        "fixedProviderPrivateIpv4":PROVIDER_IPV4,
        "expectedWorkerHostOnlyLoopback":WORKER_ENDPOINT,
        "probeRequested":probe,
        "realExternalPortReachabilityChecked":False,
        "actualWorkerDockerConfigReaudited":False,
        "actualLocalCpuChallengeIndependentlyVerified":False,
        "remoteLeaseOrSlaVerified":False,
        "nativeChainTransactionSent":False,
        "walletOrValidatorSecretsRead":False,
        "dockerChanged":False,
        "networkListenerStarted":False,
    }
    if not probe:
        return result
    result["actualNetworkProbes"]=[
        tcp_probe(PROVIDER_IPV4,port,connect=connect) for port in (22,8877)
    ]
    result["privateProviderHostTcpChecked"]=True
    result["unexpectedRawWorkerPrivateNetworkExposureObserved"]=(
        result["actualNetworkProbes"][1]["tcpStatus"]=="TCP_HANDSHAKE_SUCCEEDED"
    )
    # The data-plane is only local VM4714 localhost. Other VMs MUST
    # wait for authenticated TLS or explicitly owner-approved SSH forwarding.
    if user=="ayoubakrvm4714":
        profile={
            "endpoint":WORKER_ENDPOINT,"imageId":IMAGE_ID,
            "cpuMilli":500,"memoryBytes":256*2**20
        }
        inspect=docker_inspect(
            profile,WORKER_ENDPOINT,WORKER_NAME,
            strict_hardening=True,dedicated_vm4714_sudo_docker=True
        )
        if (inspect.get("containerId")!=WORKER_ID or
            inspect.get("imageId")!=IMAGE_ID or
            inspect.get("runtimeReportedRunning") is not True or
            inspect.get("localDockerConfigurationInspected") is not True):
            raise Refused("real worker ID, image digest or strict runtime changed")
        result["actualWorkerDockerConfigReaudited"]=True
        challenge="0x"+random_bytes(32)
        if (len(challenge)!=66 or
            any(x not in "0123456789abcdef" for x in challenge[2:])):
            raise Refused("real random challenge malformed")
        observed=compute_probe(WORKER_ENDPOINT,1,0,challenge)
        if (observed.get("workloadResultVerified") is not True or
            observed.get("rounds")!=8192 or
            observed.get("requestHash")!=challenge):
            raise Refused("real independent CPU recomputation missing")
        result["actualLocalCpuChallengeIndependentlyVerified"]=True
        result["localProbe"]={
            "requestHash":challenge,
            "resultDigest":observed["resultDigest"],
            "rounds":observed["rounds"],
            "elapsedSecondsLocal":observed["elapsedSecondsLocal"]
        }
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    gate=p.add_mutually_exclusive_group(required=True)
    gate.add_argument("--plan",action="store_true",help="NO network, Docker or CPU")
    gate.add_argument("--probe",action="store_true",
                      help="2 actual private TCP handshakes; provider also one local actual CPU probe")
    a=p.parse_args(argv)
    try:
        report=observe(probe=a.probe)
        print(json.dumps(report,sort_keys=True,indent=2))
        print("R286_CROSS_VM_REAL_WORKER_PREFLIGHT_NO_CHAIN_NO_DOCKER_MUTATION=true")
        return 0
    except (Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R286_REAL_VM_CROSS_HOST_PREFLIGHT_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
