"""Deterministic, offline WP09H availability and selective-censorship study.

Assumptions: an IDEAL unique-output threshold VRF (not implemented),
independent honest responder availability p, f malicious responders who may
see partial outputs and decide to withhold. If h>=threshold honest responsive
shares exist, malicious parties cannot prevent eventual release. If h<threshold
and h+f>=threshold, malicious shares are necessary and selective censorship
can bias published outputs. One election samples k unique addresses uniformly.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

DEFAULT_N = 160
DEFAULT_ATTACKER_IDENTITIES = 40
DEFAULT_SEATS = 4
DEFAULT_TRIALS = 50000
DEFAULT_SEED = 20261114


def attacker_hit_probability(n: int = DEFAULT_N,
                             adversary: int = DEFAULT_ATTACKER_IDENTITIES,
                             seats: int = DEFAULT_SEATS) -> float:
    if type(n) is not int or not (0 <= adversary <= n) or not (1 <= seats <= n):
        raise ValueError('invalid roster composition')
    return 1.0 - math.comb(n - adversary, seats) / math.comb(n, seats) if n-adversary >= seats else 1.0


def binomial_tail(n: int, threshold: int, probability: float) -> float:
    if type(n) is not int or not (0 <= threshold <= n + 1) or not 0 <= probability <= 1:
        raise ValueError('invalid binomial parameters')
    return sum(math.comb(n, k) * probability**k * (1-probability)**(n-k)
               for k in range(threshold, n + 1))


def policy_exact(n_signers: int, threshold: int, compromised: int, p: float,
                 hit: float) -> dict:
    """Exact outcomes with adaptive malicious omission; no crypto proof claim.

    Honest responders >=t: unstoppable release. Otherwise, if together with
    malicious shares they could reach t, adversary publishes only if favorable.
    """
    if not (1 <= threshold <= n_signers and 0 <= compromised <= n_signers
            and 0 <= p <= 1 and 0 <= hit <= 1):
        raise ValueError('invalid threshold experiment')
    honest_count = n_signers - compromised
    forced = binomial_tail(honest_count, threshold, p)
    possible = binomial_tail(honest_count, max(0, threshold-compromised), p)
    conditional = max(0, possible - forced)
    release = forced + conditional * hit
    favorable_released = hit * (forced + conditional)
    return {
        'signers':n_signers,'threshold':threshold,'compromised':compromised,
        'honest_online_probability':p,'attacker_hit_ideal':hit,
        'forced_publish_probability':forced,
        'attacker_optional_probability':conditional,
        'publish_probability':release,
        'aborted_probability':1-release,
        'attacker_hit_among_published':favorable_released/release if release else None,
        'unbiased_if_forced':hit if forced>0 else None,
    }


def policy_simulated(n_signers: int, threshold: int, compromised: int,
                     p: float, *, trials: int = DEFAULT_TRIALS,
                     seed: int = DEFAULT_SEED) -> dict:
    """Independent Monte Carlo sanity-check of ideal-output analytical model."""
    rng=random.Random(seed)
    published=favorable=forced=aborted=0
    honest_count=n_signers-compromised
    for _ in range(trials):
        responder_count=sum(rng.random() < p for _ in range(honest_count))
        elected=rng.sample(range(DEFAULT_N),DEFAULT_SEATS)
        hit=any(i < DEFAULT_ATTACKER_IDENTITIES for i in elected)
        if responder_count >= threshold:
            forced+=1
            published+=1
            favorable+=hit
        elif responder_count+compromised >= threshold and hit:
            published+=1
            favorable+=1
        else:
            aborted+=1
    return {
        'trials':trials,'published_count':published,'aborted_count':aborted,
        'publish_probability':published/trials,
        'attacker_hit_among_published':favorable/published if published else None,
        'forced_publish_count':forced,
    }


def run_experiment(out_dir: Path, *, trials: int=DEFAULT_TRIALS) -> dict:
    out_dir.mkdir(parents=True,exist_ok=True)
    hit=attacker_hit_probability()
    scenarios=[
        ('single signer, fully adversarial',1,1,1,1.0),
        ('3 signers, 2 required, all honest',3,2,0,.95),
        ('5 signers, 3 required, all honest',5,3,0,.95),
        ('5 signers, 3 required, 1 adversarial',5,3,1,.95),
        ('5 signers, 3 required, 2 adversarial',5,3,2,.95),
        ('5 signers, 3 required, 3 adversarial',5,3,3,.95),
        ('7 signers, 4 required, 3 adversarial',7,4,3,.90),
        ('7 signers, 4 required, 4 adversarial',7,4,4,.90),
    ]
    rows=[]
    for i,(label,n,t,f,p) in enumerate(scenarios):
        exact=policy_exact(n,t,f,p,hit)
        monte=policy_simulated(n,t,f,p,trials=trials,seed=DEFAULT_SEED+i)
        row={'scenario':label,**exact,
             'mc_publish_probability':monte['publish_probability'],
             'mc_attacker_hit_among_published':monte['attacker_hit_among_published'],
             'mc_trials':trials}
        rows.append(row)
    with (out_dir/'threshold_bias_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'assumptions':{
        'registry':DEFAULT_N,'attacker_controlled_ids':DEFAULT_ATTACKER_IDENTITIES,
        'committee_seats':DEFAULT_SEATS,'independent_honest_online_probability':'scenario-specific',
        'cryptographic_threshold_vrf':'IDEAL ORACLE ONLY; NOT IMPLEMENTED',
        'attacker_strategy':'withhold only when not forced by >=t honest responders, and outcome unfavorable',
        'random_seed':DEFAULT_SEED,'trials_per_scenario':trials,
        'network_or_real_chain_measurements':False},
        'baseline_hit_probability':hit,'scenarios':rows}
    (out_dir/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--trials',type=int,default=DEFAULT_TRIALS)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent)
    args=parser.parse_args()
    outcome=run_experiment(args.output,trials=args.trials)
    print(json.dumps({'ideal_hit':outcome['baseline_hit_probability'],
                      'scenarios':[{k:r[k] for k in ('scenario','publish_probability','attacker_hit_among_published')} for r in outcome['scenarios']]},indent=2))
