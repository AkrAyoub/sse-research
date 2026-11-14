"""Exact combinatorial withholding/retry risk, NO actual VRF or network calls."""
from __future__ import annotations
import csv
import json
from math import comb
from pathlib import Path

N=160; A=40; K=4
HIT = 1 - comb(N-A, K)/comb(N, K)


def rows():
    results=[]
    for attempts in (1,2,3,5,10):
        # Assumption: independent ideal random draws, adversary can inspect
        # each result and abandon an unfavorable one before a subsequent draw.
        favourable=1-(1-HIT)**attempts
        results.append(dict(attempts=attempts, attack_identity_share=A/N,
                            ideal_single_hit_probability=HIT,
                            ability_to_find_favourable_by_any_attempt=favourable,
                            relative_increase_percentage_points=100*(favourable-HIT),
                            model='ideal independent draws; adaptive abort/retry'))
    # Availability-only (not bias reduction): external coordinator responds
    # at probability p independently, but false additional draws forbidden.
    response_availability=[0.90,0.95,0.99]
    for p in response_availability:
        results.append(dict(attempts=1, attack_identity_share=A/N,
                            ideal_single_hit_probability=HIT,
                            ability_to_find_favourable_by_any_attempt=HIT,
                            relative_increase_percentage_points=0,
                            model=f'fixed one draw; coordinator online prob={p:.2f}; ' 
                                  f'resolve prob={p:.2f}; expire prob={1-p:.2f}'))
    return results


def main():
    out=Path(__file__).resolve().parent
    data=rows()
    with (out/'reroll_attack_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(data[0]))
        writer.writeheader();writer.writerows(data)
    summary={
        'model':'ideal uniform-without-replacement, 160 identities, 40 adversary, committee=4',
        'single_draw_hit_probability':HIT,
        'reroll_two_draw_hit_probability':1-(1-HIT)**2,
        'reroll_three_draw_hit_probability':1-(1-HIT)**3,
        'worst_case_selective_publish_given_success':1.0,
        'worst_case_single_draw_publish_probability':HIT,
        'policy':'one immutable coordinator-bound request; no resampling after expire; no blockhash fallback',
        'caveat':'does not cure coordinator withholding; theoretical attack surface only, NOT implementation proof',
        'rows':data
    }
    (out/'experiment_results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
