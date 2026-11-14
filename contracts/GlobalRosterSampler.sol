// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Partial Fisher-Yates draw of distinct GLOBAL active-roster indexes.
/// @dev O(k^2), k <= 10, independent of global roster size. Seed quality is
/// inherited from the selected entropy mode; keccak modulo has tiny bias.
/// With a fixed root and no post-request exits, the ordered first 4 valid
/// parties follow a uniform-without-replacement draw under ideal seed output.
library GlobalRosterSampler {
    error InvalidDraw();

    function _at(uint256[] memory keys, uint256[] memory values,
                 uint256 used, uint256 position) private pure returns (uint256)
    {
        for (uint256 i; i < used; ++i) {
            if (keys[i] == position) return values[i];
        }
        return position;
    }

    function draw(uint256 seed, uint256 requestId, uint256 rosterSize, uint256 count)
        internal pure returns (uint256[] memory results)
    {
        if (rosterSize < count || count > 10 || count == 0) revert InvalidDraw();
        results = new uint256[](count);
        uint256[] memory keys = new uint256[](count);
        uint256[] memory values = new uint256[](count);
        uint256 used;
        for (uint256 i; i < count; ++i) {
            uint256 j = i + uint256(keccak256(abi.encode(seed, requestId, i)))
                % (rosterSize - i);
            uint256 selected = _at(keys, values, used, j);
            uint256 displaced = _at(keys, values, used, i);
            bool found;
            for (uint256 k; k < used; ++k) {
                if (keys[k] == j) { values[k] = displaced; found = true; break; }
            }
            if (!found) {
                keys[used] = j;
                values[used] = displaced;
                ++used;
            }
            results[i] = selected;
        }
    }
}
