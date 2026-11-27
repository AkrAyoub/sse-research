#!/usr/bin/env python3
"""Merkle-Patricia proof verification for eth_getProof (explorer support).

SOURCE-ONLY (2026-11-27): never executed. Pure Python, no dependencies beyond
the repo keccak helper. Verifies ONLY what the node returned: the account
proof against the block's stateRoot and each storage proof against the
account's storageRoot. It never invents sibling nodes or a full tree; the
returned `path` lists exactly the proof nodes (for visualization).
Absence proofs (value None) are reported as "proven absent", which is
distinct from "unavailable" (node refused / pruned state).
"""
from sse_challenge import keccak256

EMPTY_TRIE_ROOT = bytes.fromhex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421")
EMPTY_CODE_HASH = bytes.fromhex("c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")


class ProofError(ValueError):
    pass


# ------------------------------------------------------------------- RLP
def rlp_decode(data):
    item, rest = _rlp(data, 0)
    if rest != len(data):
        raise ProofError("trailing RLP bytes")
    return item


def _len(data, start, n):
    if start + n > len(data):
        raise ProofError("truncated RLP length")
    if n == 0 or data[start] == 0:
        raise ProofError("non-canonical RLP length")
    return int.from_bytes(data[start:start + n], "big")


def _rlp(data, i):
    if i >= len(data):
        raise ProofError("truncated RLP")
    b = data[i]
    if b < 0x80:
        return data[i:i + 1], i + 1
    if b < 0xb8:
        n = b - 0x80
        end = i + 1 + n
        if end > len(data) or (n == 1 and data[i + 1] < 0x80):
            raise ProofError("bad short string")
        return data[i + 1:end], end
    if b < 0xc0:
        ln = b - 0xb7
        n = _len(data, i + 1, ln)
        if n < 56:
            raise ProofError("non-canonical long string")
        s = i + 1 + ln
        if s + n > len(data):
            raise ProofError("truncated long string")
        return data[s:s + n], s + n
    if b < 0xf8:
        n = b - 0xc0
        s = i + 1
    else:
        ln = b - 0xf7
        n = _len(data, i + 1, ln)
        if n < 56:
            raise ProofError("non-canonical long list")
        s = i + 1 + ln
    end = s + n
    if end > len(data):
        raise ProofError("truncated list")
    items, j = [], s
    while j < end:
        it, j = _rlp(data, j)
        items.append(it)
    if j != end:
        raise ProofError("list length mismatch")
    return items, end


def rlp_encode(x):
    if isinstance(x, (bytes, bytearray)):
        x = bytes(x)
        if len(x) == 1 and x[0] < 0x80:
            return x
        return _prefix(len(x), 0x80) + x
    body = b"".join(rlp_encode(i) for i in x)
    return _prefix(len(body), 0xc0) + body


def _prefix(n, off):
    if n < 56:
        return bytes([off + n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([off + 55 + len(b)]) + b


# ------------------------------------------------------------------- MPT
def _nibbles(b):
    out = []
    for x in b:
        out += [x >> 4, x & 15]
    return out


def _hp_decode(path):
    n = _nibbles(path)
    if not n:
        raise ProofError("empty hex-prefix path")
    flag = n[0]
    if flag > 3:
        raise ProofError("bad hex-prefix flag")
    leaf = flag >= 2
    if not flag & 1 and (len(n) < 2 or n[1] != 0):
        raise ProofError("invalid even hex-prefix padding")
    rest = n[1:] if flag & 1 else n[2:]
    return rest, leaf


def verify_mpt(root, key, proof):
    """Return (value or None, path) proving key under root using `proof`
    (list of RLP node bytes as returned by eth_getProof)."""
    nodes = {keccak256(p): p for p in proof}
    target = _nibbles(keccak256(key))
    expected = bytes(root)
    path, pos, inline = [], 0, None
    if expected == EMPTY_TRIE_ROOT and not proof:
        return None, path
    for _ in range(65):
        if inline is not None:
            node, raw = inline, rlp_encode(inline)
            inline = None
        else:
            raw = nodes.get(expected)
            if raw is None:
                raise ProofError("proof missing node " + expected.hex())
            node = rlp_decode(raw)
        path.append({"hash": "0x" + keccak256(raw).hex(), "kind": None, "depth": pos})
        if not isinstance(node, list):
            raise ProofError("node is not a list")
        if len(node) == 17:
            path[-1]["kind"] = "branch"
            if pos == len(target):
                return (node[16] or None), path
            child = node[target[pos]]
            pos += 1
            if child == b"":
                return None, path  # proven absent
        elif len(node) == 2:
            rest, leaf = _hp_decode(node[0])
            path[-1]["kind"] = "leaf" if leaf else "extension"
            if target[pos:pos + len(rest)] != rest:
                return None, path  # divergent path: proven absent
            pos += len(rest)
            if not leaf and not rest:
                raise ProofError("empty extension")
            if leaf:
                if pos != len(target):
                    raise ProofError("leaf before end of key")
                return node[1], path
            child = node[1]
        else:
            raise ProofError("invalid node arity")
        if isinstance(child, list):
            if len(rlp_encode(child)) >= 32:
                raise ProofError("oversized embedded node")
            inline = child
        elif len(child) == 32:
            expected = child
        else:
            raise ProofError("invalid child reference")
    raise ProofError("proof exceeds secure trie depth")


def _hx(s):
    if not isinstance(s, str) or not s.startswith("0x"):
        raise ProofError("hex string required")
    h = s[2:]
    return bytes.fromhex(h if len(h) % 2 == 0 else "0" + h)


def _int_bytes(s):
    v = int(s, 16)
    return b"" if v == 0 else v.to_bytes((v.bit_length() + 7) // 8, "big")


def verify_get_proof(state_root_hex, response):
    """Verify an eth_getProof response. Returns a report with per-item status."""
    state_root = _hx(state_root_hex)
    address = _hx(response["address"])
    if len(state_root) != 32 or len(address) != 20:
        raise ProofError("invalid state root or account address length")
    value, apath = verify_mpt(state_root, address, [_hx(p) for p in response["accountProof"]])
    report = {"address": response["address"].lower(), "stateRoot": state_root_hex, "accountPath": apath,
              "storage": []}
    claimed = [_int_bytes(response["nonce"]), _int_bytes(response["balance"]), _hx(response["storageHash"]),
               _hx(response["codeHash"])]
    if value is None:
        empty = claimed == [b"", b"", EMPTY_TRIE_ROOT, EMPTY_CODE_HASH]
        if not empty:
            raise ProofError("account proven absent but node claims non-empty account")
        report["account"] = "proven-absent"
    else:
        if rlp_decode(value) != claimed:
            raise ProofError("account fields do not match proven leaf")
        report["account"] = "verified"
    storage_root = claimed[2]
    for sp in response.get("storageProof", []):
        slot = _hx(sp["key"]).rjust(32, b"\x00")
        v, spath = verify_mpt(storage_root, slot, [_hx(p) for p in sp["proof"]])
        proven = 0 if v is None else int.from_bytes(rlp_decode(v), "big")
        if proven != int(sp["value"], 16):
            raise ProofError("storage value mismatch for slot " + sp["key"])
        report["storage"].append({"slot": "0x" + slot.hex(), "value": hex(proven),
                                  "status": "proven-zero-absent" if v is None else "verified", "path": spath})
    return report
