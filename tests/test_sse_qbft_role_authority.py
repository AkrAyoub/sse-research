"""Offline actual-QBFT-member observation from two read-only RPC views."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_role_authority import (
    validator_membership,validator_address,ValidatorAuthorityError,
)

# Known secp256k1 generator: a real on-curve P2P identity.
PUB1=("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
      "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8")
GEN="0x"+"ab"*32
HEAD="0x"+"bc"*32
HOSTS=["http://127.0.0.1:18545","http://127.0.0.1:18546"]
ADDR="0x"+"0f"*20
OTHER=["0x"+f"{i:02x}"*20 for i in range(1,5)]


def fake(url,method,params):
    if method=="eth_chainId":return "0x7a6a"
    if method=="eth_blockNumber":return "0xc"
    if method=="eth_getBlockByNumber":
        if params[0]=="0x0":return {"hash":GEN}
        return {"hash":HEAD}
    if method=="qbft_getValidatorsByBlockNumber":
        return [validator_address(PUB1)]+OTHER
    raise AssertionError("unknown method "+method)


class AuthorityTests(unittest.TestCase):
    def test_curve_modulus_is_defined_and_known_generator_valid(self):
        import sse_qbft_role_authority as module
        self.assertEqual(module.SECP256K1_P,
                         0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F)
        self.assertEqual(validator_address(PUB1),
                         "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf")
        with self.assertRaises(ValidatorAuthorityError):
            validator_address("a" * 128)

    def test_verified_active_membership_not_stake(self):
        d=validator_membership(HOSTS,chain_id=31338,genesis_hash=GEN,
                               enode_public_key=PUB1,call=fake)
        self.assertTrue(d["activeQBFTValidatorObserved"])
        self.assertEqual(d["status"],"ACTIVE_QBFT_SET_MEMBER")
        self.assertEqual(d["validatorSetSize"],5)
        self.assertFalse(d["proofOfStakeEligibilityVerified"])
        self.assertFalse(d["permissionlessConsensusEstablished"])
        self.assertFalse(d["ethereumTransactionsSent"])
        self.assertFalse(d["physicalHostIndependenceProved"])

    def test_candidate_is_not_activated_by_request(self):
        def no_candidate(url,method,params):
            if method=="qbft_getValidatorsByBlockNumber":
                return OTHER
            return fake(url,method,params)
        d=validator_membership(HOSTS,chain_id=31338,genesis_hash=GEN,
                               enode_public_key=PUB1,call=no_candidate)
        self.assertFalse(d["activeQBFTValidatorObserved"])
        self.assertEqual(d["status"],"CANDIDATE_NOT_ACTIVE")

    def test_inconsistent_fork_and_set_rejected(self):
        def fork(url,method,params):
            if url==HOSTS[1] and method=="eth_getBlockByNumber" and params[0]=="0xc":
                return {"hash":"0x"+"dd"*32}
            return fake(url,method,params)
        with self.assertRaises(ValidatorAuthorityError):
            validator_membership(HOSTS,chain_id=31338,genesis_hash=GEN,
                                 enode_public_key=PUB1,call=fork)
        def bad_members(url,method,params):
            if url==HOSTS[1] and method=="qbft_getValidatorsByBlockNumber":
                return OTHER
            return fake(url,method,params)
        with self.assertRaises(ValidatorAuthorityError):
            validator_membership(HOSTS,chain_id=31338,genesis_hash=GEN,
                                 enode_public_key=PUB1,call=bad_members)

    def test_refuse_single_or_remote_cleartext_rpc(self):
        with self.assertRaises(ValidatorAuthorityError):
            validator_membership(HOSTS[:1],chain_id=31338,genesis_hash=GEN,
                                 enode_public_key=PUB1,call=fake)
        with self.assertRaises(Exception):
            validator_membership(["http://192.168.1.20:8545",HOSTS[0]],
                                 chain_id=31338,genesis_hash=GEN,
                                 enode_public_key=PUB1,call=fake)

    def test_wrong_chain_genesis_and_fake_p2p_pub_refused(self):
        for kwargs in [
            {"chain_id":31337,"genesis_hash":GEN,"enode_public_key":PUB1},
            {"chain_id":31338,"genesis_hash":"0x"+"00"*32,"enode_public_key":PUB1},
            {"chain_id":31338,"genesis_hash":GEN,"enode_public_key":"a"*128},
        ]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValidatorAuthorityError):
                validator_membership(HOSTS,call=fake,**kwargs)

if __name__=="__main__":
    unittest.main()
