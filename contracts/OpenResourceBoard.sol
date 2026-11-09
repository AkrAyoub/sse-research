// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {SSESettlement} from "./SSESettlement.sol";

contract OpenResourceBoard {
    struct Request {
        address consumer;
        bytes32 resourceProfileHash;
        bytes32 slaPolicyHash;
        uint256 maxEpochFee;
        uint64 biddingClose;
        bool selected;
    }
    struct Bid {
        address provider;
        uint256 epochFee;
    }
    struct LeaseConfig {
        bytes32 serviceEndpointHash;
        uint256 reservationFee;
        uint256 exposureBudget;
        uint256 maxEpochs;
        uint64 responsePeriod;
        uint64 monitoringGrace;
        uint64 evidenceWindow;
    }
    address public immutable bootstrapper;
    address public approvedSettlement;
    uint256 public nextRequestId = 1;
    mapping(uint256 => Request) public requests;
    mapping(uint256 => Bid[]) private bids;

    event Requested(uint256 indexed id, address indexed consumer, bytes32 profileHash, bytes32 slaPolicyHash);
    event BidSubmitted(uint256 indexed id, uint256 indexed index, address indexed provider, uint256 epochFee);
    event BidChosen(uint256 indexed id, uint256 indexed index, address indexed provider, uint256 epochFee);
    event LeaseFunded(uint256 indexed requestId, uint256 indexed leaseId, address indexed settlement);
    event SettlementBound(address indexed settlement);
    error BadInput();
    error NotAuthorized();
    error WrongPhase();

    constructor() {
        bootstrapper = msg.sender;
    }

    function bindSettlement(address candidate) external {
        if (msg.sender != bootstrapper) revert NotAuthorized();
        if (approvedSettlement != address(0)) revert WrongPhase();
        if (candidate == address(0) || candidate.code.length == 0) revert BadInput();
        if (SSESettlement(candidate).resourceBoard() != address(this)) revert BadInput();
        approvedSettlement = candidate;
        emit SettlementBound(candidate);
    }

    function requestResource(bytes32 profileHash, bytes32 policyHash, uint256 maxEpochFee, uint64 biddingClose)
        external returns (uint256 id)
    {
        if (profileHash == bytes32(0) || policyHash == bytes32(0) || maxEpochFee == 0 ||
            biddingClose <= block.timestamp) revert BadInput();
        id = nextRequestId++;
        requests[id] = Request(msg.sender, profileHash, policyHash, maxEpochFee, biddingClose, false);
        emit Requested(id, msg.sender, profileHash, policyHash);
    }

    function placeBid(uint256 id, uint256 epochFee) external returns (uint256 index) {
        Request storage r = requests[id];
        if (r.consumer == address(0) || msg.sender == r.consumer || epochFee == 0 ||
            epochFee > r.maxEpochFee) revert BadInput();
        if (block.timestamp >= r.biddingClose || r.selected) revert WrongPhase();
        index = bids[id].length;
        bids[id].push(Bid(msg.sender, epochFee));
        emit BidSubmitted(id, index, msg.sender, epochFee);
    }

    function chooseBid(uint256 id, uint256 index) external returns (address provider, uint256 fee) {
        Request storage r = requests[id];
        if (r.consumer != msg.sender) revert NotAuthorized();
        if (r.selected || block.timestamp < r.biddingClose || index >= bids[id].length)
            revert WrongPhase();
        Bid storage b = bids[id][index];
        r.selected = true;
        emit BidChosen(id, index, b.provider, b.epochFee);
        return (b.provider, b.epochFee);
    }

    function chooseBidAndFundLease(
        uint256 id,
        uint256 index,
        SSESettlement settlement,
        LeaseConfig calldata config
    ) external payable returns (uint256 leaseId) {
        Request storage r = requests[id];
        if (r.consumer != msg.sender) revert NotAuthorized();
        if (r.selected || block.timestamp < r.biddingClose || index >= bids[id].length)
            revert WrongPhase();
        if (approvedSettlement == address(0) || address(settlement) != approvedSettlement)
            revert BadInput();
        if (settlement.resourceBoard() != address(this)) revert BadInput();

        Bid storage b = bids[id][index];
        r.selected = true;
        SSESettlement.LeaseTerms memory terms;
        terms.consumer = msg.sender;
        terms.provider = b.provider;
        terms.serviceEndpointHash = config.serviceEndpointHash;
        terms.resourceProfileHash = r.resourceProfileHash;
        terms.slaPolicyHash = r.slaPolicyHash;
        terms.marketplaceRequestId = id;
        terms.epochFee = b.epochFee;
        terms.reservationFee = config.reservationFee;
        terms.exposureBudget = config.exposureBudget;
        terms.maxEpochs = config.maxEpochs;
        terms.responsePeriod = config.responsePeriod;
        terms.monitoringGrace = config.monitoringGrace;
        terms.evidenceWindow = config.evidenceWindow;

        leaseId = settlement.createLeaseFromBoard{value: msg.value}(terms);
        emit BidChosen(id, index, b.provider, b.epochFee);
        emit LeaseFunded(id, leaseId, address(settlement));
    }

    function getBid(uint256 id, uint256 index) external view returns (address, uint256) {
        Bid storage b = bids[id][index];
        return (b.provider, b.epochFee);
    }

    function bidCount(uint256 id) external view returns (uint256) {
        return bids[id].length;
    }
}
