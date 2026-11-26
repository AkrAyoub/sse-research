#!/usr/bin/env python3
"""R362 V3 owner-local registration/request/bid and read-only deployment check.
Candidate integration, not a full agent. Never retries a broadcast.
"""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
from getpass import getpass
from eth_account import Account
from eth_abi import encode, decode
from eth_utils import keccak, to_checksum_address
from sse_pos_r206_adaptive_v2_deployment_audit import rpc, GENESIS
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore, ORIGINAL_GENESIS_EOA
from sse_pos_r242_v2_owner_local_send import journal_lock

MARKET="0xf1c17ce1dc8d4310c42fed1347ca59d22f54f238"
LEDGER="0xd02d23546de19129fbaa3688ed5fa82fec4fa95a"
DEPLOYER="0xed0ed5e0526898c6e0e3c83140efca12672e7ff0"
TX="0x4490fe65b67b0adeabb190be109c4c80c55be9f24a668aaefd9c99f2479c9515"
BLOCK="0x7d999af8c200a0e53b54b3f6882ff1d68a7e2136bf6602a9614df1eba2097e68"
HEIGHT=37376
BOND=10**15
def require(ok,msg):
    if not ok: raise ValueError(msg)
def calldata(sig,types=(),args=()):
    return "0x"+(keccak(text=sig)[:4]+encode(types,args)).hex()
def call(ask,target,sig,types=(),args=(),out=("uint256",),tag="latest"):
    raw=ask("eth_call",[{"to":target,"data":calldata(sig,types,args)},tag])
    return decode(out,bytes.fromhex(raw[2:]))
def verify(ask):
    require(ask("eth_chainId",[])=="0x7a6c","wrong chain")
    require(ask("eth_getBlockByNumber",["0x0",False])["hash"].lower()==GENESIS,"wrong genesis")
    receipt=ask("eth_getTransactionReceipt",[TX])
    tx=ask("eth_getTransactionByHash",[TX])
    require(receipt["status"]=="0x1" and receipt["contractAddress"].lower()==MARKET and receipt["blockHash"].lower()==BLOCK and int(receipt["blockNumber"],16)==HEIGHT and tx["from"].lower()==DEPLOYER and tx["to"] is None and int(tx["nonce"],16)==9,"wrong deployment receipt")
    require(ask("eth_getBlockByNumber",[hex(HEIGHT),False])["hash"].lower()==BLOCK,"deployment reorganized")
    final=int(ask("eth_getBlockByNumber",["finalized",False])["number"],16)
    require(final>=HEIGHT,"deployment not finalized")
    tag=hex(final)
    hashes={}
    for name,address,size in (("market",MARKET,23753),("ledger",LEDGER,10668)):
        code=bytes.fromhex(ask("eth_getCode",[address,tag])[2:])
        require(len(code)==size,"wrong runtime size")
        hashes[name]=hashlib.sha256(code).hexdigest()
    require(call(ask,MARKET,"votes()",out=("address",),tag=tag)[0].lower()==LEDGER,"wrong ledger")
    require(call(ask,LEDGER,"settlement()",out=("address",),tag=tag)[0].lower()==MARKET,"wrong settlement")
    require(call(ask,MARKET,"minimumBond()",tag=tag)[0]==BOND,"wrong bond")
    return {"chainId":31340,"market":MARKET,"ledger":LEDGER,"finalizedHeight":final,"observedRuntimeSha256":hashes,"compiledRuntimeParityVerified":False}
def plan(action,p):
    if action=="register":
        require(set(p)==set(),"register takes no params")
        return MARKET,calldata("registerMonitor()"),BOND
    if action=="request":
        require(set(p)=={"profileHash","policyHash","maxFeeWei","biddingClose"},"wrong request fields")
        return MARKET,calldata("requestResource(bytes32,bytes32,uint256,uint64)",("bytes32","bytes32","uint256","uint64"),(bytes.fromhex(p["profileHash"][2:]),bytes.fromhex(p["policyHash"][2:]),p["maxFeeWei"],p["biddingClose"])),0
    if action=="bid":
        require(set(p)=={"requestId","feeWei"},"wrong bid fields")
        return MARKET,calldata("placeBid(uint256,uint256)",("uint256","uint256"),(p["requestId"],p["feeWei"])),0
    if action=="fund":
        require(set(p)=={"requestId","bidIndex","bidFeeWei","terms"},"wrong funding fields")
        t=p["terms"]
        names=("endpointHash","epochs","monitorBudget","perMonitorEpochReward","requiredFaultTolerance","gasBoundSeats","confirmationSeconds","responseSeconds","monitoringSeconds","evidenceSeconds","reservationFee","exposureBudget","conditionalQuorumPolicy")
        require(set(t)==set(names),"wrong V3 terms")
        ts="(bytes32,uint256,uint256,uint256,uint256,uint256,uint64,uint64,uint64,uint64,uint256,uint256,bool)"
        values=tuple(bytes.fromhex(t[n][2:]) if n=="endpointHash" else t[n] for n in names)
        return MARKET,calldata("chooseBidAndFund(uint256,uint256,"+ts+")",("uint256","uint256",ts),(p["requestId"],p["bidIndex"],values)),p["bidFeeWei"]*t["epochs"]+t["monitorBudget"]
    if action=="accept":
        require(set(p)=={"leaseId","termsHash"},"wrong accept fields")
        return MARKET,calldata("acceptLease(uint256,bytes32)",("uint256","bytes32"),(p["leaseId"],bytes.fromhex(p["termsHash"][2:]))),0
    if action=="start":
        require(set(p)=={"leaseId","requestHash"},"wrong start fields")
        return MARKET,calldata("startEpoch(uint256,bytes32)",("uint256","bytes32"),(p["leaseId"],bytes.fromhex(p["requestHash"][2:]))),0
    if action in ("draw","close","cancel-expired-draw","cancel-unconfirmed","cancel-unaccepted","expire-idle"):
        require(set(p)=={"leaseId"},"wrong lease fields")
        fn={"draw":"drawCommittee","close":"closeLease","cancel-expired-draw":"cancelExpiredDraw","cancel-unconfirmed":"cancelUnconfirmed","cancel-unaccepted":"cancelUnaccepted","expire-idle":"forceCloseIdle"}[action]
        return MARKET,calldata(fn+"(uint256)",("uint256",),(p["leaseId"],)),0
    if action in ("finalize","close-evidence"):
        require(set(p)=={"leaseId","epochId"},"wrong epoch fields")
        fn={"finalize":"finalizeEpoch","close-evidence":"closeEpochEvidence"}[action]
        return MARKET,calldata(fn+"(uint256,uint256)",("uint256","uint256"),(p["leaseId"],p["epochId"])),0
    if action in ("market-withdraw","ledger-withdraw","monitor-exit"):
        require(not p,"unexpected fields")
        return (LEDGER if action=="ledger-withdraw" else MARKET),calldata("exitMonitor()" if action=="monitor-exit" else "withdraw()"),0
    if action=="authenticate":
        require(set(p)=={"leaseId","epochId","responseHash","signature"},"wrong response fields")
        return MARKET,calldata("authenticateProviderResponse(uint256,uint256,bytes32,bytes)",("uint256","uint256","bytes32","bytes"),(p["leaseId"],p["epochId"],bytes.fromhex(p["responseHash"][2:]),bytes.fromhex(p["signature"][2:]))),0
    if action=="acknowledge":
        require(set(p)=={"leaseId","epochId","signature"},"wrong acknowledgment fields")
        return MARKET,calldata("submitAcknowledgment(uint256,uint256,bytes)",("uint256","uint256","bytes"),(p["leaseId"],p["epochId"],bytes.fromhex(p["signature"][2:]))),0
    if action=="vote":
        require(set(p)=={"leaseId","epochId","outcome","evidenceHash"} and p["outcome"] in (1,2),"wrong vote fields")
        return LEDGER,calldata("submitVoteDirect(uint256,uint256,uint8,bytes32)",("uint256","uint256","uint8","bytes32"),(p["leaseId"],p["epochId"],p["outcome"],bytes.fromhex(p["evidenceHash"][2:]))),0
    raise ValueError("unknown action")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    p.add_argument("--action",choices=("inspect","register","request","bid","fund","accept","start","draw","close","cancel-expired-draw","cancel-unconfirmed","cancel-unaccepted","expire-idle","finalize","close-evidence","market-withdraw","ledger-withdraw","monitor-exit","authenticate","acknowledge","vote"),default="inspect")
    p.add_argument("--params",default="{}")
    p.add_argument("--address")
    p.add_argument("--keystore",type=Path)
    p.add_argument("--max-wei",type=int,default=10**10+BOND)
    p.add_argument("--send",action="store_true")
    a=p.parse_args()
    ask=lambda m,v:rpc(a.rpc,m,v)
    proof=verify(ask)
    print(json.dumps(proof),flush=True)
    if a.action=="inspect":
        print("ACTIVE_MONITORS",call(ask,MARKET,"activeMonitorCount()")[0])
        return
    sender=to_checksum_address(a.address).lower()
    require(sender!=ORIGINAL_GENESIS_EOA.lower(),"genesis wallet prohibited")
    target,data,value=plan(a.action,json.loads(a.params))
    query={"from":sender,"to":target,"data":data,"value":hex(value)}
    def quote():
        gas=(int(ask("eth_estimateGas",[query]),16)*125+99)//100
        price=int(ask("eth_gasPrice",[]),16)
        require(0<gas and 0<price and gas*price+value<=a.max_wei,"spend cap exceeded")
        require(int(ask("eth_getBalance",[sender,"latest"]),16)>=gas*price+value,"insufficient funds")
        nonce=int(ask("eth_getTransactionCount",[sender,"latest"]),16)
        require(int(ask("eth_getTransactionCount",[sender,"pending"]),16)==nonce,"pending nonce")
        return gas,price,nonce
    gas,price,nonce=quote()
    print(json.dumps({"action":a.action,"from":sender,"to":target,"data":data,"valueWei":value,"gas":gas,"gasPrice":price,"nonce":nonce,"maxWei":a.max_wei}),flush=True)
    if not a.send:return
    require(a.keystore is not None and sys.stdin.isatty() and sys.stderr.isatty(),"local owner terminal required")
    root=Path.home()/".local/share/sse-transaction-journal"
    with journal_lock(root,sender):
        # V2 and V3 share wallet lock, but separate journal schemas.
        dest=root/"v3"
        dest.mkdir(mode=0o700,exist_ok=True)
        require(not dest.is_symlink() and dest.stat().st_uid==os.geteuid() and not dest.stat().st_mode&0o077,"unsafe V3 journal")
        for folder in (root,dest):
            for f in folder.glob(sender+"-*.json"):
                require(not f.is_symlink() and f.is_file() and f.stat().st_size<=65536,"unsafe journal")
                entry=json.loads(f.read_text())
                h=entry["transactionHash"]
                rec=ask("eth_getTransactionReceipt",[h])
                require(rec is not None and rec["from"].lower()==sender and rec["transactionHash"].lower()==h.lower(),"unresolved prior intent")
                require(ask("eth_getBlockByNumber",[rec["blockNumber"],False])["hash"].lower()==rec["blockHash"].lower(),"prior intent reorganized")
                require(int(rec["blockNumber"],16)<=int(ask("eth_getBlockByNumber",["finalized",False])["number"],16),"prior intent not finalized")
        require(input("Type AUTHORIZE-ONE-V3-TRANSACTION: ")=="AUTHORIZE-ONE-V3-TRANSACTION","not authorized")
        private=Account.decrypt(safe_keystore(a.keystore),getpass("Application wallet password: "))
        account=Account.from_key(private)
        require(account.address.lower()==sender,"wrong wallet")
        verify(ask)
        require(quote()==(gas,price,nonce),"quote changed; review again")
        signed=account.sign_transaction({"chainId":31340,"nonce":nonce,"to":to_checksum_address(target),"data":data,"value":value,"gas":gas,"gasPrice":price})
        h="0x"+bytes(signed.hash).hex()
        path=dest/(sender+"-"+str(nonce)+".json")
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as f:
            json.dump({"sender":sender,"nonce":nonce,"transactionHash":h,"target":target,"data":data,"valueWei":value},f)
            f.flush();os.fsync(f.fileno())
        fd=os.open(dest,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        print("DURABLE_TX_HASH="+h,flush=True)
        require(ask("eth_sendRawTransaction",["0x"+bytes(signed.raw_transaction).hex()]).lower()==h,"wrong acknowledgment; do not retry")
        del private,account,signed
        for _ in range(24):
            rec=ask("eth_getTransactionReceipt",[h])
            if rec:
                require(ask("eth_getBlockByNumber",[rec["blockNumber"],False])["hash"].lower()==rec["blockHash"].lower(),"receipt reorganized")
                print(json.dumps(rec,indent=2))
                require(rec["status"]=="0x1","transaction reverted")
                return
            time.sleep(1)
        print("RECEIPT_PENDING_DO_NOT_RETRY="+h)
if __name__=="__main__":
    try:main()
    except (ValueError,TypeError,KeyError,OSError) as exc:
        sys.exit("R362_REFUSED: "+str(exc))
