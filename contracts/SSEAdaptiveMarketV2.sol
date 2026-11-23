// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {AdaptiveMonitorQuorum} from "./AdaptiveMonitorQuorum.sol";
import {SSEAdaptiveVoteLedger} from "./SSEAdaptiveVoteLedger.sol";

/// @notice Research SSE V2: actual marketplace escrow + on-chain dynamically
/// selected and funded monitor ledger. No synthetic SLA outcomes.
/// @dev Research caveats: bounded, bond-gated EOA roster is NOT proof of
/// physically independent monitors. Future blockhash entropy is proposer-
/// biasable (NOT VRF); never call this production-unbiased randomness.
contract SSEAdaptiveMarketV2 is EIP712 {
    uint256 public constant MAX_ELIGIBLE = 64;
    uint256 public constant MAX_EPOCHS = 64;
    uint64 public constant MAX_WINDOW = 7 days;
    bytes32 private constant RESPONSE_TYPEHASH = keccak256(
        "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)"
    );
    bytes32 private constant ALLOCATION_TYPEHASH = keccak256(
        "ResidualAllocation(uint256 leaseId,uint256 epochId,uint256 consumerShare,uint256 providerShare,uint256 nonce,uint256 expiry)"
    );

    enum Phase { None, Bidding, PendingDraw, Assigned, Active, Closed, Cancelled }
    struct Request {
        address consumer;
        bytes32 profileHash;
        bytes32 policyHash;
        uint256 maxEpochFee;
        uint64 biddingClose;
        bool selected;
    }
    struct Bid { address provider; uint256 epochFee; }
    struct Terms {
        bytes32 endpointHash;
        uint256 epochs;
        uint256 monitorBudget;
        uint256 perMonitorEpochReward;
        uint256 requiredFaultTolerance;
        uint256 gasBoundSeats;
        uint64 confirmationSeconds;
        uint64 responseSeconds;
        uint64 monitoringSeconds;
    }
    struct Lease {
        address consumer;
        address provider;
        bytes32 profileHash;
        bytes32 policyHash;
        bytes32 endpointHash;
        bytes32 snapshotRoot;
        uint256 requestId;
        uint256 epochFee;
        uint256 maxEpochs;
        uint256 nextEpoch;
        uint256 closedEpochs;
        uint256 serviceRemaining;
        uint256 monitorBudget;
        uint256 perMonitorEpochReward;
        uint256 requiredFaultTolerance;
        uint256 gasBoundSeats;
        uint256 eligibleCount;
        uint64 confirmationSeconds;
        uint64 responseSeconds;
        uint64 monitoringSeconds;
        uint256 entropyBlock;
        Phase phase;
        bool providerAccepted;
    }
    struct Epoch {
        bytes32 requestHash;
        bytes32 responseHash;
        uint256 fee;
        uint256 nonce;
        bool exists;
        bool resolved;
    }
    struct Monitor { uint256 bond; uint256 locked; bool active; }

    SSEAdaptiveVoteLedger public immutable votes;
    uint256 public immutable minimumBond;
    uint256 public nextRequestId = 1;
    uint256 public nextSnapshotCursor;
    uint256 public nextLeaseId = 1;
    uint256 public totalServiceEscrow;
    // Native TEST ETH for funded leases awaiting their future-block draw.
    uint256 public totalPendingMonitorFunding;
    uint256 public totalMonitorBonds;
    uint256 public totalWithdrawable;
    mapping(uint256 => Request) public requests;
    mapping(uint256 => Bid[]) private bids;
    mapping(uint256 => Lease) private leases;
    mapping(uint256 => address[]) private eligibilitySnapshots;
    mapping(uint256 => mapping(uint256 => Epoch)) private epochs;
    mapping(uint256 => mapping(uint256 => bool)) public epochSettled;
    mapping(address => Monitor) public monitors;
    mapping(address => uint256) public withdrawable;
    address[] private activeMonitors;
    mapping(address => uint256) private activeSlot;
    bool private entered;

    error Unauthorized();
    error InvalidInput();
    error InvalidPhase();
    error InsufficientFunding();
    error NoWithdrawal();
    error TransferFailed();
    error InvalidSignature();

    event MonitorJoined(address indexed monitor, uint256 bond);
    event MonitorExited(address indexed monitor);
    event ResourceRequested(uint256 indexed requestId, address indexed consumer, bytes32 profile, bytes32 policy);
    event BidPlaced(uint256 indexed requestId, uint256 indexed index, address indexed provider, uint256 price);
    event LeaseFunded(uint256 indexed leaseId, uint256 indexed requestId, address consumer, address provider, uint256 serviceWei, uint256 monitorWei);
    event EligibilityFrozen(uint256 indexed leaseId, bytes32 indexed root, uint256 eligibleCount, uint256 entropyBlock);
    event CommitteeDrawn(uint256 indexed leaseId, bytes32 indexed entropyHash, uint256 seats, uint256 quorum);
    event ProviderAccepted(uint256 indexed leaseId);
    event EpochStarted(uint256 indexed leaseId, uint256 indexed epochId, bytes32 requestHash);
    event ProviderResponseVerified(uint256 indexed leaseId, uint256 indexed epochId, bytes32 responseHash);
    event EpochConcluded(uint256 indexed leaseId, uint256 indexed epochId, SSEAdaptiveVoteLedger.Outcome outcome);
    event InconclusiveAllocated(uint256 indexed leaseId, uint256 indexed epochId, uint256 consumerShare, uint256 providerShare);
    event LeaseClosed(uint256 indexed leaseId, uint256 returnedServiceWei);
    event LeaseCancelled(uint256 indexed leaseId);
    event Withdrawal(address indexed account, uint256 amount);

    constructor(uint256 bondWei) EIP712("SSEAdaptiveMarketV2", "1") {
        // The actual original research chain is 31340. The deployment
        // script ALSO checks this, but a direct constructor call must never
        // silently deploy an apparently valid marketplace on Mainnet or a
        // different network with no original chain genesis provenance.
        if (bondWei == 0 || block.chainid != 31340) revert InvalidInput();
        minimumBond = bondWei;
        votes = new SSEAdaptiveVoteLedger(address(this));
    }

    function registerMonitor() external payable {
        Monitor storage m = monitors[msg.sender];
        if (m.active || m.locked != 0 || msg.value < minimumBond) revert InvalidInput();
        m.active = true;
        m.bond += msg.value;
        totalMonitorBonds += msg.value;
        activeSlot[msg.sender] = activeMonitors.length + 1;
        activeMonitors.push(msg.sender);
        emit MonitorJoined(msg.sender, msg.value);
    }

    function exitMonitor() external {
        Monitor storage m = monitors[msg.sender];
        if (!m.active || m.locked != 0) revert InvalidPhase();
        m.active = false;
        uint256 index = activeSlot[msg.sender] - 1;
        uint256 last = activeMonitors.length - 1;
        if (index != last) {
            address moved = activeMonitors[last];
            activeMonitors[index] = moved;
            activeSlot[moved] = index + 1;
        }
        activeMonitors.pop();
        delete activeSlot[msg.sender];
        uint256 bond = m.bond;
        m.bond = 0;
        totalMonitorBonds -= bond;
        _credit(msg.sender, bond);
        emit MonitorExited(msg.sender);
    }

    function activeMonitorCount() external view returns (uint256) { return activeMonitors.length; }
    function activeMonitorAt(uint256 index) external view returns (address) { return activeMonitors[index]; }

    function requestResource(bytes32 profile, bytes32 policy, uint256 maxFee, uint64 biddingClose)
        external returns (uint256 id)
    {
        if (profile == bytes32(0) || policy == bytes32(0) ||
            maxFee == 0 || biddingClose <= block.timestamp ||
            biddingClose > block.timestamp + MAX_WINDOW) revert InvalidInput();
        id = nextRequestId++;
        requests[id] = Request(msg.sender, profile, policy, maxFee, biddingClose, false);
        emit ResourceRequested(id, msg.sender, profile, policy);
    }

    function placeBid(uint256 id, uint256 fee) external returns (uint256 index) {
        Request storage r = requests[id];
        if (r.consumer == address(0) || r.consumer == msg.sender ||
            fee == 0 || fee > r.maxEpochFee) revert InvalidInput();
        if (r.selected || block.timestamp >= r.biddingClose) revert InvalidPhase();
        index = bids[id].length;
        bids[id].push(Bid(msg.sender, fee));
        emit BidPlaced(id, index, msg.sender, fee);
    }

    function bidCount(uint256 id) external view returns (uint256) { return bids[id].length; }
    function getBid(uint256 id, uint256 index) external view returns (Bid memory) { return bids[id][index]; }

    function chooseBidAndFund(uint256 requestId, uint256 index, Terms calldata t)
        external payable returns (uint256 leaseId)
    {
        Request storage r = requests[requestId];
        if (r.consumer != msg.sender) revert Unauthorized();
        if (r.selected || block.timestamp < r.biddingClose || index >= bids[requestId].length)
            revert InvalidPhase();
        Bid memory bid = bids[requestId][index];
        if (t.endpointHash == bytes32(0) ||
            t.epochs == 0 || t.epochs > MAX_EPOCHS ||
            t.confirmationSeconds < 1 hours || t.confirmationSeconds > MAX_WINDOW ||
            t.responseSeconds == 0 || t.responseSeconds > MAX_WINDOW ||
            t.monitoringSeconds == 0 || t.monitoringSeconds > MAX_WINDOW)
            revert InvalidInput();
        uint256 service = bid.epochFee * t.epochs;
        if (msg.value != service + t.monitorBudget) revert InsufficientFunding();
        // Select from the bounded rotating window, never hand-pick accounts.
        address[] memory eligible = _frozenEligible(msg.sender, bid.provider);
        uint256 n = eligible.length;
        AdaptiveMonitorQuorum.Decision memory d = AdaptiveMonitorQuorum.decide(
            n, t.requiredFaultTolerance, t.gasBoundSeats,
            t.monitorBudget, t.epochs, t.perMonitorEpochReward
        );
        if (t.monitorBudget != d.seats * t.epochs * t.perMonitorEpochReward)
            revert InsufficientFunding();

        r.selected = true;
        leaseId = nextLeaseId++;
        _recordLease(leaseId, requestId, bid, t, service, eligible);
        emit LeaseFunded(leaseId, requestId, msg.sender, bid.provider, service, t.monitorBudget);
    }

    function _frozenEligible(address consumer, address provider)
        private returns (address[] memory eligible)
    {
        uint256 totalActive = activeMonitors.length;
        uint256 scan = totalActive > MAX_ELIGIBLE ? MAX_ELIGIBLE : totalActive;
        address[] memory scanned = new address[](scan);
        uint256 n;
        // This is a deterministic bounded rotating window, NOT global
        // cryptographically uniform election or proof of independence.
        uint256 cursor = totalActive == 0 ? 0 : nextSnapshotCursor % totalActive;
        for (uint256 i; i < scan; ++i) {
            address candidate = activeMonitors[(cursor + i) % totalActive];
            if (candidate != consumer && candidate != provider) scanned[n++] = candidate;
        }
        if (totalActive != 0) nextSnapshotCursor = (cursor + scan) % totalActive;
        eligible = new address[](n);
        for (uint256 i; i < n; ++i) eligible[i] = scanned[i];
    }

    function _recordLease(
        uint256 leaseId, uint256 requestId, Bid memory bid,
        Terms calldata t, uint256 service, address[] memory eligible
    ) private {
        Request storage r = requests[requestId];
        Lease storage l = leases[leaseId];
        l.consumer = r.consumer;
        l.provider = bid.provider;
        l.profileHash = r.profileHash;
        l.policyHash = r.policyHash;
        l.endpointHash = t.endpointHash;
        l.requestId = requestId;
        l.epochFee = bid.epochFee;
        l.maxEpochs = t.epochs;
        l.serviceRemaining = service;
        l.monitorBudget = t.monitorBudget;
        l.perMonitorEpochReward = t.perMonitorEpochReward;
        l.requiredFaultTolerance = t.requiredFaultTolerance;
        l.gasBoundSeats = t.gasBoundSeats;
        l.eligibleCount = eligible.length;
        l.confirmationSeconds = t.confirmationSeconds;
        l.responseSeconds = t.responseSeconds;
        l.monitoringSeconds = t.monitoringSeconds;
        l.entropyBlock = block.number + 2;
        l.phase = Phase.PendingDraw;
        // Lock ALL frozen candidates' bonds before the future entropy is
        // known. Otherwise a monitored address can exit after commitment but
        // before lottery, and the resulting chosen seat would be unbonded.
        // Each snapshot lock is released on draw/cancel; chosen seats stay
        // locked until the corresponding lease is safely closed/cancelled.
        for (uint256 i; i < eligible.length; ++i) {
            eligibilitySnapshots[leaseId].push(eligible[i]);
            ++monitors[eligible[i]].locked;
        }
        l.snapshotRoot = keccak256(abi.encode(
            block.chainid, address(this), leaseId, requestId,
            r.consumer, bid.provider, r.profileHash, r.policyHash, eligible
        ));
        totalServiceEscrow += service;
        totalPendingMonitorFunding += t.monitorBudget;
        emit EligibilityFrozen(leaseId, l.snapshotRoot, eligible.length, l.entropyBlock);
    }

    function drawCommittee(uint256 leaseId) external {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.PendingDraw ||
            block.number <= l.entropyBlock || block.number > l.entropyBlock + 256)
            revert InvalidPhase();
        bytes32 entropy = blockhash(l.entropyBlock);
        if (entropy == bytes32(0)) revert InvalidPhase();
        AdaptiveMonitorQuorum.Decision memory d = AdaptiveMonitorQuorum.decide(
            l.eligibleCount, l.requiredFaultTolerance, l.gasBoundSeats,
            l.monitorBudget, l.maxEpochs, l.perMonitorEpochReward
        );
        address[] memory roster = eligibilitySnapshots[leaseId];
        address[] memory selected = new address[](d.seats);
        // Unique positions, deterministic partial Fisher-Yates; no arbitrary
        // caller-selected committee. Entropy may be biased by proposer.
        for (uint256 i; i < d.seats; ++i) {
            uint256 pick = i + (uint256(keccak256(abi.encode(
                entropy, address(this), leaseId, i
            ))) % (roster.length - i));
            (roster[i], roster[pick]) = (roster[pick], roster[i]);
            selected[i] = roster[i];
        }
        // The in-memory shuffled roster contains each frozen candidate
        // exactly once. Unselected addresses are the tail of the permutation
        // and must be unlocked; selected addresses retain their original
        // snapshot lock for the lease's entire lifetime.
        for (uint256 i = d.seats; i < roster.length; ++i) {
            --monitors[roster[i]].locked;
        }
        l.phase = Phase.Assigned;
        totalPendingMonitorFunding -= l.monitorBudget;
        SSEAdaptiveVoteLedger.FreezeTerms memory p = SSEAdaptiveVoteLedger.FreezeTerms({
            leaseId: leaseId, consumer: l.consumer, provider: l.provider,
            snapshotRoot: l.snapshotRoot, eligibleCount: l.eligibleCount,
            requiredFaultTolerance: l.requiredFaultTolerance, gasBoundSeats: l.gasBoundSeats,
            monitorBudget: l.monitorBudget, payableEpochs: l.maxEpochs,
            perMonitorEpochReward: l.perMonitorEpochReward,
            confirmationTimeoutSeconds: l.confirmationSeconds
        });
        votes.freezeCommittee{value: l.monitorBudget}(p, selected);
        emit CommitteeDrawn(leaseId, entropy, d.seats, d.quorum);
    }

    /// @notice If the committed future blockhash has expired (256-block
    /// window), the transaction sender cannot pick a replacement seed.
    function cancelExpiredDraw(uint256 leaseId) external {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.PendingDraw || block.number <= l.entropyBlock + 256)
            revert InvalidPhase();
        l.phase = Phase.Cancelled;
        _releaseFrozenSnapshot(leaseId);
        totalPendingMonitorFunding -= l.monitorBudget;
        totalServiceEscrow -= l.serviceRemaining;
        _credit(l.consumer, l.serviceRemaining + l.monitorBudget);
        l.serviceRemaining = 0;
        emit LeaseCancelled(leaseId);
    }

    /// @notice For incomplete committee, expiry triggers ledger's own
    /// monitor-budget refund; market refunds only its service escrow.
    function cancelUnconfirmed(uint256 leaseId) external {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.Assigned) revert InvalidPhase();
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        if (c.ready) revert InvalidPhase();
        if (!c.confirmationExpired) votes.expireUnconfirmed(leaseId);
        _unlockSeats(leaseId);
        l.phase = Phase.Cancelled;
        totalServiceEscrow -= l.serviceRemaining;
        _credit(l.consumer, l.serviceRemaining);
        l.serviceRemaining = 0;
        emit LeaseCancelled(leaseId);
    }

    /// @notice Non-accepting provider cannot strand consumer escrow forever.
    /// Only after the monitor confirmation deadline; releases bonds and both
    /// reserved pools safely, even if no selected monitor has confirmed.
    function cancelUnaccepted(uint256 leaseId) external {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.Assigned || l.providerAccepted) revert InvalidPhase();
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        if (block.timestamp <= c.confirmationDeadline) revert InvalidPhase();
        if (c.ready) votes.closeReporting(leaseId);
        else if (!c.confirmationExpired) votes.expireUnconfirmed(leaseId);
        _unlockSeats(leaseId);
        l.phase = Phase.Cancelled;
        totalServiceEscrow -= l.serviceRemaining;
        _credit(l.consumer, l.serviceRemaining);
        l.serviceRemaining = 0;
        emit LeaseCancelled(leaseId);
    }

    function acceptLease(uint256 leaseId) external {
        Lease storage l = leases[leaseId];
        if (msg.sender != l.provider) revert Unauthorized();
        if (l.phase != Phase.Assigned || l.providerAccepted) revert InvalidPhase();
        l.providerAccepted = true;
        emit ProviderAccepted(leaseId);
    }

    function startEpoch(uint256 leaseId, bytes32 requestHash) external returns (uint256 epochId) {
        Lease storage l = leases[leaseId];
        if (msg.sender != l.consumer) revert Unauthorized();
        if (!l.providerAccepted || (l.phase != Phase.Assigned && l.phase != Phase.Active)
            || l.nextEpoch >= l.maxEpochs || l.nextEpoch != l.closedEpochs ||
            requestHash == bytes32(0)) revert InvalidPhase();
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        if (!c.ready) revert InvalidPhase();
        uint256 responseDeadline = block.timestamp + l.responseSeconds;
        uint256 monitoringClose = responseDeadline + l.monitoringSeconds;
        if (monitoringClose > type(uint64).max) revert InvalidInput();
        epochId = l.nextEpoch++;
        Epoch storage e = epochs[leaseId][epochId];
        e.requestHash = requestHash;
        e.fee = l.epochFee;
        e.exists = true;
        l.phase = Phase.Active;
        votes.openEpoch(leaseId, epochId, requestHash,
                        uint64(responseDeadline), uint64(monitoringClose));
        emit EpochStarted(leaseId, epochId, requestHash);
    }

    /// @notice A real signed provider response is required before any monitor
    /// may cast a Success vote. This authenticates the response hash, not SLA.
    function authenticateProviderResponse(uint256 leaseId, uint256 epochId,
                                          bytes32 responseHash, bytes calldata signature) external {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.resolved || responseHash == bytes32(0)) revert InvalidPhase();
        bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(
            RESPONSE_TYPEHASH, leaseId, epochId, e.requestHash, responseHash
        )));
        if (ECDSA.recover(digest, signature) != l.provider) revert InvalidSignature();
        e.responseHash = responseHash;
        votes.authenticateResponse(leaseId, epochId, responseHash);
        emit ProviderResponseVerified(leaseId, epochId, responseHash);
    }

    /// @notice Only quorum Success/Failure is payable. Inconclusive leaves
    /// fee in escrow for an explicit bilateral signed allocation.
    function finalizeEpoch(uint256 leaseId, uint256 epochId)
        external returns (SSEAdaptiveVoteLedger.Outcome outcome)
    {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.resolved || epochId != l.closedEpochs) revert InvalidPhase();
        SSEAdaptiveVoteLedger.Epoch memory v = votes.epoch(leaseId, epochId);
        outcome = v.monitoringSealed ? v.outcome : votes.seal(leaseId, epochId);
        if (outcome == SSEAdaptiveVoteLedger.Outcome.None) {
            // Seal remains final but no payment decision is fabricated.
            emit EpochConcluded(leaseId, epochId, outcome);
            return outcome;
        }
        e.resolved = true;
        ++l.closedEpochs;
        l.serviceRemaining -= e.fee;
        totalServiceEscrow -= e.fee;
        _credit(outcome == SSEAdaptiveVoteLedger.Outcome.Success ? l.provider : l.consumer, e.fee);
        emit EpochConcluded(leaseId, epochId, outcome);
    }

    function resolveInconclusive(
        uint256 leaseId, uint256 epochId, uint256 consumerShare, uint256 providerShare,
        uint256 nonce, uint256 expiry, bytes calldata consumerSig, bytes calldata providerSig
    ) external {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.resolved || epochId != l.closedEpochs ||
            block.timestamp > expiry || nonce != e.nonce ||
            consumerShare + providerShare != e.fee) revert InvalidPhase();
        SSEAdaptiveVoteLedger.Epoch memory v = votes.epoch(leaseId, epochId);
        if (!v.monitoringSealed || v.outcome != SSEAdaptiveVoteLedger.Outcome.None)
            revert InvalidPhase();
        bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(
            ALLOCATION_TYPEHASH, leaseId, epochId, consumerShare, providerShare, nonce, expiry
        )));
        if (ECDSA.recover(digest, consumerSig) != l.consumer ||
            ECDSA.recover(digest, providerSig) != l.provider) revert InvalidSignature();
        ++e.nonce;
        e.resolved = true;
        ++l.closedEpochs;
        l.serviceRemaining -= e.fee;
        totalServiceEscrow -= e.fee;
        _credit(l.consumer, consumerShare);
        _credit(l.provider, providerShare);
        emit InconclusiveAllocated(leaseId, epochId, consumerShare, providerShare);
    }

    function closeLease(uint256 leaseId) external {
        Lease storage l = leases[leaseId];
        if (msg.sender != l.consumer) revert Unauthorized();
        if (!l.providerAccepted || (l.phase != Phase.Assigned && l.phase != Phase.Active)
            || l.nextEpoch != l.closedEpochs) revert InvalidPhase();
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        if (!c.ready) revert InvalidPhase();
        // Ledger refunds only its unspent monitored report escrow to consumer.
        votes.closeReporting(leaseId);
        _unlockSeats(leaseId);
        l.phase = Phase.Closed;
        uint256 refund = l.serviceRemaining;
        l.serviceRemaining = 0;
        totalServiceEscrow -= refund;
        _credit(l.consumer, refund);
        emit LeaseClosed(leaseId, refund);
    }

    /// @dev Called only for a lease never drawn: every candidate still holds
    /// exactly the pre-draw snapshot lock and can be released once.
    function _releaseFrozenSnapshot(uint256 leaseId) private {
        address[] storage candidates = eligibilitySnapshots[leaseId];
        for (uint256 i; i < candidates.length; ++i) {
            --monitors[candidates[i]].locked;
        }
    }

    function _unlockSeats(uint256 leaseId) private {
        address[] memory seats = votes.selected(leaseId);
        for (uint256 i; i < seats.length; ++i) --monitors[seats[i]].locked;
    }

    function _credit(address account, uint256 amount) private {
        if (amount == 0) return;
        withdrawable[account] += amount;
        totalWithdrawable += amount;
    }

    function withdraw() external {
        if (entered) revert InvalidPhase();
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoWithdrawal();
        entered = true;
        withdrawable[msg.sender] = 0;
        totalWithdrawable -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        entered = false;
        emit Withdrawal(msg.sender, amount);
    }

    function lease(uint256 leaseId) external view returns (Lease memory) { return leases[leaseId]; }
    function epoch(uint256 leaseId, uint256 epochId) external view returns (Epoch memory) {
        return epochs[leaseId][epochId];
    }
    function eligibleAt(uint256 leaseId, uint256 index) external view returns (address) {
        return eligibilitySnapshots[leaseId][index];
    }
    /// @notice Public inspectable market-side native-test-ETH conservation;
    /// vote ledger maintains separate reserve/credit accounting.
    /// Forced ETH can create surplus, so only coverage (>=) is asserted.
    function escrowAccounting() external view
        returns (uint256 marketBalance, uint256 outstanding, bool fullyCovered)
    {
        marketBalance = address(this).balance;
        outstanding = totalServiceEscrow + totalPendingMonitorFunding +
                      totalMonitorBonds + totalWithdrawable;
        fullyCovered = marketBalance >= outstanding;
    }

    function domainSeparator() external view returns (bytes32) { return _domainSeparatorV4(); }
}
