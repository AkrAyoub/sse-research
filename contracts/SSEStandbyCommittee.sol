// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AdaptiveMonitorQuorum} from "./AdaptiveMonitorQuorum.sol";

/// @notice Candidate pre-service committee lifecycle; not wired to live V3.
/// @dev Only the integrating market may initialize a verified ordered draw.
/// The market must reserve collateral/capacity for every supplied candidate,
/// and release it on cancellation or lease closure. This contract holds no funds.
/// A reserve confirms only after promotion. No changes after readiness.
contract SSEStandbyCommittee {
    enum Phase { None, Confirming, Ready, Expired }
    struct Assignment {
        Phase phase;
        uint64 deadline;
        uint64 roundSeconds;
        uint256 quorum;
        uint256 confirmedCount;
        uint256 nextStandby;
        address[] primary;
        address[] standby;
    }
    address public immutable market;
    mapping(uint256 => Assignment) private assignments;
    mapping(uint256 => mapping(address => bool)) public activeSeat;
    mapping(uint256 => mapping(address => bool)) public confirmed;
    error Unauthorized();
    error InvalidPolicy();
    error InvalidPhase();
    event Initialized(uint256 indexed leaseId,uint256 seats,uint256 quorum,uint256 reserves,uint64 deadline);
    event Confirmed(uint256 indexed leaseId,address indexed monitor);
    event Promoted(uint256 indexed leaseId,address indexed removed,address indexed replacement);
    event Ready(uint256 indexed leaseId);
    event Expired(uint256 indexed leaseId);
    constructor(address market_) {
        if(market_==address(0)) revert InvalidPolicy();
        market=market_;
    }
    function initialize(uint256 leaseId,address consumer,address provider,
        address[] calldata ordered,uint256 seats,uint64 roundSeconds) external {
        if(msg.sender!=market) revert Unauthorized();
        if(leaseId==0 || assignments[leaseId].phase!=Phase.None ||
            consumer==address(0) || provider==address(0) || consumer==provider ||
            seats<4 || seats>ordered.length || ordered.length>64 ||
            roundSeconds<60 || roundSeconds>1 days) revert InvalidPolicy();
        Assignment storage a=assignments[leaseId];
        a.phase=Phase.Confirming;
        a.roundSeconds=roundSeconds;
        a.deadline=deadlineAfter(roundSeconds);
        a.quorum=AdaptiveMonitorQuorum.strictTwoThirdsQuorum(seats);
        for(uint256 i=0;i<ordered.length;++i){
            address m=ordered[i];
            if(m==address(0)||m==consumer||m==provider) revert InvalidPolicy();
            for(uint256 j=0;j<i;++j) if(ordered[j]==m) revert InvalidPolicy();
            if(i<seats){
                a.primary.push(m);
                activeSeat[leaseId][m]=true;
            }else a.standby.push(m);
        }
        emit Initialized(leaseId,seats,a.quorum,a.standby.length,a.deadline);
    }
    function deadlineAfter(uint64 seconds_) private view returns(uint64) {
        uint256 end=block.timestamp+seconds_;
        if(end>type(uint64).max) revert InvalidPolicy();
        return uint64(end);
    }
    function confirm(uint256 leaseId) external {
        Assignment storage a=assignments[leaseId];
        if(a.phase!=Phase.Confirming || block.timestamp>a.deadline) revert InvalidPhase();
        if(!activeSeat[leaseId][msg.sender]) revert Unauthorized();
        if(confirmed[leaseId][msg.sender]) revert InvalidPhase();
        confirmed[leaseId][msg.sender]=true;
        ++a.confirmedCount;
        emit Confirmed(leaseId,msg.sender);
        if(a.confirmedCount==a.primary.length){
            a.phase=Phase.Ready;
            emit Ready(leaseId);
        }
    }
    /// @notice Permissionless deterministic advancement, no chosen seat or seed.
    /// @dev Replace all missing seats in index order or expire atomically.
    /// Each successful round consumes at least one reserve, bounding rounds.
    function advance(uint256 leaseId) external {
        Assignment storage a=assignments[leaseId];
        if(a.phase!=Phase.Confirming || block.timestamp<=a.deadline) revert InvalidPhase();
        uint256 missing=a.primary.length-a.confirmedCount;
        if(missing>a.standby.length-a.nextStandby){
            a.phase=Phase.Expired;
            for(uint256 i=0;i<a.primary.length;++i){
                activeSeat[leaseId][a.primary[i]]=false;
                confirmed[leaseId][a.primary[i]]=false;
            }
            a.confirmedCount=0;
            emit Expired(leaseId);
            return;
        }
        for(uint256 i=0;i<a.primary.length;++i){
            address old=a.primary[i];
            if(confirmed[leaseId][old]) continue;
            address replacement=a.standby[a.nextStandby++];
            activeSeat[leaseId][old]=false;
            activeSeat[leaseId][replacement]=true;
            a.primary[i]=replacement;
            emit Promoted(leaseId,old,replacement);
        }
        a.deadline=deadlineAfter(a.roundSeconds);
    }
    /// @notice Market-only cancellation before market activation, including a
    /// ready but not yet activated assignment. Clears seats; no funds held here.
    /// The integrating market must never call this on an activated lease.
    /// @dev Added 2026-11-27 (source-only, not compiled/tested). R429 tests
    /// covered the contract before this addition.
    function cancel(uint256 leaseId) external {
        if(msg.sender!=market) revert Unauthorized();
        Assignment storage a=assignments[leaseId];
        if(a.phase!=Phase.Confirming && a.phase!=Phase.Ready) revert InvalidPhase();
        a.phase=Phase.Expired;
        for(uint256 i=0;i<a.primary.length;++i){
            activeSeat[leaseId][a.primary[i]]=false;
            confirmed[leaseId][a.primary[i]]=false;
        }
        a.confirmedCount=0;
        emit Expired(leaseId);
    }
    function assignment(uint256 leaseId) external view returns(Assignment memory){
        return assignments[leaseId];
    }
    /// @notice Only a ready committee may be passed to a future vote ledger.
    function readyMembers(uint256 leaseId) external view returns(address[] memory,uint256){
        Assignment storage a=assignments[leaseId];
        if(a.phase!=Phase.Ready) revert InvalidPhase();
        return(a.primary,a.quorum);
    }
}
