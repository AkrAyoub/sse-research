#!/usr/bin/env python3
"""VM-local SSE role provisioning. No remote wallet copying or implicit spending.

Commands:
  init             Create encrypted, owner-only wallets for selected roles.
  status           Inspect the local role manifest and optional on-chain state.
  lab-fund         Explicitly fund wallets from Anvil's public TEST account.
  register-monitor Preview or explicitly sign/broadcast the monitor bond.

The original portal-generated hostname is used as nodeId; never rename VMs.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import stat
import sys
import time

from sse_challenge import keccak256
from sse_node_marketplace import RPC, NodeTxError, execute, make_plan
from sse_node_role_policy import RolePolicyError, role_manifest

DEV_FUNDER = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"
DEV_CHAIN_ID = 31337
DEFAULT_BALANCE_WEI = 10**16  # 0.01 test ETH


class SetupError(ValueError):
    """Unsafe configuration, duplicate provisioning, or chain mismatch."""


def wallet_directory() -> Path:
    return Path.home() / ".local" / "share" / "sse-lab"


def _private_dir(directory: Path, *, create: bool = False) -> None:
    if create and not directory.exists() and not directory.is_symlink():
        directory.mkdir(parents=True, mode=0o700)
    if directory.is_symlink():
        raise SetupError("wallet directory may not be a symlink")
    try:
        info = directory.stat()
    except FileNotFoundError as exc:
        raise SetupError("wallet directory absent; run init first") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise SetupError("wallet directory must be owned by caller and mode 0700")


def _private_file(path: Path) -> None:
    if path.is_symlink():
        raise SetupError("wallet or manifest may not be a symlink")
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise SetupError("wallet or manifest must be owned by caller and mode 0600")


def _exclusive_json(path: Path, obj: dict) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(obj, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except BaseException:
        # Preserve existing files for manual recovery; never overwrite keys.
        raise


def init_wallets(directory: Path, hostname: str, roles: str,
                 password: str, confirmation: str) -> dict:
    if password != confirmation or len(password) < 16:
        raise SetupError("passphrase must match and contain at least 16 characters")
    selected = [item.strip() for item in roles.split(",")]
    manifest = {"schema": "sse-node-roles-v1", "nodeId": hostname,
                "roles": selected, "wallets": {}}
    # Validate role names and hostname BEFORE creating any files.
    for i, role in enumerate(selected):
        if role != "observer":
            manifest["wallets"][role] = "0x" + format(i + 1, "040x")
    role_manifest(manifest)

    _private_dir(directory, create=True)
    targets = [directory / (role + ".json") for role in selected if role != "observer"]
    targets.append(directory / "roles.json")
    if any(target.exists() or target.is_symlink() for target in targets):
        raise SetupError("existing wallet/manifest found; refusing to overwrite")

    from eth_account import Account  # Only required for wallet creation/signing.
    public_wallets = {}
    for role in selected:
        if role == "observer":
            continue
        wallet = Account.create(os.urandom(32))
        public_wallets[role] = wallet.address
        encrypted = Account.encrypt(wallet.key, password)
        _exclusive_json(directory / (role + ".json"), encrypted)

    manifest["wallets"] = public_wallets
    role_manifest(manifest)
    _exclusive_json(directory / "roles.json", manifest)
    return {"result": "LOCAL_WALLETS_ENCRYPTED", "hostname": hostname,
            "roles": selected, "wallets": public_wallets,
            "chainTransactionsSent": False, "monitorBondRegistered": False}


def load_manifest(directory: Path, *, require_this_vm: bool = True) -> dict:
    _private_dir(directory)
    path = directory / "roles.json"
    _private_file(path)
    obj = role_manifest(json.loads(path.read_text(encoding="utf-8")))
    if require_this_vm and obj["nodeId"] != os.uname().nodename:
        raise SetupError("manifest hostname differs from this VM; refusing copied identity")
    for role in obj["wallets"]:
        _private_file(directory / (role + ".json"))
    return obj


def _selector(signature: str) -> str:
    return "0x" + keccak256(signature.encode("ascii"))[:4].hex()


def _call_uint(rpc: RPC, contract: str, signature: str,
               address: str | None = None) -> int:
    data = _selector(signature)
    if address is not None:
        data += int(address, 16).to_bytes(32, "big").hex()
    answer = rpc.request("eth_call", [{"to": contract, "data": data}, "latest"])
    if not isinstance(answer, str) or not answer.startswith("0x") or len(answer) < 66:
        raise SetupError("malformed contract response")
    return int(answer[2:66], 16)


def chain_status(manifest: dict, rpc: RPC, chain_id: int,
                 pool: str | None = None) -> dict:
    if int(rpc.request("eth_chainId", []), 16) != chain_id:
        raise SetupError("wrong chain ID")
    balances = {}
    for role, addr in manifest["wallets"].items():
        balances[role] = int(rpc.request("eth_getBalance", [addr, "latest"]), 16)
    out = {"chainId": chain_id, "balancesWei": balances}
    if "monitor" in manifest["wallets"] and pool is not None:
        if int(rpc.request("eth_getCode", [pool, "latest"]), 16) == 0:
            raise SetupError("committee contract not deployed")
        addr = manifest["wallets"]["monitor"]
        candidate = rpc.request("eth_call", [{
            "to": pool, "data": _selector("candidates(address)")
            + int(addr, 16).to_bytes(32, "big").hex()
        }, "latest"])
        if (not isinstance(candidate, str) or not candidate.startswith("0x")
                or len(candidate) < 2 + 6 * 64):
            raise SetupError("invalid candidate record")
        words = [int(candidate[2 + i*64:2 + (i+1)*64], 16) for i in range(6)]
        out["monitor"] = {
            "address": addr, "bondWei": words[0], "active": bool(words[4]),
            "minimumBondWei": _call_uint(rpc, pool, "minimumBond()"),
            "candidateCount": _call_uint(rpc, pool, "candidateCount()")
        }
    return out


def fund_lab(manifest: dict, rpc: RPC, chain_id: int, min_balance: int,
             execute_funding: bool) -> dict:
    if chain_id != DEV_CHAIN_ID or int(rpc.request("eth_chainId", []), 16) != DEV_CHAIN_ID:
        raise SetupError("lab funding allowed only on chain 31337")
    if min_balance <= 0 or min_balance > 10**18:
        raise SetupError("lab minimum balance must be in (0, 1 ETH]")
    unlocked = {value.lower() for value in rpc.request("eth_accounts", [])}
    if DEV_FUNDER not in unlocked:
        raise SetupError("known public Anvil dev funder is not unlocked")
    transfers = []
    for role, account in manifest["wallets"].items():
        balance = int(rpc.request("eth_getBalance", [account, "latest"]), 16)
        missing = max(0, min_balance - balance)
        entry = {"role": role, "address": account, "balanceWei": balance,
                 "fundingWei": missing, "sent": False}
        if execute_funding and missing:
            tx = rpc.request("eth_sendTransaction", [{
                "from": DEV_FUNDER, "to": account, "value": hex(missing)
            }])
            if not isinstance(tx, str) or not tx.startswith("0x") or len(tx) != 66:
                raise SetupError("invalid funding transaction hash")
            entry["transactionHash"] = tx
            for _ in range(30):
                receipt = rpc.request("eth_getTransactionReceipt", [tx])
                if receipt is not None:
                    if int(receipt.get("status", "0x0"), 16) != 1:
                        raise SetupError("development funding transaction reverted")
                    entry["sent"] = True
                    break
                time.sleep(0.5)
            if not entry["sent"]:
                raise SetupError("funding tx submitted but receipt not observed; recheck balances")
        transfers.append(entry)
    return {"result": "LAB_FUNDED" if execute_funding else "LAB_FUNDING_PREVIEW",
            "chainId": DEV_CHAIN_ID, "transfers": transfers,
            "ethereumTransactionsSent": any(item["sent"] for item in transfers)}


def register_monitor(manifest: dict, directory: Path, rpc: RPC, *,
                     chain_id: int, board: str, settlement: str, pool: str,
                     bond_wei: int, max_total_wei: int, broadcast: bool,
                     password: str | None = None) -> dict:
    if "monitor" not in manifest["wallets"]:
        raise SetupError("VM has no locally configured monitor role")
    state = chain_status(manifest, rpc, chain_id, pool)["monitor"]
    if state["active"] or state["bondWei"] != 0:
        raise SetupError("monitor already registered or has locked bond")
    if bond_wei < state["minimumBondWei"]:
        raise SetupError("bond below on-chain minimum")
    plan = make_plan("monitor-register", "monitor", chain_id=chain_id,
                     board=board, settlement=settlement, pool=pool,
                     params={"bondWei": bond_wei})
    if not broadcast:
        return {"result": "MONITOR_REGISTRATION_PREVIEW",
                "monitorAddress": manifest["wallets"]["monitor"],
                "minimumBondWei": state["minimumBondWei"], "plan": plan.public()}
    if max_total_wei <= bond_wei:
        raise SetupError("max-total-wei must cover bond plus gas")
    if password is None:
        raise SetupError("passphrase required for registration")
    from eth_account import Account
    file = directory / "monitor.json"
    _private_file(file)
    try:
        signer = Account.from_key(Account.decrypt(
            json.loads(file.read_text(encoding="utf-8")), password))
    except (ValueError, KeyError) as exc:
        raise SetupError("monitor wallet unlock failed") from exc
    if signer.address.lower() != manifest["wallets"]["monitor"].lower():
        raise SetupError("encrypted monitor key does not match this VM's role manifest")
    receipt = execute(rpc, plan, signer, max_total_wei=max_total_wei)
    return {"result": "MONITOR_REGISTRATION_SUBMITTED",
            "monitorAddress": signer.address, **receipt}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SSE VM-local encrypted role operator")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="create role keystores; never overwrite")
    init.add_argument("--roles", required=True)
    init.add_argument("--node-id", default=os.uname().nodename,
                      help="actual portal-generated hostname, not an alias")
    status = sub.add_parser("status", help="read-only local and optional chain status")
    status.add_argument("--rpc-url")
    status.add_argument("--chain-id", type=int)
    status.add_argument("--pool")
    fund = sub.add_parser("lab-fund", help="Anvil 31337 ONLY, public dev funds")
    fund.add_argument("--rpc-url", required=True)
    fund.add_argument("--chain-id", type=int, required=True)
    fund.add_argument("--min-balance-wei", type=int, default=DEFAULT_BALANCE_WEI)
    fund.add_argument("--execute", action="store_true")
    reg = sub.add_parser("register-monitor", help="register local monitor wallet")
    reg.add_argument("--rpc-url", required=True)
    reg.add_argument("--chain-id", type=int, required=True)
    reg.add_argument("--board", required=True)
    reg.add_argument("--settlement", required=True)
    reg.add_argument("--pool", required=True)
    reg.add_argument("--bond-wei", type=int, required=True)
    reg.add_argument("--max-total-wei", type=int, default=0)
    reg.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        directory = wallet_directory()
        if args.action == "init":
            pwd = getpass("New encryption passphrase (16+ characters): ")
            confirm = getpass("Repeat passphrase: ")
            result = init_wallets(directory, args.node_id, args.roles, pwd, confirm)
        else:
            manifest = load_manifest(directory)
            if args.action == "status":
                result = {"result": "LOCAL_ROLE_STATUS", "manifest": manifest}
                if args.rpc_url or args.chain_id or args.pool:
                    if not args.rpc_url or not args.chain_id:
                        raise SetupError("status requires both RPC URL and chain ID")
                    result["chain"] = chain_status(manifest, RPC(args.rpc_url),
                                                  args.chain_id, args.pool)
            elif args.action == "lab-fund":
                result = fund_lab(manifest, RPC(args.rpc_url), args.chain_id,
                                  args.min_balance_wei, args.execute)
            else:
                pwd = getpass("Monitor wallet passphrase: ") if args.execute else None
                result = register_monitor(
                    manifest, directory, RPC(args.rpc_url), chain_id=args.chain_id,
                    board=args.board, settlement=args.settlement, pool=args.pool,
                    bond_wei=args.bond_wei, max_total_wei=args.max_total_wei,
                    broadcast=args.execute, password=pwd)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (SetupError, NodeTxError, RolePolicyError, OSError, ValueError,
            TypeError, KeyError, json.JSONDecodeError) as exc:
        print("SSE_VM_ROLE_SETUP_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
