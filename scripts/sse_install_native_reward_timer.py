#!/usr/bin/env python3
"""Install owner-local persistent native reward observation timer."""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

def run(*args):
    subprocess.run(args,check=True)

def install_unit(path,body):
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.stat().st_uid!=os.getuid() or path.read_text()!=body:
            raise ValueError("existing unit differs: "+path.name)
        return
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        f.write(body)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--commit",required=True)
    a=p.parse_args()
    if os.getuid()==0:
        raise ValueError("run as node owner")
    root=Path(__file__).resolve().parents[1]
    if not re.fullmatch("[0-9a-f]{40}",a.commit):
        raise ValueError("full release commit required")
    def git(*args):
        return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
    if git("rev-parse","HEAD")!=a.commit or git("status","--porcelain"):
        raise ValueError("clean pinned checkout required")
    source=root/"tools/sse_native_reward_collector.py"
    out=Path.home()/".local/share/sse-native-rewards"
    args=[sys.executable,"-B",str(source),"--tick","--output",str(out)]
    if any(not re.fullmatch("[A-Za-z0-9_./-]+",x) for x in args):
        raise ValueError("unsafe systemd argument")
    # Live read-only readiness probe, before installing services.
    run(*args)
    uid=str(os.getuid())
    def linger():
        return subprocess.check_output(["loginctl","show-user",uid,"-p","Linger","--value"],text=True).strip()=="yes"
    if not linger():
        run("loginctl","enable-linger",uid)
    if not linger():
        raise ValueError("linger unavailable")
    units=Path.home()/".config/systemd/user"
    units.mkdir(parents=True,exist_ok=True)
    service="[Unit]\nDescription=SSE native reward observation\n[Service]\nType=oneshot\nExecStart="+" ".join(args)+"\nUMask=0077\nNoNewPrivileges=true\nTimeoutStartSec=180\n"
    timer="[Unit]\nDescription=Periodic SSE native reward observation\n[Timer]\nOnBootSec=10s\nOnUnitInactiveSec=24s\nAccuracySec=1s\n[Install]\nWantedBy=timers.target\n"
    install_unit(units/"sse-native-rewards.service",service)
    install_unit(units/"sse-native-rewards.timer",timer)
    run("systemctl","--user","daemon-reload")
    run("systemctl","--user","enable","--now","sse-native-rewards.timer")
    run("systemctl","--user","is-active","sse-native-rewards.timer")
    print("SSE_NATIVE_REWARD_TIMER_ACTIVE=true")
    print("LATEST_SUMMARY="+str(out/"latest.json"))

if __name__=="__main__":
    main()
