"""Adversarial *unit cases*, not observed malicious Internet node attacks."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_node_dashboard_policy import (
    ABSOLUTE_DENY, PUBLIC_READ, ServerEvidence, authorize,
)


class DashboardPolicySecurityTests(unittest.TestCase):
    def owner(self, **overrides):
        trusted = ServerEvidence(
            owner_authenticated=True, origin_verified=True, csrf_verified=True,
            node_owned_locally=True, onchain_identity_verified=True,
            chain_identity_verified=True, signer_consent_verified=True,
            local_roles_enabled=frozenset({
                "consumer", "provider", "monitor", "validator", "wallet"
            }),
            onchain_roles_verified=frozenset({
                "consumer", "provider", "monitor", "validator", "wallet"
            }),
            lease_authorized_roles=frozenset({"provider", "monitor"}),
            monitor_selected_on_chain=True, valid_signed_evidence=True,
            signer_address="0x" + "a" * 40,
            withdrawal_beneficiary="0x" + "a" * 40,
        )
        return replace(trusted, **overrides)

    def test_public_requests_may_only_read_public_data(self):
        for action in PUBLIC_READ:
            self.assertTrue(authorize(action, ServerEvidence()).permitted)
        for action in (
            "read_private_node_metrics", "enable_local_role",
            "submit_monitor_evidence", "withdraw_own_credit",
        ):
            self.assertFalse(authorize(action, ServerEvidence()).permitted)

    def test_known_privileged_attack_actions_never_allowed_even_to_owner(self):
        for action in ABSOLUTE_DENY:
            with self.subTest(action=action):
                self.assertFalse(authorize(action, self.owner()).permitted)

    def test_unknown_mutations_are_denied_not_treated_as_local_preferences(self):
        for action in ("set_quorum", "sudo", "change_block_hash",
                       "post_admin", "", "claim_all_escrow", "promote_validator"):
            self.assertFalse(authorize(action, self.owner()).permitted)

    def test_owner_session_must_be_origin_csrf_and_locality_verified(self):
        for attr in ("owner_authenticated", "origin_verified",
                     "csrf_verified", "node_owned_locally"):
            with self.subTest(attr=attr):
                self.assertFalse(
                    authorize("enable_local_role", self.owner(**{attr: False})).permitted
                )
                self.assertFalse(
                    authorize("submit_monitor_evidence", self.owner(**{attr: False})).permitted
                )

    def test_browser_role_toggle_does_not_grant_onchain_roles(self):
        unverified = self.owner(
            local_roles_enabled=frozenset({"monitor"}),
            onchain_roles_verified=frozenset(),
        )
        self.assertTrue(authorize("enable_local_role", unverified).permitted)
        self.assertFalse(authorize("submit_monitor_evidence", unverified).permitted)

    def test_monitor_cannot_vote_for_other_lease_or_fake_observation(self):
        for props in (
            {"lease_authorized_roles": frozenset()},
            {"monitor_selected_on_chain": False},
            {"valid_signed_evidence": False},
            {"onchain_roles_verified": frozenset()},
        ):
            with self.subTest(props=props):
                self.assertFalse(
                    authorize("submit_monitor_evidence", self.owner(**props)).permitted
                )

    def test_monitor_vote_requires_owner_key_consent_even_with_evidence(self):
        e = self.owner(signer_consent_verified=False)
        self.assertFalse(authorize("submit_monitor_evidence", e).permitted)

    def test_wallet_withdrawal_is_beneficiary_bound_and_requires_consent(self):
        self.assertTrue(authorize("withdraw_own_credit", self.owner()).permitted)
        self.assertFalse(authorize("withdraw_own_credit", self.owner(
            withdrawal_beneficiary="0x" + "b" * 40,
        )).permitted)
        self.assertFalse(authorize("withdraw_own_credit", self.owner(
            signer_consent_verified=False,
        )).permitted)

    def test_sse_provider_request_must_be_real_selected_lease_role(self):
        self.assertTrue(authorize("submit_provider_response", self.owner()).permitted)
        self.assertFalse(authorize("submit_provider_response", self.owner(
            lease_authorized_roles=frozenset(),
        )).permitted)

    def test_chain_mismatch_fails_for_every_money_action(self):
        for action in ("open_consumer_lease", "accept_provider_lease",
                       "submit_provider_response", "register_monitor_bond",
                       "submit_monitor_evidence", "request_validator_deposit",
                       "withdraw_own_credit"):
            with self.subTest(action=action):
                self.assertFalse(authorize(action, self.owner(
                    chain_identity_verified=False,
                )).permitted)

    def test_multiple_roles_allowed_without_fixed_network_role_count(self):
        e = self.owner()
        self.assertTrue(authorize("open_consumer_lease", e).permitted)
        self.assertTrue(authorize("accept_provider_lease", e).permitted)
        self.assertTrue(authorize("submit_monitor_evidence", e).permitted)
        self.assertTrue(authorize("request_validator_deposit", e).permitted)
        # Each role in a distinct lease needs its own separate chain check.

    def test_malformed_context_not_accepted_from_client_json(self):
        self.assertFalse(authorize("withdraw_own_credit", {
            "owner_authenticated": True, "csrf_verified": True
        }).permitted)
        self.assertFalse(authorize(None, self.owner()).permitted)

    def test_raw_http_worker_is_not_a_public_owner_console(self):
        worker = (ROOT / "services/provider-agent/compute_http_service.py").read_text()
        runner = (ROOT / "tools/sse_docker_sla_runner.py").read_text()
        gateway = (ROOT / "services/provider-agent/direct_work_service.py").read_text()
        self.assertIn("('0.0.0.0', port)", worker)
        self.assertIn('"--publish", f"127.0.0.1:{port}:8877"', runner)
        self.assertIn('ThreadingHTTPServer(("127.0.0.1", port), Handler)', gateway)
        self.assertIn('authenticate_request(payload, state, policy, endpoint, signer)', gateway)
        self.assertIn('pin_block_hash=True', gateway)
        self.assertIn('"--cap-drop", "ALL"', runner)
        self.assertIn('"--security-opt", "no-new-privileges:true"', runner)


if __name__ == "__main__":
    unittest.main()
