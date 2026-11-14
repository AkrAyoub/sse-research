"""WP09L pure-Python reference ledger: not EVM proof or real VRF billing.

Fee is a fixed ETH reimbursement to subscriber, never an exact LINK quote.
Money conservation modeled as received ETH = held ETH + withdrawn ETH.
"""
from __future__ import annotations
from dataclasses import dataclass
import random

class PolicyError(ValueError):
    pass

@dataclass
class Lease:
    consumer: str
    provider: str
    accepted: bool = False
    closed: bool = False
    escrow: int = 25
    prepaid: int = 0
    spent: bool = False
    requested: bool = False
    pool_cancelled: bool = False


class VrfFeeLedger:
    def __init__(self, fee: int, limit: int, sponsor: str = 'sponsor'):
        if not isinstance(fee, int) or fee <= 0 or not isinstance(limit, int) or limit <= 0:
            raise PolicyError('invalid immutable fee policy')
        self.fee = fee
        self.limit = limit
        self.sponsor = sponsor
        self.requests = 0
        self.leases: dict[int, Lease] = {}
        self.credits: dict[str, int] = {}
        self.received = 0
        self.balance = 0
        self.withdrawn = 0
        self.purchase_entered = False
        self.next_id = 1

    def _credit(self, who: str, amount: int):
        self.credits[who] = self.credits.get(who, 0) + amount

    def create(self, consumer: str, provider: str) -> int:
        if consumer == provider or not consumer or not provider:
            raise PolicyError('invalid lease parties')
        lease_id = self.next_id
        self.next_id += 1
        self.leases[lease_id] = Lease(consumer, provider)
        self.balance += 25
        self.received += 25
        return lease_id

    def accept(self, lease_id: int, caller: str) -> None:
        lease = self.leases[lease_id]
        if caller != lease.provider or lease.closed or lease.accepted:
            raise PolicyError('provider acceptance required once')
        lease.accepted = True

    def fund(self, lease_id: int, caller: str, amount: int) -> None:
        lease = self.leases[lease_id]
        if caller != lease.consumer or not lease.accepted or lease.closed or lease.prepaid != 0 or lease.spent or lease.requested or self.requests >= self.limit or amount != self.fee:
            raise PolicyError('invalid consumer fee funding')
        lease.prepaid = amount
        self.balance += amount
        self.received += amount

    def buy(self, lease_id: int, caller: str, *, coordinator_reverts: bool = False,
            reentry_lease: int | None = None) -> None:
        # caller intentionally permissionless once the consumer funds.
        lease = self.leases[lease_id]
        if self.purchase_entered or lease.closed or not lease.accepted or lease.requested or lease.spent or lease.prepaid != self.fee or self.requests >= self.limit:
            raise PolicyError('unfunded, duplicate, or over quota')
        self.purchase_entered = True
        try:
            if reentry_lease is not None:
                try:
                    self.buy(reentry_lease, 'malicious coordinator')
                except PolicyError:
                    pass
                else:
                    raise AssertionError('reentrant purchase succeeded')
            if coordinator_reverts:
                raise PolicyError('coordinator order reverted atomically')
            lease.prepaid = 0
            lease.spent = True
            lease.requested = True
            self.requests += 1
            self._credit(self.sponsor, self.fee)
        finally:
            self.purchase_entered = False

    def close(self, lease_id: int, caller: str) -> None:
        lease = self.leases[lease_id]
        if caller != lease.consumer or lease.closed:
            raise PolicyError('invalid closure')
        if lease.prepaid:
            self._credit(lease.consumer, lease.prepaid)
            lease.prepaid = 0
        self._credit(lease.consumer, lease.escrow)
        lease.escrow = 0
        lease.closed = True
        lease.pool_cancelled = True

    def withdraw(self, caller: str) -> int:
        amount = self.credits.get(caller, 0)
        if amount <= 0:
            raise PolicyError('nothing to withdraw')
        self.credits[caller] = 0
        self.balance -= amount
        self.withdrawn += amount
        return amount

    def invariants(self):
        assert 0 <= self.requests <= self.limit
        assert self.received == self.balance + self.withdrawn
        held = sum(lease.escrow + lease.prepaid for lease in self.leases.values())
        owed = sum(self.credits.values())
        assert self.balance == held + owed, (self.balance, held, owed)
        assert all(x >= 0 for x in self.credits.values())
        for l in self.leases.values():
            assert not (l.prepaid and l.spent)
            if l.closed:
                assert l.escrow == 0 and l.prepaid == 0 and l.pool_cancelled
            if l.requested:
                assert l.spent and l.prepaid == 0


def adversarial_traces(sequences: int = 400, steps: int = 96) -> int:
    rng = random.Random(9012001)
    actions = ['create','accept','fund','buy','buy_fail','buy_reentry','close',
               'withdraw_consumer','withdraw_sponsor']
    for _ in range(sequences):
        ledger = VrfFeeLedger(fee=7, limit=rng.randint(1, 9))
        for _ in range(steps):
            action = rng.choice(actions)
            lease_id = rng.randint(1, max(1, ledger.next_id))
            try:
                if action == 'create':
                    ledger.create('consumer', 'provider')
                elif action == 'accept':
                    ledger.accept(lease_id, rng.choice(['provider','attacker']))
                elif action == 'fund':
                    ledger.fund(lease_id, rng.choice(['consumer','attacker']),
                                rng.choice([7,0,2,11]))
                elif action == 'buy':
                    ledger.buy(lease_id, rng.choice(['attacker','consumer','sponsor']))
                elif action == 'buy_fail':
                    ledger.buy(lease_id, 'attacker', coordinator_reverts=True)
                elif action == 'buy_reentry':
                    ledger.buy(lease_id, 'attacker', reentry_lease=rng.randint(1,max(1,ledger.next_id-1)))
                elif action == 'close':
                    ledger.close(lease_id, rng.choice(['consumer','attacker']))
                elif action == 'withdraw_consumer':
                    ledger.withdraw('consumer')
                elif action == 'withdraw_sponsor':
                    ledger.withdraw('sponsor')
            except (PolicyError, KeyError):
                pass
            ledger.invariants()
    return sequences * steps
