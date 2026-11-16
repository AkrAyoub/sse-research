"""R8: ABI event decoding, strict canonical topics, and settlement semantics."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_challenge import keccak256
from sse_event_decoder import LOOKUP, EventDecodeError, decode_sse_event

CONTRACT="0x"+"11"*20


def word(value):
    if type(value) is int:
        return value.to_bytes(32,"big")
    if type(value) is str and value.startswith("0x"):
        raw=bytes.fromhex(value[2:])
        if len(raw) in (20,32):
            return raw.rjust(32,b"\0")
    raise AssertionError("bad test ABI word")


def ev(signature, indexed=(), data=(), emitter=CONTRACT):
    return {"address":emitter,
            "topics":["0x"+keccak256(signature.encode()).hex(),
                      *["0x"+word(v).hex() for v in indexed]],
            "data":"0x"+b"".join(word(v) for v in data).hex(),
            "blockNumber":"0x1","logIndex":"0x0","removed":False}


class DecoderTests(unittest.TestCase):
    def test_unique_event_signatures(self):
        from sse_event_decoder import EVENTS
        self.assertEqual(len(LOOKUP),len(EVENTS))

    def test_marketplace_request(self):
        result=decode_sse_event(ev(
            "Requested(uint256,address,bytes32,bytes32)",
            indexed=(7,"0x"+"12"*20),
            data=("0x"+"31"*32,"0x"+"42"*32)))
        self.assertEqual(result["name"],"Requested")
        self.assertEqual(result["parameters"]["requestId"],7)
        self.assertEqual(result["parameters"]["consumer"],"0x"+"12"*20)
        self.assertFalse(result["chainFinalityVerified"])

    def test_submitted_bid_and_winning_bid_decode(self):
        for name in ("BidSubmitted","BidChosen"):
            with self.subTest(name=name):
                res=decode_sse_event(ev(
                    f"{name}(uint256,uint256,address,uint256)",
                    indexed=(4,2,"0x"+"42"*20),data=(25,)))
                self.assertEqual(res["name"],name)
                self.assertEqual(res["parameters"]["epochFeeWei"],25)
                self.assertEqual(res["parameters"]["provider"],"0x"+"42"*20)

    def test_monitor_failure_not_labeled_truth(self):
        res=decode_sse_event(ev(
            "MonitorVoted(uint256,uint256,address,uint8,bytes32)",
            indexed=(2,1,"0x"+"ab"*20),data=(2,"0x"+"bb"*32)))
        self.assertEqual(res["name"],"MonitorVoted")
        self.assertEqual(res["parameters"]["outcomeLabel"],"Failure")
        self.assertEqual(res["parameters"]["evidenceHash"],"0x"+"bb"*32)
        self.assertEqual(res["interpretation"],"CHAIN_EVENT_ONLY_NOT_SLA_CERTIFICATION")
        self.assertFalse(res["offchainEvidenceVerified"])

    def test_conservative_settlement_bounds_named(self):
        res=decode_sse_event(ev("SettlementUpdated(uint256,uint256,uint256,uint256,uint256)",
                                indexed=(10,0),data=(5,20,15)))
        p=res["parameters"]
        self.assertEqual(p["providerLowerWei"],5)
        self.assertEqual(p["providerUpperWei"],20)
        self.assertEqual(p["unresolvedExposureWei"],15)

    def test_funded_bid_has_no_unindexed_words(self):
        res=decode_sse_event(ev("LeaseFunded(uint256,uint256,address)",
                                indexed=(2,6,"0x"+"33"*20)))
        self.assertEqual(res["parameters"]["leaseId"],6)
        self.assertEqual(res["parameters"]["settlement"],"0x"+"33"*20)

    def test_fixed_array_committee_decryption(self):
        selected=["0x"+format(i,"040x") for i in range(1,5)]
        res=decode_sse_event(ev("CommitteeSelected(uint256,address[4])",
                                indexed=(9,),data=selected))
        self.assertEqual(res["parameters"]["committee"],selected)

    def test_unknown_topic_preserves_raw_event(self):
        raw=ev("SomeFutureEvent(uint256)",indexed=(1,))
        self.assertIsNone(decode_sse_event(raw))

    def test_malformed_known_topics_or_data_refused(self):
        raw=ev("LeaseFunded(uint256,uint256,address)",
               indexed=(1,2,"0x"+"33"*20))
        for mutate in (
            lambda e:e.update(data="0x42"),
            lambda e:e.update(topics=e["topics"][:-1]),
            lambda e:e.update(topics=[e["topics"][0], "0xNOTHEX", *e["topics"][2:]]),
        ):
            with self.subTest(mutate=mutate):
                value={**raw, "topics":list(raw["topics"])}
                mutate(value)
                with self.assertRaises(EventDecodeError):
                    decode_sse_event(value)

    def test_uint8_out_of_range_refused(self):
        with self.assertRaises(EventDecodeError):
            decode_sse_event(ev("MonitoringSealed(uint256,uint256,uint8)",
                                indexed=(1,0),data=(256,)))

    def test_event_layout_disallows_noncanonical_address(self):
        data=ev("CandidateRegistered(address,uint256)",
                indexed=("0x"+"15"*20,),data=(100,))
        data["topics"][1]="0x"+"ff"*32
        with self.assertRaises(EventDecodeError):
            decode_sse_event(data)


if __name__=="__main__": unittest.main()
