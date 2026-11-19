#!/usr/bin/env python3
"""Fail-closed *candidate* per-node dashboard action guard.

NOT a deployed dashboard, auth server, signer, or on-chain authorization.
All evidence supplied to authorize() MUST be derived SERVER-SIDE from a
trusted local session, pinned finalized chain, real lease and monitored
measurements. Never deserialize this context from public HTTP JSON.
The smart contracts and local signer MUST enforce every rule independently.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import FrozenSet


ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\\Z")
PUBLIC_READ = frozenset({"read_public_chain", "read_public_market", "read_public_node_status"})
OWNER_READ = frozenset({"read_private_node_metrics"})
LOCAL_ONLY = frozenset({"enable_local_role", "disable_local_role"})
ROLE_ACTIONS = {
    "open_consumer_lease": "consumer",
    "accept_provider_lease": "provider",
    "submit_provider_response": "provider",
    "register_monitor_bond": "monitor",
    "submit_monitor_evidence": "monitor",
    "request_validator_deposit": "validator",
    "withdraw_own_credit": "wallet",
}
# A future node console MUST NOT accept any such operation from HTTP callers,
# including a caller with legitimate local owner credentials.
ABSOLUTE_DENY = frozenset({
    "read_wallet_private_key", "export_validator_mnemonic",
    "get_validator_keystore_password", "change_chain_genesis",
    "set_global_monitor_quorum", "override_monitor_assignment",
    "force_sla_verdict", "move_other_wallet_funds",
    "set_finalized_chain_state", "inject_randomness_seed",
    "access_docker_socket", "execute_host_shell",
    "expose_engine_api", "expose_validator_keymanager",
    "change_other_node_roles",
})


@dataclass(frozen=True, slots=True)
class ServerEvidence:
    # Constructed only by trusted server middleware; never from a client body.
    owner_authenticated: bool = False
    origin_verified: bool = False
    csrf_verified: bool = False
    node_owned_locally: bool = False
    onchain_identity_verified: bool = False
    chain_identity_verified: bool = False
    signer_consent_verified: bool = False
    local_roles_enabled: FrozenSet[str] = frozenset()
    onchain_roles_verified: FrozenSet[str] = frozenset()
    lease_authorized_roles: FrozenSet[str] = frozenset()
    monitor_selected_on_chain: bool = False
    valid_signed_evidence: bool = False
    signer_address: str | None = None
    withdrawal_beneficiary: str | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    permitted: bool
    reason: str


def authorize(action: str, evidence: ServerEvidence) -> Decision:
    """Make a proposed local UI authorization decision; fail closed.

    This does not execute anything, validate actual cryptography, or grant
    eligibility for consensus or smart-contract calls.
    """
    if type(action) is not str or type(evidence) is not ServerEvidence:
        return Decision(False, "malformed_request")
    bool_fields = (
        evidence.owner_authenticated, evidence.origin_verified,
        evidence.csrf_verified, evidence.node_owned_locally,
        evidence.onchain_identity_verified, evidence.chain_identity_verified,
        evidence.signer_consent_verified, evidence.monitor_selected_on_chain,
        evidence.valid_signed_evidence,
    )
    if any(type(flag) is not bool for flag in bool_fields):
        return Decision(False, "malformed_server_evidence")
    if (type(evidence.local_roles_enabled) is not frozenset
            or type(evidence.onchain_roles_verified) is not frozenset
            or type(evidence.lease_authorized_roles) is not frozenset
            or any(type(role) is not str for collection in (
                evidence.local_roles_enabled, evidence.onchain_roles_verified,
                evidence.lease_authorized_roles
            ) for role in collection)):
        return Decision(False, "malformed_server_evidence")
    if action in ABSOLUTE_DENY:
        return Decision(False, "forbidden_dashboard_capability")
    if action in PUBLIC_READ:
        return Decision(True, "public_read_only")
    if action not in OWNER_READ | LOCAL_ONLY | ROLE_ACTIONS.keys():
        return Decision(False, "unknown_action")
    if not (evidence.owner_authenticated and evidence.origin_verified
            and evidence.csrf_verified and evidence.node_owned_locally):
        return Decision(False, "local_owner_session_required")
    if action in OWNER_READ:
        return Decision(True, "owner_read_only")
    if action in LOCAL_ONLY:
        # A local role toggle cannot grant on-chain rights or cancel existing
        # funded obligations. The runtime still needs state-transition checks.
        return Decision(True, "local_preference_only")
    role = ROLE_ACTIONS[action]
    if not evidence.chain_identity_verified or not evidence.onchain_identity_verified:
        return Decision(False, "pinned_chain_and_identity_required")
    if not (role in evidence.local_roles_enabled and role in evidence.onchain_roles_verified):
        return Decision(False, "objective_role_not_verified")
    if action in {"accept_provider_lease", "submit_provider_response",
                  "submit_monitor_evidence"} and role not in evidence.lease_authorized_roles:
        return Decision(False, "not_authorized_for_this_lease")
    if action == "submit_monitor_evidence" and not (
        evidence.monitor_selected_on_chain and evidence.valid_signed_evidence
    ):
        return Decision(False, "no_selected_monitor_or_authenticated_evidence")
    if action == "withdraw_own_credit" and not (
        type(evidence.signer_address) is str
        and type(evidence.withdrawal_beneficiary) is str
        and ADDRESS.fullmatch(evidence.signer_address) is not None
        and ADDRESS.fullmatch(evidence.withdrawal_beneficiary) is not None
        and evidence.signer_address.lower() == evidence.withdrawal_beneficiary.lower()
    ):
        return Decision(False, "withdrawal_beneficiary_must_be_local_signer")
    if not evidence.signer_consent_verified:
        return Decision(False, "fresh_explicit_local_signer_consent_required")
    return Decision(True, "candidate_owner_action_only")
