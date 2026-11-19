"""R16: never bind settlement before committee bootstrap feature switches.

This regression is tied to the ACTUAL VM4705 chain31339 script trace:
committee.bindSettlement(...) succeeded, then
committee.enableDelayedBlockEntropy() reverted Unauthorized().
The source checker inspects executable Solidity statements, not
comments. The Foundry PoSDeploymentBootstrap.t.sol checks both
legal configurations on a real EVM simulation.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PoSDeploymentOrderTests(unittest.TestCase):
    @staticmethod
    def _statement_pos(src:str,statement:str)->int:
        # Excludes comments and enforces exactly one executable statement.
        hits=list(re.finditer(
            r"^[ \t]*"+re.escape(statement)+r"\s*$",
            src,re.MULTILINE,
        ))
        if len(hits)!=1:
            raise AssertionError(f"expected exactly one executable {statement!r}, got {len(hits)}")
        return hits[0].start()

    def test_delayed_entropy_before_irreversible_settlement_binding(self):
        source=(ROOT/"script"/"DeploySSEPos.s.sol").read_text()
        deployment=self._statement_pos(source,"committee = new OpenMonitorCommittee(")
        delay=self._statement_pos(source,"committee.enableDelayedBlockEntropy();")
        global_mode=self._statement_pos(source,"committee.enableGlobalMerkleElection();")
        batched=self._statement_pos(source,"committee.enableGlobalBatchedRecovery();")
        binding=self._statement_pos(source,"committee.bindSettlement(address(settlement));")
        self.assertLess(deployment,delay)
        self.assertLess(delay,global_mode)
        self.assertLess(global_mode,batched)
        self.assertLess(batched,binding)

    def test_both_modes_and_atomic_role_wiring_are_checked(self):
        source=(ROOT/"script"/"DeploySSEPos.s.sol").read_text()
        for required in (
            "require(block.chainid == OWN_SSE_POS_CHAIN",
            'vm.envOr("SSE_USE_GLOBAL_MERKLE", false)',
            'require(committee.globalMerkleElectionEnabled() == useGlobalMerkle,',
            'require(committee.globalBatchedRecoveryEnabled() == useGlobalMerkle,',
            'committee.bindSettlement(address(settlement));',
            'settlement.bindResourceBoard(address(board));',
            'board.bindSettlement(address(settlement));',
        ):
            self.assertIn(required,source)
        self.assertLess(
            self._statement_pos(source,"committee.bindSettlement(address(settlement));"),
            self._statement_pos(source,"settlement.bindResourceBoard(address(board));")
        )

    def test_foundry_regresses_actual_unauthorized_error(self):
        test=(ROOT/"foundry"/"test"/"PoSDeploymentBootstrap.t.sol").read_text()
        for method in (
            "testLegacyModeBootstrapsBeforeWiring",
            "testGlobalMerkleBatchedModeBootstrapsBeforeWiring",
            "testPostBindingLateFeatureChangesRefused",
        ):
            self.assertIn(f"function {method}(",test)
        self.assertIn("vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);",test)

if __name__=="__main__":
    unittest.main()
