#!/usr/bin/env python3
"""R407 integrated owner credential enrollment and bounded session primitives.
No application or validator wallet credentials accepted here.
"""
import argparse,hashlib,hmac,json,os,secrets,stat,threading,time
from pathlib import Path
from getpass import getpass

def require(ok,msg):
    if not ok:raise ValueError(msg)

def derive(password,salt):
    require(isinstance(password,str) and 12<=len(password)<=256,"password length must be 12–256 characters")
    return hashlib.scrypt(password.encode("utf-8"),salt=salt,n=32768,r=8,p=1,maxmem=64*1024*1024,dklen=32)

def load(path):
    path=Path(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,"r") as f:
        s=os.fstat(f.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077 and s.st_size<=4096,"unsafe owner credential file")
        d=json.load(f)
    require(set(d)=={"version","salt","digest"} and d["version"]==1,"invalid credential format")
    salt=bytes.fromhex(d["salt"]);digest=bytes.fromhex(d["digest"])
    require(len(salt)==32 and len(digest)==32,"invalid credential record")
    return salt,digest

def enroll(path,password):
    path=Path(path)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    s=path.parent.stat()
    require(not path.parent.is_symlink() and s.st_uid==os.getuid() and not s.st_mode&0o077,"unsafe credential directory")
    salt=secrets.token_bytes(32)
    d=dict(version=1,salt=salt.hex(),digest=derive(password,salt).hex())
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(d,f);f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

class Sessions:
    def __init__(self,path,*,clock=time.monotonic):
        self.salt,self.digest=load(path)
        self.clock=clock
        self.lock=threading.Lock()
        self.sessions={}
        self.next_login=0
        self.failures=0
    @staticmethod
    def key(token):
        require(isinstance(token,str) and len(token)==43,"invalid session")
        return hashlib.sha256(token.encode("ascii")).digest()
    def login(self,password):
        with self.lock:
            now=self.clock()
            require(now>=self.next_login,"login temporarily rate limited")
            self.next_login=now+1
            try:ok=hmac.compare_digest(derive(password,self.salt),self.digest)
            except (ValueError,TypeError):ok=False
            if not ok:
                self.failures=min(self.failures+1,6)
                self.next_login=self.clock()+min(60,2**self.failures)
                raise ValueError("invalid owner credentials")
            self.failures=0
            now=self.clock()
            self.sessions={k:v for k,v in self.sessions.items() if v[1]>now}
            require(len(self.sessions)<8,"session limit; log out or wait for expiry")
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            self.sessions[self.key(token)]=(csrf,now+900)
            return token,csrf
    def authorize(self,token,csrf=None):
        with self.lock:
            k=self.key(token);v=self.sessions.get(k)
            require(v is not None and v[1]>self.clock(),"session expired or unknown")
            if csrf is not None:
                require(isinstance(csrf,str) and hmac.compare_digest(v[0],csrf),"invalid CSRF token")
            return v[0]
    def logout(self,token,csrf):
        with self.lock:
            k=self.key(token);v=self.sessions.get(k)
            require(v is not None and v[1]>self.clock() and isinstance(csrf,str) and hmac.compare_digest(v[0],csrf),"invalid logout")
            del self.sessions[k]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--credential",type=Path,default=Path.home()/".local/share/sse-owner-login/credential.json")
    a=p.parse_args()
    require(os.getuid()!=0 and os.isatty(0) and os.isatty(2),"local nonroot owner terminal required")
    require(not a.credential.exists() and not a.credential.is_symlink(),"already enrolled; do not overwrite")
    print("Choose a dedicated administration password, NOT your blockchain wallet password.")
    first=getpass("New administration password: ")
    require(first==getpass("Repeat administration password: "),"passwords differ")
    enroll(a.credential,first)
    print("SSE_INTEGRATED_OWNER_ENROLLED=true")
if __name__=="__main__":main()
