"""Milestone 3 evidence-integrity tests (hash function mocked for unit isolation)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import m3_evidence_audit as audit


class EvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.monitor = '0x' + 'aa'*20
        self.run = {
            'schema':'sse-local-full-cycle-v1', 'status':'SUCCESS_COMPLETE',
            'chainId':31337, 'leaseId':3, 'settlement':'0x'+'12'*20,
            'requestHash':'0x'+'34'*32, 'responseHash':'0x'+'56'*32,
            'responseDeadline':100, 'monitoringClose':200,
            'evidenceCommitments':{}, 'evidenceFiles':['.local\\lease-3\\monitor_1_evidence.json'],
        }
        self.evidence = {
            'monitor':self.monitor, 'chainId':31337, 'leaseId':3, 'epochId':0,
            'settlement':self.run['settlement'], 'requestHash':self.run['requestHash'],
            'responseHash':self.run['responseHash'], 'responseDeadline':100,
            'monitoringClose':200,
            'observation':{'outcome':'SUCCESS_OBSERVED','leaseId':3,'epochId':0,'requestHash':self.run['requestHash']},
        }
        self.write()

    def write(self):
        path = self.root/'monitor_1_evidence.json'
        path.write_text(json.dumps(self.evidence),encoding='utf8')
        digest = '0x'+hashlib.sha256(audit.canonical_bytes(self.evidence)).hexdigest()
        self.run['evidenceCommitments'] = {self.monitor:digest}
        (self.root/'run.json').write_text(json.dumps(self.run),encoding='utf8')

    def verified(self):
        with patch.object(audit, 'keccak256', lambda data: hashlib.sha256(data).digest()):
            return audit.verify_offline(self.root/'run.json')

    def test_match(self):
        v=self.verified()
        self.assertTrue(v['offlineCommitmentsVerified'])
        self.assertFalse(v['onChainCommitmentsVerified'])
        self.assertFalse(v['truthOrIndependenceProven'])

    def test_mutation_rejected(self):
        self.evidence['observation']['testNote']='tampered'
        (self.root/'monitor_1_evidence.json').write_text(json.dumps(self.evidence), encoding='utf8')
        with self.assertRaisesRegex(audit.EvidenceAuditError, 'commitment'):
            self.verified()

    def test_wrong_lease_rejected(self):
        self.evidence['leaseId']=99
        (self.root/'monitor_1_evidence.json').write_text(json.dumps(self.evidence), encoding='utf8')
        with self.assertRaisesRegex(audit.EvidenceAuditError, 'leaseId'):
            self.verified()

    def test_missing_file_rejected(self):
        (self.root/'monitor_1_evidence.json').unlink()
        with self.assertRaisesRegex(audit.EvidenceAuditError, 'missing'):
            self.verified()

    def test_malformed_filename_rejected(self):
        self.run['evidenceFiles']=['../secrets.json']
        (self.root/'run.json').write_text(json.dumps(self.run),encoding='utf8')
        with self.assertRaisesRegex(audit.EvidenceAuditError, 'filename'):
            self.verified()

    def test_evidence_response_mismatch_rejected(self):
        self.evidence['responseHash']='0x'+'ff'*32
        (self.root/'monitor_1_evidence.json').write_text(json.dumps(self.evidence),encoding='utf8')
        with self.assertRaisesRegex(audit.EvidenceAuditError, 'responseHash'):
            self.verified()

    def test_duplicate_filename_rejected(self):
        self.run['evidenceFiles'] *= 2
        self.run['evidenceCommitments']['0x'+'bb'*20] = '0x'+'12'*32
        (self.root/'run.json').write_text(json.dumps(self.run),encoding='utf8')
        with self.assertRaisesRegex(audit.EvidenceAuditError, 'duplicate evidence filename'):
            self.verified()

    def test_chain_inclusion_match(self):
        offline=self.verified()
        class RPC:
            def request(self,*args): raise AssertionError('network access should be mocked')
        with patch.object(audit,'inspect_chain',return_value={
            'blockNumber':18,
            'epoch':{'requestHash':self.run['requestHash'],'responseHash':self.run['responseHash']},
        }), patch.object(audit,'_call',return_value=self.run['evidenceCommitments'][self.monitor]):
            result=audit.verify_on_chain(offline,RPC())
        self.assertTrue(result['onChainCommitmentsVerified'])
        self.assertEqual(result['snapshotBlockNumber'],18)

    def test_chain_inclusion_wrong_hash_rejected(self):
        offline=self.verified()
        with patch.object(audit,'inspect_chain',return_value={
            'blockNumber':18,
            'epoch':{'requestHash':self.run['requestHash'],'responseHash':self.run['responseHash']},
        }), patch.object(audit,'_call',return_value='0x'+'ff'*32):
            with self.assertRaisesRegex(audit.EvidenceAuditError,'chain commitment'):
                audit.verify_on_chain(offline,object())

if __name__=='__main__':unittest.main()
