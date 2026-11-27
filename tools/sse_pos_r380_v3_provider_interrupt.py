#!/usr/bin/env python3
"""R380 bounded local provider V3 interruption, preserving V2 and native chain.
Temporarily disable only the V3 loopback backend using SIGSTOP/SIGCONT.
Owner-only process, exact cmdline check, independent systemd recovery timer.
No root, network firewall, Docker, validator or key modifications.
"""
import argparse,os,subprocess,signal,time,sys
from pathlib import Path
def require(x,m):
    if not x:raise ValueError(m)
def identity(pid):
    p=Path("/proc")/str(pid)
    require(pid>1 and p.stat().st_uid==os.getuid() and os.getuid()!=0,"not owner process")
    cmd=(p/"cmdline").read_bytes().split(b"\x00")
    require(any(x.endswith(b"/v3_compute_response_server.py") for x in cmd),"not V3 provider process")
    return (p/"stat").read_text().rsplit(")",1)[1].split()[19]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seconds",type=int,default=120)
    p.add_argument("--pid",type=int,required=True)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--identity")
    a=p.parse_args()
    ident=identity(a.pid)
    if a.resume:
        require(a.identity==ident,"process identity changed")
        os.kill(a.pid,signal.SIGCONT)
        print("V3_PROVIDER_RESUMED=true")
        return
    require(10<=a.seconds<=240 and sys.stdin.isatty(),"bounded owner terminal required")
    print("Pause only V3 provider PID",a.pid,"for",a.seconds,"seconds")
    require(input("Type INTERRUPT-V3-PROVIDER: ")=="INTERRUPT-V3-PROVIDER","not authorized")
    pause(a.pid,a.seconds,expected_identity=ident)

def pause(pid,seconds,*,expected_identity):
    """Internal bounded operation; caller must authenticate owner first."""
    require(type(seconds) is int and 10<=seconds<=240,"invalid duration")
    ident=identity(pid)
    require(ident==expected_identity,"process identity changed")
    state=(Path("/proc")/str(pid)/"stat").read_text().rsplit(")",1)[1].split()[0]
    require(state not in ("T","t","Z","X"),"provider already paused or unavailable")
    unit="sse-v3-recover-"+str(pid)+"-"+str(time.time_ns())
    subprocess.run(["systemd-run","--user","--unit",unit,"--on-active="+str(seconds)+"s","--timer-property=AccuracySec=1s","--timer-property=RandomizedDelaySec=0",sys.executable,str(Path(__file__).resolve()),"--pid",str(pid),"--resume","--identity",ident],check=True)
    subprocess.run(["systemctl","--user","is-active","--quiet",unit+".timer"],check=True)
    require(identity(pid)==ident,"process changed")
    os.kill(pid,signal.SIGSTOP)
    print("V3_PROVIDER_PAUSED=true recovery="+unit+".timer",flush=True)
    return unit+".timer"
if __name__=="__main__":main()
