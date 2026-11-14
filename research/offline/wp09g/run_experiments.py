"""Exact, local, CPU-only evaluation; never calls GitHub or network."""
import csv
import json
import math
from pathlib import Path

from wp09g_recovery import global_draw, Election, Status, complete_attempt

DIR = Path(__file__).resolve().parent


def p_usable(n: int, active_parties: int, draw: int, p_exit: float, threshold=4) -> float:
    """Hypergeometric party exclusions mixed with binomial voluntary exits."""
    total = math.comb(n, draw)
    probability = 0.0
    for p in range(min(draw, active_parties) + 1):
        if draw - p > n - active_parties:
            continue
        p_parties = math.comb(active_parties, p) * math.comb(n-active_parties, draw-p) / total
        candidates = draw-p
        p_survive = sum(math.comb(candidates, k) * (1-p_exit)**k * p_exit**(candidates-k)
                        for k in range(threshold, candidates+1))
        probability += p_parties * p_survive
    return probability


def p_attacker(n: int, attackers: int, seats: int = 4) -> float:
    return 1.0-math.comb(n-attackers, seats)/math.comb(n, seats)


def run():
    n = 160
    parties = 2
    results = []
    for p in [0.0, 0.1, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9]:
        old = p_usable(n, parties, 10, p)
        new = p_usable(n, parties, 40, p)
        results.append({'exit_probability': p,
                        'old_10_proofs_p_four_usable': round(old, 8),
                        'new_40_proofs_p_four_usable': round(new, 8),
                        'improvement_percentage_points': round((new-old)*100, 4)})
    attacker_fraction = p_attacker(160, 40, 4)
    payload = {
        'id': 'WP09G-OFFLINE-2026-11-14',
        'execution': 'stdlib-only local Python, zero network or GitHub Actions',
        'reference_model': 'bounded 8-proof per transaction, max 40 distinct globally sampled indices',
        'assumptions': {'global_population': n, 'enrolled_lease_parties': parties,
                        'independent_post_snapshot_exit_probability': True,
                        'ideal_uniform_seed_for_closed_form_liveness': True,
                        'no_proof_unavailability_or_censorship_in_probability_model': True},
        'per_exit_rate': results,
        'attackers_40_of_160_p_at_least_one_in_four_under_ideal_randomness': attacker_fraction,
        'selective_signer_publish_only_if_attacker_selected_publication_rate': attacker_fraction,
        'selective_signer_withholding_fraction': 1-attacker_fraction,
        'selective_signer_attack_in_published_committees': 1.0,
        'seed_1234_request1_population160_first10': global_draw(1234, 1, n)[:10],
        'seed_1234_request1_population160_all40': global_draw(1234, 1, n),
        'tests': 'python -m unittest -q test_wp09g.py',
        'critical_nonclaims': [
            'Off-chain reference model, NOT compiled/verified Solidity.',
            'More standby draws improve independent-exit availability, not unbiased entropy.',
            'Adversarial targeted exits, proof withholding and deadline censorship can still force failure.',
            'Partial seat reservations are bounded in time but expose lock-griefing risk.',
            'Gas cost, calldata and real-world performance must be measured in local Foundry.'
        ]
    }
    (DIR/'metrics.json').write_text(json.dumps(payload, indent=2)+'\n')
    with (DIR/'liveness_comparison.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({'exit_rate_40pct': results[3], 'exit_rate_60pct': results[4],
                      'exit_rate_80pct': results[6],
                      'withholding_fraction_unchanged': payload['selective_signer_withholding_fraction']}, indent=2))
    return payload


if __name__ == '__main__':
    run()
