// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {RSA2048EntropyVerifier} from "./RSA2048EntropyVerifier.sol";
import {GlobalRosterMerkle} from "./GlobalRosterMerkle.sol";
import {GlobalRosterSampler} from "./GlobalRosterSampler.sol";




contract OpenMonitorCommittee {
    // Maximum active candidates examined by ONE assignment transaction.
    // This is a gas bound, NOT a lifetime registration ceiling or a global
    // uniform sampling claim. Enrollment is permissionless but not Sybil-safe.
    uint256 public constant MAX_SNAPSHOT_SCAN = 64;
    uint256 public constant COMMITTEE_SIZE = 4;
    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;
    uint256 public constant GLOBAL_MERKLE_CAPACITY = 1 << 20;
    uint256 public constant DELAYED_ENTROPY_BLOCKS = 4;
    bytes32 public constant DELAYED_ENTROPY_DOMAIN = keccak256("SSEDelayedBlockEntropyV1");
    bytes32 public constant RSA_ENTROPY_DOMAIN = keccak256("SSERSAProofEntropyV1");

    enum RequestStatus { None, AwaitingRandomness, Assigned, Expired, Released }
    struct Candidate {
        uint256 bond;
        uint64 exitRequestedAt;
        uint32 pendingSelections;
        uint32 activeAssignments;
        bool active;
        bool everRegistered;
    }
    struct Assignment {
        address consumer;
        address provider;
        uint64 requestedAt;
        RequestStatus status;
        address[4] committee;
    }

    address public immutable bootstrapper;
    address public immutable randomnessSource;
    uint256 public immutable minimumBond;
    uint64 public immutable exitDelay;
    uint64 public immutable randomnessTimeout;
    address public settlement;
    uint256 public nextAssignmentId = 1;
    // Opt-in only before settlement binding: blocks the legacy source callback
    // and uses a future block hash. This is NOT an Ethereum VRF/finality proof.
    bool public delayedBlockEntropyEnabled;
    // A mutually exclusive, opt-in deterministic proof-verification mode.
    // The verifier is DEPLOYED by this pool, never arbitrary external code.
    RSA2048EntropyVerifier public rsaEntropyVerifier;
    // Independent opt-in for global indexed election, compatible with any
    // ONE entropy mode. Must be enabled before any candidate is registered.
    bool public globalMerkleElectionEnabled;
    bool private entered;

    // Dense ACTIVE roster. Exited addresses are removed by swap-and-pop,
    // allowing new identities to register without an unbounded history scan.
    address[] private activeCandidates;
    mapping(address => uint256) private activeIndexPlusOne;
    uint256 public totalRegistrations;
    uint256 public nextSnapshotCursor;
    mapping(address => Candidate) public candidates;
    mapping(uint256 => Assignment) private assignments;
    mapping(uint256 => address[]) private snapshots;
    // Full post-seed shuffle: never hand-pick a replacement or resample seed.
    mapping(uint256 => address[]) private standbyRosters;
    mapping(uint256 => uint256) private nextStandbyIndex;
    mapping(uint256 => uint256) public assignmentRequestedBlock;
    mapping(uint256 => bytes32) public snapshotCommitment;
    // Updates are bounded to 20 levels, even for large active populations.
    mapping(uint256 => bytes32) private globalTree;
    mapping(uint256 => bytes32) public globalSnapshotRoot;
    mapping(uint256 => uint256) public globalSnapshotCount;
    mapping(uint256 => uint256) public pendingGlobalSeed;
    mapping(uint256 => bool) public pendingGlobalSeedReady;

    error InvalidInput();
    error InvalidPhase();
    error Unauthorized();
    error InsufficientCandidates();
    error TransferFailed();
    error InvalidEntropyProof();
    error InvalidGlobalProof();
    event CandidateRegistered(address indexed account, uint256 bond);
    event ActiveCandidateRemoved(address indexed account, uint256 activeRemaining);
    event SnapshotWindowUsed(uint256 indexed requestId, uint256 startIndex,
                             uint256 scanned, uint256 activeCount, uint256 eligible);
    event ExitRequested(address indexed account);
    event BondWithdrawn(address indexed account, uint256 amount);
    event SettlementBound(address indexed settlement);
    event DelayedEntropyModeEnabled();
    event RSAProofEntropyModeEnabled(address indexed verifier, bytes32 modulusHash);
    event GlobalMerkleElectionEnabled();
    event GlobalRosterLeafUpdated(uint256 indexed index, address indexed account);
    event GlobalRosterRootUpdated(bytes32 root, uint256 activeCount);
    event GlobalEligibilityCommitted(uint256 indexed requestId, bytes32 root,
                                     uint256 count, bytes32 requestCommitment);
    event GlobalEntropySeedReady(uint256 indexed requestId, bytes32 seedHash);
    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,
                                uint256 sampled, uint256 validCandidates);
    event RSARequestCommitted(uint256 indexed requestId, bytes32 requestDigest,
                              bytes32 snapshotHash);
    event RSAProofEntropyApplied(uint256 indexed requestId, bytes32 requestDigest,
                                bytes32 proofHash, uint256 derivedSeed);
    event EligibilitySnapshotCommitted(uint256 indexed requestId, bytes32 commitment,
                                       uint256 requestBlock, uint256 entropyBlock);
    event DelayedEntropyApplied(uint256 indexed requestId, uint256 entropyBlock,
                                bytes32 entropyBlockHash, bytes32 snapshotHash,
                                uint256 derivedSeed);
    event AssignmentRequested(uint256 indexed requestId, address consumer, address provider, uint256 poolSize);
    event CommitteeSelected(uint256 indexed requestId, address[4] committee);
    event CommitteeMemberReplaced(uint256 indexed requestId, address indexed removed,
                                  address indexed replacement, uint256 remainingStandbys);
    event AssignmentExpired(uint256 indexed requestId);
    event AssignmentCancelled(uint256 indexed requestId, RequestStatus previousStatus);
    event AssignmentReleased(uint256 indexed requestId);

    constructor(address randomProvider, uint256 minBond, uint64 exitDelaySeconds, uint64 randomnessTimeoutSeconds) {
        if (randomProvider == address(0) || minBond == 0 ||
            randomnessTimeoutSeconds == 0 || exitDelaySeconds <= randomnessTimeoutSeconds)
            revert InvalidInput();
        bootstrapper = msg.sender;
        randomnessSource = randomProvider;
        minimumBond = minBond;
        exitDelay = exitDelaySeconds;
        randomnessTimeout = randomnessTimeoutSeconds;
    }

    //One time deployment wiring. After this, bootstrapper has no admin operations
    function bindSettlement(address target) external {
        if (msg.sender != bootstrapper || settlement != address(0)) revert Unauthorized();
        if (target == address(0) || target.code.length == 0) revert InvalidInput();
        settlement = target;
        emit SettlementBound(target);
    }

    /// @notice One-way deployment configuration, before any lease can be wired.
    /// @dev A block proposer can bias/reorg the future block; use reviewed
    /// VRF or other independent entropy for production global elections.
    function enableDelayedBlockEntropy() external {
        if (msg.sender != bootstrapper || settlement != address(0) ||
            delayedBlockEntropyEnabled || address(rsaEntropyVerifier) != address(0))
            revert Unauthorized();
        delayedBlockEntropyEnabled = true;
        emit DelayedEntropyModeEnabled();
    }

    /// @notice One-way experimental RSA-root-verified mode, prior to wiring.
    /// @dev RSA key setup, signer withholding, and global-window fairness are
    /// NOT proven. Use only a vetted genuine RSA-2048 public modulus.
    function enableRSAProofEntropy(bytes calldata publicModulus) external {
        if (msg.sender != bootstrapper || settlement != address(0) ||
            delayedBlockEntropyEnabled || address(rsaEntropyVerifier) != address(0))
            revert Unauthorized();
        RSA2048EntropyVerifier verifier = new RSA2048EntropyVerifier(publicModulus);
        rsaEntropyVerifier = verifier;
        emit RSAProofEntropyModeEnabled(address(verifier), keccak256(publicModulus));
    }

    /// @notice One-way global indexed election requires an initially empty
    /// roster and a pre-binding choice; no retroactive, untracked balances.
    /// @dev Merkle root is global, frozen per request; NOT proof of fair entropy.
    function enableGlobalMerkleElection() external {
        if (msg.sender != bootstrapper || settlement != address(0) ||
            globalMerkleElectionEnabled || totalRegistrations != 0 ||
            activeCandidates.length != 0) revert Unauthorized();
        globalMerkleElectionEnabled = true;
        emit GlobalMerkleElectionEnabled();
    }

    function globalRosterRoot() external view returns (bytes32) {
        return globalTree[1];
    }

    modifier onlySettlement() {
        if (msg.sender != settlement || settlement == address(0)) revert Unauthorized();
        _;
    }

    function register() external payable {
        Candidate storage c = candidates[msg.sender];
        if (c.bond != 0 || msg.value < minimumBond) revert InvalidInput();
        if (activeIndexPlusOne[msg.sender] != 0) revert InvalidInput();
        if (!c.everRegistered) {
            c.everRegistered = true;
            ++totalRegistrations;
        }
        if (globalMerkleElectionEnabled &&
            activeCandidates.length >= GLOBAL_MERKLE_CAPACITY) revert InvalidInput();
        activeCandidates.push(msg.sender);
        activeIndexPlusOne[msg.sender] = activeCandidates.length;
        if (globalMerkleElectionEnabled) {
            _updateGlobalLeaf(activeCandidates.length - 1, msg.sender);
            emit GlobalRosterRootUpdated(globalTree[1], activeCandidates.length);
        }
        c.bond = msg.value;
        c.active = true;
        c.exitRequestedAt = 0;
        emit CandidateRegistered(msg.sender, msg.value);
    }

    function topUpBond() external payable {
        Candidate storage c = candidates[msg.sender];
        if (!c.active || msg.value == 0) revert InvalidPhase();
        c.bond += msg.value;
    }

    function requestExit() external {
        Candidate storage c = candidates[msg.sender];
        if (!c.active || c.pendingSelections != 0 || c.activeAssignments != 0) revert InvalidPhase();
        c.active = false;
        c.exitRequestedAt = uint64(block.timestamp);
        // A candidate cannot exit while an unfulfilled snapshot references it
        // or while a confirmed/selected seat keeps its active bond locked.
        _removeActive(msg.sender);
        emit ExitRequested(msg.sender);
    }

    function _removeActive(address account) internal {
        uint256 slot = activeIndexPlusOne[account];
        if (slot == 0) revert InvalidPhase();
        uint256 last = activeCandidates.length - 1;
        uint256 index = slot - 1;
        if (index != last) {
            address moved = activeCandidates[last];
            activeCandidates[index] = moved;
            activeIndexPlusOne[moved] = slot;
        }
        activeCandidates.pop();
        delete activeIndexPlusOne[account];
        if (globalMerkleElectionEnabled) {
            if (index != last) _updateGlobalLeaf(index, activeCandidates[index]);
            _updateGlobalLeaf(last, address(0));
            emit GlobalRosterRootUpdated(globalTree[1], activeCandidates.length);
        }
        if (activeCandidates.length == 0 ||
            nextSnapshotCursor >= activeCandidates.length) nextSnapshotCursor = 0;
        emit ActiveCandidateRemoved(account, activeCandidates.length);
    }

    function _updateGlobalLeaf(uint256 index, address account) internal {
        GlobalRosterMerkle.write(globalTree, index, account);
        emit GlobalRosterLeafUpdated(index, account);
    }

    function withdrawBond() external {
        Candidate storage c = candidates[msg.sender];
        if (entered || c.active || c.bond == 0 || c.exitRequestedAt == 0 ||
            c.pendingSelections != 0 || c.activeAssignments != 0 ||
            block.timestamp < uint256(c.exitRequestedAt) + exitDelay) revert InvalidPhase();
        uint256 value = c.bond;
        c.bond = 0;
        c.exitRequestedAt = 0;
        entered = true;
        (bool ok,) = payable(msg.sender).call{value: value}("");
        if (!ok) revert TransferFailed();
        entered = false;
        emit BondWithdrawn(msg.sender, value);
    }

    function requestAssignment(address consumer, address provider) external onlySettlement returns (uint256 id) {
        if (consumer == address(0) || provider == address(0) || consumer == provider) revert InvalidInput();
        id = nextAssignmentId++;
        Assignment storage r = assignments[id];
        r.consumer = consumer;
        r.provider = provider;
        r.requestedAt = uint64(block.timestamp);
        r.status = RequestStatus.AwaitingRandomness;
        uint256 count = activeCandidates.length;
        if (count < COMMITTEE_SIZE) revert InsufficientCandidates();
        if (globalMerkleElectionEnabled) {
            // Exclude the two lease parties in O(1). Both are in the global
            // registry at most once each and never count as eligible.
            uint256 eligible = count;
            if (activeIndexPlusOne[consumer] != 0) --eligible;
            if (activeIndexPlusOne[provider] != 0) --eligible;
            if (eligible < COMMITTEE_SIZE) revert InsufficientCandidates();
            bytes32 root = globalTree[1];
            if (root == bytes32(0)) revert InvalidPhase();
            assignmentRequestedBlock[id] = block.number;
            globalSnapshotRoot[id] = root;
            globalSnapshotCount[id] = count;
            bytes32 commitment = keccak256(abi.encode(
                block.chainid, address(this), id, block.number, root, count
            ));
            snapshotCommitment[id] = commitment;
            emit GlobalEligibilityCommitted(id, root, count, commitment);
            emit AssignmentRequested(id, consumer, provider, count);
            return id;
        }
        uint256 scanned = count < MAX_SNAPSHOT_SCAN ? count : MAX_SNAPSHOT_SCAN;
        uint256 start = nextSnapshotCursor % count;
        for (uint256 i; i < scanned; ++i) {
            address account = activeCandidates[(start + i) % count];
            Candidate storage c = candidates[account];
            if (account != consumer && account != provider && c.active && c.bond >= minimumBond) {
                snapshots[id].push(account);
                ++c.pendingSelections;
            }
        }
        if (snapshots[id].length < COMMITTEE_SIZE) revert InsufficientCandidates();
        // The eligible order and membership are frozen BEFORE the future
        // block can exist; bounded to 64 addresses from WP-09B.
        assignmentRequestedBlock[id] = block.number;
        bytes32 commitment = keccak256(abi.encode(
            block.chainid, address(this), id, block.number, snapshots[id]));
        snapshotCommitment[id] = commitment;
        if (delayedBlockEntropyEnabled) {
            emit EligibilitySnapshotCommitted(id, commitment, block.number,
                                              block.number + DELAYED_ENTROPY_BLOCKS);
        }
        if (address(rsaEntropyVerifier) != address(0)) {
            emit RSARequestCommitted(id, rsaRequestDigest(id), commitment);
        }
        nextSnapshotCursor = (start + scanned) % count;
        emit SnapshotWindowUsed(id, start, scanned, count, snapshots[id].length);
        emit AssignmentRequested(id, consumer, provider, snapshots[id].length);
    }

    /// @notice Legacy source-controlled path; disabled in both proof modes.
    function fulfillRandomness(uint256 id, uint256 seed) external {
        if (delayedBlockEntropyEnabled || address(rsaEntropyVerifier) != address(0) ||
            msg.sender != randomnessSource) revert Unauthorized();
        _selectSeededCommittee(id, seed);
    }

    /// @notice Domain-bound hash of the frozen eligible window for an RSA
    /// proof operator. No Ethereum PoS finality or physical SLA attestation.
    function rsaRequestDigest(uint256 id) public view returns (bytes32) {
        bytes32 commitment = snapshotCommitment[id];
        if (commitment == bytes32(0)) revert InvalidPhase();
        return keccak256(abi.encode(
            RSA_ENTROPY_DOMAIN, block.chainid, address(this), id,
            assignmentRequestedBlock[id], commitment
        ));
    }

    /// @notice Any relayer can submit a canonical RSA exponentiation proof.
    /// @dev Excludes arbitrary-seed substitution and alternate proof encodings,
    /// but private-key operator can withhold, with no deterministic liveness.
    function fulfillRSAProofEntropy(uint256 id, bytes calldata proof) external {
        RSA2048EntropyVerifier verifier = rsaEntropyVerifier;
        if (address(verifier) == address(0)) revert InvalidPhase();
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp > uint256(r.requestedAt) + randomnessTimeout)
            revert InvalidPhase();
        bytes32 digest = rsaRequestDigest(id);
        if (!verifier.verify(digest, proof)) revert InvalidEntropyProof();
        bytes32 proofHash = keccak256(proof);
        uint256 seed = uint256(keccak256(abi.encode(
            RSA_ENTROPY_DOMAIN, digest, proofHash
        )));
        _selectSeededCommittee(id, seed);
        emit RSAProofEntropyApplied(id, digest, proofHash, seed);
    }

    /// @notice Anyone may finalize once the FUTURE target block has been mined.
    /// @dev This is reproducible on-chain entropy, not unbiased PoS VRF or
    /// finality. Reorgs, block-proposer bias and targeted assignment timing
    /// remain possible and are explicitly outside this WP09C guarantee.
    function fulfillDelayedBlockEntropy(uint256 id) external {
        if (!delayedBlockEntropyEnabled) revert InvalidPhase();
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp > uint256(r.requestedAt) + randomnessTimeout)
            revert InvalidPhase();
        uint256 requestBlock = assignmentRequestedBlock[id];
        if (requestBlock == 0 || snapshotCommitment[id] == bytes32(0))
            revert InvalidPhase();
        uint256 entropyBlock = requestBlock + DELAYED_ENTROPY_BLOCKS;
        if (block.number <= entropyBlock || block.number - entropyBlock > 256)
            revert InvalidPhase();
        bytes32 hash = blockhash(entropyBlock);
        if (hash == bytes32(0)) revert InvalidPhase(); // >256 old or missing
        uint256 seed = uint256(keccak256(abi.encode(
            DELAYED_ENTROPY_DOMAIN, block.chainid, address(this), id,
            snapshotCommitment[id], entropyBlock, hash)));
        _selectSeededCommittee(id, seed);
        emit DelayedEntropyApplied(id, entropyBlock, hash,
                                   snapshotCommitment[id], seed);
    }

    function _selectSeededCommittee(uint256 id, uint256 seed) internal {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp > uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();
        if (globalMerkleElectionEnabled) {
            if (pendingGlobalSeedReady[id]) revert InvalidPhase();
            pendingGlobalSeed[id] = seed;
            pendingGlobalSeedReady[id] = true;
            emit GlobalEntropySeedReady(id, keccak256(abi.encode(seed)));
            return;
        }
        address[] memory roster = snapshots[id];
        uint256 length = roster.length;
        
        // Finish the seed-determined Fisher-Yates-style permutation; modulo
        // reduction may introduce negligible bias and the seed is V1 trusted.
        // Finish all selected and standby slots in this bounded snapshot.
        // SAME randomness draw; no consumer-selected standby on recovery.
        for (uint256 i; i < length; ++i) {
            uint256 j = i + uint256(keccak256(abi.encode(seed, id, i))) % (length - i);
            (roster[i], roster[j]) = (roster[j], roster[i]);
            if (i < COMMITTEE_SIZE) r.committee[i] = roster[i];
            else standbyRosters[id].push(roster[i]);
        }
        _unlockSnapshot(id);
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            ++candidates[r.committee[i]].activeAssignments;
        }
        r.status = RequestStatus.Assigned;
        emit CommitteeSelected(id, r.committee);
    }

    /// @notice After seed fulfillment, anyone can prove the first at most ten
    /// GLOBAL indexes from a deterministic partial Fisher-Yates permutation.
    /// @dev The caller supplies EVERY drawn leaf in the exact derived order;
    /// skipping an unfavorable result or substituting a candidate fails.
    /// Post-request exits can reduce liveness; such candidates are skipped,
    /// and <4 currently bonded active candidates fails closed.
    function finalizeGlobalCommittee(
        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths
    ) external {
        if (!globalMerkleElectionEnabled || !pendingGlobalSeedReady[id])
            revert InvalidPhase();
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp > uint256(r.requestedAt) + randomnessTimeout)
            revert InvalidPhase();
        uint256 count = globalSnapshotCount[id];
        uint256 drawCount = count < GLOBAL_SAMPLE_LIMIT ? count : GLOBAL_SAMPLE_LIMIT;
        if (drawCount < COMMITTEE_SIZE || accounts.length != drawCount ||
            siblingPaths.length != drawCount) revert InvalidInput();
        uint256[] memory indexes = GlobalRosterSampler.draw(
            pendingGlobalSeed[id], id, count, drawCount
        );
        bytes32 root = globalSnapshotRoot[id];
        uint256 valid;
        for (uint256 i; i < drawCount; ++i) {
            address account = accounts[i];
            if (!GlobalRosterMerkle.verify(root, indexes[i], account, siblingPaths[i]))
                revert InvalidGlobalProof();
            Candidate storage c = candidates[account];
            // The historical root proves prior enrollment; current bond and
            // activity must still hold before a candidate can be assigned.
            if (account == r.consumer || account == r.provider ||
                !c.active || c.bond < minimumBond) continue;
            if (valid < COMMITTEE_SIZE) r.committee[valid] = account;
            else standbyRosters[id].push(account);
            ++valid;
        }
        if (valid < COMMITTEE_SIZE) revert InsufficientCandidates();
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            ++candidates[r.committee[i]].activeAssignments;
        }
        r.status = RequestStatus.Assigned;
        delete pendingGlobalSeedReady[id];
        delete pendingGlobalSeed[id];
        emit GlobalCommitteeProved(id, root, drawCount, valid);
        emit CommitteeSelected(id, r.committee);
    }

    /// @notice Publish the first at most ten sampled indices for independent
    /// indexer replay, without a caller-controlled choose-a-member option.
    function globalDrawIndexes(uint256 id) external view returns (uint256[] memory) {
        if (!globalMerkleElectionEnabled || !pendingGlobalSeedReady[id] ||
            assignments[id].status != RequestStatus.AwaitingRandomness)
            revert InvalidPhase();
        uint256 n = globalSnapshotCount[id];
        uint256 k = n < GLOBAL_SAMPLE_LIMIT ? n : GLOBAL_SAMPLE_LIMIT;
        return GlobalRosterSampler.draw(pendingGlobalSeed[id], id, n, k);
    }

    /// @notice Settlement may atomically cancel an assignment when a
    /// lease is CLOSED before the committee is copied into settlement.
    /// The consumer is NOT granted direct permission on this pool method.
    /// This also prevents already-staged global seeds from assigning after
    /// lease close, and frees selected bonds if not yet finalized.
    function cancelUnassigned(uint256 id) external onlySettlement {
        Assignment storage r = assignments[id];
        RequestStatus previous = r.status;
        if (previous == RequestStatus.AwaitingRandomness) {
            if (!globalMerkleElectionEnabled) _unlockSnapshot(id);
            delete pendingGlobalSeedReady[id];
            delete pendingGlobalSeed[id];
            r.status = RequestStatus.Expired;
        } else if (previous == RequestStatus.Assigned) {
            // Settlement hasn't copied the committee yet; no epoch exists.
            for (uint256 i; i < COMMITTEE_SIZE; ++i) {
                --candidates[r.committee[i]].activeAssignments;
            }
            delete standbyRosters[id];
            delete nextStandbyIndex[id];
            r.status = RequestStatus.Released;
            emit AssignmentReleased(id);
        } else if (previous != RequestStatus.Expired) {
            revert InvalidPhase();
        }
        emit AssignmentCancelled(id, previous);
    }

    function expire(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp <= uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();
        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);
        delete pendingGlobalSeedReady[id];
        delete pendingGlobalSeed[id];
        r.status = RequestStatus.Expired;
        emit AssignmentExpired(id);
    }

    /// @dev A standby may have exited after the original randomness reveal;
    /// skip it, never select an unbonded or currently inactive identity.
    /// Only the bound settlement may replace a confirmed *missing* seat.
    /// The settlement enforces the per-seat confirmation timeout and no epochs.
    function replaceUnconfirmed(uint256 id, address missing)
        external onlySettlement returns (address replacement)
    {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.Assigned || missing == address(0)) revert InvalidPhase();
        bool member;
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            if (r.committee[i] == missing) { member = true; break; }
        }
        if (!member) revert InvalidInput();

        address[] storage standby = standbyRosters[id];
        uint256 cursor = nextStandbyIndex[id];
        while (cursor < standby.length) {
            address candidate = standby[cursor++];
            Candidate storage c = candidates[candidate];
            if (!c.active || c.bond < minimumBond) continue;
            bool alreadyMember;
            for (uint256 j; j < COMMITTEE_SIZE; ++j) {
                if (r.committee[j] == candidate) { alreadyMember = true; break; }
            }
            if (alreadyMember) continue;
            replacement = candidate;
            break;
        }
        if (replacement == address(0)) revert InsufficientCandidates();
        nextStandbyIndex[id] = cursor;
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            if (r.committee[i] == missing) {
                r.committee[i] = replacement;
                break;
            }
        }
        --candidates[missing].activeAssignments;
        ++candidates[replacement].activeAssignments;
        emit CommitteeMemberReplaced(id, missing, replacement, standby.length - cursor);
    }

    function standbyRemaining(uint256 id) external view returns (uint256) {
        return standbyRosters[id].length - nextStandbyIndex[id];
    }

    function releaseAssignment(uint256 id) external onlySettlement {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.Assigned) revert InvalidPhase();
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            --candidates[r.committee[i]].activeAssignments;
        }
        delete standbyRosters[id];
        delete nextStandbyIndex[id];
        r.status = RequestStatus.Released;
        emit AssignmentReleased(id);
    }

    function _unlockSnapshot(uint256 id) internal {
        address[] storage roster = snapshots[id];
        for (uint256 i; i < roster.length; ++i) --candidates[roster[i]].pendingSelections;
        delete snapshots[id];
    }

    function getCommittee(uint256 id) external view returns (address[4] memory) {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.Assigned && r.status != RequestStatus.Released) revert InvalidPhase();
        return r.committee;
    }

    /// @notice Original request time anchors VRF timeout; immutable per ID.
    function assignmentRequestedAt(uint256 id) external view returns (uint64) {
        return assignments[id].requestedAt;
    }
    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }
    // These getters enumerate ACTIVE bonded candidates, not a lifetime list.
    function candidateCount() external view returns (uint256) { return activeCandidates.length; }
    function candidateAt(uint256 index) external view returns (address) { return activeCandidates[index]; }
    function activeSlot(address account) external view returns (uint256) {
        return activeIndexPlusOne[account];
    }
    function snapshotSize(uint256 id) external view returns (uint256) { return snapshots[id].length; }
}
