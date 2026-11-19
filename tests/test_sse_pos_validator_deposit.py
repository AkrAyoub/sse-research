"""Self-service PoS deposit: SSZ root, ABI selector, no admin or real ETH."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_pos_validator_deposit import (
    validate,ssz_deposit_root,DepositError,GWEI,VALUE_WEI,CONTRACT,
)

FORK="0x12345678"

def record():
    pub=bytes([0x11])*48
    wd=bytes([0x01])+bytes([0x22])*31
    sig=bytes([0x33])*96
    return {
        "pubkey":pub.hex(),
        "withdrawal_credentials":wd.hex(),
        "signature":sig.hex(),
        "amount":GWEI,
        "fork_version":FORK[2:],
        "deposit_data_root":ssz_deposit_root(pub,wd,sig,GWEI).hex(),
    }


class IndependentValidatorDepositTests(unittest.TestCase):
    def test_real_deposit_abi_calldata_matches_standard_signature(self):
        d=validate(record(),expected_fork=FORK)
        self.assertEqual(d["chainId"],31339)
        self.assertEqual(d["depositValueTestWei"],32*10**18)
        self.assertEqual(d["depositContract"].lower(),CONTRACT.lower())
        self.assertTrue(d["calldata"].startswith("0x22895118"))
        self.assertTrue(d["sszRootVerified"])
        self.assertFalse(d["cryptographicBlsProofVerified"])
        self.assertFalse(d["validatorActivationVerified"])
        self.assertFalse(d["validatorAcceptedBySSEAdministrator"])
        self.assertFalse(d["stakingTransactionBroadcast"])
        self.assertFalse(d["walletPrivateKeyRead"])

    def test_wrong_root_amount_fork_and_zero_bls_public_key_denied(self):
        base=record()
        mutations=[
            {"amount":GWEI-1},
            {"fork_version":"11223344"},
            {"deposit_data_root":"00"*32},
            {"pubkey":"00"*48},
            {"signature":"22"*96},
            {"withdrawal_credentials":"03"+"22"*31},
            {"pubkey":"zz"*48},
        ]
        for change in mutations:
            with self.subTest(change=change),self.assertRaises(DepositError):
                validate({**base,**change},expected_fork=FORK)

    def test_not_standard_eth_mainnet_currency_purchase(self):
        d=validate(record(),expected_fork=FORK)
        self.assertEqual(d["depositValueTestEth"],32)
        self.assertFalse(d["realEthRequired"])
        self.assertFalse(d["testEthEconomicallySybilResistant"])
        self.assertNotIn("privateKey",d)
        self.assertNotIn("mnemonic",d)

if __name__=="__main__":
    unittest.main()
