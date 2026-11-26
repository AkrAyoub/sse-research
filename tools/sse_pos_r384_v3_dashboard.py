"""Read-only finalized V3 marketplace panel; bounded queries, no signing."""
from sse_pos_r362_v3_market_operations import MARKET,LEDGER,verify,call,require
from sse_pos_r367_v3_compute_wire import LEASE,EPOCH,VOTE
def overview(ask):
    proof=verify(ask)
    tag=hex(proof["finalizedHeight"])
    head=ask("eth_getBlockByNumber",[tag,False])
    def read(sig,types=(),args=(),out=("uint256",),target=MARKET):
        return call(ask,target,sig,types,args,out,tag=tag)
    n=read("nextRequestId()")[0]; m=read("nextLeaseId()")[0]
    requests=[];leases=[]
    for i in range(max(1,n-4),n):
        r=read("requests(uint256)",("uint256",),(i,),("address","bytes32","bytes32","uint256","uint64","bool"))
        requests.append(dict(id=i,consumer=r[0],profileHash="0x"+r[1].hex(),policyHash="0x"+r[2].hex(),maxFeeWei=str(r[3]),biddingClose=r[4],selected=r[5],bidCount=read("bidCount(uint256)",("uint256",),(i,))[0]))
    for i in range(max(1,m-3),m):
        l=read("lease(uint256)",("uint256",),(i,),(LEASE,))[0]
        a=read("scientificAccounting(uint256)",("uint256",),(i,),("uint256","uint256","uint256","uint256","uint256","uint256","bool"))
        epochs=[]
        for j in range(max(0,l[9]-4),l[9]):
            e=read("epoch(uint256,uint256)",("uint256","uint256"),(i,j),(EPOCH,))[0]
            v=read("epoch(uint256,uint256)",("uint256","uint256"),(i,j),(VOTE,),LEDGER)[0]
            h=read("scientificEpoch(uint256,uint256)",("uint256","uint256"),(i,j),("(bytes32,uint8,bool,bool,uint256,uint256,uint256)",))[0]
            epochs.append(dict(id=j,accounted=e[7],acknowledged=e[6],resolved=e[5],authenticated=v[8],outcome=v[10],successVotes=v[4],failureVotes=v[5],historyMask=h[1],unresolvedWei=str(h[6])))
        leases.append(dict(id=i,consumer=l[0],provider=l[1],phase=l[21],accepted=l[22],nextEpoch=l[9],maxEpochs=l[8],epochFeeWei=str(l[7]),accounting=dict(zip(("fundedWei","availableWei","exposureWei","budgetWei","providerCreditWei","consumerCreditWei","conserved"),[str(x) for x in a[:6]]+[a[6]])),epochs=epochs))
    active=read("activeMonitorCount()")[0]
    require(ask("eth_getBlockByNumber",[tag,False])["hash"]==head["hash"],"finalized anchor changed")
    return dict(deployment=proof,blockHash=head["hash"],requestsCreated=n-1,leasesCreated=m-1,activeMonitors=active,recentRequests=requests,recentLeases=leases,physicalSlaTruthProved=False)
