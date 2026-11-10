"""Readable WP-07 demonstration; all strong certificates are TEST-ONLY ASSUMPTIONS."""
import json
from sse_formal_reference import SLA, World, world_sound
from sse_evidence_policy_v1 import (
    Binding, PolicyManifest, PolicyMode, Assumption, RawKind, RawObservation,
    QualifiedFact, FactKind, TimeInterval, PhysicalPolicyState, ChainPolicyState,
    ChainSnapshot,
)


def render(label, state, stipulated_world=None):
    d = state.decision()
    print(json.dumps({
        'scenario': label,
        'service_semantics': state.manifest.mode.value,
        'admissible': sorted(w.value for w in d.histories),
        'provider_guaranteed': d.funds.guaranteed_provider,
        'consumer_guaranteed': d.funds.guaranteed_consumer,
        'unresolved': d.funds.unresolved,
        'physical_world_sound_if_stipulated': (
            None if stipulated_world is None else world_sound(stipulated_world, d.histories)),
        'qualified_facts': sorted(d.accepted_fact_ids),
        'raw_reports': d.raw_report_count,
    }, sort_keys=True))


def main():
    b = Binding(7, 2, '0x' + 'a'*64)
    sla = SLA(25, 5)
    m = PolicyManifest(b, PolicyMode.PHYSICAL_DELIVERY, 100, 110)
    strict = PhysicalPolicyState(m, sla)
    for i in range(4):
        strict = strict.with_raw(RawObservation(b, f'timeout-{i}', RawKind.MONITOR_TIMEOUT, f'monitor-{i}'))
    render('all four honest monitors timeout, provider physically fulfilled', strict, World.S)

    assumed = PolicyManifest(b, PolicyMode.PHYSICAL_DELIVERY, 100, 110,
        frozenset({Assumption.NONFULFILLMENT_CERT_SOUND}))
    conditional = PhysicalPolicyState(assumed, sla).with_fact(QualifiedFact(
        b, 'test-certificate-1', FactKind.PHYSICAL_NONFULFILLMENT,
        Assumption.NONFULFILLMENT_CERT_SOUND, 'TEST-ONLY-UNVERIFIED-PROOF'), observed_at=111)
    render('if externally certified nonfulfillment is sound', conditional, World.F)
    render('same assumed certificate is NOT safe if provider actually fulfilled', conditional, World.S)

    clock = PolicyManifest(b, PolicyMode.PHYSICAL_DELIVERY, 100, 110,
        frozenset({Assumption.FULFILLMENT_CERT_SOUND}))
    timed = PhysicalPolicyState(clock, sla).with_fact(QualifiedFact(
        b, 'test-timing', FactKind.PHYSICAL_FULFILLMENT,
        Assumption.FULFILLMENT_CERT_SOUND, 'TEST-ONLY-UNVERIFIED-PROOF',
        TimeInterval(109, 111)), observed_at=112)
    render('event clock interval crosses deadline', timed)

    publication = ChainPolicyState(PolicyManifest(b, PolicyMode.CHAIN_PUBLICATION,
        100, 110, frozenset({Assumption.CANONICAL_CHAIN_COMPLETE})),sla)
    render('on-chain-publication obligation before chain finalized deadline', publication)
    render('on-chain-publication response included at 105 and final through 115',
        publication.advance(ChainSnapshot(b, 115, 105)))
    render('on-chain-publication no valid response by finalized deadline',
        publication.advance(ChainSnapshot(b, 110)))


if __name__ == '__main__':
    main()
