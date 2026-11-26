"""R399: owner authorization for remote node controls, not transaction signing.
EIP-712 binds each approval to node, chain, owner, operation, exact parameters,
nonce and expiry. No passwords or signing keys are received by this module.
"""
import json,time,secrets,re,os
from pathlib import Path
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak,to_checksum_address
DOMAIN={"name":"SSE Node Control","version":"1","chainId":31340}
FIELDS=[{"name":k,"type":t} for k,t in (
("nodeId","string"),("owner","address"),("operation","string"),
("parametersHash","bytes32"),("nonce","bytes32"),("expiry","uint64"))]
def require(ok,msg):
    if not ok:raise ValueError(msg)
def canonical(params):
    require(type(params) is dict,"object parameters required")
    return json.dumps(params,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def challenge(node,owner,operation,params,*,now=None):
    require(isinstance(node,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}",node),"invalid node")
    require(operation=="provider-interrupt","unsupported operation")
    require(set(params)=={"seconds"} and type(params["seconds"]) is int and 10<=params["seconds"]<=240,"invalid interruption duration")
    now=int(time.time()) if now is None else now
    return dict(nodeId=node,owner=to_checksum_address(owner),operation=operation,
                parametersHash="0x"+keccak(canonical(params)).hex(),
                nonce="0x"+secrets.token_hex(32),expiry=now+120)
def typed(d):
    return encode_typed_data(domain_data=DOMAIN,message_types={"NodeControl":FIELDS},message_data=d)
def wallet_payload(d):
    return dict(types={"EIP712Domain":[{"name":"name","type":"string"},{"name":"version","type":"string"},{"name":"chainId","type":"uint256"}],"NodeControl":FIELDS},primaryType="NodeControl",domain=DOMAIN,message=d)
def verify_and_consume(d,signature,params,*,node,owner,issued,store,now=None):
    now=int(time.time()) if now is None else now
    require(type(d) is dict and set(d)=={f["name"] for f in FIELDS},"invalid challenge fields")
    require(d==issued,"challenge not issued by this node")
    require(d["nodeId"]==node and d["owner"].lower()==owner.lower(),"wrong owner or node")
    require(type(d["expiry"]) is int and now<=d["expiry"]<=now+120,"expired challenge")
    require(d["operation"]=="provider-interrupt" and set(params)=={"seconds"} and type(params["seconds"]) is int and 10<=params["seconds"]<=240,"invalid operation")
    require(d["parametersHash"]=="0x"+keccak(canonical(params)).hex(),"parameters changed")
    require(isinstance(signature,str) and re.fullmatch(r"0x[0-9a-fA-F]{130}",signature),"invalid signature")
    require(Account.recover_message(typed(d),signature=signature).lower()==owner.lower(),"wrong signature")
    require(re.fullmatch(r"0x[0-9a-f]{64}",d["nonce"]),"invalid nonce")
    store=Path(store)
    store.mkdir(mode=0o700,parents=True,exist_ok=True)
    require(not store.is_symlink() and store.stat().st_uid==os.getuid() and not store.stat().st_mode&0o077,"unsafe replay store")
    path=store/(d["nonce"][2:]+".json")
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except FileExistsError:raise ValueError("approval already consumed") from None
    with os.fdopen(fd,"w") as f:
        json.dump(d,f);f.flush();os.fsync(f.fileno())
    fd=os.open(store,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {"operation":d["operation"],"parameters":dict(params),"owner":d["owner"],"nonce":d["nonce"]}
