"""Offline-only WP09I tests. No network, GitHub, blockchain or VRF service."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wp09i_vrf_policy import VRFPolicy, Profile, Phase, Decision, PolicyError
from keccak import keccak256

C1 = '0x'+'11'*20
C2 = '0x'+'22'*20
POOL = '0x'+'aa'*20
SETTLEMENT = '0x'+'bb'*20
GOVERNANCE = '0x'+'cc'*20
ROOT = keccak256(b'160 active monitors')
KH1 = keccak256(b'coordinator published key hash A')
KH2 = keccak256(b'coordinator published key hash B')


def profile(v=1, coordinator=C1, key_hash=KH1):
    return Profile(v, 31337, coordinator, key_hash, 123, 5, 200_000, False)


def policy():
    return VRFPolicy(31337, POOL, SETTLEMENT, GOVERNANCE, {1:profile()}, 1)


def request(p, lease=5, vrfid=100, root=ROOT, now=10):
    return p.issue_request(caller=SETTLEMENT, lease_id=lease, coordinator_request_id=vrfid,
                           root=root, count=160, request_block=77,
                           opened_at=now, deadline=now+600)


class ScopeAndConfiguration(unittest.TestCase):
    def test_digest_different_lease(self):
        p=policy()
        a=request(p,5,100)
        b=request(p,6,101)
        self.assertNotEqual(a.digest,b.digest)

    def test_digest_different_snapshot(self):
        p=policy()
        a=request(p,5,100)
        b=request(p,6,101,keccak256(b'second root'))
        self.assertNotEqual(a.digest,b.digest)

    def test_invalid_sender_cannot_request(self):
        p=policy()
        with self.assertRaises(PolicyError):
            p.issue_request(caller=C2,lease_id=5,coordinator_request_id=100,root=ROOT,count=160,
                            request_block=77,opened_at=1,deadline=10)
        self.assertEqual(p.requests,{})

    def test_no_rerequest_after_expiry(self):
        p=policy();request(p)
        p.expire(lease_id=5,now=611)
        with self.assertRaisesRegex(PolicyError,'cannot request randomness twice'):
            request(p,5,101)

    def test_replay_same_coordinator_id_other_lease_rejected(self):
        p=policy();request(p)
        with self.assertRaisesRegex(PolicyError,'replay'):
            request(p,6,100)

    def test_caller_cannot_force_old_profile(self):
        p=policy();p.rotate_future_requests(profile(2,C2,KH2),caller=GOVERNANCE)
        with self.assertRaises(PolicyError):
            p.issue_request(caller=SETTLEMENT,lease_id=6,coordinator_request_id=101,
                            root=ROOT,count=160,request_block=78,opened_at=20,deadline=620,
                            provider_version=1)

    def test_unauthorized_rotation_rejected(self):
        p=policy()
        with self.assertRaisesRegex(PolicyError,'only governance'):
            p.rotate_future_requests(profile(2,C2,KH2),caller=C1)
        self.assertEqual(p.active_version,1)

    def test_unauthorized_retirement_rejected(self):
        p=policy();p.rotate_future_requests(profile(2,C2,KH2),caller=GOVERNANCE)
        with self.assertRaisesRegex(PolicyError,'only governance'):
            p.decommission_profile(1,caller=C1)
        self.assertIn(1,p.disabled_for_new)  # disallowed for future requests, still retained historically

    def test_bad_profile_rejected(self):
        for p in [Profile(1,31337,C1,KH1,123,5,200_000,False)]:
            self.assertEqual(p.version,1)
        for args in [dict(version=0), dict(chain_id=0), dict(coordinator='0x'+'00'*20),
                     dict(key_hash=b'bad'),dict(subscription_id=0),dict(confirmations=0),
                     dict(callback_gas_limit=0), dict(native_payment=1)]:
            kwargs=dict(version=1,chain_id=31337,coordinator=C1,key_hash=KH1,
                        subscription_id=123,confirmations=5,callback_gas_limit=200_000,
                        native_payment=False)
            kwargs.update(args)
            with self.subTest(args=args),self.assertRaises(ValueError):Profile(**kwargs)


class CallbackLifecycle(unittest.TestCase):
    def setUp(self):
        self.p=policy();self.r=request(self.p)

    def test_verified_callback_stores_and_applies_once(self):
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                            random_words=(47,),now=30),Decision.STORED)
        self.assertEqual(self.r.phase,Phase.READY)
        v=self.p.apply_seed(lease_id=5,now=31)
        self.assertGreaterEqual(v,0)
        self.assertLess(v,1<<256)
        self.assertEqual(self.r.phase,Phase.APPLIED)
        with self.assertRaises(PolicyError):self.p.apply_seed(lease_id=5,now=32)

    def test_wrong_origin_cannot_fulfill(self):
        with self.assertRaises(PolicyError):
            self.p.coordinator_callback(caller=C2,coordinator_request_id=100,
                                        random_words=(1,),now=30)
        self.assertEqual(self.r.phase,Phase.REQUESTED)

    def test_valid_unknown_request_is_ignored(self):
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=999,
                            random_words=(1,),now=30),Decision.UNKNOWN_IGNORED)

    def test_duplicate_callback_does_not_replace_output(self):
        self.p.coordinator_callback(caller=C1,coordinator_request_id=100,random_words=(11,),now=30)
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                            random_words=(999,),now=31),Decision.DUPLICATE_IGNORED)
        self.assertEqual(self.r.raw_word,11)
        self.assertEqual(self.r.ignored_callbacks,1)

    def test_late_callback_not_resurrected(self):
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                            random_words=(11,),now=611),Decision.LATE_IGNORED)
        self.assertEqual(self.r.phase,Phase.EXPIRED)
        with self.assertRaises(PolicyError):self.p.apply_seed(lease_id=5,now=612)

    def test_expired_before_callback_and_cleanup(self):
        self.p.expire(lease_id=5,now=611)
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                            random_words=(11,),now=612),Decision.LATE_IGNORED)
        self.assertIsNone(self.r.raw_word)
        self.assertEqual(self.p.progress()[Phase.EXPIRED.value],1)

    def test_failed_callback_input_rejected(self):
        for value in [(1,2),(),(-1,),('1',),(2**256,),[1]]:
            with self.subTest(value=value),self.assertRaises(PolicyError):
                self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                                            random_words=value,now=20)
        self.assertEqual(self.r.phase,Phase.REQUESTED)

    def test_deadline_last_second_accepted_next_expires(self):
        self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                                    random_words=(9,),now=610)
        self.p.apply_seed(lease_id=5,now=610)
        self.assertEqual(self.r.phase,Phase.APPLIED)
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                            random_words=(10,),now=611),Decision.LATE_IGNORED)

    def test_ready_but_unapplied_can_expire(self):
        self.p.coordinator_callback(caller=C1,coordinator_request_id=100,random_words=(12,),now=30)
        self.p.expire(lease_id=5,now=611)
        self.assertEqual(self.r.phase,Phase.EXPIRED)
        self.assertIsNone(self.r.raw_word)

    def test_unauthorized_cannot_change_result_after_apply(self):
        self.p.coordinator_callback(caller=C1,coordinator_request_id=100,random_words=(88,),now=20)
        seed=self.p.apply_seed(lease_id=5,now=21)
        self.assertEqual(self.p.coordinator_callback(caller=C1,coordinator_request_id=100,
                             random_words=(99,),now=22),Decision.LATE_IGNORED)
        self.assertEqual(seed,self.r.applied_seed)


class RotationAndComposition(unittest.TestCase):
    def test_inflight_still_accepts_old_coordinator_after_rotation(self):
        p=policy();a=request(p,5,100)
        p.rotate_future_requests(profile(2,C2,KH2),caller=GOVERNANCE)
        b=request(p,6,101)
        self.assertNotEqual(a.digest,b.digest)
        self.assertEqual(p.coordinator_callback(caller=C1,coordinator_request_id=100,
                            random_words=(5,),now=30),Decision.STORED)
        self.assertEqual(p.coordinator_callback(caller=C2,coordinator_request_id=101,
                            random_words=(6,),now=30),Decision.STORED)
        self.assertNotEqual(p.apply_seed(lease_id=5,now=31),p.apply_seed(lease_id=6,now=31))
        p.decommission_profile(1,caller=GOVERNANCE)

    def test_old_coordinator_cannot_be_retired_with_pending_request(self):
        p=policy();request(p)
        p.rotate_future_requests(profile(2,C2,KH2),caller=GOVERNANCE)
        with self.assertRaisesRegex(PolicyError,'in-flight'):
            p.decommission_profile(1,caller=GOVERNANCE)
        p.expire(lease_id=5,now=611)
        p.decommission_profile(1,caller=GOVERNANCE)

    def test_cross_coordinator_request_id_collision_is_scoped(self):
        p=policy();a=request(p,5,100)
        p.rotate_future_requests(profile(2,C2,KH2),caller=GOVERNANCE);b=request(p,6,100)
        self.assertNotEqual(a.digest,b.digest)
        p.coordinator_callback(caller=C1,coordinator_request_id=100,random_words=(1,),now=30)
        p.coordinator_callback(caller=C2,coordinator_request_id=100,random_words=(2,),now=30)
        self.assertEqual(a.raw_word,1)
        self.assertEqual(b.raw_word,2)

    def test_wrong_coordinator_for_old_id_cannot_crosswire(self):
        p=policy();request(p,5,100);p.rotate_future_requests(profile(2,C2,KH2),caller=GOVERNANCE)
        self.assertEqual(p.coordinator_callback(caller=C2,coordinator_request_id=100,
                         random_words=(9,),now=30),Decision.UNKNOWN_IGNORED)
        self.assertEqual(p.requests[(C1,100)].phase,Phase.REQUESTED)

    def test_reference_seed_can_feed_existing_wp09g_election(self):
        # No EVM assertion: this combines two OFFLINE models only.
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from wp09g_recovery import Election, Status
        p=policy();request(p)
        p.coordinator_callback(caller=C1,coordinator_request_id=100,random_words=(2026,),now=30)
        seed=p.apply_seed(lease_id=5,now=31)
        addresses=tuple('0x'+format(0xC100+i,'040x') for i in range(40))
        election=Election(addresses,1,'consumer','provider',requested_at=10,timeout_seconds=600)
        election.fulfill_entropy(seed,verified=True,now=31)
        while election.remaining:
            sample=election.indexes[election.proof_cursor:election.proof_cursor+8]
            election.batch([(i,addresses[i]) for i in sample],now=32)
        self.assertEqual(election.status,Status.ASSIGNED)
        self.assertEqual(len(election.committee),4)
        self.assertEqual(len(election.standbys),36)

    def test_not_yet_verified_no_fallback_into_wp09g(self):
        from wp09g_recovery import Election, ElectionError
        p=policy();request(p)
        election=Election(tuple('0x'+format(0xC100+i,'040x') for i in range(40)),
                          1,'consumer','provider',requested_at=10,timeout_seconds=600)
        with self.assertRaises(ElectionError):
            election.fulfill_entropy(7,verified=False,now=31)
        with self.assertRaises(PolicyError):p.apply_seed(lease_id=5,now=31)


if __name__ == '__main__':unittest.main()
