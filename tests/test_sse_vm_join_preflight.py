"""R5/R6 onboarding preflight tests: mocked RPC, no network and no wallet keys."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sse_vm_join_preflight import (
    JoinPreflightError, address, inspect_vm, require_revision,
    roles, validate_rpc_url,
)
from sse_chain_read import _domain_separator
from sse_challenge import keccak256

COMMIT = "7b0a4def315a598a9626f75bf6596d2d8ede5207"
CONTRACT = "0x" + "12" * 20
WALLET = "0x" + "34" * 20
URL = "https://rpc.example.org/v2/secret-do-not-log"


class FakeRpc:
    def __init__(self, *, chain=11155111, code="0x6001", bad_domain=False,
                 balance=12345, fail_method=None):
        self.chain = chain
        self.code = code
        self.bad_domain = bad_domain
        self.balance = balance
        self.fail_method = fail_method
        self.calls = []

    def __call__(self, url, method, params):
        self.calls.append((url, method, params))
        if method == self.fail_method:
            raise JoinPreflightError("RPC failed closed")
        if method == "eth_chainId":
            return hex(self.chain)
        if method == "eth_getCode":
            return self.code
        if method == "eth_call":
            assert params == [{"to": CONTRACT, "data": "0x" +
                               keccak256(b"domainSeparator()")[:4].hex()}, "latest"]
            return "0x" + ("00" * 32) if self.bad_domain else _domain_separator(self.chain, CONTRACT)
        if method == "eth_getBalance":
            return hex(self.balance)
        raise AssertionError("unknown RPC call")


def check(fake=None, **changes):
    config = dict(checkout=Path("."), expected_revision=COMMIT,
                  role_names="provider,monitor", rpc_url=URL,
                  chain_id=11155111, settlement=CONTRACT, wallet=WALLET,
                  rpc=fake or FakeRpc(), head=lambda p: COMMIT)
    config.update(changes)
    return inspect_vm(**config)


class VmJoinPreflightTests(unittest.TestCase):
    def test_valid_pinned_role_and_read_only_chain_report(self):
        fake = FakeRpc()
        result = check(fake)
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["eip712DomainMatched"])
        self.assertEqual(result["rolesConfigured"], ["provider", "monitor"])
        self.assertEqual(result["walletNativeBalanceWei"], 12345)
        self.assertFalse(result["roleActivated"])
        self.assertFalse(result["walletOwnershipVerified"])
        self.assertFalse(result["networkConsensusFinalityVerified"])
        self.assertEqual([call[1] for call in fake.calls],
                         ["eth_chainId", "eth_getCode", "eth_call", "eth_getBalance"])

    def test_missing_wallet_not_treated_as_funded_or_authenticated(self):
        fake = FakeRpc()
        result = check(fake, wallet=None)
        self.assertIsNone(result["walletNativeBalanceWei"])
        self.assertFalse(result["nativeGasFundingObserved"])
        self.assertFalse(result["walletOwnershipVerified"])
        self.assertNotIn("eth_getBalance", [c[1] for c in fake.calls])

    def test_zero_balance_does_not_grant_gas_capability(self):
        result = check(FakeRpc(balance=0))
        self.assertFalse(result["nativeGasFundingObserved"])

    def test_wrong_commit_rejected_before_network_access(self):
        fake = FakeRpc()
        with self.assertRaises(JoinPreflightError):
            check(fake, head=lambda _: "f" * 40)
        self.assertEqual(fake.calls, [])

    def test_short_commit_not_accepted(self):
        for sha in ("7b0a4de", "HEAD", "../main", "g" * 40):
            with self.subTest(sha=sha), self.assertRaises(JoinPreflightError):
                require_revision(sha)

    def test_wrong_chain_id_fails_closed(self):
        fake = FakeRpc(chain=1)
        with self.assertRaises(JoinPreflightError):
            check(fake)
        self.assertEqual([x[1] for x in fake.calls], ["eth_chainId"])

    def test_missing_or_zero_code_rejected(self):
        for code in ("0x", "0x00", "invalid", "0x0", None):
            with self.subTest(code=code), self.assertRaises(JoinPreflightError):
                check(FakeRpc(code=code))

    def test_wrong_eip712_domain_rejected(self):
        with self.assertRaises(JoinPreflightError):
            check(FakeRpc(bad_domain=True))

    def test_remote_plaintext_http_rejected_before_network(self):
        fake = FakeRpc()
        with self.assertRaises(JoinPreflightError):
            check(fake, rpc_url="http://rpc.example.org:8545")
        self.assertFalse(fake.calls)

    def test_loopback_http_allowed_for_anvil(self):
        self.assertEqual(validate_rpc_url("http://127.0.0.1:8545"), "http://127.0.0.1:8545")

    def test_url_credentials_query_and_fragment_rejected(self):
        for url in ("https://a:b@rpc.example.org/", "https://rpc.example.org/?key=secret",
                    "https://rpc.example.org/#fragment", "file:///etc/passwd",
                    "http://10.0.0.2:8545"):
            with self.subTest(url=url), self.assertRaises(JoinPreflightError):
                validate_rpc_url(url)

    def test_invalid_role_sets_fail_closed(self):
        for role_config in ("", "monitor,monitor", "validator", "monitor,",
                            "provider,executor", "monitor,unknown"):
            with self.subTest(roles=role_config), self.assertRaises(JoinPreflightError):
                roles(role_config)

    def test_provider_consumer_monitor_observer_is_valid(self):
        self.assertEqual(roles("provider,consumer,monitor,observer"),
                         ("provider", "consumer", "monitor", "observer"))

    def test_invalid_wallet_or_contract_rejected_before_rpc(self):
        fake = FakeRpc()
        for updates in ({"wallet": "0x0"}, {"settlement": "0x" + "00" * 20}):
            with self.subTest(updates=updates), self.assertRaises(JoinPreflightError):
                check(fake, **updates)
        self.assertEqual(fake.calls, [])

    def test_rpc_error_does_not_activate_role(self):
        with self.assertRaises(JoinPreflightError):
            check(FakeRpc(fail_method="eth_getCode"))

    def test_anvil_chain_id_is_explicit_and_not_inferred(self):
        fake = FakeRpc(chain=31337)
        result = check(fake, chain_id=31337, rpc_url="http://127.0.0.1:8545")
        self.assertEqual(result["chainId"], 31337)
        self.assertFalse(result["publicTestnetOrMainnetInferred"])


if __name__ == "__main__":
    unittest.main()
