// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;


contract OpenMonitorBondPool {
    struct Candidate {
        uint256 bond;
        uint64 exitRequestedAt;
        bool active;
        bool everRegistered;
    }

    uint256 public immutable minimumBond;
    uint64 public immutable exitDelay;
    mapping(address => Candidate) public candidates;
    address[] private allCandidateAddresses;
    bool private withdrawalEntered;

    event Registered(address indexed account, uint256 bond);
    event BondIncreased(address indexed account, uint256 extra, uint256 total);
    event ExitRequested(address indexed account, uint64 since);
    event ExitCancelled(address indexed account);
    event BondWithdrawn(address indexed account, uint256 bond);

    error InvalidArgument();
    error InvalidState();
    error NothingToWithdraw();
    error TransferFailed();

    constructor(uint256 minBond, uint64 exitDelaySeconds) {
        if (minBond == 0 || exitDelaySeconds == 0) revert InvalidArgument();
        minimumBond = minBond;
        exitDelay = exitDelaySeconds;
    }

    //Anyone can register by depositing the public minimum bond
    function register() external payable {
        Candidate storage c = candidates[msg.sender];
        if (c.bond != 0 || msg.value < minimumBond) revert InvalidArgument();
        if (!c.everRegistered) {
            allCandidateAddresses.push(msg.sender);
            c.everRegistered = true;
        }
        c.bond = msg.value;
        c.exitRequestedAt = 0;
        c.active = true;
        emit Registered(msg.sender, msg.value);
    }

    function topUpBond() external payable {
        Candidate storage c = candidates[msg.sender];
        if (!c.active || msg.value == 0) revert InvalidState();
        c.bond += msg.value;
        emit BondIncreased(msg.sender, msg.value, c.bond);
    }

    function requestExit() external {
        Candidate storage c = candidates[msg.sender];
        if (!c.active || c.bond == 0) revert InvalidState();
        c.active = false;
        c.exitRequestedAt = uint64(block.timestamp);
        emit ExitRequested(msg.sender, c.exitRequestedAt);
    }

    function cancelExit() external {
        Candidate storage c = candidates[msg.sender];
        if (c.active || c.bond == 0 || c.exitRequestedAt == 0) revert InvalidState();
        c.active = true;
        c.exitRequestedAt = 0;
        emit ExitCancelled(msg.sender);
    }

    function withdrawBond() external {
        if (withdrawalEntered) revert InvalidState();
        Candidate storage c = candidates[msg.sender];
        if (c.active || c.bond == 0 || c.exitRequestedAt == 0) revert NothingToWithdraw();
        if (block.timestamp < uint256(c.exitRequestedAt) + exitDelay) revert InvalidState();
        uint256 amount = c.bond;
        c.bond = 0;
        c.exitRequestedAt = 0;
        withdrawalEntered = true;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        withdrawalEntered = false;
        emit BondWithdrawn(msg.sender, amount);
    }

    function isEligible(address candidate) external view returns (bool) {
        Candidate storage c = candidates[candidate];
        return c.active && c.bond >= minimumBond;
    }

    function candidateCount() external view returns (uint256) {
        return allCandidateAddresses.length;
    }

    function candidateAt(uint256 index) external view returns (address) {
        return allCandidateAddresses[index];
    }
}
