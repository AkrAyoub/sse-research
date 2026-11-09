// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenResourceBoard} from "../../contracts/OpenResourceBoard.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

contract FakeSettlementDestination {
    address public immutable resourceBoard;
    uint256 public received;

    constructor(address boardAddress) {
        resourceBoard = boardAddress;
    }

    function createLeaseFromBoard(SSESettlement.LeaseTerms calldata)
        external payable returns (uint256)
    {
        received += msg.value;
        return 999;
    }
}

contract MarketplaceEscrowTest is Test {
    OpenResourceBoard board;
    OpenMonitorCommittee committee;
    SSESettlement settlement;

    address consumer = address(0xA100);
    address provider = address(0xB100);
    bytes32 profile = keccak256("cpu-2-ram-4gb");
    bytes32 policy = keccak256("response-availability-policy");
    bytes32 endpoint = keccak256("provider-http-endpoint");

    function setUp() public {
        vm.warp(10_000);
        board = new OpenResourceBoard();
        committee = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        settlement = new SSESettlement(address(committee));
        committee.bindSettlement(address(settlement));
        settlement.bindResourceBoard(address(board));
        board.bindSettlement(address(settlement));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        for (uint256 i; i < 5; ++i) {
            address monitor = address(uint160(0xC100 + i));
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            committee.register{value: 1 ether}();
        }
    }

    function _requestAndBid() internal returns (uint256 requestId) {
        vm.prank(consumer);
        requestId = board.requestResource(profile, policy, 40, uint64(block.timestamp + 100));
        vm.prank(provider);
        board.placeBid(requestId, 25);
        vm.warp(block.timestamp + 101);
    }

    function _config() internal view returns (OpenResourceBoard.LeaseConfig memory config) {
        config = OpenResourceBoard.LeaseConfig({
            serviceEndpointHash: endpoint,
            reservationFee: 5,
            exposureBudget: 25,
            maxEpochs: 1,
            responsePeriod: 100,
            monitoringGrace: 100,
            evidenceWindow: 100
        });
    }

    function _fund(uint256 requestId, uint256 value) internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = board.chooseBidAndFundLease{value: value}(
            requestId, 0, settlement, _config()
        );
    }

    function testSelectedBidCreatesMatchingFundedLease() public {
        uint256 requestId = _requestAndBid();
        uint256 leaseId = _fund(requestId, 25);

        SSESettlement.Lease memory lease = settlement.getLease(leaseId);
        assertEq(lease.consumer, consumer);
        assertEq(lease.provider, provider);
        assertEq(lease.epochFee, 25);
        assertEq(lease.reservationFee, 5);
        assertEq(lease.totalEscrow, 25);
        assertEq(lease.resourceProfileHash, profile);
        assertEq(lease.slaPolicyHash, policy);
        assertEq(lease.serviceEndpointHash, endpoint);
        assertEq(lease.marketplaceRequestId, requestId);
        assertEq(address(settlement).balance, 25);
        assertEq(committee.snapshotSize(lease.assignmentId), 5);

        vm.prank(provider);
        settlement.acceptLease(leaseId);
        SSESettlement.Lease memory accepted = settlement.getLease(leaseId);
        assertEq(uint8(accepted.state), uint8(SSESettlement.LeaseState.Accepted));
    }

    function testMarketplaceLeaseSettlesAndWithdraws() public {
        uint256 requestId = _requestAndBid();
        uint256 leaseId = _fund(requestId, 25);

        vm.prank(provider);
        settlement.acceptLease(leaseId);
        committee.fulfillRandomness(1, 0xC0FFEE);
        settlement.finalizeMonitorCommittee(leaseId);
        address[4] memory selected = committee.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            vm.prank(selected[i]);
            settlement.confirmMonitorAssignment(leaseId);
        }

        vm.prank(consumer);
        settlement.admitEpoch(leaseId, keccak256("canonical-request"));
        SSESettlement.Epoch memory ep = settlement.getEpoch(leaseId, 0);
        vm.warp(uint256(ep.responseDeadline) + 1);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            settlement.submitMonitorVoteDirect(
                leaseId, 0, SSESettlement.Outcome.Failure, keccak256(abi.encode(i))
            );
        }
        vm.warp(uint256(ep.evidenceClose) + 1);
        settlement.closeEpochEvidence(leaseId, 0);

        assertEq(settlement.withdrawable(consumer), 20);
        assertEq(settlement.withdrawable(provider), 0);
        uint256 beforeBalance = consumer.balance;
        vm.prank(consumer);
        settlement.withdraw();
        assertEq(consumer.balance, beforeBalance + 20);
        assertEq(address(settlement).balance, 5);

        vm.prank(consumer);
        settlement.closeLease(leaseId);
        settlement.releaseCommitteeAfterEvidence(leaseId);
        assertEq(uint8(committee.assignmentStatus(1)), 4);
    }

    function testUnderpaymentRevertsSelectionAtomically() public {
        uint256 requestId = _requestAndBid();
        vm.expectRevert(SSESettlement.InsufficientFunding.selector);
        _fund(requestId, 24);
        (,,,,, bool selected) = board.requests(requestId);
        assertFalse(selected);
        assertEq(settlement.nextLeaseId(), 1);
        assertEq(address(settlement).balance, 0);
    }

    function testDuplicateFundingReverts() public {
        uint256 requestId = _requestAndBid();
        _fund(requestId, 25);
        vm.expectRevert(OpenResourceBoard.WrongPhase.selector);
        _fund(requestId, 25);
        assertEq(settlement.nextLeaseId(), 2);
    }

    function testNonConsumerCannotFundSelectedBid() public {
        uint256 requestId = _requestAndBid();
        vm.prank(provider);
        vm.expectRevert(OpenResourceBoard.NotAuthorized.selector);
        board.chooseBidAndFundLease{value: 25}(
            requestId, 0, settlement, _config()
        );
    }

    function testOnlyBootstrapperCanBindAndCannotRebind() public {
        vm.prank(consumer);
        vm.expectRevert(OpenResourceBoard.NotAuthorized.selector);
        board.bindSettlement(address(settlement));

        vm.expectRevert(OpenResourceBoard.WrongPhase.selector);
        board.bindSettlement(address(settlement));
        assertEq(board.approvedSettlement(), address(settlement));
    }

    function testBindingRejectsSettlementPairedWithDifferentBoard() public {
        OpenResourceBoard otherBoard = new OpenResourceBoard();
        vm.expectRevert(OpenResourceBoard.BadInput.selector);
        otherBoard.bindSettlement(address(settlement));
        assertEq(otherBoard.approvedSettlement(), address(0));
    }

    function testFakeSettlementCannotReceiveConsumerFunds() public {
        uint256 requestId = _requestAndBid();
        FakeSettlementDestination fake = new FakeSettlementDestination(address(board));
        assertEq(fake.resourceBoard(), address(board));

        vm.prank(consumer);
        vm.expectRevert(OpenResourceBoard.BadInput.selector);
        board.chooseBidAndFundLease{value: 25}(
            requestId, 0, SSESettlement(address(fake)), _config()
        );

        (,,,,, bool selected) = board.requests(requestId);
        assertFalse(selected);
        assertEq(fake.received(), 0);
        assertEq(address(fake).balance, 0);
        assertEq(settlement.nextLeaseId(), 1);
        assertEq(address(settlement).balance, 0);
    }

    function testDirectCallCannotImpersonateMarketplace() public {
        SSESettlement.LeaseTerms memory terms;
        terms.consumer = consumer;
        terms.provider = provider;
        terms.marketplaceRequestId = 1;
        terms.slaPolicyHash = policy;
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.createLeaseFromBoard{value: 25}(terms);
    }
}
