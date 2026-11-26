#!/usr/bin/env python3
"""R393 offline regression coverage for unsigned browser intents."""
import json,sys,unittest
from pathlib import Path
from urllib.parse import urlencode
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from sse_pos_r389_v3_intent_forms import parse,render
from sse_pos_r388_v3_owner_intent import validate

class IntentTests(unittest.TestCase):
    def form(self,role,action,**fields):
        return json.loads(parse(urlencode(dict(role=role,action=action,maxWei=10**10,**fields)).encode(),{role}))
    def test_bid(self):
        d=self.form("provider","bid",requestId=1,feeWei=10**15)
        self.assertEqual(d["params"],{"requestId":1,"feeWei":10**15})
        self.assertEqual(validate(d)[2],0)
    def test_request(self):
        d=self.form("consumer","request",profileHash="0x"+"11"*32,policyHash="0x"+"22"*32,maxFeeWei=10**15,biddingClose=1795800000)
        self.assertEqual(validate(d)[2],0)
    def test_fund(self):
        fields=dict(role="consumer",action="fund",maxWei=10**16,requestId=1,bidIndex=0,bidFeeWei=10**15,endpointHash="0x"+"33"*32,epochs=4,monitorBudget=16*10**14,perMonitorEpochReward=10**14,requiredFaultTolerance=1,gasBoundSeats=4,confirmationSeconds=3600,responseSeconds=180,monitoringSeconds=300,evidenceSeconds=600,reservationFee=2*10**14,exposureBudget=12*10**14,conditionalQuorumPolicy="true")
        d=json.loads(parse(urlencode(fields).encode(),{"consumer"}))
        self.assertEqual(validate(d)[2],56*10**14)
        self.assertIs(d["params"]["terms"]["conditionalQuorumPolicy"],True)
    def test_reject_wrong_role(self):
        with self.assertRaises(ValueError):self.form("monitor","bid",requestId=1,feeWei=1)
    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):parse(b"role=consumer&role=provider&action=close&maxWei=100&leaseId=1",{"consumer"})
    def test_reject_negative(self):
        with self.assertRaises(ValueError):self.form("provider","bid",requestId=-1,feeWei=1)
    def test_reject_extra(self):
        with self.assertRaises(ValueError):self.form("consumer","close",leaseId=1,command="anything")
    def test_role_forms(self):
        s=render({"consumer","monitor"})
        self.assertIn("Fund",s)
        self.assertIn("Register",s)
        self.assertNotIn(">Bid</summary>",s)
if __name__=="__main__":unittest.main()
