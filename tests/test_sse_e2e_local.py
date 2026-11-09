"""Offline tests for ABI, typed-data, dev-only safety and preflight."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from sse_challenge import keccak256
from sse_e2e_local import (word, encode_static, encode_last_bytes,
                           eip712, DemoError, sign, fast_forward)

CONTRACT='0x0dcd1bf9a1b36ce34237eeafef220932846bcd82'
USER='0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266'
RESPONSE='0x'+'11'*32
SIGNATURE='0x'+ '12'*64 + '1b'

class E2ETest(unittest.TestCase):
    def test_abi_uint(self):
        self.assertEqual(word(13),bytes.fromhex('00'*31+'0d'))

    def test_abi_address(self):
        self.assertEqual(word(USER)[-20:],bytes.fromhex(USER[2:]))

    def test_abi_reject_bool_and_oversize(self):
        for bad in (True,-1,2**256,'broken'):
            with self.assertRaises(DemoError): word(bad)

    def test_create_lease_selector_and_args(self):
        sig='createLease(address,bytes32,bytes32,uint256,uint256,uint256,uint256,uint64,uint64,uint64)'
        data=bytes.fromhex(encode_static(sig, USER, RESPONSE, RESPONSE,25,5,25,1,600,300,300)[2:])
        self.assertEqual(len(data), 4+320)
        self.assertEqual(data[:4],keccak256(sig.encode())[:4])
        self.assertEqual(int.from_bytes(data[-32:],'big'),300)

    def test_provider_response_dynamic_bytes(self):
        sig='submitProviderResponse(uint256,uint256,bytes)'
        data=bytes.fromhex(encode_last_bytes(sig,(2,0),SIGNATURE)[2:])
        self.assertEqual(data[:4],keccak256(sig.encode())[:4])
        self.assertEqual(int.from_bytes(data[68:100],'big'),96)
        self.assertEqual(int.from_bytes(data[100:132],'big'),65)
        self.assertEqual(data[132:197],bytes.fromhex(SIGNATURE[2:]))
        self.assertEqual(len(data),4+96+32+96)

    def test_monitor_vote_dynamic_bytes(self):
        sig='submitMonitorVote(uint256,uint256,uint8,bytes32,bytes)'
        data=bytes.fromhex(encode_last_bytes(sig,(2,0,1,RESPONSE),SIGNATURE)[2:])
        self.assertEqual(data[:4],keccak256(sig.encode())[:4])
        self.assertEqual(int.from_bytes(data[132:164],'big'),160)
        self.assertEqual(int.from_bytes(data[164:196],'big'),65)

    def test_bad_signature_rejected(self):
        for bad in ('abc', '0xzz', '0x12'):
            with self.assertRaises(DemoError):
                encode_last_bytes('go(bytes)',(),bad)

    def test_typed_provider_fields(self):
        msg={'leaseId':2,'epochId':0,'requestHash':RESPONSE,'responseHash':RESPONSE}
        data=eip712('ProviderResponse', USER, msg, 31337, CONTRACT)
        self.assertEqual(data['domain']['chainId'],31337)
        self.assertEqual(data['domain']['verifyingContract'],CONTRACT)
        self.assertEqual(data['primaryType'],'ProviderResponse')
        self.assertEqual([f['name'] for f in data['types']['ProviderResponse']],list(msg))

    def test_typed_vote_fields(self):
        msg={'leaseId':2,'epochId':0,'requestHash':RESPONSE,'outcome':1,
             'responseHash':RESPONSE,'evidenceHash':RESPONSE}
        data=eip712('MonitorVote',USER,msg,31337,CONTRACT)
        self.assertEqual(data['types']['MonitorVote'][3],{'name':'outcome','type':'uint8'})

    def test_typed_bad_fields_rejected(self):
        with self.assertRaises(DemoError): eip712('ProviderResponse',USER,{'leaseId':2},31337,CONTRACT)

    def test_typed_bad_type_rejected(self):
        with self.assertRaises(DemoError): eip712('ProviderAck',USER,{},31337,CONTRACT)

    def test_fast_forward_does_not_rewind(self):
        class RPC:
            def request(self,method,params):
                if method=='eth_getBlockByNumber': return {'timestamp':'0x20'}
                raise AssertionError('must not mine')
        fast_forward(RPC(),20)

    def test_sign_rpc_string_payload(self):
        class RPC:
            def request(self,method,params):
                self.assert_method=method
                return SIGNATURE
        self.assertEqual(sign(RPC(),USER,{'types':{}}),SIGNATURE)

    def test_response_signature_format(self):
        self.assertEqual(len(bytes.fromhex(SIGNATURE[2:])),65)


class FullControllerFlowTest(unittest.TestCase):
    """Mocked protocol control flow, not an on-chain integration substitute."""
    def test_full_flow_state_machine_with_fake_chain(self):
        import tempfile
        from unittest.mock import patch
        import sse_e2e_local as demo
        from sse_challenge import expected_response_hash
        consumer = demo.DEFAULT_CONSUMER
        provider = demo.DEFAULT_PROVIDER
        monitors = [f'0x{n:040x}' for n in range(11, 15)]
        pool = '0x'+'be'*20
        rand = '0x'+'ef'*20
        state = {'epoch':None, 'lease':None, 'created':False, 'confirmed':0,
                 'votes':0, 'signed':False, 'sealed':False,
                 'settled':False, 'evidenceClosed':False,'closed':False,
                 'time':10000, 'counter':0}
        old_lease = {'consumer':consumer,'provider':provider,'stateName':'Closed',
                     'maxEpochs':1,'resourceProfileHash':'0x'+'ab'*32,
                     'monitors':monitors}
        def inspection(rpc, contract, lease_id, epoch_id, **kwargs):
            if lease_id == 1:
                return {'lease':old_lease,'epoch':{'outcomeName':'Failure','evidenceClosed':True}}
            if not state['created']:
                raise AssertionError('new lease not created')
            return {'lease':state['lease'], 'epoch':state['epoch']}
        def send(rpc, sender, to, data, value=0):
            from sse_e2e_local import _selector
            sigs = {
                'createLease(address,bytes32,bytes32,uint256,uint256,uint256,uint256,uint64,uint64,uint64)': 'create',
                'acceptLease(uint256)':'accept',
                'fulfillRandomness(uint256,uint256)':'randomness',
                'finalizeMonitorCommittee(uint256)':'assigned',
                'confirmMonitorAssignment(uint256)':'confirm',
                'admitEpoch(uint256,bytes32)':'admit',
                'submitProviderResponse(uint256,uint256,bytes)':'provider',
                'submitMonitorVote(uint256,uint256,uint8,bytes32,bytes)':'vote',
                'sealMonitoring(uint256,uint256)':'seal',
                'settleEpoch(uint256,uint256)':'settle',
                'closeEpochEvidence(uint256,uint256)':'evidence',
                'closeLease(uint256)':'close',
                'releaseCommitteeAfterEvidence(uint256)':'release',
            }
            action = next((name for signature,name in sigs.items()
                           if data.startswith('0x'+_selector(signature).hex())), None)
            self.assertIsNotNone(action)
            state['counter'] += 1
            if action == 'create':
                self.assertEqual(value, 25)
                state['created']=True
                state['lease']={'stateName':'Offered','assignmentId':2,
                                'provider':provider,'monitors':monitors}
            elif action == 'accept': state['lease']['stateName']='Accepted'
            elif action == 'assigned': state['lease']['monitors']=monitors
            elif action == 'confirm':
                state['confirmed']+=1
                if state['confirmed']==4:state['lease']['stateName']='Ready'
            elif action == 'admit':
                request='0x'+data[2+4*2+64:2+4*2+128]
                state['lease']['stateName']='Active'
                state['epoch']={'requestHash':request,'responseHash':expected_response_hash(request),
                                'responseDeadline':state['time']+600,
                                'monitoringClose':state['time']+900,
                                'evidenceClose':state['time']+1200,
                                'responseAuthenticated':False,'successVotes':0,'failureVotes':0}
            elif action=='provider':state['epoch']['responseAuthenticated']=True
            elif action=='vote':
                self.assertTrue(state['epoch']['responseAuthenticated'])
                state['epoch']['successVotes']+=1
            elif action=='seal':
                self.assertGreater(state['time'],state['epoch']['monitoringClose'])
                state['epoch']['outcomeName']='Success'
            elif action=='settle':
                state['epoch'].update(providerCredited=25,consumerCredited=0,unresolvedExposure=0)
            elif action=='evidence':state['epoch']['evidenceClosed']=True
            elif action=='close':state['lease']['stateName']='Closed'
            elif action=='release':self.assertTrue(state['epoch']['evidenceClosed'])
            return '0x'+f'{state["counter"]:064x}'
        def forward(rpc, target):state['time']=target
        class RPC:
            def request(self,method,params):
                if method=='eth_accounts':return [consumer,provider,rand,*monitors]
                raise AssertionError(method)
        with tempfile.TemporaryDirectory() as d, \
             patch.object(demo,'inspect_chain',side_effect=inspection), \
             patch.object(demo,'one_address',side_effect=[pool,rand]), \
             patch.object(demo,'one_uint',side_effect=[4,2]), \
             patch.object(demo,'quick_health'), \
             patch.object(demo,'tx',side_effect=send), \
             patch.object(demo,'observe',return_value={'outcome':'SUCCESS_OBSERVED'}), \
             patch.object(demo,'sign',return_value=SIGNATURE), \
             patch.object(demo,'latest_timestamp',side_effect=lambda rpc:state['time']), \
             patch.object(demo,'fast_forward',side_effect=forward):
            result=demo.run(RPC(),CONTRACT,'http://127.0.0.1:8877',Path(d),True,True)
            self.assertEqual(result['status'],'SUCCESS_COMPLETE')
            self.assertTrue(result['quorumReached'])
            self.assertEqual(result['finalEpoch']['providerCredited'],25)
            self.assertEqual(len(result['evidenceCommitments']),3)
            self.assertEqual(len(result['evidenceFiles']),3)
            self.assertEqual(state['confirmed'],4)
            self.assertEqual(state['epoch']['successVotes'],3)
            self.assertTrue((Path(d)/'lease-2'/'run.json').exists())


if __name__ == '__main__':
    unittest.main()
