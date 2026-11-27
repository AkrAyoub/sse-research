# Requirements traceability (session S1 subset; extend each session)

Source codes: OWN = owner instruction (handoff/REQUIREMENTS.md "Latest owner requirements" / governing instruction),
PROP = proposal extract, M3 = Milestone 3 extract, ENG = engineering necessity, REC = agent recommendation.
Milestone 4 official rubric: **unavailable** (not in repository) — not invented.

| Req | Source | Component | Files | Status | Test source | Runtime verification | Acceptance |
|---|---|---|---|---|---|---|---|
| Consumer selects n monitors and b; quorum shown; no silent weakening | OWN | Board, planner | SSEServiceBoardV4.createRequest; sse_v4_committee_planner.plan | NI/SR/TW | test_sse_v4_committee_planner; V4 market tests | DRV-V4-01, DRV-PY-01 | n≥3b+1 enforced; alternatives that lower b flagged requiresExplicitConsent |
| Fixed epochs or provider-proposed epochs, committed before funding | OWN | Board/Market | placeBid epochs; termsHash | NI/SR/TW | testEarlyAward…, testWrongTermsHash… | DRV-V4-01 | provider accepts exact termsHash |
| Award any bid, no minimum, early close | OWN | Board.award | — | NI/SR/TW | testEarlyAwardOfSingleBidClosesRequest | DRV-V4-01 | single bid awardable before biddingClose |
| Bidding never starts paid work | OWN | Market.startEpoch | — | NI/SR/TW | testBidAwardAndFundingAloneNeverAuthorizeExecution | DRV-V4-01 + agent tests (NO) | no EpochStarted without Active∧accepted |
| Standby fixed order, promotion pre-service only, no mid-epoch change | OWN/ENG | Standby + Ledger | — | ET(R429)+NI | testStandbyPromotion… | DRV-V4-01 | replaced primary cannot vote |
| Capacity reservation and safe release on every path | OWN/ENG | Registry | reserveSample/releaseExcept/releaseAll | NI/SR/TW | testConcurrentLeases…, testUnformed…, testUnaccepted… | DRV-V4-01 | totalReserved()==0 after close/cancel |
| Global unbiased sampling, no central randomness | OWN/ENG | Registry | reserveSample | NI/SR/TW | testSamplingRoughUniformity | DRV-V4-01, E9 | — |
| SSE invariants (N/F/S, conservation, monotone, exposure) | PROP/M3 | Market + libs | — | ET(V3) + SR(V4) | testFuzzConservation, V3 suites | DRV-V4-01 | conserved()==true, coverage holds |
| Signed response ≠ SLA truth; receipt only by explicit policy | OWN/M3 | Market | responseAdmitsReceipt | NI/SR/TW | testResponseAsReceiptOnlyUnderExplicitTerm | DRV-V4-01 | — |
| Separate V4 deployment, V3 preserved | OWN | Deploy script | DeploySSEV4Candidate31340 | NI/SR | — | DRV-V4-05 | V3 addresses untouched |
| Role UIs, explorer, installer, agents | OWN | — | — | NO | — | — | see checklist B/C/D/E |
