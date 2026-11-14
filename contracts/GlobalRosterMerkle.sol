// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Experimental incrementally maintained active-roster Merkle tree.
/// @dev A fixed 20-level heap supports at most 2^20 SIMULTANEOUS active slots.
/// Root is updated on each register and swap-pop exit, in O(20) gas.
/// Not a proof of operator independence or honest key setup.
library GlobalRosterMerkle {
    uint256 internal constant DEPTH = 20;
    uint256 internal constant CAPACITY = 1 << DEPTH;

    error InvalidIndex();

    function leafHash(uint256 index, address account) internal pure returns (bytes32) {
        return account == address(0) ? bytes32(0) :
            keccak256(abi.encodePacked(bytes1(0x01), uint32(index), account));
    }

    function parentHash(bytes32 left, bytes32 right) internal pure returns (bytes32) {
        return left == bytes32(0) && right == bytes32(0)
            ? bytes32(0) : keccak256(abi.encodePacked(left, right));
    }

    /// @notice Write the indexed ACTIVE identity; address(0) erases a slot.
    function write(mapping(uint256 => bytes32) storage tree, uint256 index, address account)
        internal returns (bytes32 newRoot)
    {
        if (index >= CAPACITY) revert InvalidIndex();
        uint256 node = CAPACITY + index;
        tree[node] = leafHash(index, account);
        while (node > 1) {
            uint256 sibling = node ^ 1;
            bytes32 left = (node & 1) == 0 ? tree[node] : tree[sibling];
            bytes32 right = (node & 1) == 0 ? tree[sibling] : tree[node];
            node >>= 1;
            tree[node] = parentHash(left, right);
        }
        return tree[1];
    }

    /// @notice Validate one indexed address against the frozen historical root.
    function verify(bytes32 root, uint256 index, address account, bytes32[] calldata siblings)
        internal pure returns (bool)
    {
        if (index >= CAPACITY || account == address(0) || siblings.length != DEPTH)
            return false;
        bytes32 node = leafHash(index, account);
        for (uint256 level; level < DEPTH; ++level) {
            if (((index >> level) & 1) == 0)
                node = parentHash(node, siblings[level]);
            else
                node = parentHash(siblings[level], node);
        }
        return node == root;
    }
}
