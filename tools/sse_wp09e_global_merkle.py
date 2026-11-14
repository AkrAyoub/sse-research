"""WP09E experimental global Merkle-roster and bounded partial-shuffle reference.

This is an independent Python test/indexer implementation, not a trusted
source of committee candidates: the EVM verifies every leaf against its
on-chain root and derives every index itself. Root updates use depth 20.
"""
from __future__ import annotations

from eth_abi import encode

try:
    from sse_challenge import keccak256
except ModuleNotFoundError:
    from tools.sse_challenge import keccak256

TREE_DEPTH = 20
CAPACITY = 1 << TREE_DEPTH
DRAW_LIMIT = 10
ZERO = b"\x00" * 32


def leaf_hash(index: int, address: str) -> bytes:
    if type(index) is not int or index < 0 or index >= CAPACITY:
        raise ValueError("out-of-range active roster index")
    if type(address) is not str or not address.startswith("0x") or len(address) != 42:
        raise ValueError("invalid monitor address")
    raw = bytes.fromhex(address[2:])
    if raw == b"\x00" * 20:
        return ZERO
    return keccak256(b"\x01" + index.to_bytes(4, "big") + raw)


def parent(left: bytes, right: bytes) -> bytes:
    if len(left) != 32 or len(right) != 32:
        raise ValueError("parent expects 32-byte children")
    return ZERO if left == ZERO and right == ZERO else keccak256(left + right)


class RosterTree:
    def __init__(self):
        self.nodes: dict[int, bytes] = {}
        self.accounts: list[str] = []

    @property
    def root(self) -> bytes:
        return self.nodes.get(1, ZERO)

    def write(self, index: int, account: str) -> None:
        node = CAPACITY + index
        value = leaf_hash(index, account)
        if value == ZERO:
            self.nodes.pop(node, None)
        else:
            self.nodes[node] = value
        while node > 1:
            sibling = node ^ 1
            left = self.nodes.get(node, ZERO) if (node & 1) == 0 else self.nodes.get(sibling, ZERO)
            right = self.nodes.get(sibling, ZERO) if (node & 1) == 0 else self.nodes.get(node, ZERO)
            node >>= 1
            result = parent(left, right)
            if result == ZERO:
                self.nodes.pop(node, None)
            else:
                self.nodes[node] = result

    def append(self, address: str) -> None:
        if len(self.accounts) == CAPACITY or address.lower() in self.accounts:
            raise ValueError("duplicate or full active roster")
        index = len(self.accounts)
        self.accounts.append(address.lower())
        self.write(index, address)

    def remove(self, address: str) -> None:
        address = address.lower()
        index = self.accounts.index(address)
        last = len(self.accounts) - 1
        if index != last:
            self.accounts[index] = self.accounts[last]
            self.write(index, self.accounts[index])
        self.accounts.pop()
        self.write(last, "0x" + "00" * 20)

    def proof(self, index: int) -> list[bytes]:
        if index < 0 or index >= len(self.accounts):
            raise ValueError("not an active leaf")
        node = CAPACITY + index
        siblings: list[bytes] = []
        for _ in range(TREE_DEPTH):
            siblings.append(self.nodes.get(node ^ 1, ZERO))
            node >>= 1
        return siblings


def verify(root: bytes, index: int, address: str, siblings: list[bytes]) -> bool:
    if type(siblings) is not list or len(siblings) != TREE_DEPTH or index < 0 or index >= CAPACITY:
        return False
    node = leaf_hash(index, address)
    for level, sibling in enumerate(siblings):
        node = parent(node, sibling) if ((index >> level) & 1) == 0 else parent(sibling, node)
    return node == root


def sampled_indexes(seed: int, request_id: int, size: int) -> list[int]:
    if type(size) is not int or size <= 0 or size > CAPACITY:
        raise ValueError("invalid active count")
    if type(seed) is not int or seed < 0 or seed >= 1 << 256 or request_id <= 0:
        raise ValueError("invalid scoped entropy seed")
    count = min(size, DRAW_LIMIT)
    table: dict[int, int] = {}
    chosen: list[int] = []
    for i in range(count):
        j = i + int.from_bytes(keccak256(encode(
            ["uint256", "uint256", "uint256"], [seed, request_id, i]
        )), "big") % (size - i)
        selected = table.get(j, j)
        displaced = table.get(i, i)
        table[j] = displaced
        chosen.append(selected)
    return chosen


def request_commitment(chain_id: int, pool: str, request_id: int,
                       block_number: int, root: bytes, count: int) -> bytes:
    if len(root) != 32 or count <= 0:
        raise ValueError("invalid snapshot")
    return keccak256(encode(
        ["uint256", "address", "uint256", "uint256", "bytes32", "uint256"],
        [chain_id, pool, request_id, block_number, root, count]
    ))
