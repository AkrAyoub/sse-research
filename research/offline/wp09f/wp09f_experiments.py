"""WP-09F, strictly OFFLINE / ZERO GITHUB ACTIONS: monitor selection adversarial lab.

Tracks mechanics in the stacked research PR #26 (WP-09E), not deployed code.
Uses exact EVM Keccak-256 for sparse Fisher-Yates regression vectors and
standard-library random sampling for high-volume *ideal entropy* simulations.
The simulation oracle is deliberately NOT an audited RSA-VRF or blockchain.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from typing import NamedTuple

from keccak import keccak256

K = 4
DRAW_LIMIT = 10
WINDOW = 64
N = 160
ATTACKER_IDENTITIES = 40
WINDOW_STARTS = tuple((i * WINDOW) % N for i in range(5))
FIXED_SEED = 20261114


class Finding(NamedTuple):
    group: str
    metric: str
    value: float
    unit: str
    assumption: str


def abi_u256(value: int) -> bytes:
    if not isinstance(value, int) or not 0 <= value < 1 << 256:
        raise ValueError("invalid uint256")
    return value.to_bytes(32, 'big')


def exact_wp09e_sparse_draw(seed: int, request_id: int, n: int,
                            draw_limit: int = DRAW_LIMIT) -> list[int]:
    """Bit-for-bit index draw of WP09E GlobalRosterSampler.draw Solidity.

    Mapping keys + values model a partial Fisher–Yates swap. Zero external
    dependencies; this function uses Keccak-256, not SHA3-256.
    """
    if not 4 <= n <= (1 << 20) or not 0 < request_id < 1 << 256:
        raise ValueError("bad n or request")
    if not 1 <= draw_limit <= 10:
        raise ValueError("draw count out of Solidity research bound")
    abi_u256(seed)
    values: dict[int, int] = {}
    results: list[int] = []
    for i in range(min(n, draw_limit)):
        digest = keccak256(abi_u256(seed) + abi_u256(request_id) + abi_u256(i))
        j = i + int.from_bytes(digest, 'big') % (n - i)
        selected = values.get(j, j)
        displaced = values.get(i, i)
        values[j] = displaced
        results.append(selected)
    return results


def dense_draw_reference(seed: int, request_id: int, n: int,
                         draw_limit: int = DRAW_LIMIT) -> list[int]:
    """Independent full-length reference: tests sparse implementation."""
    abi_u256(seed)
    permutation = list(range(n))
    for i in range(min(n, draw_limit)):
        j = i + int.from_bytes(keccak256(
            abi_u256(seed) + abi_u256(request_id) + abi_u256(i)), 'big') % (n - i)
        permutation[i], permutation[j] = permutation[j], permutation[i]
    return permutation[:min(n, draw_limit)]


def hypergeom_at_least(n: int, attackers: int, seats: int, threshold: int) -> float:
    """P(X >= threshold), sampling distinct identities uniformly without replacement."""
    if not 0 <= attackers <= n or not 0 <= seats <= n:
        raise ValueError("bad hypergeometric parameters")
    ways = math.comb(n, seats)
    return sum(math.comb(attackers, i) * math.comb(n - attackers, seats - i)
               for i in range(max(0, threshold), min(attackers, seats) + 1)
               if seats - i <= n - attackers) / ways


def retain_at_least(draw: int, online_probability: float, needed: int = K) -> float:
    """P(>=needed live names among `draw` after independent post-snapshot exits)."""
    if not 0 <= online_probability <= 1:
        raise ValueError("invalid online probability")
    return sum(math.comb(draw, i) * online_probability ** i *
               (1 - online_probability) ** (draw - i)
               for i in range(needed, draw + 1)) if draw >= needed else 0.0


def global_snapshot_survival(n: int, active_parties: int, draw: int,
                             post_snapshot_exit_rate: float) -> float:
    """Finite-population mixture for party exclusions plus independent monitor exits."""
    if not 0 <= active_parties <= n or not 1 <= draw <= n:
        raise ValueError("invalid parties/draw")
    denom = math.comb(n, draw)
    out = 0.0
    for p in range(0, min(active_parties, draw) + 1):
        if draw - p > n - active_parties:
            continue
        probability = (math.comb(active_parties, p) *
                       math.comb(n - active_parties, draw - p) / denom)
        out += probability * retain_at_least(draw - p,
                                            1 - post_snapshot_exit_rate)
    return out


def window_attacker_counts(n: int = N, adversary: int = ATTACKER_IDENTITIES,
                           window: int = WINDOW) -> list[int]:
    """Fixed attacker IDs in [0,adversary): clustered at the start of the roster."""
    if n != N or window != WINDOW:
        raise ValueError("scenario has explicit N=160, window=64")
    return [sum(((start + i) % n) < adversary for i in range(window))
            for start in WINDOW_STARTS]


def ideal_entropy_monte_carlo(rounds: int = 20_000,
                              random_seed: int = FIXED_SEED) -> dict:
    """Independent ideal draw oracle: NOT the exact on-chain keccak seed model."""
    if rounds <= 0 or rounds % len(WINDOW_STARTS) != 0:
        raise ValueError("rounds must be positive multiple of five")
    rng = random.Random(random_seed)
    attack_windows = window_attacker_counts()
    actual_window = [0] * len(WINDOW_STARTS)
    global_attack = 0
    total_window_attack = 0
    for run in range(rounds):
        window_index = run % len(WINDOW_STARTS)
        start = WINDOW_STARTS[window_index]
        window_roster = [(start + offset) % N for offset in range(WINDOW)]
        chosen_window = rng.sample(window_roster, K)
        chosen_global = rng.sample(range(N), K)
        window_hit = any(i < ATTACKER_IDENTITIES for i in chosen_window)
        global_hit = any(i < ATTACKER_IDENTITIES for i in chosen_global)
        actual_window[window_index] += int(window_hit)
        total_window_attack += int(window_hit)
        global_attack += int(global_hit)
    return {
        'samples': rounds,
        'seed': random_seed,
        'window_attacker_counts': attack_windows,
        'window_attack_frequency_by_start': [v / (rounds / 5) for v in actual_window],
        'window_attack_frequency_overall': total_window_attack / rounds,
        'global_attack_frequency': global_attack / rounds,
    }


def run_experiment(rounds: int = 20_000, random_seed: int = FIXED_SEED) -> dict:
    simulated = ideal_entropy_monte_carlo(rounds, random_seed)
    window_counts = window_attacker_counts()
    exact_window = [hypergeom_at_least(WINDOW, m, K, 1) for m in window_counts]
    any_malicious = hypergeom_at_least(N, ATTACKER_IDENTITIES, K, 1)
    two_malicious = hypergeom_at_least(N, ATTACKER_IDENTITIES, K, 2)
    churn = []
    for p in (0.0, 0.1, 0.2, 0.4, 0.6):
        churn.append({
            'post_snapshot_exit_rate': p,
            'p_four_available_no_parties': retain_at_least(DRAW_LIMIT, 1 - p),
            'p_four_available_two_active_parties': global_snapshot_survival(
                N, 2, DRAW_LIMIT, p),
            'p_all_four_initial_confirm_independent_no_show': (1 - p) ** K,
            'p_at_least_four_confirm_if_all_ten_tried': retain_at_least(
                DRAW_LIMIT, 1 - p)
        })

    # Separate attempts over future leases, with a signer privately computing
    # its canonical RSA proof but selectively *publishing* only favorable ones.
    selective = []
    for required_malicious in (0, 1, 2):
        p_publish = (1.0 if required_malicious == 0 else
                     hypergeom_at_least(N, ATTACKER_IDENTITIES, K, required_malicious))
        selective.append({
            'operator_policy': 'always' if required_malicious == 0 else
                               f'publish only if >= {required_malicious} attacker(s) in first four',
            'min_attacker_seats_for_publication': required_malicious,
            'publication_rate': p_publish,
            'nonpublication_rate': 1 - p_publish,
            'p_attack_in_published_committees': any_malicious if required_malicious == 0 else 1.0,
            'publication_rate_assumes_ideal_uniform_seed': True
        })

    return {
        'experiment_id': 'WP09F-OFFLINE-2026-11-14',
        'execution': 'local Python standard library only, no GitHub Actions, no RPC',
        'source_policy': 'simulation of current PR26 WP09B/WP09E selection logic; not executing Solidity',
        'design_constants': {
            'active_roster_size': N,
            'committee_size': K,
            'global_proved_draws': DRAW_LIMIT,
            'wp09b_window': WINDOW,
            'window_starts_full_cycle': WINDOW_STARTS,
            'adversarial_identities': ATTACKER_IDENTITIES,
            'attacker_addresses_are_concentrated_in_index_range': [0, ATTACKER_IDENTITIES - 1],
            'party_addresses_in_churn_model': 2
        },
        'seeded_regression_vector': {
            'seed': 1234,
            'request_id': 1,
            'active_count': N,
            'exact_wp09e_draw_indices': exact_wp09e_sparse_draw(1234, 1, N)
        },
        'ideal_entropy_analytic': {
            'global_p_at_least_one_attacker_in_four': any_malicious,
            'global_p_at_least_two_attackers_in_four': two_malicious,
            'wp09b_window_attacker_counts': window_counts,
            'wp09b_window_p_at_least_one_attacker_by_start': exact_window,
            'wp09b_full_cursor_cycle_average_p_attack': sum(exact_window) / len(exact_window),
            'wp09b_cursor_cycle_marginal_per_identity': 4 / N,
            'wp09e_global_marginal_per_identity': 4 / N
        },
        'ideal_entropy_simulation': simulated,
        'selective_proof_withholding': selective,
        'independent_post_snapshot_churn': churn,
        'adversarial_exit_bound': {
            'drawn_indexes': DRAW_LIMIT,
            'min_four_to_finalize': K,
            'exits_that_guarantee_failure_if_all_draws_were_initially_eligible': DRAW_LIMIT - K + 1,
            'consequence': 'at most 3 current candidates; global finalization reverts; timeout and consumer refund path required'
        },
        'caveats': [
            'Monte Carlo uses Python Random as an ideal uniform oracle, not Ethereum Keccak or production RSA entropy.',
            'WP09E sampler regression uses exact Ethereum Keccak and ABI uint256 big endian, but does not execute EVM.',
            'Economic bond exit costs, lease fees, proposer bias and correlated infrastructure are not measured.',
            'Proof-operator censorship does not change distribution of all originally attempted leases, but makes published sample conditionally biased.',
            'Time-to-recovery depends on renewed one-hour confirmation timeouts and callable relayers; success probability is not latency.',
            'Churn assumes independently random per-monitor exits, which is weaker than adaptive adversarial targeted churn.',
            'Fixed 2^20 slots, O(20) root mutations and 20-level proofs are contract design bounds, not measured gas costs.'
        ]
    }


def findings_rows(payload: dict) -> list[Finding]:
    theory = payload['ideal_entropy_analytic']
    rows = [
        Finding('global', 'p_any_attacker_in_first_four', theory['global_p_at_least_one_attacker_in_four'],
                'probability', 'ideal unbiased seed, n=160 attacker=40'),
        Finding('global', 'p_two_attackers_in_first_four', theory['global_p_at_least_two_attackers_in_four'],
                'probability', 'ideal unbiased seed'),
    ]
    for i, value in enumerate(theory['wp09b_window_p_at_least_one_attacker_by_start']):
        rows.append(Finding('wp09b_window', f'p_any_attacker_start_{WINDOW_STARTS[i]}', value,
                            'probability', f'{theory["wp09b_window_attacker_counts"][i]}/64 attacker identities'))
    for item in payload['selective_proof_withholding']:
        rows.append(Finding('withholding', f'publication_rate_min_attacker_{item["min_attacker_seats_for_publication"]}',
                            item['publication_rate'], 'probability', item['operator_policy']))
    for item in payload['independent_post_snapshot_churn']:
        rows.append(Finding('churn', f'prob_four_survive_p_{item["post_snapshot_exit_rate"]:.1f}',
                            item['p_four_available_two_active_parties'], 'probability',
                            'ten globally drawn indexes, two in-roster lease parties, independent exits'))
    return rows


def write_results(output_dir: Path, rounds: int, seed: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = run_experiment(rounds, seed)
    (output_dir / 'results.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    with (output_dir / 'metrics.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(Finding._fields)
        writer.writerows(findings_rows(payload))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=20_000)
    parser.add_argument('--seed', type=int, default=FIXED_SEED)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = write_results(args.output, args.rounds, args.seed)
    print(json.dumps({
        'experiment': result['experiment_id'],
        'iterations': args.rounds,
        'exact_keccak_indexes': result['seeded_regression_vector']['exact_wp09e_draw_indices'],
        'global_attack_probability': result['ideal_entropy_analytic']['global_p_at_least_one_attacker_in_four'],
        'global_attack_simulated': result['ideal_entropy_simulation']['global_attack_frequency'],
        'withholding_publish_probability_attacker_hit': result['selective_proof_withholding'][1]['publication_rate'],
        'data_files': [str(args.output / 'results.json'), str(args.output / 'metrics.csv')]
    }, indent=2))
