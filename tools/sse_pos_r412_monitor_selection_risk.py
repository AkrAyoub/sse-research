#!/usr/bin/env python3
"""Exact ideal-sampling risk model; not a measurement of V3/V4 entropy or operators."""
import argparse
import json
from math import comb
from fractions import Fraction

def risk(population, adversarial, seats):
    if any(type(v) is not int for v in (population,adversarial,seats)):
        raise ValueError("integer counts required")
    if not 4 <= seats <= population or not 0 <= adversarial <= population:
        raise ValueError("invalid committee or population")
    b=(seats-1)//3
    q=seats-b
    denominator=comb(population,seats)
    distribution={}
    for i in range(max(0,seats-(population-adversarial)),min(seats,adversarial)+1):
        distribution[i]=Fraction(comb(adversarial,i)*comb(population-adversarial,seats-i),denominator)
    assert sum(distribution.values())==1
    exceeded=sum((p for i,p in distribution.items() if i>b),Fraction(0))
    quorum=sum((p for i,p in distribution.items() if i>=q),Fraction(0))
    unavailable=sum((p for i,p in distribution.items() if seats-i<q),Fraction(0))
    return {"population":population,"adversarialIdentities":adversarial,"seats":seats,"quorum":q,
            "modeledByzantineTolerance":b,"assumptionExceeded":exceeded,"attackerQuorum":quorum,
            "honestOnlyQuorumUnavailableIfAdversaryAbstains":unavailable,"distribution":distribution}

def render(v):
    if isinstance(v,Fraction):
        return {"numerator":v.numerator,"denominator":v.denominator,"probability":float(v)}
    if isinstance(v,dict):return {k:render(x) for k,x in v.items()}
    return v

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--population",type=int,required=True)
    p.add_argument("--adversarial",type=int,required=True)
    p.add_argument("--seats",type=int,required=True)
    a=p.parse_args()
    print(json.dumps({"schema":"SSE_IDEAL_MONITOR_SAMPLING_RISK_V1",
        "model":"Uniform sampling without replacement from a fixed known eligible identity population",
        "observedNetworkRisk":False,"operatorIndependenceProved":False,
        "appliesToV3GlobalSelection":False,"result":render(risk(a.population,a.adversarial,a.seats))},indent=2))
if __name__=="__main__":main()
