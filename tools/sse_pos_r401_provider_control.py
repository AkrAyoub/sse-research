"""R401: single-node owner control broker. No arbitrary PID or shell from requests."""
import threading,time
from pathlib import Path
from sse_pos_r399_owner_control_auth import challenge,wallet_payload,verify_and_consume,require
from sse_pos_r380_v3_provider_interrupt import identity,pause

class ProviderControl:
    def __init__(self,*,node,owner,pid,store):
        self.node=node
        self.owner=owner
        self.pid=pid
        self.identity=identity(pid)
        self.store=Path(store)
        self.lock=threading.Lock()
        self.pending={}
        self.last_issue=0.0
        self.blocked_until=0.0

    def issue(self,seconds):
        with self.lock:
            now=time.monotonic()
            require(now>=self.blocked_until,"interruption or recovery window active")
            require(now-self.last_issue>=1,"challenge rate limit")
            self.pending={k:v for k,v in self.pending.items() if v[2]>now}
            require(len(self.pending)<16,"too many outstanding challenges")
            params={"seconds":seconds}
            d=challenge(self.node,self.owner,"provider-interrupt",params)
            self.pending[d["nonce"]]=(d,params,now+120)
            self.last_issue=now
            return {"challenge":dict(d),"parameters":dict(params),"typedData":wallet_payload(dict(d))}

    def approve(self,d,signature,params):
        with self.lock:
            now=time.monotonic()
            require(now>=self.blocked_until,"interruption or recovery window active")
            require(type(d) is dict and isinstance(d.get("nonce"),str),"invalid challenge")
            pending=self.pending.get(d["nonce"])
            require(pending is not None and pending[2]>now and pending[1]==params,"unknown or expired approval")
            require(identity(self.pid)==self.identity,"provider process replaced; rebind locally")
            approval=verify_and_consume(d,signature,params,node=self.node,owner=self.owner,issued=pending[0],store=self.store)
            del self.pending[d["nonce"]]
            self.pending.clear()
            self.blocked_until=time.monotonic()+params["seconds"]+5
            timer=pause(self.pid,params["seconds"],expected_identity=self.identity)
            return {"operation":approval["operation"],"nonce":approval["nonce"],"providerPaused":True,"recoveryTimer":timer,"recoveryVerified":False,"requestedDurationSeconds":params["seconds"]}
